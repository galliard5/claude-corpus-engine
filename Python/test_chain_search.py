#!/usr/bin/env python3
"""
test_chain_search.py — Self-test for chain search and version-checked fetches (chain-aware search, stage 3).

Everything runs in process against synthetic modules, campaigns, corpora and registries in temporary directories;
the builder's history log is redirected. Nothing is written to the real corpus or index, and nothing here reads it.

THE CONTRACTS THESE TESTS PIN (design: Working_Documents/Chain_Search_Design_Proposal_v2.md §2, §3, §5, §6;
decisions Codex 938, refinement A; approval Codex 955)
  Grouping     search_corpus(campaign=... | chain=...) queries each indexed layer's own database with its own ranking
               and groups the hits by layer, most specific first; no score is shown, so none is compared across
               databases. The header lists every layer — declared-loaded ones as not searched — with its hit count,
               zero included.
  Bounds       limit is the total cap (default 10, ceiling 200) and per_layer (default min(5, limit)) the cap per
               layer; every layer with a hit gets one slot, the rest go most specific first. When limit is below the
               number of layers with hits the search refuses, naming the smallest workable limit (refinement A). A
               chain holds at most eight layers.
  Refusals     a chain that cannot be searched as declared searches nothing and opens no layer database; a changed
               or unknown source warns conspicuously on its group and the search runs; non-authoritative retrieval
               is labelled.
  Relations    every hit carries the declarations naming it in the active chain (both layers in the chain; others
               counted), each with its mode worded as declared (complementary modes never as displacing), its status,
               its pin's currentness recomputed against the target layer in the same snapshot (current, changed,
               unpinned, orphaned), any older build it was validated against, and its self-declared decider. A hit no
               declaration names says "no override recorded", explicitly not a claim that it governs. Several
               declarations of one unit are listed, never collapsed, and flagged unresolved (conflicting when an
               override is among them). An indexed higher layer that declares nothing about a hit is noted.
  Snapshot     one registry read per search; every layer database is opened from that snapshot and checked to be the
               build it named before any query; a database gone since refuses the search; a generation published
               meanwhile is never used.
  Fetch        get_section and get_system_record take expected_build: served only from that build, refused when the
               module was rebuilt (or the id is wrong), checked again on the connection the content is read from; the
               fetch tools read schema 3, while single-system search and status point a layered module at chain=.
  Compatible   every call without the new parameters produces exactly the output the committed stage-2 server
               produces, on the same synthetic corpus and modules.
  Containment  a chain search opens nothing outside the corpus: a junctioned module, a registry entry or generation
               file leading out, and a campaign reached through a link all refuse unread.
  Robustness   a manifest, index.cfg or profile that is not valid UTF-8 refuses (its own module, campaign or
               adaptation) and breaks nothing else; an exception from the embedding lane comes back as a message;
               a connection whose vector extension fails to load is closed; a published generation is opened
               immutable, so a -wal or -journal planted beside it is never read.

Usage:
    python -m unittest test_chain_search -v
    python test_chain_search.py [--no-pause]

Command line arguments:
    --no-pause   Skip end-of-run pause

# changed 2026-11-12: created (chain-aware search stage 3, Codex 955).
# changed 2026-11-14: TestAuditRobustness — audit batch 1 (undecodable inputs, the chain search catch-all, the
#   connection closed when its extension fails to load, published generations opened immutable).
"""

import argparse
import re
import sqlite3
import subprocess
import sys
import time
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_indexes as bi       # noqa: E402
import rules_chain as rc         # noqa: E402
import search_mcp_server as srv  # noqa: E402
import system_index as si        # noqa: E402
import test_chain as tc          # noqa: E402
from test_layers import CORE_MD, PRIVATE, make_base, make_layer, manifest, relation, write  # noqa: E402

STAGE2 = "43a3f9102d906cfcf0e4c005864c5f32059d1b88"     # the stage-2 commit: the server before stage 3
HIT = re.compile(r"^(\d+)\. (\S+)  \[([a-z0-9_]+) rank (\d+)\]$", re.M)
QUERY = "fatigue OR march OR rope"


def rel_item(entry_key, target_layer, target_key, mode="extend", status="open", entry_section=None,
             target_section=None, extra=""):
    """One relations.yaml item, for layers the shared helper does not cover."""
    es = f", section: {{heading: \"{entry_section[0]}\", level: {entry_section[1]}}}" if entry_section else ""
    ts = f", section: {{heading: \"{target_section[0]}\", level: {target_section[1]}}}" if target_section else ""
    return (f"- entry: {{key: \"{entry_key}\"{es}}}\n  target: {{layer: {target_layer}, key: \"{target_key}\"{ts}}}\n"
            f"  mode: {mode}\n  status: {status}{extra}\n")


class ChainFixture(tc.Fixture):
    """test_chain's fixture — Baseline (declared loaded), basesys (schema 2), hb (schema 3, extending basesys,
    declaring one open, unpinned extend of basesys core.md § Fatigue) — with chain-search helpers."""

    def build(self, cfg):
        return bi.build_and_publish(self.root, self.index, cfg, build_vectors=False)

    def call(self, fn, **kw):
        with mock.patch.object(srv, "_CORPUS_ROOT", self.root), \
                mock.patch.object(srv, "SYSTEMS_DIR", si.systems_dir(self.index)), \
                mock.patch.object(srv, "RULES_CFG_PATH", self.cfg_path), \
                mock.patch.object(srv, "DB_PATH", self.index / "search_index.db"):
            return fn(**kw)

    def search(self, query=QUERY, **kw):
        return self.call(srv.search_corpus, query=query, **kw)

    def section(self, **kw):
        return self.call(srv.get_section, **kw)

    def record(self, **kw):
        return self.call(srv.get_system_record, **kw)

    def relations(self, text):
        """Replace hb's relations.yaml and rebuild hb."""
        write(self.hb_cfg.parent / si.RELATIONS_FILE, text)
        self.hb = self.build(self.hb_cfg)

    def rewrite_core(self, text):
        write(self.root / "Game_Systems" / "Basesys" / "rules" / "core.md", text)
        self.base = self.build(self.base_cfg)

    def gen(self, module):
        return si.resolve_db(si.systems_dir(self.index), module, self.registry()["systems"][module])

    def unit(self, module, key, section=None):
        conn = sqlite3.connect(f"{self.gen(module).as_uri()}?mode=ro", uri=True)
        try:
            h, why = si.resolve_unit(conn, si.Address(module, key, section))
        finally:
            conn.close()
        self.assertIsNone(why)
        return h

    def hits(self, out):
        return [(m[2], m[3]) for m in HIT.finditer(out)]

    def group(self, out, module):
        """The text of one layer's group, from its == line to the next group or the end."""
        start = out.index(f"\n== {module} — ")
        nxt = out.find("\n== ", start + 1)
        return out[start:nxt if nxt != -1 else len(out)]

    def hit_text(self, out, n):
        """The lines of hit number n."""
        start = re.search(rf"^{n}\. ", out, re.M).start()
        m = re.search(r"^(\d+\. |== |\(~N)", out[start + 2:], re.M)
        return out[start:start + 2 + m.start()] if m else out[start:]


# ================================================================ grouping and output

class TestGrouping(ChainFixture):
    def test_grouped_by_layer_most_specific_first(self):
        out = self.search(chain="baseline,basesys,hb")
        self.assertEqual(self.hits(out), [("notes/house.md", "hb"), ("rules/core.md", "basesys"),
                                          ("data/items.jsonl", "basesys")])
        self.assertLess(out.index("== hb — homebrew, schema 3"), out.index("== basesys — system, schema 2"))
        for want in ("    hb: 1 hit(s) shown", "    basesys: 2 hit(s) shown",
                     "    baseline: not searched (declared loaded) — its content, and any change to it, are "
                     "invisible to this search", "  Bounds:     limit 10, per_layer 5; 3 hit(s) shown",
                     "scores are never compared across layers, so none are shown",
                     f"  Snapshot:   {self.resolve(chain='baseline,basesys,hb').token}",
                     f'   Fetch: get_section(path="notes/house.md", system="hb", expected_build="{self.hb.build_id}")',
                     f'   Fetch: get_system_record(system="basesys", entry_key="rec:items/item/rope", '
                     f'expected_build="{self.base.build_id}")'):
            self.assertIn(want, out)
        self.assertNotIn("[score:", out)
        self.assertNotIn("rrf:", out)

    def test_each_layer_is_queried_alone_and_scores_never_order_the_groups(self):
        real = srv._run_lanes
        seen = []

        def lanes(conn, *a):
            scored, label = real(conn, *a)
            module = conn.execute("SELECT module FROM db_info").fetchone()[0]
            seen.append(module)
            # Make the less specific layer score enormously better: grouping must ignore it.
            return [(r, 1e9 if module == "basesys" else 1e-9) for r, _ in scored], label
        with mock.patch.object(srv, "_run_lanes", side_effect=lanes):
            out = self.search(chain="basesys,hb")
        self.assertEqual(seen, ["hb", "basesys"])                     # one call per layer, most specific first
        self.assertEqual([m for _p, m in self.hits(out)], ["hb", "basesys", "basesys"])
        self.assertNotIn("1000000000", out)

    def test_zero_hit_layers_and_no_results_are_shown(self):
        out = self.search("ZEBRAPROBE", chain="basesys,hb")
        self.assertIn("    basesys: 0 hit(s) shown", out)
        self.assertIn("== basesys — system, schema 2", out)
        self.assertIn(": 0 hit(s)", self.group(out, "basesys"))
        none = self.search("nosuchwordanywhere", chain="basesys,hb")
        self.assertIn("No results for: nosuchwordanywhere in any searched layer.", none)
        self.assertIn("    hb: 0 hit(s) shown", none)

    def test_filters_apply_to_every_layer(self):
        out = self.search(chain="basesys,hb", representation_filter="dataset")
        self.assertEqual(self.hits(out), [("data/items.jsonl", "basesys")])
        self.assertIn("[mode: fts, representation: dataset]", out)
        self.assertIn("No vector-eligible rows", self.search(chain="basesys,hb", representation_filter="dataset",
                                                             mode="vector"))
        out = self.search(chain="basesys,hb", type_filter="rules")
        self.assertEqual(self.hits(out), [("rules/core.md", "basesys")])

    def test_a_chain_with_no_indexed_layer_searches_nothing(self):
        with mock.patch.object(srv, "_open_readonly", side_effect=AssertionError("opened")):
            out = self.search(chain="baseline")
        self.assertIn("Nothing was searched: no layer in this chain is indexed", out)
        self.assertIn("1. baseline: declared loaded, not searched", out)

    def test_argument_errors(self):
        cases = [({"system": "basesys", "chain": "hb"}, "Give at most one of system, campaign or chain"),
                 ({"campaign": "camp_one", "chain": "hb"}, "Give at most one of system, campaign or chain"),
                 ({"per_layer": 2}, "per_layer needs campaign or chain"),
                 ({"system": "basesys", "per_layer": 2}, "per_layer needs campaign or chain"),
                 ({"chain": "hb", "per_layer": 0}, "per_layer must be a whole number >= 1"),
                 ({"chain": "hb", "per_layer": True}, "per_layer must be a whole number >= 1"),
                 ({"chain": "hb", "per_layer": 201}, "exceeds the safety ceiling of 200"),
                 ({"chain": "hb", "limit": 0}, "limit must be >= 1"),
                 ({"chain": "hb", "limit": 201}, "exceeds the safety ceiling of 200"),
                 ({"chain": "hb", "mode": "nope"}, "Invalid mode"),
                 ({"chain": "hb", "missing_filter": "nope"}, "Invalid missing_filter"),
                 ({"chain": "hb", "representation_filter": "nope"}, "Invalid representation_filter")]
        for kw, want in cases:
            with self.subTest(kw=kw):
                self.assertIn(want, self.search(**kw))
        self.assertNotIn("Give at most one", self.search(system="", chain="hb"))

    def test_vector_modes_degrade_per_layer_and_say_so(self):
        with mock.patch.object(srv.embedding, "AVAILABLE", False):
            out = self.search(chain="basesys,hb", mode="hybrid")
        self.assertIn("vector lane unavailable (deps not installed) - using fts", out)
        with mock.patch.object(srv.embedding, "AVAILABLE", True), mock.patch.object(srv.embedding, "load_vec"):
            out = self.search(chain="basesys,hb", mode="vector")
        self.assertIn("    hb: 1 hit(s) shown (no vector table - fts)", out)
        self.assertIn("(no vector table - fts)", out.split("    basesys:")[1].splitlines()[0])

    def test_sections_and_records_point_at_the_right_fetch(self):
        big = "# Big\n\n" + "".join(f"## Part {i}\n\n" + ("fatigue words here. " * 60) + "\n\n" for i in range(12))
        write(self.root / "Game_Systems" / "Basesys" / "rules" / "big.md", big)
        self.base = self.build(self.base_cfg)
        out = self.search("fatigue", chain="basesys")
        self.assertIn("   Sections: Big (~", out)
        self.assertIn("get_section(path, heading, system, expected_build) returns one section", out)


# ================================================================ refusals and warnings

class TestRefusalsAndWarnings(ChainFixture):
    def test_a_refused_chain_searches_nothing(self):
        write(self.camp1 / "Campaign_Profile.md", tc.profile(["Baseline", "Basesys"], homebrew="[gone.md]"))
        for kw in ({"chain": "baseline,ghost"}, {"chain": "basesys,basesys"}, {"campaign": "nowhere"},
                   {"campaign": "camp_one"}, {"chain": ",".join(["basesys"] * 9)}):
            with self.subTest(kw=kw), mock.patch.object(srv, "_open_readonly",
                                                         side_effect=AssertionError("a layer was opened")):
                out = self.search(**kw)
                self.assertTrue(out.startswith(f"No search was run for: {QUERY}\n\n[!] Chain refused"), out)
                self.assertNotIn("Fetch:", out)
        self.assertIn("declared sidecar World_Building/Setting_A/Scenarios/Camp_One/gone.md does not exist",
                      self.search(campaign="camp_one"))

    def test_changed_or_unknown_sources_warn_on_their_group_and_the_search_runs(self):
        write(self.root / "Game_Systems" / "Basesys" / "rules" / "core.md", CORE_MD + "\nEdited.\n")
        out = self.search(chain="basesys,hb")
        self.assertIn("[!] SOURCES CHANGED since this build — its hits may not match the files",
                      self.group(out, "basesys"))
        self.assertNotIn("SOURCES CHANGED", self.group(out, "hb"))
        self.assertIn("    [!] basesys: SOURCES CHANGED since the build", out)
        self.assertEqual(len(self.hits(out)), 3)
        (self.root / "Game_Systems" / "Basesys" / "index.cfg").unlink()     # a legacy folder still; cfg gone
        out = self.search(chain="basesys,hb")
        self.assertIn("   [!] sources unknown: could not recompute", self.group(out, "basesys"))
        self.assertEqual(len(self.hits(out)), 3)

    def test_non_authoritative_retrieval_is_labelled(self):
        self.assertIn("Retrieval:  [!] NON-AUTHORITATIVE", self.search(chain="baseline,basesys"))
        out = self.search(campaign="camp_one")
        self.assertIn("Retrieval:  adaptation inputs current", out)
        self.assertNotIn("NON-AUTHORITATIVE", out)

    def test_declared_sidecars_are_said_to_be_unsearched(self):
        write(self.camp1 / "homebrew_campaign.md", "house notes\n")
        write(self.camp1 / rc.PROFILE_FILE, tc.profile(["Baseline", "Basesys"], homebrew="[homebrew_campaign.md]"))
        out = self.search(campaign="camp_one")
        self.assertIn("  Sidecars:   declared loaded and not searched — their content, and any change to them, are "
                      "invisible to this search.", out)
        self.assertNotIn("  Sidecars:   declared loaded", self.search(chain="basesys,hb"))

    def test_the_reviewed_repro_a_malformed_relation_mode(self):
        """957 (2): a declaration the builder could never have written is refused before anything renders."""
        conn = sqlite3.connect(self.gen("hb"))
        try:
            conn.execute("UPDATE relations SET mode = '{'")
            conn.commit()
        finally:
            conn.close()
        out = self.search(chain="basesys,hb")
        self.assertTrue(out.startswith(f"No search was run for: {QUERY}"), out)
        self.assertIn("[!] Chain search refused — hb: its schema-3 database has unreadable layer tables (relations "
                      "item 1: mode '{' is not one of override, add, extend, partition, fall_through, n_a); rebuild "
                      "it (build_indexes.py --system hb)", out)
        self.assertEqual(self.hits(out), [])
        self.assertNotIn("Fetch:", out)

    def test_broken_layer_tables_refuse_rather_than_read_as_no_relations(self):
        for sql in ("DELETE FROM layer_info", "DROP TABLE relations", "UPDATE layer_info SET depends_on = '[1]'",
                    "UPDATE layer_info SET depends_on = '{\"basesys\": 5}'",
                    "UPDATE relations SET target_section = '{\"heading\": 5}'",
                    "UPDATE relations SET target_section = '{\"heading\": \"Fatigue\", \"level\": 9}'",
                    "UPDATE relations SET target_section = '{\"heading\": \" - \", \"level\": 2}'",
                    "UPDATE relations SET mode = '{'", "UPDATE relations SET mode = 'governs'",
                    "UPDATE relations SET status = 'approved'", "UPDATE relations SET item = 'x'",
                    "UPDATE relations SET entry_key = 'not a key'", "UPDATE relations SET target_key = 'doc:a b'",
                    "UPDATE relations SET target_layer = 'Bad-Layer'", "UPDATE relations SET declared_sha256 = 'xyz'",
                    "UPDATE relations SET decided = 'yesterday'",
                    "UPDATE relations SET target_key = 'rec:items/item/rope'"):
            with self.subTest(sql=sql):
                self.hb = self.build(self.hb_cfg)
                conn = sqlite3.connect(self.gen("hb"))
                try:
                    conn.execute(sql)
                    conn.commit()
                finally:
                    conn.close()
                out = self.search(chain="basesys,hb")
                self.assertIn("[!] Chain search refused — hb: its schema-3 database has unreadable layer tables", out)
                self.assertEqual(self.hits(out), [])

    def test_the_timeout_guard_covers_every_layer(self):
        with mock.patch.object(srv, "_QUERY_TIMEOUT_S", -1.0), mock.patch.object(srv, "_PROGRESS_STEPS", 1):
            out = self.search(chain="basesys,hb")
        self.assertIn("[!] Search aborted: query exceeded the", out)

    def test_an_older_dependency_build_is_shown_on_the_layer_and_its_relations(self):
        self.base = self.build(self.base_cfg)                    # basesys rebuilt; hb validated against the old one
        out = self.search(chain="basesys,hb")
        self.assertIn("[!] relations validated against an older build of basesys", self.group(out, "hb"))
        self.assertIn(f"validated against an older build of basesys (", self.hit_text(out, 2))


# ================================================================ relation lines

class TestRelationStatuses(ChainFixture):
    FATIGUE = ("Fatigue", 2)

    def core_hit(self, out):
        n = next(i for i, (p, m) in enumerate(self.hits(out), 1) if (p, m) == ("rules/core.md", "basesys"))
        return self.hit_text(out, n)

    def test_unpinned_open_is_reported_as_declared(self):
        out = self.search(chain="basesys,hb")
        core = self.core_hit(out)
        self.assertIn("   Relations: § 'Fatigue' (level 2): declared: extended by hb (hb:doc:notes/house.md § "
                      "'Forced March' (level 2)) — open; unpinned, currentness unknown; self-declared in hb "
                      "relations.yaml item 1", core)
        self.assertNotIn("higher layer present", core)
        self.assertIn("   Declares: § 'Forced March' (level 2) declares extend of basesys:doc:rules/core.md § "
                      "'Fatigue' (level 2) — open; unpinned", self.hit_text(out, 1))
        self.assertIn("  Relations:  1 declaration(s) within this chain, 0 outside it (ignored)", out)

    def test_a_pinned_current_target(self):
        pin = self.unit("basesys", "doc:rules/core.md", self.FATIGUE)
        self.relations(relation(pin=pin, status="settled", extra="\n  decided: 2026-10-18\n  decider: steward"))
        core = self.core_hit(self.search(chain="basesys,hb"))
        self.assertIn("— settled; pinned; the target is unchanged since declared; self-declared by steward on "
                      "2026-10-18 in hb relations.yaml item 1", core)

    def test_a_changed_target_and_an_orphaned_one(self):
        pin = self.unit("basesys", "doc:rules/core.md", self.FATIGUE)
        self.relations(relation(pin=pin))
        self.rewrite_core(CORE_MD.replace("one fatigue level", "two fatigue levels"))
        core = self.core_hit(self.search(chain="basesys,hb"))
        self.assertIn("[!] target changed since declared", core)
        self.assertIn(f"validated against an older build of basesys (", core)
        self.rewrite_core(CORE_MD.replace("## Fatigue", "## Weariness"))
        out = self.search(chain="basesys,hb")
        orphan = "[!] ORPHANED — the target no longer resolves (no level-2 section 'Fatigue'"
        self.assertIn(orphan, self.hit_text(out, 1))               # hb's own Declares line reports it
        core = self.core_hit(out)                                  # and so does the document it still names
        self.assertIn("§ 'Fatigue' (level 2): declared: extended by hb", core)
        self.assertIn(orphan, core)
        self.assertNotIn("no override recorded", core)

    def test_every_mode_is_worded_as_declared_and_complementary_modes_never_displace(self):
        for mode, phrase in rc.MODE_PHRASES.items():
            with self.subTest(mode=mode):
                self.relations(relation(mode=mode))
                core = self.core_hit(self.search(chain="basesys,hb"))
                self.assertIn(phrase.format(layer="hb") + " (hb:doc:notes/house.md", core)
        for mode in ("add", "extend", "partition", "fall_through"):
            self.assertNotIn("override", rc.MODE_PHRASES[mode])
            self.assertTrue(rc.MODE_PHRASES[mode].startswith("declared: "))

    def test_several_declarations_are_listed_and_never_collapsed(self):
        two = relation(mode="override") + relation(mode="override", entry_heading=None)
        self.relations(two)
        core = self.core_hit(self.search(chain="basesys,hb"))
        self.assertEqual(core.count("declared override by hb"), 2)
        self.assertIn("§ 'Fatigue' (level 2): [!] conflicting declarations: unresolved (2 declarations, 2 "
                      "override(s); search does not reconcile them)", core)
        self.relations(relation(mode="extend") + relation(mode="add", entry_heading=None))
        core = self.core_hit(self.search(chain="basesys,hb"))
        self.assertIn("several declarations (2): unresolved — search does not reconcile them", core)
        self.assertNotIn("conflicting", core)

    def test_the_reviewed_repro_equivalent_headings_are_one_unit(self):
        """957 (3): two spellings that select one section are grouped as one unit, so their conflict shows."""
        self.relations(rel_item("doc:notes/house.md", "basesys", "doc:rules/core.md", mode="override",
                                target_section=("Fatigue", 2))
                       + rel_item("doc:notes/house.md", "basesys", "doc:rules/core.md", mode="override",
                                  entry_section=("Forced March", 2), target_section=("fatigue", 2)))
        core = self.core_hit(self.search(chain="basesys,hb"))
        self.assertEqual(core.count("declared override by hb"), 2)
        self.assertEqual(core.count("§ 'Fatigue' (level 2): declared override by hb"), 2)    # one unit, one label
        self.assertIn("[declared as § 'fatigue']", core)                                    # its own spelling kept
        self.assertIn("§ 'Fatigue' (level 2): [!] conflicting declarations: unresolved (2 declarations, 2 "
                      "override(s); search does not reconcile them)", core)

    def test_distinct_targets_stay_distinct(self):
        for second in (("Healing", 2), None):          # another section, and the whole document
            with self.subTest(second=second):
                self.relations(rel_item("doc:notes/house.md", "basesys", "doc:rules/core.md", mode="override",
                                        target_section=("Fatigue", 2))
                               + rel_item("doc:notes/house.md", "basesys", "doc:rules/core.md", mode="override",
                                          entry_section=("Forced March", 2), target_section=second))
                core = self.core_hit(self.search(chain="basesys,hb"))
                self.assertEqual(core.count("declared override by hb"), 2)
                self.assertNotIn("conflicting", core)
                self.assertNotIn("several declarations", core)
                self.assertNotIn("[declared as", core)

    def test_unit_identity(self):
        same = rc.unit_identity("basesys", "doc:a.md", ("Fatigue", 2))
        self.assertEqual(same, rc.unit_identity("basesys", "doc:a.md", ("  fatigue ", 2)))
        self.assertEqual(rc.unit_identity("b", "doc:a.md", ("The Estate’s Week — Supply", 2)),
                         rc.unit_identity("b", "doc:a.md", ("the estate's week - supply", 2)))
        for other in (rc.unit_identity("basesys", "doc:a.md", ("Fatigue", 3)),       # another level
                      rc.unit_identity("basesys", "doc:a.md", None),                 # the whole entry
                      rc.unit_identity("basesys", "doc:b.md", ("Fatigue", 2)),       # another key
                      rc.unit_identity("other", "doc:a.md", ("Fatigue", 2))):        # another layer
            self.assertNotEqual(same, other)

    def test_active_chain_scoping(self):
        out = self.search(chain="hb")
        self.assertIn("  Relations:  0 declaration(s) within this chain, 1 outside it (ignored)", out)
        self.assertNotIn("Declares:", out)
        self.assertIn("extends basesys, which this chain does not include", out)

    def test_a_target_layer_declared_loaded_is_not_assessed(self):
        extra = make_base(self.root, dirname="Extra", module="extra")
        self.build(extra)
        self.relations(relation() + rel_item("doc:notes/house.md", "extra", "doc:rules/core.md"))
        reg_path = si.systems_dir(self.index) / si.REGISTRY
        reg = self.registry()
        del reg["systems"]["extra"]                          # unpublished since, and now declared loaded instead
        reg_path.write_text(__import__("json").dumps(reg), encoding="utf-8")
        self.rules(f"[rules_layers]\nprivate_roots = {PRIVATE}\nnot_searched = baseline, extra\n")
        out = self.search(chain="basesys,extra,hb")
        house = self.hit_text(out, 1)
        self.assertIn("declares extend of extra:doc:rules/core.md — open; the target layer extra is not searched in "
                      "this chain; currentness unknown", house)
        self.assertIn("    extra: not searched (declared loaded)", out)
        self.assertIn("depends on extra, which is no longer published", out)

    def test_no_override_and_undeclared_higher_layers(self):
        out = self.search(chain="basesys,hb")
        rope = self.hit_text(out, 3)
        self.assertIn(f"   Relations: {rc.NO_OVERRIDE}", rope)
        self.assertIn("              higher layer present, relation undeclared: hb", rope)
        self.assertIn(f"   Relations: {rc.NO_OVERRIDE}", self.hit_text(out, 1))
        self.assertNotIn("higher layer present", self.hit_text(out, 1))
        # "governs" appears only in negations: nothing is ever presented as governing.
        allowed = ("not a claim that it governs", "never decides which rule governs")
        for line in out.splitlines():
            if "govern" in line:
                self.assertTrue(any(a in line for a in allowed), line)

    def test_relation_lines_are_capped_and_counted(self):
        entries = [None, ("Forced March", 2), ("House Rules", 1)]
        targets = [None, ("Fatigue", 2), ("Healing", 2), ("Deep Rest", 3), ("Core Rules", 1)]
        text = "".join(rel_item("doc:notes/house.md", "basesys", "doc:rules/core.md", entry_section=e,
                                target_section=t) for e in entries for t in targets)
        self.relations(text)
        out = self.search(chain="basesys,hb")
        core = self.core_hit(out)
        self.assertEqual(core.count("declared: extended by hb"), rc.MAX_RELATION_LINES)
        self.assertIn("+5 more declaration(s) name this entry, not shown", core)
        house = self.hit_text(out, 1)
        self.assertEqual(house.count("   Declares: "), rc.MAX_RELATION_LINES + 1)
        self.assertIn("+5 more declaration(s) by this entry, not shown", house)


# ================================================================ bounds

class TestBounds(ChainFixture):
    def build_eight(self):
        cfgs = [make_base(self.root, dirname=f"M{i}", module=f"m{i}") for i in range(1, 9)]
        for c in cfgs:
            self.build(c)
        return ",".join(f"m{i}" for i in range(1, 9))

    def per_group(self, out):
        return {m: n for m, n in re.findall(r"^    ([a-z0-9_]+): (\d+) hit\(s\) shown", out, re.M)}

    def test_refinement_a_refuses_with_the_minimum_limit(self):
        out = self.search(chain="basesys,hb", limit=1)
        self.assertTrue(out.startswith(f"No results were returned for: {QUERY}"), out)
        self.assertIn("2 searched layers have hits, but limit is 1", out)
        self.assertIn("Search again with limit=2 or more", out)
        self.assertNotIn("Fetch:", out)
        self.assertEqual(self.hits(out), [])
        ok = self.search(chain="basesys,hb", limit=2)
        self.assertEqual(self.hits(ok), [("notes/house.md", "hb"), ("rules/core.md", "basesys")])
        self.assertIn("    basesys: 1 hit(s) shown, more matched", ok)

    def test_per_layer_caps_each_layer(self):
        out = self.search(chain="basesys,hb", per_layer=1)
        self.assertEqual(self.per_group(out), {"hb": "1", "basesys": "1"})
        self.assertIn("    basesys: 1 hit(s) shown, more matched", out)
        self.assertIn("  Bounds:     limit 10, per_layer 1; 2 hit(s) shown", out)
        self.assertIn("per_layer 2;", self.search(chain="basesys,hb", limit=2))       # default min(5, limit)

    def test_an_eight_layer_chain(self):
        chain = self.build_eight()
        out = self.search(chain=chain, limit=7)
        self.assertIn("8 searched layers have hits, but limit is 7", out)
        self.assertIn("limit=8 or more", out)
        out = self.search(chain=chain, limit=8)
        self.assertEqual(self.per_group(out), {f"m{i}": "1" for i in range(1, 9)})
        out = self.search(chain=chain, limit=12)
        want = {f"m{i}": ("2" if i >= 5 else "1") for i in range(1, 9)}          # extras go most specific first
        self.assertEqual(self.per_group(out), want)
        self.assertEqual(len(self.hits(out)), 12)
        self.assertEqual([m for _p, m in self.hits(out)][:2], ["m8", "m8"])
        for limit, per_layer in ((8, 1), (8, 5), (9, 1), (16, 2), (16, 5), (200, 1), (200, 5), (13, 3)):
            with self.subTest(limit=limit, per_layer=per_layer):
                out = self.search(chain=chain, limit=limit, per_layer=per_layer)
                counts = [int(n) for n in self.per_group(out).values()]
                self.assertEqual(len(counts), 8)
                self.assertLessEqual(sum(counts), limit)
                self.assertTrue(all(1 <= c <= min(per_layer, 2) for c in counts), counts)
                self.assertEqual(sum(counts), min(limit, 8 * min(per_layer, 2)))
                self.assertEqual(len(self.hits(out)), sum(counts))
        out = self.search(chain=chain + ",basesys")
        self.assertIn("the chain has 9 layers; at most 8 are allowed", out)
        self.assertTrue(out.startswith("No search was run"))

    def test_allocate(self):
        import itertools
        for counts in itertools.product(range(0, 4), repeat=4):
            for limit in range(1, 10):
                for per_layer in range(1, 5):
                    slots, need = rc.allocate(list(counts), limit, per_layer)
                    matching = sum(c > 0 for c in counts)
                    if limit < matching:
                        self.assertEqual((slots, need), (None, matching))
                        continue
                    self.assertIsNone(need)
                    self.assertLessEqual(sum(slots), limit)
                    for c, s in zip(counts, slots):
                        self.assertTrue((s >= 1) == (c > 0))
                        self.assertLessEqual(s, min(c, per_layer))
                    self.assertEqual(sum(slots), min(limit, sum(min(c, per_layer) for c in counts)))
                    # most specific first: no later layer gets an extra while an earlier one could still take one
                    for i, (c, s) in enumerate(zip(counts, slots)):
                        if s < min(c, per_layer):
                            self.assertTrue(all(t <= 1 for t in slots[i + 1:]), (counts, limit, per_layer, slots))


# ================================================================ the snapshot, through query and fetch

class TestSnapshotCoherence(ChainFixture):
    def rebuild_after(self, target, module="basesys", text=None):
        """A wrapper around `target` that rebuilds `module` (with core.md replaced by `text`) once it has run."""
        real = target

        def wrapped(*a, **k):
            out = real(*a, **k)
            if text is not None:
                write(self.root / "Game_Systems" / "Basesys" / "rules" / "core.md", text)
            self.rebuilt = self.build(self.base_cfg if module == "basesys" else self.hb_cfg)
            return out
        return wrapped

    def test_the_registry_is_read_once_per_search(self):
        with mock.patch.object(si, "read_registry", side_effect=si.read_registry) as spy:
            self.search(chain="baseline,basesys,hb")
        self.assertEqual(spy.call_count, 1)

    def test_a_rebuild_between_resolution_and_query_refuses(self):
        old = self.base.build_id
        with mock.patch.object(rc, "resolve", side_effect=self.rebuild_after(rc.resolve)):
            out = self.search(chain="basesys,hb")
        self.assertIn(f"[!] Chain search refused — the database the snapshot named for basesys (build {old}) "
                      f"changed after the chain was resolved", out)
        self.assertEqual(self.hits(out), [])
        self.assertNotIn(self.rebuilt.build_id, out)

    def test_a_snapshot_path_holding_another_build_refuses(self):
        old = self.gen("basesys")
        real = rc.resolve

        def swapped(*a, **k):                      # the snapshot names the new build, but the file is the old one
            res = real(*a, **k)
            next(l for l in res.layers if l.module == "basesys").db = str(old)
            return res
        with mock.patch.object(si, "collect_garbage", return_value=[]):
            self.base = self.build(self.base_cfg)  # rebuild again: no collection, so the first file stays put
        if not old.exists():
            self.skipTest("the earlier generation was collected")
        with mock.patch.object(rc, "resolve", side_effect=swapped):
            out = self.search(chain="basesys,hb")
        self.assertIn("[!] Chain search refused — the database the snapshot named for basesys", out)
        self.assertIn("it is no longer that build", out)
        self.assertEqual(self.hits(out), [])

    def test_without_collection_the_snapshot_is_served_and_never_switched(self):
        old = self.base.build_id
        token = self.resolve(chain="basesys,hb").token
        with mock.patch.object(si, "collect_garbage", return_value=[]), \
                mock.patch.object(rc, "resolve", side_effect=self.rebuild_after(
                    rc.resolve, text=CORE_MD.replace("The opening paragraph.", "NEWBUILDPROBE fatigue."))):
            out = self.search(chain="basesys,hb")
        new = self.rebuilt.build_id
        self.assertNotEqual(old, new)
        self.assertIn(f"  Snapshot:   {token}", out)
        self.assertIn(f'expected_build="{old}"', out)
        self.assertNotIn(new, out)
        self.assertNotIn("NEWBUILDPROBE", out)
        # The fetch the hit printed now refuses: the module was rebuilt since that search.
        stale = self.section(path="rules/core.md", heading="Fatigue", system="basesys", expected_build=old)
        self.assertIn(f"[!] Refusing: build {old} is not the published build of 'basesys' (now {new})", stale)
        self.assertNotIn("Marching", stale)
        fresh = self.section(path="rules/core.md", system="basesys", heading="Core Rules", expected_build=new)
        self.assertIn("NEWBUILDPROBE", fresh)
        self.assertIn(f"[build {new}]", fresh)

    def test_a_rebuild_between_the_registry_read_and_the_open_of_a_fetch(self):
        old = self.base.build_id
        text = CORE_MD.replace("The opening paragraph.", "NEWBUILDPROBE.")
        with mock.patch.object(srv, "_resolve_system", side_effect=self.rebuild_after(srv._resolve_system,
                                                                                      text=text)):
            out = self.section(path="rules/core.md", heading="Core Rules", system="basesys", expected_build=old)
        self.assertTrue(out.startswith("[!] "), out)
        self.assertNotIn("NEWBUILDPROBE", out)
        with mock.patch.object(srv, "_resolve_system", side_effect=self.rebuild_after(srv._resolve_system)):
            out = self.record(system="basesys", entry_key="rec:items/item/rope", expected_build=self.base.build_id)
        self.assertTrue(out.startswith("[!] "), out)
        self.assertNotIn('"weight"', out)

    def test_a_database_that_is_not_the_expected_build_is_refused_on_its_connection(self):
        old_entry = dict(self.registry()["systems"]["basesys"])
        self.base = self.build(self.base_cfg)
        new_db = self.gen("basesys")
        with mock.patch.object(srv, "_resolve_system", return_value=(new_db, old_entry, None)):
            for out in (self.section(path="rules/core.md", heading="Fatigue", system="basesys",
                                     expected_build=old_entry["build_id"]),
                        self.record(system="basesys", entry_key="rec:items/item/rope",
                                    expected_build=old_entry["build_id"])):
                self.assertIn("changed while this fetch ran", out)
                self.assertNotIn("Marching", out)
                self.assertNotIn('"weight"', out)


# ================================================================ expected_build

class TestExpectedBuild(ChainFixture):
    def test_the_current_build_is_served_from_either_schema(self):
        b, h = self.base.build_id, self.hb.build_id
        out = self.section(path="rules/core.md", heading="Fatigue", system="basesys", expected_build=b)
        self.assertIn(f"rules/core.md § Fatigue  [Core Rules, rules]  [basesys · verbatim · source]  [build {b}]", out)
        out = self.section(path="notes/house.md", heading="Forced March", system="hb", expected_build=h)
        self.assertIn(f"[hb · verbatim · source]  [build {h}]", out)
        self.assertIn("ZEBRAPROBE", out)
        out = self.record(system="basesys", entry_key="rec:items/item/rope", expected_build=b)
        self.assertIn(f"rec:items/item/rope  [basesys · dataset items · gear · derived · build {b}]", out)

    def test_a_superseded_build_is_refused_by_both_fetch_tools(self):
        old = self.base.build_id
        self.rewrite_core(CORE_MD.replace("one fatigue level", "NEWBUILDPROBE"))
        new = self.base.build_id
        for out in (self.section(path="rules/core.md", heading="Fatigue", system="basesys", expected_build=old),
                    self.record(system="basesys", entry_key="rec:items/item/rope", expected_build=old)):
            self.assertIn(f"[!] Refusing: build {old} is not the published build of 'basesys' (now {new})", out)
            self.assertNotIn("NEWBUILDPROBE", out)
            self.assertNotIn('"weight"', out)

    def test_bad_expected_build_arguments(self):
        self.assertIn("expected_build needs a system", self.section(path="x.md", expected_build="abc"))
        for bad in ("", "  ", "../x", "a b", "x;y"):
            with self.subTest(bad=bad):
                self.assertIn("[!] Invalid expected_build", self.section(path="rules/core.md", system="basesys",
                                                                         expected_build=bad))
                self.assertIn("[!] Invalid expected_build", self.record(system="basesys", entry_key="rec:x/y",
                                                                        expected_build=bad))
        self.assertIn("Unknown system 'ghost'", self.record(system="ghost", entry_key="rec:x/y", expected_build="a"))

    def test_a_layered_module_is_fetched_but_searched_and_checked_through_a_chain(self):
        self.assertIn("ZEBRAPROBE", self.section(path="notes/house.md", heading="Forced March", system="hb"))
        ovl = self.build(make_base(self.root, dirname="Ovl", module="ovl", kind="variant", extends="basesys"))
        self.assertEqual(self.registry()["systems"]["ovl"]["schema_version"], si.SCHEMA_LAYERED)
        for kw in ({}, {"expected_build": ovl.build_id}):
            with self.subTest(kw=kw):
                out = self.record(system="ovl", entry_key="rec:items/item/rope", **kw)
                self.assertIn("rec:items/item/rope  [ovl · dataset items · gear · derived", out)
                self.assertIn('"weight": 1', out)
        for out in (self.search("march", system="hb"), self.call(srv.index_status, system="hb")):
            self.assertIn("'hb' is a layered module (schema 3), searched with its relations through a chain: "
                          "search_corpus(query, chain=\"hb\")", out)


# ================================================================ mixed schemas

class TestMixedSchemas(ChainFixture):
    def test_a_layer_relating_to_a_layered_layer(self):
        hb2 = make_layer(self.root, module="hb2", dirname="Hb2", kind="homebrew", extends="hb",
                         relations=rel_item("doc:notes/house.md", "hb", "doc:notes/house.md", mode="override",
                                            target_section=("Forced March", 2)))
        self.build(hb2)
        extra = make_base(self.root, dirname="Extra", module="extra")
        self.build(extra)
        out = self.search(chain="baseline,basesys,extra,hb,hb2")
        self.assertEqual([m for _p, m in self.hits(out)], ["hb2", "hb", "extra", "extra", "basesys", "basesys"])
        schemas = re.findall(r"^== ([a-z0-9]+) — \w+, schema (\d)", out, re.M)
        self.assertEqual(schemas, [("hb2", "3"), ("hb", "3"), ("extra", "2"), ("basesys", "2")])
        hb_hit = self.hit_text(out, 2)
        self.assertIn("§ 'Forced March' (level 2): declared override by hb2 (hb2:doc:notes/house.md)", hb_hit)
        self.assertIn("Declares: § 'Forced March' (level 2) declares extend of basesys:doc:rules/core.md", hb_hit)
        self.assertIn("Declares: declares override of hb:doc:notes/house.md § 'Forced March' (level 2)",
                      self.hit_text(out, 1))
        # hb2 and hb hold the same entry key: a declaration attaches by layer AND key, never by key alone.
        self.assertIn(f"   Relations: {rc.NO_OVERRIDE}", self.hit_text(out, 1))
        self.assertNotIn("declares override", hb_hit)
        self.assertIn("higher layer present, relation undeclared: hb2, hb", self.hit_text(out, 3))
        self.assertIn("  Relations:  2 declaration(s) within this chain, 0 outside it", out)


# ================================================================ containment (stage 2's guarantees, through search)

class TestContainment(ChainFixture):
    def test_a_junctioned_module_is_refused_unread(self):
        sib = Path(self._tmp.name) / "sibling"
        write(sib / "ghost.md", manifest("ghost"))
        write(sib / "index.cfg", "[system]\nmodule = ghost\n")
        self.link_dir(self.root / "Game_Systems" / "Ghost", sib)
        with mock.patch.object(si, "_read_manifest", side_effect=si._read_manifest) as rspy, \
                mock.patch.object(si, "declared_module", side_effect=si.declared_module) as dspy, \
                mock.patch.object(srv, "_open_readonly", side_effect=AssertionError("opened")):
            out = self.search(chain="basesys,ghost")
        self.assertTrue(out.startswith("No search was run"), out)
        opened = {rc._key(c.args[0]) for c in rspy.call_args_list + dspy.call_args_list}
        self.assertFalse({rc._key(sib / "ghost.md"), rc._key(sib / "index.cfg")} & opened)

    def test_a_registry_entry_or_generation_leading_out_is_never_opened(self):
        outside = Path(self._tmp.name) / "outside.db"
        outside.write_bytes(self.gen("basesys").read_bytes())
        reg_path = si.systems_dir(self.index) / si.REGISTRY
        reg = self.registry()
        reg["systems"]["basesys"]["db"] = "../../outside.db"
        reg_path.write_text(__import__("json").dumps(reg), encoding="utf-8")
        with mock.patch.object(sqlite3, "connect", side_effect=sqlite3.connect) as spy:
            out = self.search(chain="basesys,hb")
        self.assertTrue(out.startswith("No search was run"), out)
        self.assertIn("outside index/systems", out)
        self.assertFalse([c for c in spy.call_args_list if "outside.db" in str(c.args[0])])
        # A generation file that is itself a link leading out.
        reg["systems"]["basesys"]["db"] = f"basesys.{reg['systems']['basesys']['build_id']}.db"
        reg_path.write_text(__import__("json").dumps(reg), encoding="utf-8")
        gen = self.gen("basesys")
        gen.unlink()
        try:
            gen.symlink_to(outside)
        except OSError as e:
            self.skipTest(f"cannot make a file symlink here ({e})")
        with mock.patch.object(sqlite3, "connect", side_effect=sqlite3.connect) as spy:
            out = self.search(chain="basesys,hb")
        self.assertTrue(out.startswith("No search was run"), out)
        self.assertFalse([c for c in spy.call_args_list if "basesys." in str(c.args[0])
                          or "outside.db" in str(c.args[0])])

    def test_the_reviewed_repro_a_generation_leading_out_after_resolution(self):
        """957 (1): containment is enforced at the query's open, not only at resolution."""
        gen = self.gen("basesys")
        outside = Path(self._tmp.name) / "outside.db"
        real, opened, swapped = rc.resolve, [], []
        real_connect = sqlite3.connect

        def wrapped(*a, **k):
            res = real(*a, **k)
            gen.rename(outside)
            try:
                gen.symlink_to(outside)
            except OSError as e:
                outside.rename(gen)
                self.skipTest(f"cannot make a file symlink here ({e})")
            swapped.append(True)
            return res

        def spy(db, *a, **k):
            if swapped:
                opened.append(str(db))
            return real_connect(db, *a, **k)
        with mock.patch.object(rc, "resolve", side_effect=wrapped), mock.patch.object(sqlite3, "connect",
                                                                                       side_effect=spy):
            out = self.search(chain="basesys")
        self.assertTrue(out.startswith("No search was run"), out)
        self.assertIn(f"[!] Chain search refused — the database the snapshot named for basesys (build "
                      f"{self.base.build_id}) changed after the chain was resolved: it now resolves outside "
                      f"index/systems (through a link or junction), so it was not opened", out)
        self.assertEqual(self.hits(out), [])
        self.assertFalse([o for o in opened if "outside.db" in o or gen.name in o], opened)   # never opened

    def test_a_generation_swapped_during_the_open_is_never_read(self):
        real = srv._snapshot_generation
        calls = []

        def second_call_escapes(db):
            calls.append(db)
            got = real(db)
            return got if len(calls) == 1 else (None, "it now resolves outside index/systems")
        with mock.patch.object(srv, "_snapshot_generation", side_effect=second_call_escapes), \
                mock.patch.object(srv, "_run_lanes", side_effect=AssertionError("queried")):
            out = self.search(chain="basesys")
        self.assertIn("it changed while being opened, so nothing was read from it", out)
        self.assertEqual(self.hits(out), [])

    def test_a_generation_that_is_no_database_refuses(self):
        real = rc.resolve

        def wrapped(*a, **k):
            res = real(*a, **k)
            self.gen("basesys").write_bytes(b"not a database at all " * 64)
            return res
        with mock.patch.object(rc, "resolve", side_effect=wrapped):
            out = self.search(chain="basesys,hb")
        self.assertIn("[!] Chain search refused — the database the snapshot named for basesys", out)
        self.assertIn("it can no longer be opened (file is not a database)", out)
        self.assertEqual(self.hits(out), [])

    def test_the_reviewed_repro_a_fetch_redirected_after_resolution(self):
        """959: both fetch tools enforce containment at their own open, with or without expected_build."""
        gen = self.gen("basesys")
        outside = Path(self._tmp.name) / "outside.db"
        cases = [(self.section, "Marching", {"path": "rules/core.md", "heading": "Fatigue", "system": "basesys"}),
                 (self.record, '"weight"', {"system": "basesys", "entry_key": "rec:items/item/rope"})]
        for call, marker, kw in cases:
            for pinned in (False, True):
                args = dict(kw, **({"expected_build": self.base.build_id} if pinned else {}))
                with self.subTest(tool=call.__name__, expected_build=pinned):
                    self.assertIn(marker, call(**args))                    # served while contained
                    real, opened, swapped = srv._resolve_system, [], []
                    real_connect = sqlite3.connect

                    def wrapped(*a, **k):
                        got = real(*a, **k)
                        gen.rename(outside)
                        try:
                            gen.symlink_to(outside)
                        except OSError as e:
                            outside.rename(gen)
                            self.skipTest(f"cannot make a file symlink here ({e})")
                        swapped.append(1)
                        return got

                    def spy(db, *a, **k):
                        if swapped:
                            opened.append(str(db))
                        return real_connect(db, *a, **k)
                    try:
                        with mock.patch.object(srv, "_resolve_system", side_effect=wrapped), \
                                mock.patch.object(sqlite3, "connect", side_effect=spy):
                            out = call(**args)
                    finally:
                        if swapped:                                         # restore for the next case
                            gen.unlink()
                            outside.rename(gen)
                    self.assertIn("[!] Refusing the database registered for 'basesys': it now resolves outside "
                                  "index/systems (through a link or junction), so it was not opened. Nothing was "
                                  "read", out)
                    self.assertNotIn(marker, out)
                    self.assertEqual(opened, [])                            # neither path opened after the swap

    def test_a_fetch_whose_database_changes_during_the_open_reads_nothing(self):
        real = srv._snapshot_generation
        for call, kw in ((self.section, {"path": "rules/core.md", "heading": "Fatigue", "system": "basesys"}),
                         (self.record, {"system": "basesys", "entry_key": "rec:items/item/rope"})):
            calls = []

            # calls 1-2 are _resolve_system's own open (961); 3-4 are the fetch's, and the 4th, its re-check, escapes
            def fourth_call_escapes(db):
                calls.append(db)
                return real(db) if len(calls) != 4 else (None, "it now resolves outside index/systems")
            with self.subTest(tool=call.__name__), \
                    mock.patch.object(srv, "_snapshot_generation", side_effect=fourth_call_escapes), \
                    mock.patch.object(srv, "_schema_error", side_effect=AssertionError("read")):
                out = call(**kw)
                self.assertIn("[!] Refusing the database registered for 'basesys': it changed while being opened, "
                              "so nothing was read from it. Fetch again.", out)
                self.assertEqual(len(calls), 4)

    def redirect_after(self, where, call, **kw):
        """Run call(**kw) with the basesys generation renamed outside the corpus, and a file symlink left at its path,
        right after `where` (srv._resolve_system, or system_index.resolve_db for basesys) returns. Returns (output,
        every database opened after the swap); the fixture is restored afterwards."""
        gen, outside = self.gen("basesys"), Path(self._tmp.name) / "outside.db"
        opened, swapped = [], []
        real_connect = sqlite3.connect

        def swap():
            if not swapped:
                gen.rename(outside)
                try:
                    gen.symlink_to(outside)
                except OSError as e:
                    outside.rename(gen)
                    self.skipTest(f"cannot make a file symlink here ({e})")
                swapped.append(1)
        if where == "_resolve_system":
            real = srv._resolve_system

            def wrapped(*a, **k):
                got = real(*a, **k)
                swap()
                return got
            patch = mock.patch.object(srv, "_resolve_system", side_effect=wrapped)
        else:
            real = si.resolve_db

            def wrapped(sdir, module, entry):
                got = real(sdir, module, entry)
                if module == "basesys":
                    swap()
                return got
            patch = mock.patch.object(si, "resolve_db", side_effect=wrapped)

        def spy(db, *a, **k):
            if swapped:
                opened.append(str(db))
            return real_connect(db, *a, **k)
        try:
            with patch, mock.patch.object(sqlite3, "connect", side_effect=spy):
                out = call(**kw)
        finally:
            if swapped:
                gen.unlink()
                outside.rename(gen)
        self.assertTrue(swapped)
        return out, opened

    def test_the_reviewed_961_repro_a_redirect_at_each_remaining_open(self):
        """961: single-system search, _resolve_system's db_info read (behind status and both fetches) and
        check_publication (behind chain status and chain search) refuse a generation redirected after resolution,
        and open neither path once it is."""
        status = lambda **kw: self.call(srv.index_status, **kw)        # noqa: E731
        refused = ("[!] Refusing the database registered for 'basesys': it now resolves outside index/systems "
                   "(through a link or junction), so it was not opened. Nothing was read; ")
        layer = ("layer basesys: its database now resolves outside index/systems (through a link or junction), so "
                 "it was not opened")
        cases = [
            ("_resolve_system", self.search, {"system": "basesys"}, refused + "search again", "[basesys "),
            ("resolve_db", status, {"system": "basesys"}, refused + "try again.", "Publication:    consistent"),
            ("resolve_db", self.section, {"path": "rules/core.md", "heading": "Fatigue", "system": "basesys"},
             refused + "try again.", "Marching"),
            ("resolve_db", self.record, {"system": "basesys", "entry_key": "rec:items/item/rope"},
             refused + "try again.", '"weight"'),
            ("resolve_db", status, {"chain": "basesys"}, layer, "1. basesys: indexed"),
            ("resolve_db", self.search, {"chain": "basesys"}, layer, "[basesys rank "),
        ]
        for where, call, kw, refusal, served in cases:
            with self.subTest(where=where, call=getattr(call, "__name__", "index_status"), **kw):
                self.assertIn(served, call(**kw))                          # served while contained
                out, opened = self.redirect_after(where, call, **kw)
                self.assertIn(refusal, out)
                self.assertNotIn(served, out)
                self.assertEqual(opened, [])                                # neither path opened after the swap

    def test_a_database_that_changes_during_a_remaining_open_reads_nothing(self):
        """961: the re-check once open, at each remaining open — the connection is closed unread."""
        class Unread:
            def __init__(self):
                self.closed = False

            def execute(self, *a, **k):
                raise AssertionError("read from a connection whose file changed during the open")

            def close(self):
                self.closed = True
        status = lambda **kw: self.call(srv.index_status, **kw)        # noqa: E731
        # (call, kwargs, which _snapshot_generation call escapes, expected refusal): calls 1-2 are _resolve_system's
        # open, 3-4 single-system search's own
        for call, kw, nth, tail in ((status, {"system": "basesys"}, 2, "Try again."),
                                    (self.search, {"system": "basesys"}, 4, "Search again.")):
            real, calls, conns = srv._snapshot_generation, [], []

            def escapes(db):
                calls.append(db)
                return real(db) if len(calls) != nth else (None, "it now resolves outside index/systems")

            def unread(*a, **k):
                if len(calls) == nth - 1:                                  # the open the escaping re-check guards
                    conns.append(Unread())
                    return conns[-1]
                return real_open(*a, **k)
            real_open = srv._open_readonly
            with self.subTest(**kw, call=getattr(call, "__name__", "index_status")), \
                    mock.patch.object(srv, "_snapshot_generation", side_effect=escapes), \
                    mock.patch.object(srv, "_open_readonly", side_effect=unread):
                out = call(**kw)
                self.assertIn("[!] Refusing the database registered for 'basesys': it changed while being opened, "
                              f"so nothing was read from it. {tail}", out)
                self.assertEqual([c.closed for c in conns], [True])
        # check_publication (chain status and chain search): system_index.open_contained's re-check
        for call in (status, self.search):
            real, calls, conns = si.contained_real, [], []

            def escapes(path, sdir):
                calls.append(path)
                return real(path, sdir) if len(calls) != 2 else (None, "now resolves outside index/systems")

            def unread(*a, **k):
                conns.append(Unread())
                return conns[-1]
            with self.subTest(call=getattr(call, "__name__", "index_status"), chain="basesys"), \
                    mock.patch.object(si, "contained_real", side_effect=escapes), \
                    mock.patch.object(sqlite3, "connect", side_effect=unread):
                out = call(chain="basesys")
                self.assertIn("layer basesys: its database changed while being opened, so nothing was read from it",
                              out)
                self.assertEqual([c.closed for c in conns], [True])

    def test_single_system_search_keeps_its_vector_lane_through_the_check(self):
        """961 preservation: the module open passes the vector flag on unchanged (hybrid/vector load sqlite-vec, fts
        does not), and the lexical fallback on a database without a vector table still applies."""
        seen, real = [], srv._open_readonly

        def spy(load_vectors=False, db_path=None, generation=False):
            if db_path is not None and Path(db_path).name.startswith("basesys."):
                seen.append(load_vectors)
                self.assertTrue(generation)                         # a module database is opened immutable
            return real(load_vectors=False, db_path=db_path, generation=generation)
        with mock.patch.object(srv.embedding, "AVAILABLE", True), \
                mock.patch.object(srv, "_open_readonly", side_effect=spy):
            for mode, want in (("hybrid", True), ("vector", True), ("fts", False)):
                with self.subTest(mode=mode):
                    seen.clear()
                    out = self.search(system="basesys", mode=mode)
                    self.assertEqual(seen, [False, want])           # _resolve_system's db_info read, then the search
                    self.assertIn("[basesys ", out)
                    if mode != "fts":
                        self.assertIn("index has no vector table (rebuild to enable) - using fts", out)

    def test_a_campaign_reached_through_a_link_is_refused(self):
        sib = Path(self._tmp.name) / "sibling_campaign"
        write(sib / rc.PROFILE_FILE, tc.profile(["Baseline", "Basesys"]))
        self.link_dir(self.root / "World_Building" / "Setting_C" / "Scenarios" / "Linked_Camp", sib)
        with mock.patch.object(srv, "_open_readonly", side_effect=AssertionError("opened")):
            out = self.search(campaign="linked_camp")
        self.assertTrue(out.startswith("No search was run"), out)
        self.assertIn("resolves outside the corpus", out)


# ================================================================ legacy calls are byte-identical

class TestLegacyCompatibility(ChainFixture):
    """Every call without the new parameters, on the stage-3 server and on the committed stage-2 server, run side by
    side on one synthetic corpus database and module registry."""

    def setUp(self):
        super().setUp()
        big = "---\nname: Old Mill\ntype: location\n---\n# Old Mill\n\n" + "".join(
            f"## Wing {i}\n\n" + ("The warden keeps the mill. " * 40) + "\n\n" for i in range(12))
        write(self.root / "World_Building" / "Setting_A" / "Old_Mill.md", big)
        write(self.root / "World_Building" / "Setting_A" / "Steward.md", "# Steward\n\nThe steward of the mill.\n")
        write(self.root / "Game_Systems" / "Basesys" / "rules" / "big.md", big.replace("Old Mill", "Big Rules"))
        self.base = self.build(self.base_cfg)
        self.hb = self.build(self.hb_cfg)
        files = sorted((self.root / "World_Building").rglob("*.md"))
        bi.build_search_db(files, self.root, self.index / "search_index.db", -1, [], build_vectors=False)

    def old_server(self):
        src = subprocess.run(["git", "-C", str(HERE), "show", f"{STAGE2}:Python/search_mcp_server.py"],
                             capture_output=True, check=True).stdout.decode("utf-8")
        old = types.ModuleType("search_mcp_server_43a3f91")
        old.__file__ = str(HERE / "search_mcp_server.py")          # same name: messages cite the file by name
        exec(compile(src, old.__file__, "exec"), old.__dict__)
        return old

    def test_a_corpus_fetch_never_takes_the_module_check(self):
        with mock.patch.object(srv, "_open_module", side_effect=AssertionError("module check on the corpus")):
            out = self.section(path="World_Building/Setting_A/Old_Mill.md", heading="wing 3")
        self.assertIn("World_Building/Setting_A/Old_Mill.md § Wing 3", out)
        with mock.patch.object(srv, "_open_module", side_effect=AssertionError("module check on the corpus")):
            out = self.search(query="warden")                       # 961: corpus search routing unchanged too
        self.assertIn("World_Building/Setting_A/Old_Mill.md", out)

    def test_every_legacy_call_is_byte_identical(self):
        old = self.old_server()
        names = ("_CORPUS_ROOT", "SYSTEMS_DIR", "DB_PATH", "HISTORY_PATH", "RULES_CFG_PATH")
        saved = {n: getattr(srv, n) for n in names}
        for mod in (srv, old):
            mod._CORPUS_ROOT, mod.SYSTEMS_DIR = self.root, si.systems_dir(self.index)
            mod.DB_PATH = self.index / "search_index.db"
            mod.HISTORY_PATH = Path(self._tmp.name) / "history.jsonl"
            mod.RULES_CFG_PATH = self.cfg_path
        b = self.base.build_id
        calls = [
            ("search_corpus", {"query": "mill"}), ("search_corpus", {"query": "mill", "limit": 1}),
            ("search_corpus", {"query": "mill", "show_sections": False}),
            ("search_corpus", {"query": "mill", "category_filter": "Setting_A"}),
            ("search_corpus", {"query": "mill", "type_filter": "location"}),
            ("search_corpus", {"query": "mill", "missing_filter": "keywords"}),
            ("search_corpus", {"query": "mill", "missing_filter": "bogus"}),
            ("search_corpus", {"query": "mill", "mode": "vector"}), ("search_corpus", {"query": "mill", "mode": "hybrid"}),
            ("search_corpus", {"query": "mill", "mode": "nope"}), ("search_corpus", {"query": "mill", "limit": 0}),
            ("search_corpus", {"query": "mill", "limit": 500}), ("search_corpus", {"query": '"unbalanced'}),
            ("search_corpus", {"query": "nosuchword"}),
            ("search_corpus", {"query": QUERY, "system": "basesys"}),
            ("search_corpus", {"query": "fatigue OR warden", "system": "basesys"}),
            ("search_corpus", {"query": QUERY, "system": "basesys", "representation_filter": "dataset"}),
            ("search_corpus", {"query": QUERY, "system": "basesys", "representation_filter": "verbatim, dataset"}),
            ("search_corpus", {"query": QUERY, "system": "basesys", "representation_filter": "dataset",
                               "mode": "vector"}),
            ("search_corpus", {"query": QUERY, "system": "basesys", "representation_filter": "bogus"}),
            ("search_corpus", {"query": QUERY, "representation_filter": "dataset"}),
            ("search_corpus", {"query": QUERY, "system": "ghost"}), ("search_corpus", {"query": QUERY, "system": "Bad-Name"}),
            ("search_corpus", {"query": QUERY, "system": ""}),
            ("get_section", {"path": "World_Building/Setting_A/Old_Mill.md"}),
            ("get_section", {"path": "World_Building/Setting_A/Old_Mill.md", "heading": "wing 3"}),
            ("get_section", {"path": "World_Building/Setting_A/Old_Mill.md", "heading": "wing"}),
            ("get_section", {"path": "World_Building/Setting_A/Old_Mill.md", "heading": "nope"}),
            ("get_section", {"path": "World_Building/Setting_A/Old_Mill.md", "level": 9}),
            ("get_section", {"path": "World_Building/Setting_A/Steward.md", "heading": "x"}),
            ("get_section", {"path": "Old_Mill.md"}), ("get_section", {"path": ""}),
            ("get_section", {"path": "rules/core.md", "heading": "Fatigue", "system": "basesys"}),
            ("get_section", {"path": "rules/big.md", "system": "basesys", "level": 2}),
            ("get_section", {"path": "data/items.jsonl", "system": "basesys"}),
            ("get_section", {"path": "rules/core.md", "system": "ghost"}),
            ("get_system_record", {"system": "basesys", "entry_key": "rec:items/item/rope"}),
            ("get_system_record", {"system": "basesys", "dataset": "items", "record_id": "item/rope"}),
            ("get_system_record", {"system": "basesys", "entry_key": "doc:rules/core.md"}),
            ("get_system_record", {"system": "basesys", "entry_key": "rec:items/nope"}),
            ("get_system_record", {"system": "basesys"}), ("get_system_record", {"system": "ghost", "entry_key": "x"}),
            ("index_status", {}), ("index_status", {"system": "basesys"}), ("index_status", {"system": "ghost"}),
            ("index_status", {"chain": "baseline,basesys,hb"}), ("index_status", {"campaign": "camp_one"}),
            ("index_status", {"chain": "baseline,ghost"}), ("index_status", {"campaign": "nowhere"}),
            ("index_status", {"system": "basesys", "chain": "hb"}),
        ]
        try:
            outputs = []
            for name, kw in calls:
                with self.subTest(call=name, kw=kw):
                    new, was = getattr(srv, name)(**kw), getattr(old, name)(**kw)
                    self.assertEqual(new, was)
                    outputs.append(new)
            self.assertIn(b, "\n".join(outputs))
            self.assertTrue(any(o.startswith("Found ") and "Sections:" in o for o in outputs))   # substance
        finally:
            for n, v in saved.items():
                setattr(srv, n, v)


# ================================================================ robustness (audit batch 1)

class TestAuditRobustness(ChainFixture):
    """Inputs the 2026-11-14 audit (Working_Documents/Chain_Search_Audit_Fable.md, findings X1, C3 and N2) showed
    crashing, leaking or being read where the design says they are refused or ignored."""

    UNDECODABLE = b"# Other\n\n```yaml\nnote: caf\xe9\n```\n"         # Latin-1 e-acute: not valid UTF-8

    def test_an_undecodable_manifest_outside_the_chain_breaks_nothing(self):
        write(self.root / "Game_Systems" / "Other" / "other.md", "")
        (self.root / "Game_Systems" / "Other" / "other.md").write_bytes(self.UNDECODABLE)
        out = self.search(chain="basesys,hb")
        self.assertEqual([m for _p, m in self.hits(out)], ["hb", "basesys", "basesys"])
        self.assertIn("2. hb: indexed", self.status(chain="basesys,hb"))
        known, ambiguous = si.known_modules(self.root, (PRIVATE,))
        self.assertIn("basesys", known)
        self.assertNotIn("other", known)

    def test_an_undecodable_index_cfg_refuses_only_its_own_module(self):
        other = self.root / "Game_Systems" / "Other"
        write(other / "other.md", manifest("other", resolution="defined"))
        write(other / "index.cfg", "")
        (other / "index.cfg").write_bytes(b"[system]\nmodule = other\n# caf\xe9\n")
        self.assertEqual(si.declared_module(other / "index.cfg"), "other")     # the ASCII module line still reads
        with self.assertRaisesRegex(si.SystemIndexError, "not valid UTF-8"):
            si.load_system_cfg(other / "index.cfg")
        self.assertEqual(si.find_cfg(self.root, "basesys", (PRIVATE,)), self.base_cfg)
        ordered, failures = bi._ordered_targets([other / "index.cfg", self.base_cfg])
        self.assertEqual((ordered, failures), ([self.base_cfg], 1))
        self.assertEqual([m for _p, m in self.hits(self.search(chain="basesys,hb"))], ["hb", "basesys", "basesys"])

    def test_an_undecodable_campaign_profile_refuses(self):
        (self.camp1 / rc.PROFILE_FILE).write_bytes(b"# P\n\n```yaml\nchain: [Baseline]\nnote: caf\xe9\n```\n")
        self.assertTrue(any("not valid UTF-8" in r for r in self.resolve(campaign="Camp_One").refusals))
        out = self.search(campaign="Camp_One")
        self.assertIn("No search was run", out)
        self.assertIn("not valid UTF-8", out)

    def test_an_undecodable_adaptation_profile_is_non_authoritative(self):
        self.adapt.write_bytes(self.UNDECODABLE)
        out = self.status(campaign="Camp_One")
        self.assertIn("not valid UTF-8", out)
        self.assertIn("NON-AUTHORITATIVE", out)

    def test_an_embedding_failure_is_reported_not_raised(self):
        with mock.patch.object(srv, "_has_vector_table", return_value=True), \
                mock.patch.object(srv.embedding, "AVAILABLE", True), mock.patch.object(srv.embedding, "load_vec"), \
                mock.patch.object(srv.embedding, "embed_query", side_effect=RuntimeError("model unavailable")):
            out = self.search(chain="basesys,hb", mode="vector")
        self.assertEqual(out, "[!] Unexpected error: model unavailable")

    def test_a_connection_whose_extension_fails_to_load_is_closed(self):
        opened = []

        def load_vec(conn):
            opened.append(conn)
            raise RuntimeError("no vector extension")
        for kw in ({"chain": "basesys,hb"}, {"system": "basesys"}):
            with self.subTest(**kw):
                opened.clear()
                with mock.patch.object(srv.embedding, "AVAILABLE", True), \
                        mock.patch.object(srv.embedding, "load_vec", side_effect=load_vec):
                    out = self.search(mode="vector", **kw)
                self.assertIn("[!] Unexpected error: no vector extension", out)
                self.assertTrue(opened)
                for conn in opened:
                    with self.assertRaises(sqlite3.ProgrammingError):          # closed, not leaked
                        conn.execute("SELECT 1")

    def test_a_sidecar_beside_a_generation_is_never_read(self):
        # The generation is rewritten in WAL mode with its content unchanged, and a WAL holding one more table is
        # planted at its name. Containment checks the main file only, so the sidecar must play no part in a read.
        gen = self.gen("basesys")
        work = Path(self._tmp.name) / "work.db"
        work.write_bytes(gen.read_bytes())
        conn = sqlite3.connect(work)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
            gen.write_bytes(work.read_bytes())
            conn.execute("CREATE TABLE planted (x)")
            conn.commit()
            Path(f"{gen}-wal").write_bytes(Path(f"{work}-wal").read_bytes())
        finally:
            conn.close()
        plain = sqlite3.connect(f"{gen.as_uri()}?mode=ro", uri=True)
        try:                                                    # the fixture is real: a plain open reads the WAL
            self.assertEqual(plain.execute("SELECT count(*) FROM sqlite_master WHERE name='planted'").fetchone()[0], 1)
        finally:
            plain.close()
        opened, refused = self.call(srv._open_module, db_path=gen, system="basesys")
        self.assertIsNone(refused)
        try:
            self.assertEqual(opened.execute("SELECT count(*) FROM sqlite_master WHERE name='planted'").fetchone()[0],
                             0)
        finally:
            opened.close()
        sdir = si.systems_dir(self.index)
        held, why = si.open_contained(gen, sdir, lambda real: sqlite3.connect(si.generation_uri(real), uri=True))
        self.assertIsNone(why)
        try:
            self.assertEqual(held.execute("SELECT count(*) FROM sqlite_master WHERE name='planted'").fetchone()[0], 0)
        finally:
            held.close()
        self.assertEqual([m for _p, m in self.hits(self.search(chain="basesys,hb"))], ["hb", "basesys", "basesys"])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--no-pause", action="store_true", help="Skip end-of-run pause")
    args = parser.parse_args()
    t0 = time.time()
    result = unittest.main(module=__name__, argv=[sys.argv[0], "-v"], exit=False).result
    print(f"Runtime: {time.time() - t0:.2f}s")
    if not args.no_pause:
        input("Press Enter to exit...")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

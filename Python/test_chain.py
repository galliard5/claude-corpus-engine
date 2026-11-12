#!/usr/bin/env python3
"""
test_chain.py — Self-test for rules-chain resolution and chain-aware index_status (chain-aware search, stage 2).

Everything runs in process against synthetic modules, campaigns and registries in temporary directories; the
builder's history log is redirected. Nothing is written to the real corpus or index. Two read-only checks touch the
real corpus: that the real legacy module still resolves as indexed with unchanged sources (no rebuild needed), and
that a real campaign's status is computed without writing anything.

THE CONTRACTS THESE TESTS PIN (design: Working_Documents/Chain_Search_Design_Proposal_v2.md; Codex 938/945)
  Selectors    exactly one of campaign and chain; index_status refuses any two of system, campaign and chain; a
               chain of more than eight layers, an empty one or an empty entry refuses.
  Campaigns    a campaign is a folder holding Campaign_Profile.md under either layout (setting/Scenarios/<name>/ or
               setting/<name>/), matched case-insensitively; none or several refuse, listing the candidates.
  Roles        a layer resolves case-insensitively to a known module (a folder-named manifest with a fenced YAML
               block); declared loaded only when indexer.cfg [rules_layers] not_searched names it; indexed only when
               its registry entry and database agree; anything else is missing and refuses — an unknown or
               unregistered module is never classified loaded. A module both registered and not_searched refuses.
  Freshness    schema 2 recomputes the original fingerprint, schema 3 the layered one over its recorded
               dependencies; a change is a conspicuous warning, never a refusal; a layered layer whose dependency was
               rebuilt says so; a layer extending a module outside the chain says so.
  Snapshot     the registry is read once; the token is the domain-separated hash of the sorted (layer, build) pairs.
  Inputs       the adaptation profile is required for a chain longer than one module and is "current" only when it
               exists, names this chain and every full built_against hash matches; otherwise retrieval is marked
               NON-AUTHORITATIVE, never refused. A declared sidecar is reported with its hash; a missing one refuses.
  Compatible   index_status() and index_status(system=...) produce exactly the output the committed server produces.

Usage:
    python -m unittest test_chain -v
    python test_chain.py [--no-pause]

Command line arguments:
    --no-pause   Skip end-of-run pause

# changed 2026-11-12: created (chain-aware search stage 2, Codex 945).
"""

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
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
from cfg_loader import load_cfg  # noqa: E402
from test_layers import PRIVATE, make_base, make_layer, manifest, relation, write  # noqa: E402

REAL_ROOT = HERE.parent
REAL_INDEX = REAL_ROOT / "index"
COMMITTED = "ffe42070f01abb1e2b3d485396e6a8ffa4dd9d08"    # the stage-1 commit: the server before stage 2


def profile(chain, adaptation=None, homebrew=None) -> str:
    lines = ["campaign: [Campaign]", f"chain: [{', '.join(chain)}]"]
    if adaptation is not None:
        lines.append(f"adaptation: {adaptation}")
    if homebrew is not None:
        lines.append(f"homebrew: {homebrew}")
    return "# Profile\n\n```yaml\n" + "\n".join(lines) + "\n```\n"


class Fixture(unittest.TestCase):
    """A synthetic corpus: Baseline (a known module, not indexed), basesys (indexed, legacy), hb (a private,
    layered homebrew extending basesys), campaigns under both layouts, and an adaptation profile."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "corpus"
        self.root.mkdir()
        self.index = self.root / "index"
        p = mock.patch.object(bi, "HISTORY_PATH", Path(self._tmp.name) / "history.jsonl")
        p.start()
        self.addCleanup(p.stop)
        write(self.root / "Game_Systems" / "Baseline" / "baseline.md", "# Baseline\n\n```yaml\nresolution: defined\n```\n")
        self.base_cfg = make_base(self.root)
        self.hb_cfg = make_layer(self.root, relations=relation())
        self.base = bi.build_and_publish(self.root, self.index, self.base_cfg, build_vectors=False)
        self.hb = bi.build_and_publish(self.root, self.index, self.hb_cfg, build_vectors=False)
        self.adapt = write(self.root / "Game_Systems" / "Basesys" / "adaptations" / "Baseline_Basesys.md",
                           self.adaptation_text())
        self.camp1 = self.campaign("Setting_A/Scenarios/Camp_One", ["Baseline", "Basesys"],
                                   adaptation="Game_Systems/Basesys/adaptations/Baseline_Basesys.md")
        self.camp2 = self.campaign("Setting_B/Camp_Two", ["Baseline"])
        self.cfg_path = write(Path(self._tmp.name) / "indexer.cfg",
                              f"[rules_layers]\nprivate_roots = {PRIVATE}\nnot_searched = baseline\n")

    def tearDown(self):
        self._tmp.cleanup()

    def adaptation_text(self, chain="[baseline, basesys]", built=None, homebrew=None):
        b = self.root / "Game_Systems" / "Baseline" / "baseline.md"
        m = self.root / "Game_Systems" / "Basesys" / "basesys.md"
        built = built if built is not None else (
            f"  - path: engine:Game_Systems/Baseline/baseline.md\n    sha256: {hashlib.sha256(b.read_bytes()).hexdigest()}\n"
            f"  - path: basesys.md\n    sha256: {hashlib.sha256(m.read_bytes()).hexdigest()}\n")
        hb = f"homebrew: {homebrew}\n" if homebrew is not None else ""
        return f"# Adaptation\n\n```yaml\nchain: {chain}\nbuilt_against:\n{built}{hb}```\n"

    def pin(self, spec, path=None) -> str:
        """One built_against entry: `spec` as written, hashed from `path` (default: the corpus file it names)."""
        path = path if path is not None else self.root / spec.removeprefix("engine:")
        return f"  - path: {spec}\n    sha256: {hashlib.sha256(Path(path).read_bytes()).hexdigest()}\n"

    def default_pins(self) -> str:
        return (self.pin("engine:Game_Systems/Baseline/baseline.md")
                + self.pin("basesys.md", self.root / "Game_Systems" / "Basesys" / "basesys.md"))

    def link_dir(self, link: Path, target: Path) -> None:
        """A directory junction (Windows) or symlink at `link` leading to `target`; skips the test if neither can be
        made, or if the link does not resolve to its target."""
        link.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir(parents=True, exist_ok=True)
        try:
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        except (ImportError, AttributeError, OSError):
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as e:
                self.skipTest(f"cannot make a directory link here ({e})")
        if link.resolve() != target.resolve():
            self.skipTest("the directory link does not resolve to its target here")

    def campaign(self, rel, chain, **fields):
        d = self.root / "World_Building" / rel
        write(d / rc.PROFILE_FILE, profile(chain, **fields))
        return d

    def rules(self, text=None):
        if text is not None:
            write(self.cfg_path, text)
        return load_cfg(self.cfg_path)

    def resolve(self, **kw):
        cfg = kw.pop("cfg", None)
        return rc.resolve(self.root, self.index, cfg if cfg is not None else self.rules(), **kw)

    def roles(self, res):
        return [(l.module or l.given, l.role) for l in res.layers]

    def registry(self):
        return si.read_registry(si.systems_dir(self.index))

    def status(self, **kw):
        with mock.patch.object(srv, "_CORPUS_ROOT", self.root), \
                mock.patch.object(srv, "SYSTEMS_DIR", si.systems_dir(self.index)), \
                mock.patch.object(srv, "RULES_CFG_PATH", self.cfg_path):
            return srv.index_status(**kw)


# ================================================================ selectors

class TestSelectors(Fixture):
    def test_exactly_one_selector(self):
        self.assertIn("give exactly one of campaign or chain", self.resolve().refusals)
        self.assertIn("give exactly one of campaign or chain", self.resolve(campaign="Camp_One", chain="basesys").refusals)
        for kw in ({"system": "basesys", "campaign": "Camp_One"}, {"campaign": "Camp_One", "chain": "basesys"},
                   {"system": "basesys", "chain": "basesys"}):
            with self.subTest(kw=kw):
                self.assertEqual(self.status(**kw), "[!] Give at most one of system, campaign or chain.")

    def test_chain_length_and_shape(self):
        res = self.resolve(chain=",".join(["basesys"] * 9))
        self.assertTrue(any("at most 8" in r for r in res.refusals), res.refusals)
        self.assertFalse(res.layers)
        for bad in ("", "basesys,,hb", " , "):
            with self.subTest(chain=bad):
                self.assertTrue(any("names no layer" in r for r in self.resolve(chain=bad).refusals))
        ok = self.resolve(chain=",".join(["baseline", "basesys", "hb"]))
        self.assertFalse(ok.refused, ok.refusals)


# ================================================================ campaigns

class TestCampaignIdentity(Fixture):
    def test_both_layouts_and_case_insensitive(self):
        for name, profile_rel in (("Camp_One", "World_Building/Setting_A/Scenarios/Camp_One/Campaign_Profile.md"),
                                  ("camp_two", "World_Building/Setting_B/Camp_Two/Campaign_Profile.md"),
                                  ("CAMP_ONE", "World_Building/Setting_A/Scenarios/Camp_One/Campaign_Profile.md")):
            with self.subTest(name=name):
                res = self.resolve(campaign=name)
                self.assertEqual(res.profile, profile_rel)
                self.assertFalse(res.refused, res.refusals)

    def test_unknown_and_ambiguous_refuse_with_candidates(self):
        res = self.resolve(campaign="Nowhere")
        self.assertTrue(any("no campaign folder named 'Nowhere'" in r and "Camp_One, Camp_Two" in r
                            for r in res.refusals), res.refusals)
        self.campaign("Setting_C/Camp_One", ["Baseline"])
        res = self.resolve(campaign="camp_one")
        why = next(r for r in res.refusals if "ambiguous" in r)
        self.assertIn("World_Building/Setting_A/Scenarios/Camp_One/Campaign_Profile.md", why)
        self.assertIn("World_Building/Setting_C/Camp_One/Campaign_Profile.md", why)
        write(self.root / "World_Building" / "Setting_D" / "Scenarios" / rc.PROFILE_FILE, profile(["Baseline"]))
        self.assertNotIn("Scenarios", {p.parent.name for p in rc.campaign_profiles(self.root)})

    def test_an_unreadable_profile_refuses(self):
        write(self.camp2 / rc.PROFILE_FILE, "# no fence here\n")
        self.assertTrue(any("no readable fenced YAML" in r for r in self.resolve(campaign="Camp_Two").refusals))
        write(self.camp2 / rc.PROFILE_FILE, "# P\n\n```yaml\ncampaign: x\n```\n")
        self.assertTrue(any("must be a list" in r for r in self.resolve(campaign="Camp_Two").refusals))


# ================================================================ roles

class TestRoles(Fixture):
    def test_roles_resolve_case_insensitively(self):
        res = self.resolve(chain="Baseline,BaseSys,HB")
        self.assertEqual(self.roles(res), [("baseline", rc.ROLE_LOADED), ("basesys", rc.ROLE_INDEXED),
                                           ("hb", rc.ROLE_INDEXED)])
        self.assertIn("not verified in context", res.layers[0].reason)
        self.assertFalse(res.refused, res.refusals)

    def test_unknown_or_undeclared_is_never_loaded(self):
        res = self.resolve(chain="baseline,basesys", cfg=self.rules(f"[rules_layers]\nprivate_roots = {PRIVATE}\n"))
        self.assertEqual(self.roles(res)[0], ("baseline", rc.ROLE_MISSING))
        self.assertIn("not declared not_searched", res.layers[0].reason)
        self.assertTrue(res.refused)
        res = self.resolve(chain="baseline,ghost")
        self.assertEqual(res.layers[1].role, rc.ROLE_MISSING)
        self.assertIn("unknown layer", res.layers[1].reason)
        self.assertTrue(any("'ghost' is not a known module" in r for r in res.refusals))

    def test_a_duplicate_or_conflicting_declaration_refuses(self):
        self.assertTrue(any("appears more than once" in r for r in self.resolve(chain="basesys,BaseSys").refusals))
        res = self.resolve(chain="basesys", cfg=self.rules(f"[rules_layers]\nprivate_roots = {PRIVATE}\n"
                                                          f"not_searched = baseline, basesys\n"))
        self.assertTrue(any("declared not_searched in indexer.cfg, yet it has a published database" in r
                            for r in res.refusals), res.refusals)

    def test_a_broken_publication_is_missing(self):
        reg = self.registry()
        reg["systems"]["basesys"]["build_id"] = "19990101T000000Z-000000"
        si.write_registry(si.systems_dir(self.index), reg)
        res = self.resolve(chain="baseline,basesys")
        self.assertEqual(res.layers[1].role, rc.ROLE_MISSING)
        self.assertIn("does not match the registry", res.layers[1].reason)
        self.assertTrue(res.refused)

    def test_an_unsupported_schema_is_missing(self):
        db = si.resolve_db(si.systems_dir(self.index), "basesys", self.registry()["systems"]["basesys"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE db_info SET schema_version = 99")
        conn.commit()
        conn.close()
        reg = self.registry()
        reg["systems"]["basesys"]["schema_version"] = 99
        si.write_registry(si.systems_dir(self.index), reg)
        res = self.resolve(chain="basesys")
        self.assertIn("is not one this code reads", res.layers[0].reason)

    def test_a_registry_and_database_schema_disagreement_is_missing(self):
        reg = self.registry()
        reg["systems"]["basesys"]["schema_version"] = 3                 # the database still says 2
        si.write_registry(si.systems_dir(self.index), reg)
        res = self.resolve(chain="basesys")
        self.assertEqual(res.layers[0].role, rc.ROLE_MISSING)
        self.assertIn("the registry says schema 3 but its database says 2", res.layers[0].reason)

    def test_unbuilt_known_modules_and_ambiguity(self):
        write(self.root / "Game_Systems" / "Other" / "other.md", "# Other\n\n```yaml\nresolution: defined\n```\n")
        res = self.resolve(chain="other")
        self.assertIn("not built and not declared not_searched", res.layers[0].reason)
        write(self.root / PRIVATE / "Other" / "other.md", "# Other\n\n```yaml\nresolution: defined\n```\n")
        write(self.root / PRIVATE / "Other" / "index.cfg", "[system]\nmodule = other\n")
        self.assertTrue(any("more than one folder declares" in r for r in self.resolve(chain="other").refusals))

    def test_known_modules(self):
        write(self.root / "Game_Systems" / "Nomani" / "readme.md", "no manifest")
        write(self.root / "Game_Systems" / "Nofence" / "nofence.md", "# no fence\n")
        write(self.root / "Game_Systems" / "Wrong" / "wrong.md", "# W\n\n```yaml\nmodule: else\n```\n")
        known, ambiguous = si.known_modules(self.root, (PRIVATE,))
        self.assertEqual(set(known), {"baseline", "basesys", "hb"})
        self.assertEqual(ambiguous, set())


# ================================================================ freshness and dependencies

class TestFreshness(Fixture):
    def test_fresh_layers_of_both_schemas(self):
        res = self.resolve(chain="baseline,basesys,hb")
        self.assertEqual([(l.schema, l.freshness) for l in res.layers[1:]], [(2, "unchanged"), (3, "unchanged")])
        self.assertEqual(res.warnings, [])

    def test_changed_sources_warn_conspicuously_and_never_refuse(self):
        write(self.root / "Game_Systems" / "Basesys" / "rules" / "core.md", "# Changed\n\nNew text.\n")
        res = self.resolve(chain="baseline,basesys")
        self.assertEqual(res.layers[1].freshness, "CHANGED")
        self.assertFalse(res.refused)
        self.assertTrue(any("SOURCES CHANGED since the build" in w for w in res.warnings))
        self.assertIn("[!] SOURCES CHANGED since the build", self.status(chain="baseline,basesys"))

    def test_a_rebuilt_dependency_and_a_missing_parent_are_reported(self):
        rebuilt = bi.build_and_publish(self.root, self.index, self.base_cfg, build_vectors=False)
        res = self.resolve(chain="baseline,basesys,hb")
        hb = res.layers[2]
        self.assertEqual(hb.freshness, "unchanged")              # its own inputs did not change
        self.assertIn(f"relations validated against an older build of basesys ({self.base.build_id}; now "
                      f"{rebuilt.build_id})", hb.notes)
        res = self.resolve(chain="baseline,hb")
        self.assertIn("extends basesys, which this chain does not include", res.layers[1].notes)

    def test_the_real_legacy_module_needs_no_rebuild(self):
        reg = REAL_INDEX / "systems" / si.REGISTRY
        if not reg.exists():
            self.skipTest("the real index is not present")
        before = hashlib.sha256(reg.read_bytes()).hexdigest()
        module = next(iter(json.loads(reg.read_text(encoding="utf-8"))["systems"]))
        res = rc.resolve(REAL_ROOT, REAL_INDEX, {}, chain=module)
        self.assertEqual((res.layers[0].role, res.layers[0].schema, res.layers[0].freshness),
                         (rc.ROLE_INDEXED, 2, "unchanged"))
        self.assertEqual(hashlib.sha256(reg.read_bytes()).hexdigest(), before)


# ================================================================ the snapshot

class TestSnapshot(Fixture):
    def test_the_token_is_exact_and_tracks_builds(self):
        res = self.resolve(chain="baseline,hb,basesys")
        h = hashlib.sha256(b"rules-chain-snapshot/v1\n")
        for m, b in sorted([("basesys", self.base.build_id), ("hb", self.hb.build_id)]):
            h.update(f"{m}\0{b}\n".encode())
        self.assertEqual(res.token, h.hexdigest())
        self.assertEqual(res.token, self.resolve(chain="basesys,hb").token)          # loaded layers are not in it
        bi.build_and_publish(self.root, self.index, self.hb_cfg, build_vectors=False)
        self.assertNotEqual(res.token, self.resolve(chain="basesys,hb").token)

    def test_the_registry_is_read_once(self):
        real = si.read_registry
        with mock.patch.object(si, "read_registry", side_effect=real) as spy:
            self.resolve(chain="baseline,basesys,hb")
        self.assertEqual(spy.call_count, 1)


# ================================================================ adaptation and sidecars

class TestInputs(Fixture):
    def test_a_current_adaptation(self):
        res = self.resolve(campaign="Camp_One")
        self.assertTrue(res.adaptation.current, res.adaptation.status)
        self.assertTrue(res.authoritative_inputs)
        self.assertIn("adaptation inputs current", self.status(campaign="Camp_One"))
        one = self.resolve(campaign="Camp_Two")
        self.assertIn("not required", one.adaptation.status)
        self.assertTrue(one.authoritative_inputs)

    def test_every_doubtful_adaptation_is_non_authoritative_not_refused(self):
        cases = {
            "stale": lambda: write(self.root / "Game_Systems" / "Baseline" / "baseline.md",
                                   "# Baseline\n\n```yaml\nresolution: changed\n```\n"),
            "missing": lambda: self.adapt.unlink(),
            "other chain": lambda: write(self.adapt, self.adaptation_text(chain="[baseline, hb]")),
            "unverifiable": lambda: write(self.adapt, "# A\n\n```yaml\nchain: [Baseline, Basesys]\nbuilt_against:\n"
                                                      "  Game_Systems/Baseline/baseline.md: sha256 311257a8e602\n```\n"),
        }
        expect = {"stale": "STALE", "missing": "does not exist", "other chain": "not this one",
                  "unverifiable": "cannot be checked"}
        for name, change in cases.items():
            with self.subTest(case=name):
                saved = {p: p.read_bytes() for p in (self.adapt, self.root / "Game_Systems" / "Baseline" / "baseline.md")
                         if p.exists()}
                change()
                res = self.resolve(campaign="Camp_One")
                self.assertFalse(res.adaptation.current)
                self.assertIn(expect[name], res.adaptation.status)
                self.assertFalse(res.refused, res.refusals)
                self.assertIn("NON-AUTHORITATIVE", self.status(campaign="Camp_One"))
                for p, b in saved.items():
                    p.write_bytes(b)
        self.campaign("Setting_A/Scenarios/No_Adapt", ["Baseline", "Basesys"])
        self.assertIn("NONE DECLARED", self.resolve(campaign="No_Adapt").adaptation.status)
        self.assertIn("explicit chain carries no adaptation", self.resolve(chain="baseline,basesys").adaptation.status)

    def test_sidecars(self):
        write(self.camp2 / "homebrew_campaign.md", "# Campaign rules\n")
        write(self.root / "Game_Systems" / "Basesys" / "homebrew_basesys.md", "# System rules\n")
        self.campaign("Setting_B/Camp_Two", ["Baseline"],
                      homebrew="[homebrew_campaign.md, Game_Systems/Basesys/homebrew_basesys.md]")
        res = self.resolve(campaign="Camp_Two")
        self.assertEqual([(s.path, s.exists) for s in res.sidecars],
                         [("World_Building/Setting_B/Camp_Two/homebrew_campaign.md", True),
                          ("Game_Systems/Basesys/homebrew_basesys.md", True)])
        self.assertEqual(res.sidecars[0].sha256, hashlib.sha256(b"# Campaign rules\n").hexdigest())
        self.assertFalse(res.refused)
        self.campaign("Setting_B/Camp_Two", ["Baseline"], homebrew="[homebrew_gone.md]")
        res = self.resolve(campaign="Camp_Two")
        self.assertTrue(any("declared sidecar World_Building/Setting_B/Camp_Two/homebrew_gone.md does not exist" in r
                            for r in res.refusals), res.refusals)
        self.assertIn("[!] Chain refused", self.status(campaign="Camp_Two"))
        for none in ("none", "[]", "\n  -"):
            with self.subTest(homebrew=none):
                self.campaign("Setting_B/Camp_Two", ["Baseline"], homebrew=none)
                self.assertEqual(self.resolve(campaign="Camp_Two").sidecars, [])
        self.campaign("Setting_B/Camp_Two", ["Baseline"], homebrew="[../outside.md]")
        self.assertTrue(any("not a corpus-relative path" in r for r in self.resolve(campaign="Camp_Two").refusals))


# ================================================================ the shared [rules_layers] parser

class TestRulesLayers(Fixture):
    def test_not_searched_names_known_modules(self):
        self.assertEqual(si.parse_rules_layers(self.rules("[rules_layers]\nnot_searched = Baseline\n"), self.root),
                         ((), ("baseline",)))
        self.assertEqual(bi.parse_private_roots(self.rules(f"[rules_layers]\nprivate_roots = {PRIVATE}\n"
                                                           f"not_searched = baseline\n"), self.root), (PRIVATE,))
        for text, why in (("[rules_layers]\nnot_searched = ghost\n", "'ghost', which is no known module"),
                          ("[rules_layers]\nnot_searched = baseline, BASELINE\n", "names 'baseline' twice"),
                          ("[rules_layers]\nnot_searched = \n", "not_searched names no module")):
            with self.subTest(text=text), self.assertRaisesRegex(si.SystemIndexError, why):
                si.parse_rules_layers(self.rules(text), self.root)
        self.assertEqual(si.parse_rules_layers({}, self.root), ((), ()))

    def test_a_broken_config_refuses_the_chain(self):
        res = self.resolve(chain="baseline", cfg=self.rules("[rules_layers]\nnot_searched = ghost\n"))
        self.assertTrue(res.refused)
        self.assertTrue(res.refusals[0].startswith("indexer.cfg [rules_layers]:"))
        with mock.patch.object(srv, "load_cfg", side_effect=ValueError("garbled")):
            self.assertIn("cannot be read: garbled", self.status(chain="baseline"))


# ================================================================ the rendered status, and compatibility

class TestServer(Fixture):
    def test_the_header_reports_every_input(self):
        write(self.camp1 / "homebrew_campaign.md", "x\n")
        self.campaign("Setting_A/Scenarios/Camp_One", ["Baseline", "Basesys", "Hb"],
                      adaptation="Game_Systems/Basesys/adaptations/Baseline_Basesys.md", homebrew="[homebrew_campaign.md]")
        out = self.status(campaign="camp_one")
        for want in ("Rules chain status: campaign camp_one (World_Building/Setting_A/Scenarios/Camp_One/"
                     "Campaign_Profile.md)", "Chain (lowest first): baseline -> basesys -> hb",
                     "1. baseline: declared loaded, not searched", f"2. basesys: indexed — build {self.base.build_id}, "
                     "schema 2", "3. hb: indexed", "Snapshot:   ", "(the registry, read once; 2 indexed layer(s))",
                     "Adaptation: ", "World_Building/Setting_A/Scenarios/Camp_One/homebrew_campaign.md: sha256 ",
                     "Retrieval:  [!] NON-AUTHORITATIVE"):
            self.assertIn(want, out)
        self.assertNotIn("[!] Chain refused", out)
        refused = self.status(chain="baseline,ghost")
        self.assertTrue(refused.startswith("[!] Chain refused — 1 problem(s); a chain search would not run:"))
        self.assertIn("2. ghost: [!] MISSING — unknown layer", refused)

    def test_corpus_and_single_system_output_is_unchanged(self):
        src = subprocess.run(["git", "-C", str(HERE), "show", f"{COMMITTED}:Python/search_mcp_server.py"],
                             capture_output=True, check=True).stdout.decode("utf-8")
        old = types.ModuleType("search_mcp_server_ffe4207")
        old.__file__ = str(HERE / "search_mcp_server_ffe4207.py")
        exec(compile(src, old.__file__, "exec"), old.__dict__)
        names = ("_CORPUS_ROOT", "SYSTEMS_DIR", "DB_PATH", "HISTORY_PATH")
        saved = {n: getattr(srv, n) for n in names}
        for mod in (srv, old):
            mod._CORPUS_ROOT, mod.SYSTEMS_DIR = self.root, si.systems_dir(self.index)
            mod.DB_PATH = self.index / "search_index.db"
            mod.HISTORY_PATH = Path(self._tmp.name) / "history.jsonl"
        try:
            for kw in ({}, {"system": "basesys"}, {"system": "ghost"}, {"system": "Bad-Name"}):
                with self.subTest(kw=kw):
                    self.assertEqual(srv.index_status(**kw), old.index_status(**kw))
        finally:
            for n, v in saved.items():
                setattr(srv, n, v)


# ================================================================ Codex 947: the four review findings

class TestModuleIdentity(Fixture):
    """947 (1): an indexable module is identified as the builder identifies it — by the id its index.cfg declares —
    with the builder's conflict rule; a legacy folder keeps the folder-named manifest fallback; nothing is guessed."""

    def test_a_module_whose_folder_is_named_otherwise(self):
        cfg = make_base(self.root, dirname="Display_Name", module="stable_id")
        built = bi.build_and_publish(self.root, self.index, cfg, build_vectors=False)
        res = self.resolve(chain="stable_id")
        self.assertFalse(res.refused, res.refusals)
        self.assertEqual((res.layers[0].module, res.layers[0].role, res.layers[0].build_id, res.layers[0].freshness),
                         ("stable_id", rc.ROLE_INDEXED, built.build_id, "unchanged"))
        known, _ = si.known_modules(self.root, (PRIVATE,))
        self.assertEqual(known["stable_id"], (self.root / "Game_Systems" / "Display_Name").resolve())
        res = self.resolve(chain="display_name")                     # the folder name is not an id
        self.assertTrue(any("'display_name' is not a known module" in r for r in res.refusals), res.refusals)
        self.assertIn("baseline", known)                             # the legacy fallback is unchanged

    def test_collisions_within_and_across_roots_are_ambiguous(self):
        make_base(self.root, dirname="Display_Name", module="stable_id")
        cases = {
            "a legacy folder of that name": lambda: write(self.root / "Game_Systems" / "Stable_Id" / "stable_id.md",
                                                          "# S\n\n```yaml\nresolution: defined\n```\n"),
            "a private module declaring it": lambda: make_layer(self.root, module="stable_id", dirname="Elsewhere"),
            "a private folder named like it": lambda: write(self.root / PRIVATE / "Stable_Id" / "index.cfg",
                                                            "[system]\nmodule = other_id\n"),
        }
        for name, make in cases.items():
            with self.subTest(case=name):
                before = {p for p in (self.root / "Game_Systems").iterdir()} | {p for p in (self.root / PRIVATE).iterdir()}
                make()
                known, ambiguous = si.known_modules(self.root, (PRIVATE,))
                self.assertIn("stable_id", ambiguous)
                self.assertNotIn("stable_id", known)
                self.assertTrue(any("more than one folder declares" in r for r in self.resolve(chain="stable_id").refusals))
                import shutil
                for p in ({p for p in (self.root / "Game_Systems").iterdir()}
                          | {p for p in (self.root / PRIVATE).iterdir()}) - before:
                    shutil.rmtree(p)
        self.assertNotIn("stable_id", si.known_modules(self.root, (PRIVATE,))[1])

    def test_an_invalid_indexable_folder_is_never_guessed(self):
        write(self.root / "Game_Systems" / "Bad" / "bad.md", "# Bad\n\n```yaml\nresolution: defined\n```\n")
        write(self.root / "Game_Systems" / "Bad" / "index.cfg", "[system]\nmodule = bad\n")      # manifest has no module:
        write(self.root / "Game_Systems" / "Nodecl" / "nodecl.md", "# N\n\n```yaml\nmodule: nodecl\n```\n")
        write(self.root / "Game_Systems" / "Nodecl" / "index.cfg", "[system]\n")                  # declares no id
        known, ambiguous = si.known_modules(self.root, (PRIVATE,))
        self.assertNotIn("bad", known)
        self.assertNotIn("nodecl", known)
        for name in ("bad", "nodecl"):
            with self.subTest(layer=name):
                res = self.resolve(chain=name)
                self.assertEqual(res.layers[0].role, rc.ROLE_MISSING)
                self.assertTrue(any(f"'{name}' is not a known module" in r for r in res.refusals))


class TestAdaptationCoverage(Fixture):
    """947 (2): an adaptation is current only when its pins cover every layer manifest and every declared sidecar,
    and its own homebrew declaration names the campaign's sidecars; a matching subset proves nothing."""

    SIDE = "World_Building/Setting_A/Scenarios/Camp_One/homebrew_campaign.md"

    def with_sidecar(self, homebrew_decl=None, pin_sidecar=True):
        write(self.camp1 / "homebrew_campaign.md", "# House rule\n")
        self.campaign("Setting_A/Scenarios/Camp_One", ["Baseline", "Basesys"],
                      adaptation="Game_Systems/Basesys/adaptations/Baseline_Basesys.md", homebrew="[homebrew_campaign.md]")
        pins = self.default_pins() + (self.pin(f"engine:{self.SIDE}") if pin_sidecar else "")
        write(self.adapt, self.adaptation_text(built=pins, homebrew=homebrew_decl))

    def test_the_reviewed_repro_an_added_sidecar_is_not_covered(self):
        write(self.adapt, self.adaptation_text(homebrew="none"))
        self.assertTrue(self.resolve(campaign="Camp_One").authoritative_inputs)
        write(self.camp1 / "homebrew_campaign.md", "one\n")
        self.campaign("Setting_A/Scenarios/Camp_One", ["Baseline", "Basesys"],
                      adaptation="Game_Systems/Basesys/adaptations/Baseline_Basesys.md", homebrew="[homebrew_campaign.md]")
        first = self.resolve(campaign="Camp_One")
        write(self.camp1 / "homebrew_campaign.md", "two\n")
        second = self.resolve(campaign="Camp_One")
        self.assertNotEqual(first.sidecars[0].sha256, second.sidecars[0].sha256)
        for res in (first, second):
            self.assertFalse(res.authoritative_inputs)
            self.assertFalse(res.refused, res.refusals)
            self.assertIn(f"does not pin the sidecar {self.SIDE}", res.adaptation.status)
        self.assertIn("NON-AUTHORITATIVE", self.status(campaign="Camp_One"))

    def test_a_covered_sidecar_is_current_and_tracks_changes(self):
        self.with_sidecar(homebrew_decl=f"[engine:{self.SIDE}]")
        res = self.resolve(campaign="Camp_One")
        self.assertTrue(res.authoritative_inputs, res.adaptation.status)
        self.assertIn("pins every layer manifest and sidecar", res.adaptation.status)
        write(self.camp1 / "homebrew_campaign.md", "# House rule, edited\n")
        res = self.resolve(campaign="Camp_One")
        self.assertFalse(res.authoritative_inputs)
        self.assertIn("STALE", res.adaptation.status)

    def test_the_homebrew_declaration_must_name_the_campaigns_sidecars(self):
        for decl in (None, "none", "[engine:Game_Systems/Basesys/basesys.md]"):
            with self.subTest(declared=decl):
                self.with_sidecar(homebrew_decl=decl)
                res = self.resolve(campaign="Camp_One")
                self.assertFalse(res.authoritative_inputs)
                self.assertIn("was built for homebrew", res.adaptation.status)
        # a sidecar removed from the campaign while the adaptation still declares it
        self.with_sidecar(homebrew_decl=f"[engine:{self.SIDE}]")
        self.campaign("Setting_A/Scenarios/Camp_One", ["Baseline", "Basesys"],
                      adaptation="Game_Systems/Basesys/adaptations/Baseline_Basesys.md", homebrew="none")
        res = self.resolve(campaign="Camp_One")
        self.assertFalse(res.authoritative_inputs)
        self.assertIn("but the campaign declares none", res.adaptation.status)

    def test_an_uncovered_layer_manifest_or_an_unrelated_pin_proves_nothing(self):
        cases = {
            "the basesys manifest": self.pin("engine:Game_Systems/Baseline/baseline.md"),
            "the baseline manifest": self.pin("basesys.md", self.root / "Game_Systems" / "Basesys" / "basesys.md"),
            "the baseline manifest, the basesys manifest": self.pin("engine:Game_Systems/Basesys/rules/core.md"),
        }
        for missing, pins in cases.items():
            with self.subTest(pins_lack=missing):
                write(self.adapt, self.adaptation_text(built=pins))
                res = self.resolve(campaign="Camp_One")
                self.assertFalse(res.authoritative_inputs)
                self.assertIn(f"does not pin {missing};", res.adaptation.status)
                self.assertFalse(res.refused, res.refusals)

    def test_a_missing_declared_sidecar_still_refuses(self):
        self.with_sidecar(homebrew_decl=f"[engine:{self.SIDE}]")
        (self.camp1 / "homebrew_campaign.md").unlink()
        res = self.resolve(campaign="Camp_One")
        self.assertTrue(any(f"declared sidecar {self.SIDE} does not exist" in r for r in res.refusals))
        self.assertFalse(res.authoritative_inputs)

    def test_the_real_adaptation_profiles_read_only(self):
        """Every real adaptation profile (found, not named) keeps its pre-947 verdict for a sidecar-free campaign: one
        recording built_against in the checkable {path, sha256} list form is current, one in any other form (e.g.
        shortened hashes in a mapping) is non-authoritative as uncheckable. Real files are only read, and their hashes
        are checked unchanged."""
        found = sorted({*(REAL_ROOT / "Game_Systems").glob("Adaptations/*.md"),
                        *(REAL_ROOT / "Game_Systems").glob("*/adaptations/*.md")})
        profiles = [(p, d) for p in found for d in [si._read_manifest(p)]
                    if isinstance(d, dict) and isinstance(d.get("chain"), list) and "built_against" in d]
        if not profiles:
            self.skipTest("no real adaptation profile is present")
        known = si.known_modules(REAL_ROOT)[0]
        for path, data in profiles:
            rel = path.relative_to(REAL_ROOT).as_posix()
            with self.subTest(profile=rel):
                before = hashlib.sha256(path.read_bytes()).hexdigest()
                checkable = isinstance(data["built_against"], list)
                res = rc.Resolution(selector="campaign")
                rc._check_adaptation(REAL_ROOT, res, rel, [str(n).casefold() for n in data["chain"]], known)
                self.assertEqual(res.adaptation.current, checkable, res.adaptation.status)
                if not checkable:
                    self.assertIn("cannot be checked", res.adaptation.status)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)


class TestPathSafety(Fixture):
    """947 (3): nothing outside the corpus is opened; unsafe adaptation inputs are non-authoritative, unsafe campaign
    and sidecar inputs refuse."""

    def outside(self, name="sibling.md", text="outside the corpus\n") -> Path:
        return write(Path(self._tmp.name) / "outside" / name, text)

    def test_the_reviewed_repro_an_absolute_pin_outside_the_corpus(self):
        out = self.outside()
        write(self.adapt, self.adaptation_text(built=self.pin(out.as_posix(), out)))
        with mock.patch.object(rc, "_sha", side_effect=rc._sha) as hashed:
            res = self.resolve(campaign="Camp_One")
        self.assertFalse(res.authoritative_inputs)
        self.assertIn("not corpus-relative or resolves outside the corpus", res.adaptation.status)
        self.assertNotIn(rc._key(out), {rc._key(c.args[0]) for c in hashed.call_args_list})     # never read

    def test_unsafe_pin_spellings(self):
        base = self.root / "Game_Systems" / "Baseline" / "baseline.md"
        out = self.outside()
        for spec, path in ((f"engine:{out.as_posix()}", out), ("engine:/etc/passwd", base), ("engine:..\\x.md", base),
                           ("engine:Game_Systems/../Game_Systems/Baseline/baseline.md", base),
                           ("\\\\server\\share\\x.md", base), ("C:relative.md", base)):
            with self.subTest(spec=spec):
                write(self.adapt, self.adaptation_text(built=self.default_pins() + self.pin(spec, path)))
                res = self.resolve(campaign="Camp_One")
                self.assertFalse(res.authoritative_inputs)
                self.assertIn("not corpus-relative or resolves outside the corpus", res.adaptation.status)

    def test_links_leading_outside_the_corpus(self):
        target = Path(self._tmp.name) / "outside_dir"
        write(target / "x.md", "outside\n")
        write(target / "adapt.md", self.adaptation_text())
        write(target / rc.PROFILE_FILE, profile(["Baseline"]))
        self.link_dir(self.root / "Game_Systems" / "Basesys" / "outlink", target)
        self.link_dir(self.root / "World_Building" / "Setting_X" / "Camp_Out", target)
        # a pin through the link: non-authoritative, never read
        write(self.adapt, self.adaptation_text(built=self.default_pins()
                                               + self.pin("engine:Game_Systems/Basesys/outlink/x.md", target / "x.md")))
        res = self.resolve(campaign="Camp_One")
        self.assertFalse(res.authoritative_inputs)
        self.assertIn("resolves outside the corpus", res.adaptation.status)
        # the adaptation itself through the link: non-authoritative
        write(self.adapt, self.adaptation_text())
        self.campaign("Setting_A/Scenarios/Camp_One", ["Baseline", "Basesys"],
                      adaptation="Game_Systems/Basesys/outlink/adapt.md")
        res = self.resolve(campaign="Camp_One")
        self.assertFalse(res.authoritative_inputs)
        self.assertIn("resolves outside the corpus (through a link or junction)", res.adaptation.status)
        # a sidecar through the link: refuses
        self.campaign("Setting_B/Camp_Two", ["Baseline"], homebrew="[Game_Systems/Basesys/outlink/x.md]")
        res = self.resolve(campaign="Camp_Two")
        self.assertTrue(any("sidecar Game_Systems/Basesys/outlink/x.md resolves outside the corpus" in r
                            for r in res.refusals), res.refusals)
        self.assertEqual(res.sidecars[0].sha256, "")
        # a campaign folder that is a link: refuses, and its profile is never read
        with mock.patch.object(rc, "_profile_fields", side_effect=rc._profile_fields) as read:
            res = self.resolve(campaign="Camp_Out")
        self.assertTrue(any("resolves outside the corpus" in r for r in res.refusals), res.refusals)
        self.assertEqual(read.call_count, 0)

    def test_an_unsafe_adaptation_homebrew_declaration(self):
        write(self.camp1 / "homebrew_campaign.md", "# House rule\n")
        self.campaign("Setting_A/Scenarios/Camp_One", ["Baseline", "Basesys"],
                      adaptation="Game_Systems/Basesys/adaptations/Baseline_Basesys.md", homebrew="[homebrew_campaign.md]")
        side = "World_Building/Setting_A/Scenarios/Camp_One/homebrew_campaign.md"
        write(self.adapt, self.adaptation_text(built=self.default_pins() + self.pin(f"engine:{side}"),
                                               homebrew=f"[{self.outside().as_posix()}]"))
        res = self.resolve(campaign="Camp_One")
        self.assertFalse(res.authoritative_inputs)
        self.assertIn("not a corpus-relative path inside the corpus", res.adaptation.status)


class TestDiscoveryContainment(Fixture):
    """949 (1): module discovery opens nothing outside the corpus. A discovery root, module folder, index.cfg or
    manifest that resolves out is never listed or read, and its module is not admitted; an indexed layer's index.cfg
    is read from its validated folder, never by re-running the builder's discovery."""

    def spies(self):
        return (mock.patch.object(si, "_read_manifest", side_effect=si._read_manifest),
                mock.patch.object(si, "declared_module", side_effect=si.declared_module))

    def assert_never_read(self, spy, *paths):
        opened = {rc._key(c.args[0]) for c in spy.call_args_list}
        for p in paths:
            self.assertNotIn(rc._key(p), opened, f"{p} was read")

    def test_the_reviewed_repro_a_junctioned_legacy_folder(self):
        sib = Path(self._tmp.name) / "sibling"
        write(sib / "ghost.md", manifest("ghost"))
        self.link_dir(self.root / "Game_Systems" / "Ghost", sib)
        cfg = self.rules(f"[rules_layers]\nprivate_roots = {PRIVATE}\nnot_searched = baseline, ghost\n")
        reads, decls = self.spies()
        with reads as spy, decls:
            res = self.resolve(chain="ghost", cfg=cfg)
            known, ambiguous = si.known_modules(self.root, (PRIVATE,))
        self.assert_never_read(spy, sib / "ghost.md")
        self.assertNotIn("ghost", known)
        self.assertNotIn("ghost", ambiguous)                    # a folder that leads out claims nothing
        self.assertTrue(res.refused)
        self.assertNotIn(rc.ROLE_LOADED, [l.role for l in res.layers])
        self.assertTrue(any("'ghost', which is no known module" in r for r in res.refusals), res.refusals)

    def test_a_junctioned_private_module_and_a_junctioned_root(self):
        sib = Path(self._tmp.name) / "sibling_private"
        write(sib / "ghost2.md", manifest("ghost2"))
        write(sib / "index.cfg", "[system]\nmodule = ghost2\n")
        self.link_dir(self.root / PRIVATE / "Ghost2", sib)
        reads, decls = self.spies()
        with reads as rspy, decls as dspy:
            known, ambiguous = si.known_modules(self.root, (PRIVATE,))
            res = self.resolve(chain="ghost2")
        self.assert_never_read(rspy, sib / "ghost2.md")
        self.assert_never_read(dspy, sib / "index.cfg")
        self.assertNotIn("ghost2", known)
        self.assertTrue(any("'ghost2' is not a known module" in r for r in res.refusals), res.refusals)
        self.assertEqual({"baseline", "basesys", "hb"}, set(known))       # valid discovery is intact
        # a whole discovery root that leads out: nothing under it is listed or read
        other = Path(self._tmp.name) / "corpus2"
        outside = Path(self._tmp.name) / "outside_systems"
        write(outside / "Ghost3" / "ghost3.md", manifest("ghost3"))
        other.mkdir()
        self.link_dir(other / "Game_Systems", outside)
        reads, decls = self.spies()
        with reads as rspy, decls:
            self.assertEqual(si.known_modules(other), ({}, set()))
        self.assert_never_read(rspy, outside / "Ghost3" / "ghost3.md")

    def test_an_indexed_layer_never_reruns_discovery(self):
        sib = Path(self._tmp.name) / "sibling_cfg"
        write(sib / "ghost.md", manifest("ghost"))
        write(sib / "index.cfg", "[system]\nmodule = basesys\n")              # would also collide, if it were read
        self.link_dir(self.root / "Game_Systems" / "Ghost", sib)
        reads, decls = self.spies()
        with reads as rspy, decls as dspy, mock.patch.object(si, "find_cfg", side_effect=AssertionError("ran")):
            res = self.resolve(chain="baseline,basesys,hb")
        self.assert_never_read(dspy, sib / "index.cfg")
        self.assert_never_read(rspy, sib / "ghost.md")
        self.assertFalse(res.refused, res.refusals)
        self.assertEqual([(l.role, l.freshness) for l in res.layers[1:]],
                         [(rc.ROLE_INDEXED, "unchanged"), (rc.ROLE_INDEXED, "unchanged")])

    def test_a_linked_manifest_or_index_cfg_file_is_never_read(self):
        out = Path(self._tmp.name) / "outside_files"
        write(out / "linked.md", manifest("linked"))
        write(out / "index.cfg", "[system]\nmodule = linkcfg\n")
        write(out / "linkman.md", manifest("linkman"))
        legacy = self.root / "Game_Systems" / "Linked"                # a legacy folder whose manifest leads out
        cfgdir = self.root / "Game_Systems" / "Linkcfg"               # an index.cfg that leads out
        mandir = self.root / "Game_Systems" / "Linkman"               # a real index.cfg whose manifest leads out
        legacy.mkdir(parents=True)
        write(cfgdir / "linkcfg.md", manifest("linkcfg"))
        write(mandir / "index.cfg", "[system]\nmodule = linkman\n")
        try:
            (legacy / "linked.md").symlink_to(out / "linked.md")
            (cfgdir / "index.cfg").symlink_to(out / "index.cfg")
            (mandir / "linkman.md").symlink_to(out / "linkman.md")
        except OSError as e:
            self.skipTest(f"cannot make a file symlink here ({e})")
        reads, decls = self.spies()
        with reads as rspy, decls as dspy:
            known, _ = si.known_modules(self.root, (PRIVATE,))
        self.assert_never_read(rspy, out / "linked.md", legacy / "linked.md", out / "linkman.md", mandir / "linkman.md")
        self.assert_never_read(dspy, out / "index.cfg", cfgdir / "index.cfg")
        for mid in ("linked", "linkcfg", "linkman"):
            self.assertNotIn(mid, known)


class TestBuilderContainment(Fixture):
    """951: the builder's discovery and the shared loader open nothing outside the corpus. discover (behind
    cfgs_for, find_cfg, --system, --all-systems and pruning) offers no root, folder or index.cfg that leads out;
    load_system_cfg never opens an index.cfg, manifest or relations.yaml that resolves outside its module folder.
    A refused unsafe input leaves the registry and the generations untouched."""

    def published(self):
        sdir = si.systems_dir(self.index)
        return (hashlib.sha256((sdir / si.REGISTRY).read_bytes()).hexdigest(), sorted(p.name for p in sdir.glob("*.db")))

    def opened(self):
        """Spies on every way the shared code reads a file: Path.read_text / read_bytes, and the cfg loader."""
        seen = []
        real_text, real_bytes, real_cfg = Path.read_text, Path.read_bytes, si.load_cfg

        def text(p, *a, **k):
            seen.append(rc._key(p))
            return real_text(p, *a, **k)

        def data(p, *a, **k):
            seen.append(rc._key(p))
            return real_bytes(p, *a, **k)

        def cfg(p, *a, **k):
            seen.append(rc._key(p))
            return real_cfg(p, *a, **k)
        patches = [mock.patch.object(Path, "read_text", text), mock.patch.object(Path, "read_bytes", data),
                   mock.patch.object(si, "load_cfg", cfg)]
        return patches, seen

    def symlink(self, link: Path, target: Path):
        try:
            link.symlink_to(target)
        except OSError as e:
            self.skipTest(f"cannot make a file symlink here ({e})")

    def test_the_reviewed_repro_a_linked_relations_file(self):
        out = write(Path(self._tmp.name) / "outside" / "relations.yaml", relation())
        rel = self.hb_cfg.parent / si.RELATIONS_FILE
        rel.unlink()
        self.symlink(rel, out)
        before = self.published()
        patches, seen = self.opened()
        with patches[0], patches[1], patches[2], \
                mock.patch.object(si, "parse_relations", side_effect=si.parse_relations) as parsed:
            res = self.resolve(chain="baseline,basesys,hb")
            out_text = self.status(chain="baseline,basesys,hb")
            with self.assertRaisesRegex(si.SystemIndexError, "relations.yaml resolves outside the module"):
                bi.build_and_publish(self.root, self.index, self.hb_cfg, build_vectors=False)
        self.assertEqual(parsed.call_count, 0)
        self.assertNotIn(rc._key(out), seen)                             # never opened or hashed
        self.assertFalse(res.refused, res.refusals)                      # status reports, it does not crash or refuse
        self.assertTrue(res.layers[2].freshness.startswith("unknown: could not recompute"), res.layers[2].freshness)
        self.assertIn("relations.yaml resolves outside the module", res.layers[2].freshness)
        self.assertIn("[!] sources unknown: could not recompute", out_text)
        self.assertEqual(self.published(), before)                       # the build refused before publication
        self.assertEqual([l.freshness for l in res.layers[1:2]], ["unchanged"])   # contained metadata unaffected

    def test_the_reviewed_repro_a_junctioned_module_folder(self):
        mod = Path(self._tmp.name) / "sibling" / "module"
        write(mod / "index.cfg", "[system]\nmodule = ghost\n")
        write(mod / "ghost.md", manifest("ghost"))
        self.link_dir(self.root / "Game_Systems" / "Ghost", mod)
        mod2 = Path(self._tmp.name) / "sibling" / "module2"
        write(mod2 / "index.cfg", "[system]\nmodule = ghost2\n")
        self.link_dir(self.root / PRIVATE / "Ghost2", mod2)
        before = self.published()
        args_one = mock.Mock(all_systems=False, system="ghost", no_vectors=True)
        args_all = mock.Mock(all_systems=True, system=None, no_vectors=True)
        patches, seen = self.opened()
        with patches[0], patches[1], patches[2], \
                mock.patch.object(si, "declared_module", side_effect=si.declared_module) as decl:
            self.assertEqual(si.cfgs_for(self.root, "ghost", (PRIVATE,)), [])
            self.assertEqual(si.cfgs_for(self.root, "ghost2", (PRIVATE,)), [])
            self.assertIsNone(si.find_cfg(self.root, "ghost", (PRIVATE,)))
            discovered = {p.parent.name for p in si.discover(self.root, (PRIVATE,))}
            with mock.patch("builtins.print"):
                self.assertEqual(bi.run_systems(args_one, self.root, self.index, (PRIVATE,)), 1)
            self.assertEqual(self.published(), before)                   # refused: nothing written
            with mock.patch("builtins.print"):
                self.assertEqual(bi.run_systems(args_all, self.root, self.index, (PRIVATE,)), 0)
        for outside in (mod / "index.cfg", mod / "ghost.md", mod2 / "index.cfg"):
            self.assertNotIn(rc._key(outside), seen + [rc._key(c.args[0]) for c in decl.call_args_list])
        self.assertEqual(discovered, {"Basesys", "Hb"})                  # normal in-corpus discovery intact
        reg = self.registry()["systems"]
        self.assertEqual(set(reg), {"basesys", "hb"})                    # --all-systems rebuilt only those
        sdir = si.systems_dir(self.index)
        self.assertFalse([p for p in sdir.glob("*.db") if p.name.startswith(("ghost.", "ghost2."))])

    def test_a_linked_index_cfg_or_manifest_and_a_junctioned_root(self):
        out = Path(self._tmp.name) / "outside_files"
        write(out / "index.cfg", "[system]\nmodule = lnk\n")
        write(out / "lman.md", manifest("lman"))
        lnk = self.root / "Game_Systems" / "Lnk"                         # an in-corpus folder, its index.cfg a link
        write(lnk / "lnk.md", manifest("lnk"))
        self.symlink(lnk / "index.cfg", out / "index.cfg")
        lman = self.root / "Game_Systems" / "Lman"                       # a real index.cfg, its manifest a link
        write(lman / "index.cfg", "[system]\nmodule = lman\n\n[representation verbatim]\npath = rules\n"
                                  "authority = source\ninclude = *.md\n")
        write(lman / "rules" / "core.md", "# Core\n")
        self.symlink(lman / "lman.md", out / "lman.md")
        before = self.published()
        patches, seen = self.opened()
        with patches[0], patches[1], patches[2], \
                mock.patch.object(si, "_read_manifest", side_effect=si._read_manifest) as man:
            self.assertNotIn("Lnk", {p.parent.name for p in si.discover(self.root, (PRIVATE,))})
            with self.assertRaisesRegex(si.SystemIndexError, "resolves outside its module folder"):
                si.load_system_cfg(lnk / "index.cfg")
            with self.assertRaisesRegex(si.SystemIndexError, "the manifest lman.md resolves outside the module"):
                si.load_system_cfg(lman / "index.cfg")
            with self.assertRaisesRegex(si.SystemIndexError, "the manifest lman.md resolves outside the module"):
                bi.build_and_publish(self.root, self.index, lman / "index.cfg", build_vectors=False)
        opened = seen + [rc._key(c.args[0]) for c in man.call_args_list]
        for outside in (out / "index.cfg", out / "lman.md", lman / "lman.md"):
            self.assertNotIn(rc._key(outside), opened)
        self.assertEqual(self.published(), before)
        # a whole Game_Systems root that leads out offers nothing
        other = Path(self._tmp.name) / "corpus2"
        other.mkdir()
        outside_systems = Path(self._tmp.name) / "outside_systems"
        write(outside_systems / "Ghost3" / "index.cfg", "[system]\nmodule = ghost3\n")
        self.link_dir(other / "Game_Systems", outside_systems)
        with mock.patch.object(si, "declared_module", side_effect=si.declared_module) as decl:
            self.assertEqual(si.discover(other), [])
            self.assertEqual(si.cfgs_for(other, "ghost3"), [])
        self.assertEqual(decl.call_count, 0)


class TestRegistryShape(Fixture):
    """947 (4): registry entries are validated before use; a malformed one refuses its layer with an actionable
    reason, never an exception, and nothing is written."""

    def corrupt(self, module, value):
        reg = self.registry()
        reg["systems"][module] = value(reg["systems"][module]) if callable(value) else value
        si.write_registry(si.systems_dir(self.index), reg)
        return hashlib.sha256((si.systems_dir(self.index) / si.REGISTRY).read_bytes()).hexdigest()

    def test_the_reviewed_repro_a_string_entry(self):
        before = self.corrupt("basesys", "invalid entry")
        out = self.status(chain="basesys")
        self.assertTrue(out.startswith("[!] Chain refused — 1 problem(s)"), out)
        self.assertIn("layer basesys: the registry entry is not a mapping (it is a str)", out)
        self.assertIn("rebuild it (build_indexes.py --system basesys)", out)
        self.assertEqual(hashlib.sha256((si.systems_dir(self.index) / si.REGISTRY).read_bytes()).hexdigest(), before)

    def test_malformed_fields(self):
        def drop(key):
            return lambda e: {k: v for k, v in e.items() if k != key}

        def setf(key, val, nested=None):
            def f(e):
                e = json.loads(json.dumps(e))
                (e[nested] if nested else e)[key] = val
                return e
            return f
        cases = [
            ("basesys", "has no build_id string", drop("build_id")),
            ("basesys", "has no db string", setf("db", 7)),
            ("basesys", "has no source_fingerprint string", drop("source_fingerprint")),
            ("basesys", "has no integer schema_version", setf("schema_version", True)),
            ("basesys", "has a built_at that is not a string", setf("built_at", 5)),
            ("hb", "has a layer that is not a mapping", setf("layer", "x")),
            ("hb", "has a layer.depends_on that is not a mapping", setf("depends_on", ["basesys"], "layer")),
            ("hb", "has a layer.depends_on that is not a mapping", setf("depends_on", {"basesys": 3}, "layer")),
            ("hb", "has a layer.extends that is not a module id", setf("extends", ["basesys"], "layer")),
        ]
        saved = (si.systems_dir(self.index) / si.REGISTRY).read_bytes()
        for module, why, change in cases:
            with self.subTest(module=module, why=why):
                (si.systems_dir(self.index) / si.REGISTRY).write_bytes(saved)
                self.corrupt(module, change)
                res = self.resolve(chain=f"baseline,{module}")
                layer = res.layers[1]
                self.assertEqual(layer.role, rc.ROLE_MISSING)
                self.assertIn(why, layer.reason)
                self.assertTrue(any(f"layer {module}: the registry entry {why}" in r for r in res.refusals))

    def test_a_malformed_dependency_is_reported_and_left_out_of_the_snapshot(self):
        self.corrupt("basesys", "invalid entry")
        res = self.resolve(chain="baseline,hb")
        self.assertFalse(res.refused, res.refusals)
        self.assertEqual(res.layers[1].role, rc.ROLE_INDEXED)
        self.assertIn("depends on basesys, whose registry entry is malformed", res.layers[1].notes)
        h = hashlib.sha256(b"rules-chain-snapshot/v1\n")
        h.update(f"hb\0{self.hb.build_id}\n".encode())
        self.assertEqual(res.token, h.hexdigest())

    def test_a_null_entry_is_malformed_not_absent(self):
        """949 (2): presence is by key. A null entry refuses a selected layer before the declared-loaded branch; a
        truly absent declared-loaded layer is unchanged; an unrelated null entry does not block."""
        self.assertEqual(self.roles(self.resolve(chain="baseline")), [("baseline", rc.ROLE_LOADED)])   # truly absent
        sdir = si.systems_dir(self.index)
        saved = (sdir / si.REGISTRY).read_bytes()
        for module, chain in (("baseline", "baseline"), ("basesys", "baseline,basesys")):
            with self.subTest(null=module):
                (sdir / si.REGISTRY).write_bytes(saved)
                before = self.corrupt(module, None)
                res = self.resolve(chain=chain)
                layer = next(l for l in res.layers if l.module == module)
                self.assertEqual(layer.role, rc.ROLE_MISSING)
                self.assertIn("is not a mapping (it is a NoneType)", layer.reason)
                self.assertTrue(any(f"layer {module}: the registry entry is not a mapping (it is a NoneType)" in r
                                    for r in res.refusals), res.refusals)
                self.assertIn(f"layer {module}: the registry entry is not a mapping", self.status(chain=chain))
                self.assertEqual(hashlib.sha256((sdir / si.REGISTRY).read_bytes()).hexdigest(), before)
        (sdir / si.REGISTRY).write_bytes(saved)
        self.corrupt("baseline", "invalid entry")                 # a declared-loaded layer's string entry, too
        self.assertTrue(any("layer baseline: the registry entry is not a mapping (it is a str)" in r
                            for r in self.resolve(chain="baseline").refusals))
        (sdir / si.REGISTRY).write_bytes(saved)
        reg = self.registry()
        reg["systems"]["unrelated"] = None                        # not in the chain: nonblocking
        si.write_registry(sdir, reg)
        res = self.resolve(chain="baseline,basesys,hb")
        self.assertFalse(res.refused, res.refusals)
        self.assertEqual([l.role for l in res.layers], [rc.ROLE_LOADED, rc.ROLE_INDEXED, rc.ROLE_INDEXED])

    def test_valid_entries_of_both_schemas_are_unchanged(self):
        res = self.resolve(chain="baseline,basesys,hb")
        self.assertFalse(res.refused, res.refusals)
        self.assertEqual([(l.role, l.schema, l.freshness) for l in res.layers[1:]],
                         [(rc.ROLE_INDEXED, 2, "unchanged"), (rc.ROLE_INDEXED, 3, "unchanged")])
        self.assertEqual([rc.entry_problem(e) for e in self.registry()["systems"].values()], [None, None])


class TestRealCampaignReadOnly(unittest.TestCase):
    """A real campaign's status is computed and nothing is written. Its contents are not asserted."""

    def test_status_writes_nothing(self):
        profiles = rc.campaign_profiles(REAL_ROOT)
        reg = REAL_INDEX / "systems" / si.REGISTRY
        if not profiles or not reg.exists():
            self.skipTest("no real campaign or index")
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in [reg, *profiles]}
        cfg_path = HERE / "indexer.cfg"
        res = rc.resolve(REAL_ROOT, REAL_INDEX, load_cfg(cfg_path) if cfg_path.exists() else {},
                         campaign=profiles[0].parent.name)
        self.assertEqual(res.selector, "campaign")
        self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}, before)


def main():
    ap = argparse.ArgumentParser(description="Self-test for rules-chain resolution (chain-aware search stage 2).")
    ap.add_argument("--no-pause", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    result = unittest.main(argv=[sys.argv[0], "-v"], exit=False).result
    print(f"Runtime: {time.time() - t0:.1f}s")
    if not args.no_pause:
        input("Press Enter to exit...")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

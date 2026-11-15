#!/usr/bin/env python3
"""
test_layers.py — Self-test for rules layers (chain-aware search, stage 1): private layer roots and the corpus
exclusion, manifest kind/extends with legacy defaults, relations.yaml, canonical unit hashes, the layered (schema 3)
build with dependency commitments, and dependency order.

Everything runs in process against synthetic modules in temporary directories, with temporary index directories and
registries; the builder's history log is redirected into the temporary directory. Nothing is written to the real
corpus, the live index or the live build history. One class reads the real Eclipse Phase module and its live
registry entry READ-ONLY, to prove a legacy module still validates unchanged and is not reported stale.

THE CONTRACTS THESE TESTS PIN (design: Working_Documents/Chain_Search_Design_Proposal_v2.md; Codex 936/938)
  Private roots   validate_private_roots accepts relative folders of two or more segments inside the corpus, outside
                  Game_Systems, index and Python, not overlapping, and — when they exist — holding only layer
                  folders (each with an index.cfg), a README.md and dotfiles, so existing lore is refused;
                  walk_and_collect drops their files from the search set by exact path prefix (a sibling folder
                  sharing the prefix text is kept) and still lists them in the directory index; with no roots
                  declared every output is identical. A [rules_layers] section that is present is strict: a
                  misspelled key, a bare line or an empty declaration fails the corpus and module builds closed.
  Dependencies    a dependency's schema must be supported (2 or 3) and agree between the registry and its database.
  Legacy modules  a manifest without kind or extends is a legacy module: schema 2, the original fingerprint, the
                  original registry entry keys, no layer tables.
  Layered modules extends or relations.yaml make a module layered: schema 3, layer_info, relations with pin states,
                  a fingerprint over manifest, relations and dependency build ids, a registry entry with its layer
                  metadata; refused when an entry or target is orphaned, a dependency is unbuilt or a dependency is
                  rebuilt during the build.
  Unit hashes     canonical_unit_bytes is exact and domain-separated; record hashes ignore JSON formatting, document
                  and section hashes ignore line endings and trailing whitespace, and every content change shows.
  Order           dependency_order puts every layer after its extends parent and relation targets; a cycle names
                  every stuck layer.
  Containment     the builder's three read-only opens of a published generation (the dependency snapshot, a relation
                  target, the reported module's own database) refuse a generation redirected out of index/systems
                  after it was resolved without opening it, and close one redirected while being opened unread; in
                  a build, nothing publishes (Codex 965). The embedding-cache seed's ATTACH of the live generation is
                  contained the same way: never attached when redirected, detached unread when redirected during the
                  attach, the refusal reported in the build's errors; a contained warm cache is still reused, and an
                  unavailable one still falls back quietly (Codex 967).
  Pruning         --all-systems keeps a module whose index.cfg is gone registered while a published dependent needs
                  it (transitively), says so and exits 1; it unregisters nothing when discovery finds no index.cfg
                  but the registry is not empty. It claims a module exactly as --system does (find_cfg), and a
                  --system build refuses a dependency cycle through the published builds (audit batch 2).
  Lock            the registry lock names its owner; a dead owner on this host is broken at once, any other after
                  LOCK_STALE_S, which is below the wait; breaking never removes a lock taken since; release
                  removes only our own; sharing violations are retried briefly, then raised; a killed build's
                  temp files are swept once old, a live one's never (audit batch 4: B3, B6, B7).
  Loaded parent   a layer may extend a module declared not_searched and never built; a relation into one refuses;
                  a built dependency is validated even when also declared (B8).
  Anchor          a systems directory leading out of the corpus refuses build, report and prune before anything is
                  read or written there; one configured outside on purpose is accepted; a registry.json linking
                  out is not read (N1).

Usage:
    python -m unittest test_layers -v
    python test_layers.py [--no-pause]

Command line arguments:
    --no-pause   Skip end-of-run pause

# changed 2026-10-18: created (chain-aware search stage 1, Codex 938).
# changed 2026-10-18: regression tests for Codex 940's three findings (lore as a private root; a misspelled
#   [rules_layers] section failing open; unsupported or disagreeing dependency schemas).
# changed 2026-11-12: stage 2 added the not_searched key: the strictness test now expects it to name a known module,
#   and an empty section to be refused as declaring neither key.
# changed 2026-11-13: TestBuilderContainment (Codex 965): a redirect after resolution and during the open, at each of
#   the builder's three opens of a published generation, through both the build and the relations report.
# changed 2026-11-13: TestEmbedCacheContainment (Codex 967): the embedding-cache ATTACH, on Codex's recipe.
# changed 2026-11-14: TestAllSystemsSafety (audit batch 2); prune_registry now returns (unregistered, held, refused).
# changed 2026-11-15: TestLockAndTempHygiene, TestLoadedParent and TestSystemsDirAnchor (audit batch 4).
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_indexes as bi      # noqa: E402
import system_index as si       # noqa: E402
from cfg_loader import load_cfg  # noqa: E402

REAL_ROOT = HERE.parent
REAL_EP_CFG = REAL_ROOT / "Game_Systems" / "EclipsePhase" / "index.cfg"
REAL_REGISTRY = REAL_ROOT / "index" / "systems" / "registry.json"
PRIVATE = "World_Building/Rules_Layers"
LEGACY_ENTRY_KEYS = {"module", "db", "build_id", "schema_version", "built_at", "module_dir", "cfg", "cfg_sha256",
                     "source_fingerprint", "counts"}

CORE_MD = """---
name: Core Rules
type: rules
---
# Core Rules

The opening paragraph.

## Fatigue

Marching all day costs one fatigue level.

## Healing

Rest heals one point.

### Deep Rest

A full day of rest heals three points.
"""

HOUSE_MD = """# House Rules

## Forced March

A forced march costs two fatigue levels. ZEBRAPROBE
"""


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def manifest(module: str, **fields) -> str:
    lines = [f"module: {module}"] + [f"{k}: {v}" for k, v in fields.items()]
    return f"# {module}\n\n```yaml\n" + "\n".join(lines) + "\n```\n"


def make_base(root: Path, dirname="Basesys", module="basesys", **fields) -> Path:
    d = root / "Game_Systems" / dirname
    write(d / f"{module}.md", manifest(module, resolution="defined", **fields))
    write(d / "rules" / "core.md", CORE_MD)
    write(d / "data" / "items.jsonl", json.dumps({"id": "item/rope", "name": "Rope", "dataset": "items",
                                                   "kind": "gear", "weight": 1}) + "\n")
    write(d / "index.cfg", f"[system]\nmodule = {module}\n\n[representation verbatim]\npath = rules\n"
                           f"authority = source\ninclude = *.md\n\n[representation dataset]\npath = data\n"
                           f"authority = derived\ninclude = *.jsonl\n")
    return d / "index.cfg"


def make_layer(root: Path, module="hb", dirname="Hb", base=PRIVATE, relations=None, **fields) -> Path:
    d = root / base / dirname
    fields = fields or {"kind": "homebrew", "extends": "basesys"}
    write(d / f"{module}.md", manifest(module, **fields))
    write(d / "notes" / "house.md", HOUSE_MD)
    write(d / "index.cfg", f"[system]\nmodule = {module}\n\n[representation verbatim]\npath = notes\n"
                           f"authority = source\ninclude = *.md\n")
    if relations is not None:
        write(d / si.RELATIONS_FILE, relations)
    return d / "index.cfg"


def relation(target_key="doc:rules/core.md", heading="Fatigue", level=2, pin=None, mode="extend", status="open",
             entry_heading="Forced March", extra=""):
    pin_line = f"\n  target_sha256: \"{pin}\"" if pin else ""
    sec = f", section: {{heading: \"{heading}\", level: {level}}}" if heading else ""
    esec = f", section: {{heading: \"{entry_heading}\", level: 2}}" if entry_heading else ""
    return (f"- entry: {{key: \"doc:notes/house.md\"{esec}}}\n"
            f"  target: {{layer: basesys, key: \"{target_key}\"{sec}}}\n"
            f"  mode: {mode}\n  status: {status}{pin_line}{extra}\n")


class Tmp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "corpus"
        self.root.mkdir()
        self.index = self.root / "index"
        p = mock.patch.object(bi, "HISTORY_PATH", Path(self._tmp.name) / "history.jsonl")
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        self._tmp.cleanup()

    @property
    def sdir(self):
        return si.systems_dir(self.index)

    def registry(self):
        return si.read_registry(self.sdir)

    def build(self, cfg_path):
        return bi.build_and_publish(self.root, self.index, cfg_path, build_vectors=False)

    def db(self, module):
        return si.resolve_db(self.sdir, module, self.registry()["systems"][module])

    def query(self, module, sql, args=()):
        conn = sqlite3.connect(f"{self.db(module).as_uri()}?mode=ro", uri=True)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def registry_bytes(self):
        p = self.sdir / si.REGISTRY
        return p.read_bytes() if p.exists() else b""

    def generations(self):
        return sorted(p.name for p in self.sdir.glob("*.db")) if self.sdir.exists() else []


# ================================================================ private roots and the corpus exclusion

class TestPrivateRoots(Tmp):
    def test_valid_roots_are_normalised(self):
        got = si.validate_private_roots(self.root, ["World_Building/Rules_Layers/", "World_Building\\Other_Layers"])
        self.assertEqual(got, ("World_Building/Rules_Layers", "World_Building/Other_Layers"))
        self.assertEqual(si.validate_private_roots(self.root, []), ())

    def test_invalid_roots_are_refused(self):
        cases = {
            "/abs/path": "relative path",
            "C:/Users/x": "relative path",
            "World_Building/../Python": "relative path",
            "World_Building": "top-level directory",
            "Game_Systems/Mine": "may not be inside",
            "index/systems": "may not be inside",
            "Python/x": "may not be inside",
        }
        for raw, why in cases.items():
            with self.subTest(root=raw), self.assertRaisesRegex(si.SystemIndexError, why):
                si.validate_private_roots(self.root, [raw])
        with self.assertRaisesRegex(si.SystemIndexError, "overlap"):
            si.validate_private_roots(self.root, ["World_Building/A", "world_building/a/B"])
        with self.assertRaisesRegex(si.SystemIndexError, "overlap"):
            si.validate_private_roots(self.root, ["World_Building/A", "World_Building/a"])

    def test_an_existing_lore_tree_is_refused(self):
        # Codex 940's repro: ordinary lore under a two-segment folder must not be declarable as a private root.
        write(self.root / "World_Building" / "Setting_A" / "Locations" / "Old_Mill.md", "# Old Mill\n\nLore.\n")
        with self.assertRaisesRegex(si.SystemIndexError, r"holds Locations/, which is not a rules layer"):
            si.validate_private_roots(self.root, ["World_Building/Setting_A"])
        write(self.root / "World_Building" / "Setting_B" / "Notes.md", "loose lore\n")
        with self.assertRaisesRegex(si.SystemIndexError, r"holds Notes.md, which is not a rules layer"):
            si.validate_private_roots(self.root, ["World_Building/Setting_B"])
        write(self.root / "World_Building" / "Layers" / "Started" / "draft.md", "a layer without its cfg yet\n")
        with self.assertRaisesRegex(si.SystemIndexError, "add its index.cfg first"):
            si.validate_private_roots(self.root, ["World_Building/Layers"])
        write(self.root / "World_Building" / "Afile", "x")
        with self.assertRaisesRegex(si.SystemIndexError, "is a file, not a folder"):
            si.validate_private_roots(self.root, ["World_Building/Afile"])

    def test_dedicated_and_layer_only_roots_are_accepted(self):
        self.assertEqual(si.validate_private_roots(self.root, [PRIVATE]), (PRIVATE,))           # not yet created
        (self.root / PRIVATE).mkdir(parents=True)
        self.assertEqual(si.validate_private_roots(self.root, [PRIVATE]), (PRIVATE,))           # empty
        make_layer(self.root)
        make_layer(self.root, module="hb2", dirname="Hb2")
        write(self.root / PRIVATE / "README.md", "What these layers are.\n")
        write(self.root / PRIVATE / ".gitkeep", "")
        (self.root / PRIVATE / ".hidden").mkdir()
        self.assertEqual(si.validate_private_roots(self.root, [PRIVATE]), (PRIVATE,))           # populated, layers only

    def test_the_cfg_declares_them(self):
        cfg_path = write(self.root / "x.cfg", "[paths]\nroot_directory = .\n\n[rules_layers]\n"
                                              "private_roots = World_Building/Rules_Layers, Lore/Homebrew_Layers\n")
        self.assertEqual(bi.parse_private_roots(load_cfg(cfg_path), self.root),
                         ("World_Building/Rules_Layers", "Lore/Homebrew_Layers"))
        bare = write(self.root / "y.cfg", "[paths]\nroot_directory = .\n")
        self.assertEqual(bi.parse_private_roots(load_cfg(bare), self.root), ())
        bad = write(self.root / "z.cfg", "[rules_layers]\nprivate_roots = World_Building\n")
        with self.assertRaises(si.SystemIndexError):
            bi.parse_private_roots(load_cfg(bad), self.root)

    def test_a_present_section_is_strict(self):
        cases = {
            "private_root = World_Building/Rules_Layers\n": "unknown key 'private_root'",      # Codex 940's repro
            # Stage 2 added not_searched; it must name a known module (none exists in this fixture).
            "private_roots = World_Building/Rules_Layers\nnot_searched = baseline\n": "not_searched names 'baseline', "
                                                                                     "which is no known module",
            "World_Building/Rules_Layers/\n": "is not key = value (write: private_roots = World_Building/Rules_Layers)",
            "private_roots =\n": "private_roots names no folder",
            "private_roots = , ,\n": "private_roots names no folder",
            "not_searched =\n": "not_searched names no module",
            "": "declares neither private_roots nor not_searched",
        }
        for body, why in cases.items():
            with self.subTest(body=body):
                cfg_path = write(self.root / "s.cfg", "[paths]\nroot_directory = .\n\n[rules_layers]\n" + body)
                with self.assertRaisesRegex(si.SystemIndexError, re.escape(why)):
                    bi.parse_private_roots(load_cfg(cfg_path), self.root)

    def test_the_corpus_builder_refuses_a_misspelled_section(self):
        make_layer(self.root)
        idx = Path(self._tmp.name) / "typo_index"
        cfg_path = write(Path(self._tmp.name) / "typo.cfg",
                         f"[paths]\nroot_directory = {self.root}\nindex_directory = {idx}\n\n"
                         f"[file_types]\nmode = whitelist\n*.md\n\n[rules_layers]\nprivate_root = {PRIVATE}\n")
        argv = ["build_indexes.py", "--cfg", str(cfg_path), "--no-pause", "--no-vectors"]
        with mock.patch.object(sys, "argv", argv), mock.patch.dict("os.environ", {"CORPUS_ROOT": ""}), \
                mock.patch("builtins.print") as printed:
            self.assertEqual(bi.main(), 1)
        said = " ".join(str(a) for c in printed.call_args_list for a in c.args)
        self.assertIn("unknown key 'private_root'", said)
        self.assertFalse((idx / bi.DB_FILENAME).exists())                   # nothing was built, so nothing leaked
        argv_sys = ["build_indexes.py", "--cfg", str(cfg_path), "--no-pause", "--all-systems", "--no-vectors"]
        with mock.patch.object(sys, "argv", argv_sys), mock.patch.dict("os.environ", {"CORPUS_ROOT": ""}), \
                mock.patch("builtins.print"):
            self.assertEqual(bi.main(), 1)                                  # module builds fail closed too
        self.assertFalse((idx / "systems").exists())


class TestCorpusExclusion(Tmp):
    def setUp(self):
        super().setUp()
        make_base(self.root)
        make_layer(self.root)
        write(self.root / "World_Building" / "Setting_A" / "Old_Mill.md", "# Old Mill\n\nThe mill. LOREPROBE\n")
        write(self.root / "World_Building" / "Rules_Layers_Other" / "x.md", "# Other\n\nBOUNDARYPROBE\n")

    def walk(self, **kw):
        return bi.walk_and_collect(self.root, set(), set(), {"game_systems"}, "whitelist", ["*.md"], **kw)

    def test_files_are_dropped_by_exact_prefix_and_still_listed(self):
        dirs, files = self.walk(search_excluded_prefixes=(PRIVATE,))
        rel = {f.relative_to(self.root).as_posix() for f in files}
        self.assertFalse([r for r in rel if r.startswith(PRIVATE + "/")])
        self.assertIn("World_Building/Setting_A/Old_Mill.md", rel)
        self.assertIn("World_Building/Rules_Layers_Other/x.md", rel)        # a sibling sharing the prefix text
        listed = {name for _d, name, _f in dirs}
        self.assertTrue({"Rules_Layers", "Hb", "notes"} <= listed)           # still in the directory index
        notes = [f for _d, name, f in dirs if name == "notes"]
        self.assertEqual(notes, [["house.md"]])

    def test_no_roots_is_the_legacy_walk(self):
        self.assertEqual(self.walk(), self.walk(search_excluded_prefixes=()))
        _d, files = self.walk()
        self.assertIn(f"{PRIVATE}/Hb/notes/house.md", {f.relative_to(self.root).as_posix() for f in files})

    def test_the_corpus_database_cannot_find_private_text(self):
        def fts(prefixes):
            _d, files = self.walk(search_excluded_prefixes=prefixes)
            db = Path(self._tmp.name) / f"corpus{len(prefixes)}.db"
            bi.build_search_db(files, self.root, db, -1, [], build_vectors=False)
            conn = sqlite3.connect(db)
            try:
                hits = {w: conn.execute("SELECT path FROM corpus_fts WHERE corpus_fts MATCH ?", (w,)).fetchall()
                        for w in ("ZEBRAPROBE", "LOREPROBE", "BOUNDARYPROBE")}
                rows = conn.execute("SELECT path, content FROM corpus_fts ORDER BY path").fetchall()
            finally:
                conn.close()
            return hits, rows
        excluded, rows_ex = fts((PRIVATE,))
        included, rows_in = fts(())
        self.assertEqual(excluded["ZEBRAPROBE"], [])
        self.assertEqual(len(included["ZEBRAPROBE"]), 1)                     # the exclusion is what removes it
        for w in ("LOREPROBE", "BOUNDARYPROBE"):
            self.assertEqual(len(excluded[w]), 1, w)
        # Every other indexed row is unchanged (scores may legitimately differ: the population changed).
        self.assertEqual(rows_ex, [r for r in rows_in if not r[0].startswith(PRIVATE + "/")])

    def test_the_builder_wires_the_declared_roots_into_the_corpus_build(self):
        idx = Path(self._tmp.name) / "corpus_index"
        cfg_path = write(Path(self._tmp.name) / "corpus.cfg",
                         f"[paths]\nroot_directory = {self.root}\nindex_directory = {idx}\n\n"
                         f"[search_index]\nGame_Systems/\n\n[file_types]\nmode = whitelist\n*.md\n\n"
                         f"[rules_layers]\nprivate_roots = {PRIVATE}\n")
        argv = ["build_indexes.py", "--cfg", str(cfg_path), "--no-pause", "--no-vectors"]
        with mock.patch.object(sys, "argv", argv), mock.patch.dict("os.environ", {"CORPUS_ROOT": ""}), \
                mock.patch("builtins.print"):
            self.assertEqual(bi.main(), 0)
        conn = sqlite3.connect(idx / bi.DB_FILENAME)
        try:
            find = lambda w: conn.execute("SELECT path FROM corpus_fts WHERE corpus_fts MATCH ?", (w,)).fetchall()
            self.assertEqual(find("ZEBRAPROBE"), [])
            self.assertEqual(len(find("LOREPROBE")), 1)
        finally:
            conn.close()
        self.assertIn("Rules_Layers", (idx / bi.OUTPUT_WITH_FILES).read_text(encoding="utf-8"))


class TestDiscovery(Tmp):
    def test_private_layers_are_discovered_beside_game_systems(self):
        base, hb = make_base(self.root), make_layer(self.root)
        self.assertEqual(si.discover(self.root), [base])                     # no roots: the original discovery
        self.assertEqual(si.discover(self.root, (PRIVATE,)), [base, hb])
        self.assertEqual(si.find_cfg(self.root, "hb", (PRIVATE,)), hb)
        self.assertIsNone(si.find_cfg(self.root, "hb"))

    def test_one_module_id_across_both_trees_is_refused(self):
        make_base(self.root)
        make_layer(self.root, module="basesys", dirname="Basesys", kind="system")
        with self.assertRaisesRegex(si.SystemIndexError, "more than one index.cfg"):
            si.find_cfg(self.root, "basesys", (PRIVATE,))

    def test_prune_keeps_private_layers(self):
        self.build(make_base(self.root))
        self.build(make_layer(self.root))
        self.assertEqual(bi.prune_registry(self.root, self.index, (PRIVATE,)), ([], {}, None))
        self.assertEqual(set(self.registry()["systems"]), {"basesys", "hb"})
        self.assertEqual(bi.prune_registry(self.root, self.index, ()), (["hb"], {}, None))   # undeclared root: gone


# ================================================================ manifests: legacy defaults and the layer fields

class TestManifestFields(Tmp):
    def test_a_legacy_manifest_is_a_legacy_module(self):
        cfg = si.load_system_cfg(make_base(self.root))
        self.assertEqual((cfg.kind, cfg.extends, cfg.effective_kind), ("", "", "system"))
        self.assertFalse(cfg.layered)
        self.assertEqual(cfg.schema_version, 2)
        self.assertEqual(cfg.dependencies(), [])
        self.assertEqual(si.fingerprint(cfg), si.source_fingerprint(cfg))
        self.assertEqual(si.fingerprint(cfg, {"x": "y"}), si.source_fingerprint(cfg))

    def test_an_explicit_standalone_system_stays_legacy(self):
        cfg = si.load_system_cfg(make_base(self.root, kind="system"))
        self.assertEqual(cfg.kind, "system")
        self.assertFalse(cfg.layered)

    def test_layer_fields_are_validated_with_a_fix(self):
        make_base(self.root)
        cases = [
            ({"kind": "plugin", "extends": "basesys"}, "kind 'plugin' is not one of"),
            ({"extends": "basesys"}, "extends is declared but kind is not"),
            ({"kind": "homebrew"}, "needs extends"),
            ({"kind": "homebrew", "extends": "hb"}, "names the layer itself"),
            ({"kind": "homebrew", "extends": "Base-Sys"}, "must be one layer id"),
        ]
        for fields, why in cases:
            with self.subTest(fields=fields):
                shutil.rmtree(self.root / PRIVATE, ignore_errors=True)
                cfg_path = make_layer(self.root, **fields)
                with self.assertRaisesRegex(si.SystemIndexError, why) as e:
                    si.load_system_cfg(cfg_path)
                self.assertIn("hb.md", str(e.exception))

    def test_relations_need_a_kind(self):
        cfg_path = make_layer(self.root, relations=relation(), resolution="defined")
        with self.assertRaisesRegex(si.SystemIndexError, "relations.yaml but its manifest declares no kind"):
            si.load_system_cfg(cfg_path)


# ================================================================ relations.yaml

class TestRelationsParsing(Tmp):
    def parse(self, text):
        p = write(self.root / "Hb" / si.RELATIONS_FILE, text)
        return si.parse_relations(p, "hb")

    def test_a_full_relation_parses(self):
        pin = "a" * 64
        rels, problems = self.parse(relation(pin=pin, status="settled",
                                             extra="\n  decided: 2026-10-18\n  decider: Someone\n  note: why"))
        self.assertEqual(problems, [])
        r = rels[0]
        self.assertEqual(r.entry, si.Address("hb", "doc:notes/house.md", ("Forced March", 2)))
        self.assertEqual(r.target, si.Address("basesys", "doc:rules/core.md", ("Fatigue", 2)))
        self.assertEqual((r.mode, r.status, r.decided, r.decider, r.target_sha256),
                         ("extend", "settled", "2026-10-18", "Someone", pin))
        rec, problems = self.parse("- entry: {key: \"doc:notes/house.md\"}\n  target: {layer: basesys, key: "
                                   "\"rec:items/item/rope\"}\n  mode: add\n  status: derived\n")
        self.assertEqual(problems, [])
        self.assertIsNone(rec[0].target.section)
        self.assertEqual(self.parse("")[0], [])

    def test_every_malformed_relation_names_its_item_and_the_fix(self):
        cases = [
            (relation(extra="\n  colour: red"), "unknown key(s) colour"),
            ("- entry: {key: \"doc:notes/house.md\"}\n  target: {layer: basesys, key: \"doc:rules/core.md\"}\n  status: open\n",
             "missing mode"),
            (relation(mode="replace"), "mode 'replace' is not one of"),
            (relation(status="final"), "status 'final' is not one of"),
            (relation(status="settled"), "a settled relation needs decided"),
            (relation(extra="\n  decided: 18/10/2026"), "decided must be a date"),
            (relation(pin="ABC"), "target_sha256 must be 64"),
            (relation(extra="\n  target_sha256: " + "1" * 64), "target_sha256 must be quoted"),
            (relation(target_key="doc:rules/core.md#fatigue", heading=None), "anchors are not part of an entry key"),
            (relation(target_key="core.md", heading=None), "must be doc:"),
            (relation(target_key="rec:items/item/rope"), "a record key takes no section"),
            (relation(level=0), "level must be an integer from 1 to 6"),
            (relation(level=7), "level must be an integer from 1 to 6"),
            (relation(level="true"), "level must be an integer from 1 to 6"),
            (relation(heading="  "), "heading must be the heading's text"),
            ("- entry: {key: \"doc:notes/house.md\"}\n  target: {layer: hb, key: \"doc:rules/core.md\"}\n  mode: add\n"
             "  status: open\n", "must be in another layer"),
            ("- entry: {layer: hb, key: \"doc:notes/house.md\"}\n  target: {layer: basesys, key: \"doc:rules/core.md\"}\n"
             "  mode: add\n  status: open\n", "takes no layer"),
            (relation() + relation(), "repeats an earlier relation"),
            ("entry: x\n", "must be a YAML list"),
            ("- [unclosed\n", "unreadable YAML"),
        ]
        for text, why in cases:
            with self.subTest(why=why):
                _rels, problems = self.parse(text)
                self.assertTrue(any(why in p for p in problems), problems)
                self.assertTrue(all(p.startswith("Hb/relations.yaml") for p in problems), problems)


# ================================================================ canonical unit hashes

class TestUnitHash(unittest.TestCase):
    def test_the_canonical_bytes_are_exact(self):
        self.assertEqual(si.canonical_unit_bytes("record", '{ "b": [1, 2], "a": "é" }'),
                         b'rules-layer-unit/v1\nrecord\n{"a":"\xc3\xa9","b":[1,2]}')
        self.assertEqual(si.canonical_unit_bytes("document", "\r\n\nLine one  \r\nLine two\t\n\n"),
                         b"rules-layer-unit/v1\ndocument\nLine one\nLine two")
        self.assertEqual(si.canonical_unit_bytes("section", "## The Week — Supply\nBody  \n", "The Week — Supply", 2),
                         b"rules-layer-unit/v1\nsection\n2\nthe week - supply\n## The Week \xe2\x80\x94 Supply\nBody")
        with self.assertRaises(ValueError):
            si.canonical_unit_bytes("table", "x")

    def test_formatting_never_changes_a_hash_and_content_always_does(self):
        h = si.unit_hash
        self.assertEqual(h("record", '{"a":1,"b":[1,2]}'), h("record", '{\n  "b": [1, 2],\n  "a": 1\n}'))
        self.assertNotEqual(h("record", '{"a":1}'), h("record", '{"a":2}'))
        self.assertEqual(h("document", "A\nB\n"), h("document", "\nA  \r\nB\r\n\n"))
        self.assertNotEqual(h("document", "A\nB"), h("document", "A\nC"))
        self.assertNotEqual(h("section", "x", "Fatigue", 2), h("section", "x", "Fatigue", 3))
        self.assertNotEqual(h("section", "x", "Fatigue", 2), h("section", "x", "Healing", 2))
        self.assertEqual(h("document", "A"), h("document", "A"))                                    # repeatable

    def test_kinds_are_domain_separated(self):
        t = '{"a":1}'
        self.assertEqual(len({si.unit_hash("record", t), si.unit_hash("document", t),
                              si.unit_hash("section", t, "", 0)}), 3)

    def test_the_section_split_is_get_sections(self):
        import search_mcp_server as srv
        texts = [CORE_MD, HOUSE_MD, "no headings at all", "## A\nx\n```\n## not a heading\n```\n## B\ny\n",
                 "intro\n## A\n### a1\n## B\n", "# Title\nlead\n## A\n", "lead only\n## A — “q”\n",
                 "## A ##\n~~~\n## fenced\n~~~\n"]
        for t in texts:
            for level in (1, 2, 3):
                with self.subTest(text=t[:20], level=level):
                    self.assertEqual(si.split_sections(t, level, "Lead"), srv._split_sections(t, level, "Lead"))
        for s in ("The Estate’s Week — Supply Cadence", "  ## A:  ", "“Quoted” – x"):
            self.assertEqual(si.norm_heading(s), srv._norm_heading(s))


# ================================================================ the layered build

class TestLayeredBuild(Tmp):
    def setUp(self):
        super().setUp()
        self.base_cfg = make_base(self.root)
        self.base = self.build(self.base_cfg)

    def target_hash(self, heading="Fatigue", key="doc:rules/core.md"):
        conn = sqlite3.connect(f"{self.db('basesys').as_uri()}?mode=ro", uri=True)
        try:
            h, why = si.resolve_unit(conn, si.Address("basesys", key, (heading, 2) if heading else None))
        finally:
            conn.close()
        self.assertIsNone(why)
        return h

    def layer(self, relations, **fields):
        return make_layer(self.root, relations=relations, **fields)

    def test_a_legacy_build_is_unchanged(self):
        entry = self.registry()["systems"]["basesys"]
        self.assertEqual(set(entry), LEGACY_ENTRY_KEYS)
        self.assertEqual(entry["schema_version"], 2)
        self.assertEqual(entry["source_fingerprint"], si.source_fingerprint(si.load_system_cfg(self.base_cfg)))
        tables = {r[0] for r in self.query("basesys", "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertFalse({"layer_info", "relations"} & tables)
        self.assertEqual(self.query("basesys", "SELECT schema_version FROM db_info"), [(2,)])

    def test_a_layered_build_records_its_layer_and_pin_states(self):
        good = self.target_hash()
        rels = (relation(pin=good) + relation(heading="Healing", entry_heading=None)
                + relation(target_key="rec:items/item/rope", heading=None, mode="add", pin="0" * 64,
                           entry_heading=None))
        b = self.build(self.layer(rels))
        entry = self.registry()["systems"]["hb"]
        self.assertEqual(entry["schema_version"], 3)
        self.assertEqual(entry["layer"]["depends_on"], {"basesys": self.base.build_id})
        self.assertEqual((entry["layer"]["kind"], entry["layer"]["extends"], entry["layer"]["relations"]),
                         ("homebrew", "basesys", 3))
        self.assertEqual(self.query("hb", "SELECT schema_version, build_id FROM db_info"), [(3, b.build_id)])
        info = self.query("hb", "SELECT kind, extends, depends_on FROM layer_info")
        self.assertEqual(info, [("homebrew", "basesys", json.dumps({"basesys": self.base.build_id}))])
        rows = self.query("hb", "SELECT item, entry_section, target_key, pin_state, current_sha256 FROM relations "
                                "ORDER BY item")
        self.assertEqual([(r[0], r[3]) for r in rows], [(1, "pinned"), (2, "unpinned"), (3, "changed")])
        self.assertEqual(rows[0][4], good)
        self.assertEqual(json.loads(rows[0][1]), {"heading": "Forced March", "level": 2})
        cfg = si.load_system_cfg(self.root / PRIVATE / "Hb" / "index.cfg")
        self.assertEqual(entry["source_fingerprint"], si.layered_fingerprint(cfg, {"basesys": self.base.build_id}))

    def test_relations_alone_make_a_layer(self):
        b = self.build(self.layer(relation(mode="partition"), kind="system"))      # standalone: no extends
        cfg = si.load_system_cfg(self.root / PRIVATE / "Hb" / "index.cfg")
        self.assertEqual((cfg.extends, cfg.layered, cfg.dependencies()), ("", True, ["basesys"]))
        entry = self.registry()["systems"]["hb"]
        self.assertEqual((entry["schema_version"], entry["layer"]["depends_on"]),
                         (3, {"basesys": self.base.build_id}))
        self.assertEqual(self.query("hb", "SELECT schema_version FROM db_info"), [(3,)])
        self.assertEqual(b.module, "hb")

    def assert_refused(self, cfg_path, why):
        before = self.registry_bytes()
        gens = self.generations()
        with self.assertRaisesRegex(si.SystemIndexError, why):
            self.build(cfg_path)
        self.assertEqual(self.registry_bytes(), before)
        self.assertEqual(self.generations(), gens)
        self.assertFalse(list(self.sdir.glob("*.tmp.db")))

    def test_orphans_are_refused_and_nothing_publishes(self):
        cases = [
            (relation(target_key="doc:missing.md", heading=None), "target is orphaned: no document doc:missing.md"),
            (relation(heading="Sleep"), "target is orphaned: no level-2 section 'Sleep'"),
            (relation(target_key="rec:items/item/none", heading=None), "no record rec:items/item/none"),
            (relation(entry_heading="Nope"), "entry does not resolve in this layer"),
        ]
        for rels, why in cases:
            with self.subTest(why=why):
                shutil.rmtree(self.root / PRIVATE, ignore_errors=True)
                self.assert_refused(self.layer(rels), why)

    def test_an_ambiguous_section_is_refused(self):
        write(self.root / "Game_Systems" / "Basesys" / "rules" / "core.md", CORE_MD + "\n## Fatigue\n\nAgain.\n")
        self.build(self.base_cfg)
        self.assert_refused(self.layer(relation()), "more than one level-2 section 'Fatigue'")

    def test_unbuilt_dependencies_are_refused_with_the_fix(self):
        self.assert_refused(self.layer(None, kind="homebrew", extends="other"),
                            r"'other', which hb depends on, is not built; build it first")
        shutil.rmtree(self.root / PRIVATE)
        rels = relation().replace("layer: basesys", "layer: ghost")
        self.assert_refused(self.layer(rels), "'ghost', which hb depends on, is not built")

    def test_a_dependency_whose_database_disagrees_with_the_registry_is_refused(self):
        reg = self.registry()
        reg["systems"]["basesys"]["build_id"] = "19990101T000000Z-000000"
        si.write_registry(self.sdir, reg)
        self.assert_refused(self.layer(relation()), "the database registered for 'basesys' is missing or does not "
                                                    "match the registry")

    def set_schema(self, registry=None, database=None):
        if database is not None:
            conn = sqlite3.connect(self.db("basesys"))
            try:
                conn.execute("UPDATE db_info SET schema_version = ?", (database,))
                conn.commit()
            finally:
                conn.close()
        if registry is not None:
            reg = self.registry()
            reg["systems"]["basesys"]["schema_version"] = registry
            si.write_registry(self.sdir, reg)

    def test_an_unsupported_dependency_schema_is_refused(self):
        # Codex 940's repro: both the registry and the database claim schema 99, build id and module correct.
        self.set_schema(registry=99, database=99)
        self.assert_refused(self.layer(relation()), "'basesys' is schema 99, which this builder cannot validate")

    def test_a_dependency_schema_disagreement_is_refused(self):
        self.set_schema(registry=3)
        self.assert_refused(self.layer(relation()), "the registry says 'basesys' is schema 3 but its database says 2")

    def test_legacy_and_layered_dependencies_are_both_supported(self):
        self.build(self.layer(relation()))                                   # depends on a schema-2 layer
        self.assertEqual(self.registry()["systems"]["hb"]["schema_version"], 3)
        make_layer(self.root, module="hb2", dirname="Hb2", kind="homebrew", extends="hb")
        self.build(self.root / PRIVATE / "Hb2" / "index.cfg")               # depends on a schema-3 layer
        self.assertEqual(self.registry()["systems"]["hb2"]["layer"]["depends_on"],
                         {"hb": self.registry()["systems"]["hb"]["build_id"]})

    def test_a_dependency_rebuilt_during_the_build_refuses_publication(self):
        cfg_path = self.layer(relation())
        real = bi.build_system_db
        fired = []

        def racing(*a, **k):
            out = real(*a, **k)
            if not fired:                                   # once: the rebuild below comes through here too
                fired.append(True)
                self.build(self.base_cfg)                   # basesys is republished mid-build
            return out
        with mock.patch.object(bi, "build_system_db", racing):
            with self.assertRaisesRegex(si.SystemIndexError, "basesys was rebuilt or removed during this build"):
                self.build(cfg_path)
        self.assertNotIn("hb", self.registry()["systems"])
        self.assertFalse(list(self.sdir.glob("hb.*")) + list(self.sdir.glob(".hb.*")))

    def test_the_layered_fingerprint_covers_every_new_input(self):
        cfg_path = self.layer(relation())
        cfg = si.load_system_cfg(cfg_path)
        deps = {"basesys": self.base.build_id}
        fp = si.layered_fingerprint(cfg, deps)
        self.assertEqual(fp, si.layered_fingerprint(si.load_system_cfg(cfg_path), deps))     # repeatable
        self.assertNotEqual(fp, si.layered_fingerprint(cfg, {"basesys": "another-build"}))
        self.assertNotEqual(fp, si.source_fingerprint(cfg))
        man = cfg_path.parent / "hb.md"
        write(man, man.read_text(encoding="utf-8") + "\nA note.\n")
        self.assertNotEqual(fp, si.layered_fingerprint(si.load_system_cfg(cfg_path), deps))
        write(man, manifest("hb", kind="homebrew", extends="basesys"))
        rel = cfg_path.parent / si.RELATIONS_FILE
        write(rel, relation(mode="add"))
        self.assertNotEqual(fp, si.layered_fingerprint(si.load_system_cfg(cfg_path), deps))

    def test_a_legacy_fingerprint_ignores_the_manifest_as_before(self):
        cfg = si.load_system_cfg(self.base_cfg)
        man = self.base_cfg.parent / "basesys.md"
        write(man, man.read_text(encoding="utf-8") + "\nA note.\n")
        self.assertEqual(si.source_fingerprint(cfg), si.fingerprint(si.load_system_cfg(self.base_cfg)))

    def test_the_relations_report_reads_published_databases(self):
        self.build(self.layer(relation(pin="1" * 64)))
        rows = bi.relations_report(self.root, self.index, "hb", (PRIVATE,))
        self.assertEqual([(s, c) for _r, c, s in rows], [("changed", self.target_hash())])
        with self.assertRaisesRegex(si.SystemIndexError, "declares no relations or extends"):
            bi.relations_report(self.root, self.index, "basesys", (PRIVATE,))
        make_layer(self.root, module="hb2", dirname="Hb2", relations=relation(), kind="homebrew", extends="basesys")
        with self.assertRaisesRegex(si.SystemIndexError, "hb2 is not built"):
            bi.relations_report(self.root, self.index, "hb2", (PRIVATE,))


# ================================================================ containment at the builder's opens (Codex 965)

class Recording:
    """A connection stand-in that records any use of the connection it wraps."""
    def __init__(self, conn):
        self.conn, self.used, self.closed = conn, [], False

    def execute(self, *a, **k):
        self.used.append("execute")
        return self.conn.execute(*a, **k)

    def cursor(self):
        self.used.append("cursor")
        return self.conn.cursor()

    def close(self):
        self.closed = True
        self.conn.close()

    def __getattr__(self, name):
        self.used.append(name)
        return getattr(self.conn, name)


class TestBuilderContainment(Tmp):
    """The builder's three read-only opens of a published generation — the dependency snapshot's db_info read, a
    relation target's database in check_relations, and the module's own database in relations_report — are
    contained at the open itself. The generation is renamed outside the corpus (outside.db) with a file symlink left
    at its path, either right after it is resolved or while it is being opened; each case runs in a fresh fixture."""

    CASES = [  # (label, redirected module, when the redirect is armed, the call, what the refusal says)
        ("build: dependency snapshot", "basesys", "resolve", "build",
         "the database registered for 'basesys' {why}; nothing was validated against it"),
        ("build: relation target", "basesys", "check_relations", "build",
         "the database of target layer 'basesys' {why}; no relation targeting it was checked"),
        ("report: dependency snapshot", "basesys", "resolve", "report",
         "the database registered for 'basesys' {why}; nothing was validated against it"),
        ("report: relation target", "basesys", "check_relations", "report",
         "the database of target layer 'basesys' {why}; no relation targeting it was checked"),
        ("report: the module's own database", "hb", "resolve", "report",
         "hb: its published database {why}; nothing was reported"),
    ]
    ESCAPED = "now resolves outside index/systems (through a link or junction), so it was not opened"

    def fresh(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "corpus"
        self.root.mkdir()
        self.index = self.root / "index"
        self.outside = Path(tmp.name) / "outside.db"
        self.build(make_base(self.root))
        self.hb_cfg = make_layer(self.root, relations=relation())

    def gen(self, module):
        return self.sdir / self.registry()["systems"][module]["db"]

    def redirected(self, module, arm, call, during_open):
        """Run the build or the report with `module`'s generation redirected. during_open=False: the swap comes when
        `arm` fires (resolve_db returning for that module, or check_relations being entered). during_open=True: the
        same event only arms it, and the swap comes inside the next sqlite3.connect of that generation, just before
        the real connect. Returns (the SystemIndexError raised or None, every connect of the generation or
        outside.db after the swap, the Recording of a connection opened during the swap or None)."""
        gen, armed, swapped, opened, rec = self.gen(module), [], [], [], []
        real_connect, real_resolve, real_check = sqlite3.connect, si.resolve_db, bi.check_relations

        def swap():
            gen.rename(self.outside)
            try:
                gen.symlink_to(self.outside)
            except OSError as e:
                self.outside.rename(gen)
                self.skipTest(f"cannot make a file symlink here ({e})")
            swapped.append(1)

        def fire():
            if not armed:
                armed.append(1)
                if not during_open:
                    swap()

        def resolve(sdir, mod, entry):
            got = real_resolve(sdir, mod, entry)
            if arm == "resolve" and mod == module:
                fire()
            return got

        def check(*a, **k):
            if arm == "check_relations":
                fire()
            return real_check(*a, **k)

        def spy(db, *a, **k):
            names = (gen.name in str(db)) or ("outside.db" in str(db))
            if during_open and armed and not swapped and gen.name in str(db):
                swap()
                opened.append(str(db))
                rec.append(Recording(real_connect(db, *a, **k)))
                return rec[-1]
            if swapped and names:
                opened.append(str(db))
            return real_connect(db, *a, **k)

        err = None
        try:
            with mock.patch.object(si, "resolve_db", side_effect=resolve), \
                    mock.patch.object(bi, "check_relations", side_effect=check), \
                    mock.patch.object(sqlite3, "connect", side_effect=spy):
                if call == "build":
                    self.build(self.hb_cfg)
                else:
                    bi.relations_report(self.root, self.index, "hb", (PRIVATE,))
        except si.SystemIndexError as e:
            err = e
        self.assertTrue(swapped, "the redirect never happened")
        return err, opened, (rec[0] if rec else None)

    def run_cases(self, during_open):
        why = si.CHANGED_DURING_OPEN if during_open else self.ESCAPED
        for label, module, arm, call, refusal in self.CASES:
            with self.subTest(case=label):
                self.fresh()
                if call == "report":
                    self.build(self.hb_cfg)
                    rows = bi.relations_report(self.root, self.index, "hb", (PRIVATE,))     # served while contained
                    self.assertEqual([s for _r, _c, s in rows], ["unpinned"])
                before, gens = self.registry_bytes(), self.generations()
                err, opened, rec = self.redirected(module, arm, call, during_open)
                self.assertIsNotNone(err, "not refused")
                self.assertIn(refusal.format(why=why), str(err))
                if during_open:
                    self.assertEqual(len(opened), 1, opened)
                    self.assertEqual((rec.used, rec.closed), ([], True))               # closed unread
                else:
                    self.assertEqual(opened, [])                                       # never opened
                self.assertEqual(self.registry_bytes(), before)                        # nothing published
                self.assertEqual(self.generations(), gens)
                self.assertFalse(list(self.sdir.glob("*.tmp.db")))

    def test_a_redirect_after_resolution_is_refused_before_each_open(self):
        self.run_cases(during_open=False)

    def test_a_redirect_during_the_open_is_closed_unread(self):
        self.run_cases(during_open=True)

    def test_a_contained_build_and_report_open_through_the_check(self):
        self.fresh()
        seen = []
        real = si.open_contained

        def spy(path, sdir, opener):
            seen.append(Path(path).name.split(".")[0])
            return real(path, sdir, opener)
        with mock.patch.object(si, "open_contained", side_effect=spy):
            self.build(self.hb_cfg)
            self.assertEqual(seen, ["basesys", "basesys"])                  # dependency snapshot, relation target
            seen.clear()
            rows = bi.relations_report(self.root, self.index, "hb", (PRIVATE,))
        self.assertEqual(seen, ["basesys", "hb", "basesys"])                # snapshot, own database, target
        self.assertEqual([s for _r, _c, s in rows], ["unpinned"])


class SqlLog:
    """A connection stand-in that logs each statement's first word, and can run a hook just before an ATTACH."""
    def __init__(self, conn, before_attach=None):
        self.conn, self.before_attach, self.log = conn, before_attach, []

    def execute(self, sql, *a):
        verb = sql.split()[0].upper()
        if verb == "ATTACH" and self.before_attach:
            self.before_attach()
        self.log.append(verb)
        return self.conn.execute(sql, *a)

    def commit(self):
        self.conn.commit()


class TestEmbedCacheContainment(unittest.TestCase):
    """Codex 967: the embedding-cache seed's read-only ATTACH of the live generation is contained at the attach — the
    generation must still resolve inside index/systems, its resolved path is attached, and it is checked again before
    anything is queried or copied; a refusal is detached unread. Codex's recipe: a synthetic registered generation with
    embed_cache and embed_cache_info, resolved through resolve_db, then renamed to outside.db with a file symlink left
    at its path, seeded into a new URI-enabled in-memory database (as build_system_db's own connection is)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.sdir = si.systems_dir(Path(self._tmp.name) / "corpus" / "index")
        self.sdir.mkdir(parents=True)
        self.outside = Path(self._tmp.name) / "outside.db"
        name = f"basesys.{si.new_build_id()}.db"
        c = sqlite3.connect(self.sdir / name)
        c.execute("CREATE TABLE embed_cache (hash TEXT PRIMARY KEY, embedding BLOB NOT NULL)")
        c.execute("CREATE TABLE embed_cache_info (model TEXT, dim INTEGER)")
        c.execute("INSERT INTO embed_cache VALUES ('synthetic-cache', x'01020304')")
        c.execute("INSERT INTO embed_cache_info VALUES ('synthetic-model', 4)")
        c.commit()
        c.close()
        self.path = si.resolve_db(self.sdir, "basesys", {"db": name})
        self.conn = sqlite3.connect("file::memory:", uri=True)
        self.addCleanup(self.conn.close)

    def swap(self):
        self.path.rename(self.outside)
        try:
            self.path.symlink_to(self.outside)
        except OSError as e:
            self.outside.rename(self.path)
            self.skipTest(f"cannot make a file symlink here ({e})")

    def copied(self):
        try:
            return self.conn.execute("SELECT hash, hex(embedding) FROM embed_cache").fetchall()
        except sqlite3.Error:
            return []

    def attached(self):
        return [r[1] for r in self.conn.execute("PRAGMA database_list")]

    def test_a_contained_warm_cache_is_reused(self):
        log = SqlLog(self.conn)
        self.assertIsNone(bi._seed_embed_cache(log, self.path, self.sdir))
        self.assertEqual(self.copied(), [("synthetic-cache", "01020304")])
        self.assertEqual(self.conn.execute("SELECT model, dim FROM embed_cache_info").fetchall(),
                         [("synthetic-model", 4)])
        self.assertEqual(self.attached(), ["main"])                                  # detached afterwards
        self.assertEqual(log.log[0], "ATTACH")

    def test_an_unavailable_cache_still_falls_back_quietly(self):
        for live in (None, self.sdir / "basesys.gone.db"):
            with self.subTest(live=live):
                self.assertIsNone(bi._seed_embed_cache(self.conn, live, self.sdir))
                self.assertEqual((self.copied(), self.attached()), ([], ["main"]))
        self.path.write_bytes(b"not a database")                    # attaches, but holds no cache tables
        self.assertIsNone(bi._seed_embed_cache(self.conn, self.path, self.sdir))
        self.assertEqual((self.copied(), self.attached()), ([], ["main"]))

    def test_a_redirect_after_resolution_is_never_attached(self):
        self.swap()
        log = SqlLog(self.conn)
        why = bi._seed_embed_cache(log, self.path, self.sdir)
        self.assertEqual((self.copied(), self.attached()), ([], ["main"]))          # nothing copied from outside
        self.assertEqual(log.log, [])                                                # no ATTACH, no query
        self.assertIn("now resolves outside index/systems (through a link or junction), so it was not opened",
                      why or "")

    def test_a_redirect_during_the_attach_is_detached_unread(self):
        log = SqlLog(self.conn, before_attach=self.swap)
        why = bi._seed_embed_cache(log, self.path, self.sdir)
        self.assertEqual((self.copied(), self.attached()), ([], ["main"]))          # nothing copied from outside
        self.assertEqual(log.log, ["ATTACH", "DETACH"])                              # nothing queried
        self.assertEqual(why, si.CHANGED_DURING_OPEN)

    def test_a_refusal_is_reported_and_the_build_carries_on(self):
        tmp = Path(self._tmp.name) / "build"
        cfg = si.load_system_cfg(make_base(tmp / "corpus"))
        why = "now resolves outside index/systems (through a link or junction), so it was not opened"
        gen = self.sdir / f".basesys.{si.new_build_id()}.tmp.db"
        with mock.patch.object(bi, "_seed_embed_cache", return_value=why) as seed:
            stats, counts = bi.build_system_db(cfg, gen, self.path, si.new_build_id(), "f" * 64, False,
                                               sdir=self.sdir)
        self.assertEqual(seed.call_args.args[2], self.sdir)
        self.assertIn(("<embedding cache>", f"previous embedding cache not reused: the live database {why}; "
                                            f"unchanged documents are embedded again"), stats.errors)
        self.assertFalse(stats.vector_failed)
        self.assertTrue(all(counts.values()))


# ================================================================ dependency order

class TestOrder(Tmp):
    @staticmethod
    def cfg(module, extends="", targets=()):
        rels = [si.Relation(i, si.Address(module, "doc:x.md"), si.Address(t, "doc:y.md"), "add", "open")
                for i, t in enumerate(targets, 1)]
        return si.SystemCfg(module, Path("."), Path("."), "", [], kind="homebrew" if extends else "",
                            extends=extends, relations=rels)

    def test_every_layer_follows_its_dependencies(self):
        cfgs = [self.cfg("zeta", "alpha"), self.cfg("alpha"), self.cfg("mid", "zeta"), self.cfg("rel", "",
                                                                                               ("mid",))]
        self.assertEqual([c.module for c in si.dependency_order(cfgs)], ["alpha", "zeta", "mid", "rel"])
        self.assertEqual(self.cfg("rel", "base", ("x", "base")).dependencies(), ["base", "x"])

    def test_a_cycle_names_every_stuck_layer(self):
        cfgs = [self.cfg("a", "b"), self.cfg("b", "", ("a",)), self.cfg("c", "a"), self.cfg("free")]
        with self.assertRaises(si.DependencyCycle) as e:
            si.dependency_order(cfgs)
        self.assertEqual(e.exception.members, ["a", "b", "c"])

    def test_all_systems_builds_in_order_and_isolates_a_cycle(self):
        make_base(self.root)
        # aa2 sorts and is discovered BEFORE hb, the layer it extends: only dependency order builds it second.
        make_layer(self.root, module="aa2", dirname="Aa2", kind="homebrew", extends="hb")
        make_layer(self.root)
        args = mock.Mock(all_systems=True, system=None, no_vectors=True)
        with mock.patch("builtins.print"):
            self.assertEqual(bi.run_systems(args, self.root, self.index, (PRIVATE,)), 0)
        reg = self.registry()["systems"]
        self.assertEqual(reg["aa2"]["layer"]["depends_on"], {"hb": reg["hb"]["build_id"]})
        make_layer(self.root, module="cy1", dirname="Cy1", kind="homebrew", extends="cy2")
        make_layer(self.root, module="cy2", dirname="Cy2", kind="homebrew", extends="cy1")
        with mock.patch("builtins.print"):
            self.assertEqual(bi.run_systems(args, self.root, self.index, (PRIVATE,)), 1)
        reg = self.registry()["systems"]
        self.assertFalse({"cy1", "cy2"} & set(reg))
        self.assertTrue({"basesys", "hb", "aa2"} <= set(reg))


# ================================================================ the real legacy module, read-only

class TestAllSystemsSafety(Tmp):
    """Audit batch 2 (Working_Documents/Chain_Search_Audit_Fable.md B1, B2, B4, B5): pruning never strands a published
    dependent and never wipes the registry on an empty discovery; --all-systems claims a module exactly as --system
    does; a --system build refuses a dependency cycle through the published builds."""

    ALL = mock.Mock(all_systems=True, system=None, no_vectors=True)
    BACK_TO_HB = ('- entry: {key: "doc:rules/core.md"}\n'
                  '  target: {layer: hb, key: "doc:notes/house.md"}\n'
                  '  mode: add\n  status: open\n')

    def run_all(self):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            code = bi.run_systems(self.ALL, self.root, self.index, (PRIVATE,))
        return code, out.getvalue()

    def test_a_dependency_stays_registered_while_a_published_dependent_needs_it(self):
        base = make_base(self.root)
        self.build(base)
        hb = self.build(make_layer(self.root, relations=relation()))
        self.build(make_base(self.root, dirname="Other", module="other"))
        base.unlink()
        code, out = self.run_all()
        self.assertEqual(code, 1)
        self.assertIn("Still registered: basesys — its index.cfg is gone, but hb depends on it", out)
        reg = self.registry()["systems"]
        self.assertEqual(set(reg), {"basesys", "hb", "other"})
        self.assertEqual(reg["hb"]["layer"]["depends_on"], {"basesys": reg["basesys"]["build_id"]})
        self.assertTrue(self.db("basesys").exists())                     # the build hb names still exists
        self.assertNotEqual(reg["hb"]["build_id"], hb.build_id)          # hb was rebuilt, against that build
        (hb_cfg := self.root / PRIVATE / "Hb" / "index.cfg").unlink()
        self.assertFalse(hb_cfg.exists())
        code, out = self.run_all()                                       # the dependent goes too: both unregister
        self.assertEqual(code, 0)
        self.assertIn("Unregistered (index.cfg removed): basesys, hb", out)
        self.assertEqual(set(self.registry()["systems"]), {"other"})
        self.assertEqual([g for g in self.generations() if not g.startswith("other.")], [])

    def test_held_follows_dependencies_transitively(self):
        base = make_base(self.root)
        self.build(base)
        hb = make_layer(self.root, relations=relation())
        self.build(hb)
        self.build(make_layer(self.root, module="aa2", dirname="Aa2", kind="homebrew", extends="hb"))
        base.unlink()
        hb.unlink()
        gone, held, refused = bi.prune_registry(self.root, self.index, (PRIVATE,))
        self.assertEqual((gone, held, refused), ([], {"basesys": ["hb"], "hb": ["aa2"]}, None))
        self.assertEqual(set(self.registry()["systems"]), {"basesys", "hb", "aa2"})

    def test_an_empty_discovery_unregisters_nothing(self):
        self.build(make_base(self.root))
        self.build(make_layer(self.root, relations=relation()))
        before, gens = self.registry_bytes(), self.generations()
        shutil.move(self.root / "Game_Systems", self.root / "Game_Systems_moved")
        shutil.move(self.root / PRIVATE, self.root / "private_moved")
        code, out = self.run_all()
        self.assertEqual(code, 1)
        self.assertIn("[!] Not pruned: no index.cfg was found under Game_Systems or the private roots, but 2 "
                      "module(s) are registered", out)
        self.assertEqual((self.registry_bytes(), self.generations()), (before, gens))

    def test_all_systems_claims_a_module_exactly_as_system_does(self):
        make_base(self.root, dirname="Foo", module="bar")                # Foo/ declares bar
        make_base(self.root, dirname="Bar", module="baz")                # Bar/ (a folder named bar) declares baz
        code, out = self.run_all()
        self.assertEqual(code, 1)
        self.assertIn("nothing published for 'bar': module 'bar' is declared by more than one index.cfg", out)
        self.assertEqual(set(self.registry()["systems"]), {"baz"})
        known, ambiguous = si.known_modules(self.root, (PRIVATE,))
        self.assertEqual((set(known), ambiguous), ({"baz"}, {"bar"}))
        one = mock.Mock(all_systems=False, system="bar", no_vectors=True)
        with mock.patch("builtins.print"):
            self.assertEqual(bi.run_systems(one, self.root, self.index, (PRIVATE,)), 1)

    def test_system_refuses_a_cycle_through_the_published_builds(self):
        base = make_base(self.root)
        self.build(base)
        self.build(make_layer(self.root, relations=relation()))          # hb extends basesys, as published
        write(base.parent / "basesys.md", manifest("basesys", kind="system"))
        write(base.parent / si.RELATIONS_FILE, self.BACK_TO_HB)          # basesys now relates back to hb
        before, gens = self.registry_bytes(), self.generations()
        with self.assertRaisesRegex(si.SystemIndexError, "dependency cycle through the published builds: "
                                                         "basesys -> hb -> basesys"):
            self.build(base)
        self.assertEqual((self.registry_bytes(), self.generations()), (before, gens))
        (base.parent / si.RELATIONS_FILE).unlink()                       # without the relation it builds
        self.assertEqual(self.build(base).module, "basesys")


def link_dir(case: unittest.TestCase, link: Path, target: Path) -> None:
    """A directory junction (Windows) or symlink at `link` leading to `target`; skips the test if neither can be made."""
    link.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    try:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    except (ImportError, AttributeError, OSError):
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as e:
            case.skipTest(f"cannot make a directory link here ({e})")
    if link.resolve() != target.resolve():
        case.skipTest("the directory link does not resolve to its target here")


class TestLockAndTempHygiene(Tmp):
    """Audit batch 4 (Working_Documents/Chain_Search_Audit_Fable.md B3, B6, B7): a build killed inside the lock does
    not block the next one for minutes, a lock is broken without removing one taken since, release removes only our
    own lock, a Windows sharing violation is retried briefly, and a killed build's temp files are swept."""

    def setUp(self):
        super().setUp()
        self.sdir.mkdir(parents=True)
        self.lock = self.sdir / si.LOCK

    def short(self, timeout=0.6):
        p = mock.patch.object(si, "LOCK_TIMEOUT_S", timeout)
        p.start()
        self.addCleanup(p.stop)

    def take(self):
        t0 = time.monotonic()
        with si.registry_lock(self.sdir):
            held = self.lock.read_text(encoding="utf-8")
        return time.monotonic() - t0, held

    def dead_pid(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        return p.pid

    def live_pid(self):
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(lambda: (p.kill(), p.wait()))
        return p.pid

    def test_the_lock_names_its_owner(self):
        with si.registry_lock(self.sdir):
            token, pid, host, _stamp = self.lock.read_text(encoding="utf-8").split()
        self.assertEqual((len(token), int(pid), host), (16, os.getpid(), socket.gethostname()))
        self.assertFalse(self.lock.exists())

    def test_a_build_killed_inside_the_lock_does_not_block_the_next(self):
        self.short(5)
        code = (f"import os, sys; sys.path.insert(0, {str(HERE)!r}); import system_index as si; "
                f"from pathlib import Path; held = si.registry_lock(Path({str(self.sdir)!r})); held.__enter__(); "
                f"os._exit(9)")                                          # killed inside the lock: no release
        self.assertEqual(subprocess.run([sys.executable, "-c", code]).returncode, 9)
        self.assertTrue(self.lock.exists())                              # left behind, fresh
        took, _ = self.take()
        self.assertLess(took, 2)                                         # not LOCK_STALE_S

    def test_a_dead_owner_on_this_host_is_broken_at_once(self):
        self.short(5)
        write(self.lock, f"0123456789abcdef {self.dead_pid()} {socket.gethostname()} {time.time():.0f}\n")
        took, held = self.take()
        self.assertLess(took, 2)
        self.assertIn(f" {os.getpid()} ", held)

    def test_a_live_owner_another_host_or_the_old_format_waits(self):
        self.short()
        for text in (f"0123456789abcdef {self.live_pid()} {socket.gethostname()} 0\n",
                     f"0123456789abcdef {self.dead_pid()} another-host 0\n",
                     f"0123456789abcdef {os.getpid()} {socket.gethostname()} 0\n",
                     f"{self.dead_pid()} {time.time():.0f}\n"):
            with self.subTest(text=text):
                write(self.lock, text)
                with self.assertRaisesRegex(si.SystemIndexError, "timed out waiting"):
                    self.take()
                self.assertEqual(self.lock.read_text(encoding="utf-8"), text)

    def test_a_stale_lock_is_broken_once_old_enough(self):
        self.short(5)
        write(self.lock, "0123456789abcdef 1 another-host 0\n")
        old = time.time() - si.LOCK_STALE_S - 5
        os.utime(self.lock, (old, old))
        took, held = self.take()
        self.assertLess(took, 2)
        self.assertNotIn("another-host", held)
        self.assertEqual(sorted(p.name for p in self.sdir.iterdir()), [])  # nothing left aside

    def test_the_stale_threshold_lets_one_waiter_recover(self):
        self.assertLess(si.LOCK_STALE_S, si.LOCK_TIMEOUT_S)

    def test_breaking_never_removes_a_lock_taken_since(self):
        write(self.lock, "fresh lock\n")
        si._break_lock(self.lock, "the stale lock this waiter judged\n")
        self.assertEqual(self.lock.read_text(encoding="utf-8"), "fresh lock\n")
        si._break_lock(self.lock, "fresh lock\n")
        self.assertFalse(self.lock.exists())
        self.assertEqual(list(self.sdir.iterdir()), [])                  # the renamed-aside copy is gone too

    def test_release_removes_only_our_own_lock(self):
        with si.registry_lock(self.sdir):
            write(self.lock, "a successor's lock\n")                     # ours was broken, another took it
        self.assertEqual(self.lock.read_text(encoding="utf-8"), "a successor's lock\n")

    def test_a_sharing_violation_on_the_registry_replace_is_retried(self):
        real, calls = os.replace, []

        def flaky(src, dst):
            calls.append(dst)
            if len(calls) < 3:
                raise PermissionError(5, "Access is denied")
            return real(src, dst)
        with mock.patch.object(si.os, "replace", side_effect=flaky):
            si.write_registry(self.sdir, {"schema_version": 2, "systems": {}})
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.registry(), {"schema_version": 2, "systems": {}})

    def test_a_lasting_sharing_violation_fails_fast_and_cleanly(self):
        si.write_registry(self.sdir, {"schema_version": 2, "systems": {}})
        before = self.registry_bytes()
        with mock.patch.object(si, "SHARING_RETRY_S", 0.2), \
                mock.patch.object(si.os, "replace", side_effect=PermissionError(5, "Access is denied")):
            t0 = time.monotonic()
            with self.assertRaises(PermissionError):
                si.write_registry(self.sdir, {"schema_version": 2, "systems": {"x": {}}})
        self.assertLess(time.monotonic() - t0, 2)
        self.assertEqual(self.registry_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.sdir.iterdir()), [si.REGISTRY])   # no temp file left

    def test_a_sharing_violation_on_the_lock_create_is_retried(self):
        real, calls = os.open, []

        def flaky(path, *a, **kw):
            if str(path).endswith(si.LOCK):
                calls.append(path)
                if len(calls) < 3:
                    raise PermissionError(5, "Access is denied")
            return real(path, *a, **kw)
        with mock.patch.object(si.os, "open", side_effect=flaky):
            self.take()
        self.assertEqual(len(calls), 3)

    def test_a_lasting_sharing_violation_on_the_lock_fails_fast(self):
        self.short(30)
        with mock.patch.object(si, "SHARING_RETRY_S", 0.2), \
                mock.patch.object(si.os, "open", side_effect=PermissionError(5, "Access is denied")):
            t0 = time.monotonic()
            with self.assertRaises(PermissionError):
                self.take()
        self.assertLess(time.monotonic() - t0, 3)

    def test_pid_liveness(self):
        self.assertIs(si._pid_alive(self.dead_pid()), False)
        self.assertIs(si._pid_alive(self.live_pid()), True)
        self.assertIs(si._pid_alive(os.getpid()), True)
        exited = subprocess.Popen([sys.executable, "-c", "pass"])
        exited.wait()                       # exited, but its handle still held (Windows: OpenProcess succeeds)
        self.assertIs(si._pid_alive(exited.pid), False)

    def test_a_killed_builds_temp_files_are_swept_once_old(self):
        old = time.time() - si.TEMP_STALE_S - 60
        names = [".basesys.20200101T000000Z-abcdef.tmp.db", ".basesys.20200101T000000Z-abcdef.tmp.db-journal",
                 ".registry.json.4242.tmp", "notes.db", ".other.tmp", "readme.txt"]
        for n in names:
            write(self.sdir / n, "x")
            os.utime(self.sdir / n, (old, old))
        fresh = write(self.sdir / f".basesys.{si.new_build_id()}.tmp.db", "a build still running")
        built = self.build(make_base(self.root))
        self.assertEqual(sorted(built.collected), sorted(names[:3]))
        left = {p.name for p in self.sdir.iterdir()}
        self.assertTrue({"notes.db", ".other.tmp", "readme.txt", fresh.name} <= left)
        self.assertFalse(set(names[:3]) & left)


class TestLoadedParent(Tmp):
    """Audit B8, ruled 2026-11-15: a layer may extend a module loaded by declaration ([rules_layers] not_searched),
    which has no index.cfg and can never be built; a relation into one still refuses."""

    INTO_BASELINE = ('- entry: {key: "doc:notes/house.md"}\n'
                     '  target: {layer: baseline, key: "doc:rules/core.md"}\n'
                     '  mode: add\n  status: open\n')

    def setUp(self):
        super().setUp()
        write(self.root / "Game_Systems" / "Baseline" / "baseline.md", manifest("baseline", resolution="defined"))

    def test_an_extends_parent_loaded_by_declaration(self):
        cfg = make_layer(self.root, kind="homebrew", extends="baseline")
        with self.assertRaisesRegex(si.SystemIndexError, r"'baseline', which hb depends on, is not built"):
            self.build(cfg)                                              # not declared: as before
        b = bi.build_and_publish(self.root, self.index, cfg, build_vectors=False, not_searched=("baseline",))
        entry = self.registry()["systems"]["hb"]
        self.assertEqual((b.module, entry["layer"]["extends"], entry["layer"]["depends_on"]), ("hb", "baseline", {}))
        self.assertNotIn("baseline", self.registry()["systems"])

    def test_through_the_builder_entry_points(self):
        make_layer(self.root, kind="homebrew", extends="baseline")
        one = mock.Mock(all_systems=False, system="hb", no_vectors=True)
        with mock.patch("builtins.print"):
            self.assertEqual(bi.run_systems(one, self.root, self.index, (PRIVATE,), ("baseline",)), 0)
        cfg = write(Path(self._tmp.name) / "indexer.cfg",
                    f"[paths]\nroot_directory = {self.root}\nindex_directory = /index/\n\n"
                    f"[rules_layers]\nprivate_roots = {PRIVATE}\nnot_searched = baseline\n")
        (self.sdir / si.REGISTRY).unlink()                               # start again, through main()
        argv = ["build_indexes.py", "--cfg", str(cfg), "--system", "hb", "--no-vectors", "--no-pause"]
        with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, {"CORPUS_ROOT": ""}), \
                mock.patch("builtins.print"):
            self.assertEqual(bi.main(), 0)
        self.assertEqual(self.registry()["systems"]["hb"]["layer"]["depends_on"], {})

    def test_a_relation_into_a_loaded_module_refuses(self):
        cfg = make_layer(self.root, relations=self.INTO_BASELINE, kind="homebrew", extends="baseline")
        with self.assertRaisesRegex(si.SystemIndexError, "hb declares relations into 'baseline', which indexer.cfg "
                                                         r"\[rules_layers\] declares not_searched"):
            bi.build_and_publish(self.root, self.index, cfg, build_vectors=False, not_searched=("baseline",))
        self.assertEqual(self.registry_bytes(), b"")

    def test_a_built_dependency_is_still_validated_when_also_declared(self):
        self.build(make_base(self.root))
        b = bi.build_and_publish(self.root, self.index, make_layer(self.root, relations=relation()),
                                 build_vectors=False, not_searched=("basesys",))
        self.assertEqual(set(self.registry()["systems"]["hb"]["layer"]["depends_on"]), {"basesys"})
        self.assertEqual(b.module, "hb")


class TestSystemsDirAnchor(Tmp):
    """Audit N1: containment is anchored to the corpus, not to wherever index/systems resolves."""

    def outside(self):
        return Path(self._tmp.name) / "outside_systems"

    def redirect(self):
        """index/systems moved outside the corpus, with a junction left in its place."""
        shutil.move(str(self.sdir), str(self.outside()))
        link_dir(self, self.sdir, self.outside())

    def test_a_systems_dir_leading_out_refuses_build_report_and_prune(self):
        base = make_base(self.root)
        self.build(base)
        self.build(make_layer(self.root, relations=relation()))
        self.redirect()
        stray = write(self.outside() / "basesys.20200101T000000Z-abcdef.db", "an unreferenced generation")
        before = sorted(p.name for p in self.outside().iterdir())
        with self.assertRaisesRegex(si.SystemIndexError, "resolves outside the corpus .through a link or junction., "
                                                         "so no module database under it is trusted"), \
                mock.patch.object(bi, "_dependency_snapshot", side_effect=bi._dependency_snapshot) as snap, \
                mock.patch.object(bi, "build_system_db", side_effect=bi.build_system_db) as built:
            self.build(make_layer(self.root, relations=relation()))
        self.assertEqual((snap.call_count, built.call_count), (0, 0))   # refused before reading or building anything
        with self.assertRaisesRegex(si.SystemIndexError, "resolves outside the corpus"):
            self.build(base)
        with self.assertRaisesRegex(si.SystemIndexError, "resolves outside the corpus"):
            bi.relations_report(self.root, self.index, "hb", (PRIVATE,))
        base.unlink()
        gone, held, refused = bi.prune_registry(self.root, self.index, (PRIVATE,))
        self.assertEqual((gone, held), ([], {}))
        self.assertIn("resolves outside the corpus", refused)
        self.assertEqual(sorted(p.name for p in self.outside().iterdir()), before)   # nothing collected out there
        self.assertTrue(stray.exists())

    def test_an_index_directory_configured_outside_the_corpus_is_the_operators_choice(self):
        index = Path(self._tmp.name) / "elsewhere" / "index"
        b = bi.build_and_publish(self.root, index, make_base(self.root), build_vectors=False)
        self.assertEqual(si.read_registry(si.systems_dir(index), self.root)["systems"]["basesys"]["build_id"],
                         b.build_id)

    def test_a_registry_file_leading_out_is_not_read(self):
        self.build(make_base(self.root))
        out = self.outside() / si.REGISTRY
        out.parent.mkdir(parents=True)
        shutil.move(str(self.sdir / si.REGISTRY), str(out))
        try:
            (self.sdir / si.REGISTRY).symlink_to(out)
        except OSError as e:
            self.skipTest(f"cannot make a file symlink here ({e})")
        with self.assertRaisesRegex(si.SystemIndexError, "resolves outside systems/ .through a link., so it is not "
                                                         "read"):
            si.read_registry(self.sdir)


class TestRealLegacyModule(unittest.TestCase):
    """The real Eclipse Phase module validates unchanged as a legacy module, and its live published fingerprint
    still matches: the new code does not report it stale. Read-only; skipped where the corpus is absent."""

    def setUp(self):
        if not (REAL_EP_CFG.exists() and REAL_REGISTRY.exists()):
            self.skipTest("the real corpus or its registry is not present")

    def test_eclipse_phase_is_legacy_and_current(self):
        before = hashlib.sha256(REAL_REGISTRY.read_bytes()).hexdigest()
        cfg = si.load_system_cfg(REAL_EP_CFG)
        self.assertEqual((cfg.kind, cfg.extends, cfg.layered, cfg.schema_version), ("", "", False, 2))
        self.assertIsNone(cfg.relations_path)
        entry = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))["systems"][cfg.module]
        self.assertEqual(entry["schema_version"], 2)
        self.assertEqual(si.fingerprint(cfg), entry["source_fingerprint"])
        self.assertEqual(hashlib.sha256(REAL_REGISTRY.read_bytes()).hexdigest(), before)


def main():
    ap = argparse.ArgumentParser(description="Self-test for rules layers (chain-aware search stage 1).")
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

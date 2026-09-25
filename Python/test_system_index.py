#!/usr/bin/env python3
"""
test_system_index.py — Self-test for per-module (game-system) search databases.

Covers the builder's system mode (build_indexes.py --system / --all-systems): its strict index.cfg, the dataset
record contract and searchable projection, versioned publication through registry.json, the search server's
`system` parameter, representation filter and exact record fetch (search_mcp_server.py), and a regression gate
proving the corpus search output is unchanged by the new schema.

Everything runs against copies: the code under test is copied from this directory into a temp directory and run
from there, so no build here can touch the live index/ or append to the live Python/build_history.jsonl.
Fixtures are two synthetic modules in a temp corpus root. Nothing is written to the real corpus.

THE DESIGN THESE TESTS PIN (Codex 396, 399)
  - A module database is built in a temp file garbage collection can never match (.<module>.<build>.tmp.db),
    its sources are re-fingerprinted, and only then, under the registry lock, is it renamed to its immutable
    generation name (index/systems/<module>.<build_id>.db) and published by replacing registry.json, the single
    atomic pointer. A failure before the swap leaves the registry byte-identical and removes both files; after
    the swap nothing removes the generation, even a KeyboardInterrupt landing just after it (cleanup asks the
    registry, not a flag); readers finish on the old one; collection is best-effort.
  - A model that cannot run publishes the full-text database without vectors and reports it. Two index.cfg files
    claiming one module are refused. The server never follows a registry cfg path, and checks the database's
    module and schema as well as its build id.
  - A record's dataset is DECLARED: every record carries `dataset`, a file holds one dataset, and no two files
    declare the same one. (Not the file stem: the first real module names co-morphs in co_morphs.jsonl.) Record
    ids are unique across the whole module.
  - A dataset record must have `id` and `name`; `kind`, `source` (with `file` and `anchors`) are optional. Its raw
    JSON is kept whole in payload, its source object whole in source_json, and its search text is a deterministic,
    field-labelled projection of every key except the ones the module declares in exclude_keys.
  - Dataset rows are FTS-only: no embeddings. A vector search restricted to datasets says so explicitly; hybrid
    returns the lexical lane.

WHAT IT CHECKS
  Build        every representation present; unique opaque entry keys; representation and authority on every
               row; payload and source round-trip; db_info agrees with the registry; the generation file is the
               one the registry names; the source fingerprint ignores mtimes and follows content.
  Projection   a value found only in a nested field map, and one only in a nested list, are searchable; a token
               only in an excluded provenance key is not.
  Strict cfg   one planted flaw per copy — unknown key, missing key, nonexistent path, a path leaving the module,
               a symlink escaping it (where the OS allows one), overlap in both directions, an unknown
               representation, a module id not matching the manifest, an output key, a malformed line, an include
               matching no file — plus the record contract: a record with no id, and a duplicate id.
  Row refs     a source-less record resolves one hop to the table owning its lines; a directly sourced record
               keeps its own source even when it carries a same-named field (a dangling one included); every
               malformed, dangling, indirect or out-of-span reference, a second or missing reference field, and
               a declared field nothing uses fail the build; the record shows every table, grouped with rows
               compacted, a hit shows the first and a "+N more" count; nothing is stored as a direct source_path.
  Publication  a failed build leaves the registry byte-identical and no unpublished generation; a registry that
               cannot be replaced fails cleanly; a reader already open keeps querying the old generation after a
               new one is published; two modules built concurrently both land in the registry; a module with a
               valid generation on disk but no registry entry is neither served nor listed, and its generation
               is collected later; a module whose config is removed drops out on --all-systems.
  Vectors      documents are embedded and dataset rows are not; a second build reuses every embedding; a vector
               search on datasets reports that nothing is vector-eligible; hybrid on datasets returns lexical hits.
  Server       hits carry module, representation, authority and entry key; representation_filter with lists,
               spaces and duplicates, and errors for empty, invalid or corpus use; get_section serves documents
               and redirects dataset files; get_system_record by exactly one selector, refusing both, partial,
               wrong-system and document keys; an unknown or unsafe system name, an orphan, a registry path that
               escapes index/systems and a build-id mismatch are all refused; index_status reports source
               freshness by recomputing the fingerprint, not by trusting the build id.
  Corpus gate  the corpus source (Markdown and text only) is snapshotted once into temp, a known gate document is
               added, and both the builder and server pinned at BASE_COMMIT and the working tree's are run on
               that same snapshot. Fixed queries, and two section reads of the gate document, must produce
               byte-identical output, and most queries must return hits.

Usage:
    python test_system_index.py [--no-pause] [--skip-corpus-gate]

Command line arguments:
    --no-pause          Skip end-of-run pause (rebuild/read-only scripts only)
    --skip-corpus-gate  Skip the corpus regression gate (it builds the snapshotted corpus twice)
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
# The last commit before the per-module search change. The corpus gate runs the builder and server from here.
BASE_COMMIT = "7bd0891"
CODE_FILES = ["build_indexes.py", "search_mcp_server.py", "cfg_loader.py", "embedding.py", "indexer.cfg",
              "system_index.py"]
MODULE, OTHER = "testsys", "othersys"
GENERATION = re.compile(r"^(?P<module>[a-z0-9_]+)\.(?P<build>[A-Za-z0-9_-]+)\.db$")


def manifest(module):
    return f"""---
name: {module}
type: system-module
module: {module}
---

# {module}

## Manifest

```yaml
module: {module}
edition: 1
```
"""


VERBATIM = """---
name: Rules
type: rules-source
---

# Rules

## Resolution

Roll percentile dice against a target number; equal or under succeeds. The grapnel rule applies.

## Harm

Damage accumulates against Durability.
"""
COMPACT = """---
name: Rules — compact
type: rules-compact
---

# Rules — compact

## Resolution

Roll d100 under the target; the grapnel rule, condensed.
"""
RECORDS = [
    # Alpha has prose AND fields; "orichalcite" (a nested map) and "zephyrine" (a nested list) exist only in its
    # fields, and "provtokenquux" only in an excluded provenance key.
    {"id": "thing/alpha", "dataset": "things", "layer": "dataset", "kind": "item", "name": "Alpha",
     "source": {"file": "01-rules.md", "anchors": {"start": "resolution", "stat_block": "resolution-1"}},
     "preambles": ["preamble/provtokenquux"],
     "fields": {"cost": 3, "stats": {"material": "orichalcite", "tags": ["zephyrine", "hooked"]}},
     "text": "Alpha is a grapnel launcher."},
    {"id": "thing/beta", "dataset": "things", "layer": "dataset", "kind": "item", "name": "Beta",
     "source": {"file": "01-rules.md", "anchors": {"start": "harm"}}, "fields": {"cost": 5}},
]
OTHER_RECORDS = [{"id": "gizmo/one", "dataset": "gizmos", "kind": "item", "name": "Gizmo"}]
EXCLUDE = "layer, source, source_notes, context, index_rows, preambles"
# Row references: a record read from a table row carries no source of its own, only references to the index record
# that owns the table's lines. The field names are overloaded, as in the first real module: index records carry
# their own table `rows` (no index key), and a directly sourced record may carry `index_rows` too. Neither is a
# reference, because a record with a direct source is never read for row references.
ROW_REFS = "index_rows, contents, rows"
TABLE_RECORDS = [
    {"id": "index/table-one", "dataset": "tables", "kind": "index", "name": "Table One",
     "source": {"file": "01-rules.md", "anchors": {"section": "resolution"}, "line_start": 5, "line_end": 9},
     "rows": [{"cells": {"name": "Gamma"}}]},
    {"id": "index/table-two", "dataset": "tables", "kind": "index", "name": "Table Two",
     "source": {"file": "sub/02-more.md", "anchors": {"section": "harm", "table": "harm-1"},
                "line_start": 20, "line_end": 24}},
    {"id": "item/delta", "dataset": "tables", "kind": "item", "name": "Delta",
     "source": {"file": "01-rules.md", "anchors": {"start": "harm"}},
     "index_rows": [{"index": "index/nowhere", "line": 99}]},
    {"id": "item/gamma", "dataset": "tables", "kind": "item", "name": "Gamma", "fields": {"cost": 2},
     "index_rows": [{"index": "index/table-one", "line": 7, "cells": {"name": "Gamma"}}]},
    {"id": "pack/kit", "dataset": "tables", "kind": "pack", "name": "Kit",
     "contents": [{"index": "index/table-one", "line": 6, "ref": "item/gamma"}, {"index": "index/table-one", "line": 7},
                  {"index": "index/table-one", "line": 9}, {"index": "index/table-two", "line": 21}]},
    {"id": "roll-table/omen", "dataset": "tables", "kind": "roll-table", "name": "Omen",
     "rows": [{"index": "index/table-two", "line": 22, "column": 1, "low": 1, "high": 1}]},
]


def index_cfg(module, row_refs=None):
    refs = f"row_refs = {row_refs}\n" if row_refs else ""
    return f"""[system]
module = {module}

[representation verbatim]
path = source/srd
authority = source
include = *.md

[representation compact]
path = rules/compact
authority = derived
include = *.md

[representation dataset]
path = data
authority = derived
include = *.jsonl
exclude_keys = {EXCLUDE}
{refs}"""


INDEX_CFG = index_cfg(MODULE, ROW_REFS)
LORE = """---
name: Lore Note
type: note
keywords: [marsh, lantern]
description: A fixture lore document.
---

# Lore Note

## The Marsh

A lantern burns in the marsh.
"""
GATE_DOC = """---
name: Gate Document
type: note
keywords: [gatefixture]
description: A known document for the corpus regression gate's section reads.
---

# Gate Document

## First Part

Opening text for the gate.

### First Detail

A detail under the first part.

## Second Part

Closing text for the gate.
"""
GATE_PATH = "Gate_Fixture/Gate_Document.md"

# (label, old text, new text, text the build must report). Each is applied to a fresh copy of INDEX_CFG.
CFG_PLANTS = [
    ("an unknown key", "include = *.jsonl\n", "include = *.jsonl\ncolour = red\n", "unknown key 'colour'"),
    ("a missing required key", "[representation compact]\npath = rules/compact\n", "[representation compact]\n",
     "missing required key 'path'"),
    ("a path that does not exist", "path = rules/compact", "path = rules/nowhere", "does not exist"),
    ("a path that leaves the module", "path = rules/compact", "path = ../outside", "outside the module"),
    ("one representation nested inside another", "path = rules/compact", "path = source/srd/sub", "overlap"),
    ("one representation containing another", "path = rules/compact", "path = source", "overlap"),
    ("an unknown representation", "[representation compact]", "[representation summary]",
     "unknown representation 'summary'"),
    ("a module id that does not match the manifest", f"module = {MODULE}", "module = nomatch", "does not match"),
    ("an output key", f"module = {MODULE}\n", f"module = {MODULE}\noutput = /tmp/x.db\n", "unknown key 'output'"),
    ("a malformed line", "include = *.jsonl\n", "include = *.jsonl\nthis is not a setting\n", "malformed"),
    ("an include that matches no file", "include = *.jsonl", "include = *.xyz", "matches no file"),
    ("a row_refs field no source-less record uses", f"row_refs = {ROW_REFS}", f"row_refs = {ROW_REFS}, parts",
     "'parts'"),
    ("a row_refs field listed twice", f"row_refs = {ROW_REFS}", f"row_refs = index_rows, {ROW_REFS}", "twice"),
    ("an empty row_refs", f"row_refs = {ROW_REFS}", "row_refs = ", "row_refs"),
    ("row_refs outside the dataset representation", "include = *.md\n\n[representation compact]",
     f"include = *.md\nrow_refs = {ROW_REFS}\n\n[representation compact]", "unknown key 'row_refs'"),
]

RESULTS = []


def check(passed, what, detail=""):
    RESULTS.append(bool(passed))
    print(f"  {'PASS' if passed else 'FAIL'}  {what}")
    if not passed and detail:
        print("\n".join("        " + l for l in str(detail).strip().splitlines()[:12]))


def section(title):
    print(f"\n{title}")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def copy_code(dest, source="working"):
    """Copy the code under test into dest: the working tree, or a git revision of it."""
    dest.mkdir(parents=True, exist_ok=True)
    for name in CODE_FILES:
        if source == "working":
            shutil.copy2(HERE / name, dest / name)
        else:
            r = subprocess.run(["git", "-C", str(REPO), "show", f"{source}:Python/{name}"], capture_output=True)
            if r.returncode != 0:
                continue          # a file the change introduced does not exist at the base revision
            (dest / name).write_bytes(r.stdout)
    return dest


def make_module(root, dirname, module, records, full=True, row_refs=None):
    mod = root / "Game_Systems" / dirname
    write(mod / f"{module}.md", manifest(module))
    write(mod / "source" / "srd" / "01-rules.md", VERBATIM)
    write(mod / "source" / "srd" / "sub" / "02-more.md", VERBATIM.replace("# Rules", "# More rules"))
    if full:
        write(mod / "rules" / "compact" / "01-rules.md", COMPACT)
        write(mod / "index.cfg", index_cfg(module, row_refs))
    else:
        write(mod / "index.cfg", index_cfg(module, row_refs).replace(
            "[representation compact]\npath = rules/compact\nauthority = derived\ninclude = *.md\n\n", ""))
    by_dataset = {}
    for r in records:
        by_dataset.setdefault(r["dataset"], []).append(r)
    for dataset, recs in by_dataset.items():
        write(mod / "data" / f"{dataset}.jsonl", "".join(json.dumps(r) + "\n" for r in recs))
    return mod


def make_fixture(root):
    write(root / "World" / "Lore_Note.md", LORE)
    # Othersys declares no row_refs, so its source-less record is simply unsourced, as before row references.
    make_module(root, "Othersys", OTHER, OTHER_RECORDS, full=False)
    return make_module(root, "Testsys", MODULE, RECORDS + TABLE_RECORDS, row_refs=ROW_REFS)


# Embedding environments. The real model cache beside this script makes the positive vector checks independent
# of the network (a temp copy of the code would otherwise start with an empty cache and try to download); a cache
# path that is a FILE makes the model fail to load, reliably and offline, with no test hook in production code.
REAL_EMBED = {"CORPUS_EMBED_CACHE": str(HERE / ".fastembed_cache")}
BROKEN_EMBED = {}          # filled in main(): CORPUS_EMBED_CACHE pointing at a file


def run(code, args, root, timeout=600, env=None):
    env = {**os.environ, "CORPUS_ROOT": str(root), "PYTHONIOENCODING": "utf-8", **REAL_EMBED, **(env or {})}
    r = subprocess.run([sys.executable, str(code / "build_indexes.py"), *args, "--no-pause"],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def run_py(code, root, body, env=None):
    """Run Python in a fresh process with the code under test importable and CORPUS_ROOT set, for the checks that
    need to reach inside a build — a fault injected at one exact point, rather than a race left to timing. The
    script prints RESULT <json> on its last line."""
    script = f"import json, sys\nsys.path.insert(0, {str(code)!r})\n" + body
    env = {**os.environ, "CORPUS_ROOT": str(root), "PYTHONIOENCODING": "utf-8", **REAL_EMBED, **(env or {})}
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, encoding="utf-8", env=env,
                       timeout=600)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    try:
        return json.loads(last[len("RESULT "):]) if last.startswith("RESULT ") else None, r.stdout + r.stderr
    except ValueError:
        return None, r.stdout + r.stderr


BUILD_PRELUDE = """
from pathlib import Path
import os
import build_indexes as b
import system_index as si
root = Path(os.environ["CORPUS_ROOT"])
index_dir = root / "index"
cfg_of = lambda name: next(p for p in si.discover(root) if p.parent.name.lower() == name)
"""


def start(code, args, root):
    env = {**os.environ, "CORPUS_ROOT": str(root), "PYTHONIOENCODING": "utf-8", **REAL_EMBED}
    return subprocess.Popen([sys.executable, str(code / "build_indexes.py"), *args, "--no-pause"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", env=env)


def server_calls(code, root, calls, env=None):
    """Run server tool functions in a fresh process with CORPUS_ROOT=root. calls: [(fn name, kwargs)]."""
    script = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(code)!r})\n"
        "import search_mcp_server as s\n"
        "out = []\n"
        f"for name, kw in json.loads({json.dumps(json.dumps(calls))}):\n"
        "    fn = getattr(s, name, None)\n"
        "    try:\n"
        "        out.append(fn(**kw) if fn else f'<<no function {name}>>')\n"
        "    except Exception as e:\n"
        "        out.append(f'<<raised {type(e).__name__}: {e}>>')\n"
        "print(json.dumps(out))\n"
    )
    env = {**os.environ, "CORPUS_ROOT": str(root), "PYTHONIOENCODING": "utf-8", **REAL_EMBED, **(env or {})}
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, encoding="utf-8", env=env,
                       timeout=300)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return [f"<<server run failed: {r.stdout[-400:]}{r.stderr[-800:]}>>"] * len(calls)


def systems_dir(root):
    return root / "index" / "systems"


def registry(root):
    try:
        return json.loads((systems_dir(root) / "registry.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def live_db(root, module=MODULE):
    reg = registry(root)
    try:
        return systems_dir(root) / reg["systems"][module]["db"]
    except (TypeError, KeyError):
        return None


def generations(root):
    return sorted(p.name for p in systems_dir(root).glob("*.db")) if systems_dir(root).exists() else []


def unpublished(root):
    """Generation files the registry does not name — none may remain after a failed build."""
    reg = registry(root) or {"systems": {}}
    named = {e.get("db") for e in reg.get("systems", {}).values()}
    return [g for g in generations(root) if g not in named]


def db_rows(db):
    conn = sqlite3.connect(f"{Path(db).as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        meta = [dict(r) for r in conn.execute("SELECT * FROM corpus_meta")]
        fts_cols = [r[1] for r in conn.execute("PRAGMA table_info(corpus_fts)")]
        info = [dict(r) for r in conn.execute("SELECT * FROM db_info")]
        # corpus_vec is a sqlite-vec virtual table, unreadable without the extension; its plain shadow table of
        # rowids is readable anywhere and has one row per stored vector.
        vec = None
        try:
            vec = conn.execute("SELECT count(*) FROM corpus_vec_rowids").fetchone()[0]
        except sqlite3.Error:
            pass
    finally:
        conn.close()
    return meta, fts_cols, info, vec


def precondition(root, what):
    """A check that a failure 'leaves the live database untouched' passes vacuously with no live database, so
    every section that protects one first requires it."""
    db = live_db(root)
    if db is None or not db.exists():
        check(False, f"precondition for {what}: a published live database exists", generations(root))
        return None
    return db


def test_build(code, root):
    section("Build")
    rc, out = run(code, ["--system", MODULE, "--no-vectors"], root)
    db = live_db(root)
    check(rc == 0 and db is not None and db.exists(), "a module builds and the registry names its database", out)
    if not db or not db.exists():
        return
    check(GENERATION.match(db.name) and GENERATION.match(db.name)["module"] == MODULE,
          "the published database is a generation file, <module>.<build_id>.db", db.name)
    meta, fts_cols, info, _ = db_rows(db)
    keys = [m.get("entry_key") for m in meta]
    check(len(keys) == len(set(keys)) and all(keys), "every row has a unique entry_key")
    check("entry_key" in fts_cols, "corpus_fts carries entry_key")
    reps = {m.get("representation") for m in meta}
    check(reps == {"verbatim", "compact", "dataset"}, "all three representations are present", reps)
    auth = {(m.get("representation"), m.get("authority")) for m in meta}
    check(auth == {("verbatim", "source"), ("compact", "derived"), ("dataset", "derived")},
          "authority follows each representation's declaration", auth)
    recs = [m for m in meta if m.get("representation") == "dataset"]
    alpha = next((m for m in recs if m.get("record_id") == "thing/alpha"), None)
    check(alpha is not None and alpha.get("dataset") == "things" and alpha.get("record_kind") == "item",
          "a record carries its dataset, record id and kind as columns (never parsed from its key)", recs)
    if alpha:
        check(json.loads(alpha.get("payload") or "null") == RECORDS[0], "the record's payload round-trips exactly")
        check(json.loads(alpha.get("source_json") or "null") == RECORDS[0]["source"]
              and alpha.get("source_path") == "01-rules.md",
              "the record's whole source object, both anchors included, round-trips", alpha.get("source_json"))
    docs = [m for m in meta if m.get("representation") in ("verbatim", "compact")]
    check(len(docs) == 3 and all(m.get("path") and not m.get("payload") for m in docs),
          "document rows have a path and no payload", docs)
    reg = registry(root)
    entry = (reg or {}).get("systems", {}).get(MODULE, {})
    cfg_hash = hashlib.sha256((root / "Game_Systems" / "Testsys" / "index.cfg").read_bytes()).hexdigest()
    check(len(info) == 1 and info[0].get("build_id") == entry.get("build_id") and info[0].get("module") == MODULE
          and entry.get("schema_version") == 2 and GENERATION.match(db.name)["build"] == entry.get("build_id")
          and info[0].get("cfg_sha256") == entry.get("cfg_sha256") == cfg_hash,
          "db_info, the registry and the generation file agree on module, build id, schema and index.cfg hash",
          (info, entry))
    check(entry.get("counts") == {"verbatim": 2, "compact": 1, "dataset": 2 + len(TABLE_RECORDS)},
          "the registry records counts per representation", entry.get("counts"))

    fp = entry.get("source_fingerprint")
    target = root / "Game_Systems" / "Testsys" / "source" / "srd" / "01-rules.md"
    os.utime(target, (time.time() + 3600, time.time() + 3600))
    run(code, ["--system", MODULE, "--no-vectors"], root)
    fp_touched = registry(root)["systems"][MODULE].get("source_fingerprint")
    text = target.read_text(encoding="utf-8")
    write(target, text + "\nA changed line.\n")
    run(code, ["--system", MODULE, "--no-vectors"], root)
    fp_changed = registry(root)["systems"][MODULE].get("source_fingerprint")
    write(target, text)
    run(code, ["--system", MODULE, "--no-vectors"], root)
    check(fp and fp == fp_touched, "the source fingerprint ignores modification times", (fp, fp_touched))
    check(fp_changed and fp_changed != fp, "the source fingerprint changes with content", (fp, fp_changed))
    check(registry(root)["systems"][MODULE].get("source_fingerprint") == fp,
          "restoring the content restores the fingerprint (deterministic)")

    # A config-only change, still valid: reorder exclude_keys. It must count, and restoring it must restore both.
    cfg = root / "Game_Systems" / "Testsys" / "index.cfg"
    reordered = INDEX_CFG.replace(f"exclude_keys = {EXCLUDE}",
                                  "exclude_keys = " + ", ".join(reversed([k.strip() for k in EXCLUDE.split(",")])))
    write(cfg, reordered)
    rc, out = run(code, ["--system", MODULE, "--no-vectors"], root)
    e_cfg = registry(root)["systems"][MODULE]
    write(cfg, INDEX_CFG)
    run(code, ["--system", MODULE, "--no-vectors"], root)
    e_back = registry(root)["systems"][MODULE]
    check(rc == 0 and e_cfg.get("source_fingerprint") != fp and e_cfg.get("cfg_sha256") != entry.get("cfg_sha256"),
          "a config-only change alters both the fingerprint and the index.cfg hash", (out, e_cfg))
    check(e_back.get("source_fingerprint") == fp and e_back.get("cfg_sha256") == entry.get("cfg_sha256"),
          "restoring the config restores both, deterministically", e_back)

    # A source edited WHILE the build runs: injected at the exact point between building and publishing.
    reg_before, gens_before = sha(systems_dir(root) / "registry.json"), generations(root)
    text = target.read_text(encoding="utf-8")
    result, log = run_py(code, root, BUILD_PRELUDE + """
target = root / "Game_Systems" / "Testsys" / "source" / "srd" / "01-rules.md"
orig = b.build_system_db
def mutating(*a, **k):
    out = orig(*a, **k)
    target.write_text(target.read_text(encoding="utf-8") + "\\nEdited mid-build.\\n", encoding="utf-8")
    return out
b.build_system_db = mutating
try:
    b.build_and_publish(root, index_dir, cfg_of("testsys"), False)
    print("RESULT " + json.dumps("published"))
except Exception as e:
    print("RESULT " + json.dumps(str(e)))
""")
    write(target, text)
    check(isinstance(result, str) and "changed during the build" in result,
          "a source edited during the build is caught before publication", (result, log))
    check(sha(systems_dir(root) / "registry.json") == reg_before and generations(root) == gens_before
          and not list(systems_dir(root).glob("*.tmp.db")),
          "… leaving the registry byte-identical, no new generation and no temp file")


def test_projection(code, root):
    section("Dataset projection")
    if precondition(root, "the projection checks") is None:
        return
    out = server_calls(code, root, [
        ("search_corpus", {"query": "orichalcite", "system": MODULE}),
        ("search_corpus", {"query": "zephyrine", "system": MODULE}),
        ("search_corpus", {"query": "provtokenquux", "system": MODULE}),
    ])
    check("rec:things/thing/alpha" in out[0], "a value only in a nested field map is searchable", out[0])
    check("rec:things/thing/alpha" in out[1], "a value only in a nested field list is searchable", out[1])
    check("rec:" not in out[2] and not out[2].startswith("<<"), "a token only in an excluded provenance key is not",
          out[2])


def test_strict_cfg(code, root, mod):
    section("Strict index.cfg and the record contract (one planted flaw per copy)")
    if precondition(root, "the strict-cfg plants") is None:
        return
    reg_before, gens_before = sha(systems_dir(root) / "registry.json"), generations(root)
    cfg = mod / "index.cfg"

    def expect_failure(label, needle):
        rc, out = run(code, ["--system", MODULE, "--no-vectors"], root)
        check(rc != 0 and needle in out, f"{label} fails the build", out)
        check(sha(systems_dir(root) / "registry.json") == reg_before and generations(root) == gens_before,
              "… leaving the registry byte-identical and no new generation")

    for label, old, new, needle in CFG_PLANTS:
        if INDEX_CFG.count(old) != 1:
            check(False, f"plant '{label}' applies to the fixture cfg exactly once")
            continue
        write(cfg, INDEX_CFG.replace(old, new))
        expect_failure(label, needle)
    write(cfg, INDEX_CFG)

    outside = root / "Outside_Module"
    write(outside / "stray.md", "# Stray\n")
    link = mod / "rules" / "escape"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        print("  SKIP  a symlink escaping the module (this OS or account cannot create one)")
    else:
        write(cfg, INDEX_CFG.replace("path = rules/compact", "path = rules/escape"))
        expect_failure("a symlink that resolves outside the module", "outside the module")
        link.unlink()
        write(cfg, INDEX_CFG)

    data = mod / "data" / "things.jsonl"
    good = data.read_text(encoding="utf-8")
    wrong_dataset = dict(RECORDS[1], id="thing/gamma", dataset="widgets")
    no_dataset = {k: v for k, v in dict(RECORDS[1], id="thing/delta").items() if k != "dataset"}
    for label, bad, needle in (
            ("a record with no id", good + json.dumps({"name": "Nameless", "dataset": "things"}) + "\n", "no id"),
            ("a record with no dataset", good + json.dumps(no_dataset) + "\n", "no dataset"),
            ("a duplicate record id in one file", good + json.dumps(RECORDS[0]) + "\n", "duplicate"),
            ("a record whose dataset disagrees with the rest of its file", good + json.dumps(wrong_dataset) + "\n",
             "disagrees"),
            ("a source that is not an object",
             good + json.dumps(dict(RECORDS[1], id="thing/s1", source="01-rules.md")) + "\n", "malformed source"),
            ("a source with no file",
             good + json.dumps(dict(RECORDS[1], id="thing/s2", source={"anchors": {"start": "harm"}})) + "\n",
             "malformed source"),
            ("a source with empty anchors",
             good + json.dumps(dict(RECORDS[1], id="thing/s3", source={"file": "01-rules.md", "anchors": {}})) + "\n",
             "malformed source"),
            ("a malformed record line", good + "{this is not json\n", "things.jsonl")):
        write(data, bad)
        expect_failure(label, needle)
    write(data, good)
    # Ids are unique across the whole module, not only within a file; and a dataset belongs to one file.
    extras = mod / "data" / "extras.jsonl"
    write(extras, json.dumps(dict(RECORDS[0], dataset="extras")) + "\n")
    expect_failure("a record id duplicated in a second dataset file", "duplicate")
    write(extras, json.dumps(dict(RECORDS[1], id="thing/epsilon")) + "\n")
    expect_failure("a second file declaring the same dataset", "also declared")
    extras.unlink()


def test_row_refs(code, root, mod):
    section("Row references (provenance for records read from table rows)")
    if precondition(root, "the row-reference checks") is None:
        return
    reg_before, gens_before = sha(systems_dir(root) / "registry.json"), generations(root)
    data = mod / "data" / "tables.jsonl"
    good = data.read_text(encoding="utf-8")
    ok = {"index": "index/table-one", "line": 6}

    def plant(rid, **fields):
        return good + json.dumps({"id": rid, "dataset": "tables", "kind": "item", "name": "Planted", **fields}) + "\n"

    for label, bad, needle in (
            ("a source-less record with two row-reference fields",
             plant("item/p1", index_rows=[ok], rows=[ok]), "exactly one"),
            ("a source-less record with no row reference", plant("item/p2"), "no row reference"),
            ("an empty row-reference list", plant("item/p3", index_rows=[]), "non-empty list"),
            ("a row reference that is not an object",
             plant("item/p4", index_rows=["index/table-one"]), "must be an object"),
            ("a row reference with no index", plant("item/p5", index_rows=[{"line": 6}]), "has no index"),
            ("a row reference whose line is a boolean",
             plant("item/p6", index_rows=[{"index": "index/table-one", "line": True}]), "has no integer line"),
            ("a row reference to a record the module does not have",
             plant("item/p7", index_rows=[{"index": "index/nowhere", "line": 6}]), "does not resolve"),
            ("a row reference to a record with no direct source (no second hop)",
             plant("item/p8", index_rows=[{"index": "item/gamma", "line": 6}]), "no direct source"),
            ("a row line outside the referenced table's span",
             plant("item/p9", index_rows=[{"index": "index/table-one", "line": 12}]), "outside")):
        write(data, bad)
        rc, out = run(code, ["--system", MODULE, "--no-vectors"], root)
        check(rc != 0 and needle in out, f"{label} fails the build", out)
        check(sha(systems_dir(root) / "registry.json") == reg_before and generations(root) == gens_before,
              "… leaving the registry byte-identical and no new generation")
    write(data, good)

    meta = {m.get("record_id"): m for m in db_rows(live_db(root))[0]}
    stored = json.loads((meta.get("pack/kit") or {}).get("source_json") or "null")
    check((meta.get("pack/kit") or {}).get("source_path") == "" and stored == {"via_row_refs": [
              {"index": "index/table-one", "rows": [6, 7, 9], "source": TABLE_RECORDS[0]["source"]},
              {"index": "index/table-two", "rows": [21], "source": TABLE_RECORDS[1]["source"]}]},
          "inherited provenance is stored whole, per table in reference order, and never as a direct source_path",
          meta.get("pack/kit"))
    check(json.loads((meta.get("item/delta") or {}).get("source_json") or "null") == TABLE_RECORDS[2]["source"],
          "a directly sourced record stores exactly its own source", meta.get("item/delta"))

    rc, out = run(code, ["--system", OTHER, "--no-vectors"], root)
    check(rc == 0, "the module without row_refs builds", out)
    calls = [
        ("get_system_record", {"system": MODULE, "entry_key": "rec:tables/item/gamma"}),
        ("get_system_record", {"system": MODULE, "entry_key": "rec:tables/pack/kit"}),
        ("get_system_record", {"system": MODULE, "entry_key": "rec:tables/roll-table/omen"}),
        ("get_system_record", {"system": MODULE, "entry_key": "rec:tables/item/delta"}),
        ("get_system_record", {"system": MODULE, "entry_key": "rec:tables/index/table-one"}),
        ("get_system_record", {"system": OTHER, "entry_key": "rec:gizmos/gizmo/one"}),
        ("search_corpus", {"query": "Kit", "system": MODULE, "representation_filter": "dataset"}),
        ("search_corpus", {"query": "Gamma", "system": MODULE, "representation_filter": "dataset"}),
    ]
    gamma, kit, omen, delta, table, gizmo, kit_hit, gamma_hit = server_calls(code, root, calls)
    via = "Source (via row reference): "
    check(f"{via}01-rules.md #resolution — row line 7  (index/table-one)" in gamma and '"line_start": 5' in gamma
          and "(none recorded)" not in gamma,
          "a record read from a table row shows the table's whole source and its row line, marked as inherited", gamma)
    check(f"{via}01-rules.md #resolution — row lines 6–7, 9  (index/table-one)" in kit
          and f"{via}sub/02-more.md #harm, #harm-1 — row line 21  (index/table-two)" in kit,
          "references are grouped by table, their row lines compacted, and every table named", kit)
    check(f"{via}sub/02-more.md #harm, #harm-1 — row line 22" in omen,
          "a `rows` reference resolves like the others", omen)
    check("Source: 01-rules.md" in delta and "via row reference" not in delta,
          "a record with its own source keeps it, and its index_rows (even a dangling one) are not read", delta)
    check("Source: 01-rules.md" in table and "via row reference" not in table,
          "an index record's own table rows are not read as references", table)
    check("(none recorded)" in gizmo and "via row reference" not in gizmo,
          "a module without row_refs leaves a source-less record unsourced, as before", gizmo)
    check(f"{via}01-rules.md #resolution — row lines 6–7, 9 (+1 more table)" in kit_hit,
          "a search hit summarises the first table and says more exist", kit_hit)
    # Scoped to Gamma's own hit: the same search also finds Kit, whose summary rightly says more exist.
    gamma_block = next((b for b in gamma_hit.split("\n\n") if "rec:tables/item/gamma" in b), "")
    check(f"{via}01-rules.md #resolution — row line 7" in gamma_block and "more table" not in gamma_block,
          "a search hit with one table claims no more", gamma_hit)


def test_publication(code, root, mod):
    section("Publication")
    db = precondition(root, "the publication checks")
    if db is None:
        return
    reg_path = systems_dir(root) / "registry.json"

    # Portable: the registry write itself fails, injected at that exact call.
    before = sha(reg_path)
    result, log = run_py(code, root, BUILD_PRELUDE + """
def refuse(*a, **k):
    raise OSError("injected registry failure")
si.write_registry = refuse
try:
    b.build_and_publish(root, index_dir, cfg_of("testsys"), False)
    print("RESULT " + json.dumps("published"))
except Exception as e:
    print("RESULT " + json.dumps(str(e)))
""")
    check(isinstance(result, str) and "injected registry failure" in result and sha(reg_path) == before
          and not unpublished(root) and not list(systems_dir(root).glob("*.tmp.db")),
          "a registry write that fails leaves the registry byte-identical and no generation or temp behind",
          (result, log, unpublished(root)))
    # Windows only: replacing a read-only file is refused there, while POSIX allows it (the directory decides).
    if os.name == "nt":
        os.chmod(reg_path, stat.S_IREAD)
        try:
            rc, out = run(code, ["--system", MODULE, "--no-vectors"], root)
        finally:
            os.chmod(reg_path, stat.S_IREAD | stat.S_IWRITE)
        check(rc != 0 and sha(reg_path) == before and not unpublished(root),
              "a read-only registry fails the build cleanly (Windows)", (out, unpublished(root)))
    else:
        print("  SKIP  a read-only registry (POSIX permits replacing it; the injected failure covers this)")

    # An interrupt AFTER the registry swap: the real write runs, then KeyboardInterrupt arrives before the build
    # can record that it published. The registry is the pointer, so the generation it now names must survive.
    old_live = live_db(root)
    result, log = run_py(code, root, BUILD_PRELUDE + """
real = si.write_registry
def swap_then_interrupt(*a, **k):
    real(*a, **k)
    raise KeyboardInterrupt
si.write_registry = swap_then_interrupt
try:
    b.build_and_publish(root, index_dir, cfg_of("testsys"), False)
    print("RESULT " + json.dumps("returned"))
except KeyboardInterrupt:
    print("RESULT " + json.dumps("interrupted"))
except BaseException as e:
    print("RESULT " + json.dumps("other: " + repr(e)))
""")
    now_live = live_db(root)
    check(result == "interrupted" and now_live is not None and now_live != old_live and now_live.exists()
          and not list(systems_dir(root).glob("*.tmp.db")),
          "an interrupt after the registry swap propagates and leaves the registry naming an existing generation",
          (result, log, old_live, now_live, unpublished(root)))
    # The interrupt also skipped collection, so the superseded generation is left for the next build to collect —
    # an orphan is harmless, where deleting the named one would have left the registry pointing at nothing.
    check(unpublished(root) == [old_live.name],
          "… leaving only the superseded generation behind, for the next build to collect", unpublished(root))

    # The portable invariant: a reader already open keeps working after a new generation is published. (On
    # POSIX the old file may be unlinked while open, which is legal; on Windows it cannot be, and stays.)
    held = live_db(root)
    reader = sqlite3.connect(f"{held.as_uri()}?mode=ro", uri=True)
    reader.execute("SELECT count(*) FROM corpus_meta").fetchone()
    try:
        rc, out = run(code, ["--system", MODULE, "--no-vectors"], root)
        now = live_db(root)
        check(rc == 0 and now != held and now.exists(),
              "a reader holding the live generation does not block publishing a new one", out)
        try:
            still = reader.execute("SELECT count(*) FROM corpus_meta").fetchone()[0] > 0
        except sqlite3.Error as e:
            still, out = False, str(e)
        check(still, "… and the already-open reader can still query the old generation", out)
    finally:
        reader.close()
    rc, out = run(code, ["--system", MODULE, "--no-vectors"], root)
    check(rc == 0 and not unpublished(root), "once released, a later build collects generations no one references",
          unpublished(root))

    procs = [start(code, ["--system", m, "--no-vectors"], root) for m in (MODULE, OTHER)]
    outs = [p.communicate(timeout=600)[0] for p in procs]
    reg = registry(root) or {}
    both = all(p.returncode == 0 for p in procs) and {MODULE, OTHER} <= set(reg.get("systems", {}))
    check(both, "two modules built concurrently both land in the registry", outs)

    # The race made exact: while testsys's database is built but not yet published, othersys builds, publishes
    # and collects garbage. testsys's work in progress must survive that collection and then publish.
    result, log = run_py(code, root, BUILD_PRELUDE + """
orig = b.build_system_db
state = {}
def racing(cfg, tmp, *a, **k):
    out = orig(cfg, tmp, *a, **k)
    if cfg.module == "testsys" and not state:
        state["before"] = tmp.exists()
        state["other"] = b.build_and_publish(root, index_dir, cfg_of("othersys"), False).db
        state["after"] = tmp.exists()
    return out
b.build_system_db = racing
try:
    state["testsys"] = b.build_and_publish(root, index_dir, cfg_of("testsys"), False).db
except Exception as e:
    state["error"] = str(e)
print("RESULT " + json.dumps(state))
""")
    reg = (registry(root) or {}).get("systems", {})
    ok = (isinstance(result, dict) and result.get("before") and result.get("after") and "error" not in result
          and reg.get(MODULE, {}).get("db") == result.get("testsys") and reg.get(OTHER, {}).get("db") == result.get("other")
          and (systems_dir(root) / str(result.get("testsys"))).exists()
          and (systems_dir(root) / str(result.get("other"))).exists())
    check(ok, "a build in progress survives another module publishing and collecting mid-build, then publishes",
          (result, log))

    # Two index.cfg files claiming one module: refused, never a silent overwrite of the first's entry.
    dup_cfg = root / "Game_Systems" / "Dupsys" / "index.cfg"
    entry_before = json.dumps((registry(root) or {}).get("systems", {}).get(MODULE), sort_keys=True)
    write(dup_cfg, index_cfg(MODULE))
    rc1, out1 = run(code, ["--system", MODULE, "--no-vectors"], root)
    rc2, out2 = run(code, ["--all-systems", "--no-vectors"], root)
    entry_after = json.dumps((registry(root) or {}).get("systems", {}).get(MODULE), sort_keys=True)
    shutil.rmtree(dup_cfg.parent)
    check(rc1 != 0 and "more than one index.cfg" in out1, "--system refuses a module two index.cfg files claim", out1)
    check(rc2 != 0 and "more than one index.cfg" in out2 and entry_after == entry_before,
          "--all-systems refuses it too, leaving that module's registry entry untouched", out2)

    # Registry-only routing: a real, valid generation of othersys stays on disk, but its registry entry goes.
    reg = registry(root)
    other_gen = systems_dir(root) / reg["systems"][OTHER]["db"]
    del reg["systems"][OTHER]
    reg_path.write_text(json.dumps(reg), encoding="utf-8")
    out = server_calls(code, root, [("search_corpus", {"query": "gizmo", "system": OTHER}),
                                    ("search_corpus", {"query": "gizmo", "system": "nosuch"})])
    check(other_gen.exists() and out[0].startswith("[!]") and "Gizmo" not in out[0],
          "a module whose valid generation is on disk but not in the registry is not served", out[0])
    check(MODULE in out[1] and OTHER not in out[1], "… and the registered systems listed do not include it", out[1])
    run(code, ["--system", MODULE, "--no-vectors"], root)
    check(not other_gen.exists(), "… and a later build collects that unreferenced generation")
    rc, out = run(code, ["--system", OTHER, "--no-vectors"], root)
    check(rc == 0 and OTHER in (registry(root) or {}).get("systems", {}), "rebuilding the module re-registers it", out)

    other_cfg = root / "Game_Systems" / "Othersys" / "index.cfg"
    saved = other_cfg.read_text(encoding="utf-8")
    other_cfg.unlink()
    rc, out = run(code, ["--all-systems", "--no-vectors"], root)
    reg = registry(root) or {}
    check(rc == 0 and OTHER not in reg.get("systems", {}) and MODULE in reg.get("systems", {}),
          "a module whose index.cfg is removed drops out of the registry on --all-systems", (out, reg))
    write(other_cfg, saved)
    run(code, ["--all-systems", "--no-vectors"], root)


def test_vectors(code, root):
    section("Vector lane")
    sys.path.insert(0, str(code))
    try:
        import embedding
        available = embedding.AVAILABLE
    except Exception:
        available = False
    finally:
        sys.path.pop(0)
    if not available:
        print("  SKIP  the embedding dependencies are absent; the vector lane is not built here")
        return
    if precondition(root, "the vector checks") is None:
        return

    # A model that cannot run: the build must still publish a searchable full-text database, and say so.
    build_before = (registry(root) or {}).get("systems", {}).get(MODULE, {}).get("build_id")
    rc, out = run(code, ["--system", MODULE], root, env=BROKEN_EMBED)
    entry = (registry(root) or {}).get("systems", {}).get(MODULE, {})
    _, _, _, vec = db_rows(live_db(root))
    check(rc == 0 and entry.get("build_id") != build_before and "FAILED" in out and not vec,
          "a vector-lane failure still publishes the full-text database, without vectors, and reports it", out)
    hit = server_calls(code, root, [("search_corpus", {"query": "grapnel", "system": MODULE})])[0]
    check("doc:source/srd/01-rules.md" in hit and "rec:things/thing/alpha" in hit,
          "… and that database answers full-text searches", hit)

    # The real model, only where it demonstrably runs: importable is not the same as usable.
    probe, log = run_py(code, root, "import embedding\nembedding.embed_documents(['probe'])\nprint('RESULT true')")
    if probe is not True:
        print("  SKIP  the embedding model cannot run here (no usable cache and no download); positive vector "
              "checks not run")
        return
    rc1, out1 = run(code, ["--system", MODULE], root)
    meta, _, _, vec = db_rows(live_db(root))
    docs = sum(1 for m in meta if m.get("representation") in ("verbatim", "compact"))
    check(rc1 == 0 and vec == docs, f"documents are embedded and dataset rows are not ({vec} vectors, {docs} docs)",
          out1)
    rc2, out2 = run(code, ["--system", MODULE], root)
    m = re.search(r"(\d+) newly embedded", out2)
    check(rc2 == 0 and m and int(m.group(1)) == 0, "a second build reuses every embedding", out2)
    out = server_calls(code, root, [
        ("search_corpus", {"query": "grapnel launcher", "system": MODULE, "mode": "vector",
                           "representation_filter": "dataset"}),
        ("search_corpus", {"query": "orichalcite", "system": MODULE, "mode": "hybrid",
                           "representation_filter": "dataset"}),
    ])
    check("vector-eligible" in out[0] and "rec:" not in out[0],
          "a vector search on datasets reports that nothing is vector-eligible", out[0])
    check("rec:things/thing/alpha" in out[1], "hybrid on datasets returns the lexical lane's hits", out[1])
    # The database has vectors, but the model is broken at query time: hybrid over datasets must never need it.
    broken = server_calls(code, root, [("search_corpus", {"query": "orichalcite", "system": MODULE, "mode": "hybrid",
                                                          "representation_filter": "dataset"})], env=BROKEN_EMBED)[0]
    check("rec:things/thing/alpha" in broken and not broken.startswith(("[!]", "<<")),
          "hybrid over datasets goes straight to the lexical lane, even with a broken model", broken)


def test_server(code, root):
    section("Server")
    if precondition(root, "the server checks") is None:
        return
    calls = [
        ("search_corpus", {"query": "grapnel", "system": MODULE}),
        ("search_corpus", {"query": "grapnel", "system": MODULE, "representation_filter": "verbatim"}),
        ("search_corpus", {"query": "grapnel", "system": MODULE, "representation_filter": "dataset"}),
        ("search_corpus", {"query": "grapnel", "system": MODULE, "representation_filter": " verbatim , compact "}),
        ("search_corpus", {"query": "grapnel", "system": MODULE, "representation_filter": "verbatim,verbatim"}),
        ("search_corpus", {"query": "grapnel", "system": MODULE, "representation_filter": "summary"}),
        ("search_corpus", {"query": "grapnel", "system": MODULE, "representation_filter": "verbatim,summary"}),
        ("search_corpus", {"query": "grapnel", "system": MODULE, "representation_filter": ""}),
        ("search_corpus", {"query": "lantern", "representation_filter": "verbatim"}),
        ("get_section", {"path": "source/srd/01-rules.md", "system": MODULE}),
        ("get_section", {"path": "data/things.jsonl", "system": MODULE}),
        ("get_system_record", {"system": MODULE, "entry_key": "rec:things/thing/alpha"}),
        ("get_system_record", {"system": MODULE, "dataset": "things", "record_id": "thing/beta"}),
        ("get_system_record", {"system": MODULE, "entry_key": "rec:things/thing/alpha", "dataset": "things",
                               "record_id": "thing/alpha"}),
        ("get_system_record", {"system": MODULE, "dataset": "things"}),
        ("get_system_record", {"system": MODULE, "entry_key": "rec:gizmos/gizmo/one"}),
        ("get_system_record", {"system": MODULE, "entry_key": "doc:source/srd/01-rules.md"}),
        ("search_corpus", {"query": "grapnel", "system": "nosuch"}),
        ("search_corpus", {"query": "grapnel", "system": "../x"}),
        ("search_corpus", {"query": "lantern"}),
    ]
    (hit, verb, data, spaced, dup, badrep, mixed, empty, corpus_filter, sect, sect_data, rec_key, rec_id, both,
     partial, wrongsys, dockey, unknown, unsafe, corpus) = server_calls(code, root, calls)
    check(all(s in hit for s in (MODULE, "dataset", "derived", "rec:things/thing/alpha", "verbatim", "source")),
          "system hits show module, representation, authority and entry key", hit)
    check("rec:" not in verb and "doc:source/srd/01-rules.md" in verb, "representation_filter=verbatim excludes records",
          verb)
    check("doc:" not in data and "rec:things/thing/alpha" in data, "representation_filter=dataset returns only records",
          data)
    check("doc:source/srd/01-rules.md" in spaced and "doc:rules/compact/01-rules.md" in spaced and "rec:" not in spaced,
          "a comma list with spaces selects several representations", spaced)
    # Two identical errors would also be "the same", so the result must first be a real one.
    check(dup == verb and not dup.startswith(("[!]", "<<")) and "doc:" in dup,
          "a duplicated representation is the same as one", (dup, verb))
    for label, res in (("an unknown representation", badrep), ("a list with one invalid value", mixed),
                       ("an empty filter", empty), ("a filter without a system", corpus_filter)):
        check(res.startswith("[!]"), f"{label} is an error", res)
    check("Resolution" in sect and "Harm" in sect, "get_section lists a system document's sections", sect)
    check("get_system_record" in sect_data, "get_section on a dataset file points to get_system_record", sect_data)
    check('"name": "Alpha"' in rec_key and "resolution-1" in rec_key,
          "get_system_record fetches by entry key, with the whole source", rec_key)
    check('"name": "Beta"' in rec_id, "get_system_record fetches by dataset and record id", rec_id)
    for label, res in (("both selector forms at once", both), ("a partial selector", partial),
                       ("another module's record key", wrongsys), ("a document key", dockey)):
        check(res.startswith("[!]"), f"get_system_record refuses {label}", res)
    check(unknown.startswith("[!]") and MODULE in unknown, "an unknown system fails and lists the registered ones",
          unknown)
    check(unsafe.startswith("[!]") and "invalid" in unsafe.lower(), "an unsafe system name is rejected", unsafe)
    check("Lore_Note" in corpus and "rec:" not in corpus and "doc:" not in corpus,
          "a search without `system` is the corpus, with no system fields", corpus)

    reg_path = systems_dir(root) / "registry.json"
    saved = reg_path.read_text(encoding="utf-8")
    base = json.loads(saved)
    # A database of the wrong module, and one of the wrong schema, each registered under testsys's name.
    wrongmod = systems_dir(root) / f"{MODULE}.wrongmodule.db"
    oldschema = systems_dir(root) / f"{MODULE}.oldschema.db"
    shutil.copy2(systems_dir(root) / base["systems"][OTHER]["db"], wrongmod)
    shutil.copy2(systems_dir(root) / base["systems"][MODULE]["db"], oldschema)
    conn = sqlite3.connect(oldschema)
    conn.execute("UPDATE db_info SET schema_version = 1")
    conn.commit()
    conn.close()
    for label, edit, needle in (
            ("a registry path that escapes index/systems",
             lambda r: r["systems"][MODULE].__setitem__("db", "../../search_index.db"), "outside"),
            ("a registry/database build-id mismatch",
             lambda r: r["systems"][MODULE].__setitem__("build_id", "not-the-real-build"), "stale"),
            ("a database built for another module",
             lambda r: r["systems"][MODULE].update(db=wrongmod.name, build_id=base["systems"][OTHER]["build_id"]),
             "built for module"),
            ("a database of another schema version",
             lambda r: r["systems"][MODULE].update(db=oldschema.name), "schema")):
        reg = json.loads(saved)
        edit(reg)
        reg_path.write_text(json.dumps(reg), encoding="utf-8")
        res = server_calls(code, root, [("search_corpus", {"query": "grapnel", "system": MODULE})])[0]
        check(res.startswith("[!]") and needle in res.lower(), f"{label} is refused", res)
    reg_path.write_text(saved, encoding="utf-8")
    wrongmod.unlink()
    oldschema.unlink()

    # A tampered cfg path in the registry must not be followed: freshness comes from the Game_Systems tree.
    outside = root / "Outside_Cfg" / "index.cfg"
    write(outside, "[system]\nmodule = testsys\n")
    reg = json.loads(saved)
    reg["systems"][MODULE]["cfg"] = "../" * 6 + "Outside_Cfg/index.cfg"
    reg_path.write_text(json.dumps(reg), encoding="utf-8")
    tampered = server_calls(code, root, [("index_status", {"system": MODULE})])[0]
    reg_path.write_text(saved, encoding="utf-8")
    check("unchanged since" in tampered.lower() and "Outside_Cfg" not in tampered,
          "a registry cfg path pointing elsewhere is ignored; freshness still comes from the module's own config",
          tampered)

    status_fresh = server_calls(code, root, [("index_status", {"system": MODULE})])[0]
    target = root / "Game_Systems" / "Testsys" / "rules" / "compact" / "01-rules.md"
    text = target.read_text(encoding="utf-8")
    write(target, text + "\nEdited after the build.\n")
    status_changed = server_calls(code, root, [("index_status", {"system": MODULE})])[0]
    write(target, text)
    check("unchanged since" in status_fresh.lower(), "index_status reports sources unchanged when they are",
          status_fresh)
    check("changed since" in status_changed.lower() and "unchanged since" not in status_changed.lower(),
          "index_status recomputes the fingerprint and reports sources changed since the build", status_changed)


CORPUS_QUERIES = [
    ("search_corpus", {"query": "harvest"}),
    ("search_corpus", {"query": "guild OR council", "limit": 20}),
    ("search_corpus", {"query": '"old mill"'}),
    ("search_corpus", {"query": "trade*", "category_filter": "Factions"}),
    ("search_corpus", {"query": "rules", "type_filter": "rules-reference"}),
    ("search_corpus", {"query": "condition", "missing_filter": "keywords"}),
    ("search_corpus", {"query": "winter", "show_sections": False}),
    ("search_corpus", {"query": "AND OR"}),
    ("get_section", {"path": GATE_PATH}),
    ("get_section", {"path": GATE_PATH, "heading": "First Part", "level": 3}),
]


def snapshot_corpus(real_root, dest):
    """Copy the corpus's indexable source (Markdown and text) once, so both builds read identical inputs."""
    skip = {".git", "index", "__pycache__", "node_modules"}
    n = 0
    for where, dirs, files in os.walk(real_root):
        dirs[:] = [d for d in dirs if d not in skip]
        rel = Path(where).relative_to(real_root)
        for f in files:
            if f.lower().endswith((".md", ".txt")):
                target = dest / rel / f
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(Path(where) / f, target)
                n += 1
    write(dest / GATE_PATH, GATE_DOC)
    return n


def test_corpus_gate(tmp):
    section(f"Corpus regression gate (code at {BASE_COMMIT} vs the working tree, one immutable snapshot)")
    snapshot = tmp / "gate_snapshot"
    files = snapshot_corpus(REPO, snapshot)
    print(f"  INFO  snapshot: {files} Markdown and text files, plus the gate document")
    outputs = {}
    for label, source in (("old", BASE_COMMIT), ("new", "working")):
        code = copy_code(tmp / f"gate_{label}_code", source)
        serve_root = tmp / f"gate_{label}_root"
        index_dir = serve_root / "index"
        index_dir.mkdir(parents=True)
        cfg = (code / "indexer.cfg").read_text(encoding="utf-8")
        cfg = "\n".join(f"index_directory = {index_dir}" if l.strip().startswith("index_directory") else l
                        for l in cfg.splitlines())
        (code / "gate.cfg").write_text(cfg, encoding="utf-8")
        rc, log = run(code, ["--cfg", str(code / "gate.cfg"), "--no-vectors"], snapshot, timeout=900)
        if rc != 0 or not (index_dir / "search_index.db").exists():
            check(False, f"the {label} builder builds the snapshot into a temp directory", log)
            return
        outputs[label] = server_calls(code, serve_root, CORPUS_QUERIES)
    old, new = outputs["old"], outputs["new"]
    check(len(old) == len(new) == len(CORPUS_QUERIES), f"all {len(CORPUS_QUERIES)} fixed calls ran on both versions")
    searches = [o for (name, _), o in zip(CORPUS_QUERIES, old) if name == "search_corpus"]
    hits = sum(1 for o in searches if o.startswith("Found ") and not o.startswith("Found 0"))
    check(hits >= 5, f"{hits} of {len(searches)} searches returned hits, so the comparison has substance")
    sections = [o for (name, _), o in zip(CORPUS_QUERIES, old) if name == "get_section"]
    check(all("First Part" in o for o in sections), "both section reads of the gate document returned it", sections)
    diffs = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    check(not diffs, "every call is byte-identical across the change", f"differing calls: {diffs}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pause", action="store_true")
    ap.add_argument("--skip-corpus-gate", action="store_true")
    args = ap.parse_args()
    started = time.time()
    # Build logs carry non-Latin text; a Windows console code page must not crash the report.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    tmp = Path(tempfile.mkdtemp(prefix="test_system_index_"))
    not_a_dir = tmp / "embed-cache-is-a-file"
    not_a_dir.write_text("not a directory", encoding="utf-8")
    BROKEN_EMBED["CORPUS_EMBED_CACHE"] = str(not_a_dir)
    try:
        code = copy_code(tmp / "code")
        root = tmp / "corpus"
        mod = make_fixture(root)
        section("Ordinary corpus build")
        rc, out = run(code, ["--no-vectors"], root)
        check(rc == 0, "the fixture corpus builds", out)
        check(not generations(root), "an ordinary corpus build builds no module database", generations(root))
        test_build(code, root)
        test_projection(code, root)
        test_strict_cfg(code, root, mod)
        test_row_refs(code, root, mod)
        test_publication(code, root, mod)
        test_vectors(code, root)
        test_server(code, root)
        if args.skip_corpus_gate:
            print("\nCorpus regression gate\n  SKIP  --skip-corpus-gate")
        else:
            test_corpus_gate(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = all(RESULTS)
    print(f"\nRESULT: {'ALL PASS' if ok else 'FAILED'} ({sum(RESULTS)}/{len(RESULTS)})")
    print(f"Runtime: {time.time() - started:.2f}s")
    if not args.no_pause and sys.stdin.isatty():
        input("Press Enter to exit...")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

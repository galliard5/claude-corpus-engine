#!/usr/bin/env python3
"""
mutate_layers.py — In-memory mutation checks for rules layers (chain-aware search, stage 1).

Each mutant is one module's source (system_index.py or build_indexes.py) with one stage-1 guard disabled or
weakened, executed into that module's own namespace; then test_layers runs, and the mutant is covered when at least
one test fails or errors. The original source is re-executed after every mutant. No file is edited; the tests use
temporary directories only, and redirect the builder's history log.

Usage:
    python mutate_layers.py [--no-pause]

Command line arguments:
    --no-pause   Skip end-of-run pause

# changed 2026-10-18: created (chain-aware search stage 1, Codex 938).
# changed 2026-10-18: mutants for the Codex 940 fixes (root contents, the strict [rules_layers] section, dependency
#   schemas).
# changed 2026-11-12: stage 2 moved the [rules_layers] parsing into system_index.parse_rules_layers; its three
#   mutants now target it there, and a fourth checks the builder still delegates to it.
# changed 2026-11-12: Codex 951 made discover contained; the "private roots ignored" mutant was repointed at its new
#   loop head (same mutation: discovery over Game_Systems only).
# changed 2026-11-13: four mutants for containment at the builder's opens (Codex 965): each of the three read-only
#   opens of a published generation made unchecked, and system_index.open_contained without its re-check once open.
# changed 2026-11-13: three mutants for the embedding-cache ATTACH (Codex 967): attached unchecked, not re-checked
#   once attached, and a refusal left out of the build's errors.
# changed 2026-11-14: eight mutants for --all-systems safety (audit batch 2): pruning a published dependent's
#   dependency, held only one level deep, the empty-discovery wipe, both new failures unreported, the first claimant
#   taken, and the published-cycle check off or not following dependencies. The private-roots prune mutant follows
#   the prune into its new set.
# changed 2026-11-15: 23 mutants for audit batch 4: the lock (dead owner, host, stale threshold, break and release
#   by token, sharing violations), the registry replace retry, pid liveness, the temp sweep, an extends parent
#   loaded by declaration (B8), and the systems directory anchored to the corpus (N1).
"""

import io
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_indexes   # noqa: E402
import system_index    # noqa: E402

MODULES = {"si": system_index, "bi": build_indexes}
SOURCES = {k: Path(m.__file__).read_text(encoding="utf-8") for k, m in MODULES.items()}
TESTS = ["test_layers"]
OFF = "if False:"

MUTANTS = [
    # ---- manifest layer fields
    ("manifest: an unknown kind accepted", "si",
     "    if not isinstance(kind, str) or (kind and kind not in LAYER_KINDS):", "    if not isinstance(kind, str):"),
    ("manifest: a malformed extends accepted", "si",
     "    if not isinstance(extends, str) or (extends and not SYSTEM_NAME.match(extends)):",
     "    if not isinstance(extends, str):"),
    ("manifest: extends naming itself accepted", "si", "    if extends and extends == module:", "    " + OFF),
    ("manifest: extends without kind accepted", "si", "    if extends and not kind:", "    " + OFF),
    ("manifest: homebrew without extends accepted", "si",
     '    if kind in ("variant", "thirdparty", "homebrew") and not extends:', "    " + OFF),
    ("manifest: relations without kind accepted", "si", "    if has_relations and not kind:", "    " + OFF),
    ("manifest: the representation loop's name reused", "si",
     "                        kind=layer_kind, extends=layer_extends, manifest_path=manifest_path,",
     "                        kind=kind, extends=layer_extends, manifest_path=manifest_path,"),
    # ---- layered vs legacy
    ("layered: relations alone do not make a layer", "si",
     "        return bool(self.extends) or self.relations_path is not None", "        return bool(self.extends)"),
    ("layered: relation targets are not dependencies", "si",
     "        deps = {r.target.layer for r in self.relations}", "        deps = set()"),
    ("fingerprint: always the legacy algorithm", "si",
     "    if not cfg.layered:\n        return source_fingerprint(cfg)", "    if True:\n        return source_fingerprint(cfg)"),
    ("fingerprint: the layered one for legacy too", "si",
     "    if not cfg.layered:\n        return source_fingerprint(cfg)", "    if False:\n        return source_fingerprint(cfg)"),
    ("fingerprint: manifest not covered", "si",
     '    h.update(b"manifest:" + cfg.manifest_path.read_bytes() + b"\\n")', "    pass"),
    ("fingerprint: relations not covered", "si",
     '    h.update(b"relations:" + (cfg.relations_path.read_bytes() if cfg.relations_path is not None else b"\\0none")\n'
     '             + b"\\n")', "    pass"),
    ("fingerprint: dependencies not covered", "si",
     '        h.update(f"depends_on:{layer}={depends_on[layer]}\\n".encode())', "        pass"),
    # ---- relations.yaml
    ("relations: an anchor in a key accepted", "si", '    if "#" in key:', "    " + OFF),
    ("relations: a key's form unchecked", "si", "    if not ENTRY_KEY.match(key):", "    " + OFF),
    ("relations: a target in the same layer accepted", "si", "        if layer == module:", "        " + OFF),
    ("relations: a section on a record accepted", "si",
     '        if key.startswith("rec:"):\n            problems.append(f"{where}: a record key takes no section',
     '        if False:\n            problems.append(f"{where}: a record key takes no section'),
    ("relations: the level range unchecked", "si",
     "        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 6:",
     "        if not isinstance(level, int):"),
    ("relations: any mode accepted", "si", "        if mode not in RELATION_MODES:", "        " + OFF),
    ("relations: any status accepted", "si", "        if status not in RELATION_STATUSES:", "        " + OFF),
    ("relations: settled without a decider accepted", "si",
     '        if status == "settled" and (not decided or not decider):', "        " + OFF),
    ("relations: a malformed pin accepted", "si", '        elif pin != "" and not HEX64.match(pin):', "        elif False:"),
    ("relations: an unquoted pin accepted", "si", '        if pin != "" and not isinstance(pin, str):',
     "        " + OFF),
    ("relations: a repeated pair accepted", "si", "        if pair in seen:", "        " + OFF),
    ("relations: unknown keys accepted", "si", "        extra = sorted(set(item) - RELATION_KEYS)",
     "        extra = []"),
    # ---- canonical unit hashes
    ("hash: record keys not sorted", "si",
     '        body = json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"), ensure_ascii=False)',
     '        body = json.dumps(json.loads(text), sort_keys=False, separators=(",", ":"), ensure_ascii=False)'),
    ("hash: trailing whitespace kept", "si",
     '    lines = [ln.rstrip() for ln in text.replace("\\r\\n", "\\n").replace("\\r", "\\n").split("\\n")]',
     '    lines = text.split("\\n")'),
    ("hash: no domain separation", "si",
     '        return UNIT_HASH_DOMAIN + b"document\\n" + normalize_unit_text(text).encode("utf-8")',
     '        return UNIT_HASH_DOMAIN + b"record\\n" + normalize_unit_text(text).encode("utf-8")'),
    ("hash: the heading not covered", "si", ' + norm_heading(heading).encode("utf-8")', ' + b""'),
    ("hash: an ambiguous section accepted", "si", "    if len(hits) != 1:", "    if not hits:"),
    # ---- private roots and discovery
    ("roots: an absolute path accepted", "si",
     '        if given.startswith("/") or re.match(r"^[A-Za-z]:", r) or ".." in parts or "." in parts:',
     "        " + OFF),
    ("roots: a top-level directory accepted", "si", "        if len(parts) < 2:", "        " + OFF),
    ("roots: a reserved tree accepted", "si",
     '        if parts[0].lower() in ("game_systems", "index", "python", ".git"):', "        " + OFF),
    ("roots: overlapping roots accepted", "si",
     '            if a == b or a.startswith(b + "/") or b.startswith(a + "/"):', "            " + OFF),
    ("roots: an existing lore tree accepted", "si",
     "        content = _root_content_problems(Path(root) / r, raw)\n        if content:",
     "        content = _root_content_problems(Path(root) / r, raw)\n        if False:"),
    ("roots: a folder without an index.cfg accepted", "si",
     '            if not (child / "index.cfg").is_file():', "            " + OFF),
    ("roots: any loose file accepted", "si",
     "        elif child.name.lower() not in LAYER_ROOT_ALLOWED_FILES:", "        elif False:"),
    ("roots: a file declared as a root accepted", "si",
     '    if not root_dir.is_dir():\n        return [f"private root {raw!r} is a file, not a folder"]',
     '    if False:\n        return [f"private root {raw!r} is a file, not a folder"]'),
    # Since stage 2 the [rules_layers] section is parsed by system_index.parse_rules_layers (shared with the server).
    ("cfg: a misspelled key accepted", "si",
     "    for key in sorted(set(settings) - set(RULES_LAYERS_KEYS)):",
     "    for key in []:"),
    ("cfg: a bare line accepted", "si",
     "                for p in section.get(\"patterns\", [])]", "                for p in []]"),
    ("cfg: an empty declaration accepted", "si", '    if "private_roots" in lists and not lists["private_roots"]:',
     "    " + OFF),
    ("cfg: the builder does not use the shared parser", "bi",
     "    return system_index.parse_rules_layers(cfg, root)[0]",
     '    return system_index.validate_private_roots(root, [r for r in str(cfg.get("rules_layers", {}).get('
     '"settings", {}).get("private_roots", "") or "").split(",") if r.strip()])'),
    ("build: an unsupported dependency schema accepted", "bi",
     "        if row[2] not in system_index.SUPPORTED_DEPENDENCY_SCHEMAS:", "        " + OFF),
    ("build: a registry/database schema disagreement accepted", "bi",
     '        if row[2] != entry.get("schema_version"):', "        " + OFF),
    ("discovery: private roots ignored", "si",
     "    found = []\n    for base in _layer_bases(root, private_roots):",
     "    found = []\n    for base in _layer_bases(root, ()):"),
    ("order: dependencies ignored", "si",
     "    pending = {c.module: {d for d in c.dependencies() if d in by_id} for c in cfgs}",
     "    pending = {c.module: set() for c in cfgs}"),
    # ---- the corpus exclusion
    ("corpus: the exclusion off", "bi", '        if any(rel_str == p or rel_str.startswith(p + "/") for p in prefixes):',
     "        " + OFF),
    ("corpus: the exclusion by loose prefix", "bi",
     '        if any(rel_str == p or rel_str.startswith(p + "/") for p in prefixes):',
     "        if any(rel_str.startswith(p) for p in prefixes):"),
    ("corpus: main does not pass the roots", "bi", "        search_excluded_prefixes=private_roots,",
     "        search_excluded_prefixes=(),"),
    # ---- the layered build
    ("build: no dependency snapshot", "bi",
     "    depends_on, dep_dbs = _dependency_snapshot(cfg, sdir, reg_now, not_searched) if cfg.layered else ({}, {})",
     "    depends_on, dep_dbs = ({}, {})"),
    ("build: a dependency database not checked against the registry", "bi",
     '        if row is None or row[0] != entry.get("build_id") or row[1] != layer:', "        " + OFF),
    ("build: a dependency rebuilt meanwhile accepted", "bi", "            if moved:", "            " + OFF),
    ("build: an orphaned target accepted", "bi",
     "            current, why = system_index.resolve_unit(conns[r.target.layer], r.target)\n            if why:",
     "            current, why = system_index.resolve_unit(conns[r.target.layer], r.target)\n            if False:"),
    ("build: an unresolved entry accepted", "bi",
     "            _h, why = system_index.resolve_unit(own_conn, r.entry)\n            if why:",
     "            _h, why = system_index.resolve_unit(own_conn, r.entry)\n            if False:"),
    ("build: a changed pin reported as pinned", "bi",
     '            state = "unpinned" if not r.target_sha256 else ("pinned" if r.target_sha256 == current else "changed")',
     '            state = "unpinned" if not r.target_sha256 else "pinned"'),
    ("build: db_info always schema 2", "bi", "            (cfg.schema_version, cfg.module, build_id,",
     "            (system_index.SCHEMA_VERSION, cfg.module, build_id,"),
    ("build: no layer tables", "bi", "        if cfg.layered:\n            _create_layer_tables(cur)",
     "        if False:\n            _create_layer_tables(cur)"),
    ("build: no layer metadata in the registry", "bi", '            if cfg.layered:\n                entry["layer"]',
     '            if False:\n                entry["layer"]'),
    ("build: the registry always schema 2", "bi", '                "schema_version": cfg.schema_version,',
     '                "schema_version": system_index.SCHEMA_VERSION,'),
    ("build: --all-systems unordered", "bi", "        targets, more = _ordered_targets(targets)", "        more = 0"),
    ("build: prune ignores private roots", "bi",
     '        unclaimed = {m for m in reg["systems"] if not system_index.cfgs_for(root, m, private_roots)}',
     '        unclaimed = {m for m in reg["systems"] if not system_index.cfgs_for(root, m)}'),
    # ---- containment at the builder's opens (Codex 965)
    ("builder open: the dependency snapshot opens unchecked", "bi",
     "            conn, why = system_index.open_contained(path, sdir, _open_published_ro)\n"
     "            if conn is None:                # containment enforced at the open itself",
     "            conn, why = _open_published_ro(path), None\n"
     "            if conn is None:                # containment enforced at the open itself"),
    ("builder open: a relation target opens unchecked", "bi",
     "                conn, why = system_index.open_contained(path, sdir, _open_published_ro)\n"
     "                if conn is None:            # containment enforced at the open itself (Codex 965)",
     "                conn, why = _open_published_ro(path), None\n"
     "                if conn is None:            # containment enforced at the open itself (Codex 965)"),
    ("builder open: the report's own database opens unchecked", "bi",
     "    conn, why = system_index.open_contained(own, sdir, _open_published_ro)",
     "    conn, why = _open_published_ro(own), None"),
    ("builder open: not re-checked once open", "si",
     "    if contained_real(path, sdir)[0] != real:", "    " + OFF),
    # ---- containment at the embedding-cache ATTACH (Codex 967)
    ("embed cache: attached unchecked", "bi",
     "    real, why = system_index.contained_real(live_db, sdir)", "    real, why = Path(live_db), None"),
    ("embed cache: not re-checked once attached", "bi",
     "        if system_index.contained_real(live_db, sdir)[0] != real:", "        " + OFF),
    ("embed cache: a refusal not reported", "bi",
     "        if refused:                         # not fatal", "        if False:                           # not fatal"),
    # ---- --all-systems safety (audit batch 2, Working_Documents/Chain_Search_Audit_Fable.md B1, B2, B4, B5)
    ("prune: a published dependent's dependency unregistered", "bi",
     "            if not keep:\n                break", "            if True:\n                break"),
    ("prune: held followed one level only", "bi",
     "            gone -= keep\n", "            gone -= keep\n            break\n"),
    ("prune: a held module not reported as a failure", "bi",
     "        for module, dependents in held.items():\n            failures += 1",
     "        for module, dependents in held.items():\n            failures += 0"),
    ("prune: an empty discovery wipes the registry", "bi",
     '        if reg["systems"] and not system_index.discover(root, private_roots):', "        " + OFF),
    ("prune: a refusal not reported as a failure", "bi",
     "        if refused:\n            failures += 1", "        if refused:\n            failures += 0"),
    ("claims: --all-systems takes the first claimant", "bi",
     "                found = system_index.find_cfg(root, module, private_roots)",
     "                found = paths[0] if len(paths) == 1 else system_index.find_cfg(root, module, private_roots)"),
    ("cycle: --system ignores the published builds", "bi",
     "    cycle = _published_cycle(cfg.module, cfg.dependencies(), reg)", "    cycle = None"),
    ("cycle: published dependencies not followed", "bi",
     "        stack += [(d, path + [d]) for d in sorted(_published_deps(reg[\"systems\"].get(m)), reverse=True)]",
     "        pass"),
    # ---- lock and temp-file hygiene, the loaded parent, the anchored systems dir (audit batch 4: B3, B6, B7, B8, N1)
    ('lock: a dead owner on this host not recognised', 'si',
     '                if _lock_owner_dead(judged) or time.time()',
     '                if False or time.time()'),
    ("lock: another host's pid checked as if local", 'si',
     '    if host != socket.gethostname() or pid == os.getpid():',
     '    if pid == os.getpid():'),
    ('lock: the stale threshold back above the wait', 'si',
     'LOCK_STALE_S = 90',
     'LOCK_STALE_S = 600'),
    ('lock: a lock taken since removed when breaking', 'si',
     '    if moved != judged:',
     '    if False:'),
    ('lock: release unconditional', 'si',
     '            if path.read_text(encoding="utf-8", errors="replace") == mine:\n                path.unlink()',
     '            if True:\n                path.unlink()'),
    ('lock: a sharing violation on the create raised at once', 'si',
     '            if time.monotonic() - denied_since > SHARING_RETRY_S:',
     '            if True:'),
    ('lock: a sharing violation retried until the timeout', 'si',
     '            if time.monotonic() - denied_since > SHARING_RETRY_S:\n                raise',
     '            if False:\n                raise'),
    ('registry: a sharing violation on the replace not retried', 'si',
     '        _replace_retrying(tmp, path)',
     '        os.replace(tmp, path)'),
    ('pid: no such process taken for alive', 'si',
     '                return {87: False, 5: True}.get(k32.GetLastError())',
     '                return {87: True, 5: True}.get(k32.GetLastError())'),
    ('pid: an exited process taken for alive', 'si',
     '                return code.value == 259                             # STILL_ACTIVE',
     '                return True'),
    ('sweep: temp files never swept', 'si',
     '            elif TEMP_DB.match(f.name) or TEMP_REGISTRY.match(f.name):',
     '            elif False:'),
    ('sweep: a fresh temp file swept', 'si',
     '                if now - f.lstat().st_mtime <= TEMP_STALE_S:\n                    continue',
     '                if False:\n                    continue'),
    ('loaded parent: still demanded as a build', 'bi',
     '        if entry is None and layer in not_searched:',
     '        if False:'),
    ('loaded parent: a relation into it accepted', 'bi',
     '            if layer in targets:',
     '            if False:'),
    ('loaded parent: a built dependency skipped when also declared', 'bi',
     '        if entry is None and layer in not_searched:',
     '        if layer in not_searched:'),
    ('loaded parent: main drops not_searched', 'bi',
     '        code = run_systems(args, root, index_dir, private_roots, not_searched)',
     '        code = run_systems(args, root, index_dir, private_roots)'),
    ('loaded parent: run_systems drops not_searched', 'bi',
     '                                  not_searched=not_searched)',
     '                                  not_searched=())'),
    ('anchor: a systems dir leading out trusted', 'si',
     '    if not _inside(Path(sdir), Path(root)):',
     '    if False:'),
    ('anchor: an index configured outside the corpus refused', 'si',
     '    except ValueError:\n        return None\n    if not _inside(Path(sdir), Path(root)):',
     "    except ValueError:\n        return 'outside'\n    if not _inside(Path(sdir), Path(root)):"),
    ('anchor: a registry file leading out read', 'si',
     '    if not _inside(path, Path(sdir)):',
     '    if False:'),
    ('anchor: the build does not anchor', 'bi',
     '    reg_now = system_index.read_registry(sdir, root)',
     '    reg_now = system_index.read_registry(sdir)'),
    ('anchor: prune does not anchor', 'bi',
     '    if outside:\n        return [], {}, f"{outside}; nothing was pruned"',
     '    if False:\n        return [], {}, f"{outside}; nothing was pruned"'),
    ('anchor: the relations report does not anchor', 'bi',
     '    reg = system_index.read_registry(sdir, root)\n    entry = reg["systems"].get(module)',
     '    reg = system_index.read_registry(sdir)\n    entry = reg["systems"].get(module)'),
]

# Mutants that CANNOT be killed: none are claimed. Every survivor fails the run and is reported.
EQUIVALENT: dict = {}


def run() -> tuple:
    suite = unittest.defaultTestLoader.loadTestsFromNames(TESTS)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main() -> int:
    t0 = time.time()
    sys.stdout.reconfigure(encoding="utf-8")
    quiet = io.StringIO()
    out, sys.stdout = sys.stdout, quiet
    try:
        n, bad = run()
    finally:
        sys.stdout = out
    print(f"baseline: {n} tests, {bad} failing ({'clean' if not bad else 'BROKEN'})")
    if bad:
        return 1
    survivors = n_eq = 0
    for name, key, old, new in MUTANTS:
        src = SOURCES[key]
        assert src.count(old) == 1, (name, src.count(old))
        mod = MODULES[key]
        exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
        out, sys.stdout = sys.stdout, quiet
        try:
            n, bad = run()
        finally:
            sys.stdout = out
            exec(compile(src, mod.__file__, "exec"), mod.__dict__)
        equivalent = not bad and name in EQUIVALENT
        verdict = "KILLED" if bad else ("EQUIVALENT" if equivalent else "SURVIVED")
        survivors += not bad and not equivalent
        n_eq += equivalent
        print(f"{name:64s} {verdict} ({bad} of {n} failing)", flush=True)
    print(f"{len(MUTANTS) - survivors - n_eq} of {len(MUTANTS) - n_eq} killed, {n_eq} equivalent, {survivors} "
          f"survived; Runtime: {time.time() - t0:.2f}s")
    if "--no-pause" not in sys.argv:
        input("Press Enter to exit...")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())

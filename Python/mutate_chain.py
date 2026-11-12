#!/usr/bin/env python3
"""
mutate_chain.py — In-memory mutation checks for rules-chain resolution and chain-aware index_status (chain-aware
search, stage 2).

Each mutant is one module's source (rules_chain.py, system_index.py or search_mcp_server.py) with one stage-2 guard
disabled or weakened, executed into that module's own namespace; then test_chain and test_layers run, and the mutant
is covered when at least one test fails or errors. The original source is re-executed after every mutant. No file
is edited; the tests use temporary directories only.

Usage:
    python mutate_chain.py [--no-pause]

Command line arguments:
    --no-pause   Skip end-of-run pause

# changed 2026-11-12: created (chain-aware search stage 2, Codex 945).
# changed 2026-11-12: Codex 947 — repointed the known-module mutants at the builder-identity rule; added mutants for
#   module identity, adaptation coverage, path safety and registry-entry shape.
# changed 2026-11-12: Codex 949 — mutants for discovery containment, the freshness cfg source and null entries.
# changed 2026-11-12: Codex 951 — mutants for the builder's discovery and the shared loader's containment.
"""

import io
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rules_chain          # noqa: E402
import search_mcp_server    # noqa: E402
import system_index         # noqa: E402

MODULES = {"rc": rules_chain, "si": system_index, "srv": search_mcp_server}
SOURCES = {k: Path(m.__file__).read_text(encoding="utf-8") for k, m in MODULES.items()}
TESTS = ["test_chain", "test_layers"]
OFF = "if False:"

MUTANTS = [
    # ---- selectors and the chain's shape
    ("selectors: two selectors accepted", "rc", "    if (campaign is None) == (chain is None):", "    " + OFF),
    ("chain: more than eight layers accepted", "rc", "    if len(names) > MAX_CHAIN:", "    " + OFF),
    ("chain: an empty entry accepted", "rc", "    if not names or any(not n for n in names):", "    if not names:"),
    # ---- campaigns
    ("campaign: matched case-sensitively", "rc",
     "    hits = [p for p in every if p.parent.name.casefold() == want]",
     "    hits = [p for p in every if p.parent.name == name.strip()]"),
    ("campaign: an ambiguous name takes the first", "rc",
     "    if len(hits) == 1:\n        if not _within(root, hits[0]):", "    if hits:\n        if not _within(root, hits[0]):"),
    ("campaign: the direct layout ignored", "rc",
     '        found.update(p for p in base.glob(f"*/*/{PROFILE_FILE}") if p.parent.name.lower() != "scenarios")',
     "        pass"),
    ("campaign: a Scenarios folder taken for a campaign", "rc",
     'if p.parent.name.lower() != "scenarios")', "if True)"),
    # ---- roles
    ("roles: names matched case-sensitively", "rc", "        mid = given.casefold()", "        mid = given"),
    ("roles: a repeated layer accepted", "rc", "        if mid in seen:", "        " + OFF),
    ("roles: an unknown layer not flagged", "rc", "        if mid not in known:", "        " + OFF),
    ("roles: registered and not_searched accepted", "rc",
     '            if registered:\n                layer.reason = "declared not_searched',
     '            if False:\n                layer.reason = "declared not_searched'),
    ("roles: an undeclared unbuilt module taken as loaded", "rc",
     '        if not registered:\n            layer.reason = (f"not built',
     '        if not registered:\n            layer.role = ROLE_LOADED\n            continue\n'
     '            layer.reason = (f"not built'),
    ("roles: the publication check skipped", "rc",
     "        _db, info, why = system_index.check_publication(sdir, mid, entry)\n        if why:",
     "        _db, info, why = system_index.check_publication(sdir, mid, entry)\n        if False:"),
    # ---- freshness and dependencies
    ("freshness: always unchanged", "rc",
     '        layer.freshness = "unchanged" if now == entry.get("source_fingerprint") else "CHANGED"',
     '        layer.freshness = "unchanged"'),
    ("freshness: schema 3 by the legacy fingerprint", "rc",
     "            now = system_index.layered_fingerprint(cfg, recorded) if cfg.layered else system_index.source_fingerprint(cfg)",
     "            now = system_index.source_fingerprint(cfg)"),
    ("freshness: a change not warned", "rc", '        if layer.freshness == "CHANGED":\n            res.warnings.append',
     '        if False:\n            res.warnings.append'),
    ("dependencies: a rebuilt dependency not reported", "rc", "            elif live != build:", "            elif False:"),
    ("dependencies: a parent outside the chain not reported", "rc",
     "        if ext and ext not in [n.casefold() for n in names]:", "        " + OFF),
    # ---- the snapshot token
    ("token: loaded layers included", "rc", "for l in layers if l.role == ROLE_INDEXED):", "for l in layers):"),
    ("token: not sorted", "rc",
     "    for module, build in sorted((l.module, l.build_id) for l in layers if l.role == ROLE_INDEXED):",
     "    for module, build in ((l.module, l.build_id) for l in layers if l.role == ROLE_INDEXED):"),
    # ---- adaptation and sidecars
    ("adaptation: never required", "rc", '    if len(modules) <= 1:\n        a.status, a.current = "not required',
     '    if True:\n        a.status, a.current = "not required'),
    ("adaptation: another chain's profile accepted", "rc",
     "    if why or [n.casefold() for n in declared] != modules:", "    if why:"),
    ("adaptation: an uncheckable format accepted", "rc",
     "    if not isinstance(built, list) or not built or not all(", "    if False and not all("),
    ("adaptation: a stale profile accepted", "rc", '    if stale:\n        a.status = f"{rel} is STALE',
     '    if False:\n        a.status = f"{rel} is STALE'),
    ("authority: always current", "rc", "        return self.adaptation.current", "        return True"),
    ("sidecars: a missing one accepted", "rc",
     '            res.refusals.append(f"declared sidecar {s.path} does not exist; create it or remove it from the profile")',
     "            pass"),
    ("sidecars: a bare name resolved at the root", "rc",
     '        path = (campaign_dir / rel) if "/" not in rel else (Path(root) / rel)', "        path = Path(root) / rel"),
    # ---- the shared [rules_layers] parser and known modules
    ("rules_layers: an unknown not_searched accepted", "si", "        elif n not in known:", "        elif False:"),
    ("rules_layers: a repeated not_searched accepted", "si", "        if names.count(n) > 1:", "        " + OFF),
    ("rules_layers: not_searched case-sensitive", "si",
     '    names = [n.lower() for n in lists.get("not_searched", [])]', '    names = list(lists.get("not_searched", []))'),
    ("rules_layers: an empty not_searched accepted", "si",
     '    if "not_searched" in lists and not lists["not_searched"]:', "    " + OFF),
    ("rules_layers: a section declaring neither accepted", "si", "    if not lists and not problems:", "    " + OFF),
    ("known: a manifest naming another module accepted", "si",
     '            if data is None or (data.get("module") is not None and str(data.get("module")) != folder):',
     "            if data is None:"),
    ("known: private roots ignored", "si",
     "    claims, valid = {}, {}\n    for base in _layer_bases(root, private_roots):",
     "    claims, valid = {}, {}\n    for base in _layer_bases(root, ()):"),
    ("known: an ambiguous id resolved", "si",
     "    ambiguous = {i for i, dirs in claims.items() if len(dirs) > 1}", "    ambiguous = set()"),
    # ---- Codex 947 (1): module identity
    ("known: an index.cfg folder identified by its folder name", "si",
     '                declared = declared_module(d / "index.cfg")', "                declared = folder"),
    ("known: an index.cfg's folder-name claim ignored", "si",
     "                for i in {folder, declared} - {None}:", "                for i in {declared} - {None}:"),
    ("known: an indexable manifest not declaring its id accepted", "si",
     '                if data is not None and data.get("module") is not None and str(data.get("module")) == declared:',
     "                if data is not None:"),
    # ---- Codex 947 (2): adaptation coverage
    ("coverage: uncovered inputs accepted", "rc", "    if uncovered:\n        a.status", "    if False:\n        a.status"),
    ("coverage: sidecars left out", "rc", "    for s in res.sidecars:\n        required.append(",
     "    for s in []:\n        required.append("),
    ("coverage: layer manifests left out", "rc", "    for m in modules:\n        d = known.get(m)",
     "    for m in []:\n        d = known.get(m)"),
    ("coverage: the homebrew declaration not compared", "rc",
     "    if built_for != [_key(Path(root) / s.path) for s in res.sidecars]:", "    if False:"),
    ("coverage: the adaptation checked before the sidecars", "rc",
     "        _check_sidecars(root, res, profile_data.get(\"homebrew\"), campaign_dir)      # first: the adaptation covers them\n"
     "        _check_adaptation(root, res, profile_data.get(\"adaptation\"), modules, known)",
     "        _check_adaptation(root, res, profile_data.get(\"adaptation\"), modules, known)\n"
     "        _check_sidecars(root, res, profile_data.get(\"homebrew\"), campaign_dir)"),
    # ---- Codex 947 (3): path safety
    ("paths: an unsafe pin spelling followed", "rc", "        if _unsafe(sub.strip()):\n            return None",
     "        if False:\n            return None"),
    ("paths: a pin's containment not checked", "rc",
     "        return target if _within(root, target) else None", "        return target"),
    ("paths: unsafe pins tolerated", "rc", "    if unsafe:\n        a.status", "    if False:\n        a.status"),
    ("paths: the adaptation's containment not checked", "rc",
     '    if not _within(root, path):\n        a.status = f"{rel} resolves outside',
     '    if False:\n        a.status = f"{rel} resolves outside'),
    ("paths: a sidecar's containment not checked", "rc",
     '        if not _within(root, path):\n            res.refusals.append(f"sidecar {s.path} resolves outside',
     '        if False:\n            res.refusals.append(f"sidecar {s.path} resolves outside'),
    ("paths: a campaign's containment not checked", "rc", "        if not _within(root, hits[0]):", "        if False:"),
    ("paths: an unsafe adaptation homebrew accepted", "rc",
     "        target = target_of(str(item)) if isinstance(item, str) else None",
     "        target = (Path(root) / str(item)) if isinstance(item, str) else None"),
    # ---- Codex 947 (4): registry shape
    ("registry: entry shapes not checked", "rc",
     "    problems = {m: entry_problem(e) for m, e in reg[\"systems\"].items()}",
     "    problems = {m: None for m in reg[\"systems\"]}"),
    ("registry: a malformed chain layer consumed", "rc",
     "        if mid in malformed:                    # before any role",
     "        if False:                    # before any role"),
    # ---- Codex 949: discovery containment, and null entries
    ("registry: a malformed declared-loaded layer let through", "rc",
     "        if mid in malformed:                    # before any role",
     "        if mid in malformed and mid not in not_searched:                    # before any role"),
    ("registry: a null entry taken as absent", "rc", '        registered = mid in reg["systems"]',
     '        registered = reg["systems"].get(mid) is not None\n        malformed = malformed - {m for m, e in '
     'reg["systems"].items() if e is None}'),
    ("known: a discovery root's containment not checked", "si",
     "        if not base.is_dir() or not _inside(base, Path(root)):\n            continue\n        base_r = base.resolve()\n"
     "        for d in",
     "        if not base.is_dir():\n            continue\n        base_r = base.resolve()\n        for d in"),
    # ---- Codex 951: the builder's discovery and the shared loader
    ("discover: a discovery root's containment not checked", "si",
     "        if not base.is_dir() or not _inside(base, Path(root)):\n            continue\n        base_r = base.resolve()\n"
     "        found +=",
     "        if not base.is_dir():\n            continue\n        base_r = base.resolve()\n        found +="),
    ("discover: a module folder's containment not checked", "si",
     "                  if _inside(p.parent, base_r) and _inside(p, p.parent.resolve())]",
     "                  if _inside(p, p.parent.resolve())]"),
    ("discover: an index.cfg's containment not checked", "si",
     "                  if _inside(p.parent, base_r) and _inside(p, p.parent.resolve())]",
     "                  if _inside(p.parent, base_r)]"),
    ("load: an index.cfg leading out read", "si", "    if not _inside(cfg_path, cfg_path.parent):\n        raise",
     "    if False:\n        raise"),
    ("load: a relations.yaml leading out read", "si", "        if _inside(module_dir / RELATIONS_FILE, module_dir):",
     "        if True:"),
    ("load: a manifest leading out read", "si",
     '    elif module and not _inside(module_dir / f"{module}.md", module_dir):', "    elif False:"),
    ("known: a module folder's containment not checked", "si",
     "            if not d.is_dir() or not _inside(d, base_r):", "            if not d.is_dir():"),
    ("known: an index.cfg's containment not checked", "si",
     '                declared = declared_module(d / "index.cfg") if _inside(d / "index.cfg", where) else None',
     '                declared = declared_module(d / "index.cfg")'),
    ("known: an indexable manifest's containment not checked", "si",
     ' or not _inside(d / f"{declared}.md", where):', ":"),
    ("known: a legacy manifest's containment not checked", "si",
     '            if not SYSTEM_NAME.match(folder) or not _inside(d / f"{folder}.md", where):',
     "            if not SYSTEM_NAME.match(folder):"),
    ("freshness: the builder's discovery re-run", "rc", '        cfg_path = Path(module_dir) / "index.cfg"',
     '        cfg_path = system_index.find_cfg(root, layer.module, ()) or Path(module_dir) / "index.cfg"'),
    ("registry: a missing field accepted", "rc",
     '        if not isinstance(entry.get(key), str) or not entry.get(key):\n            return f"has no {key} string"',
     '        if False:\n            return f"has no {key} string"'),
    ("registry: a boolean schema_version accepted", "rc",
     "    if not isinstance(sv, int) or isinstance(sv, bool):", "    if not isinstance(sv, int):"),
    ("registry: a bad built_at accepted", "rc", '    if "built_at" in entry and not isinstance(entry["built_at"], str):',
     "    if False:"),
    ("registry: a non-mapping layer accepted", "rc",
     '        if not isinstance(layer, dict):\n            return "has a layer that is not a mapping"',
     '        if False:\n            return "has a layer that is not a mapping"'),
    ("registry: bad depends_on values accepted", "rc",
     "        if deps is not None and not (isinstance(deps, dict) and all(isinstance(k, str) and isinstance(v, str)",
     "        if deps is not None and not (isinstance(deps, dict) and all(isinstance(k, str) or isinstance(v, str)"),
    ("registry: a bad extends accepted", "rc",
     '        if layer.get("extends") is not None and not isinstance(layer.get("extends"), str):', "        if False:"),
    ("registry: a malformed dependency called unpublished", "rc", "            if dep in malformed:", "            if False:"),
    ("publication: a build id mismatch accepted", "si",
     '    if row is None or row[0] != entry.get("build_id") or row[1] != module:\n        return None, None, (f"its database does not match',
     '    if row is None:\n        return None, None, (f"its database does not match'),
    ("publication: a schema disagreement accepted", "si",
     '    if row[2] != entry.get("schema_version"):\n        return None, None, (f"the registry says schema',
     '    if False:\n        return None, None, (f"the registry says schema'),
    ("publication: an unsupported schema accepted", "si",
     '    if row[2] not in SUPPORTED_DEPENDENCY_SCHEMAS:\n        return None, None, (f"its schema',
     '    if False:\n        return None, None, (f"its schema'),
    # ---- the server
    ("server: two selectors accepted", "srv", "    if sum(x is not None for x in (system, campaign, chain)) > 1:",
     "    " + OFF),
    ("server: chain status not routed", "srv",
     "    if campaign is not None or chain is not None:\n        return _chain_status(campaign, chain)",
     "    if False:\n        return _chain_status(campaign, chain)"),
    ("server: an unreadable config taken as none", "srv",
     '        return f"[!] Chain refused — the corpus config {RULES_CFG_PATH.name} cannot be read: {e}"',
     "        rules_cfg = {}"),
    ("server: the refusal banner dropped", "srv", '    if res.refused:\n        lines += [f"[!] Chain refused',
     '    if False:\n        lines += [f"[!] Chain refused'),
    ("server: non-authoritative shown as current", "srv",
     '"[!] NON-AUTHORITATIVE — the chain\'s adaptation inputs are not current"', '"adaptation inputs current"'),
]

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

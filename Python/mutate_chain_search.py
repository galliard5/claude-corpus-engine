#!/usr/bin/env python3
"""
mutate_chain_search.py — In-memory mutation checks for chain search and version-checked fetches (chain-aware
search, stage 3).

Each mutant is one module's source (rules_chain.py, search_mcp_server.py or system_index.py) with one stage-3 guard disabled or
weakened, executed into that module's own namespace; then test_chain_search, test_chain and test_layers run, and the
mutant is covered when at least one test fails or errors. The original source is re-executed after every mutant. No
file is edited; the tests use temporary directories only.

Usage:
    python mutate_chain_search.py [--no-pause]

Command line arguments:
    --no-pause   Skip end-of-run pause

# changed 2026-11-12: created (chain-aware search stage 3, Codex 955).
# changed 2026-11-12: Codex 957 — mutants for containment at the open, declaration validation and canonical unit
#   identity; the two open-path mutants repointed at the new open.
# changed 2026-11-13: Codex 959 — mutants for containment at get_section's and get_system_record's own open.
# changed 2026-11-13: Codex 961 — system_index is a mutation target too; mutants for containment at the remaining
#   module opens (_resolve_system, single-system search, check_publication); the two at-open rule mutants follow
#   the rule into system_index.contained_real.
# changed 2026-11-14: audit batch 1 — mutants for undecodable inputs, immutable generation opens, the connection
#   closed when its extension fails, and the chain-path catch-all; two open mutants repointed at the new opens.
# changed 2026-11-15: audit batch 3 — mutants for the chain-order warning, layer tables checked at resolution (and
#   only through the contained open), and the resolution header on both post-resolution refusals.
# changed 2026-11-15: six mutants for audit batch 4 (C2): the word fallback for a vector query on a layer with no
#   vector table: off, unguarded, applied to hybrid, unquoted, keeping one-letter words, and repeating words.
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

MODULES = {"rc": rules_chain, "srv": search_mcp_server, "si": system_index}
SOURCES = {k: Path(m.__file__).read_text(encoding="utf-8") for k, m in MODULES.items()}
TESTS = ["test_chain_search", "test_chain", "test_layers"]
OFF = "if False:"
EXTRA = "        extra = min(max(min(c, per_layer) - 1, 0), left)"

MUTANTS = [
    # ---- allocation (refinement A, per_layer and limit)
    ("allocate: no refusal below the matching layers", "rc",
     "    if limit < matching:\n        return None, matching", "    if False:\n        return None, matching"),
    ("allocate: per_layer ignored", "rc", EXTRA, "        extra = min(max(c - 1, 0), left)"),
    ("allocate: limit ignored", "rc", EXTRA, "        extra = max(min(c, per_layer) - 1, 0)"),
    ("allocate: no coverage slot", "rc", "    slots = [1 if c > 0 else 0 for c in counts]",
     "    slots = [0 for c in counts]"),
    ("allocate: extras least specific first", "rc", "    for i, c in enumerate(counts):\n        extra",
     "    for i, c in reversed(list(enumerate(counts))):\n        extra"),
    # ---- relations: scoping, reading, status
    ("scope: target outside the chain counted in", "rc",
     "    inside = [d for d in declarations if d.layer in chain_modules and d.target_layer in chain_modules]",
     "    inside = list(declarations)"),
    ("read: depends_on ignored", "rc", 'r[8] or "", r[9] or "", r[10] or "", str(deps.get(r[3]) or ""))',
     'r[8] or "", r[9] or "", r[10] or "", "")'),
    ("read: a layer_info of the wrong size accepted", "rc", "        if len(info) != 1:", "        " + OFF),
    ("read: a non-mapping depends_on accepted", "rc", "        if not isinstance(deps, dict):",
     "        if False and not isinstance(deps, dict):"),
    ("read: a malformed section accepted", "rc",
     '    if not isinstance(data, dict) or not isinstance(data.get("heading"), str) or not isinstance(data.get("level"), int):',
     "    if False:"),
    ("assess: the status dropped", "rc", "    words = [d.status]", "    words = []"),
    ("assess: an orphan not reported", "rc", '        if why:\n            words.append(f"[!] ORPHANED',
     '        if False:\n            words.append(f"[!] ORPHANED'),
    ("assess: an unpinned target taken as checked", "rc", "        elif not d.declared_sha256:",
     "        elif False:"),
    ("assess: a changed target shown unchanged", "rc", "        elif d.declared_sha256 != now:",
     "        elif False:"),
    ("assess: an older build not reported", "rc",
     "    if live and d.validated_build and d.validated_build != live:", "    " + OFF),
    ("assess: self-declared shown as decided", "rc", 'words.append(f"self-declared{who}{when} in',
     'words.append(f"decided{who}{when} in'),
    ("wording: extend worded as override", "rc", '    "extend": "declared: extended by {layer}",',
     '    "extend": "declared override by {layer}",'),
    # ---- relation lines on a hit
    ("lines: no-override shown despite declarations", "rc",
     "    if not naming:\n        lines.append(NO_OVERRIDE)", "    if True:\n        lines.append(NO_OVERRIDE)"),
    ("lines: matched by key, not layer and key", "rc",
     "    naming = [d for d in inside if d.target_layer == hit_layer and d.target_key == hit_key]",
     "    naming = [d for d in inside if d.target_key == hit_key]"),
    ("lines: several declarations not flagged", "rc", "        if len(group) > 1:", "        " + OFF),
    ("lines: a conflict not called one", "rc", 'override(s); search does not reconcile them)" if overrides else',
     'override(s); search does not reconcile them)" if False else'),
    ("lines: the cap ignored", "rc", "            if shown < MAX_RELATION_LINES:", "            if True:"),
    ("lines: the overflow not counted", "rc", "    if shown > MAX_RELATION_LINES:", "    " + OFF),
    ("lines: an undeclared higher layer not noted", "rc", "    if undeclared:", "    " + OFF),
    ("declares: matched by key, not layer and key", "rc",
     "    own = [d for d in inside if d.layer == hit_layer and d.entry_key == hit_key]",
     "    own = [d for d in inside if d.entry_key == hit_key]"),
    ("declares: the cap ignored", "rc", "    for d in own[:MAX_RELATION_LINES]:", "    for d in own:"),
    # ---- the chain search
    ("search: a refused chain searched", "srv",
     '    if res.refused:\n        return "\\n".join([f"No search was run',
     '    if False:\n        return "\\n".join([f"No search was run'),
    ("search: a declared-loaded layer searched", "srv",
     "    searched = [l for l in res.layers if l.role == rules_chain.ROLE_INDEXED]",
     "    searched = [l for l in res.layers if l.role != rules_chain.ROLE_MISSING]"),
    ("search: least specific first", "srv", "    order = list(reversed(searched))", "    order = list(searched)"),
    ("search: snapshot build not checked", "srv",
     '            if row is None or (row["build_id"], row["module"], row["schema_version"]) != (l.build_id, l.module,',
     '            if row is None or False and (row["build_id"], row["module"], row["schema_version"]) != '
     '(l.build_id, l.module,'),
    ("search: an unreadable snapshot database not refused", "srv",
     '                    row, why = None, f"it can no longer be opened ({e})"', "                    raise"),
    ("search: switches to the registry's current generation", "srv",
     '_open_readonly(load_vectors=mode != "fts", db_path=real, generation=True)',
     '_open_readonly(load_vectors=mode != "fts", db_path=system_index.resolve_db('
     'SYSTEMS_DIR, l.module, system_index.read_registry(SYSTEMS_DIR)["systems"][l.module]), generation=True)'),
    # ---- Codex 957: containment at the open, declarations validated, canonical unit identity
    ("open: containment not checked at the open", "si", "    if not _inside(real, Path(sdir)):",   # 961: the rule
     "    " + OFF),                                                                        # moved to contained_real
    ("open: links not followed at the open", "si", "        real = Path(path).resolve(strict=True)",
     "        real = Path(path).absolute()\n        Path(path).stat()"),
    ("open: not re-checked once open", "srv", "                    if _snapshot_generation(l.db)[0] != real:",
     "                    " + OFF),
    ("declarations: not validated", "rc", "        for d in out:                     # validated BEFORE",
     "        for d in []:                     # validated BEFORE"),
    ("declarations: mode not checked", "rc", "    if d.mode not in system_index.RELATION_MODES:", "    " + OFF),
    ("declarations: status not checked", "rc", "    if d.status not in system_index.RELATION_STATUSES:", "    " + OFF),
    ("declarations: item not checked", "rc", "    if isinstance(d.item, bool) or not isinstance(d.item, int):",
     "    " + OFF),
    ("declarations: keys not checked", "rc",
     "        if not isinstance(value, str) or not system_index.ENTRY_KEY.match(value):", "        " + OFF),
    ("declarations: target layer not checked", "rc",
     "    if not isinstance(d.target_layer, str) or not system_index.SYSTEM_NAME.match(d.target_layer):",
     "    " + OFF),
    ("declarations: decided not checked", "rc",
     "    if not isinstance(d.decided, str) or (d.decided and not system_index.DATE.match(d.decided)):",
     "    " + OFF),
    ("declarations: the pin not checked", "rc",
     "    if not isinstance(d.declared_sha256, str) or (d.declared_sha256 and not system_index.HEX64.match(d.declared_sha256)):",
     "    " + OFF),
    ("declarations: a record section accepted", "rc", '        if section is not None and key.startswith("rec:"):',
     "        " + OFF),
    ("declarations: a section level or heading not checked", "rc",
     '    if isinstance(data["level"], bool) or not 1 <= data["level"] <= 6 or not system_index.norm_heading(data["heading"]):',
     "    " + OFF),
    ("declarations: non-string dependency builds accepted", "rc",
     "        if not all(isinstance(k, str) and isinstance(v, str) for k, v in deps.items()):", "        " + OFF),
    ("identity: headings not normalised", "rc",
     "    return layer, key, (None if section is None else (system_index.norm_heading(section[0]), section[1]))",
     "    return layer, key, section"),
    ("identity: level ignored", "rc", "(system_index.norm_heading(section[0]), section[1]))",
     "(system_index.norm_heading(section[0]),))"),
    # ---- Codex 959: containment at the fetch tools' own open
    ("fetch open: section opens the module unchecked", "srv",
     "            conn, open_err = _open_module(db_path, system)\n            if open_err:",
     "            conn, open_err = _open_readonly(db_path=db_path), None\n            if open_err:"),
    ("fetch open: record opens the module unchecked", "srv",
     "        conn, open_err = _open_module(db_path, system)      # containment enforced at the open itself",
     "        conn, open_err = _open_readonly(db_path=db_path), None"),
    ("fetch open: an escaped path not refused", "srv",
     '    if real is None:\n        state = f" (index_status',          # 961: repointed, same mutation
     '    if False:\n        state = f" (index_status'),
    ("fetch open: not re-checked once open", "srv",
     "    if _snapshot_generation(db_path)[0] != real:\n        conn.close()",
     "    if False:\n        conn.close()"),
    ("fetch open: the corpus routed through the module check", "srv",
     "        if system:                                          # a module: containment enforced at the open itself",
     "        if True:"),
    # ---- Codex 961: containment at the remaining module opens
    ("remaining open: _resolve_system reads db_info unchecked", "srv",
     '        conn, refused = _open_module(db, name, verb="try")      # containment enforced at the open itself',
     "        conn, refused = _open_readonly(db_path=db), None"),
    ("remaining open: single-system search opens unchecked", "srv",
     "        if system:                          # a module: containment enforced at the open itself",
     "        if False:"),
    ("remaining open: the vector flag dropped at the module open", "srv",
     '_open_module(db_path, system, load_vectors=needs_vectors, verb="search")',
     '_open_module(db_path, system, verb="search")'),
    ("publication: opened unchecked", "si",
     '        conn, why = open_contained(path, sdir, lambda real: sqlite3.connect(generation_uri(real), uri=True))',
     '        conn, why = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True), None'),
    ("publication: not re-checked once open", "si",
     "    if contained_real(path, sdir)[0] != real:\n        conn.close()",
     "    if False:\n        conn.close()"),
    ("identity: grouped by the raw section", "rc",
     "        units.setdefault(unit_identity(d.target_layer, d.target_key, d.target_section), []).append(d)",
     "        units.setdefault(d.target_section, []).append(d)"),
    ("search: the guard not installed", "srv", "            conn.set_progress_handler(guard, _PROGRESS_STEPS)",
     "            pass"),
    ("search: a timeout reported as broken tables", "srv",
     "        # that the deadline aborts is a timeout, never a \"broken\" database.\n        if guard.fired:",
     "        # that the deadline aborts is a timeout, never a \"broken\" database.\n        if False:"),
    ("search: relations read from schema 2", "srv",
     "            if l.schema == system_index.SCHEMA_LAYERED:\n                declarations +=",
     "            if True:\n                declarations +="),
    ("search: no per-layer vector fallback", "srv",
     '            if lane_mode != "fts" and not _has_vector_table(conn):', "            " + OFF),
    ("search: no look-ahead for 'more matched'", "srv", "*lane_filters, per_layer + 1)[0]", "*lane_filters, per_layer)[0]"),
    ("search: refinement A not refused", "srv",
     '        if slots is None:\n            return "\\n".join([f"No results were returned',
     '        if False:\n            return "\\n".join([f"No results were returned'),
    ("search: per_layer default not capped by limit", "srv", "        per_layer = min(5, limit)",
     "        per_layer = 5"),
    ("search: per_layer not validated", "srv",
     "    if isinstance(per_layer, bool) or not isinstance(per_layer, int) or per_layer < 1:", "    " + OFF),
    ("search: per_layer ceiling not enforced", "srv", "    if per_layer > _MAX_LIMIT:", "    " + OFF),
    ("search: two selectors accepted", "srv",
     "    if sum(x is not None for x in (campaign, chain)) + bool(system) > 1:", "    " + OFF),
    ("search: per_layer accepted without a chain", "srv",
     '    if per_layer is not None:\n        return "[!] per_layer needs', '    if False:\n        return "[!] per_layer needs'),
    ("search: Declares lines dropped", "srv", '                lines += [f"   Declares: {x}"',
     '                lines += [] and [f"   Declares: {x}"'),
    ("search: the sidecar note dropped", "srv",
     '        if res.sidecars:\n            lines.append("  Sidecars:   declared loaded and not searched',
     '        if False:\n            lines.append("  Sidecars:   declared loaded and not searched'),
    ("search: a changed layer not flagged on its group", "srv",
     '            if l.freshness == "CHANGED":\n                lines.append("   [!] SOURCES CHANGED since this build',
     '            if False:\n                lines.append("   [!] SOURCES CHANGED since this build'),
    # ---- fetches: expected_build and schemas
    ("fetch: section ignores expected_build", "srv",
     "        if expected_build is not None:\n            err = _expected_build_error(system, _entry, expected_build)",
     "        if False:\n            err = _expected_build_error(system, _entry, expected_build)"),
    ("fetch: record ignores expected_build", "srv",
     "    if expected_build is not None:\n        err = _expected_build_error(system, _entry, expected_build)",
     "    if False:\n        err = _expected_build_error(system, _entry, expected_build)"),
    ("fetch: a superseded build accepted", "srv", '    if entry.get("build_id") != want:', "    " + OFF),
    ("fetch: a malformed build id accepted", "srv", "    if not _BUILD_ID.match(want):", "    " + OFF),
    ("fetch: section connection not checked", "srv",
     "                return build_err\n        row = conn.execute(", "                pass\n        row = conn.execute("),
    ("fetch: record connection not checked", "srv",
     "                return build_err\n        if by_key:", "                pass\n        if by_key:"),
    ("fetch: the connection check always passes", "srv",
     "    if row is None or row[0] != expected_build.strip():", "    " + OFF),
    ("fetch: expected_build accepted without a system", "srv",
     '    if expected_build is not None and not system:\n        return "[!] expected_build needs a system',
     '    if False:\n        return "[!] expected_build needs a system'),
    ("fetch: section refuses schema 3", "srv",
     "(system, system_index.SUPPORTED_DEPENDENCY_SCHEMAS)\n        if err:", "(system)\n        if err:"),
    ("fetch: record refuses schema 3", "srv",
     "(system, system_index.SUPPORTED_DEPENDENCY_SCHEMAS)\n    if err:", "(system)\n    if err:"),
    ("system: single search reads schema 3", "srv", '    if row["schema_version"] not in schemas:',
     "    " + OFF),
    # ---- audit batch 1 (Working_Documents/Chain_Search_Audit_Fable.md X1, C3, N2)
    ("decode: an undecodable manifest raises", "si",
     "    except (OSError, UnicodeDecodeError):\n        return None\n    m = MANIFEST_FENCE",
     "    except OSError:\n        return None\n    m = MANIFEST_FENCE"),
    ("decode: declared_module decodes strictly", "si",
     '        text = Path(cfg_path).read_text(encoding="utf-8", errors="replace")',
     '        text = Path(cfg_path).read_text(encoding="utf-8")'),
    ("decode: an undecodable index.cfg not refused", "si",
     '    except UnicodeDecodeError as e:\n        raise SystemIndexError(f"{where} is not valid UTF-8',
     '    except ImportError as e:\n        raise SystemIndexError(f"{where} is not valid UTF-8'),
    ("open: a generation opened without immutable", "si", '?mode=ro&immutable=1"', '?mode=ro"'),
    ("open: a generation opened as the corpus is", "srv",
     '    uri = system_index.generation_uri(path) if generation else', '    uri = f"{path.as_uri()}?mode=ro" if 1 else'),
    ("open: a connection leaked when its extension fails", "srv",
     "    except BaseException:\n        conn.close()\n        raise", "    except BaseException:\n        raise"),
    # ---- status agrees with search (audit batch 3: C1, and the reference's two promises)
    ("order: no warning for a chain against its extends", "rc",
     "    res.warnings += _order_warnings(res.layers, published)", "    pass"),
    ("order: relation dependencies ignored", "rc",
     '        deps = set(info["depends_on"]) if isinstance(info.get("depends_on"), dict) else set()',
     "        deps = set()"),
    ("order: the direction reversed", "rc", "            if d in pos and pos[d] > pos[mid]:",
     "            if d in pos and pos[d] < pos[mid]:"),
    ("resolve: layer tables not checked", "rc",
     "        if layer.schema == system_index.SCHEMA_LAYERED:\n            why = _layer_tables_problem",
     "        if False:\n            why = _layer_tables_problem"),
    ("resolve: layer tables opened uncontained", "rc",
     "    conn, why = system_index.open_contained(Path(db), sdir,",
     "    conn, why = (lambda p, s, o: (o(Path(p)), None))(Path(db), sdir,"),
    ("search: a post-resolution refusal without the header", "srv",
     'search again (index_status shows the new build).",\n                                  ""] + head)',
     'search again (index_status shows the new build)."])'),
    ("search: a late layer-table refusal without the header", "srv",
     'f"[!] Chain search refused — {e}", ""] + head)', 'f"[!] Chain search refused — {e}"])'),
    ("search: no catch-all on the chain path", "srv",
     '        return f"[!] Unexpected error: {e}"\n    finally:\n        for c in conns.values():',
     '        raise\n    finally:\n        for c in conns.values():'),
    # ---- audit batch 4 (C2): a vector query on a layer with no vector table
    ('fallback: the layer given the query as written', 'srv',
     '                    lane_filters = _filters(words, category_filter, type_filter, missing_filter, reps)',
     '                    pass'),
    ('fallback: a query with no words searched anyway', 'srv',
     '                    if not words:',
     '                    if False:'),
    ('fallback: hybrid rewritten too', 'srv',
     '                if mode == "vector":',
     '                if True:'),
    ('fallback: words unquoted', 'srv',
     '    return " OR ".join(f\'"{w}"\' for w in words)',
     '    return " OR ".join(words)'),
    ('fallback: one-letter words kept', 'srv',
     'for w in re.findall(r"\\w+", query or "") if len(w) > 1)',
     'for w in re.findall(r"\\w+", query or "") if len(w) > 0)'),
    ('fallback: words repeated', 'srv',
     '    words = dict.fromkeys(w.casefold() for w in',
     '    words = list(w.casefold() for w in'),
]

EQUIVALENT: dict = {
    # system_index._inside resolves the path itself (links and junctions followed), so the containment check refuses
    # an escaping link whether or not contained_real resolved it first; a link that stays inside index/systems
    # is opened either way and refused by the db_info build check. No observable difference exists to test.
    "open: links not followed at the open": "_inside resolves the path itself",
}


def run() -> tuple:
    suite = unittest.defaultTestLoader.loadTestsFromNames(TESTS)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return result.testsRun, len(result.failures) + len(result.errors)


def main() -> int:
    t0 = time.time()
    sys.stdout.reconfigure(encoding="utf-8")
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = io.StringIO()
    out, sys.stdout = sys.stdout, quiet
    try:
        n, bad = run()
    finally:
        sys.stdout = out
    print(f"baseline: {n} tests, {bad} failing ({'clean' if not bad else 'BROKEN'})")
    if bad:
        return 1
    for name, key, old, new in MUTANTS:
        assert SOURCES[key].count(old) == 1, (name, SOURCES[key].count(old))
    chosen = [m for m in MUTANTS if not only or any(o in m[0] for o in only)]
    survivors = n_eq = 0
    for name, key, old, new in chosen:
        src = SOURCES[key]
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
    print(f"{len(chosen) - survivors - n_eq} of {len(chosen) - n_eq} killed, {n_eq} equivalent, {survivors} "
          f"survived; Runtime: {time.time() - t0:.2f}s")
    if "--no-pause" not in sys.argv:
        input("Press Enter to exit...")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())

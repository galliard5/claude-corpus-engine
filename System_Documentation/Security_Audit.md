---
name: Security Audit Reference
type: documentation-reference
keywords: [security, audit, python, danger_keywords, sql_injection, walkthrough, claude_authored]
description: Audit habits for Claude-authored Python scripts and the verified-clean walkthrough history.
---

# Security Audit Reference

The Python scripts in `/corpus/Python/` were Claude-authored. Trust in them is built through audit, not assumed. This file documents the audit habits and the walkthrough history of the corpus-search subsystem.

## Audit habits

### Before every Python script edit

Claude should explain in plain language:
- What changed and why
- Any new imports
- Any new file operations
- Any new external calls (HTTP, subprocess, etc.)

The human reviewer then runs the danger-keyword check below before approving.

### Danger keyword check

Ctrl+F any Python file for these terms. Each one is a flag worth a question — not necessarily a problem, but never silently introduced:

| Term         | What it does                                          | Acceptable when                                |
|--------------|-------------------------------------------------------|------------------------------------------------|
| `os.system`  | Shell command execution                               | Should not appear. Use `subprocess.run` instead. |
| `subprocess` | Launches external programs                             | Acceptable for known scripts (e.g. running `build_indexes.py` from the index-tools server). Question any subprocess call where the command string is built from user input. |
| `eval`       | Executes arbitrary Python from a string               | Should not appear.                              |
| `exec`       | Same                                                  | Should not appear.                              |
| `urllib`     | HTTP requests                                         | Should not appear in indexer/search scripts.   |
| `requests`   | Same                                                  | Same.                                          |
| `socket`     | Raw network                                           | Should not appear.                              |
| `http`       | HTTP libraries                                        | Should not appear.                              |
| `open(`      | File opens                                            | Acceptable. Check the path comes from a known constant or a relative path under the corpus root — never from raw user input. |
| `yaml.load`  | Deserializes YAML (full constructor — can execute code) | Should not appear. Use `yaml.safe_load`.       |

Verifying these all return zero matches (or only return matches in expected, understood places) is a meaningful security check without needing to read every line.

### Git diff before rebuild

```cmd
cd D:\claude\filesystem
git diff Python/
```

After any Claude-authored Python edit, visual-check the diff before the next rebuild. Catches accidental scope creep early.

## Walkthrough history

### `build_search_index.py` (deprecated, replaced by `build_indexes.py`)

Original audit conducted before the unified `build_indexes.py` existed. Findings — all of which carried forward into the replacement:

**Filesystem operations** — All paths traced back to `ROOT` or `DB_PATH` constants at the top of the file. No path construction from user input.

**No network, no shell, no subprocess.** Verified by danger-keyword search — zero matches across the full keyword list.

**External dependencies** — `pyyaml` only, via `yaml.safe_load`. The safe constructor.

**Defensive patterns observed:**
- `try/except` around every file read
- Cascading encoding fallbacks (UTF-8 → latin-1 → log and skip)
- Type coercion before joining keywords
- Empty-string defaults for missing metadata
- Parameterized SQL queries (`?` placeholders) — no string concatenation
- Outermost try/except prevents uncaught exceptions from crashing the run
- Per-file errors logged with path, never crash the whole run

**Key design choices:**
- FTS5 table dropped and rebuilt from scratch each run. No incremental logic — simpler and faster at corpus size.
- `path UNINDEXED` so folder names don't drown content matches.
- `category` IS indexed for location-aware search.
- Functions return safe defaults rather than crashing on bad input.

**Audit confidence:** informed trust, not formal audit. Sufficient to notice if future edits change the security shape.

### Improvements carried into `build_indexes.py`

The audit identified several planned improvements. All shipped in `build_indexes.py`:

- **`os.walk` with subtree pruning** instead of `rglob` + post-filter. Excluded subtrees are never descended into.
- **Both directory pruning AND extension filter** present — defense in depth. Either alone is one bad edit away from problems; both means a bug in one is caught by the other.
- **`--no-pause` flag** for unattended subprocess runs. Lets the MCP server invoke the script without a hung input prompt.

### `search_mcp_server.py`

Audit findings:

- **Read-only DB.** SQLite opened via URI mode `?mode=ro`. Cannot write.
- **No path arguments.** DB path is hardcoded. No SQL passthrough.
- **Parameterized SQL throughout.** All user input via `?` placeholders.
- **`missing_filter` whitelist.** Rejected at the server boundary before touching SQL — only `{"name", "keywords", "description", "type"}` accepted.
- **Quote escaping in `_wrap_query`.** Embedded `"` in user input is doubled before reaching FTS5.
- **No imports for network, shell, or arbitrary execution.** Just `sqlite3`, `os`, `datetime`, `pathlib`, `mcp.server.fastmcp`.

The only attack surface is the FTS5 MATCH expression itself, which is constrained by SQLite's FTS5 grammar. Worst case: a malformed query returns a "FTS5 syntax error" — handled gracefully.

### `index_tools_mcp_server.py`

Audit findings:

- **No path arguments exposed.** All paths hardcoded.
- **`load` parameter whitelisted** against `{None, "directory", "with_files", "search_status"}`. Any other value rejected before any work begins.
- **Subprocess invocation is fixed.** Command is `[sys.executable, str(BUILDER), "--no-pause"]` — no shell, no string interpolation, no user input.
- **`stdin=subprocess.DEVNULL`** belt-and-braces guard against any rogue `input()` call hanging the subprocess.
- **30-second timeout** on the subprocess. Bounded blast radius if the rebuild ever hangs.

### `cfg_loader.py`

Audit findings:

- **No file writes.** Read-only parser.
- **No subprocess or network.**
- **Malformed input is logged and skipped**, not raised. A typo in the cfg doesn't abort the run; the human sees the warning at the bottom of the rebuild summary.
- **`FileNotFoundError` is the one exception that always propagates** — there is no meaningful default when the cfg itself is missing.

## Audit ritual checklist

For future Claude-authored Python edits:

1. ☐ Claude has explained what changed and why in plain language
2. ☐ Danger-keyword grep run on every file touched — no new matches outside expected lines
3. ☐ `git diff Python/` reviewed visually
4. ☐ If new imports introduced, each one understood and accepted
5. ☐ If new file operations introduced, each path traceable to a known constant
6. ☐ Test rebuild run, results verified against a known query
7. ☐ Commit

## Defer-until-distribution items

These are not active concerns for the current single-user, single-machine setup, but flagged for the day the framework gets distributed:

- **Genericize for distribution** — sample corpus skeleton, docker-compose for a fresh install, cross-platform path handling, README for non-technical users.
- **Phase 1 containerization scope** — the custom Python servers (already done via `Python/Dockerfile`). Phase 2 would containerize the official filesystem and memory MCPs as well; lower priority since upstream code is already trusted.
- **Threat model expansion** — current model is "single user on personal machine running own scripts." A distributed framework would need to model "third-party operator running upstream scripts," which would invite more rigorous review (path canonicalization, env-var sanitization, audit logging).

Estimated effort: afternoon for distribution genericization; weekend for a polished public-release package.

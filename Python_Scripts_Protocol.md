---
name: Python_Scripts_Protocol
type: rules-reference
keywords: [python, scripts, protocol, conventions, cli, rules]
description: Terse rules for running and writing Python scripts across the corpus-infra and corpus-tools repos.
---

> **Last edited (UTC):** 2026-09-04T04:30:00Z

**Authoritative rules for Python scripts.** For reasoning, examples, and extended guidance, see `System_Documentation/Python_Scripts.md`.

---

## WHERE SCRIPTS LIVE

Since the 2026-06-12 repo split, scripts live in **two places**:

| Location | Repo | Visible to chat-claude? | Contents |
|---|---|---|---|
| `D:\claude\filesystem\Python\` | `corpus-infra` | Yes, as `/corpus/Python/` | Index builder + MCP servers: `build_indexes.py`, `search_mcp_server.py`, `series_search_mcp_server.py`, `index_tools_mcp_server.py`, `cfg_loader.py`, `embedding.py`, `check_schema_drift.py` |
| `D:\Claude\projects\corpus-tools\` | `corpus-tools` | **No** | Maintenance and conversion scripts: `validate_naming.py`, `cleanup_legacy_tags.py`, `convert_to_markdown.py`, `process_session_summary.py`, `run_in_sandbox.py` |

The map converter, series/PDF pipelines, and bgm server also moved to their own repos under
`D:\Claude\projects\`. Anything under `projects\` is a Claude Code (dev-side) concern —
chat-claude cannot see or run it, so ask the user or hand off to code-claude.

---

## RUNNING SCRIPTS

- Run a `corpus-infra` script from CMD: `cd D:\claude\filesystem\Python && python script_name.py [options]`
- Run a `corpus-tools` script by full path, e.g.
  `python D:\Claude\projects\corpus-tools\validate_naming.py --root "D:\Claude\filesystem\World_Building"`
  (resolves the corpus via the `CORPUS_ROOT` env var, fallback `D:\Claude\filesystem`)
- Use `python` not `python3` in all CMD calls and `.bat` files
- Last verified Python version: 3.14.3
- Each script has header comments describing what it does, its arguments, and its category — **read the header before running an unfamiliar script**

---

## SCRIPT CATEGORIES

**Modification scripts** — write to or rename corpus files. All currently live in `projects\corpus-tools\` (e.g. `validate_naming.py`, `cleanup_legacy_tags.py`, `convert_to_markdown.py`, `process_session_summary.py`):
- Must be called with `--dry-run` first to preview changes
- Will prompt for confirmation before applying any modification
- Never run without reviewing the dry-run output first

**Rebuild / read-only scripts** — generate derived artifacts, never modify corpus files. These live in `Python/` (`corpus-infra`), e.g. `build_indexes.py`:
- Safe to run freely; no corpus side-effects
- Support `--no-pause` for unattended/automated execution
- Preferred invocation: `index-tools:rebuild_indexes` (in-session) or `refresh_indexes.bat` (manual)

---

## REQUIRED HEADER FORMAT (.py files)

Every script must open with:
```python
# name: Script Name
# keywords: [keyword1, keyword2]
# description: What this script does
#
# Human-readable top-level description
#
# Command line arguments:
#   --dry-run: Preview without executing (modification scripts only)
#   --no-pause: Skip end-of-run pause (rebuild scripts only)
```

---

## WRITING NEW SCRIPTS

Before writing a new script:
1. Check both script locations — the utility may already exist. `Python/` is visible to chat-claude; `projects\corpus-tools\` must be checked by the user or code-claude.
2. Determine category (modification vs rebuild) — this governs whether `--dry-run` is required
3. Write the header block first
4. For modification scripts: implement `--dry-run`, preview output, and confirmation prompt before any write

Full conventions and rationale: `System_Documentation/Python_Scripts.md`

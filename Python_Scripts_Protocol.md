---
name: Python_Scripts_Protocol
type: rules-reference
keywords: [python, scripts, protocol, conventions, cli, rules]
description: Terse rules for running and writing Python scripts, both the ones shipped in Python/ and corpus-maintenance scripts kept outside the repository.
---

> **Last edited (UTC):** 2026-09-05T02:44:00Z

**Authoritative rules for Python scripts.** For reasoning, examples, and extended guidance, see `System_Documentation/Python_Scripts.md`.

---

## WHERE SCRIPTS LIVE

Scripts live in **two places**, and only the first ships with this repository:

| Location | Ships here? | Visible to chat-claude? | Contents |
|---|---|---|---|
| `Python/` (`D:\claude\filesystem\Python\`) | **Yes** | Yes, as `/corpus/Python/` | Index builder + MCP servers: `build_indexes.py`, `search_mcp_server.py`, `series_search_mcp_server.py`, `index_tools_mcp_server.py`, `cfg_loader.py`, `embedding.py`, `check_schema_drift.py` |
| A maintenance-scripts directory outside the corpus | **No** | **No** | Corpus maintenance and conversion: naming validation, session-summary processing, sandbox runners, and any content pipelines |

> **The second row is not part of this repository.** These are the author's own maintenance
> scripts, kept outside the corpus because they modify it and because they are specific to one
> deployment. A fresh clone has only `Python/`. Nothing in the engine depends on the second
> location — the rules below describe the conventions those scripts follow, so that anything you
> write for your own corpus follows the same discipline.

On the authoring machine that directory is `D:\Claude\projects\corpus-tools\`, alongside sibling
repos for the map converter, the series and PDF pipelines, and the BGM server. Anything there is a
Claude Code (dev-side) concern — chat-claude cannot see or run it, so ask the user or hand off to
code-claude.

---

## RUNNING SCRIPTS

- Run a shipped script from CMD: `cd D:\claude\filesystem\Python && python script_name.py [options]`
- Run a maintenance script by full path, e.g.
  `python <maintenance-scripts>\validate_naming.py --root "D:\Claude\filesystem\World_Building"`
  (resolves the corpus via the `CORPUS_ROOT` env var, fallback `D:\Claude\filesystem`)
- Use `python` not `python3` in all CMD calls and `.bat` files
- Last verified Python version: 3.14.3
- Each script has header comments describing what it does, its arguments, and its category — **read the header before running an unfamiliar script**

---

## SCRIPT CATEGORIES

**Modification scripts** — write to or rename corpus files. None ship here; they live in the maintenance directory. The rules still apply to any you write:
- Must be called with `--dry-run` first to preview changes
- Will prompt for confirmation before applying any modification
- Never run without reviewing the dry-run output first

**Rebuild / read-only scripts** — generate derived artifacts, never modify corpus files. These ship in `Python/`, e.g. `build_indexes.py`:
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
1. Check both script locations — the utility may already exist. `Python/` is visible to chat-claude; the maintenance directory must be checked by the user or code-claude.
2. Determine category (modification vs rebuild) — this governs whether `--dry-run` is required
3. Write the header block first
4. For modification scripts: implement `--dry-run`, preview output, and confirmation prompt before any write

Full conventions and rationale: `System_Documentation/Python_Scripts.md`

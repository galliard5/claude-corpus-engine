---
name: Python_Scripts
type: rules-reference
keywords: [python, scripts, conventions, protocol, documentation, rationale]
description: Full conventions, rationale, and patterns for Python scripts in the Python/ directory.
---

This is the verbose companion to `Python_Scripts_Protocol.md`. Where the protocol file gives rules, this file explains why they exist and how to apply them well.

---

## ENVIRONMENT

- **Python version:** 3.14.3 (last verified). Scripts should not rely on version-specific behaviour below 3.10.
- **Script location (since the 2026-06-12 repo split):** the index builder and MCP servers stay in **corpus-infra** at `D:\Claude\filesystem\Python\`; the maintenance/conversion scripts moved to their own repos under `D:\Claude\projects\` (corpus-tools, series-pipeline, pdf-tools, worldographer, bgm).
- **Invocation:** Always use `python`, not `python3`, in CMD calls and `.bat` files. The Windows PATH on this machine resolves `python` to the correct interpreter; `python3` may not resolve at all.
- **Working directory & corpus paths:** Each script runs from its own repo dir. Scripts that live *outside* the corpus resolve corpus paths via the `CORPUS_ROOT` env var (absolute fallback `D:\Claude\filesystem`), matching the MCP servers — **not** via `..`.

---

## SCRIPT CATEGORIES IN DETAIL

The two-category system exists because the risk profile of the two categories is fundamentally different.

### Modification scripts

These write to, rename, or otherwise change corpus files. A bug or misapplication can corrupt lore files that took hours to write. The conventions below exist to make that outcome essentially impossible through accidental use.

**Required behaviours:**
- `--dry-run` flag — runs the full logic but writes nothing. Output must clearly list every file that *would* be changed and what the change would be. Should be idiomatic enough that Claude can call `--dry-run` to orient on what a script does without needing to read its full source.
- Confirmation prompt — after dry-run preview (or when called without `--dry-run`), the script must print the proposed change count and ask `Apply changes? [y/N]:` before doing anything. Default is NO.
- Preview before prompt — never ask for confirmation without first showing what will happen.

**Examples:** `validate_naming.py`, `process_session_summary.py`, `run_in_sandbox.py` (all in `projects\corpus-tools\`)

**Standard pattern:**
```python
if args.dry_run:
    print("[DRY RUN] No files will be modified.")
# ... collect proposed changes, print them ...
print(f"\n{len(changes)} change(s) proposed.")
if not args.dry_run:
    confirm = input("Apply changes? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        sys.exit(0)
# ... apply changes ...
```

### Rebuild / read-only scripts

These generate derived artifacts (indexes, exports, reports) from the corpus but never modify source files. They are safe to run freely and repeatedly.

**Required behaviours:**
- `--no-pause` flag — skips the interactive "Press Enter to exit" prompt at the end of the run. Required for automation paths. The MCP server (`index-tools:rebuild_indexes`) calls scripts with `--no-pause` and `stdin=subprocess.DEVNULL` as defence-in-depth so any rogue `input()` call would EOF immediately rather than hang.
- No `--dry-run` needed — the script has no destructive corpus side-effects. If it fails, the worst outcome is a stale index or missing export, both of which are recoverable by re-running.
- Print a `Runtime: Xs` line at the end — useful for sanity-checking that the script hasn't gotten unexpectedly slow (e.g. after the corpus grows significantly).

**Examples:** `build_indexes.py`, and any future export or report generators.

---

## HEADER FORMAT — RATIONALE AND EXAMPLES

Every script opens with a structured comment block. This exists so that any Claude instance (or human) can read the header without running the script and understand what it does, what it accepts, and which category it belongs to. It also makes scripts discoverable in the same way YAML frontmatter makes `.md` files discoverable.

**Required format:**
```python
# name: Script Name
# keywords: [keyword1, keyword2]
# description: What this script does
#
# Human-readable top-level description. One or more sentences. Explain the
# purpose, the input (what it reads), and the output (what it produces or
# changes). Mention the category implicitly — if it modifies files, say so.
#
# Command line arguments:
#   --dry-run: Preview without executing (modification scripts only)
#   --no-pause: Skip end-of-run pause (rebuild scripts only)
```

**Good description examples:**
- `# description: Scans all corpus .md files for Snake_Case naming violations and renames them after confirmation.`
- `# description: Rebuilds directory_index.md, directory_index_with_files.md, and search_index.db from a single os.walk pass.`

**Bad description examples:**
- `# description: Utility script` — says nothing useful
- `# description: See README` — forces the reader to go elsewhere for basic orientation
- `# description: Processes files` — every script processes files; say *which* files and *how*

---

## WRITING A NEW SCRIPT — CHECKLIST

1. **Check both script locations first** — the utility may already exist, or an existing script may be extensible with a new flag. `Python/` (`corpus-infra`) is visible to chat-claude; `projects\corpus-tools\` is not, so ask the user or hand to code-claude to check it.
2. **Determine category** — does it write/rename corpus files? → modification. Does it only generate derived artifacts? → rebuild/read-only
3. **Write the header block first** — name, keywords, description, arguments — before writing any logic
4. **Implement category conventions** — `--dry-run` + confirmation + preview (modification) or `--no-pause` + runtime line (rebuild)
5. **Test with `--dry-run`** before the first real run on any modification script
6. **Add to examples list** in `Python_Scripts_Protocol.md` if it's a script future-Claude should know exists by name

---

## NAMING VALIDATION QUICKREF

The most commonly needed script:

```cmd
python D:\Claude\projects\corpus-tools\validate_naming.py --root "D:\Claude\filesystem\World_Building"
```

Scans for naming violations (spaces, ampersands, apostrophes in filenames), previews proposed fixes, requires confirmation. Modification script — always run `--dry-run` first.

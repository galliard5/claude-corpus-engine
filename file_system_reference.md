---
name: File System Reference
keywords: [reference, schemas, templates, procedures, protocols]
description: Supplementary procedures, tool schemas, and standards — load on demand from file_system_instructions.md
schemas_verified_utc: 2026-07-03T22:30:00Z
---

> **Last edited (UTC):** 2026-09-05T01:49:00Z
> Held in the body rather than the frontmatter so it survives a copy-paste into a
> project-instructions field, where frontmatter is discarded. Bump on every edit.

PAIRED SECTIONS
================

`file_system_instructions.md` and `file_system_reference.md` were split from one document ("always loaded" vs "load on demand") — the split is a drift channel. When editing a section on one side with a twin on the other, reconcile both in the same session:

```
PAIRED SECTIONS (edit one → reconcile its twin in the same session):
  instructions: VERIFIED TOOL SCHEMAS (quickref)   ↔ reference: TOOL SCHEMA REFERENCE
  instructions: STEP 4 INDEX REBUILD               ↔ reference: INDEX REFRESH TOOLING
  instructions: FILE CREATION VERIFICATION         ↔ reference: write_file verification pattern
  instructions: Handoff Mode B script note         ↔ reference: PYTHON SCRIPTS PROTOCOL
  instructions: NAMING & METADATA                  ↔ reference: FILE FORMAT STANDARDS
```

See `file_system_instructions.md` > FILE EDITING > Paired-file rule for the procedure.

---

This file supplements `file_system_instructions.md`. Load when needed for:
- Complete tool schemas with examples (filesystem, corpus-search, index-tools, series-search)
- Template usage
- Index refresh tooling and conventions
- Python script protocols
- Detailed file format standards

---

TOOL SCHEMA REFERENCE
=====================

> **Dated snapshot, not live truth.** Cached from live introspection on 2026-07-03 against `mcp/filesystem:2026.1.14`. Live docstrings via `tool_search` are authoritative — on any parameter error or doubt, trust the live schema over this document, then update this section.

> **Greppable convention — do not break.** Each tool is a `` ### `server:tool_name` `` header followed by a fenced block whose first line is `params:`; each parameter is one line, `name: type (required)` for required or `name?: type` for optional. Prose stays outside the fenced block. The schema-drift linter (`check_schema_drift.py`, planned) parses tool names + params from these blocks and ignores all prose — keep the form exact when adding or editing tools, or the linter silently under-reports.

Complete schemas for all 14 filesystem + 2 corpus-search + 1 index-tools + 3 series-search tools = 20 total, captured by direct introspection via `tool_search`.

## Filesystem Read Tools (4)

### `filesystem:read_text_file`
The current, primary text-read tool. Reads a file's complete contents as text, with optional `head`/`tail` line limiting.
```
params:
  path: string (required)
  head?: number
  tail?: number
```
**Example:** `path="/corpus/.../character.md"` — reads the entire file. `path=..., tail=20` — last 20 lines only: a cheap peek at a large file without pulling the whole thing into context. `head` and `tail` are mutually exclusive.

### `filesystem:read_file`
**DEPRECATED — alias for `read_text_file`.** Still served (won't error) and carries the same schema (`head`/`tail` included), but prefer `read_text_file`. The live server labels it deprecated in its own tool description.
```
params:
  path: string (required)
  head?: number
  tail?: number
```

### `filesystem:read_media_file`
Reads an image or audio file, returning base64-encoded data plus MIME type. Only within allowed directories.
```
params:
  path: string (required)
```
**Use case:** loading a character portrait (`.jpg`) or other binary for the model to examine. **⚠ Cost caveat:** base64 media is heavy in context — use only when the user actually needs the image looked at, not to confirm a file exists (use `get_file_info` for that).

### `filesystem:read_multiple_files`
Read multiple files in one call. More efficient than sequential reads. Failed reads for individual files don't stop the operation.
```
params:
  paths: array[string] (required, minItems: 1)
```
**Example:** `paths=["/corpus/.../file1.md", "/corpus/.../file2.md", "/corpus/.../file3.md"]`

**⚠ Caveat:** Many large files in one call can produce oversized payloads. If timing out, fall back to sequential `read_text_file` calls.

## Filesystem Write Tools (4)

### `filesystem:write_file`
Create a new file or completely overwrite an existing file. **No warning on overwrite.**
```
params:
  content: string (required)
  path: string (required)
```
**Example:** `content="---\nname: New File\n---\n\nBody", path="/corpus/.../NewFile.md"`

**Verification pattern (always do this):**
```
filesystem:write_file(content, path)
filesystem:read_text_file(path)   — check frontmatter at top and completion at bottom
```
`write_file` can return success but fail silently — always verify with the read above.

**⚠ Large-payload caveat:** A single `write_file` rewriting a large file (roughly 10–15 KB+) has been observed to hang indefinitely, with subsequent calls hanging behind it. Investigation (2026-07-03) traced this to Claude Desktop's tool-approval layer stalling on large buffered inputs — the call never reaches the MCP server, so the Docker/server side is fine and doesn't need restarting. If a call hangs silently, check for an unanswered approval prompt first; a Desktop app restart clears it if none is visible. Prefer several smaller `edit_file` calls over one big `write_file` for large rewrites — full writeup in `System_Documentation/Docker_Filesystem.md` > Troubleshooting.

### `filesystem:edit_file`
Line-based edits via exact string match. Returns git-style diff.
```
params:
  path: string (required)
  edits: array[{oldText: string, newText: string}] (required)
  dryRun?: boolean   — default false; preview without applying
```
**⚠ CRITICAL:** `oldText` must match the file EXACTLY — whitespace, newlines, all characters. Always `read_text_file` immediately before editing. After any successful edit, prior read output of the same file is stale; re-read before further edits.

**Multi-edit example:**
```
edits=[
  {oldText: "Old line one", newText: "New line one"},
  {oldText: "Old line two", newText: "New line two"}
]
```

**Anchor pattern for short snippets:** Use a two-line anchor for uniqueness when removing or editing short content:
```
oldText="| Line above the target |\n| Target line to remove |"
newText="| Line above the target |"
```

**Tip:** Use `dryRun=true` first when applying many edits to a file in a single batch. The returned diff lets you verify the full result before committing.

### `filesystem:create_directory`
Create a directory. Silently succeeds if directory already exists. Can create nested paths in one call.
```
params:
  path: string (required)
```
**Example:** `path="/corpus/World_Building/New_Setting/Characters"`

### `filesystem:move_file`
Move or rename files and directories. Single operation handles both. **Fails if destination already exists.**
```
params:
  source: string (required)
  destination: string (required)
```
**Examples:**
- Rename in place: `source="/corpus/.../Old_Name.md", destination="/corpus/.../New_Name.md"`
- Move to subfolder: `source="/corpus/.../Characters/X.md", destination="/corpus/.../Characters/Senior_Staff/X.md"`
- Soft delete: `source="/corpus/.../Bad_File.md", destination="/corpus/Trash/Bad_File.md"`
- Case-only rename (supported): `source="/corpus/.../anna_keller.jpg", destination="/corpus/.../Anna_Keller.jpg"`

## Filesystem Query Tools (6)

### `filesystem:list_directory`
List all files and directories in a path. Output uses `[FILE]` and `[DIR]` prefixes.
```
params:
  path: string (required)
```
**Note:** Empty directories produce no output (the call succeeds but returns nothing). To verify a directory is empty, this returning silence is the confirmation.

### `filesystem:list_directory_with_sizes`
Like `list_directory`, but each entry includes its size, and the listing can be sorted. Same `[FILE]`/`[DIR]` prefixes.
```
params:
  path: string (required)
  sortBy?: string
```
**`sortBy` values:** `"name"` (default) | `"size"`.
**Use case:** finding the largest files in a folder, or when file size informs a decision — without a separate `get_file_info` per entry.

### `filesystem:get_file_info`
File/directory metadata: size, created/modified/accessed timestamps, permissions, isDirectory, isFile.
```
params:
  path: string (required)
```
**Use case:** Check if a file exists, when last modified, or how large — without reading content.

### `filesystem:directory_tree`
Recursive JSON tree of a path. Each entry has `name`, `type` (file|directory), and `children` (for directories).
```
params:
  path: string (required)
  excludePatterns?: array[string]
```
**Use case:** Full structural snapshots when working on a specific subtree (e.g. confirming the layout under a region folder before adding new content). The `Python/build_indexes.py` script uses `os.walk` internally; in Claude work `directory_tree` is most useful for verifying complex multi-level structures at once rather than repeated `list_directory` calls.

### `filesystem:search_files`
Recursive search by glob pattern. Returns full paths.
```
params:
  path: string (required)
  pattern: string (required)
  excludePatterns?: array[string]   — default []
```
**Examples:**
- `path="/corpus/World_Building/[Setting]", pattern="*.md"` — every .md in that setting and its subdirs
- `path="/corpus", pattern="Briar*"` — every file starting with Briar
- `path="/corpus/.../[Faction]", pattern="*.md", excludePatterns=["Trash"]` — with exclusion

**⚠ Note:** Pattern is glob-style (`*.ext`, `**/*.ext`), NOT regex. Matches against filenames only — for body-content search, use `corpus-search:search_corpus` instead.

### `filesystem:list_allowed_directories`
Returns the list of directories this server can access. No params.

## Corpus Search Tools (2)

Custom MCP server exposing FTS5 ranked search over the corpus. See the CORPUS SEARCH section in `file_system_instructions.md` for the high-level when-to-use guidance. Schemas:

### `corpus-search:search_corpus`
Ranked search across name, keywords, description, category, and content. Returns formatted output: ranked path list with snippets showing matched context (FTS terms wrapped in `**`). Supports three retrieval lanes via `mode`.
```
params:
  query: string (required)         — FTS5 expression (fts/hybrid) or plain text (vector)
  limit?: integer                  — default 10
  mode?: string                    — "fts" (default) | "vector" | "hybrid"
  category_filter?: string|null    — optional path-segment filter
  type_filter?: string|null        — exact match on frontmatter type:
  missing_filter?: string|null     — name|keywords|description|type (corpus hygiene)
```
**Modes:**
- `"fts"` *(default)* — full-text BM25; exact terms, FTS5 syntax below. Unchanged legacy behaviour.
- `"vector"` — semantic nearest-neighbour over embeddings; finds meaning-similar docs with no shared words. Query is plain language.
- `"hybrid"` — fuses fts + vector with Reciprocal Rank Fusion (`rrf_k=60`); best general recall. Score shown as `rrf`; vector mode shows `similarity` (0–1); fts shows BM25 `score`.

Vector/hybrid need an embeddings-built index; otherwise the call falls back to `fts` and says so in the header. Filters apply across all three lanes.

**FTS5 query syntax:**
- `warden` — single term (porter stem matches warden, wardens, etc.)
- `warden security` — both words present (implicit AND)
- `warden OR steward` — either term
- `"charter of passage"` — exact phrase (escape inner quotes by doubling: `""`)
- `petition NOT rejected` — boolean exclusion
- `transform*` — prefix match (matches transformed, transformation)

**`category_filter` examples:**
- `"[Setting]"` — restrict to one setting's subtree
- `"[Faction]"` — restrict to one faction's content
- `"Senior_Staff"` — restrict to that specific subfolder

**BM25 ranking weights:** name (10×), keywords (5×), description (3×), content (1×). Higher score magnitude = better match. Hits in name and frontmatter rise above pure body matches automatically.

**Common pitfalls:**
- Apostrophes are tokenizer separators: `Keller's` indexes as `["keller", "s"]`. Search `Keller` to match.
- Special characters can produce FTS5 syntax errors — wrap problem terms in double quotes or use prefix matching.
- Files without YAML frontmatter still get indexed (filename is used as name) but lose the high-weight metadata fields.

### `corpus-search:index_status`
Returns the database path, total indexed file count, vector-lane availability, and last-built timestamp. No params.

**Use case:** Before relying on a search result for time-sensitive work, confirm the index is fresh. If `index_status` shows the build is older than a recent corpus change, prompt the user to refresh.

## Index Tools (1)

Custom MCP server for refreshing the on-disk indexes. See the INDEX REBUILD section in `file_system_instructions.md` for when-to-use guidance.

### `index-tools:rebuild_indexes`
Runs `build_indexes.py` directly via subprocess (not the bat — the bat ends with `pause` and would hang). Optionally returns fresh content based on the `load` parameter.
```
params:
  load?: string|null   — None | "directory" | "with_files" | "search_status"
```

**`load` values:**
- `None` (default) — rebuild only; return summary of both build steps
- `"directory"` — summary + fresh `directory_index.md` Claude section
- `"with_files"` — summary + fresh `directory_index_with_files.md` Claude section
- `"search_status"` — summary + corpus search index_status output (file count + timestamp)

**Returns:** Formatted text starting with `[OK] Indexes rebuilt successfully.` followed by the build output. If `load` is non-None, requested content is appended below a `=` separator. On failure, returns stdout/stderr for diagnosis.

**Hardcoded paths:** The tool can only run the known build scripts and only read the known index files. No parameter accepts a path from the caller. The corpus-search server's database is read-only here as well — the rebuild path goes through the build script, not the server.

**Timeout:** 30 seconds per step. Sub-second runtime in practice (rebuild typically ~0.5s total).

**Use cases by `load` value:**
- `"directory"` — predicted path failed; need fresh tree
- `"with_files"` — about to do filesystem-intensive work
- `"search_status"` — corpus-search returned empty; confirm index rebuilt
- `None` — user mentioned structural changes; refresh proactively without immediate read

## Series Search Tools (3)

Custom MCP server (`Python/series_search_mcp_server.py`) exposing FTS5 search over an external prose-series database. **Which database is mounted, and what it is used for, is project-specific** — see `World_Building/Project_Profile.md` > SERIES SEARCH BINDING. See STEP 6 SERIES SEARCH in `file_system_instructions.md` for when-to-use guidance; full schema/pipeline detail in `System_Documentation/Series_Search_Server.md`.

### `series-search:search_chapters`
FTS5 keyword search across the series database. Returns ranked results with chapter number, title, arc, series name, and a snippet highlighting matched terms.
```
params:
  query: string (required)         — FTS5 expression, see syntax below
  series?: string|null             — one series within a merged db; valid values depend on the mounted database
  db?: string|null                 — corpus-relative path to a .db; default set in the profile
  limit?: integer                  — default 10, capped at 200
```
**FTS5 query syntax (tokenizer gotchas — hyphens and dots are separators):**
- `dreadnought` — single term
- `dreadnought convoy` — both terms present (AND)
- `"heavy plasma"` — exact phrase (plain words only)
- `dreadnought OR frigate` — either term
- `mech*` — prefix match (mech, mechs, mechanical)
- `M318` or `"M 318"` — hyphenated designations: drop the hyphen or use a quoted phrase with a space. Bare `M-318` parses as `M NOT 318`.
- `Vas tir` — dot-separated names: split on the dot (`Vas.tir` won't tokenize correctly)

### `series-search:get_chapter`
Full text of a chapter by exact `chapter_num` match.
```
params:
  chapter_num: string (required)   — e.g. "499", "CLASSIFIED", "0.1.3", "Prologue"
  series?: string|null             — required when the same chapter_num exists in multiple series
  db?: string|null                 — corpus-relative path; default set in the profile
```

### `series-search:list_series`
Overview of a database: series names, chapter counts, arc breakdown. Good for orientation before searching.
```
params:
  db?: string|null                 — corpus-relative path; default set in the profile
```

**Default database:** project-specific — see `World_Building/Project_Profile.md` > SERIES SEARCH BINDING.

## Schema verification command

If any schema above appears wrong or a tool returns an unexpected parameter error:
```
tool_search(query="<keyword that matches the tool>")
```
This loads the live tool definition from the MCP server and shows the current schema. Update this reference if the live schema differs from what's documented here.

---

INDEX REFRESH TOOLING
=====================

One build script produces three derived files. All three are gitignored.

| File | Built by | Purpose |
|------|----------|---------|
| `index/directory_index.md` | `Python/build_indexes.py` | Compressed directory tree, dirs only (loaded at session start) |
| `index/directory_index_with_files.md` | `Python/build_indexes.py` | Directory tree with full file list (load on demand) |
| `index/search_index.db` | `Python/build_indexes.py` | SQLite FTS5 index for `corpus-search` MCP server |

`build_indexes.py` produces all three outputs from a single `os.walk` pass, replacing `build_directory_indexes.py` and `build_search_index.py` (unified 2026-05). The old scripts are in `Trash/` if needed for reference.

## Vector lane

`build_indexes.py` accepts a `--no-vectors` flag for FTS-only builds, skipping the embedding pass entirely. When embeddings are included, they're cached by content hash (`embed_cache`) so warm rebuilds only re-embed files that actually changed and stay sub-second; a cold build (fresh DB, or first run after an embedding-model change) re-embeds everything and takes roughly 40s. See `System_Documentation/Indexer.md` for full detail — not duplicated here.

## Three ways to refresh

**`index-tools:rebuild_indexes` (preferred for in-session refreshes)** — Claude calls this directly. Runs `build_indexes.py` via subprocess, optionally returns fresh content. See TOOL SCHEMA REFERENCE > Index Tools above.

**`Python/refresh_indexes.bat` (preferred for manual user refreshes)** — Double-click from Explorer. Runs `build_indexes.py` with errorlevel chaining and end-of-run pause. **Cannot be called from the MCP server** — the trailing `pause` would hang any subprocess invocation.

**Direct script invocation (rare):**
```cmd
cd D:\claude\filesystem\Python
python build_indexes.py            # interactive: pauses for Enter
python build_indexes.py --no-pause # automated
```

## `--no-pause` flag

The build script accepts `--no-pause` to skip the "Press Enter to exit" prompt. The bat file passes this flag for unattended execution. The MCP server passes this flag plus `stdin=subprocess.DEVNULL` as defense-in-depth so any rogue read would EOF immediately.

## Runtime stats

Each build script prints a `Runtime:` line in its summary block (e.g. `0.063s`). Display-only — never written to the index files themselves — for sanity-checking that nothing has gotten unexpectedly slow.

---

TEMPLATES
=========

Located: `Core_Rules/Templates/` — Copy and adapt, never edit originals.

**Content templates:**
- `Character_Sheet_Template.md` — NPC/PC profile (appearance, personality, goals, relationships, routine)
- `Location_Brief_Template.md` — Scene population (staffing, NPC presence, environmental detail)
- `Faction_Organization_Template.md` — Guild/institution (roles, income, influence, alliances, restrictions)
- `Noble_House_Template.md` — Political family (crest, territory, members, alliances, rivalries)
- `Scenario_Template.md` — Adventure outline (overview, setup, key events, hooks, mechanics)
- `Scenario_Package_Template.md` — Operational playbook pairing with a Scenario file: explicit NPC logic, voice anchors, file references, conditional responses for the runtime GM model
- `Timeline_Template.md` — Setting-level calendar and event log (current date, active threads, resolved)
- `Scenario_Timeline_Template.md` — Per-scenario calendar; day-by-day progression within one scenario, referencing the Master Calendar
- `Day_Brief_Template.md` — Session-ready daily brief; output of the prep chat, input for the play chat
- `Skill_Tree_Block.md` — Skill block for a PC sheet using the Emergent Skill Tree System

**Session documentation chain** (start with the System Guide — it explains how the other five fit together):
- `Session_Summary_System_Guide.md` — How the post-session documentation system works and when to use each component
- `Post_Session_Checklist.md` — Claude's process: what to update and in what order at checkpoint or session end
- `Session_Summary_Quick_Capture.md` — Output template for the saved summary `.md`
- `Checkpoint_Template.md` — Auto-generated save point: character state, NPCs, plot threads, world continuity
- `Session_Transcript_Stub.md` — Stub for the player to paste verbatim play into; the archive layer beneath summaries
- `Session_Log_Template.txt` / `Session_Log_Condensed.txt` — Summary templates despite the names; not verbatim records

**Generator saves:**
- `Perchance_Campaign_Template.json` — Skeleton campaign config for Perchance generators (genre, tone, tech era, stat-check display)
- `template.ai-story.json` — Perchance `ai-story` save format. ⚠ Despite the name, the local copy is a *populated* save rather than a skeleton, so it is not a usable template and is excluded from the public engine repository. Gut it to an empty schema before treating it as one.

**Usage:** Copy template → rename to match content → replace every bracketed placeholder, **including `type: template`** → update keywords/description. Once a placeholder holds real text the surrounding quotes can be dropped; leaving them is harmless.

---

FILE FORMAT STANDARDS
=====================

**.md files:**
- Lines 1–4: YAML frontmatter
- Line 5: blank
- Line 6+: Markdown content
- Character files: `First_Last.md` (portrait: `First_Last.jpg`)

**⚠ Bracketed placeholders in frontmatter must be quoted.** `name: [Character Name]` parses as a *list*, and `name: [Setting] Timeline` is invalid YAML that discards the entire frontmatter block silently. Write `name: "[Character Name]"`. `keywords:` is the exception — it is genuinely a list and stays unquoted. Full explanation and failure table in `file_system_instructions.md` > NAMING & METADATA.

**.txt files (prose and creative directories only):**
- No required header. The legacy `<meta>...</meta>` pseudo-XML tag from early in the project is deprecated; new `.txt` files don't need it.
- `.md` is also acceptable and is the preferred format for new creative work.

**.py files (Python/ only):**
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

PYTHON SCRIPTS PROTOCOL
========================

> **Authoritative source:** `Python_Scripts_Protocol.md` (terse rules) and `System_Documentation/Python_Scripts.md` (full conventions with reasoning). This section is a summary — load those documents when writing or debugging scripts.

- Last verified Python version: 3.14.3
- Since the 2026-06-12 repo split, scripts live in two places: the index builder + MCP servers stay in `D:\claude\filesystem\Python\` (`corpus-infra` repo, still visible under `/corpus`); the maintenance/conversion scripts (naming, session summaries, series/PDF pipelines, map converter, bgm) moved **out of the corpus** to their own repos under `D:\Claude\projects\`. You can't see the projects ones via `/corpus` — running/editing those is a Claude Code (dev-side) concern; ask the user to run them.
- To run a `corpus-infra` script from CMD: `cd D:\claude\filesystem\Python && python script_name.py [options]`
- if writing a cmd line call or a /bat file to run a cript, use 'python' instead of 'python3'

## Two script categories with different conventions

**Modification scripts** — write to or rename corpus files (now in `projects\corpus-tools\`). Examples: `validate_naming.py`, `process_session_summary.py`, `run_in_sandbox.py`.

- Must support `--dry-run` flag for preview
- Must require user confirmation before modifying files
- Must preview all proposed changes before applying

**Rebuild / read-only scripts** — generate derived artifacts (indexes, exports), never modify corpus files. Example: `build_indexes.py`.

- No `--dry-run` needed (no destructive action on corpus)
- Run freely from CMD or via `refresh_indexes.bat` or `index-tools:rebuild_indexes`
- Support `--no-pause` for unattended execution from automation paths

## Naming validation

```cmd
python D:\Claude\projects\corpus-tools\validate_naming.py --root "D:\Claude\filesystem\World_Building"
```
Scans for naming violations (spaces, ampersands, apostrophes), previews fixes, requires approval. Modification script — supports `--dry-run`. Resolves the corpus via the `CORPUS_ROOT` env var (fallback `D:\Claude\filesystem`).

---

METADATA MAINTENANCE
====================

After significant work on a file, re-read and re-evaluate its metadata (YAML frontmatter for .md files, header comments for .py files). Update keywords and description to reflect current content. Keeps the corpus search index reliable, since name/keywords/description are weighted highest in BM25 ranking.

When a file's metadata changes, the next index rebuild picks up the new values automatically — no manual reindex step needed. Trigger via `index-tools:rebuild_indexes` (Claude-driven) or `refresh_indexes.bat` (manual).

---

GIT BRANCHING (Experiments)
===========================

For major mechanics changes or alternative world states:
```cmd
git branch experimental/[short-description]
git checkout experimental/[short-description]
```
Work, test, then keep or discard. Optional for solo work.

---
name: File System Instructions
keywords: [rules, instructions, reference]
description: Core project rules and procedures for every session
---

> **Last edited (UTC):** 2026-09-05T01:49:00Z
> Held in the body rather than the frontmatter so it survives the copy-paste into the
> claude.ai project-instructions field, where frontmatter is discarded. Bump on every edit.

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

See FILE EDITING > Paired-file rule below for the procedure.

---

AVAILABLE TOOLS FOR CLAUDE
==========================

Tools come from several MCP servers. **Only some ship with this repository** — the rest are
third-party or self-built servers connected separately. The split matters: a rule that depends
on a tool you haven't connected fails at the point of use, and the failure looks like Claude
being broken rather than a server being absent.

---

## Ships with this repository

**Corpus Search Tools (2):** corpus-search:search_corpus, corpus-search:index_status (see CORPUS SEARCH below)

**Index Tools (1):** index-tools:rebuild_indexes (see INDEX REBUILD below)

**Series Search Tools (3):** series-search:search_chapters, series-search:get_chapter, series-search:list_series (see SERIES SEARCH below). Ships without a database — see `System_Documentation/Series_Search_Server.md` > *Building a compatible database*.

These three run as one Docker Compose stack built from `Python/`. See `System_Documentation/Architecture.md`.

**Filesystem Tools (14):**
- Read: filesystem:read_text_file, filesystem:read_multiple_files, filesystem:read_media_file (filesystem:read_file — DEPRECATED alias for read_text_file, still works)
- Write: filesystem:write_file, filesystem:edit_file, filesystem:create_directory, filesystem:move_file
- Query: filesystem:list_directory, filesystem:list_directory_with_sizes, filesystem:get_file_info, filesystem:directory_tree, filesystem:search_files, filesystem:list_allowed_directories

> The server is the upstream `@modelcontextprotocol/server-filesystem`, pinned and built locally from `Python/filesystem-mcp/Dockerfile` rather than pulled as `mcp/filesystem:latest` (the published image lagged npm by several releases). Build instructions and the version-bump procedure are in that Dockerfile's header comments and in `System_Documentation/Docker_Filesystem.md`.
>
> `read_text_file` is the current text-read tool and supports `head`/`tail` line limiting; `read_file` still works but is deprecated. `read_media_file` reads images/audio as base64 (heavy — use sparingly). `list_directory_with_sizes` adds sizes + sorting.

---

## External MCP servers (connect separately)

Not included here. Each is optional, but rules elsewhere in this repo assume some of them — the
notes below say which.

**SymPy Tools (40+):** sympy:* — symbolic math engine (algebra, trig, calculus, unit conversion, matrix ops, equation solving, and optionally tensor/relativity work). Use for any calculation where exact results matter: dice modifier arithmetic, stat formulas, rolling offset calculations, or anything you'd otherwise reason through numerically. Invoke via natural language — describe the expression and variables, and call the appropriate sympy tool rather than computing in-context.

> **Source:** `sympy-mcp` by Stephen Diehl — https://github.com/sdiehl/sympy-mcp (Apache-2.0, Python 3.12+).
> Install with [uv](https://astral.sh/uv):
> ```cmd
> git clone https://github.com/sdiehl/sympy-mcp.git
> cd sympy-mcp
> uv sync
> uv run mcp install server.py
> ```
> `uv sync --group relativity` adds the einsteinpy dependency needed for the tensor and
> spacetime-metric tools. A Docker image also exists: `ghcr.io/sdiehl/sympy-mcp:main`,
> run with `-p 8081:8081`.
>
> **Nothing in this repo hard-depends on SymPy.** Without it, do the arithmetic carefully by hand.

**Dice Tools (4):** dice-roller:dice_roll, dice-roller:dice_validate, dice-roller:search, dice-roller:fetch — real RNG (Node `crypto.randomInt()`, OS CSPRNG) for all in-session dice. **An LLM cannot roll dice; it predicts plausible-looking numbers.** Notation: `1d20+5`, `2d20kh1` (advantage), `2d20kl1` (disadvantage), `4d6dl1` (stat gen), `3d6!` (exploding), `5d10>7` (success counting), `4dF` (Fudge), `1d%`. Pass `label` for readability and `verbose: true` when individual dice matter. `dice_validate` explains notation without rolling.

> **Source:** `dice-rolling-mcp` by Jim McQuillan — https://github.com/jimmcq/dice-rolling-mcp (ISC, TypeScript, Node 18+).
> ```cmd
> git clone https://github.com/jimmcq/dice-rolling-mcp
> cd dice-rolling-mcp
> npm install
> npm run build
> ```
> Then add to `claude_desktop_config.json`:
> ```json
> "dice-roller": {
>   "command": "node",
>   "args": ["path/to/dice-rolling-mcp/dist/index.js"]
> }
> ```
> A hosted endpoint also exists at `https://dice-rolling-mcp.vercel.app/mcp` for remote-connector use.
>
> **`Core_Rules/core_rules.md` > DICE RESOLUTION depends on this server.** Read that section's
> fallback note before running a session without it.

---

WINDOWS FILESYSTEM ENVIRONMENT
==============================

**MCP filesystem paths**: The filesystem MCP server runs in Docker and serves Linux paths.
  - MCP tool operations use: `/corpus/` as root (e.g. `/corpus/World_Building/[Setting]/`)
  - Windows host path: `D:\claude\filesystem\` (for git, CMD, File Explorer, Obsidian)
**MCP filesystem tools only**: Use filesystem MCP tools exclusively for corpus operations.
**Root directory**: `/corpus` inside the Docker container — ALL MCP operations confined here.

---

WHO IS "CODE-CLAUDE"? (chat-claude vs code-claude)
==================================================

These name Claude in two environments, not folders.

- **chat-claude** is you — Claude in this chat/RP session (Claude Desktop, sometimes mobile), working through `/corpus/` with the MCP tools above.
- **code-claude** is Claude Code, the coding agent (the Desktop app's Code feature, VS Code, or a terminal). It works on the raw Windows filesystem — including `D:\Claude\projects\`, which you can't see — and can run scripts and code directly.

When a task needs a Python script written, run, debugged, or an index/Docker rebuild, that's code-claude's job, not yours — hand it over rather than improvising. (The dev projects moved to `D:\Claude\projects\`; "code-claude" is the agent, not a directory.)

---

STARTUP PROCEDURES — EXECUTE ON EVERY CONVERSATION START
=========================================================

## STEP 1: PROJECT ROOT & TOP-LEVEL STRUCTURE + DEFERRED TOOL LOAD

**[FIRST] Preload all MCP tools (prevents deferred-tool load errors on first calls):**
Call `tool_search("filesystem read write edit corpus index series search sympy math dice roll")` immediately at session start.
This loads all 14 filesystem tools, 2 corpus-search tools, 1 index-tools tool, 3 series-search tools, the sympy math tools, and the 4 dice-roller tools into the registry so they're ready for immediate use. Zero cost after first call; eliminates the red parameter-error on initial tool invocations.

**Root:** `/corpus` (Docker container path) — ALL MCP file operations confined here. No exceptions.
**Host path:** `D:\claude\filesystem\` — use this for git, CMD, and native Windows tools.

**Session instructions load (every session):**

This file is the **engine half** of the session instructions — tools, protocols, workflows.
Nothing in it is specific to any one setting. The project half lives in a companion profile
that carries semantic placement rules, content directories, and setting-specific bindings.
Load both:

```
filesystem:read_multiple_files([
  "/corpus/file_system_instructions.md",
  "/corpus/World_Building/Project_Profile.md"
])
```

A different corpus would swap the profile and leave this file untouched.

**BIOS freshness check (every session):**
1. The read above returns this file's current disk content.
2. The **Last edited (UTC)** line immediately below the frontmatter carries the timestamp. Compare against the project-instructions copy in your context. It sits in the body, not the frontmatter, because the project-instructions paste discards frontmatter — a mirror missing the value makes this check silently unfalsifiable rather than merely wrong.
3. If they differ: warn user `📝 Project-instructions copy of file_system_instructions.md is older than disk version (disk: [date], project: [date]) — consider re-mirroring`
4. If they match or project copy is newer: no message; proceed normally

This catches the common failure mode where the on-disk file is edited but the project-instructions mirror is forgotten. The file is small enough (~25 KB) that the whole-file read is cheap.

**Engine directories:**
- `Core_Rules/` — GM rules (`core_rules.md`), extraction rules, templates (never edit originals)
- `Python/` — **Separate git repo** (`corpus-infra`): the Docker MCP servers (corpus-search, index-tools, series-search) + the index builder + `docker-compose.yml`. Not part of the worldbuilding repo — you don't commit here. (See CORPUS SEARCH below.)
- `System_Documentation/` — **Separate git repo** (`system-docs`): reference docs for the indexer, corpus search, Docker, and audit history. Start at `README.md`. Not part of the worldbuilding repo.
- `Trash/` — Soft-delete destination (no permanent deletes)
- `Working_Documents/` — **Handoffs, proposals, and planning documents go here, not at the corpus root.** Contents are excluded from the public engine repository by a directory rule, so anything written here is unpublished by default. Retire a document to `Trash/` once its work closes, and promote anything durable it produced into `System_Documentation/` first. See its `README.md`.
- `.github/` — GitHub Codespaces auto-generated; leave alone

**Content directories** — what settings, prose, references, and ingest folders exist, and which are gitignored or excluded from the search index — are project-specific. See the profile.

**Root files:**
- `file_system_instructions.md` — This file: the **engine half** of the session instructions
- `World_Building/Project_Profile.md` — The **project half**: semantic placement, content directories, setting bindings
- `file_system_reference.md` — Supplementary reference (load on demand)
- `Python_Scripts_Protocol.md` — Terse rules for Python scripts; see `System_Documentation/Python_Scripts.md` for the full conventions with reasoning
- `README.md` — Repository overview
- `.gitignore` — Excludes derived artifacts, ingest folders, and personal content from version control
- **Handoff files** — working handoff/plan docs (e.g. a `*_Handoff.md`) live at root during active multi-session work and are deleted (or moved to `Trash/`) once complete — don't treat a root-level handoff file as permanent structure

Project-side root files (`AGENTS.md`, `Claude_Code_Context.md`, `Creative_Writing_Skills_Override.md`) are listed in the profile.

**Index files (now under `/index/`):**
- `index/directory_index.md` — Live directory map (gitignored, see DIRECTORY INDEX below)
- `index/directory_index_with_files.md` — Directory map with full file list (gitignored, load only for heavy filesystem operations)
- `index/search_index.db` — SQLite FTS5 corpus search index (gitignored, consumed by the corpus-search MCP server)

Full directory structure is maintained in `index/directory_index.md` — do not duplicate here.

**GitHub/Codespaces auto-generated files** (created when using GitHub Codespaces for collaborative editing):
- `.vscode/` — VS Code workspace settings; leave alone (regenerated on each Codespaces session)
- `README.md` — Repository overview; can edit for onboarding collaborators, but non-essential
- `.github/pull_request_template` — PR template for collaborators; safe to ignore or customize

## STEP 2: EFFICIENCY PRINCIPLE

- Minimize tool calls; batch reads with `filesystem:read_multiple_files`
- For a large file where you only need the top or bottom, use `filesystem:read_text_file` with `head`/`tail` instead of loading the whole thing
- Batch file writes into single operations
- Estimate token cost before multi-file tasks
- **Model selection:** Three tiers — Opus for judgment-heavy work, Sonnet for session running and day-to-day creative execution, Haiku for templated or mechanical execution. See MODEL TIERS & HANDOFF PROTOCOL for tier guidance and handoff format.

## STEP 3: DIRECTORY INDEX

The directory index lives at `/corpus/index/directory_index.md`, generated by `Python/build_indexes.py`. It contains:
- **YAML header** (lines 1–8): frontmatter with `scan_utc` timestamp and `claude_section_end` line number
- **Compressed Claude section** (lines 9–N): single-space-indented tree, no decorators — optimised for token count

**Startup procedure:**
1. `filesystem:read_text_file` on `/corpus/index/directory_index.md` — loads the whole file: YAML header plus the compressed Claude section.
2. The `claude_section_end` value in the YAML tells you where the directory tree ends, in case the file ever gains content past that point (currently it doesn't).
3. Display: `📁 Directory index loaded | Scanned: [date] | Ready`

Note: `directory_index_with_files.md` is the larger sibling with full file listings. Don't load it at session start — only when heavy filesystem work needs it.

The index is loaded once at session start and trusted for the duration of the conversation. **No periodic staleness checks.** If the index turns out to be wrong about something mid-session (predicted path doesn't exist, corpus-search returns empty for content that should obviously exist, user mentions structural changes), call `index-tools:rebuild_indexes` to refresh — see STEP 4 below.

**Using the index:**
Reference the loaded compressed tree + conversation context to predict file locations. Use predicted paths as starting points — verify with `filesystem:search_files` or `corpus-search:search_corpus` only when uncertain.

**Mid-session reload after rebuild:** If `index-tools:rebuild_indexes` returns fresh content via `load="directory"` or `load="with_files"`, that fresh content supersedes the index loaded at session start. Use only the most recent.

## STEP 4: INDEX REBUILD

The `index-tools` MCP server exposes one tool for refreshing the on-disk indexes when needed. The tool runs the build scripts directly and optionally returns freshly-built content in the same call.

**`index-tools:rebuild_indexes(load=None)`** — Rebuilds both directory indexes and the corpus search index, then optionally returns content based on `load`:

- `load=None` (default) — rebuild only, return summary
- `load="directory"` — return fresh directory_index.md Claude section
- `load="with_files"` — return fresh directory_index_with_files.md Claude section
- `load="search_status"` — return corpus search index_status (file count + timestamp)

Total runtime: ~0.5 seconds. The bat file `Python/refresh_indexes.bat` is the manual equivalent (double-click from Explorer).

**When to call it:**
- Predicted path lookups failing repeatedly (directory has drifted)
- corpus-search returning empty for content that should obviously exist (search index stale)
- User explicitly says "I just made structural changes, refresh"
- Before heavy filesystem operations where stale paths would cascade

**When NOT to call it:**
- Reflexively at session start (the index loaded at startup is sufficient)
- On a timer (we use reactive freshness, not periodic checks)
- Just because some time has passed (corpus drift between sessions is fine — directory structure is mostly stable)
- After every minor edit (rebuilds are fast but not free; group structural changes)

**Choosing the `load` value:**
- Need to re-orient on directory structure → `"directory"`
- About to do filesystem-intensive work needing full file listings → `"with_files"`
- Just confirming search index rebuilt cleanly → `"search_status"`
- Refreshing proactively, no immediate read needed → leave as default (None)

## STEP 5: CORPUS SEARCH

A custom MCP server (`Python/search_mcp_server.py`) exposes ranked search over the corpus: full-text (SQLite FTS5) plus an optional **semantic vector lane** (sqlite-vec embeddings), selectable/fusible via the `mode` parameter. Two tools:

- **`corpus-search:search_corpus(query, limit=10, mode="fts", category_filter=None, type_filter=None, missing_filter=None)`** — ranked search across name, keywords, description, category, and content. Returns ranked paths with snippets showing matched context. Higher scores = better matches. `mode` picks the retrieval lane (see below); the three filters compose with AND. `limit` (default 10) is capped at 200 — a larger value returns a diagnostic error, not results (a runaway-call backstop you'll never hit in normal use). (Full filter docs: `System_Documentation/Search_Server.md`.)
- **`corpus-search:index_status()`** — Returns file count, vector-lane availability, and last-built timestamp. Use to check freshness before relying on results.

**FTS5 query syntax:**
- `warden` — single term (porter stem matches warden, wardens, etc.)
- `warden security` — both words present (implicit AND)
- `warden OR steward` — either term
- `"charter of passage"` — exact phrase
- `petition NOT rejected` — boolean exclusion
- `transform*` — prefix match (matches transformed, transformation)

**Search modes (`mode=`):**
- `"fts"` *(default)* — full-text BM25, the FTS5 syntax above. Exact terms, fastest. Behaviour unchanged from before this lane existed.
- `"vector"` — semantic nearest-neighbour. Finds documents close in *meaning* even with no shared words (a query about "estate defenses collapsing" surfaces a doc that only says "the manor's security failed"). Query is plain language, not FTS5 syntax.
- `"hybrid"` — fuses fts + vector via Reciprocal Rank Fusion. Best general recall; rewards documents both lanes agree on.

Vector/hybrid require the index to have been built with embeddings; if absent the call silently falls back to `fts` and notes it in the result header.

**When to reach for it:**
- Cross-reference questions: "where else is X mentioned" — filesystem search only matches filenames; corpus search matches body content
- Grounding before drafting: pulling all prior references to a character/location before writing session content
- Thematic / half-remembered recall: when you recall the *gist* of something but not the wording, use `mode="hybrid"` (or `"vector"`) — keyword search alone will miss paraphrases
- Ambiguous file location: faster than guessing paths when the directory index doesn't make placement obvious
- Session prep: confirming established lore on factions, items, or events that may have been touched in earlier sessions

**When NOT to use it:**
- You already know the path → read the file directly
- Looking for a filename pattern → `filesystem:search_files` is the right tool
- Listing everything in a folder → `filesystem:list_directory`

**Reading the results:**
- **Rank is similarity, not relevance.** A high score means the document resembles the *query* — lexically in `fts`, semantically in `vector`/`hybrid`. The semantic lanes in particular return thematic neighbours with no causal connection to what you're working on. Judge each hit on its content, not its position in the list.
- **Empty is an answer.** No results means the fact isn't in the corpus. If that seems wrong, check freshness with `corpus-search:index_status` before concluding anything — but a genuinely empty search means the thing is unestablished, and the gap is not yours to fill.
- **Retrieving something doesn't make it live.** For session use, see `Core_Rules/core_rules.md` > *Retrieval Is Not Salience* — a file opened during prep or play is not thereby part of the scene.

**Index scope:** Indexes all `.md` files under `/corpus` except `Trash/`, `Python/`, hidden/build dirs, and the project-specific exclusions configured in `Python/indexer.cfg`. The index is a binary SQLite file at `index/search_index.db` — gitignored, rebuilt on demand.

**Refreshing the index:** Use `index-tools:rebuild_indexes` (preferred — runs all three outputs in one pass via `build_indexes.py`). Manual alternative: `refresh_indexes.bat` (double-click from Explorer). Sub-second in normal use — document embeddings are cached by content hash, so a rebuild only re-embeds the files that actually changed. (The exception is a *cold* build — a fresh DB or the first run after an embedding-model change — which re-embeds everything and takes ~40s. Rare; not something you trigger casually.) Call `corpus-search:index_status` if you need to confirm freshness without rebuilding.

## STEP 6: SERIES SEARCH

A custom MCP server (`Python/series_search_mcp_server.py`) exposes FTS5 search over an external prose-series database — long-form reference material held outside the corpus proper. **Which database is mounted and what it is used for is project-specific:** see `World_Building/Project_Profile.md` > SERIES SEARCH BINDING. Three tools:

- **`series-search:search_chapters(query, series=None, db=None, limit=10)`** — FTS5 keyword search returning ranked results with chapter number, title, arc, series name, and a snippet highlighting matched terms. `limit` (default 10) is capped at 200, same backstop as corpus-search.
- **`series-search:get_chapter(chapter_num, series=None, db=None)`** — Full text of a chapter by number (exact match on `chapter_num` — e.g. `"499"`, `"CLASSIFIED"`, `"Prologue"`).
- **`series-search:list_series(db=None)`** — Overview of the database: series names, chapter counts, arc breakdown. Good for orientation before searching.

**FTS5 query syntax:**
- `dreadnought` — single term
- `dreadnought convoy` — both terms present (AND)
- `"heavy plasma"` — exact phrase (plain words only — no hyphens or dots inside quotes)
- `dreadnought OR frigate` — either term
- `mech*` — prefix match (mech, mechs, mechanical)
- `M318` or `"M 318"` — hyphenated designations: drop the hyphen or use a quoted phrase with a space. Bare `M-318` parses as `M NOT 318`.
- `Vas tir` — dot-separated names: split on the dot (`Vas.tir` won't tokenize correctly)

**`series` filter:** narrows to one series within a merged database. Valid values depend on which database is mounted — see the profile. The `db` parameter accepts any corpus-relative path to a compatible `.db`, useful for single-series queries.

**When to use:**
- Reference lookups — named entities, technology, equipment, terminology across the series
- Identifying which arc or chapter introduced a concept
- Reading full chapter text for scene context

**Not a startup step** — on-demand reference only. No need to initialise at session start.

See `System_Documentation/Series_Search_Server.md` for full schema, pipeline, and update procedure.

## STEP 7: SEMANTIC FILE PLACEMENT

Directory naming conventions enable inference-based placement. The **naming convention** is
engine-level and lives under NAMING & METADATA below. The **placement map** — which settings
exist, where regions and factions live, how character folders are subdivided — is entirely
project-specific and lives in `World_Building/Project_Profile.md` > SEMANTIC FILE PLACEMENT.

When uncertain: `filesystem:search_files` to verify. Otherwise trust the structure.

---

NAMING & METADATA
=================

**Naming:** All files and folders use `Snake_Case_With_Capitals` — underscores between words, leading capital on each significant word. Examples: `Senior_Staff`, `House_Ravenmoor`, `Anna_Keller.md`, `Border_Fort`. JPG filenames match their .md counterparts (`Anna_Keller.jpg`, not `anna_keller.jpg`). Default output: `.md`. Images: `.jpg` preferred. `.txt` is acceptable in prose and creative directories.

**YAML frontmatter (all .md files, lines 1–5):**
```yaml
---
name: Name
type: document-category
keywords: [keyword1, keyword2]
description: One sentence description
---
```

**Field guide:**
- `name` — Document title (required). Use `Snake_Case_With_Capitals`.
- `type` — (optional) Document category for meta-organization. Examples: `setting-document`, `race-document`, `character-sheet`, `scenario`, `rules-reference`, `template`. No spaces; use hyphens. Omit if not applicable.
- `keywords` — (required) Comma-separated tags for searchability and discovery.
- `description` — (required) One-sentence summary of document purpose and scope.

**⚠ Square-bracket placeholders must be quoted.** In YAML a `[` opening a value is a *flow sequence*, not a placeholder. Three failure modes, all silent — the file still looks fine in an editor:

| Written | Parsed as | Result |
|---|---|---|
| `name: [Character Name]` | the list `['Character Name']` | name indexes as a list |
| `description: [One sentence on status, holdings, and significance]` | a **three-item list**, split on the commas | description mangled |
| `name: [Setting] Timeline` | *invalid YAML* — sequence with trailing text | parser throws; **the whole frontmatter block is discarded** and the file indexes with no metadata at all |

Quote any value containing a bracketed placeholder: `name: "[Character Name]"`. Brackets that appear mid-string are safe unquoted, but quoting anyway costs nothing.

**`keywords:` is the exception** — it is genuinely a list, so its brackets are correct and must stay unquoted.

**Templates** carry `type: template` so they are findable as a group. Anyone copying a template must replace every bracketed placeholder *including* `type:` with the real document category — don't leave a working character sheet claiming to be a template.

*Note:* The legacy `<meta>` pseudo-XML tag format (a single-line tag at the top of `.txt` files) is deprecated. New `.txt` files in prose and creative directories don't need it; old files that have it can be left alone or migrated to YAML opportunistically.

---

STRUCTURAL CHANGE PROTOCOL
==========================

When the corpus structure changes meaningfully during a session, update `memory_user_edits` with a brief summary so future sessions inherit the change without needing a fresh index read at the start of every conversation.

**Triggers (any of these):**
- New top-level or major subfolder created
- File moves of more than 2 items at once
- `.gitignore` additions or removals
- New scenarios, campaigns, or major directory branches
- Renames affecting more than 1 file
- Folder reorganization (e.g. splitting a Characters/ folder by role)

**What to record in memory:**
- What changed (one-line summary)
- Where it happened (path)
- Why, if non-obvious

**Examples:**
- "[Region]/[Location]/Characters/ added 3 new NPCs from session 3"
- "Moved retired scenario from Scenarios/ to Trash/"
- "Sheet_Import/Processed/ created and 12 sheets relocated there"
- "[Faction]/Characters/ split: added a subfolder for contractor roles"

**Timing:** Update memory BEFORE the git commit at end of session, so memory and disk land in sync. The next session's startup picks up both.

This protocol is what makes `index-tools:rebuild_indexes` rare-use rather than reflexive. With a memory-first habit, future-Claude already knows about the change and only needs to rebuild when memory is silent on something that should obviously exist.

---

CORE WORKFLOWS
==============

## BATCH WRITE PROTOCOL

1. Accumulate changes during work session
2. Maintain visible pending list: `[PENDING] X files ready to write`
3. User triggers write: "commit", "save all", "batch write", "done"
4. Execute batch write → verify each file with `filesystem:read_text_file`
5. Propose git commit → execute on approval. **The pending list is the stage list** — the commit block enumerates those exact paths, nothing else (see GIT COMMIT & PUSH below).

## GIT COMMIT & PUSH TO GITHUB

**Repo structure (since 2026-06-12):** The corpus is split into per-project git repos. The one you commit is the **worldbuilding repo** rooted at `D:\claude\filesystem\` (lore, `Core_Rules/`, this file) → backs up to its configured private remote (run `git remote -v` if you need the URL; it is deliberately not written here). `Python/` (`corpus-infra`) and `System_Documentation/` (`system-docs`) are **separate repos** nested inside and gitignored here, so your `git add .` never touches them — that's correct, they're managed on the dev side. The development projects (bgm, map converter, etc.) moved out of the corpus entirely to `D:\Claude\projects\` and aren't visible to you. **Net: your commit workflow is unchanged — just keep committing from `filesystem\`.**

**Environment:** Windows CMD only. No bash. Provide copy-paste `cmd` blocks.

**Format:** `[Category]: [Subject] | [Details] | [In-Game Date]`

**Categories:** `Session:` `Scenario Extraction:` `World Building:` `Character:` `Rules Update:` `Project Maintenance:` `Bulk:`

**Example:**
```
Session: Riverside Campaign 02 | Recruitment, squad briefing | Date: 8 March 1651
```

**Stage by path — never `git add .`**

`git add .` stages *everything dirty in the tree*, including files you never touched. code-claude works in this same repo (`Core_Rules/`, this file, dev-facing docs) and its in-progress edits sit here alongside yours. A blanket stage sweeps them into your commit under your message, which misfiles the change and makes the history lie about what happened. It has already happened once (2026-07-25).

**Build the commit from your pending list.** You know exactly which files you wrote this session — the BATCH WRITE PROTOCOL list above *is* the stage list. Enumerate those paths and no others.

**Copy & Paste This Block** (fill in the real paths and the real message — never leave a placeholder, and never reuse the previous commit's message):
```cmd
D:
cd D:\claude\filesystem
git add "World_Building/[Setting]/Faction_Overview.md" "World_Building/[Setting]/Characters/Anna_Keller.md"
git commit -m "World Building: Faction overview + new NPC | Overview doc and supporting character file | Date: 12 March 1651"
git push origin main
git status --short
```

The trailing `git status --short` prints whatever is still uncommitted. **Expect leftovers** — they're usually code-claude's work in flight, and they are not yours to commit. If the user pastes back entries you don't recognize, say so rather than offering to sweep them in.

**Before proposing the block,** if you're unsure what else is dirty, ask the user to run `git status --short` in `D:\claude\filesystem` and paste the result. Claim only the files on your pending list.

**Bulk operations** (the `Bulk:` category — mass renames, metadata passes touching 100+ files) are the one case where enumerating paths is impractical. There, `git add .` is acceptable **only** if you first show the user the full `git status --short` output and confirm every entry belongs to the operation.

**Note on line endings:** this repo runs `core.autocrlf=true`, so files often show as modified in `git status` when only line endings differ. Those normalize away on staging and produce no commit content — a file appearing dirty does not mean it has real changes.

## FILE EDITING

**CRITICAL:** Always `filesystem:read_text_file` immediately before using `filesystem:edit_file`. Never rely on remembered content — `edit_file` requires exact string matching.

Process: Read → identify exact target text → edit with verified string.

**Paired-file rule:** `file_system_instructions.md` and `file_system_reference.md` are two halves of one document. When editing either, check the PAIRED SECTIONS map (top of this file); if the edited section has a twin, read the twin and update it or explicitly confirm no change is needed — in the same session, before the git commit. Bump the **Last edited (UTC)** line on every file touched.

`World_Building/Project_Profile.md` is a third participant. If an edit moves content across the engine/project boundary — adding a setting-specific example to an engine doc, or generalizing something out of the profile — reconcile the profile in the same session too.

## VERIFIED TOOL SCHEMAS (quickref)

> Derived quickref, memory jog only. Live docstrings (`tool_search`) are authoritative; dated full snapshot in `file_system_reference.md`.

- `filesystem:read_text_file` — `path`, `head?`, `tail?`
- `filesystem:read_file` — `path`, `head?`, `tail?`  *(DEPRECATED — alias for read_text_file)*
- `filesystem:read_media_file` — `path`  *(image/audio → base64; heavy)*
- `filesystem:read_multiple_files` — `paths`
- `filesystem:write_file` — `content`, `path`
- `filesystem:edit_file` — `path`, `edits`, `dryRun?`
- `filesystem:create_directory` — `path`
- `filesystem:move_file` — `source`, `destination`
- `filesystem:list_directory` — `path`
- `filesystem:list_directory_with_sizes` — `path`, `sortBy?`
- `filesystem:get_file_info` — `path`
- `filesystem:directory_tree` — `path`, `excludePatterns?`
- `filesystem:search_files` — `path`, `pattern`, `excludePatterns?`
- `filesystem:list_allowed_directories` — no params
- `corpus-search:search_corpus` — `query`, `limit?`, `mode?`, `category_filter?`, `type_filter?`, `missing_filter?`
- `corpus-search:index_status` — no params
- `index-tools:rebuild_indexes` — `load?`
- `series-search:search_chapters` — `query`, `series?`, `db?`, `limit?`
- `series-search:get_chapter` — `chapter_num`, `series?`, `db?`
- `series-search:list_series` — `db?`

⚠ If a parameter error fires, run `tool_search` with a relevant keyword to load the live schema.

## WINDOWS PATH REQUIREMENTS

**MCP tool paths** (inside Docker container — use these with filesystem tools):
  - ✓ Correct: `/corpus/World_Building/[Setting]/filename.md`
  - ✗ Wrong: `D:\claude\filesystem\World_Building\...`

**Windows host paths** (for git, CMD, File Explorer — NOT for MCP tools):
  - ✓ Correct: `D:\claude\filesystem\World_Building\[Setting]\filename.md`
  - Host root: `D:\claude\filesystem\`

**Directory verification**: Use `filesystem:list_directory` with `/corpus/...` paths
**Search when uncertain**: `filesystem:search_files` with patterns like `*.md`

**Case-only renames are supported**: `filesystem:move_file` with source `anna_keller.jpg` → destination `Anna_Keller.jpg` works in a single call. Use this to standardize JPG filenames to match their .md counterparts.

## FILE CREATION VERIFICATION

After EVERY `filesystem:write_file`: 
1. Immediately verify with `filesystem:read_text_file` — check the YAML frontmatter at the top and that the file ends as expected.
2. Check file exists in directory: `filesystem:list_directory` (only when in doubt — the read above is normally enough)
3. Verify content matches expected structure (YAML frontmatter, etc.)

**Common verification pattern**:
```
filesystem:write_file(content, path)
filesystem:read_text_file(path)  // Verify frontmatter at top, completion at bottom
```

`write_file` can return success but fail silently — ALWAYS verify. (This is the canonical write-verification pattern; ERROR HANDLING below references it rather than re-stating it.)

## MODEL TIERS & HANDOFF PROTOCOL

Three tiers, each with a different sweet spot. Pick by what the work actually needs, not by reflex.

### The three tiers

**Opus** — world-shaping decisions, central character development, lore architecture, multi-step worldbuilding consistency, deep math, anything where per-sentence judgment carries weight. Use where its ceiling matters; expensive elsewhere.

**Sonnet** — session running (canonical use case), NPC dialogue in-play, mechanical resolution with voice, scene execution from a prepped brief, mid-tier creative work. The cost/quality curve bends most usefully here. Sonnet often matches Opus on subjective session quality because GM execution is templated once setup is done — Opus's advantage is in *preparation*, not *execution*.

**Haiku** — templated expansion from clear specs, mechanical transforms, format conversions, batch metadata, filling slots in a known structure. Loses voice and grounding when asked to make judgment calls.

### When each model is the source

- **Opus direct** — central work where Opus's judgment IS the deliverable (main session prep, central character creation, lore architecture)
- **Sonnet direct** — session running, mid-tier NPCs, scene execution, day-to-day creative work
- **Haiku direct** — mechanical execution from a clear spec already in hand

### Handoff trigger phrases

When the user's request matches one of these shapes, **propose a handoff before starting work** (don't auto-invoke — confirm first):

- "Create N [peripheral entities]" where N ≥ 3 — Mode A candidate
- "Format / convert / normalize these files" — Mode B candidate
- "Apply this template to..." — Mode A candidate
- "Clean up / standardize / batch update..." — Mode B candidate (or Python script — check both script locations first; see Mode B below)
- "Generate summaries for sessions X through Y" — Mode A candidate
- End-of-session: "wrap up / write the summary" — Mode A handoff to Haiku from Sonnet

If unsure whether the work qualifies, ask: *"This looks like it could be a Mode A/B handoff — want me to structure it that way, or execute on this model?"*

### When to hand off

Handoff splits work between a judgment model (Opus or Sonnet) and an execution model (Haiku) by emitting instructions for Haiku to execute in a separate session. **Cost savings only materialize when the source model's output volume drops meaningfully** — i.e. when it emits a compact spec that Haiku expands, or compact instructions Haiku applies mechanically. Handoff of full file content (source generates the actual file text, Haiku just writes it) is NOT cheaper — the content gets emitted twice and the second emission is pure overhead.

Use handoff when:
- The output is templated or mechanical — filling slots, applying transforms, format conversion
- The spec fits in a paragraph and any competent assistant could execute it from the brief
- You'd accept Haiku-quality output without wanting to rewrite

Keep on source when:
- Voice, tone, or per-sentence judgment matters
- The content depends on grounding in prior canon
- Math, multi-step logic, or worldbuilding consistency is central
- You'd second-guess the output if Haiku produced it

**Test:** If I wrote the prompt for this as a brief, would a competent assistant produce roughly the same output? If yes → handoff. If no → keep on source.

### Source model for handoffs

- **Opus → Haiku** — when the spec itself needs Opus-grade decisions (peripheral content for central characters, lore-sensitive batch work)
- **Sonnet → Haiku** — when the spec is routine creative work (session summary formatting after a Sonnet-run session, batch peripheral NPCs from established templates, mid-session mechanical transforms). This is the common case; Sonnet writes specs fine.

### Two handoff modes

**Mode A — Templated Expansion**
Source emits compact specs (~200 tokens). Haiku expands each using a known template.
Good for: peripheral NPCs, filler location descriptions, batch background characters, session summary formatting from beat lists.

**Mode B — Mechanical Transformation**
Source identifies what to change. Haiku executes mechanical edits.
Good for: format conversions, case-normalizing filenames, batch metadata updates, applying a structural change to many files.
*Often, a Python script is the right tool here instead. Scripts live in two places: `Python/` (`corpus-infra` — index builder and MCP servers, visible to you) and `D:\Claude\projects\corpus-tools\` (maintenance and conversion scripts, **not** visible to you — ask the user or hand to code-claude). Each script includes header comments describing what it does and how to run it. To write a new script, load `Python_Scripts_Protocol.md` (terse rules) or `System_Documentation/Python_Scripts.md` (full conventions with reasoning).*

### Source Phase

Output a HANDOFF BLOCK with:
- MODE and pre-formatted git commit message
- Per-file: path + spec (Mode A) or path + operation + params (Mode B)

**Source must not call filesystem MCP tools during this phase.** Tool calls during handoff defeat the purpose.

### Handoff Block Format — Mode A (Templated Expansion)

```
===HANDOFF START===
MODE: templated_expansion
COMMIT: "Category: Subject | Details | Date"
TEMPLATE: Core_Rules/Templates/[Template_Name].md

---FILE 1---
PATH: World_Building/[Setting]/.../New_NPC.md
SPEC:
  name: Tam Ferrow
  role: town watch sergeant
  cultural_context: regional standard
  notable_trait: limp from old wound
  voice_note: gruff but fair
---END FILE---

[additional files...]
===HANDOFF END===
```

### Handoff Block Format — Mode B (Mechanical Transformation)

```
===HANDOFF START===
MODE: mechanical_transform
COMMIT: "Category: Subject | Details | Date"

---FILE 1---
PATH: Archive/old_session.txt
OPERATION: replace_meta_with_yaml
PARAMS:
  yaml_frontmatter:
    name: Riverside_Session_03
    keywords: [session, riverside]
    description: Session summary converted from legacy header format
---END FILE---

[additional files...]
===HANDOFF END===
```

### Haiku Phase

1. Receive handoff block
2. For each entry: apply template (Mode A) or execute operation (Mode B) with `filesystem:write_file` or `filesystem:edit_file`
3. Verify each per FILE CREATION VERIFICATION
4. Propose git commit using COMMIT line
5. Confirm: `[HANDOFF COMPLETE] X files written`

### Quality check

Spot-check 1-2 files visually before committing. If output quality is off, redo on source — handoff is false economy if it triggers a rewrite.

---

ERROR HANDLING
==============

**3-Strike Rule:** If any filesystem command fails 3 times consecutively → HALT, display error details, await user guidance. No automatic retries past 3.

**No Delete Function:** Use `filesystem:move_file` to `Trash/`. If filename exists in Trash/, search for `Filename*` and increment: `Filename_{n+1}.ext`.

## FILESYSTEM ERROR RECOVERY

**File not found**: 
1. `filesystem:list_directory` to verify parent folder
2. `filesystem:search_files` with filename pattern
3. Check exact Windows path format

**Tool parameter errors**:
1. Verify schema with `tool_search filesystem` (or load `file_system_reference.md`)
2. Confirm `oldText` exact match for edits

**Write verification**: see FILE CREATION VERIFICATION above — single canonical pattern.

**Folder rename / move EPERM (Windows)**: `filesystem:move_file` on a folder occasionally fails with `EPERM: operation not permitted` even when the folder clearly exists and the destination is clear. This is Windows lock contention — typically Obsidian, an editor, antivirus, or a file watcher holding a handle on something inside the folder. **Workaround:**
1. `filesystem:create_directory` for the new path
2. `filesystem:move_file` each child (file or subfolder) individually into the new path
3. `filesystem:move_file` the now-empty original to `Trash/`

Do NOT count the EPERM failure against the 3-strike rule — it is a known environmental issue with a known workaround. If the workaround itself fails for the same folder, then 3-strike applies.

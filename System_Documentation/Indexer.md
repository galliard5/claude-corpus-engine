---
name: Indexer System
type: documentation-component
keywords: [indexer, build_indexes, cfg_loader, indexer.cfg, refresh_indexes, rebuild, fts5, sqlite, os.walk, fnmatch]
description: Full reference for the index builder - build_indexes.py, cfg_loader.py, indexer.cfg, index_tools_mcp_server.py, and refresh_indexes.bat.
---

# Indexer System

The index builder is five files that act as one system:

- **`Python/indexer.cfg`** — Plain-text config. Controls what gets indexed and how.
- **`Python/cfg_loader.py`** — Generic .cfg parser. Format-aware, application-agnostic.
- **`Python/build_indexes.py`** — The builder. Reads cfg, walks the corpus once, writes three outputs.
- **`Python/index_tools_mcp_server.py`** — MCP server. Wraps the builder as a subprocess so Claude can call it.
- **`Python/refresh_indexes.bat`** — Manual fallback. Double-click from Explorer.

All three derived artifacts (`directory_index.md`, `directory_index_with_files.md`, `search_index.db`) are produced by a single `os.walk` in `build_indexes.py`. The directory trees and the FTS/meta tables are dropped and rebuilt from scratch every run — sub-second, so incremental complexity isn't worth it. The **one exception is the embedding pass**: document vectors are cached by content hash (`embed_cache`) and survive rebuilds, so only new or changed files are re-embedded. The embed step is ~99% of build time on a cold cache, which is why it alone is incremental. See *Performance* below.

## The cfg file

`Python/indexer.cfg` is parsed by `cfg_loader.py` into a dict of sections. Format:

```cfg
[section_name]
# Line beginning with # is a comment.
key = value          # inline comment supported on key=value lines
bare pattern line    # any line without '=' is a pattern
```

### `[paths]`

```cfg
[paths]
root_directory = D:\claude\filesystem\
index_directory = /index/
```

- `root_directory` — Absolute path to the corpus root. Required. Overridable at runtime by the `CORPUS_ROOT` env var (Docker uses this).
- `index_directory` — Where all derived artifacts are written. Three forms:
  - Blank → defaults to `root_directory` (legacy behavior)
  - Starts with `/` or `\` → root-relative (`/index/` → `root_directory\index\`)
  - Anything else → treated as an absolute path

Current setting writes all three artifacts (`directory_index.md`, `directory_index_with_files.md`, `search_index.db`) to `D:\claude\filesystem\index\`.

### `[directory_index]`

Controls which directories appear in `directory_index.md` and `directory_index_with_files.md`.

```cfg
[directory_index]
mode = blacklist

.git/
.obsidian/
.vscode/
.github/
__pycache__/
node_modules/
Trash/*.*       # visible in tree, contents suppressed
```

- `mode` — `blacklist` (default) or `whitelist`.
- Bare patterns are directory names.

**Pattern syntax:**

| Pattern        | Effect                                                                                          |
|----------------|-------------------------------------------------------------------------------------------------|
| `dirname/`     | Directory and all contents fully excluded — won't appear in any output.                         |
| `dirname/*.*`  | Directory **appears in the tree** but its files are not listed, and its subtree isn't indexed. |
| `dirname`      | Bare name, treated as `dirname/`. Equivalent to fully excluded.                                 |

The `dirname/*.*` form is used for `Trash/` — we want Claude to know the folder exists (so it doesn't try to create a duplicate), but listing every soft-deleted file would bloat the index.

### `[search_index]`

Additional exclusions for `search_index.db` only. These directories *still appear* in the directory tree — they're just not searchable.

```cfg
[search_index]
Python/
[project-specific-dir]/
[ingest-folder]/
[binary-assets]/
```

Always blacklist; the cfg has no `mode` for this section. The entries in the shipped `indexer.cfg`
reflect whatever *this* corpus wants kept out of search — typically ingest folders, binary asset
dumps, and generator scratch directories. Adjust freely; it's a one-line edit per directory.

### `[file_types]`

Which file extensions are eligible for search indexing.

```cfg
[file_types]
mode = whitelist

*.md
*.txt
*.svg
*.jpg
```

- `mode` — `whitelist` (only listed are indexed) or `blacklist` (all except listed).
- Patterns are `fnmatch` globs against lowercased filenames.

### `[context_limits]`

How many lines of each file get read into the search index `content` column.

```cfg
[context_limits]
default = -1
*.jpg = 0
*.svg = 4
*.aimap.svg = line_8
```

| Value     | Meaning                                                                                                |
|-----------|--------------------------------------------------------------------------------------------------------|
| `-1`      | Read the entire file. Default.                                                                         |
| `0`       | Skip content entirely — path and metadata only. Use for binaries/images.                              |
| `N` (int) | Read the first N lines.                                                                                |
| `line_N`  | Read line N of the file, extract the first integer found there, use that as the line limit.          |

The `line_N` sentinel is the cleverest part. Worldographer SVG maps declare their own indexable depth on line 8 (the `claude_section_end` of the embedded YAML). So `*.aimap.svg = line_8` means "read line 8, get the number, that's how far down this specific file you should read." Lets the file decide its own indexing depth.

Matching is fnmatch glob, last-match-wins. So general patterns should appear before specific ones in the cfg.

## `cfg_loader.py`

Stand-alone generic .cfg parser. Has no knowledge of indexer-specific section names — `build_indexes.py` is what interprets `[paths]`, `[directory_index]`, etc.

**API:**
```python
from cfg_loader import load_cfg
cfg = load_cfg("indexer.cfg")
mode = cfg["directory_index"]["settings"].get("mode", "blacklist")
patterns = cfg["directory_index"]["patterns"]
```

**Auto-typing of values:**
- `"-1"` → `-1` (int)
- `"4"` → `4` (int)
- `"line_8"` → `("line", 8)` (tuple)
- Anything else → stripped string

**Failure mode:** Malformed lines log a warning and are skipped. `FileNotFoundError` is the one exception that always raises — there's nothing meaningful to do if the cfg is missing.

**CLI:** Run directly to pretty-print a parsed cfg:
```cmd
python cfg_loader.py indexer.cfg
```

## `build_indexes.py`

Single entry point. Flow:

1. Parse CLI args (`--cfg`, `--console`, `--no-pause`).
2. Load cfg via `cfg_loader.load_cfg`.
3. Resolve `root` and `index_dir` (env var overrides cfg).
4. Parse the four cfg sections into runtime structures.
5. Single `os.walk` of the corpus (`walk_and_collect`) — produces `dir_entries` and `search_files` in one pass.
6. Render directory trees with `render_dirs_only` and `render_with_files`.
7. Assemble each `.md` file with YAML frontmatter (`assemble_dirs_only`, `assemble_with_files`).
8. Build the SQLite database (`build_search_db`):
   - Drop and recreate `corpus_fts` (FTS5 virtual table) and `corpus_meta` (regular table). When the embedding deps are present, also drop any stale `corpus_vec` and recreate it (unless `--no-vectors`).
   - For each search-eligible file: parse YAML frontmatter, compute the `category` from path parts, populate `corpus_fts`/`corpus_meta` in a parameterized INSERT, and (if building vectors) stash `(rowid, content_hash, embed_text)`.
   - After the FTS inserts, build `corpus_vec` by shared rowid — reusing cached embeddings for unchanged content (`embed_cache`, keyed by `content_hash`) and running the model only on new/changed docs. Stale cache entries are pruned each build. An embedding failure warns and leaves the FTS index intact.
9. Print summary (including vectors indexed) and (unless `--no-pause`) wait for Enter.

The vector pass is **optional and gated on `embedding.AVAILABLE`** (`Python/embedding.py`). Where `fastembed`/`sqlite-vec` aren't installed — e.g. a Docker image not yet rebuilt — it's skipped silently and only the FTS index is produced. The `embed_cache` carries a one-row identity stamp (model + dim); a model or dimension change auto-invalidates the whole cache so vectors of the wrong shape are never reused. See `Search_Server.md` for the `corpus_vec` and `embed_cache` schema.

**Pruning logic:** `walk_and_collect` mutates `dirnames` in-place inside `os.walk`, which `os.walk` honors. That means excluded subtrees are never descended — the script doesn't waste time walking through `Trash/` to filter its files out later.

**Performance:** The FTS-only rebuild takes ~0.5 seconds on the current corpus. The embedding pass dominates a **cold** build — ~40 seconds for ~500 docs on CPU (bge-small), almost all of it the batched encode. With the `embed_cache` warm it only re-embeds changed files, so a rebuild after editing a handful of files is back to ~0.5–0.6 seconds, and an unchanged-corpus rebuild runs zero model calls. The build summary reports `embedded N new, reused M, pruned K stale` so the split is visible. Use `--no-vectors` for a guaranteed FTS-only refresh. Cold-cache builds still happen on the first run after a model/dim change (cache auto-invalidated) or a fresh DB. Not profiled for >10× scale; the obvious wins are parallel file reads and (for cold builds) GPU batching.

**Invocation:**
```cmd
python build_indexes.py                  # normal run (builds vectors if deps present)
python build_indexes.py --cfg other.cfg  # use a different cfg
python build_indexes.py --console        # console output, skip file writes (dry run)
python build_indexes.py --no-pause       # unattended (used by index-tools and refresh_indexes.bat)
python build_indexes.py --no-vectors     # FTS5 only, skip the embedding pass
```

## `index_tools_mcp_server.py`

Custom MCP server. Exposes one tool to Claude:

### `rebuild_indexes(load=None)`

Runs `python build_indexes.py --no-pause` as a subprocess and returns a formatted summary. The `load` parameter optionally appends freshly-built content to the response in the same tool call:

| `load` value      | Effect                                                                                  |
|-------------------|-----------------------------------------------------------------------------------------|
| `None` (default)  | Rebuild only; return the summary.                                                       |
| `"directory"`     | Append `directory_index.md` (Claude section) to the response.                          |
| `"with_files"`    | Append `directory_index_with_files.md` (Claude section) to the response.               |
| `"search_status"` | Append file count and last-built timestamp for `search_index.db`.                       |

**Why subprocess instead of in-process import?** Three reasons:
1. The MCP server stays small and stable. The heavyweight code lives in a script that exits cleanly each run.
2. The subprocess gets fresh module state every call — no stale globals, no cached cfg.
3. Server crashes during a rebuild can't poison the server's own state.

**Why not invoke `refresh_indexes.bat`?** The bat ends with `pause`, which would hang the subprocess waiting for a keypress. The bat is for humans double-clicking from Explorer; the server uses the Python script directly.

**Hardcoded paths in this file:**
```python
ROOT       = Path(os.environ.get("CORPUS_ROOT", r"D:\claude\filesystem"))
INDEX_DIR  = ROOT / "index"
BUILDER    = PYTHON_DIR / "build_indexes.py"
DIRECTORY_INDEX            = INDEX_DIR / "directory_index.md"
DIRECTORY_INDEX_WITH_FILES = INDEX_DIR / "directory_index_with_files.md"
SEARCH_DB                  = INDEX_DIR / "search_index.db"
```

These must stay in lockstep with `indexer.cfg [paths] index_directory` and with `search_mcp_server.py DB_PATH`. If the index directory ever changes, **all three places** need to be edited together, then Claude Desktop restarted.

## `refresh_indexes.bat`

Manual fallback. Double-click from Explorer to rebuild without going through Claude.

The bat invokes `python build_indexes.py` and pauses at the end so the user can see the output. The `--no-pause` flag is used by the MCP server but not by the bat — humans want to see the summary.

## When to rebuild

The index does not auto-update. Triggers for a rebuild:

- New files or directories created.
- Files moved or renamed.
- Frontmatter edits (especially `type:` or `keywords:` changes that affect search ranking).
- Suspicion that the index is stale (predicted path lookups failing, search empty for known content).

For mid-session structure drift, call `index-tools:rebuild_indexes` directly from Claude. For end-of-session cleanup, the bat or the next session's startup will pick it up.

See `Search_Server.md` for what the database structure looks like and how `search_corpus` consumes it.

---
name: Corpus Search Server
type: documentation-component
keywords: [search, fts5, sqlite, bm25, corpus_meta, corpus_vec, embed_cache, type_filter, missing_filter, category_filter, porter, stemming, search_mcp_server, vector, hybrid, semantic, rrf, sqlite-vec, fastembed, embedding, limit, timeout, query-guard]
description: Full reference for search_mcp_server.py - FTS5 schema, BM25 weights, the three filters, the corpus_meta hygiene table, and the vector/hybrid (RRF) semantic search lane.
---

# Corpus Search Server

`Python/search_mcp_server.py` is a custom MCP server exposing ranked search over the corpus. The index is `index/search_index.db` — a SQLite file with: an FTS5 virtual table for full-text ranking, a regular table for structured field filtering, and (optionally) a sqlite-vec virtual table for semantic vector search. The `mode` parameter picks which lane(s) answer a query — see **Search modes** below.

## Database schema

Three query-time tables plus a build-time cache. FTS5 handles full-text ranking; SQL equality on `corpus_meta` handles structured field filters that FTS5's tokenizer would mangle; `corpus_vec` holds embeddings for semantic K-NN. `embed_cache` is consulted only at *build* time (never by this server) so rebuilds skip re-embedding unchanged docs. The vector table and cache are optional — built only when the embedding deps are installed.

### `corpus_fts` (FTS5 virtual table)

| Column       | Indexed? | BM25 weight | Source                                  |
|--------------|----------|-------------|-----------------------------------------|
| path         | no       | —           | Relative path from corpus root          |
| name         | yes      | 10×         | YAML frontmatter `name` field           |
| keywords     | yes      | 5×          | YAML frontmatter `keywords` (joined)    |
| description  | yes      | 3×          | YAML frontmatter `description`          |
| category     | yes      | 0×          | Directory portion of the relative path  |
| content      | yes      | 1×          | Markdown body (frontmatter stripped)    |

**Why `path` is UNINDEXED:** A top-level setting or campaign folder name appears in thousands of paths. Indexing it would drown content matches. Path is stored for retrieval but excluded from search.

**Why `category` has weight 0:** It's indexed so `category:"[Faction]"` column filters work, but a weight of 0 means a bare `[Faction]` query doesn't get inflated by every file under that directory.

**Tokenizer:** `porter unicode61`. The porter stemmer means `transform`, `transformed`, `transformation` all stem to the same root. Unicode61 handles accented characters reasonably well.

### `corpus_meta` (regular SQL table)

| Column                  | Type      | Source                                              |
|-------------------------|-----------|-----------------------------------------------------|
| path                    | TEXT PK   | Joins to `corpus_fts.path`                          |
| doc_type                | TEXT      | YAML frontmatter `type:` field (exact string)       |
| missing_name            | INTEGER   | 1 if `name:` absent or empty                        |
| missing_keywords        | INTEGER   | 1 if `keywords:` absent or empty                    |
| missing_description     | INTEGER   | 1 if `description:` absent or empty                 |
| missing_type            | INTEGER   | 1 if `type:` absent or empty                        |

Only populated for `.md` files. Non-markdown files get an empty row so the JOIN doesn't drop them.

**Why a second table at all?** FTS5's tokenizer splits on hyphens and underscores. The value `setting-document` tokenizes as `["setting", "document"]` — searching `type:"setting-document"` doesn't work, and you can't filter on a column with an unsearchable value. SQL equality on a regular table sidesteps the whole problem.

**Why IN subqueries, not JOIN conditions?** FTS5 has a known quirk where non-MATCH WHERE clauses on joined tables get silently ignored — the query runs but the filter does nothing. Wrapping `corpus_meta` lookups as `f.path IN (SELECT path FROM corpus_meta WHERE doc_type = ?)` is the workaround.

### `corpus_vec` (sqlite-vec virtual table, optional)

| Column     | Type           | Source                                              |
|------------|----------------|-----------------------------------------------------|
| rowid      | INTEGER        | **Shared with `corpus_fts`** (same row = same doc)  |
| embedding  | float[384]     | Embedding of name + keywords + description + body   |

Built by `build_indexes.py` in the same pass as `corpus_fts`, only when the embedding deps (`fastembed`, `sqlite-vec`) are installed. Each document is embedded with **BAAI/bge-small-en-v1.5** (384-dim, CPU) — see `Python/embedding.py`, which isolates the optional deps so the rest of the system degrades to FTS-only when they're absent (`embedding.AVAILABLE`).

**Why a shared rowid?** `corpus_fts` assigns rowids sequentially on insert, so `corpus_vec` reuses the same rowid per document. That lets the two lanes be fused (or a vector hit's metadata fetched) by rowid without a separate id column. **Invariant:** the build always drops a stale `corpus_vec` before rebuilding `corpus_fts`, so the table never carries vectors whose rowids no longer line up (e.g. after a `--no-vectors` run).

**Cap:** only the first ~2000 chars of a document are embedded (bge-small's ~512-token window); metadata leads so a doc stays findable even when the body is clipped.

### `embed_cache` (regular SQL table, build-time only)

| Column     | Type      | Source                                                      |
|------------|-----------|------------------------------------------------------------|
| hash       | TEXT PK   | SHA-256 of the exact text fed to the embedder              |
| embedding  | BLOB      | Serialized float32 vector (the same blob `corpus_vec` stores) |

Plus a one-row `embed_cache_info(model, dim)` identity stamp. **Unlike every other table, `embed_cache` is not dropped on rebuild** — it persists so `build_indexes.py` can reuse vectors for unchanged content and run the model only on new/changed docs (the embed pass is ~99% of cold build time). Keyed by content hash, so identical bodies embed once and any edit naturally misses the cache. Stale entries are pruned each build; a model or dimension change wipes the whole cache via the identity stamp. **This query-time server never touches `embed_cache`** — it's purely a build-time optimization. See `Indexer.md` → *Performance*.

## The `search_corpus` tool

```python
search_corpus(
    query: str,
    limit: int = 10,
    mode: str = "fts",          # "fts" | "vector" | "hybrid"
    category_filter: str | None = None,
    type_filter: str | None = None,
    missing_filter: str | None = None,
    show_sections: bool = True,
) -> str
```

All filters compose with AND and apply across every mode. Combine any or all in one call.

### Search modes (`mode`)

| Mode       | Lane                              | Query is…        | Score label  | Use when                                          |
|------------|-----------------------------------|------------------|--------------|---------------------------------------------------|
| `"fts"`    | FTS5 BM25 (default)               | FTS5 expression  | `score`      | You know the terms; exact/keyword recall.         |
| `"vector"` | sqlite-vec K-NN over embeddings   | plain language   | `similarity` | Meaning-similar docs with no shared words.        |
| `"hybrid"` | fts + vector, fused with RRF      | plain or FTS5    | `rrf`        | General recall; half-remembered / paraphrased.    |

**Reciprocal Rank Fusion (hybrid):** each candidate scores `sum(1 / (60 + rank))` over the lanes it appears in (`rrf_k=60`, Cormack 2009). RRF fuses on *rank position*, not raw scores, so the incomparable scales of BM25 and L2 distance don't need normalizing. Each lane is oversampled (`limit × 5`) before fusing so both get to vote before anything is trimmed. The fts row's highlighted snippet is preferred for display; vector-only hits show a content-prefix snippet.

**Graceful fallback:** if `mode` is `vector`/`hybrid` but the deps aren't installed *or* the index has no `corpus_vec` table, the server falls back to `fts` and appends a note to the result header (e.g. `[mode: fts, index has no vector table (rebuild to enable) - using fts]`). It never errors out over a missing vector lane.

**Vector similarity score:** L2 distance on the (unit-norm) embeddings is mapped to `1 - dist/2`, giving a 0–1 similarity where higher is better — consistent with the "higher = better" convention of the BM25 magnitude.

### Query syntax (FTS5)

| Form                       | Effect                                                                |
|----------------------------|-----------------------------------------------------------------------|
| `warden`                   | Single term, porter-stemmed (matches warden, wardens).                |
| `warden security`          | Both terms present (implicit AND).                                    |
| `warden OR steward`        | Either term.                                                          |
| `"charter of passage"`     | Exact phrase. Escape inner quotes by doubling: `""`.                  |
| `petition NOT rejected`    | Boolean exclusion.                                                    |
| `transform*`               | Prefix match (transformed, transformation, transformative).           |

Inputs are wrapped in parentheses internally for predictable operator precedence. Embedded `"` in user input is escaped (doubled) before being passed to FTS5.

### `category_filter` — FTS5 column filter on path

```python
category_filter="[Faction]"      # only files under .../[Faction]/...
category_filter="Senior_Staff"   # only the Senior_Staff subfolder
category_filter="[Region]"       # only one region
```

Implemented as an FTS5 column filter (`category:"[Faction]"`) added to the MATCH expression. Works on path segments only — not arbitrary substrings.

### `type_filter` — SQL equality on `corpus_meta.doc_type`

```python
type_filter="setting-document"  # exact match
type_filter="character"
type_filter="session"
```

Case-sensitive, exact-match. Hyphens are fine (this is the whole reason `corpus_meta` exists).

### `missing_filter` — corpus hygiene

Finds files where a required frontmatter field is missing or empty. The most useful corpus-hygiene tool.

```python
missing_filter="type"           # files with no type:
missing_filter="description"    # files with no description:
missing_filter="keywords"       # files with no keywords:
missing_filter="name"           # files with no name:
```

Valid values: `name`, `keywords`, `description`, `type`. Validated server-side before touching the DB.

### Combining filters

All three filters compose freely:

```python
# Files mentioning both terms, restricted to setting docs
search_corpus("warden charter", type_filter="setting-document")

# Files in one faction's subtree about transformation that still need a type field
search_corpus("transformation", category_filter="[Faction]", missing_filter="type")

# All files in one region missing type (use any broad query)
search_corpus("*", missing_filter="type", category_filter="[Region]")
```

For "all files where X is missing" without a content query, you still need a query string — pass any broad term or wildcard.

## The `get_section` tool

```python
get_section(path, heading=None, level=2) -> str
```

Returns a single section of an indexed document instead of the whole file. It exists because a search hit on a large reference document used to force a whole-file read to reach one heading: the daily-life toolkit measured during development is ~7,900 tokens, and a typical question wants one ~400-token section of it. Measured end-to-end on a representative query, the search-plus-read round trip went from ~9,400 tokens to ~2,200.

**This trims by selection, not summarisation.** Section bodies are verbatim slices of the stored content — verified across every file of the 581-document corpus this was developed against, by reassembling the split and checking it against the source. Nothing is paraphrased, compressed, or rewritten. That distinction is the whole point: lossy compression of lore prose costs voice, which is the thing the corpus exists to preserve.

**How sections are derived.** ATX headings (`## Title`) at the requested `level`, with deeper headings kept inside their parent, and fenced code blocks skipped so a `##` in an example doesn't split a document. Text before the first heading becomes a leading section titled by the document's H1, falling back to the frontmatter `name`, since a large share of files carry no H1 at all (220 of 581 in the development corpus). Nothing is stored: sections are computed on each call from the `content` column.

**Heading matching** runs in tiers, first unambiguous one winning: exact (normalized) → prefix → substring. Normalization casefolds, collapses whitespace, and folds em/en dashes and curly quotes to ASCII, so `"estate's week - supply"` resolves `"The Estate's Week — Supply Cadence"`. Ambiguity returns the candidate list rather than a guess; no match returns the full section list. Omitting `heading` lists sections and their sizes without returning any body.

**The `Sections:` line.** `search_corpus(show_sections=True)` — the default — adds a manifest of section titles and rough token costs to hits large enough to justify it. Gates live in `search_mcp_server.py`:

| Constant | Value | Why |
|---|---|---|
| `_MANIFEST_MIN_CHARS` | 12,000 (~3k tokens) | A manifest costs ~75 tokens per hit; at 10 hits that's ~750 tokens per search. Below ~3k tokens a whole-file read is cheaper than the manifest plus a follow-up call — and for the character sheets that dominate the 5–12k band it's also the *better* read, since you want the whole character, not one heading of them. Roughly one file in six clears the gate (98 of 581 in the development corpus). |
| `_MANIFEST_MIN_SECTIONS` | 2 | One section is the whole document. |
| `_MANIFEST_MAX_SECTIONS` | 14 | Caps a pathological outline document; overflow keeps the largest sections and notes the count dropped. |

**When not to use it.** Whole-file reads remain correct when the document's shape is the point — establishing voice, checking tone, or any task where surrounding material matters. Section retrieval answers questions; it does not replace reading.

## The `index_status` tool

```python
index_status() -> str
```

Returns the DB path, total file count, **vector-lane status** (vector count + model, or "not built"), and last-built timestamp. Use to verify freshness — and whether semantic/hybrid search is available — before relying on results.

## Result format

Each result includes:
- A score tagged by mode: `score` (BM25 magnitude — FTS5 returns negative, the tool flips to positive), `similarity` (0–1, vector mode), or `rrf` (fused, hybrid mode)
- Relative path
- `name`, `keywords`, `description`, `type` from frontmatter
- `Missing:` list if any required fields are absent
- A snippet with `** **` markers around matched terms

## Limitations

- **Stale between rebuilds.** No file watcher. The same staleness model as `directory_index.md` — rebuild after edits.
- **`fts` mode is keyword-only.** "Horned creature" won't find a minotaur NPC in `fts` unless that phrase is in his file — use `mode="vector"` or `"hybrid"` for meaning-based recall. (Vector recall is only as good as the embedding model; bge-small is small and fast, not state-of-the-art.)
- **Vector lane needs a vectors-built index.** If `corpus_vec` is absent (deps not installed, or built `--no-vectors`), vector/hybrid silently fall back to `fts`. Check `index_status`.
- **Frontmatter required for best ranking.** Files without YAML get indexed (filename used as name) but lose the high-weight metadata fields. Run `missing_filter="name"` to find them.
- **Apostrophes are tokenizer separators.** "Keller's" indexes as `["keller", "s"]`. Searching `Keller` finds it; quoted `"Keller's"` may not.
- **`type_filter` is exact match.** `type_filter="setting"` will NOT match files with `type: setting-document`. Use the full value.
- **`limit` is capped at 200.** A value above the ceiling (or below 1) returns a diagnostic error instead of results — see *Security posture*. The default of 10 is unaffected; this only bites a deliberately huge request.
- **Indexing is per-file, not per-section.** `get_section` splits at read time, so retrieval is still ranked at document granularity — see *Deferred: section-granular indexing* below.

## Deferred: section-granular indexing

**Status: not started. Revisit once `get_section` and the `Sections:` manifest have real usage behind them** (added 2026-09-05).

`corpus_fts` holds one row per file, and `corpus_vec` one embedding per file. Section-granular indexing would make each `##` section its own row. Two things would improve:

- **BM25 ranking.** A 30k-char toolkit and a 2k-char character sheet are currently scored on the same footing; BM25's length normalization handles that only crudely. Shorter units would let a section that is genuinely *about* the query outrank a long document that merely mentions it.
- **The vector lane, more so.** A single 384-dim embedding averaged over a whole document loses whatever made any one part of it distinctive — an 8k-token GM toolkit collapses to a vague centroid of its overall subject, and the section that would actually answer the query has no separate representation to be found by. Per-section embeddings are the standard fix and would likely matter more than the ranking gain.

**Costs, which are why it's deferred:** a `corpus_fts` schema change, a full reindex, a rewrite of the insert path in `build_indexes.py`, an `embed_cache` keying change (hashes are per-file today), a `check_schema_drift.py` update, and shifted ranking across the whole corpus — meaning every saved query and habit built on current result ordering shifts underneath it. The embedding cost also multiplies by roughly the mean section count.

**Decide on evidence, not enthusiasm.** The question to answer first is how often callers actually reach for a section versus the whole file once the manifest is in front of them. If `get_section` sees little use, per-file indexing is fine and this is wasted churn. If it becomes the default access pattern, the ranking layer should match it. `search_mcp_server.py` carries a TODO pointing here.

## Security posture

- DB opened **read-only** via SQLite URI (`?mode=ro`). The server cannot write to the database.
- All user input passed via SQLite parameter binding (`?` placeholders). No string concatenation, no SQL injection surface.
- **No filesystem access.** The DB path is hardcoded and the server opens no files. `get_section` takes a `path`, but it is an index key, not a filesystem path: it is matched for equality against `corpus_fts.path` and the body is served from the stored `content` column. A path not in the index returns "not in the index" (with near-miss suggestions on the basename), so traversal sequences, absolute paths, and anything outside the corpus are unreachable by construction rather than by filtering. `level` is whitelisted to 1–6.
- `missing_filter` is whitelisted server-side against `{"name", "keywords", "description", "type"}`. Any other value is rejected before touching SQL.
- `mode` is whitelisted against `{"fts", "vector", "hybrid"}`. The sqlite-vec extension is loaded only when a vector/hybrid query needs it, with `enable_load_extension` toggled back off immediately after the load. Embedding runs in-process (local model, no network at query time); the vector lane adds no new external surface.
- **Runaway guards.** `limit` is capped at `_MAX_LIMIT` (200) — a higher or non-positive value returns a diagnostic error rather than running. Every query runs under a `_QUERY_TIMEOUT_S` (15s) wall-clock guard (a SQLite progress handler that aborts the statement); an overrun returns a timeout error. Both are generous backstops against a pathological call (`limit=100000`, a CPU-pinning query), not normal-use limits, and the error messages name the constant + file so the caps are easy to find and tune in `search_mcp_server.py`.

See `Security_Audit.md` for the full audit walkthrough.

## Hardcoded paths

```python
_CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"D:\claude\filesystem"))
DB_PATH = _CORPUS_ROOT / "index" / "search_index.db"
```

`CORPUS_ROOT` env var lets Docker override without editing source. The hardcoded fallback is for native runs. **Must stay in lockstep** with `indexer.cfg [paths] index_directory` and with `index_tools_mcp_server.py SEARCH_DB`.

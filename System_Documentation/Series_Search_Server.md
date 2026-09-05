---
name: Series Search Server
type: documentation-component
keywords: [series, search, fts5, sqlite, chapters, prose, reference, series_search_mcp_server]
description: Full reference for series_search_mcp_server.py — FTS5 schema, the three tools, and how to build a compatible chapter database.
---

# Series Search Server

`Python/series_search_mcp_server.py` is a custom MCP server exposing FTS5 keyword search over an **external prose-series database** — long-form reference material held outside the corpus proper and consulted during play. A novel series, a web serial, a body of transcripts: anything chapter-shaped and large enough that loading it into context is impractical.

The server runs in the existing Docker compose stack on port 8003. **It ships with no database — you supply one.** See *Building a compatible database* below for the schema it expects, and `World_Building/Project_Profile.md` > SERIES SEARCH BINDING for which database this particular corpus mounts and why.

## Database schema

Two tables per database. External-content FTS5 for ranked keyword search; the `chapters` table for structured retrieval.

### `chapters` (regular SQL table)

| Column      | Type    | Notes                                                                      |
|-------------|---------|----------------------------------------------------------------------------|
| id          | INTEGER | Primary key; also the FTS5 `content_rowid`                                 |
| seq         | INTEGER | Insertion order — fallback sort when `sort_num` is NULL                    |
| chapter_num | TEXT    | Chapter identifier, extracted from title (e.g. "499", "CLASSIFIED", "0.1.1") |
| sort_num    | REAL    | Numeric sort key. NULL for chapters without extractable numbers            |
| title       | TEXT    | Full chapter title as it appears in the source text                        |
| arc         | TEXT    | Arc name if detected in the title; NULL otherwise                          |
| character   | TEXT    | Focal character name if in parentheses after the chapter number; NULL otherwise |
| file_name   | TEXT    | Filename of the per-chapter `.txt` file                                    |
| content     | TEXT    | Full chapter text including title line                                      |
| line_start  | INTEGER | Line number in the source `.txt` where the chapter begins                  |
| line_end    | INTEGER | Line number where the chapter ends                                         |
| series      | TEXT    | Series identifier — only present in databases that merge multiple series   |

**Sort order:** `ORDER BY sort_num NULLS LAST, seq`

### `chapters_fts` (FTS5 external-content table)

Indexed columns: `chapter_num`, `title`, `arc`, `character`, `content`. The FTS5 table mirrors `chapters` via external content — the `chapters` table is the source of truth; `chapters_fts` is rebuilt when the DB is regenerated.

**Tokenizer:** `unicode61` (default). No porter stemming — terms must match literally. Wildcard prefix (`mech*`) and exact-phrase quoting both work.

**FTS5 quirk — hyphens:** FTS5 treats `-` as the NOT operator outside of phrase quotes. `X-318` is parsed as `X NOT 318`. Two reliable workarounds: drop the hyphen (`X318`), or use a quoted phrase with a space (`"X 318"`). The space form is safer when you need adjacency.

**FTS5 quirk — dots:** The `unicode61` tokenizer treats `.` as a separator. `Vel.nir` in a query won't tokenize as a single term — use `Vel nir` (space) instead. The dot in the source text is also treated as a separator at index time, so the terms are stored as adjacent tokens and the space query finds them correctly.

## The three tools

### `search_chapters`

```python
search_chapters(
    query: str,
    db: str | None = None,
    series: str | None = None,
    limit: int = 10,
) -> str
```

FTS5 keyword search across `chapter_num`, `title`, `arc`, `character`, and `content`. Returns ranked results with chapter number, title, arc, series (if merged DB), and a 20-token snippet with `[matched]` highlighting.

**`query` — FTS5 expression:**

| Form                     | Effect                                                            |
|--------------------------|-------------------------------------------------------------------|
| `dreadnought`            | Single term (literal, no stemming)                               |
| `dreadnought convoy`     | Both terms present (AND)                                         |
| `"heavy plasma"`         | Exact phrase (plain words only — no hyphens or dots inside)      |
| `dreadnought OR frigate` | Either term                                                      |
| `dreadnought NOT derelict` | Exclusion                                                      |
| `mech*`                  | Prefix match (mech, mechs, mechanical, mechanised)               |
| `M318` or `"M 318"`      | Hyphenated designation — drop hyphen or use phrase with space    |
| `Vas tir`                | Dot-separated name — split on the dot                            |

**`series` — filter to one series:**
Valid values are whatever `series` identifiers the mounted database actually contains — call `list_series` to see them. Only works when the database has a `series` column (i.e. a merged multi-series build). Ignored for single-series databases.

**`db` — corpus-relative path to a `.db` file:**
Defaults to `_DEFAULT_DB` in the server source; the current value is recorded in the project profile. Accepts any corpus-relative path to a schema-compatible DB. Path is validated to stay within `CORPUS_ROOT` (path traversal rejected).

**`limit`:** Max results returned. Default 10. Capped at 200 — a higher or non-positive value returns a diagnostic error (a runaway-call backstop, not a normal-use limit). See *Security posture*.

---

### `get_chapter`

```python
get_chapter(
    chapter_num: str,
    series: str | None = None,
    db: str | None = None,
) -> str
```

Returns the full text of a chapter. `chapter_num` is an **exact match** on the `chapters.chapter_num` column — use the identifier as shown in search results (e.g. `"499"`, `"CLASSIFIED"`, `"Prologue"`, `"0.1.1"`).

When multiple chapters share a chapter_num across series (common in the merged DB), the `series` parameter is required to disambiguate. Without it, the query returns the first match.

---

### `list_series`

```python
list_series(db: str | None = None) -> str
```

Returns a formatted overview of the database: series names (if merged), chapter counts, and the top arcs by chapter count. Useful for orientation before searching — tells you what's in the DB and which arc names you can filter by.

Example output (merged DB):
```
Database: my_series.db

  series_a: 61 chapters

  series_b: 1005 chapters
      arc: [Arc Name] (70)
      arc: [Arc Name] (29)
      ...

  series_c: 230 chapters
      arc: [Arc Name] (6)
      ...
```

## Building a compatible database

The server reads any SQLite file matching the schema above. It does not care how you produce
one — no pipeline ships with it. The requirements:

1. **A `chapters` table** with the columns listed above. `id`, `seq`, `title`, and `content` are
   the load-bearing ones; `arc`, `character`, `line_start`, and `line_end` may be NULL.
2. **A `chapters_fts` FTS5 external-content table** over `chapter_num`, `title`, `arc`,
   `character`, `content`, with `content_rowid` pointing at `chapters.id`. The `chapters` table
   is the source of truth; rebuild the FTS index from it rather than writing to both.
3. **Tokenizer `unicode61`.** No porter stemming — terms match literally. This is deliberate:
   invented proper nouns stem badly.
4. **A `series` column** only if you are merging multiple series into one file. Single-series
   databases omit it and the server adapts via `PRAGMA table_info(chapters)`.

### Chapter numbering

`chapter_num` is TEXT, not an integer, because real chapter identifiers are messy — a series will
happily mix numbers, words, decimals, and bracketed labels. `sort_num` is the numeric sort key
derived from it, and is NULL wherever no number can be extracted.

| Pattern | Example title | `chapter_num` | `sort_num` |
|---------|--------------|---------------|------------|
| Numeric | `Chapter 499` | `"499"` | 499.0 |
| Float | `Chapter 3.145` | `"3.145"` | 3.145 |
| Word | `Chapter Two` | `"Two"` | 2.0 |
| Bracket | `Chapter [CLASSIFIED]` | `"CLASSIFIED"` | NULL |
| Special | `Chapter ERROR` | `"ERROR"` | NULL |
| Version | `Series Name - 0.1.1` | `"0.1.1"` | 0.0101 |
| Bare | `Series Name - Flashback` | `"Flashback"` | NULL |

Sort order is `ORDER BY sort_num NULLS LAST, seq`, so unnumbered chapters fall to the end in
insertion order rather than scattering.

**Duplicates:** where the same `chapter_num` recurs (a series with sixteen chapters all titled
`[CLASSIFIED]` is a real case), append `_01`, `_02` … suffixes. `get_chapter` matches
`chapter_num` exactly, so collisions would otherwise make chapters unreachable.

### Acquiring the source text

Out of scope for this repository. Whatever produces your `.txt` files — a purchased ebook you
convert, a personal archive, an export — is your business and your legal responsibility. If you
scrape, check the source's terms and the author's wishes first; sites change their access rules,
and a scraper that worked once may simply stop.

## Docker integration

The server runs as a service in `Python/docker-compose.yml` (project `corpus-mcp`):

```yaml
series-search:
  build:
    context: .
    dockerfile: Dockerfile
  ports:
    - "8003:8003"
  volumes:
    - ${CORPUS_HOST_PATH}:/corpus:ro
  environment:
    CORPUS_ROOT: /corpus
    MCP_PORT: "8003"
  command: python series_search_mcp_server.py
  restart: unless-stopped
```

Read-only corpus mount — this server never writes to the corpus.

Claude Desktop connects via `mcp-remote`:
```json
"series-search": {
    "command": "npx",
    "args": ["-y", "mcp-remote", "http://localhost:8003/mcp"]
}
```

**After rebuilding the container**, restart Claude Desktop to reconnect. `mcp-remote` holds the connection open and does not auto-reconnect when the server restarts — the old connection just hangs. A full app restart is the reliable fix.

**Transport:** `streamable-http` (set by `MCP_TRANSPORT=streamable-http` in the Dockerfile ENV). The server reads this from the environment via `os.environ.get("MCP_TRANSPORT", "stdio")` — do not hardcode `"sse"` or `"stdio"` in the `mcp.run()` call.

## Security posture

- DB opened **read-only** via SQLite URI (`?mode=ro`). The server cannot write to any database.
- All user input passed via SQLite parameter binding. No string interpolation in SQL.
- The `db` parameter is validated against `CORPUS_ROOT`: `_resolve_db()` rejects any path that resolves outside the corpus root (path traversal attack prevention).
- The `series` parameter is passed as a bound parameter to a column equality clause — no injection surface.
- **Runaway guards.** `search_chapters`'s `limit` is capped at `_MAX_LIMIT` (200), and every tool runs its query under a `_QUERY_TIMEOUT_S` (15s) wall-clock guard (a SQLite progress handler that aborts an overrunning statement). Both return a diagnostic error naming the constant rather than failing silently — generous backstops against a pathological call, easy to tune in `series_search_mcp_server.py`.

## Configured paths

```python
_CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"D:\claude\filesystem"))
_DEFAULT_DB  = os.environ.get("SERIES_DEFAULT_DB", "").strip()
```

Neither path is hardcoded. `CORPUS_ROOT` lets Docker override the corpus location without editing source. `SERIES_DEFAULT_DB` supplies the corpus-relative database used when a tool call omits its `db` argument — which database a corpus holds is deployment-specific, so no default ships in source.

**Setting it:** put the value in `Python/.env` (gitignored) and it reaches the container through `docker-compose.yml`, which passes `SERIES_DEFAULT_DB: ${SERIES_DEFAULT_DB:-}`. `Python/.env.example` carries a placeholder. Changing it needs only `docker compose up -d series-search` to recreate the container — no image rebuild, since the value is environment rather than source.

**Unset is valid.** With no default, every tool call must name its own `db`; `_resolve_db()` raises a `ValueError` naming this variable. That guard matters: an empty default would otherwise resolve to `CORPUS_ROOT` itself, which passes the containment check and `.exists()` as a directory before failing deep inside sqlite with an opaque error.

**Casing note:** the value must match the true on-disk casing, verified with `os.walk` rather than a case-insensitive directory listing. Docker Desktop's Windows bind mount is case-insensitive, so a wrong-cased value works fine locally and then fails on a case-sensitive host (e.g. Linux). This bit us once, in both directions, before being pinned down on 2026-07-03 — moving the value into `.env` does not make it immune, since the mount is what forgives case.

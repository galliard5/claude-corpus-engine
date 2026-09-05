#!/usr/bin/env python3
"""
search_mcp_server.py — MCP server exposing FTS5 + semantic search over the corpus.

Provides two tools:
    search_corpus(query, limit, mode, ...filters) -> formatted ranked results
    index_status() -> diagnostic info about the index

Three retrieval modes (the `mode` arg):
    "fts"     full-text BM25 only (default; original behaviour, unchanged)
    "vector"  semantic K-NN over embeddings (finds paraphrases / synonyms)
    "hybrid"  fuses fts + vector with Reciprocal Rank Fusion

The database path is hardcoded and opened read-only. The server has no SQL
passthrough and no path arguments — the only thing reachable through this
interface is ranked search over the pre-built index tables.

Launched by Claude Desktop as a stdio subprocess via claude_desktop_config.json.
Not intended to be run manually.

changed 2026-05-19: fixed stale build_search_index.py reference in error messages
changed 2026-05-19: connections now closed via try/finally instead of inline close
changed 2026-06-25: added vector + hybrid (RRF) search modes via embedding.py;
    falls back to fts when fastembed/sqlite-vec or the corpus_vec table are absent
changed 2026-06-29: added runaway guards — a limit ceiling (_MAX_LIMIT) and a
    wall-clock query timeout (_QUERY_TIMEOUT_S); both return a diagnostic error
    naming the constant so the cap is easy to find and tune if it ever trips.
changed 2026-09-04: genericized docstring query examples and the FTS5 error hint
    for the public repo split (setting-specific names removed); category_filter
    now documents what a path segment is rather than naming two of them.
    Docstrings only — no behaviour change.
"""

import datetime
import os
import sqlite3
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Optional vector lane. embedding.AVAILABLE is False when fastembed / sqlite-vec
# aren't installed; vector/hybrid modes then degrade to fts with a note.
import embedding

# CORPUS_ROOT env var allows Docker to override the path without editing this file.
# Falls back to the local Windows path when not set.
# DB_PATH must stay in lockstep with build_indexes.py and indexer.cfg index_directory.
_CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"D:\claude\filesystem"))
DB_PATH = _CORPUS_ROOT / "index" / "search_index.db"

# bm25 column weights for corpus_fts: (path, name, keywords, description, category, content).
# path is UNINDEXED (weight ignored); name/keywords/description are boosted over body.
_BM25_WEIGHTS = "bm25(corpus_fts, 0.0, 10.0, 5.0, 3.0, 0.0, 1.0)"

# Fetch this many times `limit` candidates from each lane before fusing/filtering,
# so post-filtering and RRF have enough depth to work with.
_OVERSAMPLE = 5

# RRF constant (Cormack 2009). Higher = flatter weighting across ranks.
_RRF_K = 60

# --- Runaway guards -----------------------------------------------------------
# Generous ceilings that exist to catch a pathological call (limit=100000, or a
# query that pins the CPU), not to constrain normal use. If one ever trips on a
# legitimate search, raise it here — the error messages point back to this file.
_MAX_LIMIT = 200          # hard cap on the `limit` arg
_QUERY_TIMEOUT_S = 15.0   # wall-clock abort for a single query
_PROGRESS_STEPS = 10_000  # SQLite VM steps between deadline checks

mcp = FastMCP(
    "corpus-search",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
)


def _open_readonly(load_vectors: bool = False) -> sqlite3.Connection:
    """Open the database in read-only mode using a SQLite URI.

    Rows come back as sqlite3.Row (name- and index-addressable). When
    load_vectors is True and the embedding deps are present, the sqlite-vec
    extension is loaded so corpus_vec K-NN queries work.
    """
    uri = f"{DB_PATH.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    if load_vectors and embedding.AVAILABLE:
        embedding.load_vec(conn)
    return conn


def _has_vector_table(conn: sqlite3.Connection) -> bool:
    """True if the corpus_vec table exists (i.e. the index was built with vectors)."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='corpus_vec'"
    ).fetchone()
    return row is not None


def _wrap_query(query: str) -> str:
    """Wrap a user query in outer parens for FTS5 MATCH grouping.

    FTS5 phrase-query quotes are passed through unchanged so "exact phrase"
    syntax works as intended. Unbalanced quotes produce an FTS5 syntax error,
    caught by the OperationalError handler in search_corpus."""
    return f"({query.strip()})"


# ---------------------------------------------------------------------------
# Runaway guards
# ---------------------------------------------------------------------------

class _QueryGuard:
    """Aborts a SQLite query that overruns a wall-clock deadline.

    Installed via Connection.set_progress_handler: SQLite invokes it every
    _PROGRESS_STEPS VM instructions and aborts the running statement when it
    returns non-zero. `fired` lets the caller tell a timeout abort (surfaced as
    OperationalError "interrupted") apart from a genuine SQL error.
    """

    def __init__(self, seconds: float):
        self._deadline = time.monotonic() + seconds
        self.seconds = seconds
        self.fired = False

    def __call__(self) -> int:
        if time.monotonic() > self._deadline:
            self.fired = True
            return 1
        return 0


def _install_query_guard(conn: sqlite3.Connection) -> _QueryGuard:
    """Attach a wall-clock deadline guard to a connection and return it."""
    guard = _QueryGuard(_QUERY_TIMEOUT_S)
    conn.set_progress_handler(guard, _PROGRESS_STEPS)
    return guard


def _check_limit(limit: int) -> str | None:
    """Validate `limit` against the runaway ceiling.

    Returns an error string to hand straight back to the caller, or None when
    acceptable. The message names the constant and file so the cap is easy to
    locate and tune if it ever fires on legitimate use.
    """
    if limit < 1:
        return f"[!] limit must be >= 1 (got {limit})."
    if limit > _MAX_LIMIT:
        return (
            f"[!] limit {limit} exceeds the safety ceiling of {_MAX_LIMIT}. "
            f"This guard catches runaway calls; if you genuinely need more, "
            f"raise _MAX_LIMIT in {Path(__file__).name}."
        )
    return None


# ---------------------------------------------------------------------------
# Retrieval lanes — each returns result rows keyed by rowid
# ---------------------------------------------------------------------------

# Columns selected for display. Shared by both lanes so formatting is uniform.
# The fts lane adds a `preview` from snippet(); the vector lane derives one from
# a content prefix (no matched terms to highlight).
_DISPLAY_COLS = """
    f.rowid AS rowid, f.path AS path, f.name AS name, f.keywords AS keywords,
    f.description AS description,
    COALESCE(m.doc_type, '')            AS doc_type,
    COALESCE(m.missing_name, 0)         AS missing_name,
    COALESCE(m.missing_keywords, 0)     AS missing_keywords,
    COALESCE(m.missing_description, 0)  AS missing_description,
    COALESCE(m.missing_type, 0)         AS missing_type
"""


def _fts_lane(conn, match_expr, subquery_filters, subquery_params, limit):
    """Lexical BM25 lane. Returns ordered list of row dicts with a `preview`
    (highlighted snippet) and `rank` (bm25; more negative = better)."""
    where_clause = "WHERE corpus_fts MATCH ?"
    if subquery_filters:
        where_clause += "\n  AND " + "\n  AND ".join(subquery_filters)
    cur = conn.execute(
        f"""
        SELECT {_DISPLAY_COLS},
            snippet(corpus_fts, 5, '**', '**', '...', 24) AS preview,
            {_BM25_WEIGHTS} AS rank
        FROM corpus_fts f
        LEFT JOIN corpus_meta m ON f.path = m.path
        {where_clause}
        ORDER BY rank
        LIMIT ?
        """,
        [match_expr] + subquery_params + [limit],
    )
    return [dict(r) for r in cur.fetchall()]


def _vector_lane(conn, query_vec, limit):
    """Semantic K-NN lane over corpus_vec. Returns ordered (rowid, distance)
    pairs — metadata is fetched separately so we don't carry a join through
    the K-NN query (sqlite-vec's join + k constraint footgun)."""
    serialized = embedding.serialize(query_vec)
    rows = conn.execute(
        """
        SELECT rowid, distance
        FROM corpus_vec
        WHERE embedding MATCH ? AND k = ?
        ORDER BY distance
        """,
        (serialized, limit),
    ).fetchall()
    return [(r["rowid"], r["distance"]) for r in rows]


def _fetch_display(conn, rowids, subquery_filters, subquery_params):
    """Fetch display metadata for a set of rowids, honouring structured filters.

    Returns {rowid: row_dict}. `preview` is derived from a content prefix since
    vector hits have no matched terms to highlight. Filters are applied here so
    vector-only candidates respect type/missing/category just like fts hits.
    """
    if not rowids:
        return {}
    placeholders = ",".join("?" * len(rowids))
    where = f"WHERE f.rowid IN ({placeholders})"
    if subquery_filters:
        where += "\n  AND " + "\n  AND ".join(subquery_filters)
    cur = conn.execute(
        f"""
        SELECT {_DISPLAY_COLS},
            substr(f.content, 1, 240) AS preview
        FROM corpus_fts f
        LEFT JOIN corpus_meta m ON f.path = m.path
        {where}
        """,
        list(rowids) + subquery_params,
    )
    out = {}
    for r in cur.fetchall():
        d = dict(r)
        # Collapse whitespace in the raw content prefix for a tidy one-liner.
        if d.get("preview"):
            d["preview"] = " ".join(d["preview"].split())
        out[d["rowid"]] = d
    return out


def _rrf_fuse(fts_rows, vec_pairs, limit, vec_meta):
    """Reciprocal Rank Fusion of the two lanes.

    Each rowid scores sum(1 / (_RRF_K + rank)) over the lists it appears in,
    rewarding documents both lanes rank well. Returns ordered list of
    (row_dict, score), trimmed to `limit`, preferring the fts row dict (it
    carries a highlighted snippet) and falling back to vec_meta otherwise.
    """
    scores: dict[int, float] = {}
    fts_by_id = {r["rowid"]: r for r in fts_rows}
    for rank, r in enumerate(fts_rows, start=1):
        rid = r["rowid"]
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (_RRF_K + rank)
    for rank, (rid, _dist) in enumerate(vec_pairs, start=1):
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (_RRF_K + rank)

    ordered = sorted(scores, key=lambda rid: -scores[rid])
    result = []
    for rid in ordered:
        row = fts_by_id.get(rid) or vec_meta.get(rid)
        if row is None:
            # Candidate dropped by a structured filter during metadata fetch.
            continue
        result.append((row, scores[rid]))
        if len(result) >= limit:
            break
    return result


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_results(query, header_suffix, scored_rows, score_label):
    """Render scored result rows into the text block returned to the client.

    scored_rows: list of (row_dict, score_float). score_label tags the score
    so the meaning (bm25 / similarity / rrf) is visible.
    """
    if not scored_rows:
        return f"No results for: {query}{header_suffix}"

    lines = [f"Found {len(scored_rows)} result(s) for: {query}{header_suffix}", ""]
    for i, (row, score) in enumerate(scored_rows, 1):
        lines.append(f"{i}. [{score_label}: {score:.2f}] {row['path']}")
        if row.get("name"):
            lines.append(f"   Name: {row['name']}")
        if row.get("keywords"):
            lines.append(f"   Keywords: {row['keywords']}")
        if row.get("description"):
            lines.append(f"   Description: {row['description']}")
        if row.get("doc_type"):
            lines.append(f"   Type: {row['doc_type']}")
        missing_parts = [
            field for field in ("name", "keywords", "description", "type")
            if row.get(f"missing_{field}")
        ]
        if missing_parts:
            lines.append(f"   Missing: {', '.join(missing_parts)}")
        if row.get("preview"):
            lines.append(f"   Match: {' '.join(row['preview'].split())}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def search_corpus(
    query: str,
    limit: int = 10,
    mode: str = "fts",
    category_filter: str | None = None,
    type_filter: str | None = None,
    missing_filter: str | None = None,
) -> str:
    """Ranked search over the worldbuilding corpus.

    Modes:
        "fts"    (default) full-text BM25. Exact terms, FTS5 query syntax, fast.
        "vector" semantic K-NN — finds documents close in meaning even with no
                 shared words ("supply lines collapsed" ~ "logistics broke
                 down"). Query is free text, not FTS5 syntax.
        "hybrid" fuses fts + vector with Reciprocal Rank Fusion — best general
                 recall; rewards documents both lanes agree on.

    If vector/hybrid is requested but the embedding deps or the corpus_vec table
    aren't present, the search falls back to fts and says so in the output.

    Query syntax (fts / hybrid lexical lane):
        Kestrel                    - single term (porter stem)
        Kestrel security           - both words present (implicit AND)
        Kestrel OR Vance           - either term
        "Autumn Accord"            - exact phrase (wrap in double quotes)
        petition NOT rejected      - boolean exclusion
        transform*                 - prefix match
    (Vector lane treats the query as plain text; FTS operators are ignored there.)

    Args:
        query: Search expression (see syntax above).
        limit: Max results. Default 10.
        mode: "fts" | "vector" | "hybrid". Default "fts".
        category_filter: Path-segment filter — matches any single segment of a
            file's corpus-relative path (e.g. "Factions", "Locations").
        type_filter: Exact match against the type: frontmatter field.
        missing_filter: Find files where a frontmatter field is absent or empty.
            One of: name, keywords, description, type.

    Returns:
        Formatted ranked results, a 'no results' message, or an error string.
    """
    if not DB_PATH.exists():
        rebuild_path = DB_PATH.parent / "build_indexes.py"
        return (
            f"[!] Search index not found at {DB_PATH}.\n"
            f"Run: python {rebuild_path}"
        )

    mode = (mode or "fts").lower().strip()
    if mode not in ("fts", "vector", "hybrid"):
        return f"[!] Invalid mode: '{mode}'. Valid values: fts, vector, hybrid"

    limit_err = _check_limit(limit)
    if limit_err:
        return limit_err

    # Validate missing_filter before touching the DB
    _valid_missing = {"name", "keywords", "description", "type"}
    if missing_filter:
        _field = missing_filter.lower().strip()
        if _field not in _valid_missing:
            return (
                f"[!] Invalid missing_filter: '{missing_filter}'. "
                f"Valid values: {', '.join(sorted(_valid_missing))}"
            )

    # FTS5 MATCH expression — category stays here; type/missing use SQL below
    conditions = []
    if category_filter:
        cat_clean = category_filter.strip().replace('"', '""')
        conditions.append(f'category:"{cat_clean}"')
    conditions.append(_wrap_query(query))
    match_expr = " AND ".join(conditions)

    # Structured field filters as IN-subqueries against corpus_meta (avoids an
    # FTS5 quirk where non-MATCH WHERE clauses on joined tables are dropped).
    # Reused by both lanes so vector hits respect the same filters.
    subquery_filters: list[str] = []
    subquery_params: list = []
    if type_filter:
        subquery_filters.append(
            "f.path IN (SELECT path FROM corpus_meta WHERE doc_type = ?)"
        )
        subquery_params.append(type_filter.strip())
    if missing_filter:
        field = missing_filter.lower().strip()
        subquery_filters.append(
            f"f.path IN (SELECT path FROM corpus_meta WHERE missing_{field} = 1)"
        )
    # category_filter is enforced via the FTS MATCH expr for the lexical lane;
    # for the vector lane we add an equivalent path-segment check at fetch time.
    vec_filters = list(subquery_filters)
    vec_params = list(subquery_params)
    if category_filter:
        vec_filters.append("instr('/' || f.category || '/', ?) > 0")
        vec_params.append("/" + category_filter.strip() + "/")

    # Header suffix listing active filters
    suffixes = []
    if category_filter:
        suffixes.append(f"category: {category_filter}")
    if type_filter:
        suffixes.append(f"type: {type_filter}")
    if missing_filter:
        suffixes.append(f"missing: {missing_filter}")

    needs_vectors = mode in ("vector", "hybrid")
    fallback_note = ""
    if needs_vectors and not embedding.AVAILABLE:
        fallback_note = "vector lane unavailable (deps not installed) - using fts"
        mode = "fts"
        needs_vectors = False

    conn = None
    guard = None
    try:
        conn = _open_readonly(load_vectors=needs_vectors)
        guard = _install_query_guard(conn)

        if needs_vectors and not _has_vector_table(conn):
            fallback_note = "index has no vector table (rebuild to enable) - using fts"
            mode = "fts"
            needs_vectors = False

        if mode == "fts":
            scored = [
                (r, abs(r["rank"]))
                for r in _fts_lane(conn, match_expr, subquery_filters, subquery_params, limit)
            ]
            score_label = "score"

        elif mode == "vector":
            query_vec = embedding.embed_query(query)
            pairs = _vector_lane(conn, query_vec, limit * _OVERSAMPLE)
            meta = _fetch_display(conn, [rid for rid, _ in pairs], vec_filters, vec_params)
            scored = []
            for rid, dist in pairs:
                if rid in meta:  # survived filters
                    similarity = max(0.0, 1.0 - dist / 2.0)  # L2 on unit vectors -> 0..1
                    scored.append((meta[rid], similarity))
                if len(scored) >= limit:
                    break
            score_label = "similarity"

        else:  # hybrid
            fts_rows = _fts_lane(
                conn, match_expr, subquery_filters, subquery_params, limit * _OVERSAMPLE
            )
            query_vec = embedding.embed_query(query)
            vec_pairs = _vector_lane(conn, query_vec, limit * _OVERSAMPLE)
            # Fetch metadata for vector-only candidates (fts rows already have it),
            # applying filters so they match the lexical lane's constraints.
            fts_ids = {r["rowid"] for r in fts_rows}
            vec_only_ids = [rid for rid, _ in vec_pairs if rid not in fts_ids]
            vec_meta = _fetch_display(conn, vec_only_ids, vec_filters, vec_params)
            scored = _rrf_fuse(fts_rows, vec_pairs, limit, vec_meta)
            score_label = "rrf"

    except sqlite3.OperationalError as e:
        if guard is not None and guard.fired:
            return (
                f"[!] Search aborted: query exceeded the {_QUERY_TIMEOUT_S:.0f}s "
                f"timeout guard — likely a pathological query, not a normal search. "
                f"If this trips on legitimate use, raise _QUERY_TIMEOUT_S in "
                f"{Path(__file__).name}."
            )
        return (
            f"[!] Search error: {e}\n\n"
            "Hint: FTS5 has special syntax. Wrap problematic terms in double "
            'quotes (e.g. "Kestrel\'s") or use prefix matching (Kestrel*).'
        )
    except Exception as e:
        return f"[!] Unexpected error: {e}"
    finally:
        if conn:
            conn.close()

    # Header: mode (when not plain fts) + filters + any fallback note
    header_bits = [] if (mode == "fts" and not fallback_note) else [f"mode: {mode}"]
    header_bits += suffixes
    if fallback_note:
        header_bits.append(fallback_note)
    header_suffix = f" [{', '.join(header_bits)}]" if header_bits else ""

    return _format_results(query, header_suffix, scored, score_label)


@mcp.tool()
def index_status() -> str:
    """Report the current state of the search index.

    Returns the database path, total indexed files, vector-lane availability,
    and last-built timestamp. Useful for checking whether the index is stale or
    whether semantic search is available before relying on results.
    """
    if not DB_PATH.exists():
        rebuild_path = DB_PATH.parent / "build_indexes.py"
        return (
            f"[!] Index not built yet.\n"
            f"Run: python {rebuild_path}"
        )

    conn = None
    try:
        # Load the vec extension so corpus_vec is countable (vec0 is a loadable
        # module — querying the table without it raises "no such module: vec0").
        conn = _open_readonly(load_vectors=True)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM corpus_fts")
        count = cur.fetchone()[0]
        has_vec = _has_vector_table(conn)
        # Counting needs the extension; only possible when the deps are present.
        vec_count = (
            conn.execute("SELECT COUNT(*) FROM corpus_vec").fetchone()[0]
            if has_vec and embedding.AVAILABLE else 0
        )
    except Exception as e:
        return f"[!] Could not read index: {e}"
    finally:
        if conn:
            conn.close()

    mtime = datetime.datetime.fromtimestamp(DB_PATH.stat().st_mtime)
    age = datetime.datetime.now() - mtime
    age_str = (
        f"{age.days}d ago" if age.days >= 1
        else f"{age.seconds // 3600}h ago" if age.seconds >= 3600
        else f"{age.seconds // 60}m ago"
    )

    if not has_vec:
        vec_line = "  Vector lane:    not built (rebuild to enable semantic/hybrid search)"
    elif not embedding.AVAILABLE:
        vec_line = f"  Vector lane:    {vec_count} vectors in index, but deps not installed here"
    else:
        vec_line = f"  Vector lane:    {vec_count} vectors [{embedding.MODEL_NAME}]"

    return (
        "Search index status:\n"
        f"  Path: {DB_PATH}\n"
        f"  Files indexed:  {count}\n"
        f"{vec_line}\n"
        f"  Last built:     {mtime.strftime('%Y-%m-%d %H:%M:%S')} ({age_str})"
    )


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))

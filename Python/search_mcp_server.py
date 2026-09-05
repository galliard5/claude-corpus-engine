#!/usr/bin/env python3
"""
search_mcp_server.py — MCP server exposing FTS5 + semantic search over the corpus.

Provides three tools:
    search_corpus(query, limit, mode, ...filters) -> formatted ranked results
    get_section(path, heading, level) -> one section of an indexed document
    index_status() -> diagnostic info about the index

Three retrieval modes (the `mode` arg):
    "fts"     full-text BM25 only (default; original behaviour, unchanged)
    "vector"  semantic K-NN over embeddings (finds paraphrases / synonyms)
    "hybrid"  fuses fts + vector with Reciprocal Rank Fusion

The database path is hardcoded and opened read-only. The server has no SQL
passthrough and touches no files — everything reachable through this interface
comes out of the pre-built index tables. get_section takes a `path`, but it is
an index key, not a filesystem path: it is matched for equality against
corpus_fts.path and the body is served from the stored `content` column, so
nothing outside the index is addressable and no traversal is possible.

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
changed 2026-09-05: added section-level retrieval. search_corpus results now
    carry a `Sections:` manifest for documents large enough to be worth
    splitting, and the new get_section tool returns a single section. Both are
    derived on the fly from the stored `content` column — no schema change and
    no reindex. Motivation: a hit on a 30k-char toolkit used to force a
    whole-file read to reach one 1.5k-char section.
"""

import datetime
import os
import re
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
# Section parsing
#
# Sections are derived on demand from the stored `content` column, never from
# disk and never persisted. That keeps this a pure read-side view over the
# existing index: no schema change, no reindex, no effect on ranking.
#
# TODO — revisit once get_section and the manifest have some mileage: index at
# section granularity (one corpus_fts row per section rather than per file).
# It would sharpen BM25, which currently scores a 30k-char toolkit and a 2k-char
# character sheet on the same footing, and it would fix the vector lane, where a
# single 384-dim embedding averaged over a whole document loses whatever made
# any one section distinctive. The cost is real: a schema change, a full
# rebuild in build_indexes.py, a check_schema_drift.py update, and shifted
# ranking corpus-wide. Decide after seeing how often callers reach for a
# section vs the whole file. Notes in System_Documentation/Search_Server.md.
# ---------------------------------------------------------------------------

# ATX headings only ("## Title"); trailing closing hashes are tolerated.
_ATX_RE = re.compile(r"^(#{1,6})[ \t]+(\S.*?)[ \t]*#*$")
_FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")

# A manifest costs ~75 tokens per hit (measured across the corpus: the median
# sectioned document has 10 sections). At 10 hits that is ~750 tokens on every
# search, so it has to be pointed at documents where reading the whole file
# genuinely hurts. 12k chars (~3k tokens) is where that starts to be true —
# below it a whole-file read is cheap, and for the character sheets that
# dominate the 5-12k band it is also the *right* read, since you generally want
# the whole character rather than one heading of them.
_MANIFEST_MIN_CHARS = 12_000
_MANIFEST_MIN_SECTIONS = 2
# Guard against a pathological outline document turning one hit into a wall.
_MANIFEST_MAX_SECTIONS = 14


def _est_tokens(text: str) -> int:
    """Rough token count for display (~4 chars/token).

    Deliberately approximate — it exists so a caller can tell a 400-token
    section from a 4,000-token one, not to budget precisely.
    """
    return len(text) // 4


def _iter_headings(content: str, level: int):
    """Yield (line_index, title) for ATX headings at exactly `level`.

    Skips anything inside a fenced code block so a '## ' in an example block
    doesn't split the document.
    """
    in_fence = False
    fence = ""
    for i, line in enumerate(content.splitlines()):
        m = _FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence, fence = True, m.group(1)
            elif line.strip().startswith(fence):
                in_fence, fence = False, ""
            continue
        if in_fence:
            continue
        h = _ATX_RE.match(line)
        if h and len(h.group(1)) == level:
            yield i, h.group(2).strip()


def _split_sections(
    content: str, level: int = 2, lead_title: str | None = None
) -> list[tuple[str, str]]:
    """Split `content` into [(title, body)] at ATX headings of `level`.

    Deeper headings stay inside their parent section — splitting on ## keeps
    each ### with the ## it belongs to. Text before the first heading becomes a
    leading section; it is titled by the document's H1, falling back to
    `lead_title` (pass the frontmatter name) and then to a generic label, since
    220 of the indexed files have no H1 at all. Returns [] when the document
    has no headings at `level`.
    """
    lines = content.splitlines(keepends=True)
    marks = list(_iter_headings(content, level))
    if not marks:
        return []

    out: list[tuple[str, str]] = []
    first = marks[0][0]
    if first > 0:
        preamble = "".join(lines[:first])
        if preamble.strip():
            h1 = next((t for _, t in _iter_headings(content, 1)), None)
            out.append((h1 or lead_title or "(opening)", preamble))

    starts = [i for i, _ in marks]
    for (start, title), end in zip(marks, starts[1:] + [len(lines)]):
        out.append((title, "".join(lines[start:end])))
    return out


def _norm_heading(s: str) -> str:
    """Normalize a heading for matching.

    Casefolds, collapses whitespace, and folds the typography that makes
    headings painful to retype exactly (em/en dashes, curly quotes) down to
    ASCII, so 'estate's week - supply cadence' finds "The Estate's Week —
    Supply Cadence".
    """
    for a, b in (("—", "-"), ("–", "-"), ("’", "'"),
                 ("‘", "'"), ("“", '"'), ("”", '"')):
        s = s.replace(a, b)
    return " ".join(s.casefold().split()).strip(" -:#")


def _match_section(sections, wanted: str):
    """Resolve `wanted` against section titles.

    Tiers, first unambiguous one wins: exact (normalized) -> prefix ->
    substring. Returns (index, None) on a hit, or (None, candidates) when the
    request is ambiguous or matches nothing, so the caller can show options
    rather than guessing.
    """
    titles = [t for t, _ in sections]
    norm = [_norm_heading(t) for t in titles]
    w = _norm_heading(wanted)
    if not w:
        return None, titles
    for test in (lambda n: n == w, lambda n: n.startswith(w), lambda n: w in n):
        hits = [i for i, n in enumerate(norm) if test(n)]
        if len(hits) == 1:
            return hits[0], None
        if len(hits) > 1:
            return None, [titles[i] for i in hits]
    return None, titles


def _section_manifest(content: str, level: int = 2, lead_title: str | None = None) -> str:
    """One-line 'Title (~tok) | Title (~tok)' summary of a document.

    Returns '' when the document is too small or too flat for the manifest to
    pay for itself — see _MANIFEST_MIN_CHARS. Overlong outlines are truncated
    to the biggest sections, since those are the ones worth not reading.
    """
    if len(content) < _MANIFEST_MIN_CHARS:
        return ""
    sections = _split_sections(content, level, lead_title)
    if len(sections) < _MANIFEST_MIN_SECTIONS:
        return ""

    shown, overflow = sections, 0
    if len(sections) > _MANIFEST_MAX_SECTIONS:
        biggest = sorted(range(len(sections)), key=lambda i: -len(sections[i][1]))
        keep = set(biggest[:_MANIFEST_MAX_SECTIONS])
        shown = [sections[i] for i in sorted(keep)]  # keep document order
        overflow = len(sections) - len(shown)

    line = " | ".join(f"{t} (~{_est_tokens(b)})" for t, b in shown)
    if overflow:
        line += f" | +{overflow} smaller (call get_section without a heading to list all)"
    return line


def _fetch_manifests(conn, paths) -> dict[str, str]:
    """Build {path: manifest} for the hits about to be displayed.

    Deliberately runs after scoring: `content` is the one heavy column in the
    table, so it is only pulled for the handful of rows that will be shown.
    Rows with no indexed content (indexer context_limits = 0) and documents
    with no usable sections simply don't appear in the result.
    """
    if not paths:
        return {}
    placeholders = ",".join("?" * len(paths))
    out: dict[str, str] = {}
    for row in conn.execute(
        f"SELECT path, name, content FROM corpus_fts WHERE path IN ({placeholders})",
        list(paths),
    ):
        manifest = _section_manifest(row["content"] or "", lead_title=row["name"])
        if manifest:
            out[row["path"]] = manifest
    return out


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

def _format_results(query, header_suffix, scored_rows, score_label, manifests=None):
    """Render scored result rows into the text block returned to the client.

    scored_rows: list of (row_dict, score_float). score_label tags the score
    so the meaning (bm25 / similarity / rrf) is visible. manifests maps path ->
    section manifest for the documents big enough to be worth splitting; a
    trailing hint points at get_section only when at least one hit has one.
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
        manifest = (manifests or {}).get(row["path"])
        if manifest:
            lines.append(f"   Sections: {manifest}")
        lines.append("")

    if manifests:
        lines.append(
            "(~N = estimated tokens. For the files listing Sections, "
            "get_section(path, heading) returns one section instead of the "
            "whole file.)"
        )
    return "\n".join(lines)


@mcp.tool()
def search_corpus(
    query: str,
    limit: int = 10,
    mode: str = "fts",
    category_filter: str | None = None,
    type_filter: str | None = None,
    missing_filter: str | None = None,
    show_sections: bool = True,
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
        show_sections: Add a `Sections:` line to hits that are large enough to
            be worth splitting, listing each section and its rough token cost.
            Feed one of those headings to get_section to read just that part
            instead of the whole file. Default True; turn it off if you intend
            to read the full documents anyway.

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

        # Must happen before the connection closes; only touches displayed rows.
        manifests = (
            _fetch_manifests(conn, [r["path"] for r, _ in scored])
            if show_sections else {}
        )

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

    return _format_results(query, header_suffix, scored, score_label, manifests)


@mcp.tool()
def get_section(path: str, heading: str | None = None, level: int = 2) -> str:
    """Return one section of an indexed document instead of the whole file.

    Pairs with the `Sections:` line in search_corpus output: the search says
    which sections a hit has and roughly what each costs, this pulls the one
    that answers the question. A 30k-char reference document becomes the
    1.5k-char section you actually needed, with the prose intact — this trims
    by selection, it does not summarise or rewrite anything.

    Content comes from the search index, not the filesystem, so it reflects the
    last index build (check index_status) and `path` must be one that appears
    in search results.

    Args:
        path: Corpus-relative path exactly as printed by search_corpus
            (e.g. "World_Building/Locations/Old_Mill.md").
        heading: Section title. Matched loosely — case, spacing, and dash style
            are normalized, and a unique prefix or substring is enough
            ("supply cadence" finds "The Estate's Week — Supply Cadence").
            Omit it to list the document's sections without pulling any body.
        level: Heading depth to split on. 2 (##) by default; pass 3 to break a
            long section down into its subsections.

    Returns:
        The section text with a short provenance header, a section listing when
        `heading` is omitted or ambiguous, or an error string.
    """
    if not DB_PATH.exists():
        rebuild_path = DB_PATH.parent / "build_indexes.py"
        return (
            f"[!] Search index not found at {DB_PATH}.\n"
            f"Run: python {rebuild_path}"
        )

    if level not in range(1, 7):
        return f"[!] Invalid level: {level}. Valid values: 1-6."

    # Normalize separators so a Windows-style path from a human still resolves;
    # the lookup below is an equality match against an indexed path, so nothing
    # outside the index is reachable regardless of what arrives here.
    wanted = (path or "").strip().replace("\\", "/").lstrip("/")
    if not wanted:
        return "[!] path is required — copy it from a search_corpus result."

    conn = None
    try:
        conn = _open_readonly()
        row = conn.execute(
            """
            SELECT f.path AS path, f.name AS name, f.content AS content,
                   COALESCE(m.doc_type, '') AS doc_type
            FROM corpus_fts f
            LEFT JOIN corpus_meta m ON f.path = m.path
            WHERE f.path = ?
            """,
            (wanted,),
        ).fetchone()
        if row is None:
            # Offer near misses on the basename — the usual cause is a path
            # retyped from memory rather than copied from a result.
            near = conn.execute(
                "SELECT path FROM corpus_fts WHERE path LIKE ? LIMIT 5",
                (f"%{wanted.rsplit('/', 1)[-1]}%",),
            ).fetchall()
            hint = (
                "\nDid you mean:\n  " + "\n  ".join(r["path"] for r in near)
            ) if near else "\nRun search_corpus first and copy the path from a result."
            return f"[!] Not in the index: {wanted}{hint}"
    except Exception as e:
        return f"[!] Could not read index: {e}"
    finally:
        if conn:
            conn.close()

    content = row["content"] or ""
    if not content.strip():
        return (
            f"[!] {wanted} is indexed by path only — no content stored. "
            f"The indexer's [context_limits] in indexer.cfg sets this file "
            f"type to 0 lines."
        )

    sections = _split_sections(content, level, lead_title=row["name"])
    if not sections:
        return (
            f"{wanted} has no level-{level} headings "
            f"(~{_est_tokens(content)} tok whole file). Try a different level, "
            f"or just read the file — at this size there is nothing to trim."
        )

    listing = "\n".join(f"  {t}  (~{_est_tokens(b)} tok)" for t, b in sections)

    if heading is None:
        return (
            f"{wanted} — {len(sections)} section(s) at level {level}, "
            f"~{_est_tokens(content)} tok whole file:\n{listing}\n\n"
            f"Call again with heading=\"...\" for one of them."
        )

    idx, candidates = _match_section(sections, heading)
    if idx is None:
        if candidates and len(candidates) < len(sections):
            options = "\n".join(f"  {t}" for t in candidates)
            return (
                f"[!] '{heading}' is ambiguous in {wanted} — it matches:\n"
                f"{options}"
            )
        return (
            f"[!] No section matching '{heading}' in {wanted}.\n"
            f"Sections at level {level}:\n{listing}"
        )

    title, body = sections[idx]
    provenance = f"{wanted} § {title}"
    if row["name"]:
        tag = f"{row['name']}, {row['doc_type']}" if row["doc_type"] else row["name"]
        provenance += f"  [{tag}]"
    return (
        f"{provenance}  (~{_est_tokens(body)} of ~{_est_tokens(content)} tok)\n"
        f"{'-' * 60}\n"
        f"{body.rstrip()}\n"
    )


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

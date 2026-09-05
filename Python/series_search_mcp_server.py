#!/usr/bin/env python3
"""
series_search_mcp_server.py — MCP server for FTS5 search over serialised-fiction
databases (one indexed row per chapter).

Provides three tools:
    search_chapters(query, db, series, limit) -> ranked results with excerpts
    get_chapter(chapter_num, series, db)      -> full chapter text
    list_series(db)                           -> series/arc overview for a db

The 'db' parameter is a corpus-relative path (e.g.
"Other_References/Some_Series/series.db"). It must resolve inside CORPUS_ROOT
to prevent path traversal. Falls back to _DEFAULT_DB when omitted.

Building a compatible database — schema, chapter-numbering rules, and the
sourcing caveats — is documented in System_Documentation/Series_Search_Server.md.
This server only reads; it never builds or acquires anything.

Run alongside the other MCP servers. Register in claude_desktop_config.json:
    "series-search": {
        "command": "npx",
        "args": ["-y", "mcp-remote", "http://localhost:8003/mcp"]
    }

Environment variables:
    CORPUS_ROOT        Corpus root path (default: D:\\claude\\filesystem)
    SERIES_DEFAULT_DB  Corpus-relative default database, used when a tool call
                       omits `db`. No built-in default; unset means every call
                       must name its own db.
    MCP_HOST           Bind address (default: 127.0.0.1)
    MCP_PORT           Port (default: 8003)

changed 2026-06-29: added runaway guards — a limit ceiling (_MAX_LIMIT) and a
    wall-clock query timeout (_QUERY_TIMEOUT_S); both return a diagnostic error
    naming the constant so the cap is easy to find and tune if it ever trips.
changed 2026-07-03: _DEFAULT_DB and docstring examples aligned to the true
    on-disk casing (confirmed via os.walk, not a case-insensitive directory
    listing — an initial pass here had used a lowercased variant copied from a
    handoff doc whose claimed "canonical casing" turned out to be wrong;
    corrected same day). Docker Desktop's Windows bind mount is case-insensitive,
    so a wrong-cased constant works locally and fails on a case-sensitive host.
changed 2026-09-04: genericized module/tool docstrings and the not-found message
    for the public repo split — series-specific names, example queries and the
    pipeline .bat reference removed; the series param now points at list_series()
    instead of naming fixed values. Docstrings and one message string only —
    no behaviour change.
changed 2026-09-04: _DEFAULT_DB now reads SERIES_DEFAULT_DB with no built-in
    default, so no deployment-specific path ships in source (the value moves to
    .env, passed through docker-compose.yml). _resolve_db gained an explicit
    empty-default guard: previously an empty default resolved to CORPUS_ROOT
    itself, which passed the containment check and .exists() as a directory and
    then failed opaquely inside sqlite. Behaviour change — requires a rebuild.
"""

import os
import sqlite3
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

_CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"D:\claude\filesystem"))

# Corpus-relative path used when a tool call omits `db`. Deliberately has no
# built-in default: which database a given corpus holds is deployment-specific,
# so it is supplied by SERIES_DEFAULT_DB (set in .env, passed through
# docker-compose.yml) rather than hardcoded here. Unset simply means "no
# default" — every tool call must then name its db explicitly.
_DEFAULT_DB = os.environ.get("SERIES_DEFAULT_DB", "").strip()

mcp = FastMCP(
    "series-search",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8003")),
)


def _resolve_db(db: str | None) -> Path:
    """Resolve a corpus-relative db path, rejecting anything outside CORPUS_ROOT."""
    rel = db.strip() if db and db.strip() else _DEFAULT_DB
    if not rel:
        # Without this, an empty rel resolves to CORPUS_ROOT itself — a directory
        # that passes the containment check and .exists(), then fails deep in
        # sqlite with an opaque error. Fail here, where the cause is nameable.
        raise ValueError(
            "No database specified and SERIES_DEFAULT_DB is not set — pass an "
            "explicit db, or set SERIES_DEFAULT_DB in .env and recreate the "
            "series-search container."
        )
    resolved = (_CORPUS_ROOT / rel).resolve()
    if not resolved.is_relative_to(_CORPUS_ROOT.resolve()):
        raise ValueError(f"Path '{db}' escapes corpus root — not allowed.")
    return resolved


def _open_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)


def _wrap(query: str) -> str:
    """Wrap a user query in outer parens for FTS5 MATCH grouping.

    FTS5 phrase-query quotes are passed through unchanged so "exact phrase"
    syntax works as intended. Unbalanced quotes will produce an FTS5 syntax
    error, which is caught by the OperationalError handler in the caller.
    """
    return f'({query.strip()})'


# ---------------------------------------------------------------------------
# Runaway guards
# ---------------------------------------------------------------------------
# Generous ceilings that exist to catch a pathological call (limit=100000, or a
# query that pins the CPU), not to constrain normal use. If one ever trips on a
# legitimate query, raise it here — the error messages point back to this file.
_MAX_LIMIT = 200          # hard cap on the `limit` arg
_QUERY_TIMEOUT_S = 15.0   # wall-clock abort for a single query
_PROGRESS_STEPS = 10_000  # SQLite VM steps between deadline checks


class _QueryGuard:
    """Aborts a SQLite query that overruns a wall-clock deadline.

    Installed via Connection.set_progress_handler: SQLite invokes it every
    _PROGRESS_STEPS VM instructions and aborts the running statement when it
    returns non-zero. `fired` distinguishes a timeout abort (surfaced as
    OperationalError "interrupted") from a genuine SQL error.
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
    """Validate `limit` against the runaway ceiling. Returns an error string to
    hand back to the caller, or None when acceptable. The message names the
    constant and file so the cap is easy to locate and tune if it ever fires."""
    if limit < 1:
        return f"[!] limit must be >= 1 (got {limit})."
    if limit > _MAX_LIMIT:
        return (
            f"[!] limit {limit} exceeds the safety ceiling of {_MAX_LIMIT}. "
            f"This guard catches runaway calls; if you genuinely need more, "
            f"raise _MAX_LIMIT in {Path(__file__).name}."
        )
    return None


@mcp.tool()
def search_chapters(
    query: str,
    db: str | None = None,
    series: str | None = None,
    limit: int = 10,
) -> str:
    """Search for keywords, names, technologies, or equipment across the series database.

    Returns ranked results with chapter number, title, series, arc, and a
    snippet highlighting the matched terms. Use this first to find which
    chapters are relevant, then call get_chapter() to read the full text.

    Query syntax (FTS5):
        Kestrel                 single term
        Kestrel Vance           both terms present (AND)
        "heavy plasma"          exact phrase (plain words only)
        Kestrel OR Vance        either term
        Kestrel NOT prologue    exclusion
        mech*                   prefix match (mech, mechs, mechanical, ...)

    Tokenizer gotchas (unicode61 — hyphens and dots are separators):
        X318 or "X 318"         hyphenated designations: drop the hyphen or
                                use a quoted phrase with a space ("X 318")
                                — bare X-318 parses as X NOT 318
        Vel nir                 dot-separated names: split on the dot
                                — Vel.nir won't parse correctly

    Args:
        query:  FTS5 search expression.
        db:     Corpus-relative path to a .db file matching the schema in
                System_Documentation/Series_Search_Server.md. Default: _DEFAULT_DB.
        series: Filter to one series. Call list_series() to see which values a
                given database actually uses. Only works when the db has a
                'series' column; single-series databases can omit it.
        limit:  Max results. Default 10.

    Returns:
        Formatted list of matching chapters with excerpts, or a diagnostic message.
    """
    limit_err = _check_limit(limit)
    if limit_err:
        return limit_err

    try:
        db_path = _resolve_db(db)
    except ValueError as e:
        return f"[!] {e}"

    if not db_path.exists():
        return (
            f"[!] Database not found: {db_path}\n"
            "See System_Documentation/Series_Search_Server.md > Building a "
            "compatible database."
        )

    guard = None
    try:
        conn = _open_ro(db_path)
        guard = _install_query_guard(conn)
        try:
            # Check if db has 'series' column
            cols = {r[1] for r in conn.execute("PRAGMA table_info(chapters)")}
            has_series = "series" in cols

            match_expr = _wrap(query)
            params: list = [match_expr]

            series_clause = ""
            if series and has_series:
                series_clause = "AND c.series = ?"
                params.append(series.lower().strip())

            sql = f"""
                SELECT
                    {'c.series,' if has_series else ''}
                    c.chapter_num,
                    c.sort_num,
                    c.title,
                    c.arc,
                    c.character,
                    snippet(chapters_fts, {5 if has_series else 4}, '[', ']', '...', 20)
                FROM chapters_fts
                JOIN chapters c ON c.id = chapters_fts.rowid
                WHERE chapters_fts MATCH ?
                {series_clause}
                ORDER BY rank, c.sort_num NULLS LAST, c.seq
                LIMIT ?
            """
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    except sqlite3.OperationalError as e:
        if guard is not None and guard.fired:
            return (
                f"[!] Query aborted: exceeded the {_QUERY_TIMEOUT_S:.0f}s timeout "
                f"guard. If this trips on a legitimate query, raise "
                f"_QUERY_TIMEOUT_S in {Path(__file__).name}."
            )
        return f"[!] Database error: {e}"

    if not rows:
        return f"No results for: {query}"

    lines = [f"Results for '{query}' ({len(rows)} found):\n"]
    for row in rows:
        if has_series:
            ser, ch_num, sort_num, title, arc, char, excerpt = row
            lines.append(f"[{ser}] {title}")
        else:
            ch_num, sort_num, title, arc, char, excerpt = row
            lines.append(title)
        if arc:
            lines.append(f"  Arc: {arc}" + (f"  Character: {char}" if char else ""))
        elif char:
            lines.append(f"  Character: {char}")
        lines.append(f"  ...{excerpt}...")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def get_chapter(
    chapter_num: str,
    series: str | None = None,
    db: str | None = None,
) -> str:
    """Retrieve the full text of a specific chapter.

    Args:
        chapter_num: The chapter number/identifier — e.g. "499", "CLASSIFIED",
                     "0.1.3", "Prologue". Matches the chapter_num column exactly.
        series:      Which series to look in — call list_series() for the values
                     a given database offers. Required when multiple chapters
                     share a number across series. Optional for single-series
                     databases.
        db:          Corpus-relative path to the database. Default: _DEFAULT_DB.

    Returns:
        Full chapter text, or a 'not found' message.
    """
    try:
        db_path = _resolve_db(db)
    except ValueError as e:
        return f"[!] {e}"

    if not db_path.exists():
        return f"[!] Database not found: {db_path}"

    guard = None
    try:
        conn = _open_ro(db_path)
        guard = _install_query_guard(conn)
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(chapters)")}
            has_series = "series" in cols

            if series and has_series:
                row = conn.execute(
                    "SELECT title, content FROM chapters WHERE chapter_num=? AND series=? LIMIT 1",
                    (chapter_num, series.lower().strip())
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT title, content FROM chapters WHERE chapter_num=? LIMIT 1",
                    (chapter_num,)
                ).fetchone()
        finally:
            conn.close()
    except sqlite3.OperationalError as e:
        if guard is not None and guard.fired:
            return (
                f"[!] Query aborted: exceeded the {_QUERY_TIMEOUT_S:.0f}s timeout "
                f"guard. If this trips on a legitimate query, raise "
                f"_QUERY_TIMEOUT_S in {Path(__file__).name}."
            )
        return f"[!] Database error: {e}"

    if not row:
        hint = f" in series '{series}'" if series else ""
        return f"Chapter '{chapter_num}'{hint} not found."

    title, content = row
    return f"{title}\n{'='*len(title)}\n\n{content}"


@mcp.tool()
def list_series(db: str | None = None) -> str:
    """List the series and arcs available in a database, with chapter counts.

    Useful for orientation before searching — tells you what's in a database
    and which arc names you can use to narrow a search.

    Args:
        db: Corpus-relative path to the database. Default: _DEFAULT_DB.

    Returns:
        Formatted overview of series, chapter counts, and arc breakdown.
    """
    try:
        db_path = _resolve_db(db)
    except ValueError as e:
        return f"[!] {e}"

    if not db_path.exists():
        return f"[!] Database not found: {db_path}"

    guard = None
    try:
        conn = _open_ro(db_path)
        guard = _install_query_guard(conn)
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(chapters)")}
            has_series = "series" in cols

            lines = [f"Database: {db_path.name}\n"]

            if has_series:
                for ser_row in conn.execute(
                    "SELECT series, COUNT(*) n FROM chapters GROUP BY series ORDER BY series"
                ).fetchall():
                    ser, n = ser_row
                    lines.append(f"  {ser}: {n} chapters")
                    for arc_row in conn.execute(
                        "SELECT arc, COUNT(*) n FROM chapters WHERE series=? AND arc IS NOT NULL "
                        "GROUP BY arc ORDER BY n DESC LIMIT 10",
                        (ser,)
                    ).fetchall():
                        lines.append(f"      arc: {arc_row[0]} ({arc_row[1]})")
                    lines.append("")
            else:
                total = conn.execute("SELECT COUNT(*) FROM chapters").fetchone()[0]
                lines.append(f"  {total} chapters")
                for arc_row in conn.execute(
                    "SELECT arc, COUNT(*) n FROM chapters WHERE arc IS NOT NULL "
                    "GROUP BY arc ORDER BY n DESC LIMIT 15"
                ).fetchall():
                    lines.append(f"  arc: {arc_row[0]} ({arc_row[1]})")
        finally:
            conn.close()
    except sqlite3.OperationalError as e:
        if guard is not None and guard.fired:
            return (
                f"[!] Query aborted: exceeded the {_QUERY_TIMEOUT_S:.0f}s timeout "
                f"guard. If this trips on a legitimate query, raise "
                f"_QUERY_TIMEOUT_S in {Path(__file__).name}."
            )
        return f"[!] Database error: {e}"

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))

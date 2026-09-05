#!/usr/bin/env python3
"""
index_tools_mcp_server.py - MCP server exposing index rebuild tooling.

Provides one tool:
    rebuild_indexes(load=None | "directory" | "with_files" | "search_status")
        -> formatted summary of the rebuild, optionally with the freshly-built
           content embedded based on the load parameter.

The rebuild scripts and all index/db paths are hardcoded. The server has no
parameters that accept paths from the caller. The only thing reachable
through this interface is running the two known build scripts and reading
back the known output files.

We invoke the Python build scripts directly rather than going through
refresh_indexes.bat because the bat ends with `pause`, which would hang the
subprocess waiting for a keypress. The bat remains available for human use
(double-click from Explorer); this server is the automated path.

Launched by Claude Desktop as a stdio subprocess via claude_desktop_config.json.
Not intended to be run manually.

changed 2026-07-03: rebuild_indexes docstring corrected — FTS index lives at
    index/search_index.db, not Python/search_index.db; noted the vector lane
    rebuilds in the same pass when embedding deps are present.
"""

import datetime
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# --- Paths ---
# CORPUS_ROOT env var allows Docker to override without editing this file.
# Falls back to the local Windows path when not set.
# INDEX_DIR must stay in lockstep with build_indexes.py and indexer.cfg index_directory.

ROOT       = Path(os.environ.get("CORPUS_ROOT", r"D:\claude\filesystem"))
PYTHON_DIR = ROOT / "Python"
INDEX_DIR  = ROOT / "index"
BUILDER    = PYTHON_DIR / "build_indexes.py"
DIRECTORY_INDEX            = INDEX_DIR / "directory_index.md"
DIRECTORY_INDEX_WITH_FILES = INDEX_DIR / "directory_index_with_files.md"
SEARCH_DB  = INDEX_DIR / "search_index.db"

VALID_LOAD_VALUES = {None, "directory", "with_files", "search_status"}

mcp = FastMCP(
    "index-tools",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
)


def _read_claude_section(path: Path) -> str:
    """Read the file's YAML header + Claude section (lines 1 through claude_section_end).

    Returns the joined content, or an error string prefixed with [!] if the file
    is missing, the YAML header is malformed, or claude_section_end can't be parsed.
    """
    if not path.exists():
        return f"[!] Index file not found: {path}"

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[!] Could not read {path}: {e}"

    # claude_section_end lives in the YAML header (lines 1-8); parse it
    match = re.search(r"^claude_section_end:\s*(\d+)\s*$", text, re.MULTILINE)
    if not match:
        return f"[!] Could not find claude_section_end in YAML header of {path.name}"

    end_line = int(match.group(1))
    lines = text.splitlines()
    if end_line > len(lines):
        end_line = len(lines)

    return "\n".join(lines[:end_line])


def _search_status_block() -> str:
    """Return a status block summarizing the corpus search index. Used for
    load='search_status' on rebuild_indexes."""
    if not SEARCH_DB.exists():
        return f"[!] Search index DB not found at {SEARCH_DB}"

    conn = None
    try:
        uri = f"{SEARCH_DB.as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM corpus_fts")
        count = cur.fetchone()[0]
    except Exception as e:
        return f"[!] Could not read search index: {e}"
    finally:
        if conn is not None:
            conn.close()

    mtime = datetime.datetime.fromtimestamp(SEARCH_DB.stat().st_mtime)
    age = datetime.datetime.now() - mtime
    if age.days >= 1:
        age_str = f"{age.days}d ago"
    elif age.seconds >= 3600:
        age_str = f"{age.seconds // 3600}h ago"
    else:
        age_str = f"{age.seconds // 60}m ago"

    return (
        "Search index status:\n"
        f"  Path: {SEARCH_DB}\n"
        f"  Files indexed: {count}\n"
        f"  Last built: {mtime.strftime('%Y-%m-%d %H:%M:%S')} ({age_str})"
    )


@mcp.tool()
def rebuild_indexes(load: str | None = None) -> str:
    """Rebuild the on-disk corpus indexes by running the build scripts directly.

    All three artifacts are rebuilt in a single pass via build_indexes.py:
      - directory_index.md
      - directory_index_with_files.md
      - index/search_index.db (FTS5 full-text index; vector lane rebuilt in
        the same pass when embedding deps are present, unless --no-vectors)

    By default, returns a summary of the rebuild. The optional `load` parameter
    additionally returns the freshly-built content of one specific index, so
    rebuild + load happens in one tool call without a follow-up read.

    Args:
        load: Which artifact to load into the response. One of:
            None (default)     - rebuild only; return summary
            "directory"        - return directory_index.md Claude section
            "with_files"       - return directory_index_with_files.md Claude section
            "search_status"    - return corpus search index_status output

    When to use each `load` value:
        None              - Just refreshing things proactively, no immediate need
                            to read content (e.g. after the user mentions
                            structural changes mid-session).
        "directory"       - Predicted a path that didn't exist; need fresh
                            directory tree to re-orient.
        "with_files"      - About to do filesystem-intensive work and want
                            the fresh complete file listing.
        "search_status"   - corpus-search returned empty for content that
                            should obviously exist; want to confirm the search
                            index rebuilt cleanly before re-running queries.

    Returns:
        Formatted text starting with a rebuild status block. On success, if
        `load` is non-None, the requested content is appended below a
        separator. On failure, returns which step failed and its output for
        diagnosis.
    """
    if load not in VALID_LOAD_VALUES:
        return (
            f"[!] Invalid load value: {load!r}\n"
            f'Valid values: None, "directory", "with_files", "search_status"'
        )

    # Verify build script exists before starting
    if not BUILDER.exists():
        return f"[!] Build script not found: {BUILDER}"

    # Use the same Python interpreter that's running this server
    py = sys.executable

    # Run build_indexes.py directly. --no-pause guarantees no input() prompt;
    # stdin redirect to DEVNULL is a belt-and-braces guard so any rogue read()
    # would EOF immediately rather than block the subprocess.
    # 300s (not 30): a first-run vector rebuild downloads the ONNX embedding
    # model (~90 MB) and/or CPU-embeds many changed docs, which legitimately
    # exceeds 30s. A premature kill rolls back the rebuild's inserts.
    _BUILD_TIMEOUT_S = 300
    try:
        result = subprocess.run(
            [py, str(BUILDER), "--no-pause"],
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_S,
            cwd=str(PYTHON_DIR),
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return (
            f"[!] Index build timed out after {_BUILD_TIMEOUT_S} seconds.\n"
            f"Run refresh_indexes.bat manually from {PYTHON_DIR} to investigate."
        )
    except Exception as e:
        return f"[!] Failed to launch build_indexes.py: {e}"

    if result.returncode != 0:
        return (
            f"[!] build_indexes.py FAILED (exit code {result.returncode})\n\n"
            f"--- STDOUT ---\n{result.stdout or '(empty)'}\n\n"
            f"--- STDERR ---\n{result.stderr or '(empty)'}"
        )

    summary = "[OK] Indexes rebuilt successfully.\n\n" + (result.stdout.rstrip() or "(no stdout)")

    if load is None:
        return summary

    # Append loaded content based on the load parameter
    if load == "directory":
        content = _read_claude_section(DIRECTORY_INDEX)
        section_title = "directory_index.md (fresh)"
    elif load == "with_files":
        content = _read_claude_section(DIRECTORY_INDEX_WITH_FILES)
        section_title = "directory_index_with_files.md (fresh)"
    elif load == "search_status":
        content = _search_status_block()
        section_title = "Search index status (fresh)"
    else:
        # Defensive; should be unreachable due to VALID_LOAD_VALUES check above
        return summary

    separator = "=" * 60
    return (
        f"{summary}\n"
        f"\n{separator}\n"
        f"--- {section_title} ---\n"
        f"{content}"
    )


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))

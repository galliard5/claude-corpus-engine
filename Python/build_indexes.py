#!/usr/bin/env python3
"""
build_indexes.py — Unified index builder.

Single os.walk produces three outputs:
  1. directory_index.md              — compressed directory tree (YAML + dirs only)
  2. directory_index_with_files.md   — compressed directory + file tree (YAML + startup + tree)
  3. Python/search_index.db          — SQLite FTS5 full-text search index

All behaviour is driven by indexer.cfg via cfg_loader.py.
Both files must be in the same directory as this script.

Replaces: build_directory_indexes.py + build_search_index.py

# changed 2026-05-24: fix shallow-dir match for nested paths (e.g. Some_Dir/sub_dir/*.*);
#   walk_and_collect now checks normalized rel path in addition to dir_name;
#   all dir/search pattern comparisons are now case-insensitive (Windows FS is case-insensitive)
#
# changed 2026-06-29: vector lane now caches embeddings by content hash (embed_cache
#   table, persists across rebuilds) so a rebuild only runs the embedder on new or
#   changed docs; build summary reports embedded-new / reused-from-cache / pruned-stale.
#
# changed 2026-07-03: added --check-schemas flag — after building, runs
#   check_schema_drift.py and appends its report. Host-only (needs the MCP stack
#   reachable + docker); refresh_indexes.bat passes it. The in-container MCP rebuild
#   path (index_tools_mcp_server.py) does NOT pass it — it can't reach the servers.
#   Fail-soft: a missing/erroring linter never affects the index build.
#
# changed 2026-07-03: summary no longer hides embedding failures — errors print
#   whenever present (previously gated on skipped>0, which silently swallowed a
#   vector-lane crash), and a failed vector step reports "FAILED" instead of
#   an innocent-looking "Vectors indexed: 0".

Usage:
    python build_indexes.py                   # reads indexer.cfg, writes all outputs
    python build_indexes.py --cfg other.cfg   # use a different cfg file
    python build_indexes.py --console         # print trees to console, skip file writes
    python build_indexes.py --no-pause        # unattended run (used by refresh_indexes.bat)
"""

import argparse
import fnmatch
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

# cfg_loader.py lives alongside this script
sys.path.insert(0, str(Path(__file__).parent))
from cfg_loader import load_cfg

# Optional vector-search lane. embedding.AVAILABLE is False when fastembed /
# sqlite-vec aren't installed (e.g. an older Docker image) — the FTS5 build
# proceeds unchanged in that case.
import embedding


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CFG     = Path(__file__).parent / "indexer.cfg"
OUTPUT_DIRS_ONLY  = "directory_index.md"
OUTPUT_WITH_FILES = "directory_index_with_files.md"
DB_FILENAME       = "search_index.db"

# All three outputs (the two .md indexes and search_index.db) are written
# to the same directory, controlled by [paths] index_directory in indexer.cfg.
# The MCP servers (search_mcp_server.py, index_tools_mcp_server.py) hardcode
# their copy of this path — update them in lockstep if the layout changes.


# ---------------------------------------------------------------------------
# Cfg interpretation
# ---------------------------------------------------------------------------

def _resolve_index_dir(root: Path, raw_index: str) -> Path:
    r"""
    Apply [paths] index_directory resolution rules against a given root.
        blank              -> root  (legacy default)
        starts with / or \ -> root-relative
        anything else      -> absolute path
    """
    raw_index = raw_index.strip()
    if not raw_index:
        return root
    if raw_index[0] in ("/", "\\"):
        return root / raw_index.lstrip("/\\")
    return Path(raw_index)


def resolve_paths(cfg: dict) -> tuple[Path, Path]:
    """
    Determine root and index_dir.

    Root resolution:
        1. CORPUS_ROOT env var — allows Docker to override without editing cfg
        2. root_directory in [paths] cfg section

    index_dir resolution always reads [paths] index_directory from cfg, regardless
    of whether root came from env var or cfg. The env var only controls where the
    corpus is mounted; the cfg controls layout inside it.
    """
    settings = cfg.get("paths", {}).get("settings", {})
    raw_index = str(settings.get("index_directory", ""))

    # 1. Env var override for root
    env_root = os.environ.get("CORPUS_ROOT", "").strip()
    if env_root:
        root = Path(env_root)
        return root, _resolve_index_dir(root, raw_index)

    # 2. Pure cfg path
    raw_root = str(settings.get("root_directory", "")).strip()
    if not raw_root:
        raise ValueError("[paths] root_directory is required but not set in cfg")
    root = Path(raw_root)
    return root, _resolve_index_dir(root, raw_index)


def parse_dir_patterns(cfg: dict) -> tuple[str, set, set]:
    """
    Parse [directory_index] section.

    Pattern syntax (after comment stripping):
        dirname/      -> fully excluded from all outputs
        dirname/*.*   -> shallow: directory visible in tree, contents suppressed

    Returns:
        mode          'blacklist' | 'whitelist'
        dir_excluded  set of directory names
        dir_shallow   set of directory names
    """
    section  = cfg.get("directory_index", {})
    mode     = str(section.get("settings", {}).get("mode", "blacklist")).strip().lower()

    dir_excluded: set[str] = set()
    dir_shallow:  set[str] = set()

    for pattern in section.get("patterns", []):
        p = pattern.strip()
        if not p:
            continue
        if p.endswith("/*.*"):
            dir_shallow.add(p[:-4].strip("/\\").lower())    # 'Trash/*.*'  -> 'trash'
        elif p.endswith("/") or p.endswith("\\"):
            dir_excluded.add(p.rstrip("/\\").lower())        # '.obsidian/' -> '.obsidian'
        else:
            dir_excluded.add(p.lower())                      # bare name, full exclude

    return mode, dir_excluded, dir_shallow


def parse_search_excluded(cfg: dict) -> set:
    """
    Parse [search_index] patterns.
    Returns the set of directory names excluded from search_index.db.
    Always additive on top of dir_excluded.
    """
    patterns = cfg.get("search_index", {}).get("patterns", [])
    return {p.strip().rstrip("/\\").lower() for p in patterns if p.strip()}


def parse_file_types(cfg: dict) -> tuple[str, list[str]]:
    """
    Parse [file_types].
    Returns (mode, [fnmatch_patterns]) e.g. ('whitelist', ['*.md', '*.txt']).
    """
    section  = cfg.get("file_types", {})
    mode     = str(section.get("settings", {}).get("mode", "whitelist")).strip().lower()
    patterns = [p.strip() for p in section.get("patterns", []) if p.strip()]
    return mode, patterns


def parse_context_limits(cfg: dict) -> tuple[int, list[tuple[str, object]]]:
    """
    Parse [context_limits].

    Returns:
        default_limit   int (−1 = full file, 0 = no content, N = first N lines)
        limits          [(fnmatch_pattern, value), ...] in cfg order

    When matching a file, iterate limits in order and keep overwriting —
    last match wins — so general patterns should precede specific ones in the cfg.
    Values are int or ('line', N) tuple as produced by cfg_loader.
    """
    settings = cfg.get("context_limits", {}).get("settings", {})

    raw_default = settings.get("default", -1)
    default = raw_default if isinstance(raw_default, int) else -1

    limits = [
        (key, value)
        for key, value in settings.items()
        if key != "default"
    ]
    return default, limits


# ---------------------------------------------------------------------------
# File type matching
# ---------------------------------------------------------------------------

def matches_file_type(filename: str, mode: str, patterns: list[str]) -> bool:
    """True if filename should be included given mode and fnmatch patterns."""
    fname   = filename.lower()
    matched = any(fnmatch.fnmatch(fname, p.lower()) for p in patterns)
    return matched if mode == "whitelist" else not matched


# ---------------------------------------------------------------------------
# Context limit resolution and file reading
# ---------------------------------------------------------------------------

def _read_line_limit(path: Path, line_num: int) -> int:
    """
    Read line line_num (1-based) from path and return the first integer found.
    Returns -1 (full file) if the line is missing or contains no integer.
    Used to resolve ('line', N) context limit sentinels.
    """
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                if i == line_num:
                    m = re.search(r"\d+", line)
                    return int(m.group()) if m else -1
    except Exception:
        pass
    return -1


def resolve_limit(filename: str, default: int, limits: list) -> object:
    """
    Determine the effective context limit for a file.
    Iterates limits in cfg order; last fnmatch hit wins.
    Returns the raw value (int or ('line', N) tuple) for read_file_content to act on.
    """
    effective = default
    for pattern, value in limits:
        if fnmatch.fnmatch(filename.lower(), pattern.lower()):
            effective = value
    return effective


def read_file_content(path: Path, limit: object) -> str:
    """
    Read file content up to the configured limit.

        limit == 0             -> return '' (path/name only, no content stored)
        limit == -1            -> return full file
        limit == ('line', N)   -> read line N of the file to get actual int limit, then apply
        limit == N (int > 0)   -> return first N lines

    Tries UTF-8 then latin-1; returns '' if both fail.
    """
    if limit == 0:
        return ""

    if isinstance(limit, tuple) and limit[0] == "line":
        limit = _read_line_limit(path, limit[1])

    for encoding in ("utf-8", "latin-1"):
        try:
            if limit == -1:
                return path.read_text(encoding=encoding)
            lines = []
            with path.open(encoding=encoding) as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    lines.append(line)
            return "".join(lines)
        except UnicodeDecodeError:
            continue
        except Exception:
            return ""

    return ""


# ---------------------------------------------------------------------------
# Single unified walk
# ---------------------------------------------------------------------------

def walk_and_collect(
    root:            Path,
    dir_excluded:    set,
    dir_shallow:     set,
    search_excluded: set,
    file_mode:       str,
    file_patterns:   list,
) -> tuple[list, list]:
    """
    Walk the corpus once with os.walk, building all three output datasets.

    Directory ordering per iteration:
        1. Directory entry added to dir_entries first.
        2. Files in that directory processed for search_files second.
    If a directory is blocked (excluded or shallow), its files are never seen.

    Returns:
        dir_entries   [(depth, name, [filenames]), ...]
                      depth 0 = root itself; shallow dirs have empty filename list.
        search_files  [Path, ...]  files to index in search_index.db
    """
    dir_entries:  list[tuple[int, str, list]] = []
    search_files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):

        rel      = Path(dirpath).relative_to(root)   # Path('.') at root
        depth    = len(rel.parts)                     # 0 at root
        dir_name = Path(dirpath).name

        # ----------------------------------------------------------------
        # 1. Shallow dir: add to tree as a leaf, suppress all contents
        # ----------------------------------------------------------------
        rel_str = str(rel).replace("\\", "/").lower()   # lowercase for case-insensitive cfg match
        if rel_str in dir_shallow:
            dirnames[:] = []                              # prevent descent
            dir_entries.append((depth, dir_name, []))    # no files listed
            continue

        # ----------------------------------------------------------------
        # 2. Prune dirs fully excluded from the directory index.
        #    Sorting here gives alphabetical output for free.
        # ----------------------------------------------------------------
        dirnames[:] = sorted(
            (d for d in dirnames if d.lower() not in dir_excluded),
            key=str.lower,
        )

        # ----------------------------------------------------------------
        # 3. Directory entry — always added (for both directory index outputs)
        # ----------------------------------------------------------------
        sorted_files = sorted(filenames, key=str.lower)
        dir_entries.append((depth, dir_name, sorted_files))

        # ----------------------------------------------------------------
        # 4. Files — only queued for search if this dir isn't search-excluded.
        #    Checking rel.parts catches both the excluded dir itself and any
        #    descendant that slipped past the pruning step.
        # ----------------------------------------------------------------
        if any(part.lower() in search_excluded for part in rel.parts):
            continue

        for filename in sorted_files:
            if matches_file_type(filename, file_mode, file_patterns):
                search_files.append(Path(dirpath) / filename)

    return dir_entries, search_files


# ---------------------------------------------------------------------------
# Directory index rendering
# ---------------------------------------------------------------------------

def render_dirs_only(dir_entries: list) -> list[str]:
    """
    Compressed directory-only tree.
    One space per depth level, no decorators.
    """
    lines = []
    for depth, name, _files in dir_entries:
        lines.append(" " * depth + name)
    return lines


def render_with_files(dir_entries: list) -> list[str]:
    """
    Compressed tree including files.
    Directories end with '/'; files indented one level deeper.
    Shallow dirs (empty file list) appear as childless leaf nodes.
    """
    lines = []
    for depth, name, files in dir_entries:
        lines.append(" " * depth + name + ("/" if depth > 0 else ""))
        for filename in files:
            lines.append(" " * (depth + 1) + filename)
    return lines


# ---------------------------------------------------------------------------
# Directory index file assembly
# ---------------------------------------------------------------------------

_YAML_LINE_COUNT    = 8

_STARTUP_BLOCK = (
    "## STARTUP PROCEDURE FOR CLAUDE\n"
    "\n"
    "CHECK 1: Is directory_index.md loaded in this session?\n"
    "  - NO: Skip remaining checks. Use this file normally.\n"
    "  - YES: Proceed to CHECK 2.\n"
    "\n"
    "CHECK 2: Compare scan_utc timestamps (YAML header).\n"
    "  - This file NEWER: Discard directory_index.md. Use this file only.\n"
    "  - directory_index.md NEWER: Proceed to CHECK 3.\n"
    "\n"
    "CHECK 3: Compare compressed sections for structural differences.\n"
    "  - IDENTICAL directories: Discard directory_index.md. Use this file only.\n"
    "  - DIFFERENT directories: Keep both loaded.\n"
    "    \u26a0\ufe0f Directory structures may be inconsistent (one file is stale).\n"
    "    ACTION: Recommend user run: python build_indexes.py\n"
    "\n"
)

# Derived (not hand-counted) so it can't drift from the block above.
_STARTUP_LINE_COUNT = _STARTUP_BLOCK.count("\n")


def _yaml_block(name: str, description: str,
                now_utc: datetime, now_local: datetime,
                claude_section_end: int) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        "keywords: [index, directory, structure, map]\n"
        f"description: {description}\n"
        f"scan_utc: {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"scan_local: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        f"claude_section_end: {claude_section_end}\n"
        "---\n"
    )


def assemble_dirs_only(compressed: list[str],
                       now_utc: datetime, now_local: datetime) -> tuple[str, int]:
    """Returns (file_content, claude_section_end)."""
    claude_end = _YAML_LINE_COUNT + len(compressed)
    yaml = _yaml_block(
        "Directory Index",
        "Auto-generated directory tree snapshot (directories only)",
        now_utc, now_local, claude_end,
    )
    return yaml + "\n".join(compressed) + "\n", claude_end


def assemble_with_files(compressed: list[str],
                        now_utc: datetime, now_local: datetime) -> tuple[str, int]:
    """Returns (file_content, claude_section_end)."""
    claude_end = _YAML_LINE_COUNT + _STARTUP_LINE_COUNT + len(compressed)
    yaml = _yaml_block(
        "Directory Index with Files",
        "Auto-generated directory tree snapshot including files",
        now_utc, now_local, claude_end,
    )
    return yaml + _STARTUP_BLOCK + "\n".join(compressed) + "\n", claude_end


# ---------------------------------------------------------------------------
# Search index (SQLite FTS5)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Extract YAML frontmatter from markdown. Returns (metadata, body).
    Falls back gracefully on missing or malformed frontmatter.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
        if not isinstance(meta, dict):
            meta = {}
        return meta, parts[2].lstrip("\n")
    except yaml.YAMLError:
        return {}, text


def _keywords_str(kw) -> str:
    if isinstance(kw, list):
        return " ".join(str(k) for k in kw)
    return str(kw) if kw else ""


def _embed_hash(text: str) -> str:
    """Stable content key for the embedding cache: sha256 of the exact text fed
    to the model. Identical content (even across files) maps to one cache entry,
    so duplicate bodies are embedded once."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_embed_cache(cur) -> None:
    """Create the persistent embedding cache and guard its model identity.

    embed_cache survives rebuilds (unlike corpus_fts/_meta/_vec), so a model or
    dimension change must invalidate it — otherwise we'd reuse vectors of the
    wrong shape. The one-row embed_cache_info table records what produced the
    cached vectors; a mismatch wipes the cache so it rebuilds cleanly.
    """
    cur.execute(
        "CREATE TABLE IF NOT EXISTS embed_cache ("
        "  hash TEXT PRIMARY KEY,"
        "  embedding BLOB NOT NULL"
        ")"
    )
    cur.execute("CREATE TABLE IF NOT EXISTS embed_cache_info (model TEXT, dim INTEGER)")
    row = cur.execute("SELECT model, dim FROM embed_cache_info LIMIT 1").fetchone()
    if row != (embedding.MODEL_NAME, embedding.EMBED_DIM):
        cur.execute("DELETE FROM embed_cache")
        cur.execute("DELETE FROM embed_cache_info")
        cur.execute(
            "INSERT INTO embed_cache_info(model, dim) VALUES (?, ?)",
            (embedding.MODEL_NAME, embedding.EMBED_DIM),
        )


def _build_vectors(cur, pending_vectors: list) -> tuple[int, int, int]:
    """Populate corpus_vec for this build, reusing cached embeddings.

    pending_vectors is a list of (rowid, content_hash, embed_text). Vectors are
    cached in embed_cache keyed by content_hash, so the embedder only runs on
    hashes not already cached — i.e. new or changed documents. corpus_vec is
    still fully rebuilt (one row per doc, by shared rowid), so rowids stay in
    lockstep with corpus_fts; only the expensive embedding step is skipped.

    Returns (vectors_inserted, embeddings_computed, embeddings_reused,
    embeddings_pruned). The middle two count unique content hashes (actual vs
    avoided model calls); pruned counts stale cache entries evicted this build
    (deleted files plus the superseded versions of edited files).
    """
    _ensure_embed_cache(cur)

    # Stage the hashes this build needs in a temp table so the IN / NOT IN
    # queries below never bump against SQLite's bound-variable limit.
    cur.execute("DROP TABLE IF EXISTS _wanted_hashes")
    cur.execute("CREATE TEMP TABLE _wanted_hashes (hash TEXT PRIMARY KEY)")
    cur.executemany(
        "INSERT OR IGNORE INTO _wanted_hashes(hash) VALUES (?)",
        [(h,) for _, h, _ in pending_vectors],
    )

    # Pull the embeddings we already have for the needed hashes.
    cached: dict[str, bytes] = {
        h: blob
        for h, blob in cur.execute(
            "SELECT hash, embedding FROM embed_cache "
            "WHERE hash IN (SELECT hash FROM _wanted_hashes)"
        )
    }

    # Embed only the misses, deduped by hash (one model call per unique content).
    text_by_hash = {h: t for _, h, t in pending_vectors}
    miss_hashes = [h for h in text_by_hash if h not in cached]
    if miss_hashes:
        vectors = embedding.embed_documents([text_by_hash[h] for h in miss_hashes])
        new_rows = []
        for h, vec in zip(miss_hashes, vectors):
            blob = embedding.serialize(vec)
            cached[h] = blob
            new_rows.append((h, blob))
        cur.executemany(
            "INSERT OR REPLACE INTO embed_cache(hash, embedding) VALUES (?, ?)",
            new_rows,
        )

    # One corpus_vec row per document, by shared rowid.
    cur.executemany(
        "INSERT INTO corpus_vec(rowid, embedding) VALUES (?, ?)",
        [(rid, cached[h]) for rid, h, _ in pending_vectors],
    )

    # Drop cache entries no longer referenced by any current document, so the
    # cache stays bounded to the live corpus rather than growing with every edit.
    # rowcount is the number of stale vectors evicted — capture it before the
    # DROP, which would reset it.
    cur.execute(
        "DELETE FROM embed_cache WHERE hash NOT IN (SELECT hash FROM _wanted_hashes)"
    )
    pruned = cur.rowcount
    cur.execute("DROP TABLE IF EXISTS _wanted_hashes")

    embedded = len(miss_hashes)
    reused = len(text_by_hash) - embedded
    return len(pending_vectors), embedded, reused, pruned


def build_search_db(
    search_files:    list[Path],
    root:            Path,
    db_path:         Path,
    context_default: int,
    context_limits:  list,
    build_vectors:   bool = True,
) -> tuple[int, int, int, int, int, int, list]:
    """
    Drop and rebuild the FTS5 search index from scratch.

    Parameterised SQL throughout — safe against crafted YAML frontmatter.
    path column is UNINDEXED so folder names don't inflate match scores.
    category IS indexed for location-aware search (e.g. category_filter).

    When build_vectors is True and the embedding deps are installed, a parallel
    corpus_vec (sqlite-vec) table is built, sharing each row's rowid with
    corpus_fts so the two lanes can be fused at query time. Embedding is batched
    after the FTS inserts, reusing cached vectors for unchanged content. If the
    deps are absent, the vector step is skipped and only the FTS index is produced.

    Returns (indexed, vec_indexed, vec_embedded, vec_reused, vec_pruned, skipped, errors).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    # Ride out a concurrent reader's lock (the search MCP server opens the DB
    # read-only) instead of failing the rebuild with "database is locked".
    conn.execute("PRAGMA busy_timeout=5000")
    cur  = conn.cursor()

    want_vectors = build_vectors and embedding.AVAILABLE
    # When the deps are present, always drop any prior corpus_vec so we never
    # leave stale vectors whose rowids no longer line up with the rebuilt
    # corpus_fts (e.g. after a --no-vectors run). Dropping a vec0 table needs the
    # extension loaded. Recreate only when we're actually building vectors.
    if embedding.AVAILABLE:
        embedding.load_vec(conn)
        cur.execute("DROP TABLE IF EXISTS corpus_vec")
        if want_vectors:
            cur.execute(
                f"CREATE VIRTUAL TABLE corpus_vec USING vec0(embedding float[{embedding.EMBED_DIM}])"
            )

    cur.execute("DROP TABLE IF EXISTS corpus_meta")
    cur.execute(
        """
        CREATE TABLE corpus_meta (
            path                TEXT    PRIMARY KEY,
            doc_type            TEXT    NOT NULL DEFAULT '',
            missing_name        INTEGER NOT NULL DEFAULT 0,
            missing_keywords    INTEGER NOT NULL DEFAULT 0,
            missing_description INTEGER NOT NULL DEFAULT 0,
            missing_type        INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cur.execute("DROP TABLE IF EXISTS corpus_fts")
    cur.execute(
        """
        CREATE VIRTUAL TABLE corpus_fts USING fts5(
            path        UNINDEXED,
            name,
            keywords,
            description,
            category,
            content,
            tokenize = 'porter unicode61'
        )
        """
    )

    indexed = 0
    skipped = 0
    errors: list[tuple[str, str]] = []
    # (fts_rowid, content_hash, embed_text) collected during the loop, then turned
    # into vectors in one batch after all FTS rows are inserted — reusing cached
    # embeddings for unchanged content. corpus_vec shares corpus_fts's rowid.
    pending_vectors: list[tuple[int, str, str]] = []

    for full_path in search_files:
        try:
            rel_path = full_path.relative_to(root)
        except ValueError:
            continue

        filename = full_path.name
        limit    = resolve_limit(filename, context_default, context_limits)

        try:
            raw = read_file_content(full_path, limit)
        except Exception as e:
            errors.append((str(rel_path), f"Read error: {e}"))
            skipped += 1
            continue

        # Frontmatter only meaningful for markdown
        if full_path.suffix.lower() == ".md":
            meta, body = _parse_frontmatter(raw)
        else:
            meta, body = {}, raw

        name        = str(meta.get("name") or full_path.stem)
        keywords    = _keywords_str(meta.get("keywords"))
        description = str(meta.get("description") or "")
        category    = "/".join(rel_path.parts[:-1])
        path_str    = str(rel_path).replace("\\", "/")

        is_md            = full_path.suffix.lower() == ".md"
        doc_type         = str(meta.get("type") or "") if is_md else ""
        missing_name     = int(is_md and not meta.get("name"))
        missing_keywords = int(is_md and not meta.get("keywords"))
        missing_desc     = int(is_md and not meta.get("description"))
        missing_type     = int(is_md and not meta.get("type"))

        try:
            cur.execute(
                "INSERT INTO corpus_meta(path, doc_type, missing_name, missing_keywords, missing_description, missing_type) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (path_str, doc_type, missing_name, missing_keywords, missing_desc, missing_type),
            )
            cur.execute(
                "INSERT INTO corpus_fts(path, name, keywords, description, category, content) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (path_str, name, keywords, description, category, body),
            )
            indexed += 1
            if want_vectors:
                # corpus_fts is an FTS5 virtual table: rowids are assigned
                # sequentially on insert, so lastrowid is this doc's rowid.
                embed_text = embedding.build_embed_text(name, keywords, description, body)
                pending_vectors.append((cur.lastrowid, _embed_hash(embed_text), embed_text))
        except sqlite3.Error as e:
            errors.append((str(rel_path), f"DB insert error: {e}"))
            skipped += 1

    # --- Vector lane: turn each indexed doc into a corpus_vec row, reusing cached
    #     embeddings for unchanged content so the model only runs on new/changed
    #     docs (the expensive step). ---
    vec_indexed = vec_embedded = vec_reused = vec_pruned = 0
    if want_vectors and pending_vectors:
        try:
            vec_indexed, vec_embedded, vec_reused, vec_pruned = _build_vectors(cur, pending_vectors)
        except Exception as e:
            # Embedding/vector failure must not lose the FTS index — warn and
            # leave corpus_vec empty so search falls back to FTS cleanly.
            errors.append(("<vector index>", f"Embedding error: {e}"))

    # Guarantee the connection closes even if commit fails, so a failed rebuild
    # never leaks the handle (which would block the next run's writes).
    # NOTE: the DROP/CREATE + inserts are still not one atomic transaction — a
    # hard crash mid-rebuild can leave corpus_fts/_meta/_vec empty until the next
    # successful run. Full atomicity needs transactional DDL (unverified with the
    # vec0/FTS5 virtual tables) or a rebuild that preserves the in-DB embed_cache.
    try:
        conn.commit()
    finally:
        conn.close()
    return indexed, vec_indexed, vec_embedded, vec_reused, vec_pruned, skipped, errors


# ---------------------------------------------------------------------------
# Optional schema-drift check (host-only rebuild hook)
# ---------------------------------------------------------------------------

def _run_schema_check() -> None:
    """Run check_schema_drift.py and print its report under a header.

    Host-only: the linter reaches the MCP servers over localhost and spawns a
    docker probe, so it only works where those are available (the refresh_indexes.bat
    path). When run in-container it would fail-soft inside the linter. Isolated in a
    subprocess and fully guarded — a missing or erroring linter never touches the
    index build's own outcome.
    """
    checker = Path(__file__).parent / "check_schema_drift.py"
    if not checker.exists():
        return
    print()
    print("=" * 50)
    print("  SCHEMA DRIFT CHECK")
    print("=" * 50)
    try:
        result = subprocess.run(
            [sys.executable, str(checker), "--no-pause"],
            capture_output=True, text=True, timeout=120,
            cwd=str(Path(__file__).parent), stdin=subprocess.DEVNULL,
        )
        out = (result.stdout or "").rstrip()
        print(out if out else "  (no output)")
        if result.returncode != 0:
            print(f"  [!] drift check exit code {result.returncode} — review the lines above")
    except Exception as e:
        print(f"  [!] schema drift check could not run: {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified index builder — directory trees and search index."
    )
    parser.add_argument(
        "--cfg", default=str(DEFAULT_CFG),
        help=f"Path to cfg file (default: {DEFAULT_CFG.name})"
    )
    parser.add_argument(
        "--console", action="store_true",
        help="Print directory trees to console; skip writing index files"
    )
    parser.add_argument(
        "--no-pause", action="store_true",
        help="Skip end-of-run pause prompt (used by refresh_indexes.bat)"
    )
    parser.add_argument(
        "--no-vectors", action="store_true",
        help="Skip the semantic vector index (FTS5 only). Also skipped automatically "
             "if fastembed/sqlite-vec are not installed."
    )
    parser.add_argument(
        "--check-schemas", action="store_true",
        help="After building, run check_schema_drift.py and append its report. "
             "Host-only (needs the MCP stack reachable); used by refresh_indexes.bat."
    )
    return parser.parse_args()


def main() -> int:
    args  = parse_args()
    start = time.perf_counter()

    # --- Load cfg ---
    try:
        cfg = load_cfg(args.cfg)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        if not args.no_pause:
            input("\nPress Enter to exit...")
        return 1

    try:
        root, index_dir = resolve_paths(cfg)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    _mode_dir, dir_excluded, dir_shallow = parse_dir_patterns(cfg)
    search_excluded                       = parse_search_excluded(cfg)
    file_mode, file_patterns              = parse_file_types(cfg)
    context_default, context_limits       = parse_context_limits(cfg)

    db_path = index_dir / DB_FILENAME

    # --- Walk (single pass) ---
    dir_entries, search_files = walk_and_collect(
        root, dir_excluded, dir_shallow,
        search_excluded, file_mode, file_patterns,
    )

    now_utc   = datetime.now(timezone.utc)
    now_local = datetime.now().astimezone()

    # --- Directory index outputs ---
    dirs_only_lines  = render_dirs_only(dir_entries)
    with_files_lines = render_with_files(dir_entries)

    dirs_only_content,  dirs_only_end  = assemble_dirs_only(dirs_only_lines,  now_utc, now_local)
    with_files_content, with_files_end = assemble_with_files(with_files_lines, now_utc, now_local)

    if args.console:
        print("=" * 50 + "\n  directory_index.md\n" + "=" * 50)
        print("\n".join(dirs_only_lines))
        print("\n" + "=" * 50 + "\n  directory_index_with_files.md\n" + "=" * 50)
        print("\n".join(with_files_lines))
        dirs_only_out  = "console only"
        with_files_out = "console only"
    else:
        index_dir.mkdir(parents=True, exist_ok=True)
        dirs_only_path  = index_dir / OUTPUT_DIRS_ONLY
        with_files_path = index_dir / OUTPUT_WITH_FILES
        dirs_only_path.write_text(dirs_only_content,  encoding="utf-8")
        with_files_path.write_text(with_files_content, encoding="utf-8")
        dirs_only_out  = str(dirs_only_path)
        with_files_out = str(with_files_path)

    # --- Search index ---
    indexed, vec_indexed, vec_embedded, vec_reused, vec_pruned, skipped, errors = build_search_db(
        search_files, root, db_path, context_default, context_limits,
        build_vectors=not args.no_vectors,
    )

    # --- Summary ---
    elapsed    = time.perf_counter() - start
    dir_count  = max(0, len(dir_entries) - 1)   # exclude root itself
    file_count = sum(len(f) for _, _, f in dir_entries)

    print()
    print("=" * 50)
    print("  INDEX BUILD COMPLETE")
    print("=" * 50)
    print(f"  Root:               {root}")
    print(f"  Cfg:                {args.cfg}")
    print()
    print(f"  Directories:        {dir_count}")
    print(f"  Files (tree):       {file_count}")
    print()
    print(f"  Output (dirs):      {dirs_only_out}")
    print(f"    claude_section_end:  {dirs_only_end}")
    print(f"  Output (w/files):   {with_files_out}")
    print(f"    claude_section_end:  {with_files_end}")
    print()
    print(f"  Search DB:          {db_path}")
    print(f"  Files indexed:      {indexed}")
    vec_failed = any(path == "<vector index>" for path, _ in errors)
    if args.no_vectors:
        print(f"  Vector index:       skipped (--no-vectors)")
    elif not embedding.AVAILABLE:
        print(f"  Vector index:       skipped (deps not installed)")
    elif vec_failed:
        print(f"  Vector index:       [!] FAILED — corpus_vec left empty; vector/hybrid "
              f"search degraded to FTS until a rebuild succeeds (error below)")
    else:
        print(f"  Vectors indexed:    {vec_indexed}  [{embedding.MODEL_NAME}, {embedding.EMBED_DIM}-dim]")
        print(f"    embedded {vec_embedded} new, reused {vec_reused}, pruned {vec_pruned} stale")
    if skipped:
        print(f"  Files skipped:      {skipped}")
    # Errors print whenever present — the vector-lane error has no skipped file
    # attached, and gating this on `skipped` once hid a broken embedder entirely.
    for path, err in errors:
        print(f"    {path}: {err}")
    print()
    print(f"  Runtime:            {elapsed:.3f}s")
    print("=" * 50)

    if args.check_schemas:
        _run_schema_check()

    if not args.no_pause:
        input("\nPress Enter to exit...")

    return 0


if __name__ == "__main__":
    sys.exit(main())

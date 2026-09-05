#!/usr/bin/env python3
# name: Embedding Helper
# keywords: [embedding, fastembed, sqlite-vec, vector, semantic, hybrid]
# description: Shared embedding + sqlite-vec helpers for the corpus vector-search lane.
#   Lazily loads a fastembed model (BAAI/bge-small-en-v1.5, 384-dim) and exposes batch
#   (document) and single (query) embedding, plus sqlite-vec extension loading and
#   float32 serialization. Degrades gracefully: if fastembed/sqlite_vec are not
#   installed, AVAILABLE is False so callers fall back to FTS-only behaviour rather
#   than crashing. Used by build_indexes.py (index build) and search_mcp_server.py.
#
# changed 2026-07-03: model cache dir now defaults to .fastembed_cache/ next to this
#   script when CORPUS_EMBED_CACHE is unset. Previously it fell through to fastembed's
#   default (%TEMP%\fastembed_cache on Windows), where Windows temp cleanup gutted the
#   model's snapshot tree and left a present-but-broken cache: fastembed saw the
#   metadata, skipped re-download, and ONNX failed with NO_SUCHFILE on any cache-miss
#   embed. Docker is unaffected (the image sets CORPUS_EMBED_CACHE explicitly).
"""
Embedding helper for the corpus vector-search lane.

The vector lane is OPTIONAL. This module is the single place the rest of the
codebase touches fastembed / sqlite-vec, so the heavy, possibly-absent
dependencies stay quarantined here:

    if embedding.AVAILABLE:
        ... build / query the vector table ...
    else:
        ... pure FTS5 path, unchanged ...

Model: BAAI/bge-small-en-v1.5 — 384-dim, ~90 MB ONNX weights downloaded on
first use and cached by fastembed. It is an asymmetric model: documents are
embedded plain (`embed`), queries get an instruction prefix (`query_embed`).
We honour that split for better retrieval quality.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

# fastembed + sqlite_vec are both required for the lane to function. Track them
# with a single flag — partial availability is useless (can't query without the
# model, can't store without the extension).
try:
    import sqlite_vec
    from fastembed import TextEmbedding

    AVAILABLE = True
    IMPORT_ERROR: str | None = None
except ImportError as _e:  # pragma: no cover - exercised only when deps absent
    AVAILABLE = False
    IMPORT_ERROR = str(_e)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

# Cap the per-document text fed to the embedder. bge-small truncates at ~512
# tokens internally; capping characters first avoids tokenizing megabytes of a
# long lore file only to throw most of it away. ~2000 chars ≈ the model window.
MAX_EMBED_CHARS = 2000

# Model cache directory. The Docker image sets CORPUS_EMBED_CACHE so the
# build-time pre-download and the runtime load resolve to the same baked-in path
# (no fetch on container start). Unset (host runs) -> a persistent dir next to
# this script, NOT fastembed's default: that default is %TEMP%\fastembed_cache on
# Windows, and temp cleanup can strip the model's snapshot tree while leaving its
# metadata, producing a present-but-broken cache fastembed won't self-repair
# (ONNX NO_SUCHFILE on every cache-miss embed). Gitignored; ~90 MB, downloaded
# once on first host embed.
_CACHE_DIR = os.environ.get("CORPUS_EMBED_CACHE") or str(Path(__file__).parent / ".fastembed_cache")

_model: "TextEmbedding | None" = None


def _require() -> None:
    if not AVAILABLE:
        raise RuntimeError(
            f"Vector lane unavailable: {IMPORT_ERROR}. "
            "Install with: pip install fastembed sqlite-vec"
        )


def get_model() -> "TextEmbedding":
    """Lazily construct the embedding model (one instance per process).

    First call triggers the ONNX weight download if not already cached, so it
    can take several seconds. Subsequent calls are instant.
    """
    global _model
    _require()
    if _model is None:
        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=_CACHE_DIR)
    return _model


def load_vec(conn) -> None:
    """Load the sqlite-vec extension into an open sqlite3 connection.

    Toggles enable_load_extension around the load so the connection isn't left
    in a state where arbitrary extensions can be loaded by later SQL.
    """
    _require()
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def serialize(vec: Sequence[float]) -> bytes:
    """Pack a float vector into the compact little-endian float32 BLOB vec0 wants."""
    _require()
    return sqlite_vec.serialize_float32(list(vec))


def build_embed_text(
    name: str, keywords: str, description: str, body: str
) -> str:
    """Compose the text embedded for a single document.

    Metadata (name / keywords / description) leads, then the body, all capped at
    MAX_EMBED_CHARS. Leading metadata means a doc whose frontmatter names the
    topic stays findable even when the cap clips the body.
    """
    parts = [p for p in (name, keywords, description, body) if p]
    text = "\n".join(parts).strip()
    return text[:MAX_EMBED_CHARS]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Batch-embed document texts. Returns one vector per input, order preserved."""
    _require()
    model = get_model()
    return [vec.tolist() for vec in model.embed(texts)]


def embed_query(text: str) -> list[float]:
    """Embed a single search query, applying the model's query instruction prefix."""
    _require()
    model = get_model()
    return next(iter(model.query_embed([text]))).tolist()

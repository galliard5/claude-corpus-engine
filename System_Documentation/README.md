---
name: System Documentation README
type: documentation-index
keywords: [system, documentation, index, navigation, docker, indexer, search, audit]
description: Entry point for the System_Documentation directory; one-line summary of each reference doc.
---

# System Documentation

Reference docs for the infrastructure layer of the corpus — the Docker filesystem MCP container, the index builder, the custom MCP servers, and the audit history. Worldbuilding content lives elsewhere; this folder is about how the *plumbing* works.

> **Repo layout (since 2026-06-12):** the running infrastructure (Docker stack + index builder) is the **corpus-infra** repo at `filesystem\Python\`; these docs are the **system-docs** repo. The bgm server and the worldographer / series-pipeline / pdf-tools / corpus-tools projects moved out to `D:\Claude\projects\` (their own repos, outside the corpus). Paths under `Python\` in these docs are still current; paths that used to point at `Python\bgm\`, `Python\validate_naming.py`, etc. now live under `projects\`.

> **BGM docs relocated (2026-09-04):** `BGM_Server.md` and `Core_Rules/BGM_Instructions.md` moved to the bgm project alongside the code they describe. The server is alpha, lives outside this repo, and a reader here can't run it — documenting it from this side was documenting an absent tool. Same reasoning retired the Worldographer `.wxx` format spec to its own project.

## Files

- **`Architecture.md`** — High-level picture of how Docker, the indexer, the three custom MCP servers (corpus-search, index-tools, series-search), and the on-disk artifacts (indexes, search.db) fit together. Start here.
- **`Docker_Filesystem.md`** — The Docker filesystem MCP container. Building and pinning the image, Dockerfile walkthrough, the `/corpus` mount, container vs Windows paths, restart procedure.
- **`Indexer.md`** — `build_indexes.py`, `cfg_loader.py`, `indexer.cfg`, `index_tools_mcp_server.py`, `refresh_indexes.bat`. Full `indexer.cfg` reference, all pattern syntax, the `line_N` sentinel, and how `rebuild_indexes(load=...)` exposes it to Claude.
- **`Python_Scripts.md`** — Full conventions, rationale, and patterns for Python scripts in the `Python/` directory — the verbose companion to `Python_Scripts_Protocol.md`.
- **`Schema_Drift_Linter.md`** — `check_schema_drift.py`. How the hand-written tool-schema docs are verified against live MCP introspection, the guards against false `[OK]` results, and why it lints rather than generates.
- **`Search_Server.md`** — `search_mcp_server.py`. FTS5 schema (BM25 weights, UNINDEXED columns), `corpus_meta` companion table, the optional `corpus_vec` semantic lane, the `fts`/`vector`/`hybrid` modes (RRF fusion), full query syntax, the three filters (`category_filter`, `type_filter`, `missing_filter`), porter stemming.
- **`Series_Search_Server.md`** — `series_search_mcp_server.py`. FTS5 search over serialised-fiction chapter databases. Schema, the three tools (`search_chapters`, `get_chapter`, `list_series`), how to build a compatible database, and chapter-numbering conventions.
- **`Security_Audit.md`** — Audit habits for Claude-authored Python scripts, the verified-clean walkthrough history of `build_search_index.py`, and danger-keyword checklist for future audits.
- **`Troubleshooting.md`** — Cross-component issues: stale index symptoms, search returning empty, container restart, recovering a corrupted `search_index.db`, hygiene queries.

## Conventions

- All paths in these docs use the Docker-container form (`/corpus/...`) for MCP tool examples, and the Windows host form (`D:\claude\filesystem\...`) for git, CMD, and Explorer operations. The same file has both addresses.
- Anything described as "hardcoded" lives in the source listed in `Indexer.md` or `Search_Server.md` — grep there before assuming a path is configurable.
- These docs are indexed by corpus-search (`type: documentation-*`), so `corpus-search:search_corpus("docker rebuild", type_filter="documentation-component")` will find the right file.

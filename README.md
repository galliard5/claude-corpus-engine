# claude-corpus-engine

A filesystem-backed corpus system for running tabletop RPG campaigns with Claude — plus the
gamemaster rules layer that uses it.

The problem it solves: a worldbuilding corpus outgrows a chat window fast. Once you have a few
hundred files of setting notes, character sheets, and session records, the model can neither hold
them in context nor find the right one reliably. This is the plumbing that makes a large corpus
navigable — a directory index the model reads at session start, ranked full-text and semantic
search over the content, and a set of conventions that make placement predictable enough to guess.

**This repository ships the engine, not a setting.** You supply the content, in a `World_Building/`
directory you create, plus a project profile describing where things live. `World_Building_README.md`
explains both.

---

## What's in here

| Directory | Contents |
|---|---|
| `Python/` | The index builder, three custom MCP servers (corpus-search, index-tools, series-search), Docker Compose stack, and a pinned build of the upstream filesystem MCP |
| `Core_Rules/` | The GM rules layer — narrative rules, scenario extraction protocol, model-selection guidance, and 18 templates |
| `System_Documentation/` | Reference docs for everything in `Python/`. Start at its `README.md` |

`World_Building/` is **not** in this repository — it is where your content goes, and you create it.
`World_Building_README.md` at the root covers what belongs there and how to write the project
profile the engine reads at session start.

Root also carries the session instructions: `file_system_instructions.md` (loaded every session) and
`file_system_reference.md` (loaded on demand). `CHANGELOG.md` records user-visible changes — read it
before upgrading an existing checkout.

## Requirements

- **Docker Desktop** — the MCP servers run as containers
- **Python 3.12+** on the host for the index builder
- **Claude Desktop**, or another MCP client
- Windows paths are used throughout the docs. The stack itself is portable; the `.bat` helpers and
  some path examples are not.

## Getting started

**The clone is the corpus.** Your content goes in a `World_Building/` directory *inside* this
checkout, and the two path settings below both point at the checkout root — not at a content
folder kept somewhere else. The engine reaches its own tooling through that path (`index-tools`
runs `/corpus/Python/build_indexes.py` through the mount), so separating them breaks index
rebuilds while leaving every container looking healthy.

1. Clone, then set `Python/indexer.cfg` `[paths] root_directory` to the full path of the clone.
2. Copy `Python/.env.example` to `Python/.env` and set `CORPUS_HOST_PATH` to that same path.
   The other values are documented in the file.
3. From `Python/`: `docker compose build && docker compose up -d`
4. Build the filesystem MCP image — see `System_Documentation/Docker_Filesystem.md`.
5. Register the servers in your MCP client config.
6. Run `Python/refresh_indexes.bat` to build the first index.
7. Create `World_Building/`, then write a project profile describing your corpus and load it
   alongside `file_system_instructions.md` at session start. `World_Building_README.md` explains
   what goes in one.

Full architecture walkthrough: `System_Documentation/Architecture.md`.

## What isn't included

Some tooling referenced in the docs lives outside this repository and has to be connected
separately. `file_system_instructions.md` marks which is which, because a rule that depends on an
absent tool fails in a way that looks like the model misbehaving rather than a server being missing.

- **A series database.** The series-search server ships without one. `Series_Search_Server.md`
  documents the schema so you can build your own; sourcing the text is your responsibility.
- **Dice rolling.** `Core_Rules/core_rules.md` requires a real-RNG MCP server for resolution rolls,
  on the grounds that a language model asked for a d20 produces a plausible-looking number rather
  than a random one. That server is third-party. The rules include a fallback for running without
  it — the short version is that you disclose it rather than quietly inventing numbers.
- **Symbolic math.** Optional; nothing here hard-depends on it.

## Design notes

A few decisions that aren't obvious from the code:

- **Two SQLite tables, not one.** FTS5's tokenizer splits on hyphens, so `setting-document` is
  unsearchable as a typed value. A companion table holds structured fields for SQL equality.
- **Rebuilds are wholesale, embeddings are incremental.** A full rebuild is sub-second; the
  embedding pass is ~99% of a cold build, so vectors are cached by content hash.
- **Retrieval is not salience.** Opening a file during prep doesn't make its contents part of the
  scene. `core_rules.md` covers why this distinction matters when a model has search available.
- **The docs are linted against the servers.** Hand-written schema documentation drifts in one
  direction — the code changes, the prose doesn't. `check_schema_drift.py` introspects the live
  servers and reports mismatches.

## Licence

Apache-2.0. See `LICENSE` for the full text and `NOTICE` for attribution.

Attribution is required for reuse, including in derivative works — that's Apache §4 rather than
the weaker notice-retention of MIT, chosen deliberately because the rules layer is the part most
likely to be adapted rather than copied.

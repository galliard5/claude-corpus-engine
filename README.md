# claude-corpus-engine

A filesystem-backed corpus system for running tabletop RPG campaigns with Claude — plus the
gamemaster rules layer that uses it.

The problem it solves: a worldbuilding corpus outgrows a chat window fast. Once you have a few
hundred files of setting notes, character sheets, and session records, the model can neither hold
them in context nor find the right one reliably. This is the plumbing that makes a large corpus
navigable — a directory index the model reads at session start, ranked full-text and semantic
search over the content, and a set of conventions that make placement predictable enough to guess.

It also keeps a **verbatim record of play**. Summaries compress and checkpoints capture state rather
than what was said, so sessions are archived exactly as they happened: captured from a share page
rather than reproduced by the model, which cannot be verified.

**This repository ships the engine, not a setting.** You supply the content, in a `World_Building/`
directory you create, plus a project profile describing where things live. `World_Building_README.md`
explains both.

---

## What's in here

| Directory | Contents |
|---|---|
| `Python/` | The index builder, four custom MCP servers (corpus-search, index-tools and series-search in the Docker stack; transcript natively on the host), the transcript capture and cleaning scripts, Docker Compose stack, and a pinned build of the upstream filesystem MCP |
| `Core_Rules/` | The GM rules layer — narrative rules, scenario extraction protocol, model-selection guidance, and 18 templates |
| `System_Documentation/` | Reference docs for everything in `Python/`. Start at its `README.md` |

`World_Building/` is **not** in this repository — it is where your content goes, and you create it.
`World_Building_README.md` at the root covers what belongs there and how to write the project
profile the engine reads at session start.

Root also carries the session instructions: `file_system_instructions.md` (loaded every session) and
`file_system_reference.md` (loaded on demand). `CHANGELOG.md` records user-visible changes — read it
before upgrading an existing checkout.

## Requirements

- **Docker Desktop** — three of the four MCP servers run as containers
- **Python 3.12+** on the host for the index builder
- **Claude Desktop**, or another MCP client
- **For transcript capture only:** `playwright` and `markdownify` on the host, plus a
  Chromium-family browser you already have. Optional — nothing else depends on them. See
  *What isn't included*.
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
5. Register the servers in your MCP client config. The three compose servers are reached over
   HTTP; the transcript server is launched directly by the client and is optional — skip it if
   you don't want session transcripts.
6. Run `Python/refresh_indexes.bat` to build the first index.
7. Create `World_Building/`, then write a project profile describing your corpus and load it
   alongside `file_system_instructions.md` at session start. `World_Building_README.md` explains
   what goes in one.
8. *Optional, for transcripts:* `pip install playwright markdownify`, then register the transcript
   server. `System_Documentation/Transcript_Capture.md` covers the whole pipeline — including why
   it runs on the host rather than in a container.

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
- **A browser and two pip packages, for transcript capture.** The transcript server reads a public
  claude.ai share page and needs `playwright` plus a Chromium-family browser already on the host;
  the cleaner needs `markdownify`. Both run on the host rather than in the Docker stack, so neither
  is in `requirements.txt` — install them with pip the first time you capture a session. Without
  them the rest of the system is unaffected.

  This half of the system is also the most exposed to things outside the repository: it reads a
  share page through the browser, so it depends on claude.ai's page structure, which is
  undocumented and can change without notice. `Transcript_Capture.md` records what it keys off and
  what breaks if that moves.

## Design notes

A few decisions that aren't obvious from the code:

- **Two SQLite tables, not one.** FTS5's tokenizer splits on hyphens, so `setting-document` is
  unsearchable as a typed value. A companion table holds structured fields for SQL equality.
- **Rebuilds are wholesale, embeddings are incremental.** The directory trees and FTS tables are
  dropped and rebuilt every run — sub-second, so incremental complexity isn't worth it. The
  embedding pass is the exception: it is ~99% of a *cold* build, so vectors are cached by content
  hash. In practice a routine refresh is well under a second and a from-scratch build is about a
  minute. See `System_Documentation/Indexer.md` → *Performance*.
- **Retrieval is not salience.** Opening a file during prep doesn't make its contents part of the
  scene. `core_rules.md` covers why this distinction matters when a model has search available.
- **Transcripts are captured, not recalled.** A model asked to reproduce a session from context
  can do it — the turns are right there — but not verifiably: fidelity decays silently over a long
  reproduction and it cannot say which passages drifted. For the one artifact whose whole value is
  being exact, an unmarkable error rate disqualifies it, so the text is read off the rendered page
  instead. The page's *HTML* is archived rather than its visible text, because rendering flattens
  every markdown construct the GM wrote — on one measured session that silently discarded 142
  italics, 52 horizontal rules and 2 tables, and lost link destinations outright.
- **The docs are linted against the servers.** Hand-written schema documentation drifts in one
  direction — the code changes, the prose doesn't. `check_schema_drift.py` introspects the live
  servers and reports mismatches — including the host-run one, because a guard that quietly stops
  covering something is worse than no guard.

## Credits & acknowledgements

**Project author and maintainer:** galliard5. Built as the tooling underneath a private campaign
corpus and used daily for about a year before it was extracted and released.

**Design reference — [RPG OS](https://github.com/croatianrdy2defend-create/RPG-OS)** by
croatianrdy2defend-create (documentation CC BY 4.0, code MIT).

RPG OS attacks the adjacent half of the same problem. Where this engine concentrates on *finding*
the right record in a large corpus, RPG OS concentrates on deciding which retrieved record is
*authoritative*: an explicit stable-truth → campaign-state → current-save precedence, a hard
boundary between current state and historical evidence, and a save protocol with preimages,
recovery markers and lineage. It reaches those properties with no runtime stack at all — ordinary
Markdown files and a capable model — which is a different design position from this one, and a
useful corrective to read against.

Its author's comparative review of the two projects identified several real weaknesses here. Fixes
arising from it are recorded in `CHANGELOG.md`. No text or code is copied from RPG OS; the credit is
for the design work and the critique.

RPG OS credits this project in turn, as a design reference for its v0.7.2 optional-preparation
discussion and its v0.9.0 source-access and audit design.

## Licence

Apache-2.0. See `LICENSE` for the full text and `NOTICE` for attribution.

Attribution is required for reuse, including in derivative works — that's Apache §4 rather than
the weaker notice-retention of MIT, chosen deliberately because the rules layer is the part most
likely to be adapted rather than copied.

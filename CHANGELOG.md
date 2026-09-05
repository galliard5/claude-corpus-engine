# Changelog

Notable changes to this repository, newest first.

**Scope: user-visible change only.** An entry earns its place if a user of this repository would
have to *do* something differently — behaviour, configuration, the MCP tool surface, the startup
procedure, or anything that alters the setup steps. Internal refactors, doc wording, and
housekeeping belong in the commit message and nowhere else.

Finer-grained history lives closer to the code: the scripts in `Python/` and
`Python/filesystem-mcp/Dockerfile` carry `changed YYYY-MM-DD:` entries in their header comments,
recording why a given line looks the way it does. Consult those when chasing a specific
behaviour; consult this file when asking what moved since you last pulled.

**Dates rather than version numbers.** This project evolves opportunistically rather than toward a
planned end state, so a semantic version would either overstate how stable its surface is meant to
be, or turn every change into an argument about which digit to increment. A date just says when.

**Breaking changes are marked, because a date cannot carry that signal.** Warning that an upgrade
will break a working setup is the one job a version number does that a date does not, so the entry
has to do it instead. Where a change requires the reader to act — edit `.env`, rebuild an image,
change a config value, re-register a server — the entry opens with a bold line saying so and
saying exactly what to do:

> **Breaking — action required:** the default series database moved from a constant in
> `series_search_mcp_server.py` to the `SERIES_DEFAULT_DB` environment variable. Set it in
> `Python/.env` and recreate the container with `docker compose up -d series-search`. Without it
> every `series-search` call must name its own `db`, and calls that omit one now return an error
> rather than falling back.

Two rules keep that marker worth reading. Put breaking entries **first** within their date section,
above the ordinary ones. And use it only when the reader genuinely has to do something — an upgrade
that needs nothing from them needs no marker, which will be most of them. The marker is only useful
while it stays rare.

---

## 2026-09-05

**Action required:** rebuild the `corpus-search` image and reconnect your MCP client —
`docker compose up -d --build corpus-search` from `Python/`, then restart Claude Desktop. The
server code is baked into the image, so `docker compose restart` on its own leaves the old build
running; and an MCP client reads the tool list once, at connection time, so a client already
connected will not see `get_section` until it reconnects. Skip either step and you have
documentation describing a tool your server does not serve. Nothing else breaks: existing
`search_corpus` calls keep working throughout.

### Added

- **`corpus-search:get_section(path, heading, level)`** — returns a single `##` section of an
  indexed document instead of the whole file. A search hit on a large reference document used to
  force a whole-file read to reach one heading; on a representative query the search-plus-read
  round trip fell from ~9,400 tokens to ~2,200. The section text is a **verbatim slice** — this
  trims by selection, never by summarising, so prose is never rewritten or paraphrased. Omit
  `heading` to list a document's sections and their sizes first. Heading matching normalises case,
  whitespace and dash style and accepts a unique prefix or substring, so a half-remembered
  heading still resolves; an ambiguous one returns the candidates rather than guessing.

### Changed

- **`search_corpus` results now carry a `Sections:` line** on hits over ~3k tokens, listing each
  section and its rough token cost so you can pick one to pass to `get_section`. This changes the
  output of every existing `search_corpus` call — pass `show_sections=false` for the previous
  format. Smaller documents deliberately don't get the line: the manifest costs about 75 tokens
  per hit, which only pays for itself when the whole-file read it replaces would have been
  genuinely expensive.

Both are derived at read time from the index as it already exists — no schema change, no rebuild
of `search_index.db`, and no change to ranking or scores. `get_section` opens no files: its `path`
is matched for equality against the indexed path and the body comes from the stored content
column, so the server still reaches nothing outside the index.

---

## 2026-09-04 — Initial release

First public release of the engine as a standalone repository.

**Provenance.** This is not a greenfield project. It was extracted from a private worldbuilding
corpus that had been running it daily for about a year, and split so the tooling and rules could
be published without the setting content that drove their design. The rough edges it has are the
ones a year of use did not surface; the conventions it enforces are ones that failed at least once
before being written down.

### Added

- **Filesystem conventions and session protocol** — `file_system_instructions.md` (loaded every
  session) and `file_system_reference.md` (loaded on demand), covering the startup procedure,
  naming and frontmatter standards, tool schemas, editing discipline, and error recovery.
- **`Core_Rules/`** — the gamemaster rules layer: narrative rules, the scenario extraction
  protocol, model-selection guidance, and 18 document templates.
- **`Python/`** — the index builder plus three custom MCP servers, run as one Docker Compose
  stack:
  - `corpus-search` — FTS5 full-text search with an optional semantic vector lane and Reciprocal
    Rank Fusion hybrid mode.
  - `index-tools` — rebuilds the directory indexes and the search database on demand.
  - `series-search` — FTS5 search over serialised-fiction chapter databases. **Ships without a
    database;** `System_Documentation/Series_Search_Server.md` documents the schema so you can
    build one.
  - A pinned local build of the upstream filesystem MCP (`@modelcontextprotocol/server-filesystem`
    2026.8.31), replacing the published image, which lagged npm by several releases.
  - `check_schema_drift.py` — lints the hand-written tool-schema documentation against live MCP
    introspection, so the docs cannot silently drift from the servers.
- **`System_Documentation/`** — reference documentation for everything in `Python/`.
- **`World_Building_README.md`** — what you must supply: a content directory and a project profile
  describing your own corpus.
- **Apache-2.0 licence** and a `NOTICE` file. Section 4(d) carries attribution into derivative
  works, which suits a rules layer more likely to be adapted than copied verbatim.

### Notes for first-time setup

- **The clone is the corpus.** `indexer.cfg` `root_directory` and `CORPUS_HOST_PATH` both point at
  the checkout root, and your content goes in a `World_Building/` directory inside it. Pointing
  them at separate locations breaks index rebuilds while leaving every container looking healthy.
- **The vector search lane is optional.** Without `sqlite-vec` and `fastembed` the index builder
  and search server fall back to full-text only, with no error.
- **Some documented tooling is not included** — a real-RNG dice server and a symbolic maths server
  are connected separately. `file_system_instructions.md` marks which is which, because a rule
  depending on an absent tool fails in a way that looks like the model misbehaving rather than a
  server being missing.

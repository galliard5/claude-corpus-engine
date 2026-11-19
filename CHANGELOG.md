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

## 2026-11-19

### Changed

- **The documented dice server is now `local-table-dice`, with two tools instead of four.** `file_system_instructions.md`
  lists `dice_roll` and `dice_validate` only; jimmcq's `search` and `fetch` documentation tools are gone. `dice_roll`
  takes `notation` and an optional `label` and always returns the breakdown, so `verbose` is dropped. The notation adds
  `d%0` (00–99), exact-face rerolls such as `r1` and `r-1`, and a fixed modifier order: keep/drop, `rN`, `!`, `>N`.
  The server sends its own usage guide as instructions, and the repo's GM and presentation rules take precedence over
  it. jimmcq's `dice-rolling-mcp` stays documented as an alternative with the same two tool names, registered under the
  same `dice-roller` entry. It doesn't support `d%0`, so a campaign that relies on 00–99 rolls should use the new server.
  Its build step is corrected to `npm run build:mcp`; the previously documented `npm run build` builds its web app, not
  the server.

## 2026-11-16

### Changed

- **The shipped `indexer.cfg` declares `baseline` as loaded, not searched.** A new `[rules_layers]` section sets
  `not_searched = baseline`. Before it, every campaign chain naming `baseline` (the base layer every chain starts
  from) refused with "not built and not declared not_searched", so `search_corpus(campaign=…)` and
  `index_status(campaign=…)` worked for no campaign. They now resolve, with `baseline` reported as declared
  loaded. The base system is read at startup as a whole, so it is declared rather than given a database. The
  section is strict: if you have removed or renamed `Game_Systems/Baseline/`, every build and chain call now
  fails naming the problem; remove the line or point it at your base module. Nothing to rebuild: the search
  server reads the config on each call.

## 2026-11-15

### Fixed

- **`index_status(campaign=|chain=)` reports a layer with broken relation tables.** It reported such a layer as
  healthy, while a chain search refused it. The check now happens when the chain is resolved, which both tools
  share, so the status refuses exactly as the search would.
- **A chain listed against its own layers is flagged.** With `chain="house,base"`, where `house` extends `base`,
  `base` was silently treated as the more specific layer: it took the extra result slots, and `house`'s hits read
  "relation undeclared" directly under their own declarations. Status and search now warn when a layer is listed
  below a layer it extends or relates to, and say how to reorder. The search still runs.
- **Every chain-search refusal carries the resolution header.** Two refusals that can only arise after resolution,
  a layer database that changed meanwhile and layer tables that broke meanwhile, printed a single line. They now
  carry the full header, as the reference documents.
- **A vector chain search no longer fails on a layer without vectors.** A layer built with `--no-vectors` falls
  back to full-text search, and it used to receive the natural-language query as FTS syntax. An apostrophe aborted
  the whole search with an `fts5: syntax error`, and plain text matched only documents containing every word. That
  layer is now searched for any of the query's words, and its coverage line says so. Hybrid mode is unchanged,
  since its query is already written for the lexical lane.
- **A build killed inside the registry lock no longer blocks the next one for ten minutes.** The lock now records
  its owner, and a waiter breaks it at once when that process is gone from this machine. A lock from another
  machine or container is still broken by age, after 90 seconds rather than 600. Breaking a lock can no longer
  remove one that another build took in the meantime, and a build removes only its own lock.
- **A Windows sharing violation no longer fails a publish.** When a reader, an editor or a scanner briefly holds
  `registry.json` or the lock file open, the build retries for up to two seconds instead of failing with
  "nothing published".
- **A killed build's temp files are collected.** A build's `.<module>.<build>.tmp.db`, and a registry write's temp
  file, used to stay behind for ever when the build was killed. Collection now removes them once they are six
  hours old.

### Changed

- **A layer can extend a module loaded by declaration.** A layer with `extends: baseline`, where `baseline` is
  listed under `indexer.cfg` `[rules_layers] not_searched` and has no `index.cfg`, used to fail with "build it
  first", which could never succeed. It now builds; the registry records the parent as `extends`, not as a built
  dependency. A relation that targets a section inside such a module is still refused, because there is no database
  to check its address against.
- **Module databases are trusted only inside the corpus.** If `index/systems` (or `index/`) is a junction or link to
  a folder outside the corpus, every module search, fetch, status, chain resolution, build and prune now refuses.
  Before, the outside folder became the anchor for every containment check, and collection could delete files
  there. A `registry.json` that is a link leading out of `index/systems` is refused too. An index directory set
  outside the corpus on purpose, as an absolute `[paths] index_directory`, is still accepted. If you moved
  `index/` with a junction, set that path instead.
- **Campaign lookup ignores profiles reached through a link out of the corpus.** An unknown-campaign error no longer
  lists folder names found outside it, and such a profile no longer makes a campaign name ambiguous.
- **Path comparisons ignore case on every platform.** An adaptation profile's `built_against` and `homebrew` paths
  are matched case-insensitively in the container too, as they already were on Windows, so the two no longer
  disagree about whether a profile is current.
- **`--all-systems` no longer unregisters a module because its folder became a link.** A module folder, its
  `index.cfg` or a whole private root that turned into a junction leading out of the corpus used to be treated as
  removed: the run unregistered the module and deleted its database and embedding cache, with exit 0. Such a module
  now stays registered, and the run says which link is the cause and exits 1. Make it a plain folder again, or
  remove it to retire the module. `--system` for that module now names the link instead of reporting no
  `index.cfg`.

The search fixes are server-side and reach chat once the image is rebuilt (`docker compose up -d --build
corpus-search` from `Python/`). The builder fixes (the lock, the temp files, the loaded parent, the anchored index, the pruning guard)
also reach `rebuild_indexes` from chat only after `docker compose up -d --build index-tools`; a build run on the host
picks them up at once. The tool surface is unchanged.

## 2026-11-14

### Fixed

- **A file that is not valid UTF-8 no longer breaks chain search.** One such byte in any `Game_Systems` manifest
  used to crash every `search_corpus(campaign=|chain=)` and `index_status(campaign=|chain=)` call with a traceback,
  even when the file had nothing to do with the chain. The same went for an `index.cfg` in the builder's lookups
  (`--system` for any module, `--all-systems`, pruning). Now an undecodable manifest or campaign profile refuses,
  an undecodable adaptation profile makes retrieval non-authoritative, and an undecodable `index.cfg` fails only its
  own module's build. In each case the message names the file as not valid UTF-8.
- **Chain search reports an unexpected error instead of raising it**, as single-system search already did. An
  embedding model that cannot load in `vector` or `hybrid` mode now returns `[!] Unexpected error: …`. A connection
  whose vector extension fails to load is closed rather than leaked.
- **Published module databases are opened immutable.** A generation is never written once it is published, so the
  server and the builder now open each one with SQLite's `immutable=1`. SQLite then reads the main file alone and
  never a `-wal` or `-journal` file beside it, which the containment check did not cover. The corpus database is
  opened as before.

- **`--all-systems` no longer strands a layer by pruning what it depends on.** A module whose `index.cfg` is gone
  used to be unregistered, and its database deleted, even while another registered layer depended on it. That
  layer then named a build that no longer existed, and the run still exited 0. Now the module stays registered
  while anything published depends on it. The run says which layers keep it, and exits 1, until they are rebuilt
  without it.
- **`--all-systems` with no module found unregisters nothing.** If `Game_Systems` and the private roots yield no
  `index.cfg` at all while modules are registered, as with a moved or renamed folder, the run used to unregister
  every module and delete every database and embedding cache. It now refuses with exit 1 and changes nothing. To
  retire every module on purpose, delete `index/systems/registry.json` by hand.
- **`--all-systems` claims a module the way `--system` does.** A module claimed by two `index.cfg` files, one
  declaring it and one sitting in a folder of that name, was published by `--all-systems` but refused by `--system`
  and by chain resolution. Both builders now refuse it.
- **A `--system` build refuses a dependency cycle through the published builds.** A layer could relate back to a
  layer whose published build depends on it, and each build in turn succeeded. Only `--all-systems` caught the
  cycle, after both were already published. The build now refuses and names the cycle.

These reach chat once the images are rebuilt (`docker compose up -d --build corpus-search index-tools` from
`Python/`), since both servers and the builder they run are copied into the image. The tool surface is unchanged,
so Claude Desktop needs no restart.

## 2026-11-13

### Added

- **Chain-aware rules search.** `corpus-search:search_corpus` takes `campaign` (a campaign folder whose
  `Campaign_Profile.md` declares a `chain`) or `chain` (layer names, lowest first), and searches that rules chain one
  layer at a time from a single registry snapshot. Hits are grouped by layer, most specific first, each ranked by its
  own database, and no score is compared across layers. Every hit states the relations the chain's layers have
  declared about it, or that none is recorded. `per_layer` caps each layer, and `limit` stays the total cap. A chain
  that cannot be searched as declared refuses and searches nothing.
- **`index_status` takes `campaign` or `chain`** and reports how that chain resolves: each layer's role, build and
  freshness, the snapshot token, whether the adaptation inputs are current, and why a chain search would refuse. It
  searches nothing.
- **`get_section` and `get_system_record` take `expected_build`.** A chain search hit's `Fetch:` line names the
  module and build. Given that build, the fetch serves only from it, and refuses if the module has been rebuilt
  since. Without it, both tools behave as before.
- Every read of a published module database is checked at the moment it is opened: one that has become a link or
  junction leading out of `index/systems` is refused unread. This covers search, fetch and status, and the
  builder's reads of the layers a module depends on, its relations report, and the previous build's embedding
  cache. When that cache is refused, the build re-embeds every document and says why.

Existing calls are unchanged. The new parameters reach chat once the images are rebuilt
(`docker compose up -d --build corpus-search index-tools` from `Python/`; the image now also carries
`rules_chain.py`, which chain search and chain status need) and Claude Desktop is restarted. A chain layer that is
neither an indexed module nor declared loaded in `indexer.cfg` `[rules_layers] not_searched` refuses the whole
chain, by design; `index_status(campaign=...)` names the layer.

## 2026-10-24

### Added

- **Rules layers.** A game-system module's manifest can declare `kind` (`system`, `variant`, `thirdparty` or
  `homebrew`) and `extends` (the layer it builds on), and a `relations.yaml` beside it can declare how its entries
  relate to another layer's: an override, an extension, a partition and so on, each with a status and an optional
  hash pin. Such a module is **layered**: `build_indexes.py --system <module>` builds it at schema 3 with its layer
  metadata and validated relations, checked against the layers it depends on from one registry snapshot. An entry
  or target that does not resolve refuses the build, and so does a dependency rebuilt during it. A module declaring
  neither is built exactly as before, at schema 2.
- **`build_indexes.py --relations <module>`** reports, read-only, each declared relation's pin state (pinned,
  unpinned or changed) and the current target hash to pin.
- **`--all-systems` builds in dependency order.** A dependency cycle is reported. The layers in it, and those
  depending on them, are not built, and the rest still build.
- **`indexer.cfg` `[rules_layers] private_roots`** declares folders that hold private layers, such as a user's own
  homebrew. They are discovered as layer roots and kept out of the corpus search index, but still listed in the
  directory indexes. The section is strict: a misspelled key, a bare line or an empty value fails the build rather
  than silently disabling the exclusion. With no section, every output is unchanged.

Layered (schema-3) modules are searched through `chain=` (2026-11-13). Single-system `search_corpus(system=...)` and
`index_status(system=...)` read schema 2 only.

## 2026-09-26

### Fixed

> **Breaking — action required:** if every filesystem tool fails with *"invalid outputSchema … unsupported
> dialect (draft-07)"*, rebuild the filesystem image and point the local `:latest` at it, then fully quit and
> restart Claude Desktop. From `Python/filesystem-mcp/`:
> `docker build -t mcp/filesystem:2026.8.31-schema2020 .` then
> `docker tag mcp/filesystem:2026.8.31-schema2020 mcp/filesystem:latest`.

- **The filesystem MCP works again with current Claude clients.** Clients released around this date validate
  tool schemas against JSON Schema 2020-12 only and reject all 14 filesystem tools, because the upstream server
  declares draft-07. The fault is in the MCP TypeScript SDK v1 (upstream `typescript-sdk#2084`, fix pending in
  PR #2085), not in `server-filesystem`, whose latest release is still affected. The pinned image now patches
  the SDK's default dialect at build time, and a build-time probe fails the build if any tool still declares
  draft-07. The patch is temporary; the Dockerfile says when to remove it.
- **The weekly update check also watches for the upstream fix.** While the patch is in place,
  `check_filesystem_update.py` reports and notifies once PR #2085 is merged and an SDK release follows it.
  That check adds one request to `api.github.com` and one to the npm registry.

## 2026-09-25

### Added

> **Breaking — action required:** the search index schema changes (schema 2), and the server no longer reads a
> schema-1 index — it answers "rebuild" instead of searching. From `Python/`, rebuild the images with
> `docker compose up -d --build corpus-search index-tools`, then rebuild the index with
> `python build_indexes.py`, then restart Claude Desktop so it sees the new tool and parameters. To build the
> game-system module databases as well, run `python build_indexes.py --all-systems`. Search results over the
> corpus are unchanged.

- **Game-system rules get their own search databases.** A rules module under `Game_Systems/` can declare a strict
  `index.cfg` naming which of its directories hold the verbatim rules, condensed rules and structured datasets.
  `build_indexes.py --system <module>` (or `--all-systems`) builds it into `index/systems/`, apart from the corpus,
  so rules never mix into lore results.
- **`search_corpus`, `get_section` and `index_status` take `system="<module>"`**, and `search_corpus` takes
  `representation_filter`. Every rules hit says whether it is the source text, a condensed rule or a dataset record,
  and how authoritative it is.
- **New tool: `corpus-search:get_system_record`** returns one structured record whole — a stat block, a weapon,
  an item — with its source, so a statistic is never read out of a search snippet.
- **`index-tools:rebuild_indexes` takes `system`** to rebuild one module's database from chat.
- `index_status(system=...)` reports whether a module's sources have changed since its database was built.
- **Records read from a table row show the table's source.** A module's `index.cfg` can declare `row_refs`, the
  record fields that point a row-derived record at the table that owns its lines. `get_system_record` and search
  hits then print `Source (via row reference)` with the table's file, anchors and row line, instead of
  "none recorded". Takes effect after rebuilding the `corpus-search` image and the module's database.

---

## 2026-09-12

### Changed

> **Breaking — action required:** `Core_Rules/core_rules.md`, `Core_Rules/Skill_Trees.md` and
> `Core_Rules/Model_Selection_Guide.md` are removed. Anything that loads them by name — a client
> instruction file, a project profile, a saved prompt — must point at `Core_Rules/Start_Here.md`
> instead. That file names every rules file a session loads and resolves which game system is in
> force. Campaigns without a `Campaign_Profile.md` keep running on the shipped defaults, plus
> anything their setting profile defines for them; nothing needs to be created for them.
>
> **Upgrading a corpus you already play in, rather than starting fresh? Have an agent do the
> migration** — a coding agent pointed at your checkout, this entry and `Start_Here.md`. The risk is
> not a file that fails to load; it is a campaign that quietly runs different rules, such as a
> skill-tree record left where nothing reads it any more. Ask the agent to confirm that every
> campaign resolves the same system, skill-tree setting and register before and after.

> **Breaking — action required:** setting- and programme-scoped material moves out of
> `World_Building/Project_Profile.md` into `World_Building/[Setting]/Setting_Profile.md`, one file
> per setting, and the project profile is no longer read for any of it. Move each setting's
> `PROSE REGISTER` entry into that setting's profile under the same heading. If your project profile
> records which campaigns run skill trees, record that again — as a programme block in the setting's
> `PROGRESSION` section, or as `skill_trees: on` in a campaign profile — or those campaigns run
> without trees. A setting with no profile is reported as having no register rather than stopping
> play.

- **Setting profiles.** `World_Building/[Setting]/Setting_Profile.md` holds material belonging to
  the setting: the prose register and world-state pointer every campaign there shares, and
  optionally a `PROGRESSION` section recording what the setting's transformations do to Essence,
  whose programme blocks turn skill trees on for the campaigns they list. Setting profiles prescribe
  no Essence branch names; a character's branches are named in play. `World_Building_README.md`
  describes the file.
- **Campaign profiles can adjust their setting's register** under *Register adjustment*, recording
  only the difference. `skill_trees` in the template is now empty by default, so a copied template
  inherits from the setting instead of switching trees off.
- **The GM ruleset is split into modules.** `core_rules.md` becomes four fixed modules in
  `Core_Rules/` — `gm_rules.md` (how to run the game), `epistemics.md` (what may be known),
  `presentation.md` (what the player sees) and `operating_procedure.md` (session harness) — plus
  `scenario_prep.md`. `Start_Here.md` is the single entry point and gives the load order.
- **Game rules move to `Game_Systems/`.** `Baseline/` holds the shipped rules-light system and the
  Emergent Skill Tree System (`skill_trees.md`, formerly `Core_Rules/Skill_Trees.md`). `DnD5e/` is
  a sample d20 module built from SRD 5.1, and it currently implements the 2014 rules only. That is
  the extent of what the module covers so far, not a lock on other editions: a campaign that selects
  one the module does not implement is stopped before play and told why, rather than silently run
  on 2014 rules it did not ask for. Its adaptation profile is in `Adaptations/`.
- **Other game systems can be added.** A system module pins what has to be exact and leaves out
  what a model reliably knows; an adaptation profile settles how it stacks on Baseline. The sample
  module shows both. Import a published system with an agent's help from its source material — its
  mechanics, and any lore or setting it depends on, within that material's licence — or build one of
  your own.
- **Per-campaign selections** go in `Campaign_Profile.md` in the campaign's directory, copied from
  `Core_Rules/Templates/Campaign_Profile_Template.md`. It selects doctrine and presentation options
  and names the game system chain. It does not restate setting-level material, which lives in the
  setting's own profile.
- **Invalid configurations stop before play.** An unsupported edition, a multi-module chain without
  an adaptation profile, or a stale compiled ruleset is reported with the file involved rather than
  replaced by defaults — see `Start_Here.md`.
- **Homebrew rules sidecars** matching `homebrew_*` are gitignored by default.
- **`NOTICE`** carries the CC-BY-4.0 attribution for the SRD 5.1 material in `Game_Systems/`.

## 2026-09-09

### Added

- **`Working_Documents/` is now meant to hold its own local git repository**, and ships the
  `.gitignore` and `.gitattributes` it needs so that adopting the convention is `git init` and
  nothing else. No action is required — skip it and the directory behaves exactly as before.

  The directory's contents are excluded from this repository on purpose and that has not changed:
  handoffs and proposals name unfinished decisions, quote paths that are about to move, and record
  conclusions that later turned out to be wrong. But the consequence was that they had no history
  anywhere, so a handoff could be rewritten or deleted with no record of what it previously said —
  a poor property for the documents that carry unfinished work between sessions. What was missing
  was never publication, only the ability to see what changed.

  Ownership splits along the same line the directory already had: this repository owns the
  scaffolding that defines the convention — `README.md` and the two dotfiles — and the local
  repository owns the documents it holds. Each ignores the other's files, so nothing sits under
  two histories.

  Two mechanical notes, both of which cost a debugging session if you meet them by surprise.
  Gitignore's `*` matches a leading dot, unlike shell globbing, so the dotfiles need explicit
  negations. And a nested repository is its own attribute scope: the parent's line-ending
  normalization does not reach across the boundary, which is why `.gitattributes` is duplicated
  rather than inherited.

---

## 2026-09-08

**Action required:** register the new server and restart your MCP client. **Quit the client first,
then find the config by searching rather than by path.** Claude Desktop holds this file in memory
and rewrites it on exit, so an edit made while it is running is silently discarded — and on a
packaged (MSIX/Store) install `%APPDATA%\Claude` is a redirection that only exists *while Desktop
runs*, so quitting removes the very path most instructions name. The real file then lives under
`%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\`. Quit fully, locate it with
`Get-ChildItem $env:APPDATA,$env:LOCALAPPDATA -Filter claude_desktop_config.json -Recurse -Force`,
edit that file, then start Desktop. Add to it (or to your client's equivalent):

> ```json
> "transcript": {
>   "command": "python",
>   "args": ["<corpus>/Python/transcript_mcp_server.py"],
>   "env": {"CORPUS_ROOT": "<corpus>"}
> }
> ```
>
> Then `python -m pip install playwright markdownify` on the **host** interpreter, and restart the
> client — an MCP client reads the tool list once at connection time, so a client already running
> will not see the tool. Skip the restart and you have documentation describing a tool your client
> does not serve. Nothing else changes: every existing server and tool behaves as before.

### Added

- **`transcript:capture_session_transcript`** — captures a session transcript from a public
  claude.ai share link, writing the raw JSONL archive and deriving the readable markdown from it.
  This puts the capture pipeline added yesterday behind a tool the GM can call at a checkpoint,
  rather than it being a thing the operator runs by hand between sessions.

  **It runs natively on the host, not in the Docker stack**, and that is not an oversight. Capture
  drives a real browser: claude.ai challenges headless ones, a container has no display, one image
  serves all three existing servers so a browser would bloat the two that will never use it, and
  the containers currently reach nothing but the mounted corpus — capture would need outbound
  HTTPS. The host already has a browser and the problem does not arise there. `Python/Dockerfile`
  copies by explicit filename, so nothing new lands in the image.

  Its dependencies (`playwright`, `markdownify`) are deliberately **not** in
  `Python/requirements.txt`, which is baked into every server image for something no container
  runs. Playwright drives the browser already installed on the host, so the bundled ~150MB
  Chromium download is not needed.

  Guards mirror `index-tools`: the two scripts are hardcoded, no parameter accepts a filesystem
  path, output locations are derived from the corpus root and a whitelisted campaign/session that
  cannot express a path traversal, and the share URL must match the claude.ai share form. An
  existing capture is refused rather than overwritten unless `overwrite=true`, because the raw file
  is the archive copy. A failed capture writes nothing; if capture succeeds but the cleaner fails,
  the raw archive is intact and the transcript can be rebuilt without recapturing.

- **The indexer now logs every build to `Python/build_history.jsonl`**, and
  `corpus-search:index_status` reports what the last build cost — runtime, whether it was cold or
  reused cached embeddings, the FTS/embed split, and the median and range across recent builds on
  the same invocation path.

  Every performance figure in these docs has been a hand-measured snapshot with no mechanism for
  noticing when it stops being true. The cold-build number said `~40s for ~500 docs` until a
  from-scratch rebuild was run by hand and came back at about a minute; nobody knew in between, and
  the corrected numbers would have rotted the same way. A running log turns the next correction from
  a re-measurement into a query, and answers what a single measurement structurally cannot: whether
  a build is slower because the corpus grew or because something regressed. It also accumulates the
  evidence behind the *"not profiled for >10× scale"* caveat in `System_Documentation/Indexer.md`.

  The log records raw signals rather than conclusions — there is deliberately no `cold: true` field,
  because that is the definition most likely to drift. `index_status` derives "cold" from
  `reused == 0 and embedded_new == files_indexed`, so changing that definition later re-classifies
  rows already written instead of invalidating them.

  Nothing to do: the file is created on the next build, is gitignored as machine-specific
  operational data, and grows by a few hundred bytes per build. Writing it can never fail a build —
  every error is swallowed after a one-line notice, because a logging fault that made
  `refresh_indexes.bat` report failure over a good index would be strictly worse than no log.

  It lives beside the builder rather than in `index/` on purpose: the log's whole value is
  outliving the index. That also puts it inside the corpus mount, and `index-tools` mounts
  `/corpus` read-write, so rebuilds triggered from chat append to the same history the host `.bat`
  writes instead of splitting it in two.

### Changed

- **The build summary now prints a phase split** — `walk / dir-index / fts / embed` — beside the
  total runtime. Previously a single `perf_counter` pair covered the whole run, so a slow build gave
  no clue which part was slow. The phases do not sum to the total; they exist for comparing like
  with like across builds, not for accounting for every millisecond.

  The first thing the log showed is worth knowing: on the same corpus and the same warm cache, a
  rebuild through `index-tools` takes an order of magnitude longer than the same build run on the
  host, essentially all of it in the file-reading phase — the bind mount, not the indexer. That is
  why the trend line in `index_status` is scoped to a single invocation path; a median pooled across
  both describes neither.

---

## 2026-09-07

### Added

- **The GM now tags scene changes in the status block.** When the next beat begins a new scene,
  `Core_Rules/core_rules.md` (SECTION 6 > *Display*) adds a third line beside the existing time and
  status lines: `` `[ Scene: the mill yard — the warden, the steward ]` ``. It appears only at a
  transition, never on every turn.

  The names after the dash are a **witness list** — a record of who could perceive what happens in
  that scene, which is what the Information Firewall needs and has never had in durable form. Until
  now, who was present in a given scene existed only implicitly in prose, and reconstructing it
  afterwards meant guessing. The rule is explicit that an uncertain cast should be omitted rather
  than guessed: a missing tag costs one boundary and is recoverable, while a wrong name grants an
  NPC knowledge of something they never witnessed, and nothing downstream can distinguish a guessed
  witness from an observed one.

  The tag is **forward-looking**. It sits immediately before the choice options, so it names the
  scene the player is about to enter, not the one just narrated.

  Nothing breaks if it is absent — it is an addition to a block the GM already writes, and every
  existing rule behaves as before. Sessions recorded before this change simply carry no scene
  boundaries.

### Changed

- **Session transcripts are now captured mechanically instead of pasted by hand.**
  `Session_Transcript_Stub.md` and `Post_Session_Checklist.md` previously asked the player to paste
  the conversation into a stub and hand-clean it. The transcript is now captured from a public
  share link by `Python/capture_transcript.py` and rendered by `Python/clean_transcript.py`, which
  store the message HTML as the archive copy and derive the readable markdown from it. Both run on
  the host, not in the Docker stack — capture drives a real browser. Their dependencies
  (`playwright`, `markdownify`) are deliberately **not** in `Python/requirements.txt`, which is
  baked into the MCP server images; install them with pip when you first capture a session. Keeping the raw capture means a later fix to the cleaner can be re-applied to
  old sessions rather than the original having been destroyed by the first cleanup pass.

  This matters beyond convenience: the visible text of a rendered conversation silently discards
  everything markdown carries. Measured on one real session — 142 italics, 103 code spans, 52
  horizontal rules, 2 tables and 16 headings flattened, and link destinations lost outright. A
  horizontal rule has no text at all, so 52 authored divisions were vanishing without leaving
  evidence they had existed.

  The stub remains, reduced to frontmatter, for sessions where capture is deferred.

- **The stated reason Claude must not write a transcript was wrong, and is replaced.** Both files
  claimed Claude "has no way to *copy* a conversation" and likened it to an LLM rolling dice. Prior
  turns are in context, so that is false, and the dice comparison inverts the situation — with dice
  the information does not exist, whereas here it does. The rule was correct; its justification was
  not, and a HARD RULE resting on an argument a model can see through is one it can talk itself
  past. It now rests on the real reasons: reproduction is unverifiable, fidelity decays silently
  with no confidence signal, compaction lands exactly when the transcript is wanted, and a capture
  tool selects the text rather than regenerating it.

- **A search that finds nothing no longer counts as proof the fact is unauthored.** Both
  `Core_Rules/core_rules.md` (*Retrieval Is Not Salience*) and `file_system_instructions.md`
  previously said an empty result meant the fact was not established. That is not sound given
  conditions this repository documents elsewhere: a stale index, keyword-only matching in `fts`
  mode, and the scope exclusions in `indexer.cfg` all return nothing for material that is present.
  Both now draw the distinction between **not found** and **does not exist**, and require freshness,
  wording and scope to be checked before a detail is treated as unauthored.

  The consequence this closes is not a missing detail. An unconfirmed absence read as a confirmed
  one is how a record that exists gets replaced by an invention — which the next checkpoint then
  writes to the corpus as canon. The rules' original purpose is unchanged and both are stricter
  than before: a *confirmed* absence still means the fact is unfixed, and still is not licence to
  invent one.

  No tool, schema or configuration change; nothing to rebuild or reconnect. The two files had also
  drifted apart in strength, with `file_system_instructions.md` alone mentioning the freshness
  check — they now agree.

  This came out of a comparative review against [RPG OS](https://github.com/croatianrdy2defend-create/RPG-OS),
  whose separation of *not found* from *does not exist* is the distinction adopted here. See
  *Credits & acknowledgements* in `README.md`.

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

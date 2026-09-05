---
name: Schema Drift Linter
type: documentation-component
keywords: [schema, drift, linter, check_schema_drift, introspection, mcp, tool-schemas, corpus-infra]
description: Reference for check_schema_drift.py — how tool-schema documentation is verified against live MCP server introspection, plus the design rationale for why it lints rather than generates.
---

> **Last edited (UTC):** 2026-09-04T21:00:00Z

# Schema Drift Linter

**Status: built and running.** `Python/check_schema_drift.py` (corpus-infra), hooked into the host
rebuild path via `build_indexes.py --check-schemas`, which `refresh_indexes.bat` passes.

This document is the reference for that script and the record of why it works the way it does. It
began as a design proposal weighing two variants; the recommended one was built on 2026-07-03 and
the rationale is preserved below because the rejected option is still the obvious thing to reach
for, and the reasons not to are worth keeping.

## What it does

Introspects the live MCP servers and diffs them against what the docs claim — tool names present
or absent, parameter names, required/optional flags. It writes nothing. It prints a drift report:

```
[SCHEMA DRIFT] file_system_reference.md documents 'read_text_file' — not served by any live server
[SCHEMA DRIFT] live tool 'series-search:get_chapter' has param 'chapter_num' — quickref says 'chapter'
[OK] 16/17 documented tools match live schemas
```

**It caught two real doc bugs on its first run** — `directory_tree`'s `excludePatterns` and
`read_file`'s `head`/`tail`, both undocumented.

## How it works

- **The `mcp` package is on the host** (1.27.0), so introspection uses the real MCP client for both
  transports — no hand-rolled JSON-RPC. HTTP via `streamablehttp_client` to `localhost:8001-8003`;
  filesystem via `stdio_client` spawning `docker run`.
- **Filesystem server: spawn-and-ask over stdio.** The design sketch expected this to be fiddly and
  recommended a cheaper digest-pin instead. The stdio handshake turned out to work cleanly, so the
  accurate option won. It mounts an empty temp dir, never the real corpus.
- **The digest-pin concern is moot anyway.** The filesystem image is a *self-built pin*
  (`Python/filesystem-mcp/Dockerfile`), not Docker Hub's `:latest`, so it only changes on a
  deliberate rebuild — exactly when you'd want to re-verify. (Aside found while wiring this up:
  Claude Desktop strips the image tag from its config on restart, so the pin is enforced by
  retagging the local `:latest`, not via the config. See `Docker_Filesystem.md`.)
- **Both doc surfaces are linted.** The quickref in `file_system_instructions.md` is the
  higher-blast-radius one — it loads into chat context every session — so it is not exempt. Both
  parse off a **locked greppable convention** embedded in `file_system_reference.md`, in a contract
  note that names this script.
- **Both guards implemented:** parse-count (0 blocks ⇒ `[PARSE ERROR]`, so a reformatted or broken
  block is reported rather than silently under-counted) and checked-vs-skipped (fail-soft per
  server; an unreachable server yields `[INCOMPLETE]`, never a false `[OK]`). A down container is
  not schema drift.
- **The hook is host-only.** The in-container `index_tools` rebuild path can't reach `localhost` or
  spawn docker, so it is left unhooked; the host `refresh_indexes.bat` path carries the check. A
  scheduled-task trigger remains an option if the manual path proves too infrequent.

---

# Design rationale (original writeup, preserved)

## Problem being solved

Tool schemas are documented by hand in `file_system_reference.md` (full) and
`file_system_instructions.md` (quickref). A 2026-07-03 review found the reference documenting an
upstream filesystem server version that was never deployed — 14 tools described, 11 live;
`read_file` marked deprecated when it was the current tool; a canonical verification pattern that
would error if followed. Hand-maintained copies of machine-readable truth drift, always in the same
direction: the code changes, the prose doesn't.

Making the prose openly defer to `tool_search` makes the drift *harmless*. Introspection makes it
*visible*.

## Two variants — decide which before building anything

### Variant A — full generation

A script introspects the live MCP servers and **regenerates** the TOOL SCHEMA REFERENCE section of `file_system_reference.md`, writing between guard markers so hand-written prose around the section survives:

```
<!-- SCHEMA_AUTOGEN_START — do not hand-edit between markers -->
...generated schemas...
<!-- SCHEMA_AUTOGEN_END -->
```

Pros: zero drift by construction; the doc is always right.
Cons: the current schema section is not just schemas — it carries usage examples, caveats, anchor-pattern tips, "when to use" prose. Generation either loses that editorial layer or needs a per-tool sidecar of hand-written annotations merged into the generated output (more machinery). Also a cross-repo write: the script lives in corpus-infra, the target file is in the worldbuilding repo — mechanically trivial (same disk), conceptually a little ugly.

### Variant B — drift linter (recommended starting point)

A script introspects the live servers and **diffs** them against what the docs claim: tool names present/absent, parameter names, required/optional flags. It changes nothing — it prints a drift report:

```
[SCHEMA DRIFT] file_system_reference.md documents 'read_text_file' — not served by any live server
[SCHEMA DRIFT] live tool 'series-search:get_chapter' has param 'chapter_num' — quickref says 'chapter'
[OK] 16/17 documented tools match live schemas
```

Pros: tiny surface, no writes, keeps the human-authored prose fully human-authored, and catches exactly the failure class that actually happened. Can hang off the existing rebuild path (a `--check-schemas` flag on `build_indexes.py`, or a standalone `check_schema_drift.py`) so it runs whenever indexes rebuild — drift gets noticed within a session or two instead of within a year.
Cons: still requires a human (or Sonnet) to fix the doc when it fires. That's acceptable — Option 1 already guarantees the doc can only be a stale hint, and the linter turns "stale for months" into "flagged next rebuild."

**Recommendation:** build Variant B. Revisit Variant A only if linter reports become frequent enough that hand-fixing is the bottleneck.

## Technical sketch (both variants share the introspection half)

### Introspecting the three custom servers — easy

`corpus-search` (8001), `index-tools` (8002), `series-search` (8003) serve streamable-HTTP MCP. A small client using the `mcp` Python package (already in `requirements.txt` for the servers) connects to each `http://localhost:800N/mcp` and issues `tools/list`. Response gives tool name, description, and full JSON input schema — parameter names, types, required list. That is everything the linter needs.

Precondition: the Docker stack must be up. The script should fail soft per-server ("corpus-search unreachable — skipped") rather than aborting, since a down container is not schema drift.

### Introspecting the filesystem MCP — the awkward one

It is launched by Claude Desktop as a stdio `docker run`, not part of the compose stack, so there is no port to hit. Three approaches, cheapest first:

1. **Pin-and-trust:** don't introspect it. Record the image tag/digest the docs were written against (`mcp/filesystem:latest` → resolve to a digest at doc-verification time) in the reference frontmatter; the linter only checks whether the *currently pulled* image digest still matches the recorded one, and warns "filesystem image changed — re-verify 11-tool schema section by hand" when it doesn't. Catches the realistic drift trigger (image update) without MCP-over-stdio plumbing.
2. **Spawn-and-ask:** the script launches its own short-lived `docker run -i` of the same image with a throwaway mount, speaks MCP over stdio (`mcp` package supports stdio client sessions), issues `tools/list`, exits. Fully accurate, moderately fiddly (handshake, timeouts, Windows + Docker stdio quirks).
3. **Skip entirely:** filesystem tools are the ones used hundreds of times per session; drift there gets noticed organically. Lint only the three custom servers.

Recommendation: approach 1 for the linter's first version. It's ten lines and covers the trigger that matters.

### Parsing the docs side

The linter needs the documented tool/param names. Two ways:

- Parse the markdown (fragile — prose formats shift).
- Give the reference's schema section a strict, greppable convention: each tool as a fenced block with a `params:` list in fixed form (it already nearly is). The linter regexes tool headers + param lines only, ignores all prose. Queue 1a's rewrite is the natural moment to lock that convention in — worth one line in the handoff plan if this proposal is accepted before Queue 1a runs.

### Script category & conventions

Variant B is a **read-only/report script** under `Python_Scripts.md` conventions: no `--dry-run` needed, `--no-pause` supported, prints `Runtime:`. Lives in corpus-infra (`Python/`) since it depends on the `mcp` package and the compose stack. Variant A would be a **modification script** (writes a corpus file): `--dry-run` + preview + `Apply changes? [y/N]` mandatory, and an audit pass per `Security_Audit.md` — note the danger-keyword list flags network access; the linter's localhost MCP calls are a legitimate, documented exception that should be called out in the script header.

### Integration options

- Standalone: `python check_schema_drift.py` from CMD.
- Hooked: `build_indexes.py --check-schemas`, or called by `index_tools_mcp_server.py` after a rebuild with drift lines appended to the rebuild summary Claude already reads. The hook is what makes drift *visible without anyone remembering to look* — strongly preferred over standalone-only.

## Effort estimate

- Variant B, custom servers only + image-digest check: an evening. One new file, ~150 lines, one optional flag on the rebuild path.
- Variant B + stdio filesystem introspection: add half a day of MCP-client fiddling.
- Variant A on top: a further day-plus, mostly the annotation-merge design, and it forces the cross-repo-write and prose-ownership questions.

## Resolved questions

All five open questions from the original draft were settled when the linter was built:

1. **Variant B first, or straight to A?** — B. A remains unbuilt and unscheduled.
2. **Hook into the rebuild path, or standalone?** — Hooked, via `--check-schemas` on the host path.
   The hook is what makes drift visible without anyone remembering to look.
3. **Filesystem MCP: digest-pin or stdio introspection?** — stdio introspection; the fiddliness
   didn't materialise.
4. **Who fixes the doc when it fires?** — Flag to the user; a paired-file pass is the standing
   remedy, since the two doc surfaces have to move together anyway.
5. **Lint the quickref too, or only the reference?** — Both. The quickref loads into context every
   session, so it has the larger blast radius, not the smaller.

---
name: Working Documents
type: reference
keywords: [handoff, proposal, plan, working, temporary, gitignore, convention]
description: Holding directory for handoffs, proposals, and planning documents — excluded wholesale from the public engine repository.
---

# Working_Documents

**Handoffs, proposals, and planning documents go here. Nothing in this directory ships in the
public engine repository.**

## Why the directory exists

These documents are, by nature, about work in progress. They name unfinished decisions, record
things that turned out to be wrong, quote paths that are about to change, and carry whatever
project-specific detail the work happened to involve. None of that belongs in a published repo,
and most of it is stale within weeks.

The directory replaces an earlier approach of gitignoring each working document by name. That
version **failed open**: a new handoff written at the corpus root shipped by default unless
someone remembered to add a line for it. A single directory rule fails closed instead — the
default for anything created here is "not published," and getting it wrong requires actively
moving a file out.

## What belongs here

- Handoff documents between sessions, agents, or clients
- Proposals and design notes for work not yet done
- Multi-phase plans and their progress markers
- Anything explicitly temporary

## What does not

- **Reference documentation.** If it describes how something *currently works* and will still be
  true next month, it belongs in `System_Documentation/` (infrastructure) or `Core_Rules/`
  (rules and GM behaviour).
- **Corpus content.** Settings, characters, scenarios and prose live under `World_Building/`.

The test: would this document still be worth reading once the work it describes is finished? If
yes, it is reference material and belongs elsewhere. If it exists to get work *to* completion,
it belongs here.

## Lifecycle

Delete a working document, or move it to `Trash/`, once its work is closed. Each one should say
so in its own header. A finished handoff left in place is a trap — the next reader cannot tell
whether it describes pending work or a completed job, and acts on it either way.

Anything durable a document produced should be extracted into real documentation *before* the
working copy is retired. The document is scaffolding, not the building.

## Tracking

The engine repository ships this directory and this README, and nothing else in it:

```
/Working_Documents/*
!/Working_Documents/README.md
```

Two details in that rule are load-bearing. The pattern is `*`, not `*.*` — the latter matches
only names containing a dot, so a subdirectory like `Working_Documents/archive/` would not match,
git would descend into it, and its contents would ship. And the case must match exactly: a
lowercase `!working_documents/readme.md` appears to work on Windows, where `core.ignorecase` is
usually true, then inverts on a case-sensitive filesystem — the README gets ignored while
everything else ships.

The consequence is that working documents are **tracked by neither post-split repository** — the
engine repo ignores them, and the content repo is rooted at `World_Building/`. That is
deliberate. If a working document is valuable enough to want history for, that is a signal to
promote its durable content into `System_Documentation/`, not a reason to version the
scaffolding.

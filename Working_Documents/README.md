---
name: Working Documents
type: reference
keywords: [handoff, proposal, plan, working, temporary, gitignore, convention]
description: Holding directory for handoffs, proposals, and planning documents — excluded wholesale from the public engine repository.
---

# Working_Documents

**Handoffs, proposals, and planning documents go here. None of them ship in the public engine
repository.**

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

The engine repository ships this directory and three files in it — this README, plus the
`.gitignore` and `.gitattributes` that the local repository below needs — and nothing else:

```
/Working_Documents/*
!/Working_Documents/README.md
!/Working_Documents/.gitignore
!/Working_Documents/.gitattributes
```

Three details in that rule are load-bearing. The pattern is `*`, not `*.*` — the latter matches
only names containing a dot, so a subdirectory like `Working_Documents/archive/` would not match,
git would descend into it, and its contents would ship. Gitignore's `*` *does* match a leading
dot, unlike shell globbing, so the two dotfiles need explicit negations or they disappear along
with everything else. And the case must match exactly: a lowercase
`!working_documents/readme.md` appears to work on Windows, where `core.ignorecase` is usually
true, then inverts on a case-sensitive filesystem — the README gets ignored while everything else
ships.

## Local history

Because the engine repository ignores these documents, they have no history there. That is right
for publication and wrong for the documents themselves: a handoff can be rewritten or deleted
with no record of what it previously said, which is a poor property for the files that carry
unfinished decisions between working sessions.

**This directory is therefore meant to be its own local git repository.** From inside it:

```
git init -b main
```

That is the whole step. On a fresh clone there is nothing to commit yet — the three files
present are the parent's and are ignored here — so the first commit arrives with the first
document you write.

The two dotfiles that shipped with the clone do the rest. `.gitignore` excludes the three
parent-owned files, so they stay under one history rather than two; `.gitattributes` restores
the line-ending normalization, which does not otherwise apply, since a nested repository is its
own attribute scope.

That is the whole division of ownership: **the engine repository owns the scaffolding that
defines the convention; the local repository owns the documents it holds.** Adding a file here
means deciding which of the two it is.

**Give it no remote.** The reasoning that keeps these documents out of the public repository is
unchanged — they name unfinished decisions, quote paths that are about to move, and record
conclusions that later turned out to be wrong. What was missing was never publication, only the
ability to see what changed. A private mirror for backup is a different question from publishing,
and the answer to it may reasonably be yes; a local repository gives you history but not a
backup, since it sits on the same disk as the thing it is protecting.

Be accurate about what the nesting does. The parent's traversal stops at the repository
boundary, so `git add .`, `git add -A`, and a `Working_Documents/` directory pathspec cannot
pull anything in. An explicit `git add -f <path>` still reaches through. It is a second
independent barrier, not an absolute one, and the ignore rule above remains the thing doing the
real work.

The step is optional. Skip it and the directory behaves exactly as it did before — untracked
by anything, which was the arrangement until this convention existed.

None of this displaces the lifecycle rule above. Local history makes a working document
recoverable; it does not make it durable. If something here is valuable enough to keep, promote
it into `System_Documentation/` — versioning the scaffolding is not a substitute for extracting
the building.

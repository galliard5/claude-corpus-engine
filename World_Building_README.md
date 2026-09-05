---
name: World Building README
type: reference
keywords: [world_building, scaffold, project profile, setup, corpus, content]
description: What goes in World_Building/ and how to write the Project_Profile.md the engine reads at session start.
---

# World_Building — what goes in it

**`World_Building/` is where your corpus content lives. This engine repository ships none of it.**

The engine ships without a setting on purpose. `Core_Rules/`, `Python/`, and the root instruction
files describe *how* a corpus is navigated; what is actually in the corpus is yours. Keeping the
two apart is what lets the engine be published while the content stays private.

> **Why this file is at the repository root rather than at `World_Building/README.md`.**
> That was the original plan, and it does not work. Git cannot track a file inside a nested
> repository, and `World_Building/` is expected to *be* one — its own private repo with its own
> remote, which is the arrangement this document recommends below. Once it contains a `.git`, the
> outer repository treats the whole directory as an opaque embedded repo and will not descend into
> it; `git add -f World_Building/README.md` silently stages nothing.
>
> There is a second reason the original plan could not work: **git cannot track empty
> directories at all.** Shipping an "empty scaffold" was only ever possible *because* of a file
> inside it. With that file blocked, a fresh clone has no `World_Building/` directory either way —
> so the guidance had to move somewhere the engine repository can actually carry it.
>
> **Practical consequence:** after cloning this repository, `World_Building/` does not exist.
> Create it yourself, following this document.

## What goes in it

Whatever shape your material wants — settings, campaigns, characters, locations, factions,
timelines, session records. The engine imposes almost nothing on the layout. It cares about three
things:

- **Files carry YAML frontmatter** (`name`, `keywords`, `description`, and a `type` where the local
  family uses one). The indexer reads these; a file without them still gets indexed on body text,
  but searches badly.
- **Placement is predictable.** The model guesses paths before it searches, so a scheme it can
  infer beats one it has to look up.
- **Directory names are stable.** They appear in the generated index and in your profile.

## `Project_Profile.md` — the one file you must write

The root instruction file (`file_system_instructions.md`) is deliberately setting-agnostic, so it
stops short wherever a rule would need to know your content. `Project_Profile.md` is where those
answers live. Create it at `World_Building/Project_Profile.md`.

At session start the model reads both files together, in one call — engine rules from the root,
project specifics from there. Neither is complete alone.

Sections worth having, and what each is for:

| Section | Purpose |
|---|---|
| `NAMING EXAMPLES` | Your filename conventions, shown as worked examples rather than described |
| `PROJECT DIRECTORIES` | What each directory under `World_Building/` holds, and anything outside it the model should know about |
| `SEMANTIC FILE PLACEMENT` | The decision procedure for where a *new* file goes. The highest-value section — it's what stops files landing somewhere plausible but wrong |
| `SERIES SEARCH BINDING` | Which database `series-search` is pointed at and what it's for. Omit if you don't use that server |
| `COMMIT MESSAGE EXAMPLES` | Your commit categories and format |
| `WORLD REGISTER` | Durable cross-setting state you want loaded every session. Keep it small |

Two conventions carried over from the engine docs, worth matching:

- Give it frontmatter like any other corpus file, so it's findable by search.
- Put a `Last edited (UTC)` line in the **body**, not the frontmatter — it then survives being
  copy-pasted into a project-instructions field, which frontmatter does not.

Keep changing state out of it. Current scene, active tasks, and session status belong in scenario,
checkpoint, and timeline files that get loaded on demand. The profile should be durable enough that
it rarely changes.

## Version control

`World_Building/` is ignored wholesale by this repository. That is deliberate: the engine ships the
rules and the tooling, never the contents.

If you want your content under version control — and you should — **make `World_Building/` its own
repository with its own private remote.** It nests inside the engine checkout without the outer
repository tracking it, which is exactly the arrangement described in the note above. Two
repositories, one working tree, and the public half never sees the private half.

Worth putting in that repository's own `.gitignore`:

- **Raw session transcripts.** Verbatim play logs are bulky and low-value once summarised; the
  checkpoints and extracted lore derived from them are the durable artifacts and should be tracked.
- **`.gitattributes` with `* text=auto eol=lf`,** if your engine checkout has one. Line-ending
  rules do not cross a repository boundary, so a nested repo without its own copy will happily
  convert every file on first checkout.

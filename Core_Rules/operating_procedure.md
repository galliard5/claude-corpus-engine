---
name: Operating Procedure
type: rules-reference
keywords: [operating, procedure, session, checkpoint, handoff, git, capability, tools, harness]
description: The harness — session lifecycle, checkpoints, file architecture, tool availability and git integration. Deployment configuration rather than rules; depends on which tools are actually connected.
---

OPERATING PROCEDURE
===================

**This module is not rules.** It is deployment configuration wearing rules' clothes — how a session
starts and ends, what gets written where, which capabilities are available and what to do when they
are not. Everything here depends on the installation rather than on the game, the setting, or the
player's taste.

That dependency is the reason it is separate. Doctrine and epistemics hold on any host. Nothing
below does: change the client, the connected servers, or the storage layout, and this module
changes with them while the other three do not.

---

## Capability classes, not model names

**Describe roles by capability, never by brand.** The architecture is real; the names are an
installation detail that does not survive a change of host or vendor.

| Class | Used for |
|---|---|
| **Preparation** — highest-capability available | Building scenarios, designing layered NPCs, cross-referencing canon across many files, first contact with a major NPC, anything where getting it wrong cascades |
| **Session** — the runtime model | Running play within established parameters, checkpoint generation, routine file maintenance |
| **Mechanical** — lowest-cost adequate | Templated work via explicit handoff: summary formatting from beat lists, batch peripheral records, format conversions. Not primary GM duties — it lacks the context depth for canon adherence in live play |

**Escalate from Session to Preparation** when several NPC agendas collide in one scene, when formal
or political proceedings need deep behavioural logic, in a high-stakes social confrontation where
a relationship can permanently shift, on first contact with a major NPC, when a scene requires
inference across several canon files with no single clear answer, or when the scenario branches past
what its package anticipated. When in doubt, start with Session; flattening NPCs, canon
contradictions, or a package that no longer covers the live branch are the signal to escalate.

**Do not claim to switch models inside a task.** Selection is the operator's, made between
sessions. A model cannot re-instantiate itself, and saying otherwise is an assertion about the host
that the host has not made. Where a host genuinely supports delegation, it happens because the
player asked for it or configured it.

---

## Tool availability

**Name the capability; check the live surface.** Any named tool below is an example of a capability,
not a guarantee that it exists in this session. Tool names, signatures and availability are the
host's to define, and hard-coding one produces instructions that fail silently when it is absent.

**When a capability is missing, disclose and fall back — never simulate.**

The pattern, which generalises:

> Say plainly, once, that the capability is unavailable this session. Then pick a documented
> fallback and name it as a fallback. Do not emit output shaped like the tool's and present it as
> the tool's.

Concretely: with no random generator, resolve by judgement and describe outcomes as judgement, or
have the player roll physically. With no diagram renderer, describe the structure in prose. With no
search index, read source files directly and say that retrieval was manual.

*The rule against presenting invented output as real output is **epistemics**, and it is not
softened by the tool being absent — it is the reason the disclosure exists.*

**Arithmetic beyond a line or two goes to a computation tool** rather than being reasoned through:
multi-target totals, stat formulas, compounding modifiers.

### Not included: background music

A music capability exists in this workspace and is **deliberately excluded from this module**. It
is alpha, it lives outside this repository, and a reader here could not run it. Documenting it from
this side would be documenting an absent tool.

Recorded rather than omitted silently, because an absent section reads as an oversight — the same
reason a system module declares `none` rather than saying nothing.

---

## Session lifecycle

**Start.** Briefly orient the player — where they are, what is around them, what threads are
unresolved. Do not over-recap.

**Resuming after a break.** Give a brief recap of the previous session before setting the scene:
three to five sentences covering major events, current conflicts, recent NPCs and unresolved
threads. Then transition into the first scene.

**Direct continuation.** Where the previous session ended and play continued immediately, no recap
is needed — reference the previous session by number and go straight to the next scene. The
distinction is about the player's memory, not the fiction's: a recap after a break helps them back
in, and the same recap after no break is redundant.

In both cases, track the new session number as the active context. Keep the campaign-wide count in
campaign metadata — the character sheet, timeline, or scenario file — so the active session remains
recoverable independently of conversation history. The checkpoint template owns the incrementing
and filename format.

**End.** Find a natural stopping point. End on a forward-pulling moment — an unanswered question, a
new arrival, a distant sound. Never end flat.

> **Open dependency — what to load at startup.** The current instruction is to read the current
> session summary *and all previous summaries* for the scenario before beginning, while the
> handoff protocol says to load only the most recent unless the scenario package specifies
> otherwise. These conflict, and resolving them requires an audit against a real long campaign; it
> cannot be settled by editing wording. **Until it is, follow the checkpoint's own
> Required/Contextual list where one exists.**

---

## Checkpoints

A checkpoint is a save point: enough state that a later session can resume seamlessly.

**Recognising a stopping point.** The in-game day ends; a scenario milestone concludes; the player
asks; a scene reaches emotional completion; or enough time passes that a new chapter is beginning.

### Offer, display, then write — in that order

The previous rules contradicted themselves here, instructing the GM both to *offer* the player a
save and to generate one *without waiting for permission*. The resolution separates two things that
were being treated as one:

1. **Offering and displaying a checkpoint is free.** At a natural break, say so in a line, and
   display the summary. This is text in the conversation; it costs nothing and commits nothing.
2. **Writing it to disk is not.** Persisting files happens after the player agrees. So does
   anything downstream — file updates, index rebuilds, and git.

So: recognise the moment, offer it, show the summary, and write on agreement. Nothing is generated
behind the player's back and nothing is withheld from them either.

**Do not claim an elapsed pause** while doing it. *(The display format is presentation.)*

### What a checkpoint records

Always: campaign name, in-game date including time of day, current location, a two-to-three
sentence arc summary, three to five key events, the character's current state, and active
unresolved threads.

Where significant: major NPC interactions and how a relationship shifted; world changes; character
growth; mechanical changes such as items acquired or conditions applied.

Never: narrative prose, verbatim dialogue, full dialogue samples, or internal character thoughts.
A checkpoint is a summary, not a scene.

**The checkpoint is also the extraction pass.** A summary is lossy by design — it keeps the arc and
discards the small stuff, and the small stuff is exactly what breaks continuity twenty sessions
later: a promise made in passing, a debt incurred, a door left unlocked, a secret told to one
person. Ask directly: *what did anyone promise, owe, hide, break, or hand over this session?* **Where
the campaign has a World State Register**, write each answer there as a one-line entry tagged with
who knows it before finishing the checkpoint. **This is not summary work — it is the opposite.**
The summary compresses; the register preserves what compression destroys.

### Active cast

**An NPC stays on the checkpoint's active cast only while a durable causal link keeps them there.**
A name on that list claims this person is live *now* — not that they exist, were vivid last
session, or were enjoyable to write.

Promote when at least one holds: they are named in a standing register entry that has not resolved;
they have a scheduled appearance or pending appointment; an obligation is open in either direction;
or a consequence of player action is still travelling toward them.

**Do not promote** because the NPC appeared, was retrieved, was pleasant, or seems like they should
matter. None of those is a durable causal link.

**Demote when the last link closes**, and record the demotion so the roster shrinks visibly rather
than silently. Demotion removes someone from the live roster, not from the world — their file stays
where it is and remains true. *This is Retrieval Is Not Salience applied to the save rather than to
a search.*

**Do not demote a location-tied NPC unless a location brief exists to catch them.** Where no brief
records their schedule and pattern, the checkpoint is the only record, and dropping them destroys
it. Keep them listed and note the missing brief instead.

### In-world documents

When the fiction produces a document whose exact wording is authoritative — where paraphrase would
change its meaning — preserve it verbatim as its own Markdown file in the campaign's
`Scenarios/[Campaign_Name]/Documents/` directory, creating that directory if it does not exist.
Use a descriptive filename reflecting the document type and subject, and reference it from the
checkpoint in one line:

```markdown
- Writ of Formal Charges against the steward → [[Campaign_Name/Documents/Writ_Steward_Charges.md]]
```

**The test:** if a player or NPC could later argue over what the text *actually said*, it gets its
own file. If the gist suffices, summarise.

Qualifying: legal documents, prophecies, letters where phrasing or commitments matter, oaths and
binding agreements, official records where figures matter.

**Spoken words are summarised as normal unless a character in the fiction explicitly creates a
written transcript.** That transcript is an in-world document and follows the preservation rules
above; it is not a mechanical capture of the session. Write it as the in-world transcriptionist
would have produced it, reflecting their skill, attention and biases — a trained clerk produces a
disciplined record; an untrained person produces something rougher, with missed statements and
paraphrase that shifts meaning. Every transcript carries an attribution line naming who produced
it, their role and the date, because NPCs weigh a document's authority by its author.

**Transcriptionists can be compromised.** Evaluate one contemplating falsification as any NPC
contemplating a crime: motive, penalty, chance of detection. Outright fabrication is high-risk;
selective omission and unflattering paraphrase are harder to prove and more likely. **Where a
transcript is materially inaccurate, append a GM-only block listing each deviation** so a later
challenge can be adjudicated without relying on memory.

---

## File architecture

**Character, location, house and faction files use a sheet + bio structure in a single file.** The
sheet is token-light and data-dense — the runtime view, loaded at prep. The bio is narrative
reference — background, extended relationships, history — loaded only when worldbuilding context is
needed.

```yaml
---
name: [Name]
sheet_end_line: 95
---

<sheet>
[the runtime view]
</sheet>

[bio content]
```

- The `<sheet>` and `</sheet>` markers are the canonical boundary. Lowercase.
- `sheet_end_line` gives the line number where `</sheet>` appears, counting the opening `---` as
  line 1.
- **The marker is the source of truth; the field is an optimisation.** If they disagree, the marker
  wins and the field is corrected.
- Whenever the sheet section is edited, recount and update the field. Edits inside the bio need no
  update.

**This is an operating-procedure contract, not a presentation one.** Changing `sheet_end_line`
alters neither the world nor the screen — it changes how a file is loaded.

> **Host dependency.** The field exists to support a *ranged read* — fetching only the first N lines
> of a file. That is a filesystem-tool affordance, not a universal one. On a host without it the
> field is inert and the whole file loads regardless, which is correct behaviour rather than
> breakage. Keep the markers, which are portable text; treat the field as an optimisation that may
> not apply.

---

## Version control

Where the campaign is under version control, the commit is the durable save point — the checkpoint
is immediate, the commit marks it permanent.

**After a checkpoint is written and reviewed:**

1. Propose a commit message based on the session's events.
2. **Ask.** Show the message and wait.
3. On approval, stage **the session's files by explicit path** — never a blanket add, which sweeps
   in unrelated work from the same repository.
4. Commit, and report the result.

**Nothing is staged, committed or pushed because a checkpoint occurred.** The previous rules
described this as automatic in one place and approval-gated in another; approval-gated is correct.
A checkpoint is a game event, and a commit is an action on the player's repository.

Session and extraction commit messages follow the active workspace's commit convention. This
module requires the semantic content — session commits identify the campaign, session number,
concise summary and in-game date; extraction commits identify the campaign/session and that
session-specific detail was consolidated into permanent world fixtures — but it does not own their
literal prefix or field order. Where no workspace convention exists, propose a clear message that
carries those same fields.

---

## Referenced procedures and templates

This module describes what happens and when. The detail lives in files it does not duplicate —
dropping these pointers would leave working templates unreachable from the rules, which is exactly
what the first extraction pass did.

| | |
|---|---|
| Full checkpoint structure and field guide | `Templates/Checkpoint_Template.md` |
| The post-session update procedure, in order | `Templates/Post_Session_Checklist.md` |
| Summary output format | `Templates/Session_Summary_Quick_Capture.md` |
| How the summary system fits together | `Templates/Session_Summary_System_Guide.md` |
| Transcript capture stub | `Templates/Session_Transcript_Stub.md` |
| Session log formats | `Templates/Session_Log_Template.txt`, `Templates/Session_Log_Condensed.txt` |
| Preparing a scenario and handing it to a session | `scenario_prep.md` |
| Post-session data consolidation into world files | `Scenario_Extraction_Rules.md` |

**The checkpoint is immediate; file updates follow it in order.** After a checkpoint is written,
follow the Post-Session Checklist rather than improvising the sequence. Its ordering is deliberate,
not arbitrary.

---

## What lives elsewhere

| | Where |
|---|---|
| How a checkpoint is displayed; the status block; option format | presentation |
| Never present invented output as real output | epistemics |
| Retrieval is not salience — which the active-cast rule applies | epistemics |
| Session start and end *as narrative* — orienting, ending on a pull | doctrine |
| What conditions are; what recovery requires | the active system |

---

## What this module consumes

```yaml
consumes:
  pc_sheet:   [file architecture, checkpoint state]
  conditions: [checkpoint state — what is recorded as active]
```

Thinner than the other modules, and appropriately so: this module describes the harness around the
game rather than the game, and a harness that reached deeply into the rules would be coupled to
something it has no business knowing about.

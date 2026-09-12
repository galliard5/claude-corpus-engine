---
name: Presentation
type: rules-reference
keywords: [presentation, display, choices, options, status block, scene tag, checkpoint, rendering]
description: What the player sees and how it is rendered — choice options, the status block, resolution display, checkpoint format. The only player-facing layer, and the one that assumes a chat window.
---

PRESENTATION
============

**This is the only layer the player sees directly.** Everything else is GM-internal: doctrine
governs what the GM does, epistemics governs what may be known, a system module governs what
resolves how. This module governs what appears on the screen.

**The test that assigns a rule here:** *would changing it make the world different, or only the
screen different?* "No option is the right answer" changes the world — a menu of equally weighted
choices produces different play. "Three to five options, one sentence each, scannable" changes only
the screen. The first is doctrine, the second is here, and they currently sit in the same section.

**This is also the host-coupled layer, and the only one that is.** Every contract below assumes
markdown rendering in a conversational client. A terminal, a voice interface, or a client that
renders markdown differently would need different contracts for the same information. Nothing else
in the engine has that dependency, which is a reason to keep this module separate quite apart from
taste.

**Expect this to be the most homebrewed module.** It is where a player's preferences are most
legitimate and least consequential — option count, whether the status block appears at all, how
much the scene tag says. A homebrew sidecar here carries no risk to world consistency, unlike one
at epistemics.

---

## Choice options

**Default (`choice_options: 3-5`).** At natural breaks in the narrative, present three to five
numbered options reflecting genuinely different approaches.

**Format.** Each option on its own line, numbered, with a brief action description. Scannable — one
sentence each, no paragraph blocks.

```
1. Tell the captain about the fault directly.
2. Demonstrate it — let the machinery speak for itself.
3. Deflect the question. Report the capability, not the mechanism behind it.
4. Ask what the report already told them before volunteering more.
```

**Campaign selection (`choice_options`).** The campaign profile may name a range, a fixed positive
integer, or `none`. A range or integer changes only how many options are rendered; every option
still follows the format and doctrine contracts here. `none` suppresses the numbered menu, not the
decision point: end at the natural break with room for a freeform response and do not imply that
the GM has continued past the player's choice.

**Freeform always works.** The numbered choices are a starting point, not a cage. A player stating
their own action is answered as readily as one picking from the list, and nothing in the rendering
should imply otherwise.

*What the options are* — that no option is the right answer, that they reflect character range
rather than only heroic action, that slice-of-life choices matter as much as plot ones, and when to
hand control back at all — is **doctrine**, not presentation.

---

## The status block

**Campaign selection (`status_block`).** The shipped default is `on`:

- `on` — render time and any player-known active conditions under the rules below.
- `time_only` — render time under the same relevance and precision rules, but suppress the
  conditions line.
- `off` — suppress both time and conditions.

The scene tag is independent. Where `scene_tag: on`, a transition still renders its witness record
even when `status_block: off`.

When rendered, the block sits immediately before the choice point and any choice options — not
after, not inline with the prose. Keep it minimal and scannable.

### Time

Tracked and displayed above the status line whenever it is relevant to the scene. **Use only the
precision the scene supports** — no more, no less:

- A room with a clock or sundial: `12:30`
- A town with a clock tower: `12th bell`
- In the field, travelling, or no timepiece present: `noon` / `mid-afternoon` /
  `an hour before dusk`

Update as the scene progresses. If significant time has passed between scenes, reflect it. Omit
when the time is genuinely unknowable or irrelevant.

### Conditions

**If a condition is significant enough to surface in the narration, it is significant enough to
list.**

```
[ Time: mid-afternoon ]
[ Status: Injured (moderate) · Tired · Hungry ]
```

If there are no active conditions, display the time line alone. If both are irrelevant to the
current scene, omit both.

Update the block each time choices are presented — if a condition clears or a new one appears
mid-scene, the next block reflects it. Do not list resolved conditions.

**Only list conditions the character is currently aware of.** Which ones those are is an
**epistemic** question, not a presentation one: a slow poison is not felt until it takes hold, and
a hidden condition stays off the block. This module renders the list; epistemics decides its
contents.

### Scene tag

**Default (`scene_tag: on`).** When the next beat begins a new scene — a location change, a
significant time skip, or a different set of people present — add a line naming where it starts and
who is there:

```
[ Time: first light ]
[ Status: Tired ]
[ Scene: the mill yard — the warden, the steward ]
```

**The tag looks forward, not back.** It sits immediately before the choice options, so it names the
scene the player is about to enter, never the one just narrated.

**Only at a transition.** Time and conditions refresh in every block; this line appears solely when
the scene actually changes. Tagged on every turn it marks nothing and becomes noise.

> **The names after the dash are not decoration.** They are a witness record, read back later as
> evidence of who knew what, and the requirement to keep them is **epistemic** — see
> `epistemics.md`, *The witness record*. If the scene tag is homebrewed away, the Information
> Firewall loses its only structured input. Change the visible format freely; removing the record
> creates the epistemic cost stated below.

**`scene_tag: off` is valid, but its cost is not silent.** Report prominently at load that the
Information Firewall loses its only structured witness input, witness tracing falls back to
unstructured prose and whatever durable records actually exist, and later sessions may not be able
to recover who was present. An active homebrew sidecar may define a replacement witness record and
its retrieval path. If it claims one that does not exist or cannot be retrieved, the configuration
is invalid; turning the visible tag off deliberately is not.

---

## Showing resolution results

Where a system resolves by a generator, **show the result**: the notation, the outcome, and what it
was measured against.

```
2d20kh1+5 → 12 vs DC 14
```

Any outcome should be auditable after the fact.

**Hidden results conceal the number, never the mechanism.** An NPC's unseen check or a secret
perception roll hides its result from the player; that a check happened is not hidden.

> **Turning this display off never licenses fabricating the number.** The rule against asserting a
> result you did not obtain is **epistemic** and is not affected by anything in this module. A
> campaign that homebrews numbers out of the prose still generates them honestly — see
> `epistemics.md`, *Never assert what you did not obtain*.

---

## Checkpoint display

When a checkpoint is reached:

1. Pause the narrative — there is no need to finish a sentence.
2. Display the checkpoint summary.
3. Ask, out of character, whether to continue or take a break.
4. Continue only when the player signals.

This gives the player a clear moment to stop and resume later, continue immediately, or ask
questions about what happened.

**Do not claim an elapsed pause.** Earlier versions of this instruction told the GM to "wait 2–3
seconds" as a save moment. A model cannot wait and should not say it did. The pause is the
player's, created by handing them a decision — not something the GM performs.

*When a checkpoint is offered, what it contains, and whether it is written to disk are
**operating procedure**, not presentation.*

---

## What lives elsewhere

| | Where | Why |
|---|---|---|
| No option is the right answer; choice spacing; momentum stall | doctrine | Changes the world, not the screen |
| Which conditions the character is aware of | epistemics | The firewall applied to their own body |
| The witness record inside the scene tag | epistemics | Evidence, not decoration |
| Never assert a result you did not obtain | epistemics | Unaffected by whether it is displayed |
| What a condition *is* and when it applies | the active system | Baseline or a loaded module |
| When to checkpoint and what it contains | operating procedure | Depends on the tools connected |
| `<sheet>` markers and `sheet_end_line` | **operating procedure** | See below — reassigned |

### One reassignment from the original module table

The original module table filed the **sheet + bio architecture** under Presentation. Applying this
module's own test moves it out: changing `sheet_end_line` alters neither the world nor the screen.
It is a file-layout and loading contract — the marker, the line-count field, the head-only read for
token efficiency, and the maintenance discipline when the sheet section grows.

It also carries a host dependency of a different kind from this module's. Presentation assumes
markdown rendering; sheet+bio assumes a *ranged read* (`head=N`), which is a filesystem-tool
affordance. On a host without one, the field is dead weight and the whole file loads anyway.

Both belong to operating procedure. The roadmap table is amended to match; recorded here as well
because a reassignment that leaves no trace is indistinguishable from an omission.

---

## What this module consumes

`conditions` — to know what may be displayed, though **not** whether it may be: that is epistemics.
Nothing else. A system module that declares `conditions: none` leaves the status block with only a
time line, which is a correct outcome rather than a broken one.

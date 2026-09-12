---
name: Adaptation — Baseline to DnD5e
type: rules-reference
keywords: [adaptation, profile, baseline, dnd5e, d20, compile, chain]
description: Resolved adaptation for the Baseline → DnD5e chain. Records what survives, what conflicts and how each conflict was ruled, so the compile does not re-decide it and a later session does not re-litigate it.
---

ADAPTATION — `Baseline → DnD5e`
===============================

> **All rulings settled 2026-09-11**, both conflicts approved as recommended.

```yaml
chain: [Baseline, DnD5e]
edition: 2014
built_against:
  Game_Systems/Baseline/baseline.md: sha256 311257a8e602bd3e…
  Game_Systems/DnD5e/dnd5e.md:       sha256 930157ebbda55182…
homebrew: none
```

**Why this file is required rather than optional.** Two sites — `npc_statblock` and `conditions` —
resolve to *keep both layers*, and no manifest can say that. A chain compiled without this profile
does not approximate the right answer; it silently discards the behavioural half of every NPC and
the whole of Baseline's sustenance model. See
`Game_Systems/Reference/Interface_Test_Notes.md` §5.

---

## Summary

| Site | Resolution |
|---|---|
| `resolution` | DnD5e, with one Baseline principle retained |
| `difficulty` | DnD5e, clean |
| `success_grades` | neither — both `absent`, doctrine governs |
| `contest` | DnD5e, with one Baseline rule retained |
| `harm` | DnD5e, with one Baseline rule retained |
| `conditions` | **partition** — see below |
| `recovery` | ruled — see below |
| `incapacitation` | DnD5e, with one Baseline principle retained |
| `resource` | DnD5e, clean add over Baseline's `none` |
| `progression` | DnD5e, clean |
| `equipment` | **Baseline**, whole — DnD5e declares `absent` |
| `pc_sheet` | DnD5e, with three Baseline fields merged |
| `npc_statblock` | **extend** — both layers live |

**Nine of thirteen sites carry something from Baseline.** The four that carry nothing are
`difficulty`, `success_grades`, `resource` and `progression`.

**The naive later-wins resolution would have been wrong at eight of them** — every site carrying
Baseline content except `equipment`, where DnD5e declares `absent` and falling through is what
later-wins does anyway.

---

## Additive — Baseline survives where DnD5e is silent

Asked first, per the pass: *what does the lower layer cover that the upper does not mention at
all?*

**`equipment` — Baseline entire.** DnD5e models gear durability nowhere and declares `absent`.
Baseline's damage-type risk table, the check-when/skip-when guidance, the scarcity note and the
organic-threat edge case all stay exactly as written. No merge needed; this site simply falls
through.

**`conditions` — Baseline's sustenance layer, entire.** DnD5e's conditions are combat and magical
statuses; it models no hunger, no thirst, and no accumulation from ordinary activity. The two sets
are nearly disjoint. Retained from Baseline: HUNGRY, THIRSTY, **SICK**, INTOXICATED, RESTED,
INVIGORATED, the accumulation rules, the compounding rule, and the urgency tiers — the last two
applying to *both* layers' conditions, not only Baseline's. Retired: INJURED alone, superseded by
hit points. TIRED and EXHAUSTED are the conflict below.

> **`SICK` was wrongly retired in the first pass, and the correction is worth recording.** It was
> dropped alongside INJURED on the reasoning that hit points and DnD5e's poisoned and diseased
> handling covered it. They do not. SRD 5.1 has **no generic disease condition** — `poisoned` is a
> specific mechanical state, not a model of illness — and the SRD says outright that disease
> specifics are left outside the ruleset rather than governed by it. So retiring SICK would have
> deleted the only illness model in the chain and replaced it with nothing, in a system whose own
> documentation declines to supply one.
>
> This is the partition failure the adaptation pass exists to catch, caught by the pass itself: a
> site where the upper layer *looks* like it covers the lower and does not. It is also a caution
> about the other direction — the first pass over-retired here while under-retaining elsewhere, so
> "DnD5e has something similar" is not sufficient grounds either way. Check what the upper layer
> actually defines.

**`harm` — permanent results.** Baseline decides lasting injury at the moment it happens: a lost
limb, a taken eye, logged immediately and reflected in appearance thereafter. DnD5e has no
lasting-injury rules at all, so this survives an otherwise complete override.

**`incapacitation` — defeat is not the end of play.** DnD5e's death saves say what happens at 0
hit points; they say nothing about what defeat *means*. Baseline's "capture, retreat, injury or
loss — a harder situation, not a terminal state" has no DnD5e equivalent and is retained.

**`contest` — decisive capabilities.** Baseline's rule that a single capability can override the
general balance, recalculating the contest from there, has no DnD5e counterpart. Retained as
guidance on when an opposed check is the wrong tool.

**`resolution` — roll sparingly.** Baseline's "roll only where failure carries a consequence and
success is not already implied" is not in the SRD. Retained as a usage principle over DnD5e's
mechanic.

**`pc_sheet` — three fields.** DnD5e's sheet has no home for active long-duration conditions, for
permanent alterations, or for the current in-game date. All three are merged in from Baseline's
block; the date field in particular is load-bearing for tracking time-sensitive conditions across
sessions.

**`npc_statblock` — extend, not override.** DnD5e supplies AC, hit points, speed, ability scores,
saves, resistances, senses and actions. Baseline supplies bravery, loyalty, breaking point, stress
tell, instinct, and the memory/interaction log. **Both are live.** A campaign wants numbers *and* a
reason the creature stops fighting, and nothing in either manifest could have said so.

---

## Conflicting — ruled

Asked second: *where do the two model the same thing differently?*

### `conditions.fatigue` — ruled 2026-09-11

DnD5e exhaustion and Baseline's TIRED / EXHAUSTED describe the same state with different
consequences and different triggers. One has to govern.

**Ruling: DnD5e supplies the effects, Baseline supplies the triggers — through a threshold, not a
direct mapping.**

The obvious version of this is wrong and worth stating so it is not re-attempted. Mapping
Baseline's triggers straight onto exhaustion levels makes ordinary life punishing: a long day in
the saddle would become exhaustion 1, which is disadvantage on every ability check. Baseline's
TIRED is a mild condition and DnD5e's exhaustion 1 is not.

So Baseline's accumulation tracks narratively and unmechanically — the character is visibly tiring,
it shows in the prose, it shapes NPC reaction — and converts to **exhaustion 1 only at the point
where Baseline would have escalated to EXHAUSTED**: compounded fatigue, a second night without
proper sleep, exertion past the point of recovery. Above that, DnD5e's track governs entirely.

Effect: Baseline's texture at the low end, DnD5e's teeth at the high end, and no double-modelling
anywhere.

*Retires:* TIRED and EXHAUSTED as tracked Baseline conditions. *Retains:* every accumulation
trigger that fed them.

### `recovery` — ruled 2026-09-11

A long rest restores all hit points overnight. Baseline says wounds need treatment, rest and time
together and never resolve by time alone. These contradict tonally as much as mechanically:
DnD5e's curve is deliberately fast so adventuring continues, Baseline's deliberately slow so injury
has weight.

**Ruling: DnD5e's rests govern mechanically, gated on Baseline's fiction; lasting injuries follow
Baseline regardless.**

Three parts:

1. **A long rest only counts if the fiction contains what Baseline requires** — shelter, food and
   water, uninterrupted sleep. Broken rest is not rest. Where those are absent the rest does not
   happen, and hit points do not return.
2. **Hit point recovery is DnD5e's**, at DnD5e's rate, once the gate is passed.
3. **Lasting injuries — the ones `harm` retained from Baseline — are outside the hit point
   system entirely** and follow treatment-rest-time. A long rest does not regrow a hand.

This was option 3 of three argued in
`Game_Systems/Adaptations/Adaptation_Study_DnD5e.md`, and it is the least invasive: it changes no
DnD5e number, and it preserves the weight Baseline was contributing by attaching it to the injuries
that should carry it rather than to hit points, which should not.

---

## Cleanly superseded

Asked last, and the least interesting: *where does the upper layer supersede entirely?*

**`difficulty`** — DnD5e's DC ladder replaces Baseline's case-by-case judgement. That is what a
ladder is for, and Baseline declares no scale to defend.

**`progression`** — DnD5e's levels and experience replace Baseline's skill trees, which go
inactive. Note that Baseline's trees are optional per campaign in any case, so this is rarely a
loss anyone notices.

**`resource`** — Baseline declares `none`; DnD5e adds spell slots, Hit Dice, Inspiration and
per-class resources. A clean `add` into a deliberate absence, which is exactly the case the three
states exist to distinguish.

**`success_grades`** — both layers `absent`. Doctrine's Yes-But / No-And governs, untouched by
either. Recorded so that a later reader does not mistake the double absence for an oversight.

---

## Settled

Both conflicts were matters of taste rather than correctness, and both were approved as recommended
on 2026-09-11 — the `fatigue` threshold where Baseline would have escalated to EXHAUSTED, and
`recovery` as option 3 of the three argued in the study.

Recorded rather than merely applied, because the alternatives were real: the threshold could sit at
a different point, and `recovery` could reasonably have taken either of the other two options. A
later session reading this should know it was a choice, not a derivation.

Nothing in this profile is open. The additive and superseded sections follow from the two manifests
and never required a ruling.

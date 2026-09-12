---
name: DnD5e
type: rules-reference
keywords: [rules, system, d20, dnd5e, srd, module, sample]
description: Sample d20 system module. Pins the tables and edition specifics a GM needs exact, declares the thirteen call sites, and leaves everything the model reliably knows unstated.
---

DnD 5E
======

> **Attribution.** The tables below are SRD 5.1 content, available under CC-BY-4.0. The
> repository-level `NOTICE` carries the attribution for this module and its supporting reference
> measurements. Do not vendor data from OGL-licensed community datasets — see
> `Game_Systems/Adaptations/Adaptation_Study_DnD5e.md`.
>
> **Edition boundary.** This interim module supports SRD 5.1 / the 2014 rules only. A campaign
> selecting `edition: 2024`, or any other value, is invalid and the compile/load must refuse rather
> than silently supplying the 2014 answers below.

**This module pins; it does not teach.** The core loop, action economy, condition definitions,
ability scores and class structure are all reliably recalled and are deliberately absent below.
What is here is the material that needs to be exact and is not: small tables, edition divergences,
and the declarations the compile reads.

Measured basis for that choice: `Game_Systems/Reference/Recall_Tests/Recall_Test_Results.md`.
Twelve items checked against source, nothing structural wrong, four errors all in secondary
elements.

---

MANIFEST
========

```yaml
edition: 2014
# Required. This interim module accepts 2014 only; any other value is invalid and
# the compile/load refuses rather than falling back to these 2014 answers.

resolution:
  state: defined
  lookup: inline
  answer: >
    d20 + ability modifier + proficiency bonus if proficient, against a DC or AC.
    Advantage is 2d20kh1, disadvantage 2d20kl1. A natural 20 on an attack roll is a
    critical hit: roll the damage dice twice, add modifiers once.

difficulty:
  state: defined
  lookup: inline
  answer: "Fixed DC ladder — see Pinned tables."

success_grades:
  state: absent
  answer: >
    Inherits doctrine's Yes-But / No-And. 5e's hit-or-miss is a resolution output, not
    an outcome-grading philosophy — see Game_Systems/Adaptations/Baseline_DnD5e.md.

contest:
  state: defined
  lookup: inline
  answer: >
    Opposed ability checks; higher total wins, ties leave the situation unchanged.
    Grapple and shove are Athletics against Athletics or Acrobatics.

harm:
  state: defined
  lookup: inline
  answer: >
    Hit points, reduced by damage of a named type. Resistance halves, vulnerability
    doubles, immunity negates. No lasting-injury rules; Baseline supplies them.

conditions:
  state: defined
  lookup: inline
  answer: >
    Fourteen named conditions plus an exhaustion track. These are combat and magical
    statuses; nothing here models sustenance or accumulated daily fatigue.

recovery:
  state: defined
  lookup: inline
  answer: >
    Short rest (1 hour, spend Hit Dice) and long rest (8 hours, all hit points and
    half total Hit Dice back, one per 24 hours).

incapacitation:
  state: defined
  lookup: inline
  answer: "Unconscious at 0 hit points, death saves, instant death — see Pinned tables."

resource:
  state: defined
  lookup: inline
  answer: >
    Spell slots by class and level, Hit Dice, Inspiration, and per-class resources
    recovering on short or long rest. Fills a site Baseline declares `none`.

progression:
  state: defined
  lookup: inline
  answer: >
    Experience thresholds or milestone advancement, twenty levels, proficiency bonus
    scaling by tier. Baseline's skill trees are off when this module is active.

equipment:
  state: absent
  answer: >
    5e models gear durability nowhere. Falls through to Baseline, which does. This is
    scope rather than a design position: a user wanting pure-5e feel sets `none` in
    homebrew_dnd5e.md.

pc_sheet:
  state: defined
  lookup: inline
  answer: >
    Ability scores, proficiency bonus, AC, hit points and Hit Dice, saving throw and
    skill proficiencies, spell slots, equipment, class resources.

npc_statblock:
  state: defined
  lookup: dataset
  source: data/          # declared, not yet built — this module is usable for
                         # everything except statblock lookup until it exists
  answer: >
    Standard statblock — AC, HP, speed, ability scores, saves, skills, resistances,
    senses, actions. Extends rather than replaces Baseline's behavioural block —
    see Game_Systems/Adaptations/Baseline_DnD5e.md.
```

---

PINNED TABLES
=============

The material that has to be exact and is small enough to carry inline.

*Verified against source 2026-09-11: the DC ladder against the SRD directly, the proficiency table
against several consistent sources. Death saves and both exhaustion tracks were verified during the
recall test.*

**Proficiency bonus**

| Level | Bonus |
|---|---|
| 1–4 | +2 |
| 5–8 | +3 |
| 9–12 | +4 |
| 13–16 | +5 |
| 17–20 | +6 |

**Difficulty classes**

| Task | DC |
|---|---|
| Very easy | 5 |
| Easy | 10 |
| Medium | 15 |
| Hard | 20 |
| Very hard | 25 |
| Nearly impossible | 30 |

**Death saving throws**

At 0 hit points, roll a d20 at the start of each turn. 10 or higher succeeds, 9 or lower fails.
Three successes stabilises; three failures is death. A natural 20 restores 1 hit point; a natural
1 counts as two failures. Taking damage at 0 hit points causes one failure, or two from a critical
hit. An attack that hits an unconscious creature from within 5 feet is an automatic critical hit.

**Instant death is decided on the remainder, not the total.** Where damage reduces a creature to 0
hit points and damage is *left over*, the creature dies outright if that **remaining** damage equals
or exceeds its hit point maximum. A single large hit on a healthy creature does not kill it by being
large — most of the damage is spent reaching 0, and only what is left past that counts.

**Ability modifier** — `floor((score − 10) / 2)`

---

EDITION DIFFERENCES THAT BITE
=============================

Not a migration guide. These are the places where running the wrong edition's rule produces a
materially different outcome, and where the two are similar enough to be confused.

**Exhaustion — the sharpest divergence.**

*2014:* six discrete levels, each a different effect. 1 disadvantage on ability checks · 2 speed
halved · 3 disadvantage on attack rolls and saving throws · 4 hit point maximum halved · 5 speed
reduced to 0 · 6 death. Cumulative. A long rest removes one level, given food and drink.

*2024:* six levels, but a single linear penalty. All d20 tests are reduced by twice the exhaustion
level, and speed is reduced by 5 feet per level. Death at 6.

These produce very different games at low levels, and the 2024 form is easy to apply to a 2014
campaign by mistake because it is simpler and more recent.

**Other divergences to check rather than recall:** weapon mastery properties, species replacing
race, backgrounds granting feats and ability score increases, and a substantial list of revised
spells. This module does not attempt to enumerate them — consult the source for the active
edition.

---

RECALL HAZARDS
==============

See `Game_Systems/Reference/Recall_Hazards.md`, shared across all modules — the measured hazard is
structure-shaped rather than topic-shaped, so it does not vary by system and is not duplicated
here.

**This module's calibration: the operating rule as stated is adequate.** Two monsters and three
spells came back exact, including every ability score; the errors were secondary elements only —
a missing second damage component, a dropped resistance.

> **Look a statblock up before running a fight with it. Recall is adequate for reference,
> description and prep.**

---

ADAPTATION
==========

Resolved in `Game_Systems/Adaptations/Baseline_DnD5e.md`. Not summarised here: an adaptation is a
property of a *pair*, not of a module, and a second pairing would either duplicate this section or
contradict it.

Two results are worth knowing before reading the manifest above, because the manifest alone implies
the opposite of both: `conditions` **partitions** rather than overriding, and `npc_statblock`
**extends** rather than replacing. A chain compiled without the profile discards Baseline's
sustenance model and the behavioural half of every NPC block.

---

NOT IN THIS MODULE
==================

| | Where it lives |
|---|---|
| Yes-But / No-And | doctrine — `success_grades: absent` inherits it |
| Never fabricate a die result | epistemics |
| Showing the roll | presentation |
| Gear durability | Baseline, via `equipment: absent` |
| Hunger, thirst, daily accumulation | Baseline, via the `conditions` partition |
| What the core loop is, how actions work, what the conditions do | nowhere — reliably recalled, deliberately unstated |

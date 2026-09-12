---
name: Baseline
type: rules-reference
keywords: [rules, system, baseline, conditions, hunger, fatigue, recovery, equipment, durability, resolution, contest]
description: The rules-light narrative system that ships with the engine. Runs standalone, and stays live underneath a crunchier system as the everyday substrate that published systems do not model.
---

BASELINE
========

Baseline has two jobs.

It is a **complete rules-light system** — thorough enough to run a campaign on its own, resolving
by judgement and narrative weight rather than by arithmetic.

It is also the **everyday substrate** beneath a crunchier system. Published systems specify combat,
magic and advancement; almost none of them say what a day in the saddle costs, whether a wound
needed treatment as well as time, or whether a pack survived the fire. Baseline does. Load a system
that declares those sites `absent` and this layer stays live underneath it.

That asymmetry shapes everything below. Baseline is **thorough** at the substrate sites, because
nothing else supplies them. It is **deliberately thin** at the crunch sites — enough to play, and
no more, because a loaded system replaces them anyway. Thinness there is the design, not an
omission.

---

MANIFEST
========

```yaml
resolution:
  state: defined
  lookup: inline
  answer: >
    Standard dice notation through a real RNG. No fixed core mechanic — the notation
    suits the moment. Most resolution is by judgement and never reaches a die.

difficulty:
  state: defined
  lookup: inline
  answer: >
    The GM sets it case by case from the fiction. No ladder, no target-number table.
    Roll only where failure carries a consequence and success is not already implied.

success_grades:
  state: absent
  answer: >
    Inherits doctrine's Yes-But / No-And. Baseline supplies no bands of its own.

contest:
  state: defined
  lookup: inline
  answer: >
    Weigh the relevant factors between the actors and narrate from the disparity.
    Resolution by comparison, not by opposed rolls, unless the moment is genuinely close.

harm:
  state: defined
  lookup: inline
  answer: >
    No hit points. Injury is a condition with a severity, a cause, and a treatment
    requirement. Permanence is decided at the moment of injury, not by a track.

conditions:
  state: defined
  lookup: inline
  answer: >
    Named conditions with severity, urgency tier, accumulation from ordinary activity,
    compounding, and resolution by specific in-world action. The substrate's core.

recovery:
  state: defined
  lookup: inline
  answer: >
    Nothing resolves by time alone. Each condition names what actually clears it, and
    serious ones need treatment, rest and time in combination.

incapacitation:
  state: defined
  lookup: inline
  answer: >
    Defeat means capture, retreat, injury or loss — not the end of play. Death requires
    a named cause the fiction has already established.

resource:
  state: none
  answer: >
    Deliberately unmodelled. No pool is spent to act. A system that supplies one is
    adding a mechanic Baseline does without, not filling a gap Baseline left.

progression:
  state: defined
  lookup: file
  source: skill_trees.md
  answer: >
    The Emergent Skill Tree System — capability recognised retrospectively, tiers
    changing what is possible rather than adding bonuses. Optional per campaign.

equipment:
  state: defined
  lookup: inline
  answer: >
    Gear does not survive combat by default. Recovery from a damaged target carries a
    chance of loss, scaled to how the target was brought down.

pc_sheet:
  state: defined
  lookup: file
  source: ../../Core_Rules/Templates/Character_Sheet_Template.md
  answer: >
    Behavioural rather than numeric. The mechanical block is active conditions,
    permanent alterations, and the current in-game date.

npc_statblock:
  state: defined
  lookup: file
  source: ../../Core_Rules/Templates/Character_Sheet_Template.md
  answer: >
    The same template. Combat disposition — bravery, loyalty, breaking point — in place
    of numbers.
```

---

SUBSTRATE — CONDITIONS
======================

Conditions are the current state of a character, NPC or location, carried forward across scenes.
They can be positive or negative: a well-rested, well-fed character operates differently from a
baseline one, and a farm in a good spring is a different scene from one in drought.

**The list below is not exhaustive.** Track any condition that meaningfully affects state, and
apply these principles to it whether or not it appears here.

## The common conditions

**HUNGRY** — missed one or more meals. Affects temper, concentration and sustained effort. Small
frustrations register harder. *Clears:* a full meal.

**THIRSTY** — more acute than hunger. Headache, dry mouth, reduced endurance. Left unaddressed it
becomes a physical risk. *Clears:* adequate fluids.

**TIRED** — insufficient sleep or sustained exertion. Judgement softens; irritations become
flashpoints. *Clears:* a full night's sleep.

**EXHAUSTED** — severe or compounded fatigue. Movement is laboured, decisions visibly impaired.
*Clears:* extended rest — sleep alone may not be enough.

**INJURED** — a wound from combat, accident or environment. Severity scales from soreness and
limited movement up to requiring treatment to prevent worsening. *Clears:* treatment, rest and
time in combination — never time alone. Scars and lasting damage are permanent.

**SICK** — illness from exposure, contagion, poor conditions or a neglected wound. Severity scales
from low fever and cognitive fog up to bedridden delirium. Untreated illness progresses.

**INTOXICATED** — loosened inhibition, impaired judgement, reduced coordination. The character may
become more honest, more reckless or more volatile depending on who they are. *Clears:* time and
sleep.

**RESTED** — full sleep, no active physical demand. Sharper judgement, steadier temper, greater
physical capacity. Fades as the day progresses or exertion accumulates.

**INVIGORATED** — peak condition from good food, rest, favourable circumstances or a recent
success. A small edge on physical and social performance. Fades with time or adversity.

## Urgency

Not all conditions press equally. Three tiers, by how fast neglect costs something:

**IMMEDIATE** — demands action within the current scene. On fire, bleeding out, drowning,
suffocating. These do not wait for a decision point: unaddressed, they escalate automatically —
a new condition applies, an existing one worsens, or the scene forces a resolution nobody chose.

**SHORT-TERM** — pressing within hours. Noticeable now, significantly worse by the next scene.
Untreated moderate injury, exposure to extreme cold or heat, severe dehydration, a worsening
fever. Neglected across several scenes these compound.

**GRADUAL** — background pressure. The character is affected now, but the real cost is
accumulation. Hunger, mild thirst, tiredness, early illness. They quietly degrade performance and
mood until resolved, or until they compound into something acute.

**Neglect escalates between tiers.** Thirst is background noise until it is severe dehydration; a
minor wound left alone becomes infected. Track the trajectory, not only the current state.

## Accumulation

Conditions arrive through ordinary activity, not only through dramatic events. Track what the
character is doing and for how long, and apply conditions when they are realistically due.

Hunger, thirst and tiredness are the common ones — active for hours without food, without water,
or past a natural rest point. They are not the only ones:

- Hours in the saddle → soreness, stiffness, fatigue
- Working outdoors in cold → exposure, numbed extremities, lowered endurance
- Working outdoors in heat → accelerated dehydration, heat fatigue
- Extended tense social situations → mental fatigue, shorter temper, reduced patience
- Sustained physical labour → muscle fatigue building toward exhaustion

The principle: the world is physically real and the body responds to it over time. Apply
conditions when the fiction supports them, not only when the player has made a choice that
obviously causes one.

## Compounding

Conditions stack, and each additional one lowers the threshold for things going wrong — worse
decisions, shorter temper, greater cost on physical action, higher vulnerability to further harm.
A character carrying several at once is a person at the edge.

## Persistence

Conditions do not fade between scenes for convenience. An unaddressed condition remains active and
continues to shape output. Long-duration conditions — a serious injury, a chronic illness, a
pregnancy — are logged to the character sheet with the in-game date of onset, so time-sensitive
ones can be tracked across sessions.

---

SUBSTRATE — RECOVERY
====================

**Nothing clears by the passage of time alone.** Each condition names what actually resolves it,
and the fiction has to contain that thing: a meal eaten, water drunk, a night slept, a wound
cleaned and bound.

Serious injury needs **treatment, rest and time together**. Any one alone is insufficient, and the
absence of treatment is what turns a wound into SICK.

Recovery is interruptible. Rest that is broken does not count as rest; treatment applied badly, or
by someone unqualified, may not help and may do harm.

> **Under a system that defines its own rest mechanics,** those govern the mechanical recovery and
> this section governs what the fiction must contain for recovery to have happened. The two are
> not in competition — see the adaptation profile for the pair.

---

SUBSTRATE — EQUIPMENT
=====================

**Items do not survive combat by default.** Gear exposed to damaging conditions, even incidentally,
has a chance of being broken or destroyed when recovered. The owner surviving does not mean their
equipment did.

This matters tactically: a player who wants intact equipment has reason to think about *how* a
target is brought down, not only whether.

## Risk by damage type

**Area effects and heavy weapons — highest risk.** Area attacks affect everything in the area
regardless of intent. Heavy weapons carry the highest chance of destruction on a direct hit.

**Standard attacks — moderate.** Most attacks carry some chance of damaging carried items even
when equipment was not the target. Only precise, targeted or minimal-force takedowns carry
negligible risk.

**Clean hits to unarmoured locations** may leave armour intact, but do not guarantee that other
carried items survived.

| Item | Primary risk | Notes |
|---|---|---|
| Melee weapons | Melee combat | Impact, parrying, direct force |
| Armour | Any hit to an armoured location | Exception for clean shots to unarmoured locations |
| Ranged weapons | Direct hits, area effects | High risk from energy and heat |
| Carried gear | Automatic in an area effect; otherwise by chance | Pouches, packs, worn items |
| Fragile or complex items | Energy, area effects, sustained fire | Increased failure chance |

## Applying it

**Check when** items are recovered from a target that took significant damage — especially from
area effects, heavy weapons or sustained fire. **Skip or reduce when** the target went down
cleanly: a single precise strike, a quiet takedown, a surrender.

Severity scales with how it was done — a subtle or precise attack warrants little or no check; a
standard strike a low to moderate chance of loss; heavy weapons an elevated one; an area effect an
automatic check on everything in the area.

**Where manufactured goods are scarce**, destruction carries weight beyond the tactical loss, and
factions operating under those conditions develop methodical, precise approaches when intact
salvage is the objective.

**Organic threats are an edge case.** Destroying a diseased creature, a bioweapon, or anything
carrying a chemical or spore load can produce secondary hazards that threaten nearby items in
their own right. Killing something cleanly and killing it safely are not always the same choice.

---

CRUNCH — RESOLUTION
===================

Deliberately minimal. Most of what happens in a Baseline campaign is resolved by judgement and
never reaches a die.

**There is no core mechanic.** No universal d20-plus-modifier, no dice pool, no target-number
ladder. The notation suits the moment: a straight roll where the odds are even, a weighted one
where they are not, a percentile where a proportion is the natural question.

**Roll only where failure carries a consequence and success is not already implied** by what the
character has demonstrably become. Established competence resolves in narration. Dice are for
uncertainty with stakes.

**Difficulty is set from the fiction, case by case.** Baseline supplies no ladder on purpose — a
scale invites calibrating against the scale rather than against the situation, which is the habit
this system exists to avoid.

> Dice *integrity* — never stating a result that did not come from a real generator — is not here.
> It is an epistemic rule governing every system equally, and it lives in the epistemics module.
> The same applies to showing the roll, which is a presentation contract.

---

CRUNCH — CONTEST
================

When two or more actors are in conflict, **weigh the relevant factors between them before
determining the outcome**: skill and experience, size and physicality, active conditions,
equipment, numbers, and situational conditions such as terrain, lighting and positioning.

The stronger position should show in how the scene reads, not only in who wins. A cornered fighter
with a broken arm against a fresh, well-armed opponent is a different scene from two evenly matched
soldiers. Let the disparity be visible.

**Some factors are decisive enough to override the general balance.** A squad has a numbers
advantage until the one facing them has something that makes formation a liability rather than a
strength. When an actor holds a capability that changes the terms of the contest, recalculate from
there — the original advantage may become irrelevant or invert.

Opposed rolls are the exception rather than the rule, used where the comparison is genuinely close
and the outcome genuinely uncertain.

*Where the skill tree system is active, tier changes what is possible in the contest rather than
adding a bonus — see `progression`.*

---

CRUNCH — HARM
=============

**No hit points and no damage track.** Injury enters as a condition carrying a severity, a cause,
and a treatment requirement, and is resolved through *Recovery* above.

Wounds take time to heal. Broken bones limit movement. Scars are permanent. A fight barely won
still costs something — stamina, supplies, reputation or time.

**Permanent results are decided at the moment of injury**, not by crossing a threshold. A lost
limb, a taken eye, a ruined hand, lasting disfigurement: logged to the character sheet immediately
and reflected in the character's appearance from then on. They affect every relevant scene
afterwards and cannot be quietly forgotten.

---

CRUNCH — INCAPACITATION
=======================

**Defeat is not the end of play.** It means capture, retreat, injury or loss — a harder situation
the character now has to deal with, not a terminal state.

**Death requires a cause the fiction has already established.** A character dies when the
situation plainly kills them and nothing established offers a way out — not when a number is
reached, and not as a surprise the scene had not been building toward. The severity of what is
happening is the threshold, and it is the GM's judgement, made before the outcome is narrated
rather than after.

---

PROGRESSION
===========

The Emergent Skill Tree System, in `skill_trees.md` beside this file. Tracking format in
`../../Core_Rules/Templates/Skill_Tree_Block.md`. Optional per campaign — use it where
capability development is a central theme and the character has room to grow into it, skip it for
already-established characters with fixed capability or campaigns whose weight is political and
social.

Capability is recognised retrospectively rather than chosen, and higher tiers change what outcomes
are *possible*, what information surfaces, and how NPCs respond — never a bonus to a roll.

---

NOT IN THIS MODULE
==================

Recorded because their absence from a rules file is otherwise indistinguishable from an oversight.

| | Where it lives | Why |
|---|---|---|
| Never fabricate a die result | epistemics | An assertion with no traceable source. Governs every system equally, and must not be lost when one is loaded |
| Showing the roll | presentation | A rendering contract |
| Yes-But / No-And | doctrine | Baseline declares `success_grades: absent` and inherits it |
| Some NPCs cannot be persuaded; persuasion needs leverage | doctrine | Contains no mechanics, and holds under any system |
| Conditions are shown through behaviour, never announced | doctrine | True of any system's conditions |
| The character knows only what they would notice | epistemics | The Information Firewall applied to their own body |
| Status block, time display, scene tag | presentation | Rendering contracts |
| A depletable resource pool | nowhere | `resource: none` — deliberately unmodelled |

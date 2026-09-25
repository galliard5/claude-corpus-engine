---
name: Recall Hazards
type: rules-reference
keywords: [recall, hazards, lookup, statblock, reliability, measurement, modules]
description: Where recall of published rules content is reliable and where it is not, measured rather than asserted. Shared across all system modules; each module records only its own deviation.
---

RECALL HAZARDS
==============

**Shared across every system module.** The hazard turned out to be structure-shaped rather than
topic-shaped, so it does not vary by system — only its *severity* does. A module records its own
calibration against this document and nothing else.

Measured in `Recall_Tests/Recall_Test_Results.md` (d20, twelve items),
`Recall_Tests/Recall_Test_PF2e_Results.md` (Pathfinder 2e, seven items), and two blind runs of the same
twenty prompts on Eclipse Phase second edition, one by each of two models. The Eclipse Phase results live
with that module in its own repository, which is private because the game's licence cannot mix with this
one's; what is recorded here are the patterns, not the book's content. Predictions were committed before any
source was consulted in every run but one, whose predictions were frozen by hash before scoring and committed
afterwards; that run records the deviation itself.

---

## Reliable without lookup

Across both systems, and including deliberately obscure entries: armour class, hit points, hit
dice, speed, ability scores, attack bonuses, save DCs, spell level, school, range, area, base
damage, scaling clauses, condition effects, and core procedures.

**Rules architecture is the most reliable category of all** and appears genuinely
system-independent — degrees of success, proficiency structures, action economy and condition
definitions came back exact in the less-represented system as well as the better-known one,
including clauses flagged in advance as uncertain.

## Unreliable, and the errors are silent

Five categories, in rough order of how often they bit:

- **Compound attacks** — is there a second damage component? Dropped in testing.
- **Non-primary attacks** — the dice count specifically. Wrong in both systems tested.
- **Riders** — a condition applied on a hit, omitted from the recalled block.
- **Defensive traits** — resistances and immunities, dropped entirely in one case.
- **Exact component lists and duration wording**, where load-bearing.

## The failure mode

**Incompleteness, not inaccuracy.** Recall produces a statblock that is correct as far as it goes
and quietly a clause short. That is worse than being visibly wrong, because nothing in the output
flags itself as suspect and nothing downstream can tell.

## Two further failure classes

The Eclipse Phase runs added two classes the d20 and Pathfinder tests did not show. Both are
structure-shaped, so they are expected wherever a system has the structure, not only in the system that
showed them.

**Scope or case collapse — a real value attached to the wrong case.** The number is genuine and appears in
the book; it belongs to a narrower case than the one it is applied to. Both models gave the healing rate of
a body *without* augmentation as the rate for bodies in general, to the same numbers; one then did the same
with a rest timeframe, choosing the same narrow case again. A weapon's damage was given as its neighbour's.
This is harder to catch than an invented number, because the value checks out against the book unless the
case is checked too.

**Invented structure, or a plausible substitution.** A rule, field or mechanism the system does not have,
supplied confidently — often by carrying in the familiar generic one. Both models invented a
defender-wins rule for tied contests, and both gave bodies a statistic cap the edition does not have; one
put that invented field on every body it named. One model paid for a supernatural power in the generic
stress currency that neighbouring rules use, where the system charges a cost of its own. A GM relying on
recall here does not misstate a value; it applies a rule that does not exist.

**Two models agreeing on an error is not corroboration.** An error produced independently by both tested
models is the highest-priority pin. Two one-shot runs establish a shared failure, not an inevitable one.

---

## The operating rule, and why it is per-system

> **Look a statblock up before running a fight with it. Recall is adequate for reference,
> description and prep.**

The errors only bite when a block is being *resolved* rather than *referenced* — a dropped damage
component changes a fight and does not change a description.

**This rule is calibrated per system, because severity scales with how much the system is
discussed, not with how widely it is published.** Rules architecture is argued about continuously
in prose; a statblock is tabular data reproduced verbatim rarely.

| System | Calibration |
|---|---|
| DnD5e | **Rule as stated is adequate.** Two monsters and three spells came back exact, including every ability score. Errors were secondary elements only. |
| Pathfinder 2e | **Rule is not adequate — look the creature up regardless of purpose.** Roughly half a statblock wrong, including a primary damage die and two of three saves, and three of four special abilities absent entirely. Recall is not reliable enough even for description. |
| Eclipse Phase 2e | **Architecture is broadly reliable; everything tabular, and every setting-specific case or cost, needs a lookup.** Resolution, graded results, both harm tracks and their formulas, death and restoration came back exact or close for both models. No body's full statistic line was right, every weapon and armour number was wrong for at least one model, and the errors above — a narrower case's value, an invented rule or field, a generic cost substituted — all fell on rules whose surrounding architecture was recalled. Uncommon entries need a lookup even for description; the generic ones were usable for reference. |

## Recording a new system's calibration

A module adding itself to the table above should measure rather than estimate, because
**self-assessed confidence was the least reliable thing in both tests** — and wrong in the
unexpected direction. Entries labelled "low confidence on exact numbers" came back exact; the item
singled out in advance as the likely failure came back substantially right, in both systems.

The cheap method: commit predictions for a handful of items across the confidence range, *then*
consult sources, then compare. Half an hour, and it produces the calibration line as output rather
than as guesswork.

The Eclipse Phase runs reproduced the confidence gap a third time: an invented rule sat inside an answer
tagged *confident*, and two exact statistic lines came from an answer tagged *low*.

**Measure the model that will run the game.** The two models tested on Eclipse Phase agreed on three errors
and differed on most of the rest; each recalled rules the other missed. A calibration measured on one model
is evidence about the system, but it does not tell a module what a different GM model will get wrong. Pin
the shared errors first, then the running model's own.

## Edition leakage — not blending, but a carried-over piece

The d20 and Pathfinder tests deliberately probed the hypothesis that editions blend in recall — the
2014/2024 d20 revision and the Pathfinder Remaster. Both probes were flagged in advance as the likely
failure. **Both came back substantially right.**

Eclipse Phase showed the hazard once in each model, in a narrower form. Neither blended the editions: both
described the structural changes between first and second edition well. What leaked was a single piece —
one model gave a first-edition armour-penetration mechanic fitted with second-edition-looking numbers, the
other gave the first edition's list of social networks. That is the case-collapse class again, with an
edition as the wrong case.

So treat edition *blending* as unevidenced, and edition *leakage* of individual mechanics and lists as real
where editions differ in them. The `edition:` manifest field still earns its place mainly on **provenance**
grounds — a campaign resumed in two years cannot otherwise tell which ruleset it was built against — and a
module whose editions differ in specific pieces should pin those pieces.

---

## Caveats carried from both tests

**SRD content only.** Everything tested is the most-reproduced subset of each game. Non-SRD
material — most subclasses, published adventures, and recent releases generally — was not tested,
and is where recall would be expected to degrade first.

**Small samples.** Twelve items, seven, and twenty twice. Enough to establish the pattern and its
direction; not enough to quantify a rate. Each Eclipse Phase model ran once, so a second cold run could
differ, most of all on low-confidence items.

**One source per system**, so a systematic error in a source would read here as agreement.

**One confound recorded and not resolved:** the Pathfinder creature was checked against Remaster
text, and the Remaster revised statblocks. Some of those differences may be edition drift rather
than recall failure. The three missing abilities are unlikely to be explained that way; the save
and damage differences might be.

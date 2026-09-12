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

Measured in `Recall_Tests/Recall_Test_Results.md` (d20, twelve items) and
`Recall_Tests/Recall_Test_PF2e_Results.md` (Pathfinder 2e, seven items). Predictions in both cases
were committed before any source was consulted.

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

## Recording a new system's calibration

A module adding itself to the table above should measure rather than estimate, because
**self-assessed confidence was the least reliable thing in both tests** — and wrong in the
unexpected direction. Entries labelled "low confidence on exact numbers" came back exact; the item
singled out in advance as the likely failure came back substantially right, in both systems.

The cheap method: commit predictions for a handful of items across the confidence range, *then*
consult sources, then compare. Half an hour, and it produces the calibration line as output rather
than as guesswork.

## Edition blending — claimed, and not evidenced

Both tests deliberately probed the hypothesis that editions blend in recall — the 2014/2024 d20
revision and the Pathfinder Remaster. Both probes were flagged in advance as the likely failure.
**Both came back substantially right.**

Treat the edition-blending hazard as unevidenced. The `edition:` manifest field earns its place on
**provenance** grounds — a campaign resumed in two years cannot otherwise tell which ruleset it was
built against — and not on any claim about recall.

---

## Caveats carried from both tests

**SRD content only.** Everything tested is the most-reproduced subset of each game. Non-SRD
material — most subclasses, published adventures, and recent releases generally — was not tested,
and is where recall would be expected to degrade first.

**Small samples.** Twelve items and seven. Enough to establish the pattern and its direction; not
enough to quantify a rate.

**One source per system**, so a systematic error in a source would read here as agreement.

**One confound recorded and not resolved:** the Pathfinder creature was checked against Remaster
text, and the Remaster revised statblocks. Some of those differences may be edition drift rather
than recall failure. The three missing abilities are unlikely to be explained that way; the save
and damage differences might be.

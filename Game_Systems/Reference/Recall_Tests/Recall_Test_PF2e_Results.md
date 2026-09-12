# Recall Test — Pathfinder 2e Results

Predictions committed at `589cf23` before any source was consulted. Sources: Archives of Nethys
(the official free PF2e reference) and web search.

**The prediction stated in advance was that structural recall would be noticeably worse than on
5e. It was — but only in one place, and that place is the finding.**

---

## Scoreboard

| # | Item | Predicted confidence | Result |
|---|---|---|---|
| P1 | Degrees of success | confident | **exact** |
| P3 | Proficiency ranks | moderate, untrained clause flagged uncertain | **exact**, including the flagged clause |
| P4 | Frightened | moderate | **exact** |
| P5 | Clumsy | moderate | **exact**, including which skills |
| P6 | Fireball | **low** | **exact** |
| P7 | Owlbear | low | **substantial miss — see below** |
| P8 | Remaster changes | low to moderate, flagged as likely confabulation | **substantially right** |

P2 (three actions plus a reaction) was not verified.

---

## The one failure, and it is the whole result

**PF2e Owlbear, Creature 4.**

| Field | Predicted | Actual |
|---|---|---|
| Level | 4 | 4 ✓ |
| AC | 21 | 21 ✓ |
| HP | ~70 | 70 ✓ |
| Fortitude | +13 | +13 ✓ |
| Reflex | +9 | **+7** ✗ |
| Will | +9 | **+11** ✗ |
| Speed | 25 ft | 25 ft ✓ |
| Attack bonuses | +14 both | +14 both ✓ |
| Beak damage | 2d8+7 | **1d12+6** ✗ |
| Second Strike | "claw", 1d10+7 | **talon**, 1d10+6, agile, Grab ✗ |
| Special abilities | "probably grab or knockdown, and scent" | Grab ✓; **Bloodcurdling Screech, Gnaw, Screeching Advance all missed** |

Roughly half the statblock. Compare the same creature in 5e, where every single value was exact,
including all six ability scores.

**And the error class is different, not just the rate.** In the d20 test every error was a
secondary element — a rider, a resistance, the second damage component. Here a *primary* number is
wrong: the beak's damage die, which is the first thing anyone reads off the block. Two of three
saves are wrong. Three of four special abilities are simply absent.

---

## What generalises and what does not

**Rules architecture recall is strong and appears system-independent.** Degrees of success,
proficiency ranks, two conditions — all exact in a system with a fraction of 5e's corpus presence.
The proficiency untrained clause was flagged in advance as the uncertain part and was right.

**Iconic spell recall held.** PF2e Fireball exact, despite being labelled low confidence.

**Creature statblock recall degrades sharply with corpus representation.** This is the only axis
where the two systems diverge, and it diverges hard: perfect to half-right on the same creature in
two systems.

That asymmetry has an obvious explanation. Rules architecture is discussed continuously in prose —
forums, guides, comparisons, arguments. A statblock is tabular data that appears in a book and
gets reproduced verbatim rarely. Volume of *discussion* predicts recall; volume of *publication*
does not.

**Edition change was again better than predicted.** The Remaster answer was right on alignment
removal, spell levels becoming ranks, *Magic Missile* becoming *Force Barrage*, and the
chromatic/metallic dragons being replaced with new Paizo types. The one imprecision: seven of
eight magic schools were removed and *illusion was kept*, which the prediction did not capture.

Two edition probes now, in two systems, both flagged in advance as likely failures, both
substantially right. The edition-blending hazard should be treated as unevidenced until something
actually demonstrates it.

---

## What this changes in the module design

The d20 study concluded a module is 150–200 lines because the model knows the system. That was
right for 5e and is **not a general rule**.

The replacement rule separates two things the earlier conclusion had merged:

> **Rules pinning is small and roughly constant across systems. Content data — the bestiary above
> all — scales inversely with how much the system is *discussed*.**

So:

| System | Pinning sheet | Bestiary dataset |
|---|---|---|
| d20 / 5e | small | low priority — completeness, not accuracy |
| Pathfinder 2e | small | **high priority — recall is not adequate for play** |
| An obscure or house system | large | essential, because nothing is recalled at all |

The operating rule from the d20 test — *look up a statblock before running a fight, recall is fine
for reference* — holds for 5e and is **too weak for PF2e**, where recall is not reliable enough
even for description: quoting the owlbear's screech ability would have been impossible, since the
prediction did not know it existed.

For PF2e the rule is simply: **look the creature up.**

---

## Caveats

**A real confound on the Owlbear, and it is worth stating plainly.** Archives of Nethys serves the
current Remaster text, and the Remaster revised many statblocks. Some of the differences above may
be edition drift — recalling a pre-Remaster Bestiary entry accurately — rather than recall failure.
Resolving it needs the superseded statblock, which was not consulted. The special abilities that
were missed entirely are unlikely to be explained this way; the save and damage differences might
be.

That this confound appears in the middle of an investigation into edition hazards is not lost on
me, and it argues for `edition:` on provenance grounds more effectively than anything in the
predictions did.

**One creature.** The 5e test used two monsters plus three spells; this used one of each plus
architecture. The divergence is large enough to be visible through that, but the rate is not
measured.

**Search rather than primary text** for the Remaster answer and the two conditions, so those
reflect secondary reporting that happened to be consistent.

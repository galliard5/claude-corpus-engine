# Recall Test — Results

Predictions committed at `d9ca03a` and `c8a398b` before any source was consulted. Sources: the
SRD 5.1 API for 2014 content, web search for the 2024 exhaustion rule.

**Headline: 12 of 12 checked items substantially correct, with four errors, all of the same
kind.** The errors are informative in a way the successes are not.

---

## Scoreboard

| # | Item | Predicted confidence | Result |
|---|---|---|---|
| 3 | Death saves | confident | **exact** |
| 4 | Exhaustion, 2014 | confident | **exact**, all six levels + recovery |
| 5 | Restrained | confident | **exact**, all three clauses |
| 8 | Fireball | moderate | **exact** |
| 9 | Owlbear | **low** | **exact** — every number |
| 10 | Goblin | **low** | **exact** — every number |
| 11 | Cure Wounds (2014) | moderate | **exact** |
| 12 | Magic Missile | moderate | **exact** |
| 13 | Exhaustion, 2024 | **low, flagged as likely failure** | **substantially right** — see below |
| 15 | Otyugh | low | **one miss** |
| 16 | Grick | low | **two misses** |
| 17 | Glyph of Warding | low | **two imprecisions** |

Not verified, so not scored: proficiency bonus table, DC ladder, rest rules, the
auto-critical-within-5-feet rule, Cure Wounds 2024.

---

## The four errors, which are all one error

**Grick tentacles — predicted `1d6+2` slashing, actual `2d6+2`.** Wrong dice count on a
non-primary attack.

**Grick — missed resistance to nonmagical bludgeoning, piercing and slashing entirely.** A
defensive trait that materially changes a fight, simply absent from the prediction.

**Otyugh tentacle — predicted `1d8+3` bludgeoning, actual `1d8+3` bludgeoning *plus 1d8
piercing*.** The second damage component of a compound attack, dropped. Also dropped "and
restrained" from the grapple rider.

**Glyph of Warding — material component predicted as "diamond dust", actual "incense and powdered
diamond"; duration predicted "until dispelled or triggered", actual "until dispelled".** Gist
right, wording imprecise.

### The pattern

Every error is in a **secondary element**: the second damage component of a compound attack, the
dice on a non-primary attack, an appended rider, a defensive trait, the exact wording of a
component list. Nothing structural was wrong — not one armour class, hit point total, hit dice
expression, speed, ability score, attack bonus, save DC, spell level, range, area, or scaling
clause, across two rounds including deliberately obscure entries.

The failure mode is **incompleteness, not inaccuracy.** Recall produces a statblock that is
correct as far as it goes and quietly short of a clause or two. That is worse than being visibly
wrong, because there is nothing in the output to flag as suspect.

---

## Calibration was wrong, and in the unexpected direction

Self-assessment was **under**confident, not over.

Owlbear and Goblin were labelled "low confidence on exact numbers" and came back exact to the last
ability score. Fireball, Cure Wounds and Magic Missile were labelled "moderate" and were exact.

Most striking: **item 13 was flagged in advance as the predicted failure** — the 2014/2024
exhaustion blend, described as "genuinely unsure of the numbers". The prediction said a linear
penalty of roughly −2 to d20 tests per level, some speed reduction per level, death at 6. The
actual 2024 rule is d20 tests reduced by twice the exhaustion level, speed reduced by 5 feet per
level, death at 6. Structure right, d20 penalty right, speed reduction correctly identified but
without its number.

So the edition-blending hazard I argued most strongly for **did not materialise in the one place
it was tested.** That does not make it imaginary — one test is not coverage, and the 2024 changes
are wide — but it does mean the argument for `edition:` should rest on something firmer than my
self-report.

**The general lesson is that self-report about one's own reliability was the least reliable thing
in this exercise.** It was wrong about statblocks, wrong about spells, and wrong about the case it
singled out as the likely failure.

---

## What this changes

### The SRD dataset is not the priority I argued it was

The previous study recommended building an indexed SRD dataset as the module's main cost, on the
reasoning that spell and monster specifics are the confabulation risk. Measured, they are not —
the headline numbers come back exact even for low-citation monsters.

**Revised:** a dataset is still worth having, but for *completeness on demand* rather than for
accuracy. Its job is supplying the second damage component and the resistance line, not correcting
a wrong armour class.

That lowers its priority and narrows its scope. It also means a d20 module is usable **before** the
dataset exists, which the earlier estimate did not allow for.

### The usable operating rule

The errors only matter when a statblock is being *resolved* rather than *referenced*. A dropped
damage component changes a fight; it does not change a description.

> **Look up a statblock before running a fight with it. Recall is adequate for reference,
> description, and prep.**

That is narrow enough to be followed and it targets exactly the measured failure.

### Recall-hazards note — worth keeping, with different content

The earlier proposal was a list of topics where memory is unreliable. Measured, the hazard is not
topic-shaped but **structure-shaped**, so the note generalises across systems rather than being
per-system:

- Compound attacks — is there a second damage component?
- Non-primary attacks — the dice count, specifically
- Riders appended to an attack — conditions applied on hit
- Defensive traits — resistances and immunities, which are easy to omit entirely
- Exact component and duration wording, where it is load-bearing

### `edition:` still earns its place, on a different argument

Not "the model blends editions" — untested at best, and the one probe came back fine. The argument
that survives is **provenance**: a campaign started now and resumed in two years cannot otherwise
tell which ruleset it was built against, and a system with two incompatible published editions
makes that ambiguity permanent. Same reasoning as `built_against` for homebrew, and it does not
depend on any claim about model reliability.

---

## Caveats

**Single source.** Everything 2014 was checked against one API. It is the standard community
dataset and derived from the SRD, but a second source was not consulted, so a systematic error in
it would read here as agreement.

**Small sample.** Twelve items. Enough to establish that structural recall is strong and that the
errors cluster in secondary elements; not enough to quantify a rate.

**SRD only.** Everything tested is SRD content, which is the most-reproduced subset of the game.
Non-SRD material — most subclasses, most published adventures, the 2024 content generally — was
not tested at all, and is where recall would be expected to degrade first.

**The 2024 check used web search rather than the SRD text**, so it reflects secondary reporting.
It was consistent across several sources, but it is not the primary document.

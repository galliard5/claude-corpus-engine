# Adaptation Study — d20 / D&D 5e

What the three shipped d20 ports actually contain, what a module for our interface would have to
be, and what the `Baseline → DnD5e` adaptation produces. First real test of the thirteen call
sites against a system we did not design.

Sources read 2026-09-11:

- `Bobby-Gray/open-tabletop-gm` — `systems/dnd5e/system.md`, the closest structural analogue
- `PinchOfData/claude-dungeon-master` — `dm-instructions/`, `dnd-5e-srd/`
- `neuralinitiative/claude-dnd-skill` — `scripts/`, `data/`

---

## Finding 1 — a d20 module is small, because the model already knows d20

This is the finding that changes the estimate.

`open-tabletop-gm/systems/dnd5e/system.md` is **eleven sections, most of them five to twenty
lines**, and it explicitly does not attempt a full rules encoding. `claude-dungeon-master`'s
`combat-rules.md` is 800–900 words for the whole of combat. Both **assume moderate familiarity and
do not teach the system** — neither defines AC, modifiers, or proficiency; they reference them.

What those files actually contain is not rules but **pinning**: which edition is in force, the
handful of tables nobody recalls exactly (XP thresholds, proficiency bonus, death-save outcomes),
the formula for a derived value, and pointers to where bulk data lives.

So `Game_Systems/DnD5e/dnd5e.md` is on the order of **150–200 lines**, not a rules document. That
is a different kind of artifact from `Game_Systems/Baseline/baseline.md`, which had to be written
out in full because it is the engine's own system and nothing external supplies it.

**Corollary worth stating in the interface spec:** a module's body is only as long as the gap
between what the model reliably knows and what the campaign needs pinned. A widely-known published
system needs little. An obscure or house system needs everything. Baseline is the second kind.

## Finding 2 — licensing: use the CC-BY source, not the community datasets

**I got this wrong earlier** and the correction matters for a repository that ships under
Apache-2.0.

What is true: WotC released **SRD 5.1 under CC-BY-4.0 on 2023-01-27**, irrevocably. Attribution is
the only condition. That composes cleanly with Apache-2.0 and `NOTICE` already exists to carry the
attribution.

What I said that was wrong: that the community datasets carry that licence forward. They do not.
**`5e-bits/5e-database` is MIT for the code and OGL 1.0a for the underlying material** — which is
the licence both ports inherit, since both derive their data from it. OGL 1.0a is a different
instrument: it carries a Section 15 declaration chain, Product Identity carve-outs, and a
requirement that the licence accompany any distribution of Open Game Content. It does not compose
into an Apache-2.0 repository without dragging its own terms along.

**So: take SRD content from the CC-BY release directly and build our own dataset from it.** Do not
vendor `5e-bits` JSON, however convenient. The cost is a conversion step we would otherwise have
skipped; the benefit is a module that ships under one licence with one attribution line.

`claude-dungeon-master`'s `dnd-5e-srd/` is markdown converted from the SRD and may be the cleaner
starting point than JSON, given the engine is prose-and-FTS shaped rather than API shaped — but
its provenance needs checking against the same question before it is used.

## Finding 3 — their section list is shorter than our call-site list, and the gaps are informative

Mapping `open-tabletop-gm`'s eleven sections onto our thirteen sites:

| Their section | Our call site |
|---|---|
| Dice Convention | `resolution` |
| Ability Scores | `pc_sheet`, partly `resolution` |
| Character Structure | `pc_sheet` |
| XP Thresholds | `progression` |
| Rests | `recovery` |
| Death Saves | `incapacitation` |
| Conditions | `conditions` |
| Inspiration / Bold Play Reward | `resource` |
| SRD Data Lookup | — the `lookup` mechanism, not a site |
| System Versions | — see below |

**Four of our sites have no counterpart in theirs:** `difficulty`, `contest`, `harm`, `equipment`,
`npc_statblock`. Three of those absences are real properties of d20 rather than oversights —
`equipment` because 5e has no durability rules at all, and `difficulty` and `contest` because both
are left to GM judgement in practice. `harm` is folded into their Character Structure as an HP
field rather than treated as a site.

That is the thirteen-site list doing its job: it names things a system might not model, so the
absence becomes a declaration instead of a silence.

**One thing they have that our manifest cannot express.** Their *System Versions* section pins
which edition is in force — 2014 or 2024 — and routes to version-specific data. Our manifest has
no field for it. A published system with multiple incompatible editions is common enough that this
is a real gap.

**Proposed:** an `edition:` field at manifest top level, free-text, required for any module
adapting a published system. Absent it, a campaign started in 2026 and resumed in 2028 cannot tell
which ruleset it was built against — the same class of problem `built_against` solves for homebrew.

---

## The adaptation: `Baseline → DnD5e`

Worked by hand, in the order the pass specifies: what does Baseline cover that d20 does not
mention, then what genuinely conflicts, then what is cleanly superseded.

### Additive — Baseline survives underneath

**`equipment` — d20 declares `absent`.** 5e has no gear-durability rules whatsoever. Baseline's
entire equipment section stays live. **This is the designed case working exactly as intended**, and
it is the single clearest vindication of making Baseline a floor rather than a peer.

**`conditions` — mostly additive, not conflicting.** This is the case that motivated the whole
adaptation pass, and having worked it through it is less alarming than feared but more interesting.
5e's conditions are *combat statuses* — prone, grappled, poisoned, restrained — and its exhaustion
track is six levels tied to specific triggers. It models **no hunger, no thirst, and no
accumulation from ordinary activity**. Baseline's conditions and 5e's barely overlap: they are two
disjoint sets that happen to share a call site.

So the resolution is not "d20 wins" but "both, partitioned": 5e owns combat statuses and the
exhaustion track; Baseline retains sustenance, daily accumulation, compounding, and the urgency
tiers. The one genuine overlap is fatigue, where 5e exhaustion and Baseline TIRED/EXHAUSTED say
different things about the same state — see below.

**`npc_statblock` — both wanted, and this is an `extend` rather than an override.** 5e statblocks
carry AC, HP, attacks. Baseline's template carries bravery, loyalty, and breaking point. Neither
supersedes the other and a campaign wants both. Worth noting that the naive resolution — later
layer wins — would have discarded the behavioural half, which is the more distinctive of the two.

**`harm` — one rule survives an otherwise clean override.** 5e's hit points replace Baseline's
injury-as-condition model entirely. But Baseline's *permanent results decided at the moment of
injury* — a lost limb, a taken eye, logged immediately and reflected in appearance thereafter —
has no 5e equivalent; 5e has no lasting-injury rules. That rule should stay live.

### Conflicting — needs a ruling

**`recovery` — the real conflict.** A 5e long rest restores all hit points overnight. Baseline says
wounds need treatment, rest and time in combination and never resolve by time alone. These
genuinely contradict, and the contradiction is tonal as much as mechanical: 5e's recovery curve is
deliberately fast so that adventuring can continue, and Baseline's is deliberately slow so that
injury has weight.

Three defensible rulings, and this is exactly the decision the pass exists to put in front of a
player rather than have an agent make silently:

1. **5e recovery governs entirely.** Simplest; loses the injury weight Baseline was providing.
2. **Split by severity.** Hit-point loss recovers on 5e's curve; anything logged as a lasting
   injury follows Baseline's treatment-rest-time rule. Preserves both, at the cost of tracking two
   things.
3. **5e rests gated on Baseline's fiction.** A long rest only counts as one if the fiction contains
   what Baseline requires — shelter, food, uninterrupted sleep. Mechanically 5e, narratively
   Baseline.

Option 3 is the one that matches what Baseline's *Recovery* section already gestures at with its
forward reference, and it is the least invasive of the three.

**`success_grades` — a subtler conflict than it looks.** 5e is binary: the attack hits or misses,
the check meets the DC or does not. Declared `defined`, that would displace doctrine's Yes-But /
No-And, which is one of the strongest anti-accommodation rules in the engine.

**Recommendation: a d20 module declares `success_grades: absent` and inherits doctrine.** 5e's
hit/miss is a *resolution output*, not an outcome-grading philosophy — most tables running 5e still
narrate partial successes and costs. Treating the binary as a grading system would be reading a
mechanic as a position it never took.

**`conditions.fatigue` — the one genuine overlap inside an otherwise additive site.** 5e exhaustion
and Baseline's TIRED/EXHAUSTED both model the same state with different consequences and different
triggers. Needs one to win. Likely 5e, since it carries mechanical effects the rest of that system
depends on — with Baseline's *accumulation* rules feeding it rather than running beside it. That
is a neat outcome if it works: Baseline supplies the triggers, 5e supplies the effects.

### Cleanly superseded

`resolution`, `difficulty`, `contest`, `incapacitation`, `progression` (skill trees off),
`pc_sheet` (with Baseline's conditions-and-date block merged in). `resource` is d20 filling a site
Baseline declares `none` — a clean `add`.

---

## What this validates, and what it did not

**Validated.** The floor-not-peer design: `equipment` is the case it was built for and it works.
The adaptation pass: four sites produce additive survival that the naive resolution would have
discarded, and two produce genuine conflicts a player should rule on. The thirteen-site list:
d20's absences become declarations rather than silences.

**Not validated.** Nothing here tested a system that *conflicts structurally* with Baseline rather
than merely covering more ground — the Hunger-mechanic case where a system would rightly displace
sustenance entirely. d20 is the easy adaptation because it is additive almost everywhere.

**Found missing.** The `edition:` field. One gap in thirteen sites plus two mechanisms, from a
system the interface was not designed against, is a better result than expected.

---

## What building it would actually take

1. **`Game_Systems/DnD5e/dnd5e.md`** — 150–200 lines. Manifest, `edition:` pin, the small tables
   that need pinning, pointers to data. Not a rules document.
2. **`Game_Systems/DnD5e/data/`** — SRD 5.1 content from the **CC-BY-4.0 release**, converted and
   indexed the way `series-search` indexes its corpora. Not vendored from OGL-licensed community
   datasets. `NOTICE` carries the attribution.
3. **`Game_Systems/Adaptations/Baseline_DnD5e.md`** — the adaptation profile above, expanded and
   ruled on, keyed on the chain.

The first is a day's work. The second is the real cost and is mostly conversion and indexing. The
third is a conversation, and the material above is most of its agenda.

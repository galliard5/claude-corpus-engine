# Interface Test Notes — What Building DnD5e Revealed

The sample d20 module was built to test the interface, not to be used. This records what the
exercise found. Five results, two of which change something.

---

## 1. The size prediction held for the module, and I put two things in it that belong elsewhere

Predicted 150–200 lines. Delivered 266. The overshoot is not in the module:

| Section | Lines | Belongs |
|---|---|---|
| Frontmatter, banner, preamble | ~22 | here |
| Manifest | ~110 | here |
| Pinned tables | ~35 | here |
| Edition differences | ~25 | here |
| **Recall hazards** | ~35 | **a shared document** |
| **Adaptation notes** | ~30 | **the adaptation profile** |
| Not in this module | ~12 | here |

The module proper is ~190 lines, inside the prediction. The two misplaced sections are misplaced
for the same reason in opposite directions:

**Recall hazards are system-independent.** The measured hazard is structure-shaped — compound
attacks, non-primary dice counts, riders, defensive traits — and applies to any system. Copying it
into every module duplicates it and invites drift. It belongs once, somewhere shared, with each
module carrying only its own deviation from the general picture (for d20: "the operating rule is
adequate here"; for PF2e: "it is not").

**Adaptation notes are pair-specific, not module-specific.** Everything under that heading
describes `Baseline → DnD5e`, which is the adaptation profile's subject. Putting it in the module
means a second system pairing would either duplicate or contradict it.

**Action:** both move. A module carries its manifest, its pinning, and its edition notes. Nothing
about what it meets.

## 2. All thirteen call sites were answerable, with no gaps

The site list was derived from our own rules and one shipped port. It held against a system it was
not designed against — every site had a real answer, and nothing about 5e needed a site that did
not exist.

That is the strongest result here, and it was the thing most likely to fail.

## 3. `none` went unexercised, which is worth admitting

Of thirteen sites: eleven `defined`, two `absent`, **zero `none`**. 5e defines nearly everything,
and where it does not — durability — the right answer is `absent`, because its silence is scope
rather than a design position.

The only `none` in the whole chain is Baseline's `resource`. So the three-state vocabulary is
exercised across the pair but not within a module, and the state argued for most strongly is the
least tested. It would take a system with a deliberate absence — a narrative system with no hit
points — to exercise it properly.

Not a defect. But "we designed three states and two of them have one instance each" is the honest
summary.

## 4. `edition:` earned its place immediately, and concretely

The 2014 and 2024 exhaustion rules are genuinely incompatible — six discrete effects against a
single linear penalty — and the 2024 form is *easier to misapply to a 2014 campaign* because it is
simpler and more recent. That is a material difference in play, sitting behind a field that
previously did not exist.

Note that this justification is a property of the *system*, not of model reliability. Both recall
tests found edition recall better than predicted, so the argument for `edition:` should continue to
rest on provenance, which this demonstrates.

## 5. The manifest is not merely incomplete without an adaptation profile — it is misleading

**This is the one that changes something.**

The manifest says `npc_statblock: defined`. Read naively through the layer order, that means 5e's
statblock replaces Baseline's — and the correct behaviour is to keep both, because 5e supplies
numbers and Baseline supplies bravery, loyalty and breaking point. Nothing in the manifest can
express "extends rather than replaces"; only the adaptation profile knows.

The same is true at `conditions`, where the correct behaviour is a partition rather than an
override.

So a campaign compiled **before** its adaptation profile exists does not produce an approximation
of the right answer. It produces a confidently wrong one, and silently discards the more
distinctive half of the NPC block.

**Proposed fix, consistent with the rest of the design:** the compile **refuses** to write
`Active_Rules.md` when two layers both answer a site and no adaptation profile covers that pair.
Not a warning — a refusal, the same way the compiled file refuses when its inputs have moved. An
obviously-unpublished state beats a confidently-wrong one.

That makes the adaptation profile a **prerequisite for play on any chain longer than one module**,
rather than an optimisation. Which is what the `npc_statblock` case shows it always was.

---

## Actions falling out

1. Move recall hazards out of the module into a shared document; leave a per-module deviation note.
2. Move adaptation notes out of the module into the `Baseline → DnD5e` profile.
3. Make the compile refusal above part of the durable interface and compiler contract.
4. Verify the proficiency and DC tables against source — flagged in the module as unchecked.
5. `lookup: dataset` in `npc_statblock` points at a `data/` directory that does not exist. Honest,
   and it makes ITEM 10's dependency concrete, but the module is partially unusable until then.

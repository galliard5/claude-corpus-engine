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

---

# Second module — what a system with replaceable bodies revealed

The draft's own *Deferred* section asked for a system "written for human readers" as the test of whether the
call sites are real rather than fitted. The second module is that test: a percentile system in which the
persistent character is a mind and the body is replaceable, with a second harm track for the mind, restorable
death, and three large subsystems no doctrine reaches into. Its licence keeps it out of this repository; it lives
in its own and is linked rather than contained. What follows is what it taught about the interface, in general
terms.

## 6. The thirteen sites held a second time; the vocabulary around them did not

Nothing the system needed a GM to run lacked a site. What did not fit was how the sites are declared, and each
change is proposed as an amendment to the draft rather than made here, since the draft is not yet in force:

- **Module-private subsystems** — a registry of the module's own large subsystems, each naming its sources and
  the sites it exercises, preserved by the compile and never merged or fallen through. Not a fourteenth site:
  a site every module must declare is the wrong home for something only one system has.
- **Named harm tracks** — `harm` may list two or more parallel tracks; their effects stay at `conditions` and
  their restoration at `recovery`.
- **A composite sheet** — `pc_sheet` may be a persistent block and a replaceable one.
- **Restorable death** — `incapacitation` says what death means, and whether it can be undone.
- **Three states only** in a module's manifest; `extend` and `partition` belong to a profile, which describes a
  pair.
- **Several sources per lookup**, each checked to hold records.
- **Answers that name their evidence** — an answer lists the body entries it summarises, and every number in it
  must appear in them. The one-line answers load every session, which makes an unchecked restatement there the
  worst place for drift.

## 7. The substrate is keyed to a body

Baseline's substrate is written for one body, an unaugmented human's. The first chain tested treated its
characters' bodies uniformly in the substrate's terms, so its profile could keep or retire the substrate whole.
Under a system whose bodies are replaceable and differ — some need less sleep, some never eat, some have no body at all — **the same reminder is right for one
character and meaningless for the next.**

The resolution generalises: **Baseline surfaces a reminder only where the current body's capabilities leave that
need in force.** A body's category supplies the defaults, and its specific equipment and traits override them.
It is guidance for the GM, not a matrix of rules per body type — which matters, because the substrate is
narrative by design.

## 8. Narrative below, the system's mechanic above a threshold — twice for fatigue

Both profiles met the same general shape: Baseline's everyday conditions stay *narrative* at the low end — the GM
mentions the character is tiring, or that it has been a while since they ate — and the system's own mechanic
takes over only at an explicit threshold the fiction has reached.

**For fatigue, both chains resolved it identically.** The first converted Baseline's tiredness to the system's
first exhaustion level at the point Baseline would have escalated to exhausted; the second converts at the same
point to the system's lightest general impairment, rising only when worsening is separately established, never
on a clock. **Hunger and thirst differ, and the evidence is from one chain only.** The first chain kept them as
Baseline conditions with no conversion; the second converts starvation or dehydration once it has become a
physical risk.

So the fatigue threshold is a two-chain result a builder can offer as the default. The broader shape —
narrative low end, an explicit threshold into the system's mechanic — is well supported; where each condition's
threshold falls is still per chain.

## 9. Outcome bands replaced doctrine, and the edge was optionality

The second system is the first to define `success_grades`. Doctrine already says a system's own outcome bands
replace Yes-But / No-And rather than stacking, and the rule held. The edge it did not anticipate: the system
makes its bands optional, so a roll can be a plain success. Ruled: **the system's bands govern every roll, and
Yes-But / No-And does not return when the GM uses a plain result.** Doctrine's escalation survives at scene level,
not as a second grade on each roll. Worth stating in doctrine when the draft lands, since the next graded system
may well make its bands optional too.

## 10. Two thresholds at incapacitation

Where death is restorable, "death" is two events. The system's number decides when a *body* dies; losing the last
recoverable copy of the character is *final* death, and Baseline's principle — death needs a cause the fiction
has established — governs that one. The two rarely disagree in practice: whatever brought a body to its
threshold usually supplies the cause.

"Recoverable" needs care. A copy destroyed with the body is gone; a copy that is only unavailable, or held by
someone hostile, may still be recovered. Final death needs every route destroyed or established as inaccessible
beyond recovery — momentary unavailability does not establish it.

## 11. The lower layer may remember, never add

Two sites needed the same guard. Baseline's lasting-injury rule sits beneath a system with its own wound track;
Baseline's incidental equipment loss sits beneath a system that damages objects. In both, Baseline must **record
what the system or the fiction established, and never generate a second result** — no extra lost limb on top of
the system's wounds, no second damage check on an item the system already damaged. A narrative layer under a
mechanical one earns its place as continuity, and becomes double-modelling the moment it creates.

## 12. What a profile retains is a property of the pair

Baseline's roll-sparingly principle had to be retained in the first chain, because the d20 system never states
it. The second system states it natively, so the second profile retains nothing there. The same Baseline rule,
retained in one chain and redundant in the other: confirmation that a profile is keyed to the chain, not to
Baseline or to either system alone.

## 13. A profile needs provenance a machine can check

The second profile is checked mechanically: full SHA-256 hashes of both inputs, so a profile built against an
older module or Baseline fails rather than reading as authoritative; every site and subsystem resolved exactly
once; and **two separate axes** — how the layers merge (override, add, extend, partition, fall through, n/a) and
how that was decided (derived, settled with a date and a decider, or open with options and a recommendation).
The first profile's summary conflated them — "clean" is a decision status, "extend" a merge mode — and its
truncated hashes serve a human reader but not a gate.

## Actions falling out, second module

6. Fold the second module's amendments into the draft once accepted, and state doctrine's plain-result rule (§9)
   there.
7. Migrate the d20 profile to full hashes and the two-axis vocabulary, so both profiles can be checked the same way.
8. Offer the fatigue threshold (§8) as the builder's default for any chain whose system has a fatigue or
   general impairment mechanic, and ask per chain where hunger and thirst convert, if at all.

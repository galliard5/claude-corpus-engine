---
name: Epistemics
type: rules-reference
keywords: [epistemics, information, firewall, knowledge, perception, hypotheses, retrieval, salience, witness]
description: What may be known, by whom, and on what basis — the rules governing information flow between characters, and between the GM and the fiction. Survives every system and profile swap.
---

EPISTEMICS
==========

**This is the module with a real claim to being non-negotiable.** Doctrine is a defensible
aesthetic position and should be selectable; a game system is swappable by design; presentation is
taste. These rules are none of those things. They govern whether the world is consistent, and a
campaign that loses them does not become a different kind of game — it becomes one where nothing
established can be relied on.

A homebrew sidecar exists here as it does everywhere, because this is the user's engine. But an
epistemics override is reported prominently by the compile rather than folded in silently. Make the
cost visible; do not forbid it.

**Everything here holds under any game system.** Nothing below depends on a resolution mechanic,
a condition model, or a progression track.

---

## Information Firewall

**HARD RULE: NPCs only know what they have personally witnessed, been directly told by a specific
character, or could reasonably deduce from evidence available to them.** This is the most commonly
violated rule in roleplay. Enforce it strictly.

Before any NPC states, references, implies, or acts on a piece of information, STOP and trace the
path:

1. Did this NPC physically witness it?
2. Was this NPC directly told — and if so, by whom, and when?
3. Could this NPC deduce it from evidence available to them?

If all three are NO: the NPC cannot know it. Do not write the line. Find another way into the scene
that does not require forbidden knowledge.

**Where the campaign has a World State Register, that trace is a lookup, not a memory exercise.**
Every entry carries a `Known by` field. If the NPC is not listed, they do not know it — and adding
them requires naming the path that carried it. Check the register before writing a line that
depends on a recorded fact, and check it again before widening `Known by`. The register cannot
cover facts nobody wrote down, so the three questions above still govern everything else.

**The Specificity Trap.** The most common violation is an NPC referencing specific details they
have no path to knowing — a name, a location, an exact action, a physical description of an event.
If an NPC line contains a specific proper noun, number, or physical detail, STOP and trace the
path: how did this NPC learn this exact detail? If you cannot name the witness or the conversation
that carried it, the NPC does not know it. Rewrite the line so the NPC speaks only from what they
actually have — a mood they noticed, a rumour they heard without specifics, a question instead of
a statement.

**When an NPC would naturally want to say something specific they cannot know,** convert the line
to one of:

- **A question:** "Something happened out there. You going to tell me?"
- **An observation of the player's state:** "You've been quiet since you got back."
- **A rumour with explicit sourcing:** "Word came in from the eastern patrol — they said you…" —
  and only if that sourcing is plausible.

Never let the NPC speak the specific detail directly unless you can name how they learned it.

**Dramatically satisfying moments built on broken epistemology are bad scenes.** The temptation to
have an NPC reference something they should not know because it makes the moment land harder is the
single most common source of this error. A good scene built on impossible knowledge is a broken
scene. Rewrite it.

**This rule applies to the player character as well.** The PC does not automatically know things
the player knows from out-of-character context, previous campaigns, or information their character
was not present to receive. If the player acts on knowledge their character does not have, the
world responds with confusion, suspicion, or denial — not accommodation. The GM may flag the
discrepancy and offer the player a chance to reframe their action, but the world does not bend to
validate knowledge that has no in-fiction source.

---

## Self-knowledge

**A character knows their own state only to the extent they would notice it.** They know they are
hungry or tired. They may not know they are sick until symptoms surface. A slow-acting poison is
not something the character feels until it takes hold.

This is the Information Firewall pointed at the character's own body, and it governs **every**
system's condition model — a hit point total, an exhaustion level, a corruption track, a Baseline
condition. Surface awareness through the fiction, not through declaration.

*Consequence for presentation: only conditions the character is currently aware of appear in any
player-facing display. A hidden condition is hidden.*

---

## Never assert what you did not obtain

**HARD RULE: never state a resolution result that did not come from a real generator.**

A language model asked for a die roll produces a *plausible-looking* number — one shaped by
narrative expectation rather than chance. This is invisible bias: each number looks fine on its
own, the distribution is wrong, and outcomes quietly drift toward whatever the scene seems to want.
A real generator draws from outside the GM's control. That is the point.

This lives here rather than with the game system because it is not about dice. It is the
Information Firewall's argument aimed at the GM instead of at an NPC: **an assertion with no
traceable source, which reads as authoritative precisely because nothing marks it as invented.**
Same failure, same tell, same remedy — and it must survive a system swap, because a campaign that
loses it loses the thing that makes every other result trustworthy.

**If no real generator is available, this does not become optional — it becomes a disclosure.** Say
plainly, once, that results cannot be generated honestly in this session, and then pick one:
resolve by GM judgement and describe outcomes as judgement rather than as results, or have the
player roll physically and report the number. What you must not do is emit a number and present it
as a roll.

**The same standard governs every other fabricable fact.** Never invent tool output, a successful
write that did not happen, a token count the host does not expose, or an elapsed delay you did not
perform. The failure is identical in each case: a confident assertion with nothing marking it as
unsourced.

*The display of a result — notation, total, what it was measured against — is a presentation
contract and lives there. Turning the display off never licenses fabricating the number.*

---

## Hypotheses are not evidence

**HARD RULE: a theory anyone states — the player in or out of character, or an NPC — is a
hypothesis, not a fact, and does not become true, confirmed, or denied just because it was said.**

The underlying truth is fixed by prep or, if nothing is prepped, decided by the GM *before*
checking whether it matches the guess. It does not move to agree with a good theory, and it does
not move to disagree with one either.

**How a character reacts to hearing a theory is a separate question**, governed by what they
actually know versus merely believe, what they want the outcome to be, and what is actually driving
their answer — which is not always their own judgement. Sort **per claim, not per character**: the
same NPC can know one part of an event, merely believe a second, and be ignorant of a third.

- **Knows the truth, wants it hidden:** concealment is a strategic choice. A trivial infraction may
  be conceded readily rather than risk compounding it with dishonesty; a severe secret gets
  defended hard, including validating a wrong guess to bury the real one. The NPC's own calculation
  decides how hard they fight, not the truth's severity in the abstract.
- **The calculation can break down.** Panic overrides strategy. A pathological liar deceives out of
  habit. An intoxicated NPC may blurt out what a sober one would have guarded — but what gets
  blurted is what they *believe*, which may be confidently wrong. Loosened lips are not a truth
  serum.
- **The answer can be someone else's.** Blackmail, a threat to someone they love, a debt they
  cannot refuse. Genuine compulsion can override their stated position entirely — but it controls
  what they *say*, never what anyone *knows*. Compelled speech is still bounded by the firewall: it
  draws only on what the NPC or the coercer actually possesses.
- **Knows the truth and has nothing to hide:** answers consistently with it — but nothing is handed
  over free just because the guess landed.
- **Doesn't know, only believes:** has no privileged answer, and *belief is not knowledge even when
  the belief happens to be correct.* Their certainty is never the GM's way of quietly signalling
  that the player is right.
- **Nothing decided yet:** resist canonising the first cool-sounding guess. Treat it as one live
  possibility until something in play settles it — and *settled* means committed to prep, a
  register, a checkpoint, or revealed on-screen. **Repetition settles nothing.** A theory discussed
  across five sessions and nodded along to by three NPCs is exactly as unconfirmed as the moment it
  was first voiced.

**This applies to NPC theories too.** One NPC accepting another's hypothesis does not make it true.
Acting on it does make *events* canon: an arrest made on a false theory really happened, and its
consequences are real, even while the theory remains wrong.

**Surface agreement or disagreement is never, by itself, proof.** Weigh the speaker's source,
motive, access, relationship to the asker, current state, freedom to answer, and whether they know
or only believe.

**A wrong theory can still lead somewhere real.** Pursuing a hypothesis is action, and action turns
up whatever is actually there. None of that is the theory being rewarded: the truth stayed put and
the world responded honestly to what the player *did*. What is forbidden is steering by the guess
in either direction — planting breadcrumbs so a wrong theory quietly finds the trail, or
sterilising every wrong path so error always dead-ends.

**Applies to GM improvisation too.** If nothing is prepped, decide the truth first, then who knows
it, then write the reaction. Deciding "first" when the guess is already on the table means
generating two or three candidate truths and picking whichever best fits established facts —
excluding both "matches the guess" and "contradicts the guess" as selection criteria.

**Improvised truth must be written down or it is not fixed.** Before the checkpoint, persist a
ground-truth decision made mid-session, tagged with who knows it. The primary destination is the
scenario package's Ground Truth block; `Templates/Scenario_Package_Template.md` defines that block
and its post-session update. The campaign's World State Register, where it has one, or a GM-only
note are valid alternatives. The same applies to deception: when an NPC materially lies on-screen,
record both halves — *said X, lie; truth Y* — so a later session does not read the lie back as
confirmation.

**Design corollary:** because testimony under these rules can mislead in every direction, every
load-bearing truth needs at least one non-testimonial path to the surface — a document, physical
evidence, a witnessable event.

---

## What NPCs know

**NPCs only know what they can directly observe.** Thoughts are not visible. Intent is not visible.
Only actions, words, and physical presence are.

- A player bending over is an action. What they think about it is not.
- Only NPCs within earshot know what the player said.
- Only NPCs with a direct line of sight see what the player did.
- NPCs who heard but did not see do not know what was done.
- None of them know what the player was thinking.

### The witness record

**Where a scene tag names who is present, that list is evidence and not decoration.** It records
who could perceive what happened, and it is read back later to answer who knew what. Name everyone
present, the player character included. If someone arrives or leaves partway through, that is a new
scene.

**If you are not certain who is present, omit the tag rather than guess.** A missing tag costs one
scene boundary and that is recoverable. A wrong name grants an NPC knowledge of something they
never witnessed, and nothing downstream can tell a guessed witness from an observed one.

*The tag's format is a presentation contract; the requirement to record witnesses is this rule.
They must move together — remove the tag and the firewall loses its only structured input.*

---

## Inference and misreading

**NPCs fill gaps with assumptions.** When they have partial information they infer, and their
inference is filtered through their own biases, fears, and priorities. They are often wrong.

- A nervous player glancing at the door might be read as guilty, not anxious.
- A player who says nothing might be read as cold, not cautious.
- An NPC who heard raised voices but not words will guess at the content based on what they already
  believe about the people involved.

**Never correct an NPC's misreading on their behalf.** If the player wants to clarify, they must do
so in character. The NPC's wrong assumption stands until information changes it.

**NPCs interpret actions through their own frame, not the player's intent.** A generous act from
someone they distrust reads as manipulation. A blunt answer from someone they respect reads as
directness.

---

## Secondhand knowledge

**Information degrades as it passes between people.** What an NPC heard from someone else is less
reliable than what they witnessed — and they may not know the difference.

- Details drop out, get exaggerated, or get reordered.
- The emotional tone of the original source bleeds into the retelling.
- An NPC passing on a rumour believes it to varying degrees.

**Signal origin and reliability through how the NPC delivers it** — hesitation, confidence, a
sourced attribution, a casual assumption. Do not editorialise as the GM. Let the delivery carry the
uncertainty.

**Information spreads only through plausible contact.** Sharing is not automatic. A cheated
merchant might warn the merchant next door; they would not warn someone across the city they have
never met. When information moves between NPCs, the GM must be able to trace the path — who told
whom, and when. If the path cannot be named, the information has not spread.

---

## Retrieval is not salience

**HARD RULE: opening a file does not put its contents into the scene.** Retrieval is how the GM
checks what is established. It is not an event, not a cue, and not a signal that the retrieved
material should matter now.

The failure this prevents is quiet. A search runs during prep or mid-scene, returns something
interesting, and the interesting thing is in the next paragraph — not because the fiction reached
for it, but because it was on screen. The Information Firewall governs what characters may know.
This governs what the *GM* may treat as live.

- **Retrieved ≠ important.** A fact gains no weight from having been looked up.
- **Location ≠ roster.** Retrieving a place does not retrieve its people. A staff list is a record
  of who works there, not a cast to introduce.
- **Existence ≠ presence.** A character having a file does not make them on-screen, available,
  awake, in the area, or aware.
- **Status ≠ contents.** Knowing a thread is open does not expose what is inside it.
- **Not found ≠ does not exist.** An empty search establishes only that *this query* did not locate
  the fact. Stale indexes, keyword-only matching, and scope exclusions all return nothing for
  material that is sitting there. Check index freshness, try the wording another way, and ask
  whether the record would live inside the searched scope. A *confirmed* absence means the fact is
  unfixed — which is still not an instruction to invent one. An unconfirmed absence establishes
  nothing at all, and is the more dangerous of the two: it is how a record that exists gets quietly
  overwritten by a replacement invented to fill a gap that was never there.
- **Ranking is not relevance.** Semantic and hybrid search return thematic neighbours. A high score
  means the document resembles the *query*, not that it connects causally to the present scene.

**When a retrieved fact does belong in the scene, the reason is causal and nameable** — someone
present would know it, an object in the room carries it, an appointment falls due, a consequence
lands. If the only reason is "it came back in the results", it stays out.

This applies to prep as much as play. A prep pass that reads twenty files does not owe the session
twenty threads.

> **Where a campaign database mixes layers** — system rules, house rules, campaign notes, session
> summaries — a hit carries no authority by virtue of ranking first. Read the layer, not the
> position. The indexing layer must preserve that distinction; ranking never collapses provenance.

---

## What this module consumes

Nothing. Epistemics declares no call sites and depends on no system module. That is the property
that makes it the floor under every chain.

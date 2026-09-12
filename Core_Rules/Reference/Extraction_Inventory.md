# Extraction Inventory

Passage-by-passage sort of the material destined for `Baseline`, plus everything that turns out
**not** to belong there. Line numbers refer to the pre-cutover sources
`filesystem/Core_Rules/core_rules.md` as of 2026-09-07 (1,214 lines) and
`Core_Rules/Skill_Trees.md` (286 lines). Both paths retire at cutover and remain available in Git
history; they are historical anchors here, not live routes.

This is the pass where the boundary gets drawn. Nothing is rewritten yet.

**Destinations:** `SYS` Baseline · `DOC` GM doctrine · `PRES` presentation · `EPI` epistemics ·
`OPS` operating procedure

Rows marked **⚑** are argued in *Flagged for decision* below rather than settled here.

---

## The headline finding

**Roughly half of what reads as "game mechanics" is not system material.** Section 5 in particular
is mostly doctrine wearing mechanics' clothes — of its ~185 lines, the parts that a d20 module
would actually replace are dice notation, contests, the harm bullets, and looting. Everything else
holds regardless of which system is loaded.

That is good news for the split and bad news for anyone estimating it by line count. The work is
not moving five sections into a new file; it is separating four kinds of material that are
currently interleaved at paragraph level, and occasionally inside a single bullet.

---

## Section 5 — Consequences & Outcomes (260–445)

| Lines | Passage | → | Call site | Note |
|---|---|---|---|---|
| 263 | Core directive — the world does not wait, let things go wrong | DOC | — | Pacing/consequence philosophy. Survives every system swap. |
| 269–278 | No-RNG-tool disclosure block | OPS | — | Depends on which servers are connected. The *principle* inside it is not OPS — see ⚑1. |
| 280–282 | Never state a die result you did not receive, and why | ⚑ EPI | — | ⚑1 |
| 284 #1 | Tool or nothing | ⚑ EPI | — | ⚑1 |
| 284 #2 | Roll before narrating, never back-fill | DOC | — | A rule about honest sequencing, not about dice. |
| 284 #3 | First result stands; re-roll needs in-fiction cause | DOC | — | Holds under any resolution system. |
| 284 #4 | Show the roll — notation, result, what it was measured against | PRES | — | Pure rendering contract. ⚑2 |
| 284 #5 | Hidden rolls conceal the number, never the mechanism | DOC + PRES | — | Split: the principle is doctrine, the display half is presentation. |
| 284 #6 | Don't roll what doesn't matter | SYS | `difficulty` | When uncertainty is worth resolving is system-specific. |
| 293 | Notation table (`2d20kh1`, `4dF`, `5d10>7`, …) | SYS | `resolution` | Already system-agnostic; see *Manifest implications*. |
| 295 | Heavy arithmetic goes to a CAS | OPS | — | Tool routing. |
| 299–305 | Failure Rules — failure is a harder situation, no last-minute rescue | DOC | — | |
| 309–320 | Outcome Framework — Yes-But / No-And | DOC | `success_grades` | Doctrine default; a system declaring its own bands replaces it. |
| 326 | Contests — weigh skill, size, status, equipment, numbers, terrain | SYS | `contest` | |
| 326 (last sentence) | "Let the disparity be visible" | DOC | — | Narration instruction inside a mechanics paragraph. |
| 328 | Skill-tree tiers change what is *possible* in a contest | SYS | `progression` | Undeclared cross-reach — see *Consumption set*. |
| 330–332 | Choice points mark momentum shifts, not individual actions | DOC | — | |
| 334 | Decisive capabilities override general balance | SYS | `contest` | |
| 336 | Capstone nodes as decisive capabilities | SYS | `progression` | |
| 342–346 | COMBAT — wounds heal slowly, fights cost, defeat ≠ game over | SYS | `harm` | |
| 346 | Permanent results logged to the sheet immediately | SYS + OPS | `pc_sheet` | The *what* is system; the *log it now* is procedure. |
| 348–351 | SOCIAL — NPCs remember specific offenses, reputation spreads | DOC | — | Duplicates S7 NPC Memory; see ⚑5. |
| 353–355 | NEGLECT — ignored problems worsen | DOC | — | |
| 357–359 | TIME — travel and recovery cost time, factions advance | DOC | — | |
| 365–367 | Items do not survive combat by default; this matters tactically | SYS | `equipment` | |
| 371–377 | Damage categories — AoE, standard, clean hits | SYS | `equipment` | |
| 383–389 | Item-type risk table | SYS | `equipment` | |
| 395–407 | GM guidance — when to check, severity scaling, scarcity, organics | SYS | `equipment` | |
| 413–419 | Persuasion — some NPCs cannot be persuaded; leverage; failure raises resistance | DOC | — | ⚑3 |
| 421 | Social-tree nodes inform what can be attempted | SYS | `progression` | |
| 427–436 | World Progression — advance factions between scenes | DOC | — | |
| 442–444 | Proportionality — match consequence to action, let wins feel earned | DOC | — | |

## Section 6 — Status Conditions (448–576)

| Lines | Passage | → | Call site | Note |
|---|---|---|---|---|
| 451 | Statuses are internal, expressed through behaviour and NPC reaction, never announced | DOC | — | Holds for a d20 exhaustion track equally. |
| 453 | Only visible if the character would be aware; a slow poison is not felt until it takes hold | EPI | — | The Information Firewall pointed at the character's own body. |
| 455 | The list is non-exhaustive; track anything that matters | SYS | `conditions` | |
| 459–477 | The nine named statuses with resolution conditions | SYS | `conditions` | |
| 481–491 | Urgency — immediate / short-term / gradual, and escalation | SYS | `conditions` | |
| 495–507 | Daily accumulation — conditions from ordinary activity | SYS | `conditions` | |
| 511–513 | Compounding — statuses stack and lower the threshold | SYS | `conditions` | |
| 517–519 | Persistence — resolve only through specific in-world action | SYS | `recovery` | |
| 521–523 | Long-duration conditions logged to the sheet with onset date | SYS + OPS | `pc_sheet` | |
| 531–547 | In-game time display, precision matched to the scene | PRES | — | |
| 549–558 | Status block format and placement before the choice options | PRES | — | |
| 560–571 | Scene tag — format, forward-looking, only at transitions | PRES | — | |
| 573 | The names after the dash are a witness list, read back as evidence of who knew what | EPI | — | ⚑4 |
| 575 | If uncertain who is present, omit rather than guess | EPI | — | A wrong witness is unrecoverable; a missing one is not. |

## Skill_Trees.md (286 lines)

Almost entirely one call site. Sorted at coarser grain because the exceptions are what matter.

| Lines | Passage | → | Call site | Note |
|---|---|---|---|---|
| 16–35 | When to use / skip / partial use | SYS | `progression` | |
| 37–45 | Core principle — skills recognised retrospectively, no roll bonuses | SYS | `progression` | |
| 47–74 | Tree types, discovered-tree naming | SYS | `progression` | |
| 79–98 | Branch structure, splitting | SYS | `progression` | |
| 93, 231 | `visualize:show_widget` named as an available fact | OPS | — | Literal tool name, host-specific, no fallback. ITEM 1's fix list. |
| 103–111 | Tier table and unlock requirements | SYS | `progression` | |
| 119–163 | Foundation archetype nodes; Essence | SYS | `progression` | |
| 171–176 | Use marks — GM tracks silently, player does not see them | SYS + ⚑ PRES | `progression` | ⚑6 |
| 180–200 | Narrative gates, discovered-tree initialization, starting nodes | SYS | `progression` | |
| 206–223 | GM rules — naming constraints | ⚑ | `progression` | ⚑7 |
| 229–276 | Tracking format — the text skill block | PRES | — | |
| 282–286 | Cross-setting portability | SYS | `progression` | |
| 12, 161, 188 | "Recorded in the project profile" | OPS | — | Campaign configuration, not rules. |

---

## Flagged for decision

Seven. The first is the most consequential and the rest are cheap.

### ⚑1 — Is "never fabricate a roll" epistemics or doctrine?

The dice-integrity rules (280–282, 284 #1) are the strongest passage in Section 5 and they are
**not about dice.** They say: do not assert a number you did not obtain, because a fabricated one
looks fine individually while the distribution quietly bends toward whatever the scene wants.

That is the Information Firewall's argument applied to the GM instead of to an NPC — an assertion
with no traceable source, which reads as authoritative precisely because nothing marks it as
invented. Same failure, same tell, same remedy.

**Recommendation: epistemics.** It then survives every system swap and every profile, which is
what you want from a rule whose whole job is preventing a specific kind of confident fabrication.
The notation table and the when-to-roll threshold stay in `SYS`; the *don't make it up* rule goes
where the other don't-make-it-up rules already live.

Consequence worth naming: epistemics gets a homebrew sidecar like everything else, so this becomes
overridable. That is the case the interface draft already handles by reporting epistemics
overrides prominently rather than folding them in silently.

**Settled 2026-09-11 — epistemics.** Confirmed from a second direction: Baseline is the layer a
loaded system overrides, so anything filed there is at risk of vanishing under a d20 campaign.
Losing "never assert a number you did not obtain" that way would be severe and silent.

### ⚑2 — "Show the roll" is presentation, which means a system can't hide it

Rule #4 is a rendering contract: notation, result, target, visible to the player. Filed under
`PRES` it becomes subject to the presentation homebrew — a user could switch to narrated results
with no numbers shown.

That is probably correct and worth doing deliberately rather than by accident. Note the
interaction: ⚑1 keeps the *integrity* rule in epistemics, so turning off the display does not
license fabricating the number. Good separation — one governs what is true, the other what is
shown.

### ⚑3 — Persuasion is doctrine, but it currently reads as a mechanic

413–419 contains no mechanics at all: some NPCs cannot be persuaded, persuasion requires leverage,
failure raises resistance, implausible attempts fail. All four hold under a d20 social skill check
and under a system with no social mechanics whatsoever.

**Recommendation: doctrine,** with `contest` supplying the roll when a system defines one. The risk
if it goes to `SYS`: load a d20 module and these four rules silently vanish, leaving a GM that can
be talked into anything by a good argument. That is exactly the LLM-GM failure mode the rules exist
to fight.

**Settled 2026-09-11 — doctrine.** Same argument as ⚑1, and the clarification that Baseline is a
backdrop meant to be overridden makes it sharper: the override is the normal case, not the edge
case, so anything that must not be lost cannot live there.

### ⚑4 — The scene tag splits, and half of it is load-bearing

Format is presentation. The *witness list* is epistemics — 573 says the names are read back later
as evidence of who knew what, which makes it an input to the Information Firewall rather than
decoration.

Move the format to presentation and the requirement to record witnesses to epistemics, and
cross-reference. Move them together into presentation and a user who homebrews the scene tag away
silently removes the firewall's only structured input.

### ⚑5 — Section 5's SOCIAL bullets duplicate Section 7

348–351 (NPCs remember offenses, reputation spreads, doors close) restates NPC Memory at 712–721
almost exactly. Both are doctrine, so there is no boundary question — but the split is the moment
to collapse the duplicate rather than carrying it into two modules.

Keep the S7 version, which is fuller and already sits with the traceable-contact rule at 721.

### ⚑6 — "The player does not track use marks" is two rules

171–176 says the GM tracks marks silently and the player does not see them. The *tracking* is
system; the *silence* is a presentation choice, and arguably an epistemics one — it withholds
state from the player deliberately.

Low stakes either way. Suggest: system owns the mark economy, presentation owns whether marks
surface, defaulting to hidden.

### ⚑7 — The node-naming rules are craft advice inside a system

206–223 tells the GM how to name a node: name what the character does not what they are, make it
specific enough to be wrong sometimes, proper nouns at Tier 4. These are *writing* instructions —
they belong to the same family as the Section 1 style rules.

But they are meaningless without this progression system, since no other system names nodes.

**Recommendation: keep in `SYS`**, and accept that a system module may carry craft guidance
specific to its own machinery. The alternative — doctrine holding naming advice for a system that
may not be loaded — is worse. Worth stating as a general principle in the interface spec: *craft
advice travels with the mechanism it serves.*

---

## Consumption set, confirmed

Three undeclared reaches from doctrine into `progression`, each buried mid-paragraph, exactly as
ITEM 1 predicted:

| Source | Line | Reach |
|---|---|---|
| Contests | 328, 336 | Tier changes what outcomes are possible; capstones as decisive capabilities |
| Persuasion | 421 | Social nodes inform what can be attempted and what the GM surfaces |
| NPC combat behaviour | 667 | PC's Body/Edge/Essence nodes shape combat narration |

All three break silently if a module marks `progression: none` — no error, just doctrine
referencing a system that is not loaded. This is the concrete case for the declaration.

---

## Manifest implications for Baseline

What the sort implies Baseline actually answers. Four sites have no home in the current rules,
which is itself a finding.

| Call site | State | Source |
|---|---|---|
| `resolution` | `defined` | 293 notation |
| `difficulty` | `defined` | 284 #6 — thin; "uncertainty with stakes", no scale |
| `success_grades` | `absent` | Inherits doctrine's Yes-But / No-And |
| `contest` | `defined` | 326–336 |
| `harm` | `defined` | 342–346 |
| `conditions` | `defined` | 455–513 |
| `recovery` | `defined` | 517–519 |
| `incapacitation` | `defined` | 345 — *"capture, retreat, injury, or loss"*. Narrative but real. Only the **death threshold** is undefined; 301 says the player can be killed and never says when |
| `resource` | **`none`** | No depletable pool exists, and a rules-light narrative system reasonably has none |
| `progression` | `defined` | `Skill_Trees.md`, and optional per campaign |
| `equipment` | `defined` | 363–407 |
| `pc_sheet` | `defined` | `Core_Rules/Templates/Character_Sheet_Template.md` |
| `npc_statblock` | `defined` | Same template — behavioural, barely mechanical |

**One genuine gap, not two.** An earlier version of this table called `incapacitation` missing.
It is not — 345 answers it narratively, and I read past it looking for a mechanical threshold. What
is actually undefined is the *death* boundary alone, which is a smaller and more tractable
question.

`resource` is the real absence, and `none` is the right declaration rather than an admission:
it tells a later compile that Baseline supplies nothing there deliberately, where silence would
leave it guessing.

`difficulty` is thin rather than missing. 284 #6 gives a threshold for *whether* to roll and never
a scale for *how hard*. Decide during extraction whether Baseline gains a difficulty ladder or
states that the GM sets it case by case — the latter fits the system's character better.

## Substrate and crunch

Baseline has two jobs and they pull in different directions. It is the **everyday substrate**
underneath a crunchier system — hunger, fatigue from a day in the saddle, whether gear survived
the fire, none of which published systems model — and it must also be **thorough enough to run
standalone**.

That resolves into an asymmetry, which is the shape the draft should have:

| Class | Sites | Baseline's posture |
|---|---|---|
| Substrate | `conditions`, `recovery`, `equipment` | **Thorough.** Nothing else supplies these, and they stay live under any system that declares them `absent` |
| Crunch | `resolution`, `difficulty`, `harm`, `incapacitation`, `resource`, `progression` | **Deliberately thin.** Enough to play standalone; a loaded system replaces them anyway |

**The trap this exposes** — and it is why the interface gained an adaptation pass. Load order says
later wins, so a d20 module marking `conditions: defined` (it has hit points and an exhaustion
track) overrides Baseline's conditions *wholesale*, deleting hunger, thirst and daily accumulation
— the exact material Baseline exists to supply. Nothing reports it, because from the manifest's
point of view that is a clean override.

The fix is not finer call sites, which would require guessing in advance where each system's
boundary falls. It is the adaptation pass: the compile compares both rules bodies and asks first
*what does the lower layer cover that the upper does not mention at all*, persisting the answer per
system pair. The shipped interface and compiler must make this adaptation pass explicit rather than
silently applying later-wins precedence.

---

## Next

1. ~~Resolve ⚑1 and ⚑3~~ — **settled 2026-09-11**, both out of Baseline: dice integrity to
   epistemics, persuasion to doctrine. ⚑2, ⚑4–⚑7 are cheap and can be settled while drafting.
2. Draft `Game_Systems/Baseline/baseline.md`: manifest from the table above, body from the `SYS`
   rows, thorough at the substrate sites and thin at the crunch ones.
3. Hold the `DOC` / `PRES` / `EPI` rows — they are the input to the other four modules and should
   not be rewritten until Baseline proves the interface.

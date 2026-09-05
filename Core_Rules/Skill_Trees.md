---
name: Emergent Skill Tree System
type: rules-reference
keywords: [rules, skills, progression, pc, character development, trees, nodes]
description: Optional character progression system for PCs built around emergent narrative development rather than pre-set advancement paths
---

EMERGENT SKILL TREE SYSTEM
===========================

**Visual reference:** there is no static system diagram on disk. Generate one on demand with
`visualize:show_widget` using Mermaid — tier structure, branches, and a character's current
progression all diagram cleanly, and a generated view never goes stale.

OVERVIEW — WHEN TO USE THIS SYSTEM
====================================

This system is optional. Not every campaign or PC benefits from it.

**Use it when:**
- The PC is genuinely new to their capabilities — a blank slate who will grow through play
- Transformation, augmetic conversion, or soul-transfer creates a meaningful reset
- The campaign has a development arc where capability change is a core theme
- The setting rewards tracking what a character has earned through experience

**Skip it when:**
- The PC begins with deep prior experience that predates the campaign
- The campaign is primarily social and political in structure, where consequences and relationships carry the dramatic weight
- The fiction doesn't support a meaningful distinction between what the character can and cannot do at a given tier

**Partial use:**
Some campaigns may justify a single discovered tree or a limited skill block without the full six-archetype foundation. A campaign centred on an estate crisis might generate situational Craft or Social branches reflecting what the PC is navigating, without needing a full character tree. Apply the system where it earns its place and leave it out where it doesn't.

*Per-campaign judgements for the current project are recorded in the project profile.*


CORE PRINCIPLE
==============

A character's skill trees are a map of what they have *become*, drawn in retrospect. Nothing above Tier 2 exists until the fiction creates it. Some trees don't exist at all until the character stumbles into them.

Skills are not chosen. They are recognized — by the GM, after the fact, as a description of something the character has demonstrably become through repeated action and meaningful experience.

The mechanical effect of advancement is always narrative: higher tiers don't add bonuses to rolls. They change what outcomes are *possible*, what information the GM surfaces, what choice options appear, and how NPCs read and respond to the character.


TREE TYPES
==========

FOUNDATION TREES
----------------
Six archetypes present on every character sheet from the start, even at zero development. They represent the broad domains of human (or non-human) capability.

    BODY     MIND     SOCIAL     CRAFT     EDGE     ESSENCE

Foundation trees begin developing as soon as the character uses them meaningfully. Most characters will have uneven development — a few trees well-developed, others untouched.

DISCOVERED TREES
----------------
Unlocked through fiction. They do not exist on the character sheet until the moment of discovery. After that they follow the same structure as foundation trees, beginning at Tier 1.

What might generate a discovered tree:
- First genuine engagement with a magic discipline, fighting tradition, or knowledge system the character had no prior exposure to
- Undergoing transformation, augmetic conversion, or soul binding
- Deep immersion in a system of knowledge with its own internal logic: a specific alchemical school, a religious practice, an institutional methodology, a criminal craft
- Extended contact with a radically different culture or discipline that produces new capability rather than merely new knowledge

The tree is named at the moment of discovery, collaboratively between GM and player. It belongs to this character's experience of it — not to the world's taxonomy.

Examples:
- A character who first uses a witch's green-flame magic doesn't unlock "Pyromancy." They unlock "Green Flame" or "The Witch's Fire" — whatever name comes from inside the experience.
- A PC undergoing a transformation programme doesn't unlock "Transformation." They unlock a name drawn from their specific change — often the donor's name, or the form's.
- A soul trapped in a gem who begins learning to shape their internal architecture doesn't unlock "Soul Magic." They unlock "Ring Work" or "The Lattice" — the name is theirs.


BRANCH STRUCTURE
================

Within any tree, multiple branches can develop in parallel. A branch is a line of connected nodes running from the root toward a potential capstone. There is no designed limit on how many branches a character can develop within a single tree — the limit is time, use, and the fiction providing the gates.

    TREE
     │
    T1 ── Root Node (universal)
     │
    T2 ── [Branch A begins]     [Branch B begins]     [Branch C begins]
     │           │                     │                     │
    T3 ──  [Named Node]          [Named Node]           [Named Node]
     │           │                     │                     │
    T4 ──  [Named Node]          [Named Node]           [Named Node]
     │           │                     │                     │
    T5 ──  [Capstone]            [Capstone]             [Capstone]

**Visualization:** Tree structure, branches, and tiers diagram cleanly in Mermaid. Use `visualize:show_widget` with Mermaid code to display a character's current tree state, active branches, and progression toward capstones.

Branches within the same tree can connect. A node in Branch B might require a node from Branch A as a prerequisite — this happens when the fiction supports it. Cross-branch prerequisites are not designed in advance; they emerge when it is narratively true that one capability depends on another.

Branch splitting occurs when the GM observes a character using a Tier 2 node in two consistently different ways across multiple sessions. That divergence is the signal. The GM proposes the split, the player confirms, and Branch B initializes at Tier 2 with use marks carrying over from how it's been developing.


TIERS
=====

| Tier | Label      | Unlock Requirement                                              |
|------|------------|-----------------------------------------------------------------|
| 1    | Root       | 3 use marks — no gate required                                  |
| 2    | Practiced  | 3 use marks — no gate required                                  |
| 3    | Specialist | 3 use marks + minor narrative gate                              |
| 4    | Defined    | 3 use marks + significant gate — node named after the gate      |
| 5    | Capstone   | Fiction only — GM-recognized, cannot be scheduled or requested  |

Tiers 1 and 2 use generic labels (e.g. "Combat Form I", "Combat Form II"). From Tier 3 onward every node receives a specific name — after the character, the moment, the method, or the person the capability came from. The name is part of the advancement.


FOUNDATION ARCHETYPE NODES (UNIVERSAL ROOTS)
=============================================

These are the Tier 1 entry points for each foundation tree. They represent any serious practitioner's baseline — competence without distinction.

BODY
- Combat Form I — trained fighting technique: discipline, positioning, economy of motion
- Conditioning I — raw physical capacity: strength, endurance, recovery, pushing limits
- Endurance I — absorb punishment, sustain effort, keep functioning under physical stress

MIND
- Perception I — notice what others miss: exits, inconsistencies, environmental wrongness, tells
- Knowledge I — recall and apply learned information: lore, precedent, technical detail
- Focus I — maintain concentration under pressure: resist panic, pain, interference, and strain

SOCIAL
- Presence I — project authority and be taken seriously without demanding it
- Read I — understand the gap between what's said and what's meant; track what people want and fear
- Connection I — maintain and leverage relationships; know who to ask and be owed something by them

CRAFT
- Making I — build, repair, and jury-rig physical objects
- Formulation I — produce compounds, preparations, or materials: alchemy, herbalism, trade goods
- Systems I — understand how things work: logistics, economics, institutional machinery, mechanisms

EDGE
- Survival I — function through bad conditions: exposure, deprivation, being hunted, nowhere to go
- Cunning I — unconventional thinking: improvised solutions, exploiting openings others don't see
- Stealth I — move and act without being noticed: physical concealment, blending in, erasing presence

ESSENCE
- Initialized at first transformation, augmetic binding, or soul event — see ESSENCE ARCHETYPE below


ESSENCE ARCHETYPE
=================

Essence is a foundation tree that functions differently from the other five.

For most characters it begins empty and inactive. It only initializes when the character undergoes something that changes what they fundamentally *are* — transformation, soul transfer, augmetic conversion, magical binding. At that moment Essence initializes exactly like a discovered tree: named at the moment of change, Tier 1 awarded immediately without requiring use marks.

For characters who begin the campaign already transformed or altered, Essence begins initialized with nodes reflecting who they already were before play started.

Essence trees are the most personal in the system. Two characters who went through the same programme will have different Essence trees because they are different creatures who experienced it differently. The nodes cannot be meaningfully compared between characters even within the same setting.

What Essence becomes depends entirely on what happened to the character. A body transformation tends to produce branches around inhabiting the new form, translating unfamiliar senses into usable capability, and understanding the institution that performed the change. A soul bound into an object tends to produce branches around internal architecture, projecting awareness outward, and interfacing with external systems. A mechanical conversion tends to produce branches around chassis integration, managing the cognitive cost, and communicating through machinery.

These are starting points, not a taxonomy — name the branches from inside the character's experience. *Concrete per-setting starting points for the current project are recorded in the project profile.*

New settings: define Essence's initial branch during scenario creation, at the moment the transformation or binding occurs.


ACQUISITION RULES
=================

USE MARKS
---------
The GM tracks use marks silently. A mark is awarded when a node is applied in a situation where it meaningfully mattered — not routine activity, not background flavor. A mark is earned by:
- Applying the capability under genuine difficulty or pressure
- Producing a result that changes the scene
- Failing in a way that demonstrates the character was actually trying to use the skill

The GM may note marks in session summaries. The player does not track them — they are GM-side only.

NARRATIVE GATES
---------------
A gate is an in-world event that represents genuine growth — not repetition, but a moment where something changed. Gates must emerge from the fiction; the player cannot declare or request one.

Minor gate (required for Tier 3): a specific experience that shaped how the character uses this capability — a teacher, a significant failure, a situation that demanded something new. Does not need to be dramatic. A character might earn a Tier 3 Formulation node by spending a season working alongside an alchemist.

Significant gate (required for Tier 4): a moment the character cannot un-experience. It changed something. The Tier 4 node is named after this moment specifically — not after what the character can do, but after what happened that made them able to do it.

Major gate (required for capstone): the GM does not schedule this. The capstone is recognized when the character has been in a branch long enough that the fiction has started generating situations *around* the capability, rather than the capability simply responding to situations. The world has noticed. Other characters react to it. It has become a fact about the world, not merely a fact about the character.

DISCOVERED TREE INITIALIZATION
-------------------------------
When a character encounters something that might become a new tree, a two-step process:

Step 1 — Contact: The character is exposed to the thing. No tree yet. The GM notes the possibility.

Step 2 — First Use: The character actively engages with it in a meaningful situation. Success or failure doesn't matter — genuine attempt is enough. At this moment the tree is created, named collaboratively, and Tier 1 is awarded immediately. No use marks required for this first node — the act of discovery is the gate.

After initialization, the tree develops normally through marks and gates.

STARTING NODES
--------------
New characters may begin with up to 3 nodes at Tier 1 reflecting established background — no marks required. These represent who they already were before the campaign started. Characters with significant prior history (but for whom a skill tree is still appropriate) may begin with up to 3 nodes at Tier 2 as well, requiring GM sign-off.


GM RULES — NAMING
=================

When a Tier 3 or higher node is due, the GM names it using these constraints:

1. Name what the character *does*, not what they *are.*
   Not "Street Fighter" — "Dock Knife."
   Not "Patient" — "Patience."
   A trait is static. A practice is active.

2. Make it specific enough to be wrong sometimes.
   A well-named node implies contexts where it does not apply. "Dock Knife" is lethal at close range in tight spaces — it is not the right tool in an open field duel. Named nodes create real trade-offs as well as real strengths.

3. Proper nouns are encouraged at Tier 4.
   Locations, people, events. "The Merault Fight" tells you more about a character's history than "Advanced Counterattack" ever could. The name is a record of what happened.

4. The player can suggest.
   The GM decides, but if the player offers a name that is more specific and more true to how they play the character, use it. This is their character's history.

5. Capstones are offered, not announced.
   The GM does not say "you've unlocked your capstone." The moment is named afterward, in the fiction. The character does not know they have arrived somewhere final. The player does.


TRACKING FORMAT
===============

The skill block is recorded in a dedicated section of the character sheet, or in a linked Skill_Tree_Block file for campaigns where tracking is more active. See Skill_Tree_Block.md in Templates/.

For visual tracking of a character's skill trees and branch progression, use `visualize:show_widget` with Mermaid code to display the character's current tree state, active branches, and progression toward capstones. Diagrams can be regenerated any time to reflect new tiers, branches, or discovered trees as they develop.

Standard text format:

    ═══════════════════════════════════════════════════
    SKILLS — [CHARACTER NAME]
    ═══════════════════════════════════════════════════

    BODY
      Combat Form
        Branch A — [Branch Name, if named]
          T1 │ Combat Form I
          T2 │ Combat Form II
          T3 │ [Named Node]              [gate: brief description, Session ##]
          T4 │ —
          T5 │ —
        Branch B — [emerging]
          T2 │ [Node Name]               [emerging — # marks]

      Conditioning
          T1 │ Conditioning I
          T2 │ —

    MIND
      [etc.]

    ESSENCE
      [Tree Name]                        [initialized: brief description, Session ##]
        Branch A — [Branch Name]
          T1 │ [Tree Name] I
          T2 │ —

    DISCOVERED
      [Tree Name]                        [initialized: brief description, Session ##]
        Branch A — [Branch Name]
          T1 │ [Tree Name] I
          T2 │ —
      [none yet]

    ═══════════════════════════════════════════════════

Annotation key:
- `[gate: ...]` — records the narrative moment that unlocked this node
- `[emerging — # marks]` — branch forming, marks accumulated but gate not yet met
- `[initialized: ...]` — records when and how a tree first came into being
- `—` — node slot exists but is not yet developed


CROSS-SETTING PORTABILITY
==========================

Foundation trees transfer between settings fully. Body, Mind, Social, Craft, and Edge represent real capability that exists regardless of world. A character who appears in multiple settings carries these intact.

Discovered trees transfer if the thing that created them can exist in the new setting. A tree built around a specific magic system goes dormant if the character moves to a setting without compatible magic — annotated as `[dormant — no resonant system]` — and reactivates if they encounter something compatible.

Essence trees do not transfer. They are setting-specific records of what happened to the character in a particular world. If the character undergoes something in a new setting, a new Essence tree initializes alongside any prior ones. Old Essence trees are retained as history, annotated with their setting of origin.

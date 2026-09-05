---
name: Scenario Package Template
type: template
keywords: [template, scenario, package, operational, playbook, session-prep, handoff, runtime]
description: Template for the operational playbook that pairs with a Scenario file — explicit NPC logic, voice anchors, file references, and conditional responses for the runtime GM model
---

# Scenario Package: [Scenario Name]

**Companion Scenario File:** [[Scenario_Name]] *(narrative design — what the story is)*
**This File:** Operational playbook *(how to run it — paired with the Scenario file)*

**Campaign:** [[Campaign_Name]]
**Setting:** [[Location_Name]]
**In-Game Date Range:** [Start Date] to [Estimated End Date]
**Created By:** [Designer model — typically the planning instance] | [Creation Date]
**Runtime Target:** [Runtime model — typically the play instance]

---

## Quick Orientation

[3-5 sentences: What is this scenario about? What is the PC's situation? What is the central tension? What should the GM be tracking?]

---

## Files to Load by Scene

**Opening Scene / Default Load:**
- Core_Rules/core_rules.md — GM engine: NPC voice rules, consequences, status conditions, pacing, contests
- Core_Rules/Skill_Trees.md — if the Emergent Skill Tree System is active for this campaign
- [[PC_Character_Sheet]]
- [[Primary_Location]]
- [[NPC_1]], [[NPC_2]], [[NPC_3]]
- [[Relevant_Faction]] (if applicable)

**Scene: [Scene Name or Trigger]**
- [[Additional_NPC]]
- [[Secondary_Location]]
- [Why: brief note on why these files matter here]

**Scene: [Scene Name or Trigger]**
- [[Additional_Files]]
- [Why: brief note]

[Repeat for each major scene or location transition. The goal is that the runtime GM never has to guess which files to read — the package tells it.]

---

## NPC Operations Guide

For each major NPC in the scenario, provide an operational profile that the runtime GM can reference during play. This is NOT a replacement for the full character file — it's a quick-reference decision engine. Pair with the character's sheet (top of their character file, loadable via `read_text_file` with `head=` set to the file's `sheet_end_line` value) for token-efficient runtime loading.

### [NPC Name] — [Role/Title]

**Voice Anchor:**
- Quirk 1: [Specific speech pattern — e.g., "Starts every response with a question"]
- Quirk 2: [Specific speech pattern — e.g., "Never uses contractions"]
- Sample line (neutral): "[Example dialogue in their natural voice]"
- Sample line (stressed): "[Example dialogue when pressured or emotional]"
- Sample line (warm): "[Example dialogue when comfortable or friendly]"

**Core Motivation:** [One sentence — what drives this NPC right now in this scenario?]

**Behavioral Logic:**
- Default stance toward PC: [Warm / Neutral / Guarded / Cold / Hostile] — because [reason]
- What shifts them positive: [Specific actions or words from the PC]
- What shifts them negative: [Specific actions or words from the PC]
- Hard line (will not cross): [Something this NPC absolutely will or won't do]

**Conditional Responses:**
- IF [player action/event] → [NPC reaction and reasoning]
- IF [player action/event] → [NPC reaction and reasoning]
- IF [player action/event] → [NPC reaction and reasoning]

**Canon Traps:**
[Things the runtime GM might improvise that would contradict established lore. Be specific.]
- ⚠️ [e.g., "This NPC does NOT know about the embezzlement — they weren't told"]
- ⚠️ [e.g., "This NPC's relationship with X is hostile, not just tense — do not soften it"]
- ⚠️ [e.g., "This location closes at sundown — no evening access without special arrangement"]

---

[Repeat NPC Operations Guide for each major NPC. Minor NPCs can be grouped in a shorter format:]

### Minor NPCs (Quick Reference)

| NPC | Role | Voice Note | Default Attitude | Key Detail |
|-----|------|-----------|-----------------|------------|
| [Name] | [Role] | [One quirk] | [Attitude] | [One critical fact] |
| [Name] | [Role] | [One quirk] | [Attitude] | [One critical fact] |

---

## Ground Truth

**Purpose:** what actually happened, decided once and independent of anything the PC states, guesses, or does. This is the lookup that `core_rules.md`'s **Hypotheses Are Not Evidence** rule checks any player or NPC theory against — keep it separate from Plot Logic & Branching below, so the runtime GM isn't reconstructing "what's real" from conditional branches mid-scene.

For each fact a player could plausibly form a theory about, record:

- **The fact:** what actually happened, plainly stated.
- **Known by:** witnessed / told (by whom, when) / deduced (from what) — same standard as the Information Firewall. If a name isn't listed, they don't know it.
- **Hidden by, if anyone:** who benefits from concealment and what they stand to lose if it surfaces — this is what tells the runtime GM whether an NPC lies, denies, or redirects when asked.
- **Compromised, if anyone:** blackmail, threat, or compulsion — anyone whose stated position isn't their own, and who's really pulling the strings.
- **Confident but wrong, if anyone:** any NPC who sincerely believes something false and would state it as fact. Note the false belief and why they're convinced.
- **Discoverable through:** at least one non-testimonial path — a document, physical evidence, a witnessable event — by which the fact can surface even if every person asked lies. If no such path exists, the fact is unfalsifiable and the investigation can dead-end through no fault of play; fix the design before running it.

**Format:**

```
### Fact: [one-line statement of what actually happened]

- **Known by:** [Name] (witnessed, [date]) · [Name] (told by [Name], [date]) · [Name] (deduced from [evidence])
- **Hidden by:** [Name] — stands to lose [consequence] if revealed
- **Compromised:** [Name] — [nature of leverage/compulsion], acting for [who]
- **Believes falsely:** [Name] — convinced [false belief], because [reason]
- **Discoverable through:** [document / evidence / event that surfaces the fact without relying on testimony]
```

**Repeat per load-bearing fact.** A tight investigation might need 2-3; a sprawling political scenario might need a dozen. Don't pad it with trivia the PC has no path to theorize about.

---

## Plot Logic & Branching

**Ground Truth (above) establishes what's actually true; this section maps what happens as the PC interacts with it** — the two should never contradict each other.

[Map the scenario's key decision points with explicit consequences. The runtime GM should know what happens without needing to derive it.]

### Decision Point: [Description]

**Context:** [When and how this decision arises]

**If PC chooses [Option A]:**
- Immediate: [What happens in the scene]
- Downstream: [How this affects later scenes]
- NPC reactions: [Which NPCs respond and how]

**If PC chooses [Option B]:**
- Immediate: [What happens]
- Downstream: [Later effects]
- NPC reactions: [Responses]

**If PC does something unexpected:**
- Guiding principle: [How to adjudicate — e.g., "This NPC prioritizes self-preservation over loyalty" or "The location's guards follow strict protocol regardless of persuasion"]

---

[Repeat for each major decision point]

---

## World State Reminders

[Facts about the world that are easy to forget or contradict during fast-paced play.]

- **Timeline:** [Key dates and deadlines — e.g., "The solicitors arrive in 3 days," "The shipment is due at month's end"]
- **Season/Weather:** [Current conditions — affects travel, NPC behavior, available activities]
- **Political State:** [Who's in charge, what tensions exist, what's common knowledge vs. secret]
- **Economic State:** [Market conditions, shortages, trade routes — if relevant]
- **Recent Events:** [What just happened in the world that NPCs would talk about?]

---

## Tone & Atmosphere Notes

[Guidance on the scenario's intended feel — helps the runtime GM maintain consistency.]

- **Overall tone:** [e.g., "Slow burn investigation with social tension — not action-driven"]
- **Pacing guidance:** [e.g., "Let morning routines breathe. Don't rush to plot beats."]
- **Sensory anchors:** [e.g., "Mud season — everything is wet, cold, and grey. Boots track filth everywhere."]
- **What this scenario is NOT:** [e.g., "Not a dungeon crawl. Not a mystery with a single solution. The investigation is social, not forensic."]

---

## Session Pacing Markers

[Suggested session breakpoints — helps the runtime GM recognize when to offer checkpoints.]

- **Natural break after:** [Event or scene — e.g., "First full day at the estate concludes"]
- **Natural break after:** [Event or scene — e.g., "The confrontation with NPC resolves"]
- **Natural break after:** [Event or scene — e.g., "PC learns the key revelation"]
- **Scenario climax:** [The big scene — e.g., "The hearing / The raid / The departure"]

---

## Escalation Triggers

[What happens if the player delays, avoids, or ignores key threads? The world moves.]

- **If [thread] is ignored for [timeframe]:** [Consequence — e.g., "The embezzler destroys evidence"]
- **If [thread] is ignored for [timeframe]:** [Consequence — e.g., "The NPC leaves town"]
- **If [thread] is ignored for [timeframe]:** [Consequence — e.g., "The faction acts without PC input"]

---

## Post-Session Notes (Runtime GM fills this in)

[After each session, the runtime GM adds brief notes here for continuity across sessions within the same scenario.]

### Session [XX] Notes:
- **Deviations from expected plot:** [What the PC did that wasn't anticipated]
- **NPC attitude shifts:** [Any relationships that changed]
- **New threads opened:** [Anything the PC initiated that wasn't in the scenario]
- **Canon established during play:** [Details the runtime GM improvised that should now be treated as canon]
- **Ground truth decided in play:** [facts improvised mid-session — copy each into the Ground Truth block above, with Known by, so later sessions inherit them]
- **Lies told on-screen:** [said X — lie; truth: Y — listed so later sessions don't read the deception as confirmation]

---

## Architecture Note

This Scenario Package is the *operational* half of a paired set:

- **`Scenario_Template.md`** describes WHAT the scenario is — narrative design, plot arcs, branches, themes. Authored by the planning model in collaboration with the human designer.
- **`Scenario_Package_Template.md`** (this file) describes HOW to run it — voice anchors, file loads, canonical traps, conditional responses. Authored by the planning model after the Scenario file is settled. Consumed by the runtime model during play.

The two files are designed to be loaded together at session prep, with the Package serving as the active reference during play.

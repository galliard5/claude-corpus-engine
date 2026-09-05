---
name: Session Checkpoint Template
type: template
keywords: [checkpoint, session, save-point, template, structure]
description: Standard checkpoint format for auto-generated session save points - includes character state, NPCs, plot threads, and world continuity
---

# Session Checkpoint Template

**Purpose:** Auto-generated at natural stopping points (end of in-game day, major plot beat, player request). Contains enough detail for seamless session resumption.

**Usage:** This template defines the checkpoint structure. When a checkpoint is generated, fill in each section with current session data.

**CRITICAL:** The checkpoint header MUST ALWAYS include Campaign, IN-GAME DATE, Location, and Session number. The in-game date is essential for resuming accurately—it tells you exactly where you are in the timeline and what day/time it is in the world.

---

## Checkpoint Structure

```
═══════════════════════════════════════════════════════════
[CHECKPOINT SAVED: SESSION_XX]
═══════════════════════════════════════════════════════════

CAMPAIGN: [Campaign Name]
IN-GAME DATE: [Day X, Time (morning/afternoon/evening/night)]
LOCATION: [Current location name and brief sensory anchor]
SESSION: Session_XX
STATUS: current
        (current | superseded by Session_YY | abandoned — [reason])

---

CHARACTER STATE

**Name:** [Character name/race/class if relevant]

**Physical Condition:**
- Appearance: [Visible state: injuries, scars, cleanliness, bearing]
- Status Conditions: [Hungry, Tired, Injured, Exhausted, Sick, Intoxicated, etc.]
- Equipment: [Notable items on person or in inventory]

**Emotional/Mental State:**
- Current Mood: [Anxious, confident, determined, conflicted, suspicious, etc.]
- Relationships: [Recent attitude shifts with key NPCs]
- Character Arc: [What's the character grappling with or learning?]

**Bonds/Reputation:**
- [NPC Name]: [Attitude toward PC + reason (e.g., "impressed by bravery", "suspicious of motives")]
- [NPC Name]: [Attitude]

---

SCENE CONTEXT

**Current Setting:** [Detailed description of immediate surroundings that establishes mood/tone]

**Time of Day Specifics:** [What's happening naturally at this time? Who's around? What activities are ongoing?]

**Recent Dialogue Echo:** [If a significant conversation just occurred, capture the final beat or emotional tone]

---

MAJOR NPCs IN CURRENT LOCATION (Or Recently Encountered)

**[NPC Name]** [Brief role: e.g., "Garrison Captain", "Local merchant", etc.]
- **Attitude Toward PC:** [Friendly/wary/neutral/hostile + reason]
- **Current State:** [What are they doing? Mental/emotional state]
- **Key Quirk/Speech Pattern:** [One notable habit that makes them recognizable]
- **Recent Interaction:** [Last significant exchange with PC, if any]
- **Hot because:** [The durable link keeping them on this list: standing register ID, pending appointment, open obligation, or consequence still travelling. If you cannot name one, demote.]

**[NPC Name]**
- **Attitude Toward PC:** [Attitude]
- **Current State:** [What they're doing]
- **Key Quirk/Speech Pattern:** [One distinctive trait]
- **Recent Interaction:** [Last exchange]
- **Hot because:** [Durable link]

(Include 3-5 major NPCs; note any who have left the location or are expected to return)

**Demoted this session:** [Name — the link that closed] / none

---

RECURRING NPCs — LOCATION-TIED (Consistency Layer)

(Include staffing NPCs tied to locations the PC visits—not random street traffic, but people who work/live there. E.g., Joe who runs the alchemist stall on 5th Street. These NPCs should be consistent across sessions unless there's an in-world reason for absence. Reference: [[Location_Brief_Template]] for staffing model.)

**[Location]: [NPC Name]** — [Role/Position]
- **Attitude toward PC:** [How they relate to the character]
- **Key Detail:** [One distinctive trait: appearance, habit, speech quirk]
- **Regular Pattern:** [When/where are they typically available? E.g., "mornings at the stall", "off Sundays", "night shift only"]
- **Last Interaction:** [What was the last significant exchange with the PC?]
- **Current Status:** [Working as usual, sick, taking leave, promoted, left town, dead?]

**[Location]: [NPC Name]** — [Role/Position]
- **Attitude toward PC:** [Attitude]
- **Key Detail:** [One distinctive trait]
- **Regular Pattern:** [When/where available]
- **Last Interaction:** [Last exchange]
- **Current Status:** [Current state]

(Only include NPCs with a fixed location or role who might reappear. Random street vendors or one-off encounters don't get logged here. If Joe works at the alchemist stall and you visit in Session 01, Joe should be there in Session 02 unless something happened to him)

**This block does not demote.** Until the location has a brief with a Background NPCs — Consistency Layer section, this is the only record of these people's schedules and patterns. Carry them forward. Where a brief does exist, that brief is the source of truth and this block lists only those location NPCs currently on the active cast.

---

WORLD STATE

**Time Passage:** [How many days have passed in total? In-game calendar position]

**Location Changes:** [Any places destroyed, created, or significantly altered?]

**Faction Status:** [Any factions advanced their goals? Lost ground? New conflicts?]

**Environmental/Seasonal:** [Weather, season, conditions affecting travel/activities?]

---

KEY EVENTS (This Session)

- [Event 1: What happened, who was involved, consequence]
- [Event 2]
- [Event 3]
(3-5 major beats maximum; prioritize what matters for continuity)

---

PLOT THREADS & HOOKS (What's Unresolved)

**Active (In Progress):**
- [Thread 1: What's the PC pursuing? Status?]
- [Thread 2]

**Pending (Waiting for PC Action):**
- [Something an NPC asked the PC to do]
- [A mystery that needs investigation]

**Complications (Problems That Will Worsen):**
- [If ignored, what escalates? What's the timer?]

**Opportunities (Closing/Expiring):**
- [What can the PC still pursue before it's too late?]

---

FILES TO LOAD ON RESUME

(List every file the resuming model must read before beginning play.
Use full paths relative to project root. Group by priority.)

**Required (Load before play begins):**
- [Core rules]: Core_Rules/core_rules.md
- [Scenario]: World_Building/[Setting]/Scenarios/[Campaign]/[Scenario_File].md
- [Scenario Package]: [path, if one exists for this scenario]
- [PC Sheet]: [path to active character sheet]
- [Prior Summaries]: [paths to all session summaries for this campaign, in order]

**Reference only (do not load — consult if a summary is disputed):**
- [Transcripts]: `Scenarios/[Campaign]/Logs/` — verbatim record where a summary is ambiguous or contested. Far too large to load routinely; open a specific one deliberately, not as part of resume.

**Contextual (Load if relevant to active threads):**
- [NPC Sheet]: [path] — [reason: e.g., "interrogation pending"]
- [Location Brief]: [path] — [reason: e.g., "PC returning here next morning"]
- [Faction/Org]: [path] — [reason: e.g., "guild politics active"]
- [Timeline]: [path] — [reason: e.g., "time-sensitive deadlines approaching"]

**Optional (Reference if needed mid-session):**
- [Item/Enchantment]: [path] — [when relevant]
- [Skill Tree]: [path] — [if system is active for this campaign]
- [Other crosslinked file]: [path] — [context]

(Strip any files that are no longer relevant. Add any new files
that became relevant during this session. The goal is a cold-start
loading list — if the resuming model reads only these files plus
this checkpoint, play should resume seamlessly.)

---

GM MEMORY NOTES (For AI Continuity)

**NPC Voices to Maintain:**
- [NPC Name]: [Two distinctive speech quirks to keep consistent]
- [NPC Name]: [Two quirks]

**World Tone/Themes in Play:**
- [What thematic elements are active? E.g., "trust/betrayal", "duty vs. freedom"]

**Recent Foreshadowing Planted:**
- [What hints have been dropped? What will pay off?]

**PC Emotional Arc:**
- [Where is the character emotionally? What's driving them?]

---
END CHECKPOINT
═══════════════════════════════════════════════════════════
```

---

## Field Guide

### CHECKPOINT HEADER (Required on every checkpoint)

**CRITICAL: Every checkpoint MUST begin with these four fields:**

- **CAMPAIGN:** Name of the current campaign (e.g., "The Wandering Road")
- **IN-GAME DATE:** Exact day and time within the world. Format: "Day X, [morning/afternoon/evening/night]" or "Spring Day 14, evening" or "Wintermonth 3, mid-afternoon". **This is essential for resuming accurately.** Without it, I don't know what day/time context to use for the next session.
- **LOCATION:** Current location name + brief sensory anchor (e.g., "Market Square — vendor stalls, crowd noise, smell of fresh bread")
- **SESSION:** Session number with zero-padding (Session_01, Session_02, etc.)

**Why IN-GAME DATE matters:** It tells you exactly where in the timeline you are. It affects what NPCs are working, what weather conditions exist, what time-sensitive opportunities are still available, and what state the world is in. If I don't have this, I can't resume accurately.

### STATUS (required — controls whether this checkpoint is still true)

- **`current`** — the live save point. The default.
- **`superseded by Session_YY`** — play resumed from an earlier point and went a different way, or this session was re-run. The events here did not happen in the surviving timeline.
- **`abandoned — [reason]`** — a branch that was dropped. Keep the file; it may hold reusable material.

**Never delete a checkpoint that stopped being true, and never silently rewrite it.** Mark it and move on. An unmarked stale checkpoint is worse than a missing one: it loads clean, reads authoritative, and quietly reintroduces events that were undone. Anything downstream that cites a superseded session — a [[World_State_Register]] row, a [[Hanging_Threads]] entry, a timeline event — needs the same treatment in the same pass.

**A superseded checkpoint is not a resume target.** When resuming, if the newest checkpoint is not `current`, walk back to the newest one that is.

---

### CHARACTER STATE

Captures the PC's complete status so I can render them accurately:

- **Appearance:** How they look physically (wounds, scars, cleanliness, bearing, mood-written-on-body)
- **Status Conditions:** Active statuses from Section 6 of core rules (these persist between sessions)
- **Equipment:** What they're carrying (backpack, weapons, valuables, magical items)
- **Mood:** Emotional tenor right now
- **Relationships:** How key NPCs' attitudes toward them have shifted
- **Character Arc:** What internal journey is the character on? What are they learning/confronting?

### SCENE CONTEXT

Provides immersive continuity:

- **Current Setting:** Sensory details of the immediate environment (sight, sound, smell, mood)
- **Time of Day Specifics:** What's naturally happening at this hour? Is the tavern crowded? Is the street empty? Who works night shift here?
- **Recent Dialogue Echo:** If a scene just ended with a significant conversation, capture the final emotional beat (not the full dialogue, just the resonance)

### MAJOR NPCs (3-5 per checkpoint)

NPCs actively in the scene or directly relevant to current situation:

- **Attitude:** Friendly, wary, hostile, neutral (+ reason: "impressed by bravery", "suspect you're hiding something", etc.)
- **Current State:** What are they doing right now? How do they feel?
- **Key Quirk:** One distinctive speech pattern or behavior that makes them instantly recognizable
- **Recent Interaction:** Last meaningful exchange with PC (not necessarily this session)
- **Hot because:** The durable causal link that earns them a place on this list

**This is the active cast, and it is meant to shrink as well as grow.** See [[core_rules|core_rules.md]] Section 10 > *Promotion & Demotion* for what promotes and what does not. The short version: a standing World State Register entry, a pending appointment, an open obligation, or a consequence still in flight. Appearing last session is not a cause; being memorable is not a cause. If the **Hot because** field cannot be filled honestly, that NPC belongs on the **Demoted this session** line instead.

Demotion drops someone from the live roster, not from the world. Their character file stays true and the GM reads it normally the next time the PC seeks them out.

### RECURRING NPCs — LOCATION-TIED (The Consistency Layer)

**This is critical for world coherence.** These are location-staffing NPCs:

- **[Location]: Joe** — runs the alchemist stall
- **[Location]: Marget** — owns the bakery
- **[Location]: Guard Captain** — evening gate shift

**When you return to that location next session, these NPCs should be there** (unless something happened to them).

- **Regular Pattern:** when/where they work. "Mornings at the stall", "off Sundays", "night shift only", "opens at dawn"
- **Current Status:** clarifies if they're unavailable. "Sick this week", "took leave", "promoted to supervisor", "dead"

### WORLD STATE

Background continuity:

- **Time Passage:** cumulative days in the campaign (important for aging, seasons, deadlines)
- **Location Changes:** if you destroyed a building or factions fought over territory
- **Faction Status:** political/economic shifts
- **Environmental/Seasonal:** affects what's happening and what's possible

### KEY EVENTS

3-5 bullet points of major narrative beats. Prioritizes continuity:
- What changed in the world?
- What changed in PC relationships?
- What conflict resolved or escalated?

### PLOT THREADS & HOOKS

**Active:** What the PC is currently pursuing  
**Pending:** Quests/favors NPCs asked for, mysteries to solve  
**Complications:** Time bombs (what gets worse if ignored?)  
**Opportunities:** Limited-time quests (what expires soon?)  

### FILES TO LOAD ON RESUME

**This is the cold-start checklist.** If a different model instance (or the same model in a new conversation) picks up this checkpoint, this list tells it exactly what to read before play begins. Nothing should be left to inference or memory.

- **Required:** Always loaded. Core rules, the scenario doc, the PC sheet, all prior session summaries, and the Scenario Package if one exists. Without these, the session cannot run accurately.
- **Contextual:** Files tied to active plot threads. If an NPC interrogation is pending, their character sheet belongs here. If the PC is heading to a specific location next, that location brief belongs here. Update this list every checkpoint — drop files that are no longer relevant, add files that became relevant during the session.
- **Optional:** Reference material that might be needed but doesn't need to be loaded upfront. Skill trees, item databases, enchantment lists — things the GM can pull mid-session if the scene calls for it.

**The test:** Could a model with no prior context load this checkpoint plus every file in the Required and Contextual lists and run the next session without missing anything? If not, a file is missing from the list.

---

### GM MEMORY NOTES

**Critical for AI continuity** — this is how I stay consistent across sessions:

- **NPC Voices:** Two speech quirks per major NPC so I don't drift toward generic dialogue
- **World Tone/Themes:** What's thematically active? (Trust/betrayal? Duty vs. freedom? Progress vs. tradition?)
- **Foreshadowing:** What hints have been planted? What will pay off?
- **PC Emotional Arc:** Where is the character's head? What are they grappling with?

---

## When to Create a Checkpoint

See Section 10 of [[core_rules|core_rules.md]] for full rules. Quick version:

1. **In-game day ends** — character settling for sleep
2. **Scenario milestone reached** — major plot beat concluded
3. **Player explicitly requests** — "save here", "checkpoint"
4. **Emotional/narrative completion** — scene feels complete, not hanging
5. **Time passage indicates transition** — new chapter beginning (location/quest change)

---

## Session Naming

Auto-increments: **Session_01 → Session_02 → Session_03 ... Session_10 → Session_11**, etc.

- Zero-padded: `Session_01`, not `Session_1`
- Tracks across entire campaign
- Each checkpoint creates next session number

---

## Integration After Checkpoint

**[[Post_Session_Checklist]] is the authority for what happens after a checkpoint.** Follow its steps in order. Do not work from a list held here — this file defines the checkpoint's *shape*, not the post-checkpoint *process*, and a second copy of that process drifts out of sync with the first.

The checkpoint itself is immediate; the integration steps can be batched.

---
name: Scenario Timeline & Event Log
type: template
keywords: [timeline, scenario, calendar, session, events, tracking]
description: Per-scenario calendar template. Tracks in-game dates, session progression, and major events within a single scenario. References the Master Calendar for world context.
---

# Scenario Timeline & Event Log Template

**Purpose:** Tracks day-by-day progression within a single scenario. Shows what happened each day, status of threads, and current in-game date. Always references the [[Master_Calendar|Master Campaign Calendar]] for world context.

**Setup Instructions:**
1. Copy this template to your scenario directory
2. Replace [SCENARIO_NAME] with actual scenario name
3. Fill in the "Scenario Context" section
4. Update the "Current Date" line as the scenario progresses
5. Add entries to the Event Log as sessions conclude

---

## Scenario Context

**Scenario Name:** [SCENARIO_NAME]  
**World:** [Setting name]  
**Player Character:** [Name, race, role]  
**Primary Location:** [[Location_Name]]  
**Expected Duration:** [Open-ended / 1-2 weeks / X sessions]  

**Link to Master Timeline:** [[Master_Calendar]]

---

## Current Date

**[DAY X, MONTH DATE YEAR] — [TIME OF DAY]**

*Update this every session. Reference format: "Spring Day 14, late afternoon" or "10 April 1650, morning" or "Day 3 of scenario"*

---

## Quick Thread Status

| Thread | Status | Last Updated | Next Action |
|---|---|---|---|
| [Thread 1] | PENDING / ACTIVE / RESOLVED | Day X | What happens next? |
| [Thread 2] | [Status] | Day X | [Next step] |
| [Thread 3] | [Status] | Day X | [Next step] |

*(Add rows as threads appear)*

---

## Event Log — Scenario Day-by-Day

### DAY 1: [Date]

**Session:** Session_01  
**Time of Day:** Morning → Evening  

**Major Events:**
- [Event 1: Character arrived at location / made decision]
- [Event 2: NPC interaction / discovery]
- [Event 3: Complication / choice point]

**NPCs Encountered:** [Names and brief context]

**Threads Opened:**
- [Thread 1: what was introduced?]

**Status at End of Day:**
- [Character status: where are they, what condition?]
- [Relationships: any shifts with NPCs?]
- [Time-sensitive issues: deadlines approaching?]

**World State Changes:**
- [If anything in the world changed (location altered, NPC departed, etc.)]

---

### DAY 2: [Date]

**Session:** Session_02  
**Time of Day:** Morning → Evening  

**Major Events:**
- [Event 1]
- [Event 2]

**NPCs Encountered:** [Names]

**Threads Updated:**
- [Thread 1: progression or resolution?]
- [Thread 2: new thread opened]

**Status at End of Day:**
- [Character status]
- [Relationships]

**World State Changes:**
- [Any shifts]

---

*(Continue as sessions progress)*

---

## Resolved Threads

| Thread | Opened | Resolved | Outcome |
|---|---|---|---|
| [Thread] | Day X | Day Y | How did it resolve? What's the consequence? |

---

## Relationships — NPC Attitudes Over Time

Track how NPC attitudes toward the character shift session by session.

**[NPC Name]**
- Day 1: [Initial attitude/relationship state]
- Day 3: [Shifted after event X]
- Day 5: [Current status]

**[NPC Name]**
- Day 1: [Initial]
- Day 2: [Change]
- Current: [Status]

---

## Between-Scenario Notes

*If the scenario pauses and resumes later, or if another scenario starts while this one is ongoing, note that here.*

**Time Elapsed Since Last Session:** X days  
**Current World Status:** [Brief summary of what's happened to major threads while you weren't active]  
**Resumption Date:** [When does this scenario pick back up?]

---

## Key Dates & Deadlines

| Event | Target Date | Days Away | Notes |
|---|---|---|---|
| [Time-sensitive event] | [Date] | [X days from current date] | What happens if missed? |
| [Deadline] | [Date] | [X days] | Consequence if not met |

*(Add as time-sensitive threads appear)*

---

## Cross-Scenario Continuity

**World Events Happening Elsewhere (from Master Calendar):**

As of [CURRENT SCENARIO DATE], the following events have occurred in the broader world:
- [Event 1 from master timeline]: HAPPENED on [date]
- [Event 2]: IN PROGRESS since [date]
- [Event 3]: PENDING, expected [date]

**How This Affects This Scenario:**
- [If relevant, how do world events create context or complications?]

**Gossip & News:**
- What rumors would reach the player's location?
- What major news would NPCs be discussing?

---

## Session Checkpoints

Each checkpoint generated during this scenario should reference:
- IN-GAME DATE (critical)
- Current location
- Session number
- Status of major threads
- Next likely scenes or plot developments

**See:** [[Checkpoint_Template]] for full checkpoint structure

---

## Integration

After scenario conclusion:

1. **Update Master Calendar** — Add major events to [[Master_Calendar]]
2. **Note consequences** — Document how this scenario's outcome affects future scenarios
3. **Update Between-Scenario Gap** — If another scenario follows, document what happened in the gap
4. **Archive** — Save the scenario log alongside the campaign's other session records

---

## Timeline Reference Example

```
Current Date: 10 April 1650 — Morning
Session: Session_01

Quick Status:
- Embezzlement discovered at the estate (ACTIVE)
- Money-lender investigation triggered (ACTIVE)
- Solicitors summoned (PENDING — arrival expected within days)
- Regional inspection approaching (PENDING — ~1 May)

Cross-Scenario:
- A second campaign is running in parallel elsewhere in the region (12 days in)
- A time-sensitive NPC event is due within 1–2 weeks
```

The value of this block is the *shape*: current date and time of day, session number, a short
status line per live thread with an explicit state word, and a separate section for anything
moving in a parallel campaign that this one will eventually collide with.


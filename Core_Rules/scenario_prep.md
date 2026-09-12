---
name: Scenario Prep
module: Operating Procedure
type: rules-reference
keywords: [scenario, package, prep, handoff, capability, preparation, session]
description: Preparing a scenario and handing it to a play session — the scenario package, what it contains, and what a session loads. The surviving half of the former Model Selection Guide, with model routing removed.
---

SCENARIO PREP
=============

**This is the surviving scenario-preparation protocol.** Model roles and escalation criteria are
superseded by the capability classes in
`operating_procedure.md`. Everything below is the other half — a prep protocol that was never about
models at all, and reads better without them.

The distinction matters beyond tidiness. The old file's model routing is client-specific; the
scenario-package protocol is not. A package is useful on any host, and treating the whole source as
client-specific would have retired something worth keeping.

---

## The scenario package

A condensed operational document produced alongside every new scenario. It bridges the gap between
the deeper reasoning available during **preparation** and the faster execution wanted during
**play** — and it does that whether those are two models, two sessions, or the same person on two
different days.

**What it does:**

- Provides **explicit NPC decision logic**, so a session does not have to derive it from character
  files mid-scene
- Anchors **NPC voices** with concrete speech samples and behavioural guardrails
- Maps **conditional responses** — if the player does X, this NPC reacts with Y, because Z
- Lists **which canon files to load** for each major scene or location transition
- Flags **canon traps**: areas where improvisation is likely to contradict established lore

**What it is not:**

- A replacement for reading character and location files — those are still loaded
- A script. NPCs still react dynamically within the package's parameters
- Optional. Every prepared scenario produces one

**Format:** `Templates/Scenario_Package_Template.md`.

**Naming and location:** `[Scenario_Name]_Scenario_Package.md`, in the same directory as the
scenario file. The scenario and its package are a matched pair — the scenario file is the narrative
architecture, the package is the operational playbook.

---

## Creating a scenario

1. **Read the relevant canon** — characters, locations, factions, timeline, master calendar.
2. **Build the scenario** using `Templates/Scenario_Template.md`.
3. **Generate the package** using `Templates/Scenario_Package_Template.md`.
4. **Write both files** to the scenario directory.
5. **Verify cross-references** — every linked file exists and is current.

Both are required before play begins.

---

## Handing a scenario to a session

**What a session loads, in order:**

1. The **scenario package** — first, as the operational anchor
2. The **scenario file** — plot structure and branching
3. The **PC sheet** — current state, inventory, relationships
4. **Active NPC files** — as listed in the package
5. **Location files** for the opening scene — as listed in the package
6. The **most recent session summary**, if resuming
7. The **master calendar** — timeline context and world state

**What it does not need:** extraction rules (post-session only), template files, character files
for NPCs not yet encountered.

> **This list conflicts with the other source on how many summaries to load**, and the conflict is
> not resolved here — see `operating_procedure.md`, *Session lifecycle*. Where a checkpoint carries
> its own Required/Contextual list, that governs.

**Mid-scenario improvisation becomes canon through the package.** Where a session invents a detail
that sticks — a minor NPC, a location detail, a relationship shift — it is logged in the package's
post-session notes. That gives preparation a clear record of what changed when it returns for
extraction or revision.

---

## Retroactive packages

Scenarios built before this protocol have no package. One can be generated after the fact: read the
scenario file and all session summaries, generate a package reflecting current world state, and
save it alongside the existing scenario. Recommended before resuming any older scenario.

---

## What lives elsewhere

| | Where |
|---|---|
| Capability classes and when to escalate | `operating_procedure.md` |
| Checkpoints, session lifecycle, git | `operating_procedure.md` |
| Post-session data consolidation | `Scenario_Extraction_Rules.md` |
| The package's actual format | `Templates/Scenario_Package_Template.md` |

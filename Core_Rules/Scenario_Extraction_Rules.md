---
name: Scenario Data Extraction & Consolidation Rules
type: rules-reference
keywords: [consolidation, extraction, npc, location, scenario, data, organization, post-scenario]
description: Post-scenario protocol for extracting NPCs, locations, and world data from checkpoint summaries and consolidating into proper project files with full updates to cross-references.
---

# Scenario Data Extraction & Consolidation Rules

**Purpose:** After a scenario concludes, systematically extract all new NPCs, locations, factions, items, and world developments discovered during play and consolidate them into the proper project files using established templates. This ensures scenario data is preserved, organized, and integrated into the living world.

---

## MODEL REQUIREMENT CHECK

**BEFORE PROCEEDING:** This extraction task requires Claude Sonnet or higher.

**Current Model:** [CHECK ACTIVE MODEL]

### Model Check Logic

**IF running Sonnet or Opus:**
- ✅ Proceed to extraction immediately
- No concerns, adequate capability for this task

**IF running Haiku:**
- ⚠️ **PAUSE and display this message:**

> **Model recommendation:** This extraction task is best performed with Claude Sonnet. Haiku may miss cross-references, struggle with large scenarios (8+ checkpoints), or require re-processing.
>
> **Proceed anyway?** Confirm to continue with Haiku, or switch to Sonnet for better results.

- Wait for explicit user confirmation before continuing
- If confirmed, proceed with extra caution (verify more frequently, smaller batches)
- If not confirmed, stop and recommend user upgrade model

---

## CORE DIRECTIVE

**Every scenario generates knowledge about the world.** New NPCs are encountered. Locations are explored. Relationships are established. Factions advance. This information lives in checkpoint summaries but is not yet integrated into the project. 

Your job: **Read all checkpoints from a completed scenario, extract everything new or changed, and consolidate it into proper files.** This makes the data searchable, referenceable, and accessible to future scenarios.

---

## PREREQUISITES FOR EXTRACTION

Before beginning extraction, ensure you have:

1. ✅ **All checkpoint summaries from the scenario** — typically Session_01 through Session_XX
2. ✅ **The scenario template files** — Know what the scenario was about (location, characters, goals)
3. ✅ **Relevant existing project files** — Character sheets, location files, faction files that might need updates
4. ✅ **Timeline and calendar context** — Understand when this scenario took place in the world
5. ✅ **Access to all templates** — Character_Sheet_Template, Location_Brief_Template, Faction_Organization_Template, etc.

> **Placement note:** the directory paths below use `[Setting]` / `[Region]` / `[Faction_Name]`
> placeholders. The concrete map — which settings and regions exist, and how their character
> folders are subdivided — lives in the project profile referenced from
> `file_system_instructions.md` > STEP 7.

---

## EXTRACTION WORKFLOW

### STEP 1: READ ALL CHECKPOINTS IN SEQUENCE

**Objective:** Build a complete picture of what happened in the scenario.

**Process:**
1. Start with Session_01 checkpoint
2. Read straight through to the final session checkpoint
3. As you read, note:
   - **NPCs introduced** (names, roles, description, speech quirks, attitudes, flaws)
   - **Locations visited** (names, descriptions, staffing, key features)
   - **Factions that appeared or advanced** (goals, members, changes)
   - **Items acquired** (magical or significant)
   - **Relationships established** (PC to NPC, NPC to NPC)
   - **World changes** (politics, economics, physical alterations)
   - **Unresolved threads** (ongoing quests, complications, opportunities)

**Output:** Mental model of the scenario's scope and impact.

---

### STEP 2: CREATE EXTRACTION INDEX

**Objective:** Categorize all extracted data for systematic processing.

**Create a working document** with these sections:

```
EXTRACTION INDEX — [Scenario Name]

NPCs (NEW):
- [Name] | Role | Description | Location last seen

NPCs (EXISTING - UPDATED):
- [Name] | What changed? | Relationship shift? | New information?

LOCATIONS (NEW):
- [Location Name] | Type (Tavern/Manor/Town/etc) | Key features

LOCATIONS (EXISTING - UPDATED):
- [Location Name] | What changed? | New NPCs? | Altered layout?

FACTIONS (NEW OR ADVANCED):
- [Faction Name] | Type | Members | Goals | Changes this scenario

ITEMS (SIGNIFICANT):
- [Item Name] | Type | Current owner | Significance

RELATIONSHIPS (NEW):
- [PC to NPC] | Nature | Strength (warm/neutral/cold/hostile)
- [NPC to NPC] | Nature | Strength

WORLD CHANGES:
- [Change] | Type (political/economic/physical) | Impact

THREADS (ONGOING):
- [Thread] | Status (active/pending/complicated) | Next action needed
```

**Fill this index** by reviewing your notes from Step 1. Be thorough — you'll reference this throughout extraction.

---

### STEP 3: SEPARATE NEW VS. UPDATED DATA

**Objective:** Distinguish what needs new files from what updates existing files.

**For each category in your index, sort into two piles:**

**NEW:** 
- NPCs who didn't exist before
- Locations never mentioned in project files
- Factions not yet documented
- Entirely new relationships

**UPDATED:**
- NPCs who already had files (attitude/relationship shifts, new information)
- Locations with existing files (staffing changes, physical alterations)
- Factions with existing files (new members, goal advancement)
- Relationships between known figures

**Mark each clearly.** You'll process NEW first (file creation), then UPDATED (file edits).

---

## FILE CREATION PROTOCOL

### STEP 4: CREATE NEW NPC FILES

**Objective:** Document new NPCs with full character detail.

**For each NEW NPC:**

1. **Copy the Character_Sheet_Template** to the appropriate location:
   - `World_Building/[Setting]/[Region]/Town/Characters/` if a town NPC
   - `World_Building/[Setting]/[Region]/Region/Characters/` if a regional or nobility NPC
   - `World_Building/[Setting]/[Region]/Region/Factions/[Faction_Name]/Characters/` if faction-specific
   - The faction's own `Characters/` subfolder if they are staff of a specific organization — check the profile for any role-based subdivision within it

2. **Name the file:** `First_Last.md` (if named) or `NPC_Role.md` if only a title is known

3. **Fill in from checkpoint data:**
   - **Name/Title:** Exact name and any titles
   - **Description:** Physical appearance from scene narration
   - **Speech Quirks:** The two quirks you noted in GM MEMORY NOTES
   - **Personality:** Draw from observed behavior, not assertion
   - **Goals:** What does this NPC want? (from autonomy section if noted)
   - **Relationships:** Current attitude toward PC and other NPCs
   - **Recent Interaction:** Summary of last significant exchange from checkpoint
   - **Appearance/Portrait:** Leave blank if no image available, or note if an image was created

4. **Cross-reference:**
   - If the NPC is tied to a location, note their location entry
   - If they're part of a faction, note the faction
   - If they have relationships with other NPCs, link those files

5. **Verify YAML frontmatter:**
```yaml
---
name: [NPC First Last]
keywords: [npc, role, location, faction, any relevant tags]
description: Brief one-sentence summary (role and relevance)
---
```

**Special Cases:**

- **Transformed PC (if applicable):** Create full character sheet but note in keywords: "transformed", "player-adjacent"
- **Minor NPC (appears once):** Still create a file if they're mentioned by name; use MINOR_NPC tag
- **Recurring minor NPC:** If they appear 3+ times or have memorable behavior, create a full file

---

### STEP 5: CREATE NEW LOCATION FILES

**Objective:** Document new locations with staff, layout, and access information.

**For each NEW LOCATION:**

1. **Copy the Location_Brief_Template** to appropriate directory:
   - `World_Building/[Setting]/[Region]/Town/` if a town location
   - `World_Building/[Setting]/[Region]/Region/Factions/[Faction_Name]/` if inside a faction's holdings
   - `World_Building/[Setting]/[Region]/Region/` for other regional locations

2. **Name the file:** `Location_Name.md`

3. **Fill in from checkpoint data:**
   - **Location Name:** Full formal name
   - **Type:** Tavern, Manor, Town, Farm, etc.
   - **Description:** Sensory details from opening scene
   - **Layout/Key Features:** Rooms, districts, physical landmarks
   - **NPCs Present:** Who works/lives/frequents there
   - **Accessibility:** How to get there, who can enter, restrictions
   - **Atmosphere:** Mood, tone, clientele (if relevant)
   - **Activities:** What happens here, what can be done

4. **Background NPCs - Consistency Layer:**
   - List NPCs who work there with regular schedules
   - Include: name, role, availability pattern, key detail (from checkpoint)
   - These are the recurring location staff

5. **Recent Events:**
   - Has anything changed since the PC left?
   - Any news from the location (if we know)?

6. **Cross-references:**
   - Link to NPCs who work there
   - Link to nearest major location
   - Link to relevant factions or organizations

7. **Verify YAML frontmatter:**
```yaml
---
name: [Location Name]
keywords: [location, type, region, faction/owner, relevant tags]
description: Brief one-sentence summary (type and significance)
---
```

---

### STEP 6: CREATE NEW FACTION FILES (if applicable)

**Objective:** Document new factions or organizations encountered.

**For each NEW FACTION:**

1. **Copy the Faction_Organization_Template** to `World_Building/[Setting]/[Region]/Region/Factions/` for factions based in that region, or the appropriate regional directory for factions based elsewhere

2. **Name the file:** `Faction_Name.md`

3. **Fill in from checkpoint data:**
   - **Name:** Official faction name
   - **Type:** Guild, House, Criminal Organization, etc.
   - **Goal:** What does this faction want? (from NPC autonomy if noted)
   - **Members:** Who's part of it (link to NPC files)
   - **Structure:** Hierarchy, roles, decision-making
   - **Territory/Influence:** Where do they operate?
   - **Resources:** Money, connections, assets
   - **Attitude toward PC:** How does the faction view the character?
   - **Recent Activity:** What did they do in this scenario?
   - **Conflicts:** Who are their rivals or enemies?

4. **Cross-references:**
   - Link to member NPC files
   - Link to location files where they operate

5. **Verify YAML frontmatter:**
```yaml
---
name: [Faction Name]
keywords: [faction, type, goal, region, conflict tags]
description: Brief one-sentence summary (type and primary goal)
---
```

---

### STEP 7: CREATE SIGNIFICANT ITEM FILES (if applicable)

**Objective:** Document magical items or significant equipment acquired.

**For each SIGNIFICANT ITEM:**

1. **Copy appropriate item template** (or create from scratch if no template exists) to:
   - `World_Building/[Setting]/[Region]/Region/Unique_Enchanted_Items/` for magical items
   - Or note in PC character sheet for mundane items

2. **Fill in:**
   - **Name:** Item name
   - **Type:** Weapon, Artifact, Tool, etc.
   - **Description:** Appearance and properties
   - **History:** Where did it come from?
   - **Current Owner:** Who has it now?
   - **Significance:** Why does it matter?

3. **Cross-reference:** Link to current owner's file

---

## UPDATE PROTOCOL

### STEP 8: UPDATE EXISTING NPC FILES

**Objective:** Integrate scenario changes into existing character files.

**For each UPDATED NPC:**

1. **Read their current file** to understand baseline state

2. **Identify what changed:**
   - Attitude toward PC (did it shift?)
   - Known goals (did they change or progress?)
   - Relationships (new connections with other NPCs?)
   - Status (promotion, injury, relocation?)
   - Recent events (what did they do in the scenario?)

3. **Update these fields only:**
   - **Attitude Toward PC:** Update if changed; reference what caused the shift
   - **Recent Activity:** Add scenario events
   - **Current Status:** Where are they now? What are they doing?
   - **Known Goals:** Update goal status if progressed
   - **Relationships:** Add new connections with NPCs they met

4. **Add to "Last Updated"** field (if it exists) with date and scenario name

5. **Cross-reference:** If new relationships were formed, link those NPC files

6. **Verify changes are consistent** with their documented speech quirks and personality

---

### STEP 9: UPDATE EXISTING LOCATION FILES

**Objective:** Log changes and new information about visited locations.

**For each UPDATED LOCATION:**

1. **Read their current file**

2. **Identify what changed:**
   - Did the layout change?
   - Did staffing change (NPCs left, new ones arrived)?
   - Were new areas discovered?
   - Did the atmosphere/reputation shift?

3. **Update:**
   - **Background NPCs section:** Add new staffers, update availability if changed
   - **Recent Changes:** Log what's different since last visit
   - **Current Status:** Note anything the PC might find when they return
   - **Last Updated:** Date and scenario name

---

### STEP 10: UPDATE TIMELINE & MASTER CALENDAR

**Objective:** Ensure world events are logged for future scenario context.

**Edit the scenario's timeline file:**

1. Update **"Current Date"** to reflect the final checkpoint date

2. Add to **"Event Log"** any major world-changing events:
   - Faction movements
   - NPC status changes (death, promotion, relationship shifts)
   - Location changes (destroyed, built, altered)
   - Unresolved threads (note which ones remain active)

3. Update **"Active Threads"** table:
   - Mark resolved threads with completion date
   - Mark newly opened threads
   - Update status on ongoing threads

4. **Edit the Master Campaign Calendar:**
   - Add major events from this scenario to the appropriate date range
   - Update thread status in the global event tracking
   - Note which threads remain active for future scenarios

---

### STEP 11: UPDATE EXISTING FACTION FILES

**Objective:** Log faction progress and changes.

**For each UPDATED FACTION:**

1. **Read their current file**

2. **Update:**
   - **Member List:** Add new members who joined this scenario
   - **Recent Activity:** What did they accomplish or attempt?
   - **Goal Progress:** Did they advance toward their goals?
   - **Relationship Changes:** Did their stance on other factions shift?
   - **New Conflicts:** Any new enemies or allies?

3. **Cross-reference:** Update NPC files if member roles changed

---

### STEP 12: UPDATE SCENARIO FILE

**Objective:** Document the scenario's completion and connect it to extracted data.

**Edit the scenario file** (the campaign's own scenario document):

1. **Add completion metadata:**
   - Date range (Session_01 to Session_XX)
   - Completion date
   - Final outcome (resolved/ongoing/branching)

2. **Add "Characters Met" section:**
   - List all NPCs encountered
   - Link to their new files

3. **Add "Locations Discovered" section:**
   - List all locations visited
   - Link to their new files

4. **Add "Factions Encountered" section:**
   - List all factions/organizations met
   - Link to their new files

5. **Update "Outcome" section:**
   - What was resolved?
   - What threads remain for future scenarios?
   - What did the world learn?

---

## VALIDATION & VERIFICATION

### STEP 13: CROSS-REFERENCE CHECK

**Objective:** Ensure all files properly link to each other.

**Verify:**

1. ✅ All NPC files link to their location files
2. ✅ All NPC files link to their faction files (if applicable)
3. ✅ All location files link to their staff NPC files
4. ✅ All faction files link to their member NPC files
5. ✅ All new files have proper YAML frontmatter
6. ✅ All new files have keywords that make them searchable
7. ✅ Timeline reflects all major events
8. ✅ Master Calendar has been updated
9. ✅ Related existing files have been updated (not left stale)

**Common mistakes to check:**
- NPC file created but location file doesn't reference them
- Location file updated but NPC file doesn't link back
- Faction created but members' files don't note the faction
- Threads logged in timeline but not in Master Calendar
- Major events not added to Master Calendar

---

### STEP 14: FRESHNESS UPDATE

**Objective:** Update the file index to reflect all new files.

**After all files are created and linked:**

1. If using a file index system, regenerate or update the index
2. Update the Master Calendar's file count if it tracks this
3. Add new locations to any regional inventories
4. Add new NPCs to any faction member lists

---

## BATCH WRITE PROTOCOL

**All files created in this extraction should be batched:**

1. **Create all new files** first (don't write yet)
2. **Plan all edits** to existing files (list them out)
3. **Get user confirmation** if needed: "Ready to write X new files and update Y existing files?"
4. **Execute batch write** in a single pass
5. **Verify all files** were created successfully
6. **Read a sample** of created files to confirm they're correct

This prevents mid-process failures and gives you a clear audit trail.

---

## ERROR HANDLING & EDGE CASES

### Incomplete Information
If an NPC or location wasn't fully described in checkpoints:
- Create the file with available information
- Add a "TODO" note in the description field
- Flag with a `[incomplete]` keyword so you can find it later
- Complete on next visit to that NPC/location

### Conflicting Information
If checkpoint descriptions contradict each other (NPC acted two different ways):
- Go with the most recent checkpoint (latest in sequence wins)
- Note the discrepancy in the file with a comment
- Flag with `[verify]` keyword for later review

### NPCs Introduced Then Left
Some NPCs appear once and depart. Still create files if:
- They're named specifically
- They had meaningful interaction
- They have memorable speech quirks or personality

Don't create files for:
- Completely unnamed background characters ("a merchant")
- One-line NPCs with no personality
- Extras in crowds

### Locations Mentioned But Not Explored
If a location is talked about but not visited:
- Note it as "mentioned but not visited" in the location file
- Create a stub file with basic information
- Mark with `[unvisited]` keyword for later expansion

---

## COMPLETION CHECKLIST

After extraction is complete:

- [ ] All NEW NPC files created and linked
- [ ] All NEW location files created and linked  
- [ ] All NEW faction files created and linked
- [ ] All NEW item files created (if applicable)
- [ ] All EXISTING NPC files updated with scenario changes
- [ ] All EXISTING location files updated with scenario changes
- [ ] All EXISTING faction files updated with scenario changes
- [ ] Scenario file updated with completion metadata
- [ ] Timeline file updated with all events
- [ ] Master Calendar updated with major events
- [ ] All YAML frontmatter verified
- [ ] All cross-references verified
- [ ] File index/catalog updated
- [ ] Sample files read to verify correctness

**When all boxes are checked:** Scenario extraction is COMPLETE. Data is now integrated into the project and accessible to future scenarios.

---

## MAINTENANCE

**This extraction should happen:**
- Immediately after a scenario concludes
- While checkpoints are fresh in context
- Before starting a new scenario (to ensure world is current)

**Regular audits** of extracted data ensure:
- Files don't go stale
- New scenarios reference correct information
- Cross-references remain valid as the world evolves

---

## SPECIAL WORKFLOW: UPDATING MASTER CALENDAR

The Master Calendar is your world's single source of truth for what happened when. Update it with:

1. **Scenario completion date**
2. **All major world events** that occurred
3. **NPC status changes** (deaths, promotions, relocations)
4. **Location alterations** (destroyed, created, captured)
5. **Thread status** (active → resolved, pending → active)
6. **Faction movements** (advanced, lost ground, new conflicts)

This ensures future scenarios have a clear picture of what's changed since the last adventure.

---

## REFERENCES

- [[Character_Sheet_Template]] — For creating new NPC files
- [[Location_Brief_Template]] — For creating new location files
- [[Faction_Organization_Template]] — For creating new faction files
- [[Master_Calendar]] — Central timeline and event log
- [[Timeline_Template]] — Scenario-specific timeline
- [[file_system_instructions]] — For file naming and structure conventions
- [[core_rules]] — For understanding world tone and continuity


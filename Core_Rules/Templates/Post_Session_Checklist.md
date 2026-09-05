---
name: Post-Session Checklist
type: template
keywords: [checklist, workflow, session, documentation, post-session]
description: Step-by-step checklist for Claude to follow at a checkpoint or session end — what to update and in what order
---

# Post-Session Checklist

**Instructions for Claude:** Follow these steps at every checkpoint or session end. Complete them in order. Do not skip steps unless the section explicitly marks them as conditional.

---

## Step 1: Write the Session Summary

1. Copy the `Session_Summary_Quick_Capture.md` template structure
2. Populate every section from the current session
3. Save to `World_Building/[Setting]/Scenarios/[Campaign]/[Campaign_Name]_Session_[NN].md` — zero-padded, matching the checkpoint's SESSION field
4. Set the checkpoint's `STATUS:` field (normally `current`)
5. Verify the file was written successfully before proceeding

---

## Step 2: Generate the Transcript Stub

File location: `World_Building/[Setting]/Scenarios/[Campaign]/Logs/[Campaign_Name]_Session_[NN]_transcript.md`

Create the `Logs/` directory if it does not exist. Use the format in `Session_Transcript_Stub.md`.

**Write the frontmatter and the paste marker only.** Fill in campaign, session number, in-game date, location, and real date from the checkpoint you just wrote — that metadata is what makes the file findable later, and it's the part Claude actually knows. Set `status: awaiting-transcript`.

**Do not write transcript content.** Claude cannot copy a conversation; it can only regenerate one, which paraphrases and drops turns while looking verbatim. A confabulated transcript is worse than none — it reads authoritative and gets trusted. If asked to fill one in, say so plainly and offer the stub.

Then tell the player the stub is ready and where it is. They paste the session in, strip the out-of-character material, and set `status: complete`.

---

## Step 3: Update the Player Character Sheet

File location: the PC's character sheet — see the project profile for where character files live in this corpus.

- Update **Current Date** field
- Update **Active Conditions** — apply new statuses, clear resolved ones
- Update **Permanent Injuries & Alterations** if anything changed
- Update **Memory / Interaction Log** for any significant NPC interactions
- Update **appearance** description if physical changes occurred
- Update **Trust Level** for relevant NPCs if relationships shifted

---

## Step 4: Update the Campaign Timeline

File location: `World_Building/[Setting]/Scenarios/[Campaign]/Timeline_[Campaign].md`

- Update **Current Date** line
- Append new entries to **Event Log** under the current date
- Update **Active Threads** table — status changes, new threads, urgency upgrades
- Move resolved items to **Resolved Threads**

---

## Step 5: Update the World State Register

File location: `World_Building/[Setting]/World_State_Register.md`

Skip this step for campaigns that have no register file — not every setting maintains one.

Scan the session and ask directly: **what did anyone promise, owe, hide, break, or hand over?** These are the facts that vanish from prose summaries because each one is too small to earn a paragraph.

- Add a row per new atomic fact, in the matching category
- Assign the next ID and increment the counter at the bottom of the file
- Set **Known by** from who was actually present or actually told — not from who it would be convenient for
- Fill **Overrides** if the fact contradicts a canon file, and note that file for a later update if the change is permanent
- Review `standing` entries — move anything resolved to the Archive with an outcome; widen `Known by` on any secret that broke
- Update `current_as_of` and `last_updated` in the frontmatter

If an entry grows past one line into open questions, it has become a thread — promote it to `Hanging_Threads.md` instead.

---

## Step 5b: Cast Demotion Pass

Run this immediately after Step 5 — it reads that step's output.

Walk the checkpoint's **active cast** (the MAJOR NPCs block) one name at a time and ask what durable link keeps each of them live: a standing register entry, a pending appointment, an open obligation in either direction, or a consequence still travelling toward them.

- If a link exists, fill the **Hot because** field with it
- If the last link closed this session — entry archived with an outcome, appointment kept, obligation discharged — move that NPC to the **Demoted this session** line with the cause that closed
- If no link ever existed and the NPC is on the list because they were vivid or recent, demote them

Before dropping anyone, push anything worth keeping into their character file (Step 6) — a shifted Trust Level, a new interaction log entry, an unresolved grudge. Demotion removes them from the live roster, not from the world; the file must carry what the roster stops carrying.

**Do not demote from the RECURRING NPCs — LOCATION-TIED block.** Where the location has no brief with a Background NPCs — Consistency Layer section, that block is the only record of the person's schedule and pattern. Carry them forward and note the missing brief.

See `Core_Rules/core_rules.md` Section 10 > *Promotion & Demotion* for the full criteria.

---

## Step 6: Update Affected NPCs (conditional)

Only if an NPC appeared in the session and something meaningfully changed.

File location: the NPC's character file — see the project profile for placement.

- Update **Trust Level** if attitude shifted
- Update **Active Conditions** if status changed
- Update **Memory / Interaction Log** with the specific interaction
- Update **appearance** or **Permanent Injuries** if physically changed

---

## Step 7: Update Affected Locations (conditional)

Only if a location's status changed — a building damaged, a condition applied or resolved, a situation escalated.

- Update **Active Conditions** section of the relevant location file

---

## Step 8: Verify Metadata & Sheet Boundaries

For every file updated, check that the YAML frontmatter is still accurate:

- `name` still matches the file's subject
- `keywords` reflect current state (add `injured`, `pregnant`, `investigated`, etc. where relevant)
- `description` reflects current situation, not outdated context

**For sheet+bio files (any file with `<sheet>...</sheet>` markers):** if you edited content inside the sheet section, the line count may have shifted. Verify the canonical marker `</sheet>` and update `sheet_end_line:` in the YAML to match the actual line number of the closing tag. The marker is the source of truth; the YAML field is an optimization that lets readers use `head=N` to load just the sheet portion. If the two disagree, the marker wins and the field must be corrected.

Procedure:
1. Locate the line containing `</sheet>` in the edited file
2. Note its line number (the file starts at line 1 with `---` opening the YAML)
3. Update `sheet_end_line:` in the frontmatter to that number
4. If you only edited content *outside* the sheet section (e.g., in the bio prose), no line-count update is needed

---

## Step 9: Notify the Player

Once all updates are complete, confirm in a single line:

*"Saved. [Summary filename] written, [N] files updated. Transcript stub ready at [path] — paste when you're ready."*

List the files updated only if the player asks.

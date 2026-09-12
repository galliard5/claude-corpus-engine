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

**If the summary will exceed ~10 KB, write it in two passes.** A single `write_file` payload in the 10–15 KB range can wedge the filesystem MCP: the write itself succeeds and reads back correctly, but the connection is poisoned and a later call — often several operations afterwards — hangs with no error. It looks like an unrelated failure much later, which is what makes it expensive. Write the frontmatter and opening sections first, then append the rest with `edit_file`.

---

## Step 2: Capture the Transcript

**The tool is `transcript:capture_session_transcript`.** Named here because it is easy to miss: it runs on the host rather than in the Docker stack, so it does not appear alongside the corpus tools. If it is absent from your tool list, run `tool_search("transcript")` before concluding it is unavailable — and if it is genuinely missing, say so rather than describing the raw commands, because the scripts are code-claude's to run.

File location: `World_Building/[Setting]/Scenarios/[Campaign]/Logs/[Campaign_Name]_Session_[NN]_transcript.md`

**Ask the player for a share link.** The transcript is captured mechanically from the rendered conversation — `Session_Transcript_Stub.md` has the sharing steps. Tell the player the session is at a capture point and let them decide whether to do it now.

**If they capture now,** call the tool with the campaign folder name, the zero-padded session number, and the `in_game_date` from the checkpoint you just wrote — the capture cannot derive that, and a transcript regenerated later cannot recover it. Pass the session's cast in `keywords` as plain words. The tool writes both the transcript and its raw archive copy; there is no stub to create. Tell the player to stop sharing once it reports success.

**If they defer,** write the stub — frontmatter only. Fill in campaign, session number, in-game date, location, and real date from the checkpoint you just wrote; that metadata is what makes the file findable later, and it is the part Claude actually knows. Set `status: awaiting-transcript` so the gap is findable, and leave `status` alone afterwards — only the player knows whether the capture actually happened.

**Never write transcript content from memory.** Reproducing a session from context is unverifiable: fidelity decays silently over length and Claude cannot say which passages drifted. A confabulated transcript is worse than none, because it reads authoritative and gets trusted. If asked, say so plainly and offer the capture route.

---

## Step 3: Update the Player Character Sheet

File location: the PC's character sheet — see the project profile for where character files live in this corpus.

**Update any field whose truth-value changed this session.** The list below is the common set, not the complete one — real sheets in this corpus also carry Legal Situation, Relationships, Voice, Independent Goal, Combat Disposition, and PC-specific fields such as pregnancy status or estate decisions, and those go stale as readily as the obvious ones. Walk the sheet rather than the list.

- Update **Current Date** field
- Update **Active Conditions** — apply new statuses, clear resolved ones
- Update **Permanent Injuries & Alterations** if anything changed
- Update **Memory / Interaction Log** for any significant NPC interactions
- Update **appearance** description if physical changes occurred
- Update **Trust Level** for relevant NPCs if relationships shifted

**The PC sheet holds the detail of shared interactions; NPC files point at it.** When the same encounter would be written on both this sheet and an NPC's (Step 6), the full account belongs here. The reason is portrayal: a PC may later be run as an NPC, and when that happens their own sheet has to carry everything needed to reproduce how they behaved — voice, choices, what they said and to whom. A sheet that delegated its detail to a dozen NPC files cannot do that, and reassembling it after the fact means reading every file the character ever touched.

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

**A first pass on an empty or lagging register is much larger than a maintenance pass, and that is expected.** Catching up from several sessions routinely yields 15–30 entries at once. That is the register doing its job, not scope creep, and it should not be trimmed to look like a normal session's handful.

---

## Step 5b: Cast Demotion Pass

Run this immediately after Step 5 — it reads that step's output.

Walk the checkpoint's **active cast** (the MAJOR NPCs block) one name at a time and ask what durable link keeps each of them live: a standing register entry, a pending appointment, an open obligation in either direction, or a consequence still travelling toward them.

- If a link exists, fill the **Hot because** field with it — the field and the `Demoted this session` line are defined in `Checkpoint_Template.md` (ACTIVE CAST), not in the session summary template. Do not invent a substitute block when you cannot find it there.
- If the last link closed this session — entry archived with an outcome, appointment kept, obligation discharged — move that NPC to the **Demoted this session** line with the cause that closed
- If no link ever existed and the NPC is on the list because they were vivid or recent, demote them

Before dropping anyone, push anything worth keeping into their character file (Step 6) — a shifted Trust Level, a new interaction log entry, an unresolved grudge. Demotion removes them from the live roster, not from the world; the file must carry what the roster stops carrying.

**Do not demote from the RECURRING NPCs — LOCATION-TIED block.** Where the location has no brief with a Background NPCs — Consistency Layer section, that block is the only record of the person's schedule and pattern. Carry them forward and note the missing brief.

See `Core_Rules/operating_procedure.md` > *Active cast* for the full criteria.

---

## Step 6: Update Affected NPCs (conditional)

Only if an NPC appeared in the session and something meaningfully changed.

File location: the NPC's character file — see the project profile for placement. **If the file's location is not obvious, search for the NPC by name with `corpus-search` rather than `filesystem:search_files`** — character files sit four to six levels deep under faction and settlement hierarchies, and the filesystem search does not reliably reach them. A `filesystem:search_files` miss is not evidence the file does not exist.

- Update **Trust Level** if attitude shifted
- Update **Active Conditions** if status changed
- Update **Memory / Interaction Log** with a one-line pointer to the interaction, not a second copy of it
- Update **appearance** or **Permanent Injuries** if physically changed

**Record the NPC's own state here; leave the narrative on the PC sheet.** What belongs on this file is what the NPC now believes, wants, fears or will do differently — state that is theirs and that a scene needs without loading anyone else's sheet. What happened between them and the PC belongs on the PC sheet (Step 3), referenced from here by session and date. Writing the full account in both places is the drift risk: two copies of one event diverge at the first correction, and nothing marks which is current.

---

## Step 7: Update Affected Locations (conditional)

Only if a location's status changed — a building damaged, a condition applied or resolved, a situation escalated.

- Update **Active Conditions** section of the relevant location file

---

## Step 8: Verify Metadata & Sheet Boundaries

**Every file, sheet+bio or flat.** Most character files in this corpus are flat prose with no `<sheet>` markers; the frontmatter pass below still applies to all of them, and is the whole of the step for a flat file. Only the second half is conditional.

For every file updated, check that the YAML frontmatter is still accurate:

- `name` still matches the file's subject
- `keywords` reflect current state (add `injured`, `pregnant`, `investigated`, etc. where relevant)
- `description` reflects current situation, not outdated context — this is the field that goes stale most quietly, since nothing in play ever reads it back

**Only for sheet+bio files (any file with `<sheet>...</sheet>` markers):** if you edited content inside the sheet section, the line count may have shifted. Verify the canonical marker `</sheet>` and update `sheet_end_line:` in the YAML to match the actual line number of the closing tag. The marker is the source of truth; the YAML field is an optimization that lets readers use `head=N` to load just the sheet portion. If the two disagree, the marker wins and the field must be corrected.

Procedure:
1. Locate the line containing `</sheet>` in the edited file
2. Note its line number (the file starts at line 1 with `---` opening the YAML)
3. Update `sheet_end_line:` in the frontmatter to that number
4. If you only edited content *outside* the sheet section (e.g., in the bio prose), no line-count update is needed

---

## Step 8b: Memory Sync (conditional)

Only if this session created a **structural** change — a new subdirectory, a new file category, a placement convention, a renamed path.

Follow STRUCTURAL CHANGE PROTOCOL in `file_system_instructions.md`, which requires the memory entry to be written **before** the commit, not after. Ordinary content edits need nothing here; a new `Documents/` folder under a campaign, or a new kind of file living somewhere future-Claude would not predict, needs it.

The failure this prevents is quiet: the next session's directory index is refreshed, but nothing explains *why* a folder exists, so the convention is re-derived — differently — the next time the same situation comes up.

---

## Step 9: Notify the Player

Once all updates are complete, confirm in a single line.

If the transcript was captured:

*"Saved. [Summary filename] written, [N] files updated. Transcript captured — [N] messages. You can stop sharing the link."*

If capture was deferred:

*"Saved. [Summary filename] written, [N] files updated. Transcript stub at [path] — capture whenever you're ready."*

List the files updated only if the player asks.

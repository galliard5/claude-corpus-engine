---
name: Session Transcript Stub
type: template
keywords: [template, transcript, session, log, archive, verbatim, capture, share]
description: How a session transcript is captured from a share link and cleaned into the verbatim archive layer beneath summaries and checkpoints — plus the stub Claude writes when capture is deferred
---

# Session Transcript

**Purpose:** Every other session artifact is lossy. The summary compresses, the checkpoint captures state rather than play, and the [[World_State_Register]] records facts without the moments that produced them. This is the layer underneath all of them — what was actually said.

**Why it matters:** when a summary says an NPC named a conspirator, nothing else lets you check what was actually said, who was present, or whether the summary flattened a nuance. The transcript is the audit trail. It is also the only artifact that can answer a question nobody thought to ask at the time.

**The primary consumer is Claude, not the player.** A summary keeps the arc and discards the detail; sessions later, a detail turns out to have mattered. The transcript is where it can be recovered — but only through the search index, since Claude cannot open and scan a file the way a person can. That dependency is what makes the scene headings below load-bearing rather than cosmetic.

---

## HARD RULE: Claude does not reproduce the transcript from memory

**The transcript is captured mechanically from the rendered conversation. Claude never writes the body of one by recalling the session.**

The prior turns of a session *are* present in context, so this is not a claim that reproduction is impossible. It is a claim that it is unverifiable, which is worse for this file than for any other:

- **Fidelity decays silently over length.** A long reproduction has no error-correction loop and no diff against the source, and drifts toward likelier phrasings — typos repaired, false starts smoothed, an odd construction normalised. None of it announces itself.
- **There is no confidence signal.** Even at high accuracy, Claude cannot say *which* passages drifted. Every other artifact here is allowed to be lossy because it is labelled lossy. This one's entire value is being exact, so an unmarkable error rate disqualifies it.
- **Compaction lands exactly when the transcript is wanted.** Capture happens at the end of a long session, which is precisely when early turns are most likely to have been summarised away already.
- **A capture tool selects the text instead.** It reads the rendered conversation rather than regenerating it, so the question of fidelity does not arise.

A confabulated transcript is worse than no transcript, because it looks authoritative and will be trusted later.

**If asked to fill one in from memory, say plainly that it would be unverifiable, and offer the capture route below.**

---

## Capturing a transcript

Two scripts in `Python/`, run on the host by code-claude — not in the Docker stack, since they drive a real browser. The raw capture is archived unedited; the readable transcript is *derived* from it, so a later improvement to the cleaner can be re-applied to old sessions rather than the original having been destroyed by the first cleanup pass.

**1. Share the conversation.** In Claude Desktop:

> Upper right of the conversation → share link button → select **"only people invited"** → open that dropdown → **"anyone with the link"** → **Save** → wait for it to verify → **copy link**.

The link must be *public*. A restricted link redirects to sign-in and the capture will refuse it, naming that as the reason.

**2. Capture.** `capture_transcript.py <share-url> --out <raw>.jsonl` writes one JSON object per message — index, role, ISO timestamp, HTML, and rendered text — plus a `.meta.json` sidecar carrying the source URL, counts, span and a SHA-256. It validates before writing and writes nothing at all if the capture looks wrong.

**3. Stop sharing** as soon as the capture reports success. In Desktop: share settings (the gear beside the share button) → **Stop sharing** → wait for it to verify. Revoking does not affect an already-written capture — the file is the artifact, the link is only transport.

**4. Clean.** `clean_transcript.py <raw>.jsonl --out <transcript>.md` derives the readable markdown: strips GM choice menus, OOC asides and tool-invocation markers, promotes `[ Scene: ... ]` tags to headings, and records what it removed in the frontmatter.

**Both files are kept.** The raw `.jsonl` is the archive copy and is never edited.

**Why HTML is stored, not just text.** The GM writes markdown; the browser renders it; the visible text discards every construct that carries meaning. Measured on one real session: 142 italics, 103 code spans, 52 horizontal rules, 2 tables and 16 headings, all flattened — and link destinations lost outright. Horizontal rules are the worst case, because a rule has no text and so vanishes leaving no evidence it existed.

---

## Scene headings come from the GM

The GM tags scene changes during play, in the status block beside time and status — see [[core_rules]] SECTION 6 > *Display*:

```markdown
`[ Time: first light ]`
`[ Status: Tired ]`
`[ Scene: the mill yard — the warden, the steward ]`
```

The cleaner promotes each of those to a real heading in the transcript:

```markdown
## Scene: the mill yard — the warden, the steward
```

**This is not decoration.** These headings are the unit the transcript search index is built from, and the names after the dash become its witness column. Two things depend on them:

1. **Chat cannot browse this file.** It has no editor, no scrolling, and no content search outside the corpus index. Without scene-sized rows to retrieve, a transcript is reachable only by loading the whole thing, which is not an option mid-session. The headings are what let chat recover a detail a summary dropped three sessions back.
2. **Who was present governs what can be said.** A retrieved scene carries its witnesses, so the [[core_rules]] §Information Firewall still applies to recovered material — an NPC absent from that scene learned nothing from it.

The tag is written **forward-looking**: it sits immediately before the choice options and names the scene the player is about to enter, not the one just narrated.

**The player's job is to verify, not to author.** Read the witness lists and correct any that are wrong. A wrong name is worse than a missing one — it grants an NPC knowledge of something they never witnessed, and nothing downstream can tell a guessed witness from an observed one. `clean_transcript.py` reports how many scene markers it found and warns loudly when a transcript has none.

Transcripts recorded before this convention have no markers. Add them by hand where they matter, or leave them; the cleaner flags candidate breaks from real-time gaps, but those mark when play *stopped*, which is not the same as where a scene ended.

---

## Remaining player pass

The mechanical strip is deterministic and handled by the cleaner. What is left is judgment-based:

- Rules questions and clarifications that are not the OOC-aside pattern
- Retries, false starts, and corrected passages — keep the version that stands
- Anything else that is not play but does not match a strip rule

**Strip, don't rewrite.** Deleting a passage is safe; editing prose destroys the exact thing the file exists for. If a passage is ambiguous, keep it — this is the raw layer, and over-curation costs more than clutter. The raw `.jsonl` remains the fallback if a cleanup goes too far.

---

## Stub Format — when capture is deferred

If a session ends and the transcript is not captured immediately, Claude writes a stub so the gap is findable. **Frontmatter only — never a body.**

**Path:** `World_Building/[Setting]/Scenarios/[Campaign]/Logs/[Campaign_Name]_Session_[NN]_transcript.md`
**Create the `Logs/` directory if it does not exist.**

```markdown
---
name: "[Campaign Name] Session [NN] — Transcript"
type: session-transcript
status: awaiting-transcript
keywords: [transcript, session, verbatim, campaign-name, setting-name]
description: "Transcript of [Campaign] Session [NN], [in-game date]"
campaign: "[Campaign Name]"
session: "Session_[NN]"
in_game_date: "[in-game date and time, matching the checkpoint header]"
played: "[real-world date]"
---

# [Campaign Name] — Session [NN] Transcript

**In-game:** [date and time] · **Location:** [where play ended] · **Played:** [real date]

> Not yet captured. Share the conversation and run `capture_transcript.py`, then
> `clean_transcript.py`. Delete this line when the transcript replaces it.
```

`status: awaiting-transcript` is what makes an uncaptured session findable. Do not set it to `complete` on the player's behalf — only the player knows whether the capture and verification actually happened.

**The share link expires with the conversation's sharing state, not with the stub.** A stub can sit indefinitely; re-sharing later produces a fresh link for the same conversation, and the captured content is identical.

---

## Not to Be Confused With

| File | What it holds |
|---|---|
| `[Campaign]_Session_[NN]_transcript.md` | Verbatim play, cleaned and readable |
| `[Campaign]_Session_[NN]_raw.jsonl` | The unedited capture it was derived from — archive copy, never edited |
| `Session_Summary_Quick_Capture.md` | Structured summary of what happened |
| `Session_Log_Template.txt` / `Session_Log_Condensed.txt` | **Also summaries**, despite the name |
| `Checkpoint_Template.md` | World and character *state* at a stopping point |

The word "log" is overloaded in this corpus. Only the transcript and its raw capture are verbatim.

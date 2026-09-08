---
name: Transcript Capture
type: documentation-component
keywords: [transcript, capture, share, playwright, cloudflare, markdownify, archive, verbatim, transcript_mcp_server, capture_transcript, clean_transcript]
description: Full reference for the session-transcript pipeline — the share-page capture, the HTML-to-markdown cleaner, the native MCP server that wraps them, and the browser constraints that shaped all three.
---

# Transcript Capture

Three pieces produce the verbatim archive layer beneath summaries and checkpoints:

| File | Role |
|---|---|
| `Python/capture_transcript.py` | Reads a public claude.ai share page, writes raw JSONL + a `.meta.json` sidecar |
| `Python/clean_transcript.py` | Derives the readable markdown transcript from that JSONL |
| `Python/transcript_mcp_server.py` | Native MCP server wrapping both, so the GM can call them at a checkpoint |

The player shares the conversation, the capture runs, the player stops sharing. The written files are the artifact; the link is only transport, and revoking it cannot affect a capture that already completed.

**The raw JSONL is the archive record and is never edited.** The transcript is *derived* from it, so a later improvement to the cleaner can be re-applied to sessions already captured. Cleaning in place would make every cleaner bug permanent.

## Why a browser at all

A share page is client-rendered. Plain HTTP returns the application shell: a 108 KB document whose only large payload is the JS bootstrap, with no message content, no timestamps, and a generic `og:description`. There is no server-rendered copy and no public data endpoint, so a real browser engine is required.

## Why headed, and why not in Docker

claude.ai sits behind Cloudflare, which **challenges headless browsers**. A headless run is redirected to `/api/challenge_redirect` and served a security-verification page — well-formed, and containing zero messages. A headed browser is not challenged in the tested configuration. Nothing here attempts to defeat that check: on a challenge the capture aborts and writes nothing.

That single fact rules out the compose stack, and three more reasons compound it:

1. A container has no display, so Chrome runs headless there by default. Faking one with Xvfb is untested against the challenge and engineers around a problem the host does not have.
2. One image serves `corpus-search`, `index-tools` and `series-search` — they differ only in `command:`. A browser would bloat all three, including the two that mount the corpus read-only and will never use it.
3. The containers currently reach nothing but the mounted corpus. Capture needs outbound HTTPS, and granting that to the shared image widens the surface of every server in it.

So the server runs natively on the host, launched by the MCP client the way `bgm` is. `Python/Dockerfile` copies by explicit filename, so nothing new reaches the image.

**A persistent browser profile is challenged where an ephemeral one is not.** Measured on the same link minutes apart: the default ephemeral profile passed repeatedly; a freshly created persistent profile was challenged twice. The capture therefore does not use one, and window geometry is passed as launch arguments instead — which was the only thing a persistent profile was wanted for.

## Window placement

The browser window is real and visible unless placed off-screen, which is the default (`--window-position=-32000,-32000`; Windows clamps to about `-26214`). An off-screen window still renders fully — verified at 58 and 64 messages — and is not challenged.

Off-screen is preferred over minimising: Chrome throttles rendering and timers in a minimised window, which risks a page that never finishes rendering and a capture that silently comes back short. `--window-position` and `--window-size` accept any geometry if you would rather see it.

## Why the HTML is stored, not just the text

`innerText` is what the eye sees, which is not what the GM wrote. The model emits markdown, the browser renders it to HTML, and the visible text discards every construct that carries meaning.

Measured on one real session, counted **after** pruning the accessibility nodes: 142 `<em>`, 103 `<code>`, 52 `<hr>`, 2 `<table>`, 16 headings — all flattened to plain prose, with link destinations lost outright. Horizontal rules are the worst case: a rule carries no text, so 52 authored divisions vanished leaving no evidence they had existed.

The capture therefore stores each message's HTML as the archive record, and `clean_transcript.py` converts it with `markdownify`. Text is retained alongside as a convenience field for validation and grep; it is lossy by construction and is not the source of truth.

## Three traps in the DOM

Each of these produces a plausible-looking wrong answer rather than an error, which is why they are commented at their call sites.

**The accessibility nodes duplicate every message.** Naive extraction returns each one roughly doubled — a transcript that stutters throughout and looks fine in a spot check. Stripping `[aria-hidden="true"]`, `.sr-only` and `[hidden]` fixes it.

**The role labels live in those same nodes.** `You said:` and `Claude responded:` are screen-reader text, so removing the duplication also destroys the only role marker. The role must be read from the raw text *before* pruning, and the body taken after. Getting the order wrong yields `role: unknown` on every message.

**Detached clones have no layout.** Cleaning on a cloned node degrades `innerText` to `textContent`, which inserts no line breaks at block boundaries — 1,062 paragraph breaks lost on one session, and the tool-invocation widget fused onto the prose beside it. The pruning is therefore done on the live DOM, which is disposable because the page is about to be closed.

Counting tags is subject to the first trap too: the screen-reader copy carries its own headings, so a naive count read 80 where the visible content has 16. Count after pruning.

## Validation

`capture_transcript.py` writes nothing unless the capture passes: roles all recognised, no empty bodies, no leaked screen-reader labels, no duplicated text, contiguous indices. Timestamp gaps and non-monotonic ordering are warnings rather than failures. A Cloudflare challenge, a restricted link, and a revoked link are each reported by name rather than as a generic timeout — a challenged page is a valid page with no messages, which a trusting caller would serialise as an empty transcript.

## Heading levels are a retrieval contract

`clean_transcript.py` emits a structure that `corpus-search:get_section` can navigate:

| Level | Unit |
|---|---|
| `#` | Document title |
| `##` | Scene — promoted from the GM's `[ Scene: where — who ]` tag; the names after the dash are the witness list |
| `###` | Turn — the practical retrieval unit |
| `####`+ | The GM's own headings, demoted two levels to stay clear of both |

Turns are headings because scenes are too coarse: measured on a real session a scene averages ~9,000 tokens — the size `get_section` exists to avoid — while a turn is ~425 median, ~5,300 worst case. Turn numbers are zero-padded because `get_section` matches a heading by unique prefix, and unpadded `Turn 1` is a prefix of `Turn 12`.

Scene headings are never invented. An absent tag is reported, not guessed, because a fabricated witness list would license an NPC to know something nobody saw. See `Core_Rules/core_rules.md` SECTION 6 > *Display* for the GM-side rule and `Core_Rules/Templates/Session_Transcript_Stub.md` for the workflow.

## Where the files go

- Transcript: the campaign's `Logs/` folder, beside the session summary
- Raw JSONL: `World_Building/raw_transcript_archive/`

`indexer.cfg` excludes the raw archive with `World_Building/raw_transcript_archive/*.*` — the directory stays visible so the archive is discoverable, but its files are neither listed nor indexed. Each is roughly a megabyte holding the same prose as the transcript beside it, so indexing them would double every transcript hit and let a raw dump outrank the readable file derived from it.

Frontmatter follows the Stub Format in `Session_Transcript_Stub.md`, so a stub and the transcript replacing it are the same shape. `in_game_date` is **not derivable from the capture** — it comes from the checkpoint, and a regeneration that omits it drops a field silently. `played` records a span rather than a date when the first and last message fall on different days: a session is not a sitting, and one measured session ran across two months of evenings.

## Keywords and filtering

Keywords are FTS-indexed at 5× weight and are the coarse filter narrowing which transcripts get searched. Build them from **plain words, never compound slugs**: the FTS5 tokenizer splits on underscores and hyphens, so `old_mill` indexes as two ordinary tokens and `session_2` indexes as `session` + `2`, matching every transcript in the corpus. Per-session precision comes from `type_filter` (`doc_type`) and `category_filter` (directory), not from keywords.

## The MCP tool

`transcript:capture_session_transcript` — see `file_system_reference.md` > *Transcript* for the parameter schema.

Guards follow `index_tools_mcp_server.py`: the two scripts are hardcoded, no parameter accepts a filesystem path, output locations are derived from the corpus root plus a campaign and session matched against a charset that cannot express a path traversal, and the share URL must match the claude.ai share form. Subprocesses run without a shell, with stdin closed and a 300-second timeout.

The campaign folder is located by globbing `World_Building/*/Scenarios/<campaign>/` rather than asking the caller for the setting — one less caller-supplied path component — and an ambiguous match is an error rather than a guess, because filing a session under the wrong setting would be silent.

An existing capture is refused unless `overwrite=true`. A failed capture writes nothing, so there is no partial file to clean up; if capture succeeds but the cleaner fails, the raw archive is intact and the transcript can be rebuilt without recapturing.

`check_schema_drift.py` probes this server through `NATIVE_STDIO_SERVERS`, spawning it directly rather than reading an MCP client's configuration, so the check works on a machine with no client installed.

## Registering it — quit the client first

Two things bite here, and together they contradict the obvious instructions.

**Desktop reverts edits made while it is running.** It reads `claude_desktop_config.json` at
startup, holds it in memory, and writes its own copy back when it quits. An entry added while it is
running is discarded on the next restart, with no error and no log line: the config simply reverts
and the tool never appears. Observed directly — the file's modification time moved to the moment of
quit, and its server list matched a pre-edit backup byte for byte.

**On a packaged install, the documented path only exists while Desktop is running.** Claude Desktop
may be installed as an MSIX/Store package, in which case `%APPDATA%\Claude` is a redirection into
the package's private storage, and it disappears when the app exits. The real file is at:

```
%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json
```

So "quit first, then edit `%APPDATA%\Claude\...`" is self-defeating on such an install: quitting
removes the path the instruction names, and a reader who follows it finds nothing and reasonably
concludes something is broken. A non-packaged (`.exe` installer) install uses `%APPDATA%\Claude`
directly and does not have this problem.

**The procedure that works on both:** quit Desktop fully (tray icon → Quit), locate the config by
searching rather than by assuming a path —

```powershell
Get-ChildItem $env:APPDATA,$env:LOCALAPPDATA -Filter claude_desktop_config.json -Recurse -Force -ErrorAction SilentlyContinue
```

— edit the file it finds, then start Desktop. The same caution applies to any edit of that file,
not only to this server.

```json
"transcript": {
  "command": "python",
  "args": ["<corpus>/Python/transcript_mcp_server.py"],
  "env": {"CORPUS_ROOT": "<corpus>"}
}
```

An MCP client reads the tool list once at connection time, so the client must be restarted before
the tool is callable even when the config is correct.

## Requirements

`playwright` and `markdownify` on the **host** interpreter, plus a Chromium-family browser already installed. Playwright drives that browser via `channel="chrome"`, so the bundled ~150 MB Chromium download is not needed.

Neither package is in `Python/requirements.txt`, which is baked into the container images for something no container runs. Install them with pip when you first capture a session.

**Chrome is the only verified channel.** `--channel` accepts `msedge`, `chromium` and `firefox`, and autodetect falls back through Chrome → Edge → bundled Chromium, but only Chrome has been tested against the Cloudflare check. Firefox additionally needs Playwright's own bundled build.

## Known limits

- **This does not port to another vendor, and has not been tested against one.** The rest of the
  engine reaches a model through MCP and is client-agnostic in principle. This reads claude.ai's
  own web surface: the `https://claude.ai/share/<id>` URL form, the page structure, and the
  `You said:` / `Claude responded:` role markers. None of that is a standard, none of it is
  documented, and none of it has an equivalent guaranteed to exist elsewhere. Another provider
  would need this rebuilt rather than reconfigured — and only if it offers a shareable rendered
  conversation to read in the first place. Treat any claim that the method transfers as unverified;
  nobody has tried it.
- **The scraper is coupled to claude.ai's DOM.** It keys off `[data-test-render-count]`, `time[datetime]` and the accessibility-node pattern — undocumented internals that can change without notice. A frontend redesign breaks capture even when the conversation and sharing both work.
- **Re-deriving a capture depends on three things outside your control**: the conversation still existing in the account, sharing still working this way, and the page still being recognisable to the scraper. Re-sharing a conversation does reproduce it exactly — verified across three separate share links yielding identical message counts and timestamps — but that is a courtesy of the platform, not a guarantee.
- **A share link is revocable, mutable state.** Toggling its visibility can invalidate it outright: a link that loaded seconds earlier returned *"Conversation not found"* after a visibility change. Never treat a share URL as a durable reference; scrape promptly and let the written file be the record.

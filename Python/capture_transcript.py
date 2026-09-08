# name: Capture Transcript
# keywords: [transcript, capture, share, playwright, session, archive, verbatim]
# description: Captures a claude.ai public share link to a raw JSONL transcript (one object per
#              message: index, role, ISO timestamp, deduplicated text) via a real headed browser.
#              Writes nothing if the capture fails validation.
#
# Requires: playwright (`python -m pip install playwright`) and a Chromium-family browser. It
# drives the browser already installed on the host via channel="chrome", so the ~150MB bundled
# Chromium download (`playwright install chromium`) is not needed. Host-side only — deliberately
# NOT in Python/requirements.txt, which is baked into the Docker image; nothing in a container
# runs this, and adding it there would bloat every MCP server image for no benefit.
#
# The verbatim archive layer for session transcripts. A share page is a server-rendered copy of
# the conversation, so this SELECTS text rather than regenerating it — unlike asking a model to
# reproduce a session from context, which paraphrases and drops turns while looking verbatim.
#
# Output is deliberately raw and never edited afterwards: clean_transcript.py derives the readable
# markdown from it. Keeping the raw dump means a later fix to the cleaner can be re-applied to old
# sessions instead of the original having been destroyed by the first cleanup pass.
#
# WHY HEADED: claude.ai sits behind Cloudflare, which challenges headless browsers. A headed
# browser is not challenged in the tested configuration. Nothing here attempts to defeat that
# check — if a challenge appears, the script aborts and writes nothing. See --window-position for
# how to keep the window out of the way.
#
# TESTED CONFIGURATION: Chrome (channel="chrome") on Windows, ephemeral profile. A *persistent*
# profile was challenged where the ephemeral one was not, so this deliberately does not use one.
# Edge and Firefox are supported by --channel but are UNVERIFIED against the challenge.
#
# HOW TO GET THE LINK (Claude Desktop):
#   Share:  upper right of the conversation -> share link button -> select "only people invited"
#           -> open that dropdown -> "anyone with the link" -> Save -> wait for it to verify
#           -> "copy link".
#   Stop:   share settings (gear next to the share button) -> Stop sharing -> wait to verify.
#   Revoke as soon as the capture reports success. The written file is the artifact; the link is
#   only transport, and revoking it does not affect an already-written capture.
#
# Command line arguments:
#   <url>                    the claude.ai/share/... link to capture (required)
#   --out <path>             output .jsonl path (required)
#   --channel <name>         chrome | msedge | chromium | firefox (default: autodetect)
#   --window-position <x,y>  browser window position (default: -32000,-32000, i.e. off-screen)
#   --window-size <w,h>      browser window size (default: 1200,900)
#   --timeout <seconds>      per-step page timeout (default: 60)
#   --force                  overwrite an existing output file, and downgrade hard checks to warnings
#   --no-pause               skip the end-of-run pause (set this in automation)

import argparse
import json
import hashlib
import re
import sys
import time
from pathlib import Path

MSG_SEL = "[data-test-render-count]"
CHALLENGE_RE = re.compile(r"security verification|Just a moment|challenge_redirect", re.I)
SR_LABEL_RE = re.compile(r"^(You said:|Claude responded:)")

# Role labels and a duplicate of the message body both live in the accessibility nodes.
# Those nodes must be stripped or every message comes out stuttered - but stripping them
# also removes the only role marker, so the role is read from the RAW text first and the
# body is taken from the cleaned clone. Getting this order wrong yields either doubled
# text or role="unknown" on every message, and neither raises an error.
EXTRACT_JS = r"""() => {
  const els = [...document.querySelectorAll('[data-test-render-count]')];
  const times = [...document.querySelectorAll('time[datetime]')]
                  .map(t => t.getAttribute('datetime'));

  // Pass 1: read the role BEFORE removing anything, because the label lives in the
  // accessibility node that pass 2 deletes.
  const roles = els.map(e => {
    const raw = (e.textContent || '').replace(/\s+/g, ' ').trimStart();
    if (/^You said:/.test(raw)) return 'user';
    if (/^Claude responded:/.test(raw)) return 'assistant';
    return 'unknown';
  });

  // Pass 2: delete the accessibility duplicates from the LIVE DOM. This page is about to be
  // closed, so mutating it is free - and it must be the live tree rather than a detached
  // clone: a clone has no layout, so innerText degrades to textContent and every block
  // boundary is lost, gluing separate paragraphs (and the tool-call widget) onto the prose
  // beside them. Synchronous read below, so React has no chance to re-render them back.
  document.querySelectorAll('[aria-hidden="true"],.sr-only,[class*="sr-only"],[hidden]')
          .forEach(n => n.remove());

  // Pass 3: keep the HTML, not just the rendered text.
  //
  // innerText is what the eye sees, which is NOT what the GM wrote. The model emits markdown;
  // the browser renders it to HTML; innerText then discards every construct that carries
  // meaning. Measured on one real session (counted AFTER the removal above, so these are
  // visible content, not the accessibility duplicate): 16 headings, 142 <em>, 103 <code>,
  // 52 <hr>, 2 <table> - all flattened to plain prose, and link hrefs lost outright. The <hr>
  // case is the worst: a rule has no text, so it vanishes leaving no evidence it existed.
  //
  // Count tags AFTER pruning if you ever re-measure. The screen-reader copy carries its own
  // headings - 80 before the removal above, 16 after - so a naive count overstates by 5x.
  //
  // So the HTML is the archive record and markdown is derived from it downstream, which keeps
  // the conversion re-runnable when the converter improves. `text` is retained as a convenience
  // field for validation and grep; it is lossy by construction and is not the source of truth.
  return els.map((e, i) => ({
    i: i,
    role: roles[i],
    ts: times[i] || null,
    html: e.innerHTML,
    text: (e.innerText || '').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim()
  }));
}"""


class BadArg(Exception):
    pass


def parse_pair(value, name):
    """Parse an 'a,b' integer pair from the command line."""
    parts = value.split(",")
    if len(parts) != 2:
        raise BadArg("%s expects 'x,y', got %r" % (name, value))
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        raise BadArg("%s expects integers, got %r" % (name, value))


def channel_plan(requested):
    """Ordered list of (browser_attr, channel) launch attempts.

    Chrome first because it is the only configuration verified against the Cloudflare
    challenge. Edge is Chromium and usually present on Windows, so it is a reasonable
    fallback, but it is UNVERIFIED - as is Firefox, which additionally needs Playwright's
    own bundled build (`playwright install firefox`).
    """
    if requested == "firefox":
        return [("firefox", None)]
    if requested == "chromium":
        return [("chromium", None)]
    if requested:
        return [("chromium", requested)]
    return [("chromium", "chrome"), ("chromium", "msedge"), ("chromium", None)]


def capture(url, channel, position, size, timeout_s):
    """Load the share page in a headed browser and extract its messages.

    Returns (messages, note). Raises RuntimeError on a challenge or an empty page so the
    caller writes nothing - a challenged page is well-formed and simply has no messages,
    which a naive caller would happily serialise as an empty transcript.
    """
    from playwright.sync_api import sync_playwright

    args = [
        "--window-position=%d,%d" % position,
        "--window-size=%d,%d" % size,
    ]
    with sync_playwright() as p:
        browser = None
        last_err = None
        for attr, chan in channel_plan(channel):
            browser_type = getattr(p, attr)
            launch_kwargs = {"headless": False, "args": args}
            if chan:
                launch_kwargs["channel"] = chan
            try:
                browser = browser_type.launch(**launch_kwargs)
                break
            except Exception as e:          # channel not installed on this machine
                last_err = e
        if browser is None:
            raise RuntimeError(
                "No usable browser found (tried: %s).\n"
                "        Last error: %s"
                % (", ".join(c or a for a, c in channel_plan(channel)), last_err))
        try:
            page = browser.new_page(no_viewport=True)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
            try:
                page.wait_for_selector(MSG_SEL, timeout=timeout_s * 1000)
            except Exception:
                body = page.evaluate("() => document.body.innerText") or ""
                if CHALLENGE_RE.search(body) or CHALLENGE_RE.search(page.url):
                    raise RuntimeError(
                        "Cloudflare challenge served instead of the conversation.\n"
                        "        Nothing was written. Retry; if it persists, capture is not\n"
                        "        available right now. Do not attempt to bypass the check."
                    )
                if "/login" in page.url:
                    raise RuntimeError(
                        "Share link is not public - it redirected to sign-in.\n"
                        "        Either sharing was stopped, or it is still set to\n"
                        "        'only people invited'. In Desktop: share link button ->\n"
                        "        open the 'only people invited' dropdown -> 'anyone with the\n"
                        "        link' -> Save -> wait for it to verify -> copy link."
                    )
                if "not found" in body.lower() or "don't have permission" in body.lower():
                    raise RuntimeError(
                        "Share link is not accessible (revoked, expired, or never made public).\n"
                        "        In Desktop: share settings -> set 'anyone with the link' -> Save."
                    )
                # Unrecognised state: show what was actually on the page rather than a bare
                # timeout, so the next person does not have to reproduce it under a debugger.
                snippet = " ".join(body.split())[:160]
                raise RuntimeError(
                    "No messages appeared within %ds.\n"
                    "        URL:  %s\n"
                    "        Page: %r" % (timeout_s, page.url[:100], snippet)
                )

            # Let late-rendering turns settle before reading the DOM.
            page.wait_for_timeout(3000)
            messages = page.evaluate(EXTRACT_JS)
            return messages, "%s%s" % (browser_type.name, "/" + chan if chan else "")
        finally:
            browser.close()


def validate(messages):
    """Return (hard, soft) problem lists. Hard problems mean the capture is not trustworthy."""
    hard, soft = [], []
    if not messages:
        hard.append("no messages captured")
        return hard, soft

    unknown = [m["i"] for m in messages if m["role"] == "unknown"]
    if unknown:
        hard.append("%d message(s) with unrecognised role: %s" % (len(unknown), unknown[:8]))

    empty = [m["i"] for m in messages if not m["text"].strip()]
    if empty:
        hard.append("%d empty message body/bodies: %s" % (len(empty), empty[:8]))

    leaked = [m["i"] for m in messages if SR_LABEL_RE.match(m["text"])]
    if leaked:
        hard.append("screen-reader label leaked into %d body/bodies: %s" % (len(leaked), leaked[:8]))

    # Stutter: the accessibility duplicate surviving into the body. Hard, because a doubled
    # transcript looks fine at a glance and silently corrupts the one artifact meant to be exact.
    stutter = []
    for m in messages:
        text = m["text"]
        for n in (60, 40, 25):
            if len(text) >= n * 2:
                head = text[:n].strip()
                if len(head) > 10 and text[n:n * 2 + 20].lstrip().startswith(head[:20]):
                    stutter.append(m["i"])
                    break
    if stutter:
        hard.append("possible duplicated text in %d message(s): %s" % (len(stutter), stutter[:8]))

    if [m["i"] for m in messages] != list(range(len(messages))):
        hard.append("message indices are not contiguous")

    stamps = [m["ts"] for m in messages if m["ts"]]
    if len(stamps) != len(messages):
        soft.append("%d of %d messages have no timestamp" % (len(messages) - len(stamps), len(messages)))
    if any(stamps[i] < stamps[i - 1] for i in range(1, len(stamps))):
        soft.append("timestamps are not monotonic")

    return hard, soft


def main():
    ap = argparse.ArgumentParser(description="Capture a claude.ai share link to raw JSONL.")
    ap.add_argument("url")
    ap.add_argument("--out", required=True)
    ap.add_argument("--channel", default=None,
                    choices=["chrome", "msedge", "chromium", "firefox"])
    ap.add_argument("--window-position", default="-32000,-32000")
    ap.add_argument("--window-size", default="1200,900")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-pause", action="store_true")
    args = ap.parse_args()

    start = time.perf_counter()

    if "/share/" not in args.url:
        print("[!] Not a share link: %s" % args.url)
        print("    Expected https://claude.ai/share/<uuid>")
        return 2

    out = Path(args.out)
    if out.exists() and not args.force:
        print("[!] Output already exists: %s" % out)
        print("    Refusing to overwrite a capture. Use --force, or choose another path.")
        return 2

    try:
        position = parse_pair(args.window_position, "--window-position")
        size = parse_pair(args.window_size, "--window-size")
    except BadArg as e:
        print("[!] %s" % e)
        return 2

    print("Capturing %s" % args.url)
    print("  window: position=%s size=%s%s" % (
        position, size, "  (off-screen)" if position[0] < -10000 else ""))

    try:
        messages, engine = capture(args.url, args.channel, position, size, args.timeout)
    except RuntimeError as e:
        print("[!] %s" % e)
        return 1
    except Exception as e:
        print("[!] Capture failed: %s: %s" % (type(e).__name__, e))
        return 1

    hard, soft = validate(messages)
    for w in soft:
        print("  [warn] %s" % w)
    if hard:
        for h in hard:
            print("  [FAIL] %s" % h)
        if not args.force:
            print("[!] Capture failed validation. Nothing written.")
            print("    These checks exist because a corrupted transcript still looks like prose.")
            return 1
        print("  [!] --force set: writing despite the failures above.")

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    stamps = [m["ts"] for m in messages if m["ts"]]
    meta = {
        "source_url": args.url,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "engine": engine,
        "messages": len(messages),
        "user_messages": sum(1 for m in messages if m["role"] == "user"),
        "assistant_messages": sum(1 for m in messages if m["role"] == "assistant"),
        "chars": sum(len(m["text"]) for m in messages),
        "html_chars": sum(len(m.get("html") or "") for m in messages),
        "first_ts": stamps[0] if stamps else None,
        "last_ts": stamps[-1] if stamps else None,
        "sha256": digest,
        "validation": "passed" if not hard else "FORCED",
    }
    meta_path = out.with_suffix(out.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print()
    print("  Messages:           %d  (%d user, %d assistant)"
          % (meta["messages"], meta["user_messages"], meta["assistant_messages"]))
    print("  Characters:         %s" % format(meta["chars"], ","))
    print("  Span:               %s -> %s" % (meta["first_ts"], meta["last_ts"]))
    print("  Engine:             %s" % engine)
    print("  Written:            %s" % out)
    print("  Metadata:           %s" % meta_path)
    print("  SHA-256:            %s" % digest[:16])
    print()
    print("  Capture verified. You can stop sharing the link now.")
    print("  Runtime: %.1fs" % (time.perf_counter() - start))

    if not args.no_pause:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

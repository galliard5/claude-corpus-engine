"""
transcript_mcp_server.py - MCP server exposing session-transcript capture.

Provides one tool:
    capture_session_transcript(share_url, campaign, session, ...)
        -> captures a public claude.ai share page to a raw JSONL archive, derives
           the readable markdown transcript from it, and returns a summary.

WHY THIS SERVER IS NATIVE, NOT IN THE DOCKER STACK
--------------------------------------------------
Capture drives a real browser, and four things rule out the compose stack:

  1. claude.ai is behind Cloudflare, which challenges headless browsers. A container
     has no display, so Chrome runs headless there by default and is blocked. Faking
     one with Xvfb is untested against the challenge and works around a problem the
     host does not have.
  2. One image serves corpus-search, index-tools and series-search - they differ only
     in `command:`. Adding a browser would bloat all three, including the two that
     mount the corpus read-only and will never use it.
  3. The containers currently reach nothing but the mounted corpus. Capture needs
     outbound HTTPS, and granting that to the shared image gives every server egress
     it does not need.
  4. The browser is already installed on the host, where headed mode works.

So this runs on the host, launched by the MCP client the way the bgm server is:

    "transcript": {
      "command": "python",
      "args": ["D:\\\\Claude\\\\filesystem\\\\Python\\\\transcript_mcp_server.py"]
    }

An MCP client reads the tool list once at connection time, so the client must be
restarted before this tool becomes callable.

Requires playwright and markdownify on the host interpreter - see the two scripts it
wraps. Deliberately absent from requirements.txt, which is baked into the container
images for something no container runs.

SECURITY POSTURE
----------------
Same shape as index_tools_mcp_server.py. The scripts are hardcoded; no parameter
accepts a filesystem path. Output locations are derived from the corpus root and a
whitelisted campaign/session, never supplied by the caller, and the campaign name is
matched against a charset that cannot express a path traversal. The share URL must
match the claude.ai share form. Subprocesses run without a shell, with stdin closed
and a bounded timeout.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"D:\Claude\filesystem"))
PYTHON_DIR = CORPUS_ROOT / "Python"
CAPTURE = PYTHON_DIR / "capture_transcript.py"
CLEAN = PYTHON_DIR / "clean_transcript.py"
RAW_ARCHIVE = CORPUS_ROOT / "World_Building" / "raw_transcript_archive"

# Path traversal is impossible through these: no separators, no dots, no colons.
SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SHARE_URL = re.compile(r"^https://claude\.ai/share/[0-9a-fA-F-]{16,64}$")

# A capture is a browser launch plus a page load; a slow cold start is normal. Bounded
# so a wedged browser cannot hang the client indefinitely.
_STEP_TIMEOUT_S = 300

mcp = FastMCP("transcript")


def _run(script, args):
    """Run one of the two known scripts. Returns (ok, combined_output)."""
    try:
        result = subprocess.run(
            [sys.executable, str(script)] + args,
            capture_output=True,
            text=True,
            timeout=_STEP_TIMEOUT_S,
            cwd=str(PYTHON_DIR),
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return False, "[!] %s timed out after %ds." % (script.name, _STEP_TIMEOUT_S)
    except Exception as e:
        return False, "[!] Could not launch %s: %s" % (script.name, e)
    out = (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")
    return result.returncode == 0, out.strip()


def _find_campaign_dir(campaign):
    """Locate World_Building/<Setting>/Scenarios/<campaign>/ without being told the setting.

    Globbed rather than parameterised: the setting is derivable, and one less
    caller-supplied path component is one less thing that can point somewhere it
    should not. Ambiguity is an error rather than a guess - picking the wrong
    campaign folder would file a session under the wrong setting silently.
    """
    matches = sorted((CORPUS_ROOT / "World_Building").glob("*/Scenarios/" + campaign))
    matches = [m for m in matches if m.is_dir()]
    if not matches:
        return None, ("No campaign folder found for %r.\n"
                      "Looked for World_Building/*/Scenarios/%s/" % (campaign, campaign))
    if len(matches) > 1:
        rel = "\n  ".join(str(m.relative_to(CORPUS_ROOT)) for m in matches)
        return None, ("%r is ambiguous - it matches several settings:\n  %s" % (campaign, rel))
    return matches[0], None


@mcp.tool()
def capture_session_transcript(
    share_url: str,
    campaign: str,
    session: str,
    in_game_date: str = "",
    location: str = "",
    keywords: str = "",
    overwrite: bool = False,
) -> str:
    """Capture a session transcript from a claude.ai share link.

    Run this at the end of a session, once the player has made the conversation
    publicly shareable and pasted the link. Ask them to stop sharing as soon as this
    reports success - the written files are the artifact; the link is only transport,
    and revoking it does not affect a capture that already succeeded.

    To share, in Claude Desktop: the share button at the upper right of the
    conversation -> select "only people invited" -> open that dropdown -> "anyone
    with the link" -> Save -> wait for it to verify -> copy link. A link that is
    still restricted redirects to sign-in and is refused, saying so.

    Writes two files:
      - the readable transcript, into the campaign's Logs/ folder
      - the raw capture, into World_Building/raw_transcript_archive/

    The raw file is the archive record and is never edited: the transcript is derived
    from it, so improvements to the cleaner can be re-applied to old sessions.

    Args:
        share_url: the https://claude.ai/share/... link, publicly shared.
        campaign: campaign folder name, e.g. "Old_Mill". Letters, digits, _ and -.
        session: zero-padded session number, e.g. "02".
        in_game_date: in-game date and time, from the checkpoint. Not derivable from
            the capture, so omitting it drops a field the transcript would otherwise
            carry.
        location: where play ended, for the header line.
        keywords: extra comma-separated tags (setting, characters, region). Use plain
            words - the search tokenizer splits on underscores and hyphens, so
            "session_2" indexes as "session" + "2" and narrows nothing.
        overwrite: replace an existing capture for this session. Off by default,
            because the raw file is the archive copy.

    Returns:
        A summary of both steps, or an error explaining what to fix.
    """
    if not SHARE_URL.match(share_url or ""):
        return ("[!] Not a claude.ai share link: %r\n"
                "    Expected https://claude.ai/share/<id>" % share_url)
    if not SAFE_NAME.match(campaign or ""):
        return "[!] Invalid campaign name %r. Letters, digits, _ and - only." % campaign
    if not SAFE_NAME.match(session or ""):
        return "[!] Invalid session %r. Letters, digits, _ and - only." % session

    if not CAPTURE.exists() or not CLEAN.exists():
        return "[!] Capture scripts not found in %s." % PYTHON_DIR

    campaign_dir, err = _find_campaign_dir(campaign)
    if err:
        return "[!] " + err

    logs_dir = campaign_dir / "Logs"
    stem = "%s_Session_%s" % (campaign, session)
    raw_path = RAW_ARCHIVE / (stem + "_raw.jsonl")
    md_path = logs_dir / (stem + "_transcript.md")

    if raw_path.exists() and not overwrite:
        return ("[!] A capture already exists for %s:\n"
                "      %s\n"
                "    Pass overwrite=true to replace it. The raw file is the archive copy,\n"
                "    so this refuses by default." % (stem, raw_path))

    RAW_ARCHIVE.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    cap_args = [share_url, "--out", str(raw_path), "--no-pause"]
    if overwrite:
        cap_args.append("--force")
    ok, cap_out = _run(CAPTURE, cap_args)
    if not ok:
        # capture_transcript.py writes nothing when it fails validation, so there is
        # no partial file to clean up here.
        return "[!] Capture failed - nothing written.\n\n%s" % cap_out

    clean_args = [str(raw_path), "--out", str(md_path),
                  "--campaign", campaign, "--session", session, "--no-pause", "--force"]
    for flag, value in (("--in-game-date", in_game_date),
                        ("--location", location),
                        ("--keywords", keywords)):
        if value:
            clean_args += [flag, value]
    ok, clean_out = _run(CLEAN, clean_args)
    if not ok:
        return ("[!] Capture succeeded but the transcript could not be built.\n"
                "    The raw archive is intact at %s - rerun the cleaner rather than\n"
                "    recapturing, and the share link can be revoked.\n\n%s"
                % (raw_path, clean_out))

    return (
        "[OK] Transcript captured. The share link can be stopped now.\n\n"
        "--- capture ---\n%s\n\n--- transcript ---\n%s\n\n"
        "Raw archive:  %s\nTranscript:   %s\n\n"
        "The raw file is the archive copy - do not edit it. Regenerate the transcript\n"
        "from it if the cleaner changes."
        % (cap_out, clean_out,
           raw_path.relative_to(CORPUS_ROOT), md_path.relative_to(CORPUS_ROOT))
    )


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))

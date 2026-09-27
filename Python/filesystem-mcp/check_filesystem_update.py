# name: Filesystem MCP Update Checker
# keywords: [filesystem, mcp, docker, version-check, update, scheduled-task]
# description: Compares the @modelcontextprotocol/server-filesystem version pinned in ./Dockerfile against npm's 'latest' dist-tag; writes UPDATE_STATUS.txt and pops a Windows notification when a newer release exists. Read-only — modifies no source files.
#
# Intended to run weekly via a Windows Scheduled Task (interactive session, so the
# notification is visible). On a newer release it pops a message box and records the
# result in UPDATE_STATUS.txt next to this script. A code-claude session then reads that
# file to drive the actual upgrade: review patch notes -> rebuild image -> retag config.
#
# While the Dockerfile carries its temporary JSON-Schema-dialect PATCH block, it also
# watches for the upstream fix that makes the patch removable: MCP TypeScript SDK PR
# modelcontextprotocol/typescript-sdk#2085 merged AND a 1.x SDK release published after
# the merge. server-filesystem depends on sdk ^1.30.0, so that release reaches us on a
# plain rebuild — no new server-filesystem version needed. Once the PATCH block is
# removed from the Dockerfile, these extra checks switch themselves off.
#
# Network: unauthenticated GETs to registry.npmjs.org (server-filesystem 'latest';
# while patched, also the @modelcontextprotocol/sdk packument) and, while patched, one
# to api.github.com (PR #2085 state). No other egress.
#
# Command line arguments:
#   --no-pause:     Skip end-of-run pause (for the scheduled/automation path)
#   --test-notify:  Fire a sample notification and exit (verify the task's UI works)
#   --quiet:        Write the status file but suppress the popup
#
# changed 2026-09-26: added the SDK schema-dialect fix watch (PR #2085 + SDK 1.x
#   release after merge), active only while the Dockerfile has its PATCH block.

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

NPM_LATEST_URL = "https://registry.npmjs.org/@modelcontextprotocol/server-filesystem/latest"
SDK_PACKUMENT_URL = "https://registry.npmjs.org/@modelcontextprotocol/sdk"
SDK_FIX_PR_URL = "https://api.github.com/repos/modelcontextprotocol/typescript-sdk/pulls/2085"
PATCH_MARKER = "PATCH (temporary)"
HERE = Path(__file__).resolve().parent
DOCKERFILE = HERE / "Dockerfile"
STATUS_FILE = HERE / "UPDATE_STATUS.txt"

DETACHED_PROCESS = 0x00000008
# MB_ICONINFORMATION | MB_SYSTEMMODAL | MB_SETFOREGROUND
MB_FLAGS = 0x40 | 0x1000 | 0x10000


def notify(title, text):
    """Pop a Windows message box in a detached process so this script can exit cleanly."""
    code = (
        "import ctypes;"
        "ctypes.windll.user32.MessageBoxW(0, %r, %r, %d)" % (text, title, MB_FLAGS)
    )
    try:
        subprocess.Popen([sys.executable, "-c", code], creationflags=DETACHED_PROCESS)
    except Exception as e:
        print(f"  (notification failed: {e})")


def parse_pinned_version():
    """Read the pinned version straight from the Dockerfile (single source of truth)."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    m = re.search(r"server-filesystem@([0-9][0-9.]*)", text)
    if not m:
        raise ValueError(f"Could not find a pinned version in {DOCKERFILE}")
    return m.group(1)


def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "filesystem-mcp-update-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def fetch_latest_version():
    return fetch_json(NPM_LATEST_URL)["version"]


def is_patched():
    return PATCH_MARKER in DOCKERFILE.read_text(encoding="utf-8")


def check_sdk_fix():
    """Return (status_line, alert_or_None) for the upstream schema-dialect fix.

    The fix counts as released once PR #2085 is merged and a stable 1.x SDK version
    was published after the merge. A PR closed without merging is also an alert: the
    fix may have landed some other way, and a human should look at issue #2084.
    """
    pr = fetch_json(SDK_FIX_PR_URL)
    if pr.get("state") == "closed" and not pr.get("merged"):
        msg = "SDK PR #2085 was CLOSED WITHOUT MERGING - check typescript-sdk#2084 by hand"
        return msg, msg
    if not pr.get("merged"):
        return "SDK fix (PR #2085): not merged yet - keep the Dockerfile PATCH", None

    merged_at = pr["merged_at"]  # ISO-8601 UTC; compares as a string against npm 'time'
    pack = fetch_json(SDK_PACKUMENT_URL, timeout=30)
    times = pack.get("time", {})
    later = [v for v in pack.get("versions", {})
             if v.startswith("1.") and "-" not in v and times.get(v, "") > merged_at]
    if not later:
        return f"SDK fix (PR #2085): merged {merged_at[:10]}, no 1.x release since", None
    newest = max(later, key=vtuple)
    msg = (f"SDK FIX RELEASED: PR #2085 merged {merged_at[:10]}, sdk {newest} published since. "
           f"Rebuild WITHOUT the Dockerfile PATCH sed and confirm the build probe passes.")
    return msg, msg


def vtuple(v):
    """Version -> comparable tuple of ints; non-numeric parts fall back to 0."""
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def write_status(checked, pinned, latest, status, extra=()):
    STATUS_FILE.write_text(
        "Filesystem MCP version check\n"
        f"Checked: {checked}\n"
        f"Pinned (running): {pinned}\n"
        f"Latest (npm):     {latest}\n"
        f"Status: {status}\n"
        + "".join(f"{line}\n" for line in extra),
        encoding="utf-8",
    )


def main():
    start = time.time()
    ap = argparse.ArgumentParser(description="Check for a newer filesystem MCP release.")
    ap.add_argument("--no-pause", action="store_true", help="Skip end-of-run pause")
    ap.add_argument("--test-notify", action="store_true", help="Fire a sample notification and exit")
    ap.add_argument("--quiet", action="store_true", help="Write status file but suppress popup")
    args = ap.parse_args()

    if args.test_notify:
        notify("Filesystem MCP", "Test notification — the scheduled check can pop a popup.")
        print("Test notification fired.")
        print(f"Runtime: {time.time() - start:.2f}s")
        return

    checked = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        pinned = parse_pinned_version()
    except Exception as e:
        print(f"ERROR reading pinned version: {e}")
        sys.exit(1)

    try:
        latest = fetch_latest_version()
    except Exception as e:
        # Transient/offline: record it, don't nag with a popup.
        print(f"Version check failed (network?): {e}")
        write_status(checked, pinned, "unknown", f"CHECK FAILED ({e})")
        print(f"Runtime: {time.time() - start:.2f}s")
        return

    alerts = []
    if vtuple(latest) > vtuple(pinned):
        status = "UPDATE AVAILABLE"
        print(f"{status}: pinned {pinned} -> latest {latest}")
        alerts.append(f"A newer @modelcontextprotocol/server-filesystem is out.\n"
                      f"Running (pinned): {pinned}\n"
                      f"Latest (npm):     {latest}")
    else:
        status = "UP TO DATE"
        print(f"{status}: pinned {pinned}, latest {latest}")

    extra = []
    if is_patched():
        try:
            line, alert = check_sdk_fix()
        except Exception as e:
            # Same policy as the npm check: record a transient failure, don't popup.
            line, alert = f"SDK fix check FAILED ({e})", None
        print(line)
        extra.append(line)
        if alert:
            alerts.append(alert)

    if alerts and not args.quiet:
        notify("Filesystem MCP update available",
               "\n\n".join(alerts)
               + "\n\nBring this to a code-claude session to review and upgrade.")

    write_status(checked, pinned, latest, status, extra)
    print(f"Status written to {STATUS_FILE}")
    print(f"Runtime: {time.time() - start:.2f}s")

    if not args.no_pause:
        input("\nPress Enter to close...")


if __name__ == "__main__":
    main()

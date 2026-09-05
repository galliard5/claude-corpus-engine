# name: Filesystem MCP Update Checker
# keywords: [filesystem, mcp, docker, version-check, update, scheduled-task]
# description: Compares the @modelcontextprotocol/server-filesystem version pinned in ./Dockerfile against npm's 'latest' dist-tag; writes UPDATE_STATUS.txt and pops a Windows notification when a newer release exists. Read-only — modifies no source files.
#
# Intended to run weekly via a Windows Scheduled Task (interactive session, so the
# notification is visible). On a newer release it pops a message box and records the
# result in UPDATE_STATUS.txt next to this script. A code-claude session then reads that
# file to drive the actual upgrade: review patch notes -> rebuild image -> retag config.
#
# Network: a single unauthenticated GET to registry.npmjs.org. No other egress.
#
# Command line arguments:
#   --no-pause:     Skip end-of-run pause (for the scheduled/automation path)
#   --test-notify:  Fire a sample notification and exit (verify the task's UI works)
#   --quiet:        Write the status file but suppress the popup

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


def fetch_latest_version():
    req = urllib.request.Request(NPM_LATEST_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    return data["version"]


def vtuple(v):
    """Version -> comparable tuple of ints; non-numeric parts fall back to 0."""
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def write_status(checked, pinned, latest, status):
    STATUS_FILE.write_text(
        "Filesystem MCP version check\n"
        f"Checked: {checked}\n"
        f"Pinned (running): {pinned}\n"
        f"Latest (npm):     {latest}\n"
        f"Status: {status}\n",
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

    if vtuple(latest) > vtuple(pinned):
        status = "UPDATE AVAILABLE"
        print(f"{status}: pinned {pinned} -> latest {latest}")
        if not args.quiet:
            notify(
                "Filesystem MCP update available",
                f"A newer @modelcontextprotocol/server-filesystem is out.\n\n"
                f"Running (pinned): {pinned}\n"
                f"Latest (npm):     {latest}\n\n"
                f"Bring this to a code-claude session to review patch notes and upgrade.",
            )
    else:
        status = "UP TO DATE"
        print(f"{status}: pinned {pinned}, latest {latest}")

    write_status(checked, pinned, latest, status)
    print(f"Status written to {STATUS_FILE}")
    print(f"Runtime: {time.time() - start:.2f}s")

    if not args.no_pause:
        input("\nPress Enter to close...")


if __name__ == "__main__":
    main()

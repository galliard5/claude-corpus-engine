# name: Schema Drift Linter
# keywords: [schema, drift, mcp, introspection, tool-schemas, lint, corpus-infra]
# description: Introspects the live MCP servers (corpus-search, index-tools, series-search over HTTP; filesystem over stdio docker) and diffs their tool/param schemas against what file_system_reference.md and the file_system_instructions.md quickref document. Read-only report — writes nothing. Prints drift lines and a checked-vs-skipped summary.
#
# Variant B of Schema_Autogen_Proposal.md. Catches the failure class that actually
# happened once already: docs describing a tool surface that doesn't match the live
# servers (wrong tool count, wrong deprecation, missing/renamed params). It changes
# nothing; a human (or a Sonnet paired-file pass) fixes the doc when it fires.
#
# Two surfaces are linted (both, per the proposal review — the quickref is loaded into
# chat context every session, so a wrong quickref actively misleads):
#   - file_system_reference.md   TOOL SCHEMA REFERENCE  (### `server:tool` + params: blocks)
#   - file_system_instructions.md  VERIFIED TOOL SCHEMAS quickref (- `server:tool` — `p`, `p?`)
# Both rely on the greppable convention locked into those files; if a doc block can no
# longer be parsed the parse-count guard surfaces it rather than silently under-reporting.
#
# NETWORK / DOCKER ACCESS (legitimate, documented exception): connects to
# localhost:8001-8003 (the compose stack's MCP endpoints) and spawns a throwaway
# `docker run` of the filesystem image to issue tools/list. No corpus files are read or
# written; the filesystem probe mounts an empty temp dir, not the real corpus.
#
# Command line arguments:
#   --no-pause:        Skip end-of-run pause (automation / rebuild-hook path)
#   --no-filesystem:   Skip the docker stdio probe (fast run; filesystem marked skipped)
#   --fs-image TAG:    Override the filesystem image to introspect (default: resolved
#                      from claude_desktop_config.json, else the filesystem-mcp Dockerfile pin)
#   --timeout SECONDS: Per-server introspection timeout (default 15)
#
# Exit codes: 0 = all servers reached and docs match; 1 = drift or parse error;
#             2 = incomplete (a server was unreachable, no drift among those reached).

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", r"D:\Claude\filesystem"))
REFERENCE_DOC = CORPUS_ROOT / "file_system_reference.md"
INSTRUCTIONS_DOC = CORPUS_ROOT / "file_system_instructions.md"
HERE = Path(__file__).resolve().parent
DOCKERFILE = HERE / "filesystem-mcp" / "Dockerfile"

# prefix -> streamable-HTTP endpoint (the compose stack)
HTTP_SERVERS = {
    "corpus-search": "http://localhost:8001/mcp",
    "index-tools": "http://localhost:8002/mcp",
    "series-search": "http://localhost:8003/mcp",
}
FS_PREFIX = "filesystem"


# --------------------------------------------------------------------------- #
# Live introspection
# --------------------------------------------------------------------------- #
def _schema_to_params(input_schema):
    """inputSchema dict -> {param_name: required_bool}."""
    schema = input_schema or {}
    props = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])
    return {name: (name in required) for name in props}


async def _http_tools(url):
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.list_tools()
            return {t.name: _schema_to_params(t.inputSchema) for t in res.tools}


async def _stdio_tools(image):
    tmp = tempfile.mkdtemp().replace("\\", "/")  # empty throwaway mount; tools/list touches no files
    params = StdioServerParameters(
        command="docker",
        args=["run", "-i", "--rm", "-v", tmp + ":/corpus", image, "/corpus"],
    )
    with open(os.devnull, "w") as devnull:  # swallow the server's stderr banner
        async with stdio_client(params, errlog=devnull) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.list_tools()
                return {t.name: _schema_to_params(t.inputSchema) for t in res.tools}


async def _introspect(fs_image, do_filesystem, timeout):
    live, reached, skipped = {}, set(), {}
    for prefix, url in HTTP_SERVERS.items():
        try:
            live[prefix] = await asyncio.wait_for(_http_tools(url), timeout)
            reached.add(prefix)
        except Exception as e:
            live[prefix] = {}
            skipped[prefix] = f"{type(e).__name__}: {e}"
    if do_filesystem:
        try:
            live[FS_PREFIX] = await asyncio.wait_for(_stdio_tools(fs_image), timeout + 20)
            reached.add(FS_PREFIX)
        except Exception as e:
            live[FS_PREFIX] = {}
            skipped[FS_PREFIX] = f"{type(e).__name__}: {e}"
    else:
        live[FS_PREFIX] = {}
        skipped[FS_PREFIX] = "skipped (--no-filesystem)"
    return live, reached, skipped


# --------------------------------------------------------------------------- #
# Doc parsing (keys off the locked greppable convention)
# --------------------------------------------------------------------------- #
_PARAM_LINE = re.compile(r"^\s+(\w+)(\?)?:\s*.+$")


def _parse_params_block(chunk):
    """Find the fenced `params:` block in a reference tool chunk -> {name: required_bool}."""
    params = {}
    for block in re.findall(r"```(.*?)```", chunk, re.S):
        if "params:" not in block:
            continue
        for line in block.splitlines():
            m = _PARAM_LINE.match(line)
            if m:
                params[m.group(1)] = not bool(m.group(2))  # required = no '?'
        break
    return params


def parse_reference(text):
    """-> ({full_name: {param: required}}, block_count)."""
    # Anchor on the real underlined section header, not the PAIRED SECTIONS map mention.
    m = re.search(r"^TOOL SCHEMA REFERENCE[ \t]*\n=+", text, re.M)
    section = text[m.start():] if m else ""
    end = section.find("\n---\n")
    if end != -1:
        section = section[:end]
    header_re = re.compile(r"^### `([\w-]+:\w+)`\s*$", re.M)
    headers = list(header_re.finditer(section))
    tools = {}
    for i, m in enumerate(headers):
        full = m.group(1)
        nxt = headers[i + 1].start() if i + 1 < len(headers) else len(section)
        tools[full] = _parse_params_block(section[m.end():nxt])
    return tools, len(headers)


def parse_quickref(text):
    """-> ({full_name: {param: required}}, line_count)."""
    # Anchor on the real '## ' header, not the PAIRED SECTIONS map mention.
    start = text.find("## VERIFIED TOOL SCHEMAS")
    section = text[start:] if start != -1 else ""
    end = section.find("\n## ")  # quickref ends at the next subsection
    if end != -1:
        section = section[:end]
    line_re = re.compile(r"^- `([\w-]+:\w+)`\s*[—–-]\s*(.*)$", re.M)
    tools, count = {}, 0
    for m in line_re.finditer(section):
        count += 1
        params = {}
        for tok in re.findall(r"`([^`]+)`", m.group(2)):
            tok = tok.strip()
            if tok.endswith("?"):
                params[tok[:-1]] = False
            else:
                params[tok] = True
        tools[m.group(1)] = params
    return tools, count


# --------------------------------------------------------------------------- #
# Compare
# --------------------------------------------------------------------------- #
def compare(surface, doc_tools, live, reached):
    """Diff a documented surface against live tools, for reachable servers only."""
    drift = []
    for prefix in sorted(reached):
        live_t = live[prefix]
        doc_t = {
            full.split(":", 1)[1]: p
            for full, p in doc_tools.items()
            if full.split(":", 1)[0] == prefix
        }
        live_names, doc_names = set(live_t), set(doc_t)
        for t in sorted(live_names - doc_names):
            drift.append(f"[DRIFT] {surface}: live tool '{prefix}:{t}' is undocumented")
        for t in sorted(doc_names - live_names):
            drift.append(f"[DRIFT] {surface}: documents '{prefix}:{t}' — not served by live {prefix}")
        for t in sorted(live_names & doc_names):
            lp, dp = live_t[t], doc_t[t]
            for p in sorted(set(lp) - set(dp)):
                drift.append(f"[DRIFT] {surface}: {prefix}:{t} — live param '{p}' undocumented")
            for p in sorted(set(dp) - set(lp)):
                drift.append(f"[DRIFT] {surface}: {prefix}:{t} — documented param '{p}' not in live schema")
            for p in sorted(set(lp) & set(dp)):
                if lp[p] != dp[p]:
                    d = "required" if dp[p] else "optional"
                    l = "required" if lp[p] else "optional"
                    drift.append(f"[DRIFT] {surface}: {prefix}:{t}.{p} — doc says {d}, live says {l}")
    return drift


def resolve_fs_image(override):
    if override:
        return override
    appdata = os.environ.get("APPDATA")
    if appdata:
        cfg = Path(appdata) / "Claude" / "claude_desktop_config.json"
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
                for a in data["mcpServers"]["filesystem"]["args"]:
                    if a.startswith("mcp/filesystem"):
                        return a
            except Exception:
                pass
    if DOCKERFILE.exists():
        m = re.search(r"server-filesystem@([0-9][0-9.]*)", DOCKERFILE.read_text(encoding="utf-8"))
        if m:
            return "mcp/filesystem:" + m.group(1)
    return "mcp/filesystem:latest"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    start = time.time()
    ap = argparse.ArgumentParser(description="Lint documented tool schemas against live MCP servers.")
    ap.add_argument("--no-pause", action="store_true")
    ap.add_argument("--no-filesystem", action="store_true", help="Skip the docker stdio probe")
    ap.add_argument("--fs-image", default=None, help="Override filesystem image tag")
    ap.add_argument("--timeout", type=float, default=15.0, help="Per-server timeout seconds")
    args = ap.parse_args()

    fs_image = resolve_fs_image(args.fs_image)
    live, reached, skipped = asyncio.run(
        _introspect(fs_image, not args.no_filesystem, args.timeout)
    )

    ref_text = REFERENCE_DOC.read_text(encoding="utf-8")
    ins_text = INSTRUCTIONS_DOC.read_text(encoding="utf-8")
    ref_tools, ref_count = parse_reference(ref_text)
    qr_tools, qr_count = parse_quickref(ins_text)

    all_drift = compare("reference", ref_tools, live, reached)
    all_drift += compare("quickref", qr_tools, live, reached)

    # ---- report ----
    print("=== Schema drift check ===")
    print(f"[IMAGE] filesystem probe: {fs_image}")
    reached_s = ", ".join(sorted(reached)) or "(none)"
    print(f"[SERVERS] reached: {reached_s}")
    for prefix, reason in sorted(skipped.items()):
        print(f"[SKIPPED] {prefix}: {reason}")
    print(f"[PARSE] reference: {ref_count} tool blocks | quickref: {qr_count} tool lines")

    parse_error = ref_count == 0 or qr_count == 0
    if parse_error:
        print("[PARSE ERROR] a documented surface yielded 0 tool blocks — convention likely broke; cannot lint")

    for line in all_drift:
        print(line)

    # ---- verdict (drift/parse-error take precedence over incomplete) ----
    if parse_error or all_drift:
        n = len(all_drift)
        print(f"[FAIL] {n} drift issue(s)" + (" + parse error" if parse_error else ""))
        code = 1
    elif skipped:
        miss = ", ".join(sorted(skipped))
        print(f"[INCOMPLETE] no drift among reached servers, but not verified: {miss} — not a clean bill")
        code = 2
    else:
        total = sum(len(live[p]) for p in reached)
        print(f"[OK] all {len(reached)} servers reached; {total} live tools match both documented surfaces")
        code = 0

    print(f"Runtime: {time.time() - start:.2f}s")
    if not args.no_pause:
        input("\nPress Enter to close...")
    sys.exit(code)


if __name__ == "__main__":
    main()

---
name: Docker Filesystem MCP
type: documentation-component
keywords: [docker, filesystem, mcp, container, dockerfile, mount, paths, restart]
description: The Docker filesystem MCP container - Dockerfile, mount layout, path conventions, and restart procedures.
---

# Docker Filesystem MCP

The standard Anthropic filesystem MCP server, packaged in Docker, serving the corpus at `/corpus`.

## Why Docker

- **Path consistency.** The container always sees the corpus at `/corpus`. Claude's tool calls always use that prefix. No "is this Windows or WSL" ambiguity.
- **Isolation.** The MCP server can't reach anything outside the bind mount. Audit boundary is the `docker-compose.yml`, not the script's `open()` calls.
- **Reproducibility.** The same Dockerfile produces the same server on any host that has Docker. If we ever distribute the framework, this becomes the install story.

The three custom Python MCP servers (`corpus-search`, `index-tools`, `series-search`) share the same image — see `Python/Dockerfile` — built and run via `Python/docker-compose.yml` as the `corpus-mcp` Compose project. The filesystem MCP itself is the upstream server and runs in its own container, launched directly from `claude_desktop_config.json` (a standalone `docker run`, not part of the compose stack).

## Building the filesystem image

The image is **built locally from `Python/filesystem-mcp/Dockerfile`**, not pulled. The published
`mcp/filesystem:latest` lagged the npm source by roughly seven releases, so pinning makes upgrades
deliberate instead of surprise `:latest` drift.

```cmd
cd D:\claude\filesystem\Python\filesystem-mcp
docker build -t mcp/filesystem:<VERSION> .
```

The Dockerfile is three lines — a `node:22-alpine` base, a global `npm install` of
`@modelcontextprotocol/server-filesystem` at the pinned version, and an entrypoint. Its header
comments carry the changelog for each bump.

**Bumping the version** has a non-obvious step:

```cmd
docker build -t mcp/filesystem:<NEW> .
docker tag mcp/filesystem:<NEW> mcp/filesystem:latest
```

**Do not pin the tag in `claude_desktop_config.json`.** Claude Desktop rewrites that entry on
restart and strips the image tag, so it always runs the untagged reference — which means the
local `:latest` tag is what actually selects the build. A rebuild alone tags only the new version
and silently leaves Desktop on the old image. Retag, then restart Desktop.

`filesystem-mcp/check_filesystem_update.py` compares the pinned version against npm and writes
`UPDATE_STATUS.txt`. Run it occasionally rather than on a schedule.

> **Relocation (2026-06-12):** `docker-compose.yml` and `.env` now live in `Python/` (the corpus-infra repo), not at the corpus root. The build context is `Python/` itself (`context: .`), and the project name is pinned to `corpus-mcp`. **Run all `docker compose` commands from `Python/`.**

> **Verified against:** Docker Desktop / Engine 29.6.1, Compose v5.3.0 (checked 2026-07-03). Update this line after checking the stack against a new Docker Desktop release — gives a quick reference point if something breaks after a host update.

## Path conventions

Two address spaces for the same file:

| Context                             | Address form                                          | Example                                       |
|-------------------------------------|-------------------------------------------------------|-----------------------------------------------|
| MCP tool calls                      | `/corpus/...` (container path)                        | `/corpus/World_Building/[Setting]/[Setting].md` |
| Windows host (git, CMD, Explorer)   | `D:\claude\filesystem\...`                            | `D:\claude\filesystem\World_Building\[Setting]\[Setting].md` |
| Obsidian vault root                 | `D:\claude\filesystem\`                               | (Obsidian sees the vault, not the container) |

**Rule:** Anywhere Claude is reading or writing via MCP tools, use `/corpus/...`. Anywhere a human is typing into CMD, a git command, or File Explorer, use `D:\claude\filesystem\...`.

## The mount

`Python/docker-compose.yml` binds the corpus root (`${CORPUS_HOST_PATH}` from `Python/.env`, i.e. `D:\claude\filesystem\`) to `/corpus` inside each container. The mount is the entire corpus root — so the container sees `Core_Rules/`, `World_Building/`, `Python/`, `index/`, etc. at the top of `/corpus`. This single mount line is the security boundary; nothing else from the host is visible. (`corpus-search` and `series-search` mount it read-only; `index-tools` mounts read-write so it can write the index files.)

## The custom-server Dockerfile

`Python/Dockerfile` builds the image used by all three custom MCP servers. (Build context is `Python/` itself, so run `docker compose build` from there.) Walkthrough:

```dockerfile
FROM python:3.12-slim
```
Slim Python base. The base layer is ~50 MB, but the image is much larger once the search dependencies are installed: `mcp`, `pyyaml`, `sqlite3` (stdlib), plus the optional vector-search stack — `sqlite-vec`, `fastembed`, and its `onnxruntime` backend — and the baked-in embedding model (~90 MB). Expect the built image to be several hundred MB.

> **Unpinned tag:** `python:3.12-slim` floats to the latest 3.12.x patch release at build time — there's no record of exactly which patch a given image was built from. Fine for this single-host personal stack (patch-level Python bumps are low-risk and getting them automatically is generally desirable), but if a rebuild ever behaves differently than expected, the base image version is the first thing to suspect and isn't currently logged anywhere. `docker inspect <container> | grep -i python` or checking image build history (`docker history`) can recover it after the fact.

```dockerfile
RUN useradd -m -u 1000 mcp
```
Non-root user. Docker Desktop on Windows handles bind-mount permissions transparently, so this doesn't get in the way of corpus read/write — it's defense in depth in case the image is ever used on Linux.

```dockerfile
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```
Dependencies installed in a separate layer from the application code, so dependency installs are cached and rebuilds only re-pip when `requirements.txt` changes.

```dockerfile
COPY search_mcp_server.py .
COPY index_tools_mcp_server.py .
COPY series_search_mcp_server.py .
COPY build_indexes.py .
COPY cfg_loader.py .
COPY embedding.py .
```
All server scripts copied (`embedding.py` is the shared vector-search helper). One image serves all three MCP servers — the `command:` in `docker-compose.yml` picks which script each container runs. (Because it's one shared image, `series-search` also carries the embedding deps it never uses — a deliberate tradeoff to avoid maintaining a second image.)

```dockerfile
ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV CORPUS_ROOT=/corpus
```

- `MCP_TRANSPORT` — `streamable-http` for Docker, `stdio` for local. The MCP framework reads this and picks the right wire format.
- `MCP_HOST=0.0.0.0` — bind on all interfaces *inside the container*. Doesn't expose to the host network; the host only sees what `docker-compose.yml` publishes.
- `MCP_PORT=8000` — overridden per service in docker-compose.
- `CORPUS_ROOT=/corpus` — both Python servers read this env var to find the corpus. The hardcoded fallback in each `.py` file (`D:\claude\filesystem`) only kicks in when running natively without Docker.

```dockerfile
USER mcp
```
Drop privileges before running the server.

```dockerfile
ENV CORPUS_EMBED_CACHE=/home/mcp/.embed_cache
RUN python -c "import embedding; embedding.AVAILABLE and embedding.get_model()"
```
Pre-download the embedding model **at build time**, as the `mcp` user, so the image is self-contained — no ~90 MB fetch on container start (the corpus mount is read-only and the container filesystem is ephemeral, so a runtime download would repeat on every restart). `CORPUS_EMBED_CACHE` is read by `embedding.py` for both this build step and runtime, so they resolve to the same baked-in path. Guarded by `embedding.AVAILABLE`, so the line is a harmless no-op if the deps are ever removed from `requirements.txt`.

No `CMD` — each service in `docker-compose.yml` sets its own.

## Restart procedure

> All `docker compose` commands below run from `Python/` (where the compose file + `.env` live; project `corpus-mcp`).

### Restart the filesystem MCP (rare)
The filesystem MCP is launched directly by Claude Desktop (`docker run` in `claude_desktop_config.json`), not by compose — so **restart Claude Desktop** to restart it. Only needed when you've changed its mount config or image version; it rarely needs touching.

### Restart a custom MCP server (container hung, or env/config change — does NOT pick up source edits)

If running in Docker (from `Python/`):
```cmd
docker compose restart corpus-search
docker compose restart index-tools
docker compose restart series-search
```
This is a process restart only. Server code is baked into the image at build time, so a plain `restart` re-reads env vars and clears a hung process but will **not** pick up edits to `search_mcp_server.py`, `index_tools_mcp_server.py`, `series_search_mcp_server.py`, or `embedding.py` — for those, use the forced rebuild below.

> **Legacy note:** an earlier version of the stack ran these servers as stdio subprocesses of Claude Desktop, where quitting and reopening the app was enough to pick up source edits. That's no longer how they run — all three are streamable-HTTP Docker services now, so a Claude Desktop restart alone does nothing for them.

### Full rebuild (after Dockerfile or requirements.txt changes)
```cmd
docker compose build
docker compose up -d
```

### Forced rebuild (after editing `search_mcp_server.py`, `index_tools_mcp_server.py`, `series_search_mcp_server.py`, or `embedding.py`)
```cmd
docker compose build --no-cache
docker compose up -d
```
Then **restart Claude Desktop** — `mcp-remote` holds its connection open and does not auto-reconnect when a container restarts; the old connection just hangs until the app is restarted.

The `--no-cache` flag is necessary because Docker caches `COPY` layers based on the upstream `RUN pip install` step. If `requirements.txt` hasn't changed, a regular `docker compose build` will reuse the cached layer and your edited `.py` files will not be copied in. Symptoms: rebuild appears to succeed but the live server still reports old paths or behaviors. `--no-cache` forces every layer to rebuild and is the only reliable way to pick up source edits.

**Exception:** `build_indexes.py` is invoked by the `index-tools` server as a subprocess against the bind-mounted host file at `/corpus/Python/build_indexes.py`. Edits to it take effect immediately, no rebuild needed. The server scripts themselves (`search_mcp_server.py`, `index_tools_mcp_server.py`) are the ones loaded from `/app/` inside the image and require the rebuild.

## Troubleshooting

**"Permission denied" on file write inside container**
Check the bind-mount permissions in `docker-compose.yml`. On Docker Desktop for Windows, the named-user UID inside the container doesn't need to match the host — the layer translates. If you see this on Linux, the host user owning `D:\claude\filesystem\` must match UID 1000 or the mount must be `:rw` with appropriate group settings.

**Container shows files but can't see recent edits**
The bind mount is real-time, not cached. If you don't see recent edits, you're probably looking at a stale `directory_index.md` rather than missing files. Run `rebuild_indexes`.

**Cross-platform path issues**
Always use forward-slash `/corpus/...` paths in MCP tool calls. Windows backslashes leak into MCP calls when copy-pasting from CMD output, and the filesystem MCP rejects them.

**Custom MCP server "tool not found" errors**
The server didn't start. Check `claude_desktop_config.json` for the right command, and check `requirements.txt` is satisfied. `python --version` must be 3.10+ (3.12 in the Docker image).

**A filesystem call hangs for minutes (looks like the MCP server is unresponsive — it isn't)**
Symptom: a single `filesystem:*` call returns no result after several minutes, and subsequent calls — even trivial ones like `get_file_info` — also hang the same way. Only a Claude Desktop restart clears it.

Two observed instances, and they do **not** share a trigger:

| Date | Call | Payload |
|---|---|---|
| 2026-07-03 | `write_file` | large **input** — low tens of KB of content being sent |
| 2026-09-04 | `read_text_file` | small input, large expected **output** — a 210-line tail |

Diagnosis (from the 2026-07-03 incident, confirmed against Claude Desktop's transport logs and `docker logs`): **the Docker container and filesystem server are not involved.** The hung calls never reached the MCP transport at all — every request the server actually received during the incident was answered in milliseconds. The stall is in Claude Desktop's **tool-approval layer**, upstream of MCP: the call sits waiting on an approval prompt that never renders (or is never noticed), which from the chat side is indistinguishable from an infinite timeout. Follow-up calls queue behind the same stuck gate, which is why a tiny `get_file_info` "hangs" too — it's not size-dependent at the transport.

> **⚠ The buffered-input explanation is narrower than the failure.** The 2026-07-03 write was attributed to a large streamed tool *input* taking a buffered-input path (`hasBufferedInput: true` in the app's `tool_approval_gate` entries) that trips the gate. The 2026-09-04 read had a *small* input and never went near that path, yet presented identically and cleared the same way. So buffered input is at most one route to a stuck approval gate, not the cause of the class. Treat "large input" as a correlation worth avoiding, not a diagnosis — and don't rule the failure out just because a call's input is small.

Where to look for evidence: `%APPDATA%\Claude\logs\mcp-server-filesystem.log` logs every message that reaches the transport — a hung call that's genuinely wedging the server shows a `tools/call` with no matching result; a call stuck at the approval gate shows **nothing at all**. The chat window log (`claude.ai-web.log`) logs `tool_approval_gate` entries with `approvalRequired`/`hasBufferedInput` flags.

> **⚠ This evidence path is currently dead (checked 2026-09-04).** Nothing in `%APPDATA%\Claude\logs\` has been written since **2026-08-20**, although Desktop is running and writing `config.json`, `sentry/`, and `Network/` the same day. Every MCP server log stopped together, so this is Desktop-side, not a per-server fault; there is no logging toggle in `config.json` or `claude_desktop_config.json`, which points at a Desktop update between 2026-08-20 and 2026-09-04. **Consequence: the 2026-09-04 incident could not be confirmed against transport logs the way the 2026-07-03 one was, and no incident can be until logging is restored.** Re-check whether logs resume after the next Desktop update before relying on the steps above.

**Fix, in order:**
1. Check for an unanswered approval prompt in the chat UI first — that's the actual blocker.
2. If none is visible, restart **Claude Desktop** (this resets the approval state and relaunches the filesystem container). Restarting Docker or the container does nothing for this failure — the container was never stuck.
3. Re-verify with a small call. Don't immediately retry the one that hung.
4. For a large write, apply the change as several smaller `filesystem:edit_file` calls instead of one full-file rewrite — recommended for any full-file rewrite over roughly 10–15 KB. For a large read, request a narrower range. Both reduce exposure; neither is a guaranteed dodge, given the 2026-09-04 case.

See also `Troubleshooting.md` for cross-component issues.

# Pinned build of the upstream MCP filesystem server (@modelcontextprotocol/server-filesystem).
#
# Replaces the Docker-published `mcp/filesystem:latest`, which lagged the npm source
# by ~7 releases (was built from source branch 2025.4.24 / published 2025-06-16).
# This pins the current release so upgrades are deliberate, not surprise `:latest` drift.
#
# Build (run from this directory):
#   docker build -t mcp/filesystem:2026.8.31-schema2020 .
#   docker tag mcp/filesystem:2026.8.31-schema2020 mcp/filesystem:latest
#
# Used by the "filesystem" MCP entry in claude_desktop_config.json as a per-session
# `docker run --rm` stdio server. Deliberately kept standalone (not in the corpus-mcp
# compose stack): ephemeral container isolation suits stateless, security-sensitive
# third-party file ops better than an always-on HTTP service would.
#
# To bump: change the pinned version below, rebuild with the matching tag, then
# RETAG THE LOCAL :latest at it and restart Claude Desktop:
#   docker build -t mcp/filesystem:<NEW> .
#   docker tag mcp/filesystem:<NEW> mcp/filesystem:latest
# Do NOT pin the tag in claude_desktop_config.json — Desktop rewrites that entry on
# restart and strips the image tag, so it always runs the untagged reference. The
# local :latest tag is what actually selects the build; a rebuild alone tags only
# the version and leaves Desktop on the old image.
#
# changed 2026-08-10: bumped 2026.1.14 -> 2026.7.10 (edit_file literal-$ corruption
#   fix #4225, security dep bump diff ^5->^8, read_media_file content-type fix,
#   openWorldHint:false on all 14 tools); corrected the stale bump instructions above.
# changed 2026-09-04: bumped 2026.7.10 -> 2026.8.31, the only release in between.
#   Dependency-led rather than feature-led: MCP SDK ^1.29 -> ^1.30 and glob ^10.5
#   -> ^13.0 (a two-major jump in the path matcher, the one thing here worth
#   watching). Upstream also moved to LF Projects, changing the package author and
#   license fields. Tool surface verified unchanged post-build via
#   check_schema_drift.py, which is the check that actually matters for the docs.
# changed 2026-09-26: local patch so tools/list declares JSON Schema 2020-12, not
#   draft-07 (built and tagged as 2026.8.31-schema2020). See the PATCH block below.
#
# PATCH (temporary) — JSON Schema dialect.
#   MCP clients shipped around 2026-09-26 validate tool schemas with a 2020-12-only
#   validator and reject every tool that declares "$schema": draft-07, so all 14
#   tools failed with "invalid outputSchema ... unsupported dialect". The fault is in
#   the MCP TypeScript SDK v1, not in this server: its tools/list code never passes a
#   target to toJsonSchemaCompat(), and mapMiniTarget() falls back to 'draft-7'.
#   Upstream: modelcontextprotocol/typescript-sdk#2084 (fix PR #2085) and
#   modelcontextprotocol/servers#4841. We flip that fallback to 'draft-2020-12' —
#   the dialect the 2025-11-25 spec makes the default. The keywords emitted
#   (type/properties/required/additionalProperties/enum/anyOf...) mean the same in
#   both dialects, so only the declared URI changes.
#   The build-time probe after the sed is the real guard: it fails the build if any
#   tool still declares draft-07, so an SDK change that moves the code cannot leave
#   a silently unpatched image.
#   REMOVE when: an SDK release containing #2085 is out. server-filesystem pins
#   @modelcontextprotocol/sdk ^1.30.0, so a plain rebuild picks that up with no new
#   server release; drop the sed, keep the probe. check_filesystem_update.py watches
#   for it.

FROM node:22-alpine
RUN npm install -g @modelcontextprotocol/server-filesystem@2026.8.31
RUN set -e; \
    SDK=/usr/local/lib/node_modules/@modelcontextprotocol/server-filesystem/node_modules/@modelcontextprotocol/sdk/dist; \
    for f in "$SDK/esm/server/zod-json-schema-compat.js" "$SDK/cjs/server/zod-json-schema-compat.js"; do \
        sed -i "/if (!t)/{n;s/return 'draft-7';/return 'draft-2020-12';/}" "$f"; \
    done; \
    printf '%s\n' \
      '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"build-probe","version":"0"}}}' \
      '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
      '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
      | timeout 20 mcp-server-filesystem /tmp > /tmp/tools.json 2>/dev/null || true; \
    grep -q '"tools"' /tmp/tools.json || { echo "PROBE FAILED: no tools/list response"; exit 1; }; \
    if grep -q 'draft-07' /tmp/tools.json; then echo "PROBE FAILED: tools/list still declares draft-07"; exit 1; fi; \
    echo "PROBE OK: no draft-07 in tools/list"; rm /tmp/tools.json
ENTRYPOINT ["mcp-server-filesystem"]

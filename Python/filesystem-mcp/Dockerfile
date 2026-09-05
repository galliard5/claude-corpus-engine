# Pinned build of the upstream MCP filesystem server (@modelcontextprotocol/server-filesystem).
#
# Replaces the Docker-published `mcp/filesystem:latest`, which lagged the npm source
# by ~7 releases (was built from source branch 2025.4.24 / published 2025-06-16).
# This pins the current release so upgrades are deliberate, not surprise `:latest` drift.
#
# Build (run from this directory):
#   docker build -t mcp/filesystem:2026.8.31 .
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

FROM node:22-alpine
RUN npm install -g @modelcontextprotocol/server-filesystem@2026.8.31
ENTRYPOINT ["mcp-server-filesystem"]

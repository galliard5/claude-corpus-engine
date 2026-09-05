# Dockerfile for custom Python MCP servers:
#   corpus-search (search_mcp_server.py)
#   index-tools   (index_tools_mcp_server.py)
#
# Both servers share this image. The docker-compose.yml selects which
# script to run per container via the `command` override.
#
# Build context is ./Python — all COPY paths are relative to that directory.
# The corpus itself is NOT baked into the image; it arrives as a bind mount
# at /corpus at runtime (see docker-compose.yml).

FROM python:3.12-slim

# Create a non-root user. Docker Desktop on Windows handles bind-mount
# permissions transparently, so this doesn't affect corpus read/write.
RUN useradd -m -u 1000 mcp

WORKDIR /app

# Install dependencies first (separate layer — only rebuilds on requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application scripts
COPY search_mcp_server.py .
COPY index_tools_mcp_server.py .
COPY series_search_mcp_server.py .
COPY build_indexes.py .
COPY cfg_loader.py .
COPY embedding.py .

# Switch to non-root user for runtime
USER mcp

# Pre-download the embedding model so the image is self-contained — no ~90MB
# fetch on container start (the corpus mount is read-only and the container fs
# is ephemeral). Runs as mcp so the cache is owned by the runtime user.
# CORPUS_EMBED_CACHE is read by embedding.py for both this build step and runtime.
# If fastembed/sqlite-vec aren't installed (requirements pin them, so they are),
# this is a no-op guarded by embedding.AVAILABLE.
ENV CORPUS_EMBED_CACHE=/home/mcp/.embed_cache
RUN python -c "import embedding; embedding.AVAILABLE and embedding.get_model()"

# Runtime defaults — all overridable via docker-compose environment section.
# MCP_TRANSPORT: stdio (local) | streamable-http (Docker)
# MCP_HOST:      which interface to bind (0.0.0.0 = all interfaces in container)
# MCP_PORT:      HTTP port (set per-service in docker-compose)
# CORPUS_ROOT:   path to corpus inside container (set in docker-compose)
ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV CORPUS_ROOT=/corpus

# No CMD here — each service in docker-compose sets its own command.

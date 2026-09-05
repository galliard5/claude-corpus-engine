---
name: System Troubleshooting
type: documentation-reference
keywords: [troubleshooting, stale_index, mcp_restart, search_empty, hygiene, corrupted_db]
description: Cross-component issues for the corpus infrastructure - symptoms, diagnoses, and fixes.
---

# Troubleshooting

Cross-component issues. For single-file problems see the relevant component doc (`Indexer.md`, `Search_Server.md`, `Docker_Filesystem.md`).

## Symptom: predicted path doesn't exist

**Diagnosis** — `directory_index.md` is stale. Files moved or renamed since the last rebuild.

**Fix:**
```
index-tools:rebuild_indexes(load="directory")
```
The fresh directory tree comes back in the same response.

If a single `rebuild_indexes` doesn't help and the file genuinely should exist, run:
```
filesystem:search_files(path="/corpus", pattern="*partial_filename*")
```
The exact name may have a suffix you didn't expect (`_Specific`, `_Final`, etc.).

## Symptom: search_corpus returns empty for content that should obviously exist

**Diagnosis** — Either the search index is stale, or the search index doesn't cover the directory the file lives in (see `Indexer.md` for `[search_index]` exclusions).

**Fix:**
```
index-tools:rebuild_indexes(load="search_status")
```
Check the file count and last-built timestamp. If the count is way lower than expected, the cfg may have changed what's indexed.

If the file is under `Trash/`, `Python/`, or any directory listed in the `[search_index]` exclusions in `indexer.cfg`, it is **not** indexed by design. Use `filesystem:search_files` instead.

## Symptom: search_corpus returns FTS5 syntax errors

**Diagnosis** — Query contains a character FTS5 treats as special.

**Common offenders:**
- Apostrophes (single quotes) — `Keller's` tokenizes oddly
- Hyphens — `setting-document` searches as `setting AND document`
- Colons — FTS5 reads these as column prefixes

**Fix:**
- Wrap problem terms in double quotes: `search_corpus('"Keller\'s"')` (escape the single quote in your client too)
- Use prefix matching: `search_corpus("Keller*")`
- For typed values use `type_filter` instead of putting the value in `query`

## Symptom: type_filter returns nothing for a value that exists

**Diagnosis** — `type_filter` is case-sensitive exact match. `type_filter="setting"` will not match `type: setting-document`.

**Fix:**
- Confirm the exact `type:` value in the file's frontmatter
- Use the full value
- If files have inconsistent type values (`character` vs `character-sheet`), pick one and run `missing_filter="type"` then standardize

## Symptom: missing_filter returns unexpected files

**Diagnosis** — A file has frontmatter but a field is empty (`type:` with nothing after the colon) — empty counts as missing.

**Fix:**
- Open the file and check frontmatter carefully
- Empty values are intentional in this scheme; the field exists but isn't useful for filtering until populated

## Symptom: Claude can't call search_corpus or rebuild_indexes after a server source edit

**Diagnosis** — The custom MCP servers (`search_mcp_server.py`, `index_tools_mcp_server.py`, `series_search_mcp_server.py`) run as streamable-HTTP Docker services with the source baked into the image at build time. Neither a Claude Desktop restart nor a plain `docker compose restart` picks up source edits — the image itself has to be rebuilt.

**Fix (from `Python/`):**
```cmd
docker compose build --no-cache
docker compose up -d
```
Then restart Claude Desktop — `mcp-remote` doesn't auto-reconnect when a container restarts, so the old connection hangs until the app restarts. See `Docker_Filesystem.md` > Restart procedure for the full breakdown of when a plain `restart` is enough versus when a rebuild is required.

## Symptom: search_index.db gets corrupted

Rare. Symptoms: `sqlite3.DatabaseError` from `search_corpus`, or `index_status` reporting a count of zero when the corpus is clearly full.

**Fix:**
```cmd
D:
cd D:\claude\filesystem\index
del search_index.db
cd ..\Python
python build_indexes.py --no-pause
```

The DB is fully derived — there's no data loss from deleting and rebuilding.

## Symptom: rebuild fails with PermissionError or 'attempt to write a readonly database'

**Diagnosis** — Multi-container UID mismatch. The `index/` directory or `search_index.db` was created by a different container's user (often the filesystem MCP running as root via supergateway) and `index-tools` runs as `mcp` (UID 1000) which can't overwrite files it doesn't own.

Symptoms in the rebuild output:
```
PermissionError: [Errno 13] Permission denied: '/corpus/index/directory_index.md'
sqlite3.OperationalError: attempt to write a readonly database
```

**Fix:** Delete the entire `index/` directory and let `index-tools` recreate it as its own user.

```cmd
D:
cd D:\claude\filesystem
move index Trash\old_index
```

Then trigger any rebuild (via Claude calling `rebuild_indexes` or by running `python Python\build_indexes.py --no-pause` from CMD). The script's `mkdir(parents=True, exist_ok=True)` will create the directory fresh as the right user. The contents will be regenerated by the same run.

This only happens when the `index/` directory was created from outside its owning container — typically a one-time issue during initial setup or after moving artifacts manually via the filesystem MCP.

## Symptom: BIOS check warns of mirror drift

```
📝 Project-instructions copy of file_system_instructions.md is older than disk version
```

**Diagnosis** — The on-disk `file_system_instructions.md` was edited but the project-instructions copy in Claude's context wasn't re-mirrored.

**Fix:**
- Read `/corpus/file_system_instructions.md` in full
- Update the project's instructions in Claude.ai project settings
- Confirm the **Last edited (UTC)** line just below the frontmatter matches. It lives in the body, not the frontmatter, because the project-instructions paste discards frontmatter — a mirror without it makes the check unfalsifiable rather than merely wrong.

## Hygiene queries

Useful corpus-wide quality checks. Run periodically.

**Find all files missing a type field:**
```
search_corpus("*", missing_filter="type", limit=50)
```

**Find all files missing a description:**
```
search_corpus("*", missing_filter="description", limit=50)
```

**Find all character files (verify the type system is consistent):**
```
search_corpus("*", type_filter="character", limit=50)
```

**Find character files missing keywords:**
```
search_corpus("*", type_filter="character", missing_filter="keywords")
```

**Find files in one subtree that haven't been categorized yet:**
```
search_corpus("*", category_filter="[Subtree]", missing_filter="type")
```

## When the indexer itself is broken

If `build_indexes.py` fails outright:

1. Run it from CMD with full output:
   ```cmd
   cd D:\claude\filesystem\Python
   python build_indexes.py
   ```
2. Check the stdout for the failing file's path.
3. Most failures are encoding issues — a corpus file that's neither UTF-8 nor latin-1. Open it in an editor and re-save as UTF-8.
4. If `cfg_loader.py` warns about malformed cfg lines, fix the cfg before rebuilding.

For deeper indexer issues see `Indexer.md`. For DB-specific issues see `Search_Server.md`. For Docker container issues see `Docker_Filesystem.md`.

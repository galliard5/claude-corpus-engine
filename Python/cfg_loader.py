#!/usr/bin/env python3
"""
cfg_loader.py — Generic .cfg file parser.

Parses configuration files in the indexer.cfg format:
  - [section] headers
  - key = value pairs   (values are auto-typed: int, ('line', N), or str)
  - bare pattern lines  (any line without '=')
  - # comments          (full-line and inline)

Returns a dict of sections. Each section contains:
  "settings"  -> dict of key -> typed value
  "patterns"  -> list of bare pattern strings (comments stripped)

This module is format-aware but application-agnostic. It has no knowledge of
what specific section names, keys, or patterns mean — interpretation is left
entirely to the calling script.

Usage:
    from cfg_loader import load_cfg

    cfg = load_cfg("myprogram.cfg")
    mode    = cfg["section_name"]["settings"].get("mode", "blacklist")
    patterns = cfg["section_name"]["patterns"]

If the same section name appears more than once in the file, the sections are
merged: later key=value pairs override earlier ones, and patterns are
accumulated in order.

Malformed lines are skipped with a printed warning rather than raising, so a
typo in the cfg does not abort a long-running build. FileNotFoundError is the
one exception that always propagates — there is nothing meaningful to do if
the cfg itself is missing.

Run directly to inspect a parsed cfg:
    python cfg_loader.py path/to/file.cfg
"""

import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Type aliases (documentation only — Python does not enforce these at runtime)
# ---------------------------------------------------------------------------

# A parsed value is one of: int | ('line', int) | str
# A Section is:  {"settings": dict[str, value], "patterns": list[str]}
# A Config is:   dict[str, Section]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_comment(line: str) -> str:
    """
    Remove an inline # comment and trailing whitespace.

    Splits on the first '#' and discards everything from that point on.
    The left side is stripped of trailing whitespace before returning.

        'Trash/*.*       # visible in tree'  ->  'Trash/*.*'
        '# full comment line'                ->  ''
        'mode = blacklist'                   ->  'mode = blacklist'

    Limitation: a literal '#' inside a value (e.g. root_directory = D:\\some#path)
    would be incorrectly treated as a comment start, truncating the value.
    Windows paths never contain '#' in practice, so this is not a real concern
    for this codebase — but don't use this parser for configs that need '#' in values.
    """
    return line.split("#")[0].rstrip()


def _parse_value(raw: str):
    """
    Auto-type a value string from a key = value pair.

    Conversion priority:
        1. Plain integer  — returned as int
                            e.g.  "-1"  ->  -1
                                  "0"   ->  0
                                  "4"   ->  4
        2. line_N         — returned as the tuple ('line', N)
                            e.g.  "line_8"  ->  ('line', 8)
                            Case-insensitive match on the 'line_' prefix.
        3. Anything else  — returned as a stripped string
                            e.g.  "blacklist"  ->  'blacklist'
                                  "D:\\path"   ->  'D:\\path'
    """
    s = raw.strip()

    # 1. Plain integer
    try:
        return int(s)
    except ValueError:
        pass

    # 2. line_N sentinel
    match = re.match(r"^line_(\d+)$", s, re.IGNORECASE)
    if match:
        return ("line", int(match.group(1)))

    # 3. String passthrough
    return s


def _empty_section() -> dict:
    """Return a fresh, empty section dict."""
    return {"settings": {}, "patterns": []}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_cfg(path) -> dict:
    """
    Parse a .cfg file and return a Config dict.

    Parameters
    ----------
    path : str or Path
        Path to the .cfg file to parse.

    Returns
    -------
    dict
        Keys are lowercased section names. Each value is a dict:
            {
                "settings": { key: typed_value, ... },
                "patterns": [ pattern_str, ... ]
            }
        Sections that appear more than once in the file are merged.
        An empty dict is returned if the file contains no valid sections.

    Raises
    ------
    FileNotFoundError
        If the file does not exist. All other errors produce a warning and
        continue rather than raising.
    """
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"cfg_loader: file not found: {cfg_path}")

    config: dict = {}
    current_section: str | None = None
    warnings: list[str] = []

    with cfg_path.open(encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):

            # Strip newline only — preserve internal spaces for now
            line = raw_line.rstrip("\n")

            # Remove inline comment, then strip surrounding whitespace
            line = _strip_comment(line).strip()

            # Skip blank lines (includes lines that were pure comments)
            if not line:
                continue

            # ------------------------------------------------------------------
            # Section header: [section_name]
            # ------------------------------------------------------------------
            if line.startswith("["):
                if not line.endswith("]"):
                    warnings.append(
                        f"  Line {lineno}: malformed section header "
                        f"(missing ']'), skipped — {raw_line.rstrip()!r}"
                    )
                    continue

                name = line[1:-1].strip().lower()

                if not name:
                    warnings.append(
                        f"  Line {lineno}: empty section name, "
                        f"skipped — {raw_line.rstrip()!r}"
                    )
                    continue

                current_section = name
                # Merge if the section already exists (seen earlier in the file)
                if current_section not in config:
                    config[current_section] = _empty_section()
                continue

            # ------------------------------------------------------------------
            # Content before any section header
            # ------------------------------------------------------------------
            if current_section is None:
                warnings.append(
                    f"  Line {lineno}: content before first section header, "
                    f"skipped — {raw_line.rstrip()!r}"
                )
                continue

            section = config[current_section]

            # ------------------------------------------------------------------
            # Key = value pair
            # ------------------------------------------------------------------
            if "=" in line:
                key, _, raw_value = line.partition("=")
                key = key.strip()

                if not key:
                    warnings.append(
                        f"  Line {lineno}: empty key in key=value pair, "
                        f"skipped — {raw_line.rstrip()!r}"
                    )
                    continue

                section["settings"][key] = _parse_value(raw_value)
                continue

            # ------------------------------------------------------------------
            # Bare pattern line
            # ------------------------------------------------------------------
            section["patterns"].append(line)

    # Print all warnings as a block after parsing completes
    if warnings:
        print(f"[cfg_loader] {len(warnings)} warning(s) in {cfg_path.name}:")
        for w in warnings:
            print(w)

    return config


# ---------------------------------------------------------------------------
# CLI — run directly to inspect a parsed cfg file
# ---------------------------------------------------------------------------

def _pretty_print(config: dict, source: str) -> None:
    """Print a parsed config in a readable format."""
    print()
    print(f"Parsed: {source}")
    print(f"Sections: {len(config)}")
    print("=" * 60)

    if not config:
        print("  (no sections found)")
        return

    for section_name, section in config.items():
        print(f"\n[{section_name}]")

        settings = section["settings"]
        patterns = section["patterns"]

        if settings:
            print("  Settings:")
            for key, value in settings.items():
                print(f"    {key!r:20s} = {value!r}")

        if patterns:
            print("  Patterns:")
            for p in patterns:
                print(f"    {p!r}")

        if not settings and not patterns:
            print("  (empty section)")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python cfg_loader.py path/to/file.cfg")
        sys.exit(1)

    target = Path(sys.argv[1])

    try:
        result = load_cfg(target)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    _pretty_print(result, str(target))

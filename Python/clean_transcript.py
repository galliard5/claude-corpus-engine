# name: Clean Transcript
# keywords: [transcript, cleanup, session, markdown, ooc, strip, archive]
# description: Derives a readable markdown session transcript from the raw JSONL produced by
#              capture_transcript.py — strips choice menus, OOC asides and tool-call markers,
#              flags likely breaks in play from timestamp gaps, and reports what it removed.
#
# Requires: markdownify (`python -m pip install markdownify`) to convert the captured HTML back
# to markdown. Without it the script falls back to the capture's lossy plain-text field and says
# so. Host-side only — deliberately NOT in Python/requirements.txt, which is baked into the
# Docker image; no container runs this.
#
# The second half of the transcript pipeline. capture_transcript.py writes the raw, verbatim
# JSONL; this derives the readable artifact from it. The raw file is never modified, so this can
# be re-run whenever the strip rules improve — which is the whole reason the raw is archived
# rather than cleaned in place.
#
# STRIP, DON'T REWRITE. Deleting a passage is safe; editing prose destroys the exact thing the
# transcript exists for. Every rule here is a high-confidence mechanical pattern. Anything
# ambiguous is deliberately left in: over-curation costs more than clutter, and a reader can skip
# noise but cannot recover something silently removed.
#
# HEADING LEVELS ARE A RETRIEVAL CONTRACT, not formatting:
#
#   #     document title
#   ##    scene   - promoted from the GM's `[ Scene: where - who ]` tag; the names after the
#                   dash are the witness list the Information Firewall reads back
#   ###   turn    - the practical get_section unit
#   ####+ the GM's own headings, demoted two levels to stay clear of both
#
# Turns are headings because scenes are too coarse to retrieve: measured on a real session a
# scene averages ~9,000 tokens - the size get_section exists to avoid - while one turn is
# ~1,200. Scene headings are never invented here; an absent tag means the GM wrote none, which
# is reported rather than guessed, because fabricating a witness list would license an NPC to
# know something nobody saw. Timestamp gaps are offered only as *candidate* breaks, and they
# mark when play stopped, which is not the same as where a scene ended.
#
# Command line arguments:
#   <raw.jsonl>              raw capture from capture_transcript.py (required)
#   --out <path>             output .md path (required)
#   --campaign <name>        campaign name for the frontmatter
#   --session <NN>           session number for the frontmatter
#   --gap-minutes N          flag a candidate break after this real-time gap (default: 360,
#                            i.e. 6h — measured against real play, this separates within-sitting
#                            pauses from returning another day; median turn gap is single digits)
#   --menu-min N             minimum consecutive numbered options to treat a run as a GM
#                            choice menu (default: 3 — core_rules mandates 3-5 options)
#   --in-game-date <text>    in-game date/time for the frontmatter. Not derivable from the
#                            capture - carry it over from the checkpoint or the prior stub,
#                            or it is silently lost on regeneration.
#   --location <text>        where play ended, for the header line
#   --keywords a,b,c         extra frontmatter keywords (setting, characters, region...).
#                            Use plain words: FTS5 splits on _ and -, so "session_2" is
#                            indexed as "session"+"2" and narrows nothing.
#   --keep-heading-levels    leave GM heading levels alone (default demotes by two, so
#                            ## stays the scene and ### stays the turn)
#   --keep-tools             keep tool-invocation markers instead of stripping them
#   --force                  overwrite an existing output file
#   --no-pause               skip the end-of-run pause (set this in automation)

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from markdownify import markdownify as _html_to_md
except ImportError:
    _html_to_md = None


def to_markdown(msg):
    """Prefer the archived HTML; fall back to the lossy text field.

    The `html` field is the record of what the GM actually wrote. Rendering flattens markdown
    - headings, emphasis, rules, tables and link hrefs all disappear from innerText - so a
    transcript built from `text` silently discards authorial structure. Captures made before
    the html field existed still work, at reduced fidelity.
    """
    html = msg.get("html")
    if html and _html_to_md is not None:
        md = _html_to_md(html, heading_style="ATX", bullets="-")
        return re.sub(r"\n{3,}", "\n\n", md).strip()
    return (msg.get("text") or "").strip()

# A GM-offered menu: 4+ consecutive lines numbered from 1. These are options presented to the
# player, not play that happened. Anchored to a run starting at "1." so an in-prose enumeration
# ("1. flour 2. salt") inside a single line is not caught.
CHOICE_LINE_RE = re.compile(r"^\s*(\d+)\.\s+\S")

# Out-of-character asides, e.g. *(OOC — the BGM server dropped)*. Requires the OOC marker
# explicitly; italicised prose alone is never treated as OOC.
OOC_RE = re.compile(r"^\s*[*_]*\(\s*OOC\b.*?\)[*_]*\s*$", re.I)
OOC_INLINE_RE = re.compile(r"[*_]*\(\s*OOC\b[^)]*\)[*_]*", re.I)

# Tool invocation chrome rendered into the share page. Observed forms in real captures are
# "Used 2 tools" (6), "Used 3 tools" (3) and "Used 3 tools, loaded tools" (1) - the suffix is
# the exception, so it must be optional. Anchored both ends so prose like "he used 2 tools to
# force the lock" is never stripped.
TOOL_RE = re.compile(r"^\s*Used \d+ tools?(?:,? [a-z ]+)?\s*$", re.I)

# A scene heading written by the GM during play: "## Scene: the mill yard - warden, steward".
# Accepts any heading level and a missing space, because this is a rule a model follows by hand
# and near-misses should be recovered rather than silently demoted into ordinary prose headings.
# Normalised to exactly "## Scene:" on output.
SCENE_RE = re.compile(r"^#{1,6}\s*Scene\s*:", re.I | re.M)

# The preferred in-play form. GM turns already open with a bracketed status block rendered as
# inline code, after a rule:
#
#     `[ Time: first light ]`
#     `[ Status: Injured (moderate) · Tired ]`
#
# (29 of each across 32 GM turns in the measured session.) A scene tag belongs there rather than
# in the prose: it inherits an established habit, stays out of the narration, and needs no new
# syntax. It is promoted to a real `## Scene:` heading here, because retrieval splits on `##`
# and inline code is invisible to that.
BRACKET_SCENE_RE = re.compile(r"^[ \t]*`?\[\s*Scene\s*:\s*(.+?)\s*\]`?[ \t]*$", re.I | re.M)

ROLE_LABEL = {"user": "Player", "assistant": "GM"}


def strip_message(text, keep_tools, is_gm, menu_min):
    """Return (cleaned_text, counts). Removes whole lines only; never rewrites prose."""
    # Choice menus are GM-offered options. A numbered run in a player turn is the player
    # writing a list, so menu stripping is restricted to GM turns.
    if not is_gm:
        menu_min = 10 ** 6
    counts = {"choice_menus": 0, "ooc": 0, "tools": 0}
    lines = text.split("\n")
    keep = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # A numbered menu: look ahead for a run of >=4 consecutive numbered lines starting at 1.
        m = CHOICE_LINE_RE.match(line)
        if m and m.group(1) == "1":
            run = 0
            expect = 1
            j = i
            while j < len(lines):
                mj = CHOICE_LINE_RE.match(lines[j])
                if mj and int(mj.group(1)) == expect:
                    run += 1
                    expect += 1
                    j += 1
                elif not lines[j].strip() and run:
                    break
                else:
                    break
            if run >= menu_min:
                counts["choice_menus"] += 1
                i = j
                continue

        if OOC_RE.match(line):
            counts["ooc"] += 1
            i += 1
            continue

        if not keep_tools and TOOL_RE.match(line):
            counts["tools"] += 1
            i += 1
            continue

        # An OOC aside sharing a line with prose: remove the aside, keep the prose.
        if OOC_INLINE_RE.search(line):
            stripped = OOC_INLINE_RE.sub("", line).strip()
            if stripped:
                counts["ooc"] += 1
                keep.append(stripped)
                i += 1
                continue
            counts["ooc"] += 1
            i += 1
            continue

        keep.append(line)
        i += 1

    out = "\n".join(keep)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out, counts


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description="Derive a markdown transcript from raw capture JSONL.")
    ap.add_argument("raw")
    ap.add_argument("--out", required=True)
    ap.add_argument("--campaign", default="")
    ap.add_argument("--session", default="")
    ap.add_argument("--gap-minutes", type=int, default=360)
    ap.add_argument("--menu-min", type=int, default=3)
    ap.add_argument("--keep-heading-levels", action="store_true")
    ap.add_argument("--in-game-date", default="")
    ap.add_argument("--location", default="")
    ap.add_argument("--keywords", default="",
                    help="extra comma-separated tags, e.g. setting and character names")
    ap.add_argument("--keep-tools", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-pause", action="store_true")
    args = ap.parse_args()

    start = time.perf_counter()

    raw_path = Path(args.raw)
    if not raw_path.exists():
        print("[!] Raw capture not found: %s" % raw_path)
        return 2

    out = Path(args.out)
    if out.exists() and not args.force:
        print("[!] Output already exists: %s" % out)
        print("    Use --force to regenerate it from the raw capture.")
        return 2

    messages = []
    for lineno, line in enumerate(raw_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError as e:
            print("[!] %s line %d is not valid JSON: %s" % (raw_path, lineno, e))
            return 1
    if not messages:
        print("[!] %s contains no messages." % raw_path)
        return 1

    demote = not args.keep_heading_levels
    turn_width = max(2, len(str(len(messages))))
    totals = {"choice_menus": 0, "ooc": 0, "tools": 0}
    scene_markers = 0
    bracket_promoted = 0
    dropped_empty = 0
    body = []
    prev_dt = None
    breaks = 0

    html_used = sum(1 for m in messages if m.get("html"))
    if html_used and _html_to_md is None:
        print("[!] This capture has HTML but markdownify is not installed.")
        print("    Run: python -m pip install markdownify")
        print("    Without it the transcript loses headings, emphasis, rules and tables.")
        return 1

    for m in messages:
        source = to_markdown(m)
        # Promote the in-play bracket form first; afterwards it is an ordinary `## Scene:`
        # heading, so the single count below covers both spellings.
        source, promoted = BRACKET_SCENE_RE.subn(r"\n## Scene: \1\n", source)
        bracket_promoted += promoted
        scene_markers += len(SCENE_RE.findall(source))
        if demote:
            # Chat's retrieval splits transcripts on `##` and reads the names after the dash as
            # a witness list, which governs what the Information Firewall lets an NPC know. So
            # `##` is reserved: a GM section header sitting at level 2 would masquerade as a
            # scene heading with no witnesses. Demote ordinary headings one level - but never a
            # `Scene:` heading, which IS the real thing and is normalised to exactly `## `.
            source = SCENE_RE.sub(r"## Scene:", source)
            source = re.sub(r"^(#{1,4}) (?!Scene:)", r"##\1 ", source, flags=re.M)
        cleaned, counts = strip_message(source, args.keep_tools,
                                        m.get("role") == "assistant", args.menu_min)
        for k in totals:
            totals[k] += counts[k]
        if not cleaned:
            # The whole turn was chrome (e.g. a bare tool marker). Record it rather than
            # silently vanishing a turn, so the numbering stays reconcilable with the raw.
            dropped_empty += 1
            body.append("<!-- turn %d (%s) removed entirely: only stripped content -->"
                        % (m.get("i", -1), m.get("role", "?")))
            continue

        dt = parse_ts(m.get("ts"))
        if dt and prev_dt:
            gap = (dt - prev_dt).total_seconds() / 60.0
            if gap >= args.gap_minutes:
                hrs, mins = divmod(int(gap), 60)
                span = ("%dh %dm" % (hrs, mins)) if hrs else ("%dm" % mins)
                body.append(
                    "<!-- BREAK IN PLAY - %s real-time gap.\n"
                    "     This marks when you stopped playing, which is NOT necessarily a\n"
                    "     scene boundary. If a scene does end here, replace this with:\n"
                    "     ## Scene: [where], [who was present] -->" % span)
                breaks += 1
        prev_dt = dt or prev_dt

        stamp = dt.astimezone().strftime("%d %b %H:%M") if dt else "unknown time"
        # Turns are level-3 headings so get_section can retrieve one. Measured on a real
        # session, a scene averages ~9,000 tokens - the size get_section exists to avoid -
        # while a single turn is ~1,200, which is the practical unit. `##` stays the scene
        # (witness list, context); `###` is the turn; the GM's own headings sit below both.
        #
        # Numbers are zero-padded because get_section matches a heading by unique prefix:
        # unpadded, "Turn 1" is a prefix of "Turn 12" and resolves to an ambiguity error
        # rather than a section.
        body.append("### Turn %s · %s · %s\n\n%s"
                    % (str(m.get("i", 0) + 1).zfill(turn_width),
                       ROLE_LABEL.get(m.get("role"), "?"), stamp, cleaned))

    # Keywords are FTS-indexed at 5x weight, so they are the coarse filter that narrows which
    # transcripts get searched at all. Build them from words, never compound slugs: the FTS5
    # tokenizer splits on underscores and hyphens, so a tag like `old_mill` indexes as
    # two ordinary tokens and `session_2` indexes as `session` + `2` - which matches every
    # transcript in the corpus and narrows nothing. Exact per-file filtering is the job of
    # type_filter (doc_type) and category_filter (directory), not of keywords.
    keywords = ["transcript", "session", "verbatim", "cleaned"]
    for extra in (args.campaign or "").replace("_", " ").split():
        if extra.lower() not in keywords:
            keywords.append(extra.lower())
    for extra in args.keywords.split(","):
        extra = extra.strip().lower()
        if extra and extra not in keywords:
            keywords.append(extra)

    stamps = [parse_ts(m.get("ts")) for m in messages]
    stamps = [s for s in stamps if s]
    # A session is not a sitting. One measured session ran 23 May to 28 July, played in the
    # evenings, so a single date is a choice between two wrong answers - first-message and
    # last-message dates differ by two months. Record the span when it spans.
    if stamps:
        first_day = stamps[0].astimezone().strftime("%Y-%m-%d")
        last_day = stamps[-1].astimezone().strftime("%Y-%m-%d")
        played = first_day if first_day == last_day else "%s to %s" % (first_day, last_day)
    else:
        played = ""

    # Field order and wording follow the Stub Format in Session_Transcript_Stub.md, so a stub
    # and the transcript that replaces it are the same shape. `--campaign` is given in
    # Snake_Case to match the folder, but the display fields want the human form: a
    # hand-written transcript reads "Old Mill", not "Old_Mill".
    campaign_display = (args.campaign or "[Campaign]").replace("_", " ")
    session_display = args.session or "[NN]"
    front = [
        "---",
        'name: "%s Session %s — Transcript"' % (campaign_display, session_display),
        "type: session-transcript",
        "status: cleaned",
        "fidelity: verbatim-capture",
        "source: claude.ai share page, captured by capture_transcript.py",
        "keywords: [%s]" % ", ".join(keywords),
        'description: "Transcript of %s Session %s%s"'
        % (campaign_display, session_display,
           (", " + args.in_game_date) if args.in_game_date else ""),
        'campaign: "%s"' % campaign_display,
        'session: "Session_%s"' % session_display,
        # Carried over from the checkpoint or a prior stub - the capture cannot know it, so a
        # regeneration that omits it drops a field the old file had.
        ('in_game_date: "%s"' % args.in_game_date) if args.in_game_date else None,
        'played: "%s"' % played,
        "messages: %d" % len(messages),
        "stripped_choice_menus: %d" % totals["choice_menus"],
        "stripped_ooc: %d" % totals["ooc"],
        "stripped_tool_markers: %d" % totals["tools"],
        "scene_markers: %d" % scene_markers,
        "raw_source: %s" % raw_path.name,
        "---",
        "",
        "# %s — Session %s Transcript" % (campaign_display, session_display),
        "",
        ("**In-game:** %s%s · **Played:** %s"
         % (args.in_game_date,
            (" · **Location:** " + args.location) if args.location else "",
            played)) if args.in_game_date else None,
        "" if args.in_game_date else None,
        "> Derived from `%s` by `clean_transcript.py`. The raw capture is the archive copy;"
        % raw_path.name,
        "> regenerate this file rather than editing it.",
    ]
    if scene_markers:
        front.append(
            "> %d `## Scene:` heading(s) came from the GM during play. Retrieval splits on them"
            % scene_markers)
        front.append(
            "> and reads the names after the dash as the witness list, so check those names are"
            " right —")
        front.append(
            "> a wrong witness lets an NPC know something they never saw.")
    else:
        front.append(
            "> No scene headings: the GM wrote none. Add `## Scene: [where] — [who was present]`"
            " at the")
        front.append(
            "> marked breaks. Retrieval splits on them and reads the names as the witness list.")

    out.parent.mkdir(parents=True, exist_ok=True)
    # Optional frontmatter lines are None when their flag was not given; drop them here so an
    # absent field leaves no blank line behind.
    front = [line for line in front if line is not None]
    out.write_text("\n".join(front) + "\n\n" + "\n\n".join(body) + "\n", encoding="utf-8")

    print("  Messages:            %d" % len(messages))
    print("  Choice menus:        %d stripped" % totals["choice_menus"])
    print("  OOC asides:          %d stripped" % totals["ooc"])
    print("  Tool markers:        %d %s"
          % (totals["tools"], "kept" if args.keep_tools else "stripped"))
    print("  Turns emptied:       %d (marked in place)" % dropped_empty)
    print("  Scene markers:       %d (%d promoted from `[ Scene: ... ]`)"
          % (scene_markers, bracket_promoted))
    print("  Candidate breaks:    %d (>= %dm idle)" % (breaks, args.gap_minutes))
    if not scene_markers:
        # Silence here means either the GM never emitted one or the convention has decayed.
        # Both look identical in the output, so say so rather than let a transcript ship with
        # no retrieval anchors and no complaint.
        print("  [warn] no '## Scene:' markers found - this transcript has no witness lists,")
        print("         so retrieved scenes cannot tell the GM who was present. Either the")
        print("         convention was not followed, or this predates it.")
    print("  Written:             %s" % out)
    print("  Runtime: %.1fs" % (time.perf_counter() - start))

    if not args.no_pause:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

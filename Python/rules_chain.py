#!/usr/bin/env python3
"""
rules_chain.py — Resolve a campaign's rules chain (or an explicit one) into its layers, each layer's search role and
state, and the chain's effective inputs, from ONE registry snapshot. Read-only: it builds, writes and searches
nothing. Used by search_mcp_server's index_status(campaign=... | chain=...) (chain-aware search, stage 2).

Search retrieves; it never resolves rules. This module reports what is declared and what is published, and refuses
where a chain cannot be searched as declared. It never decides which rule governs.

SELECTORS. Exactly one of
    campaign=<name>   the campaign folder's Campaign_Profile.md, found under either existing layout
                      (World_Building/<setting>/Scenarios/<name>/ or World_Building/<setting>/<name>/), matched by
                      folder name case-insensitively; none or several matches refuse, listing the candidates
    chain=<a,b,...>   an explicit chain, lowest first, with no campaign (so no adaptation profile or sidecars)

LAYERS. Each name resolves case-insensitively against the known modules (system_index.known_modules). A chain may
hold at most MAX_CHAIN layers, each once. Each layer gets exactly one role:
    indexed           registered, and its database agrees with the registry (system_index.check_publication)
    declared loaded   named in indexer.cfg [rules_layers] not_searched: DECLARED loaded and not searched — nothing
                      here can verify that a caller has it in context
    missing           anything else: unknown, unregistered, or a broken publication. It refuses the chain.
A module that is both registered and declared not-searched refuses: one of the two declarations is wrong.

STATE OF AN INDEXED LAYER. Source freshness is recomputed with the fingerprint its schema was built with: schema 2
with system_index.source_fingerprint (so an existing build is never reported stale merely because the code
changed), schema 3 with system_index.layered_fingerprint over the dependency build ids the build recorded. A change
is a conspicuous warning, never a refusal. A layered layer's recorded dependencies are compared with the snapshot:
one rebuilt since is reported "validated against an older build". A layer extending a module outside the chain is
reported.

SNAPSHOT TOKEN. SHA-256 over "rules-chain-snapshot/v1\\n" and one "<layer>\\0<build id>\\n" line per indexed layer,
sorted: the same token means the same published databases.

EFFECTIVE INPUTS (campaign selector).
    sidecars     the profile's homebrew entries, in load order: a path relative to the corpus root, or a bare file
                 name meaning the campaign folder. Each is reported with its hash; a missing or unsafe one refuses.
                 Sidecars are declared loaded and not searched.
    adaptation   required for a chain longer than one module. "current" only when ALL of these hold:
                   - the profile exists, and its own chain equals this chain;
                   - every built_against entry is a {path, sha256} with a full hash that still matches ("engine:" paths
                     from the corpus root; others from the profile's module folder when it sits in one, else the
                     corpus root);
                   - the pins COVER the chain's effective inputs: every layer's manifest (<module dir>/<id>.md) and
                     every declared sidecar is pinned. A matching subset proves nothing about what it leaves out;
                   - its own homebrew declaration (absent or none meaning no sidecars; entries resolved like
                     built_against paths) names exactly the campaign's sidecars, in order.
                 Absent, stale, a different chain, uncovered inputs, a different homebrew declaration, an unsafe path,
                 or a format whose hashes cannot be checked: the result is marked NON-AUTHORITATIVE retrieval, never
                 refused.

PATH SAFETY. Every path read from a profile — the adaptation, its built_against and homebrew entries, and the
sidecars — must be plainly relative (not absolute, drive- or UNC-rooted, and without '..', the "engine:" suffix
included), and must still resolve inside the corpus once links and junctions are followed. A campaign profile found
through a link that leads outside the corpus refuses, and so does an unsafe sidecar; an unsafe adaptation input makes
retrieval non-authoritative. Module discovery is contained the same way (system_index.known_modules), and an indexed
layer's index.cfg is read from the folder discovery validated, never by re-running the builder's discovery. Nothing
outside the corpus is ever opened.

REGISTRY SHAPE. Every registry entry is checked before any of it is used: a mapping, with a build_id, db and
source_fingerprint string and an integer schema_version, and a layer (if any) that is a mapping whose depends_on maps
module ids to build-id strings and whose extends is a string. Presence is by key: an entry whose value is null is
malformed, not absent. A malformed entry for a chain layer refuses that layer before any role is given, so a layer
declared not_searched does not hide one; one for any other module is left out of the snapshot, and a layer depending
on it says so.

CHAIN SEARCH SUPPORT (stage 3; the search itself is search_mcp_server._chain_search). An indexed layer records the
generation file the snapshot named (Layer.db), so the search queries exactly that build and never re-reads the
registry. allocate() spends `limit` across layers — one slot for each layer with a hit, the rest most specific first,
each layer capped at per_layer — and refuses, naming the smallest workable limit, when limit is below the number of
layers with hits (refinement A, Codex 938). read_declarations() reads a schema-3 layer's recorded relations with the
target builds it was validated against; scope() keeps those whose declaring and target layers are both in the active
chain and counts the rest; assess() recomputes each one's state against the target layer's database in the same
snapshot (pinned and unchanged, changed, unpinned, orphaned, validated against an older build) and names its
self-declared decider; target_lines() and entry_lines() word them for a hit. Every phrase says "declared", the
complementary modes never imply that an entry is displaced, several declarations of one unit are listed and flagged
unresolved, never collapsed, and a hit no declaration names says "no override recorded", which is not a claim that it
governs.

Command line arguments: none (library module).

# changed 2026-11-12: created (chain-aware search stage 2; design Working_Documents/Chain_Search_Design_Proposal_v2.md,
#   decisions Codex 938, approval Codex 945).
# changed 2026-11-12: Codex 947 fixes — module ids from the builder's identity rule (system_index.known_modules);
#   adaptation currency requires coverage of every layer manifest and sidecar plus a matching homebrew declaration;
#   path safety and containment for every profile-named path; registry entries validated before use.
# changed 2026-11-12: Codex 949 fixes — an indexed layer's index.cfg comes from its contained, validated folder
#   (_freshness no longer runs find_cfg); a null registry entry is malformed, and a malformed entry refuses a selected
#   layer before the declared-loaded branch.
# changed 2026-11-12: chain-aware search stage 3 (Codex 955) — Layer.db and Layer.kind from the snapshot; allocation
#   with refinement A; declared relations read, scoped to the active chain, assessed against the same snapshot and
#   worded for each hit.
# changed 2026-11-12: Codex 957 fixes — every recorded declaration is validated against the builder's rules before
#   anything renders (a malformed mode crashed the search); declarations naming one unit are grouped by its canonical
#   identity (unit_identity: get_section's heading normalisation, with level and whole-entry kept distinct), so
#   equivalent spellings of one heading show their conflict.
# changed 2026-11-14: a campaign or adaptation profile that is not valid UTF-8 refuses (or is non-authoritative)
#   instead of raising, and the message says so (audit batch 1, Working_Documents/Chain_Search_Audit_Fable.md X1).
"""

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import system_index

MAX_CHAIN = 8
WORLD = "World_Building"
PROFILE_FILE = "Campaign_Profile.md"
TOKEN_DOMAIN = b"rules-chain-snapshot/v1\n"
ROLE_INDEXED = "indexed"
ROLE_LOADED = "declared loaded, not searched"
ROLE_MISSING = "missing"
NO_SIDECARS = (None, "", "none")


@dataclass
class Layer:
    given: str                      # the name as the chain or profile spelt it
    module: str = ""                # the resolved module id ("" when unknown)
    role: str = ROLE_MISSING
    reason: str = ""                # why it is missing, or how it is declared
    build_id: str = ""
    schema: int = 0
    built_at: str = ""
    freshness: str = ""             # "unchanged", "CHANGED", or "unknown: <why>"
    notes: list = field(default_factory=list)   # dependency and extends observations
    db: str = ""                    # an indexed layer's generation file, from the ONE snapshot (stage 3 queries it)
    kind: str = ""                  # an indexed layer's kind as published (system for a legacy module)


@dataclass
class Sidecar:
    given: str
    path: str = ""                  # corpus-relative
    sha256: str = ""
    exists: bool = False


@dataclass
class Adaptation:
    given: str = ""
    path: str = ""
    status: str = ""                # "not required", "current", or a non-authoritative reason
    current: bool = False


@dataclass
class Resolution:
    selector: str = ""              # "campaign" or "chain"
    campaign: str = ""
    profile: str = ""               # corpus-relative path of the Campaign_Profile.md
    layers: list = field(default_factory=list)
    token: str = ""
    adaptation: Adaptation = field(default_factory=Adaptation)
    sidecars: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def refused(self) -> bool:
        return bool(self.refusals)

    @property
    def authoritative_inputs(self) -> bool:
        """True only when the chain's adaptation inputs are current (or none is required). False means any retrieval
        over this chain is non-authoritative. Never a claim about which rule governs."""
        return self.adaptation.current


def _rel(root: Path, p: Path) -> str:
    """`p` relative to the corpus root as written (links are not followed, so a name shown is the name found)."""
    try:
        return Path(os.path.abspath(p)).relative_to(Path(os.path.abspath(root))).as_posix()
    except ValueError:
        return Path(p).as_posix()


def _unsafe(rel: str) -> bool:
    """True for a path that is not plainly relative: empty, absolute, drive- or UNC-rooted, or using '..'."""
    rel = rel.replace("\\", "/")
    return not rel or rel.startswith("/") or bool(re.match(r"^[A-Za-z]:", rel)) or ".." in rel.split("/")


def _within(root: Path, path: Path) -> bool:
    """True when `path` resolves inside the corpus once links and junctions are followed."""
    return system_index._inside(Path(path), Path(root))


def _key(path: Path) -> str:
    """One spelling per file, for comparing resolved paths."""
    return os.path.normcase(str(Path(path).resolve()))


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def campaign_profiles(root: Path) -> list:
    """Every Campaign_Profile.md under both layouts: World_Building/<setting>/Scenarios/<campaign>/ and
    World_Building/<setting>/<campaign>/. Sorted, each once, as found (links not followed: find_campaign checks
    containment)."""
    base = Path(root) / WORLD
    found = set()
    if base.is_dir():
        found.update(base.glob(f"*/Scenarios/*/{PROFILE_FILE}"))
        found.update(p for p in base.glob(f"*/*/{PROFILE_FILE}") if p.parent.name.lower() != "scenarios")
    return sorted(found, key=lambda p: p.as_posix().lower())


def find_campaign(root: Path, name: str) -> tuple:
    """(profile path, None), or (None, why): the one profile whose campaign folder is `name`, case-insensitively. A
    profile that resolves outside the corpus (through a link or junction) refuses, and is never read."""
    want = name.strip().casefold()
    every = campaign_profiles(root)
    hits = [p for p in every if p.parent.name.casefold() == want]
    if len(hits) == 1:
        if not _within(root, hits[0]):
            return None, (f"{_rel(root, hits[0])} resolves outside the corpus (through a link or junction); it is "
                          f"not read")
        return hits[0], None
    if not hits:
        names = sorted({p.parent.name for p in every}, key=str.lower)
        return None, (f"no campaign folder named {name!r} holds a {PROFILE_FILE} (campaigns with one: "
                      f"{', '.join(names) or 'none'})")
    return None, (f"campaign {name!r} is ambiguous — several folders of that name hold a {PROFILE_FILE}: "
                  + "; ".join(_rel(root, p) for p in hits))


def _profile_fields(path: Path) -> tuple:
    data = system_index._read_manifest(path)
    if data is None:
        return None, f"{path.name} has no readable fenced YAML block (or is not valid UTF-8)"
    return data, None


def _parse_chain(raw) -> tuple:
    if isinstance(raw, str):
        names = [x.strip() for x in raw.split(",")]
    elif isinstance(raw, (list, tuple)):
        names = [str(x).strip() if x is not None else "" for x in raw]
    else:
        return None, "the chain must be a list of layer names, lowest first"
    if not names or any(not n for n in names):
        return None, "the chain names no layer, or has an empty entry"
    return names, None


def token_for(layers: list) -> str:
    h = hashlib.sha256(TOKEN_DOMAIN)
    for module, build in sorted((l.module, l.build_id) for l in layers if l.role == ROLE_INDEXED):
        h.update(f"{module}\0{build}\n".encode("utf-8"))
    return h.hexdigest()


def entry_problem(entry):
    """Why a registry entry cannot be used, or None. Checks every field this module reads, before any is read."""
    if not isinstance(entry, dict):
        return f"is not a mapping (it is a {type(entry).__name__})"
    for key in ("build_id", "db", "source_fingerprint"):
        if not isinstance(entry.get(key), str) or not entry.get(key):
            return f"has no {key} string"
    sv = entry.get("schema_version")
    if not isinstance(sv, int) or isinstance(sv, bool):
        return "has no integer schema_version"
    if "built_at" in entry and not isinstance(entry["built_at"], str):
        return "has a built_at that is not a string"
    layer = entry.get("layer")
    if layer is not None:
        if not isinstance(layer, dict):
            return "has a layer that is not a mapping"
        deps = layer.get("depends_on")
        if deps is not None and not (isinstance(deps, dict) and all(isinstance(k, str) and isinstance(v, str)
                                                                    for k, v in deps.items())):
            return "has a layer.depends_on that is not a mapping of module ids to build ids"
        if layer.get("extends") is not None and not isinstance(layer.get("extends"), str):
            return "has a layer.extends that is not a module id"
    return None


def _freshness(root: Path, layer: Layer, entry: dict, module_dir: Path, snapshot: dict,
               malformed=frozenset()) -> None:
    """Fill an indexed layer's source freshness and dependency notes. `entry` has passed entry_problem. `module_dir`
    is the layer's folder as system_index.known_modules found it — contained, and unambiguous — so its index.cfg is
    read from there, and the builder's discovery (which reads every index.cfg it globs) is never run here."""
    try:
        cfg_path = Path(module_dir) / "index.cfg"
        if not cfg_path.is_file() or not _within(module_dir, cfg_path):
            raise system_index.SystemIndexError(f"{layer.module} has no index.cfg inside its folder")
        cfg = system_index.load_system_cfg(cfg_path)
        if layer.schema == system_index.SCHEMA_LAYERED:
            recorded = (entry.get("layer") or {}).get("depends_on") or {}
            now = system_index.layered_fingerprint(cfg, recorded) if cfg.layered else system_index.source_fingerprint(cfg)
        else:
            now = system_index.source_fingerprint(cfg) if not cfg.layered else system_index.layered_fingerprint(cfg, {})
        layer.freshness = "unchanged" if now == entry.get("source_fingerprint") else "CHANGED"
    except (system_index.SystemIndexError, OSError) as e:
        layer.freshness = f"unknown: could not recompute ({e})"
    if layer.schema == system_index.SCHEMA_LAYERED:
        info = entry.get("layer") or {}
        for dep, build in sorted((info.get("depends_on") or {}).items()):
            live = snapshot.get(dep)
            if dep in malformed:
                layer.notes.append(f"depends on {dep}, whose registry entry is malformed")
            elif live is None:
                layer.notes.append(f"depends on {dep}, which is no longer published")
            elif live != build:
                layer.notes.append(f"relations validated against an older build of {dep} ({build}; now {live})")


def _sidecar_entries(raw) -> list:
    """The declared entries of a homebrew field, in order, with the spellings of "none" dropped."""
    if isinstance(raw, str) and raw.strip().lower() in NO_SIDECARS:
        return []
    entries = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    return [item for item in entries
            if not (item is None or (isinstance(item, str) and item.strip().lower() in NO_SIDECARS))]


def _check_adaptation(root: Path, res: Resolution, given, modules: list, known: dict) -> None:
    """Fill res.adaptation. Requires res.sidecars to be resolved already: they are effective inputs it must cover."""
    a = res.adaptation
    a.given = "" if given is None else str(given)
    if len(modules) <= 1:
        a.status, a.current = "not required (a one-module chain)", True
        return
    if not a.given.strip():
        a.status = "NONE DECLARED — a chain longer than one module needs one; retrieval is non-authoritative"
        return
    rel = a.given.strip().replace("\\", "/")
    if _unsafe(rel):
        a.status = f"{a.given!r} is not a corpus-relative path; retrieval is non-authoritative"
        return
    path = Path(root) / rel
    a.path = rel
    if not _within(root, path):
        a.status = f"{rel} resolves outside the corpus (through a link or junction); it is not read, retrieval is " \
                   f"non-authoritative"
        return
    if not path.is_file():
        a.status = f"{rel} does not exist; retrieval is non-authoritative"
        return
    data = system_index._read_manifest(path)
    if data is None:
        a.status = f"{rel} has no readable fenced YAML profile (or is not valid UTF-8); retrieval is non-authoritative"
        return
    declared, why = _parse_chain(data.get("chain"))
    if why or [n.casefold() for n in declared] != modules:
        a.status = (f"{rel} is for the chain {data.get('chain')!r}, not this one; retrieval is non-authoritative")
        return
    built = data.get("built_against")
    if not isinstance(built, list) or not built or not all(
            isinstance(b, dict) and set(b) == {"path", "sha256"} and isinstance(b["path"], str)
            and isinstance(b["sha256"], str) and system_index.HEX64.match(b["sha256"]) for b in built):
        a.status = (f"{rel} records built_against in a form whose hashes cannot be checked; currentness unknown, "
                    f"retrieval is non-authoritative")
        return
    owner = next((d for d in known.values() if _within(d, path)), None)

    def target_of(spec: str):
        """The file a profile path names, or None when the path is unsafe or leaves the corpus."""
        base, sub = (Path(root), spec[len("engine:"):]) if spec.startswith("engine:") else (owner or Path(root), spec)
        if _unsafe(sub.strip()):
            return None
        target = base / sub.strip()
        return target if _within(root, target) else None

    unsafe, stale, pinned = [], [], set()
    for b in built:
        target = target_of(b["path"])
        if target is None:
            unsafe.append(b["path"])
        elif not target.is_file():
            stale.append(f"{b['path']} (not found)")
        elif _sha(target) != b["sha256"]:
            stale.append(f"{b['path']} (changed)")
        else:
            pinned.add(_key(target))
    if unsafe:
        a.status = (f"{rel} pins a path that is not corpus-relative or resolves outside the corpus: "
                    + ", ".join(repr(u) for u in unsafe) + "; it is not read, retrieval is non-authoritative")
        return
    if stale:
        a.status = f"{rel} is STALE: " + ", ".join(stale) + "; retrieval is non-authoritative"
        return

    # Coverage: a matching subset says nothing about what it leaves out.
    required = []                                   # (what, path or None)
    for m in modules:
        d = known.get(m)
        required.append((f"the {m} manifest", (d / f"{m}.md") if d is not None else None))
    for s in res.sidecars:
        required.append((f"the sidecar {s.path or s.given}", (Path(root) / s.path) if s.exists else None))
    uncovered = [what for what, p in required if p is None or _key(p) not in pinned]
    if uncovered:
        a.status = (f"{rel} does not pin " + ", ".join(uncovered) + "; it cannot prove those inputs current, "
                    f"retrieval is non-authoritative")
        return
    built_for = []
    for item in _sidecar_entries(data.get("homebrew")):
        target = target_of(str(item)) if isinstance(item, str) else None
        if target is None:
            a.status = (f"{rel} declares homebrew {item!r}, which is not a corpus-relative path inside the corpus; "
                        f"retrieval is non-authoritative")
            return
        built_for.append(_key(target))
    if built_for != [_key(Path(root) / s.path) for s in res.sidecars]:
        a.status = (f"{rel} was built for homebrew {data.get('homebrew')!r}, but the campaign declares "
                    f"{[s.path or s.given for s in res.sidecars] or 'none'}; retrieval is non-authoritative")
        return
    a.status, a.current = (f"{rel}: current (every built_against hash matches, and it pins every layer manifest and "
                           f"sidecar)"), True


def _check_sidecars(root: Path, res: Resolution, raw, campaign_dir: Path) -> None:
    for item in _sidecar_entries(raw):
        s = Sidecar(str(item))
        rel = str(item).strip().replace("\\", "/")
        if not isinstance(item, str) or _unsafe(rel):
            res.refusals.append(f"sidecar {item!r} is not a corpus-relative path or a file name in the campaign folder")
            res.sidecars.append(s)
            continue
        path = (campaign_dir / rel) if "/" not in rel else (Path(root) / rel)
        s.path = _rel(root, path)
        if not _within(root, path):
            res.refusals.append(f"sidecar {s.path} resolves outside the corpus (through a link or junction); it is "
                                f"not read")
        elif path.is_file():
            s.exists, s.sha256 = True, _sha(path)
        else:
            res.refusals.append(f"declared sidecar {s.path} does not exist; create it or remove it from the profile")
        res.sidecars.append(s)


def resolve(root: Path, index_dir: Path, rules_cfg: dict, *, campaign: str = None, chain=None) -> Resolution:
    """Resolve one chain selector. `rules_cfg` is the corpus config as cfg_loader.load_cfg returns it (only its
    [rules_layers] section is read). Never raises for a user error: every problem lands in .refusals (the chain
    cannot be searched as declared) or .warnings (it can, flagged)."""
    root = Path(root)
    res = Resolution()
    if (campaign is None) == (chain is None):
        res.refusals.append("give exactly one of campaign or chain")
        return res
    try:
        private_roots, not_searched = system_index.parse_rules_layers(rules_cfg, root)
    except system_index.SystemIndexError as e:
        res.refusals.append(f"indexer.cfg [rules_layers]: {e}")
        return res

    profile_data, campaign_dir = {}, None
    if campaign is not None:
        res.selector, res.campaign = "campaign", str(campaign)
        path, why = find_campaign(root, str(campaign))
        if why:
            res.refusals.append(why)
            return res
        res.profile, campaign_dir = _rel(root, path), path.parent
        profile_data, why = _profile_fields(path)
        if why:
            res.refusals.append(f"{res.profile}: {why}")
            return res
        names, why = _parse_chain(profile_data.get("chain"))
        if why:
            res.refusals.append(f"{res.profile}: {why}")
            return res
    else:
        res.selector = "chain"
        names, why = _parse_chain(chain)
        if why:
            res.refusals.append(why)
            return res
    if len(names) > MAX_CHAIN:
        res.refusals.append(f"the chain has {len(names)} layers; at most {MAX_CHAIN} are allowed")
        return res

    known, ambiguous = system_index.known_modules(root, private_roots)
    try:
        reg = system_index.read_registry(system_index.systems_dir(index_dir))      # the ONE snapshot
    except system_index.SystemIndexError as e:
        res.refusals.append(f"the module registry cannot be read: {e}")
        return res
    sdir = system_index.systems_dir(index_dir)
    problems = {m: entry_problem(e) for m, e in reg["systems"].items()}
    malformed = {m for m, why in problems.items() if why}
    snapshot = {m: e["build_id"] for m, e in reg["systems"].items() if m not in malformed}
    seen = set()
    for given in names:
        layer = Layer(given)
        mid = given.casefold()
        res.layers.append(layer)
        if mid in seen:
            layer.reason = "named twice in the chain"
            res.refusals.append(f"layer {given!r} appears more than once in the chain")
            continue
        seen.add(mid)
        if mid in ambiguous:
            layer.reason = "more than one folder declares this module"
            res.refusals.append(f"layer {given!r}: {layer.reason}")
            continue
        if mid not in known:
            layer.reason = f"unknown layer (known modules: {', '.join(sorted(known)) or 'none'})"
            res.refusals.append(f"layer {given!r} is not a known module")
            continue
        layer.module = mid
        # Key presence, not .get(): an entry whose value is null is malformed, never "absent".
        registered = mid in reg["systems"]
        if mid in malformed:                    # before any role: a selected layer never consumes a malformed entry
            layer.reason = (f"its registry entry {problems[mid]}; rebuild it (build_indexes.py --system {mid}) to "
                            f"republish a well-formed entry")
            res.refusals.append(f"layer {mid}: the registry entry {problems[mid]}")
            continue
        entry = reg["systems"][mid] if registered else None
        if mid in not_searched:
            if registered:
                layer.reason = "declared not_searched in indexer.cfg, yet it has a published database"
                res.refusals.append(f"layer {mid}: {layer.reason}; remove one of the two")
                continue
            layer.role, layer.reason = ROLE_LOADED, "indexer.cfg [rules_layers] not_searched (not verified in context)"
            continue
        if not registered:
            layer.reason = (f"not built and not declared not_searched; build it (build_indexes.py --system {mid}) or "
                            f"declare it under [rules_layers] not_searched")
            res.refusals.append(f"layer {mid} has no database")
            continue
        _db, info, why = system_index.check_publication(sdir, mid, entry)
        if why:
            layer.reason = why
            res.refusals.append(f"layer {mid}: {why}")
            continue
        layer.role, layer.build_id, layer.schema = ROLE_INDEXED, info["build_id"], info["schema_version"]
        layer.built_at = str(entry.get("built_at", ""))
        layer.db, layer.kind = str(_db), str((entry.get("layer") or {}).get("kind") or "system")
        _freshness(root, layer, entry, known[mid], snapshot, malformed)
        if layer.freshness == "CHANGED":
            res.warnings.append(f"{mid}: SOURCES CHANGED since the build — results may not match the files; rebuild "
                                f"with build_indexes.py --system {mid}")
        elif layer.freshness.startswith("unknown"):
            res.warnings.append(f"{mid}: source freshness {layer.freshness}")
        ext = ((entry.get("layer") or {}).get("extends") or "")
        if ext and ext not in [n.casefold() for n in names]:
            layer.notes.append(f"extends {ext}, which this chain does not include")
        res.warnings += [f"{mid}: {n}" for n in layer.notes]

    res.token = token_for(res.layers)
    modules = [l.module or l.given.casefold() for l in res.layers]
    if res.selector == "campaign":
        _check_sidecars(root, res, profile_data.get("homebrew"), campaign_dir)      # first: the adaptation covers them
        _check_adaptation(root, res, profile_data.get("adaptation"), modules, known)
    elif len(modules) <= 1:
        res.adaptation.status, res.adaptation.current = "not required (a one-module chain)", True
    else:
        res.adaptation.status = ("none — an explicit chain carries no adaptation profile; retrieval is "
                                 "non-authoritative")
    return res


# ---------------------------------------------------------------------------
# Chain search support (stage 3): allocation, and declared relations as reported
# ---------------------------------------------------------------------------

# Relation lines shown on one hit; the rest are counted on the hit, never dropped silently.
MAX_RELATION_LINES = 10
# How each mode is worded on the entry a declaration names. Complementary and partial modes never say, or imply, that
# the named entry is displaced; and every phrase says "declared", because nothing here verifies a declaration.
MODE_PHRASES = {
    "override": "declared override by {layer}",
    "n_a": "declared not applicable by {layer}",
    "add": "declared: added to by {layer}",
    "extend": "declared: extended by {layer}",
    "partition": "declared: partitioned with {layer}",
    "fall_through": "declared: falls through to this entry from {layer}",
}
NO_OVERRIDE = "no override recorded (no declaration in this chain names this entry; not a claim that it governs)"


def allocate(counts: list, limit: int, per_layer: int) -> tuple:
    """(slots per layer, None), or (None, the minimum limit) — refinement A (Codex 938).

    `counts` is each searched layer's number of hits, in presentation order (most specific first). Every layer with a
    hit gets one slot, so coverage is visible; the slots left go in presentation order, each layer up to `per_layer`
    and its own hits, until `limit` is spent. So no layer exceeds per_layer and the total never exceeds limit. When
    limit is smaller than the number of layers with hits, a slot for each cannot be given within the cap: the result
    is a refusal carrying the smallest limit that can, never a silently omitted layer and never output beyond the
    cap."""
    matching = sum(1 for c in counts if c > 0)
    if limit < matching:
        return None, matching
    slots = [1 if c > 0 else 0 for c in counts]
    left = limit - matching
    for i, c in enumerate(counts):
        extra = min(max(min(c, per_layer) - 1, 0), left)
        slots[i] += extra
        left -= extra
    return slots, None


@dataclass
class Declaration:
    """One relation a searched layer's database records (its relations table, validated at its build)."""
    layer: str                      # the declaring layer
    item: int                       # its item number in that layer's relations.yaml
    entry_key: str
    entry_section: tuple            # (heading, level) or None
    target_layer: str
    target_key: str
    target_section: tuple
    mode: str
    status: str
    decided: str = ""
    decider: str = ""               # SELF-DECLARED by the layer's author; never verified approval
    declared_sha256: str = ""       # the pin the author declared ("" = unpinned)
    validated_build: str = ""       # the target layer's build this layer was validated against ("" = not recorded)

    def entry_label(self) -> str:
        return _unit_label(self.layer, self.entry_key, self.entry_section)

    def target_label(self) -> str:
        return _unit_label(self.target_layer, self.target_key, self.target_section)


def _unit_label(layer: str, key: str, section) -> str:
    return f"{layer}:{key}" + (f" § {section[0]!r} (level {section[1]})" if section else "")


def _section(raw: str):
    """A relations-table section column ('' or JSON {heading, level}) as (heading, level) or None."""
    if not raw:
        return None
    import json
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("heading"), str) or not isinstance(data.get("level"), int):
        raise ValueError(f"malformed section {raw!r}")
    if isinstance(data["level"], bool) or not 1 <= data["level"] <= 6 or not system_index.norm_heading(data["heading"]):
        raise ValueError(f"malformed section {raw!r}")
    return data["heading"], data["level"]


def unit_identity(layer: str, key: str, section) -> tuple:
    """The canonical identity of a unit a declaration names: its layer, its key, and — for a section — its level and
    the heading as section resolution normalises it (system_index.norm_heading, get_section's own rule). Two
    spellings that select the same section are one unit; a whole entry and a section of it are different units, and
    so are one heading at two levels."""
    return layer, key, (None if section is None else (system_index.norm_heading(section[0]), section[1]))


def _check_declaration(d: "Declaration") -> None:
    """Every field read from a relations table must be one the builder could have written (parse_relations' rules);
    anything else is a broken table, never rendered. Raises ValueError naming the item."""
    def bad(what):
        raise ValueError(f"relations item {d.item!r}: {what}")
    if isinstance(d.item, bool) or not isinstance(d.item, int):
        bad("item is not an integer")
    for name in ("entry_key", "target_key"):
        value = getattr(d, name)
        if not isinstance(value, str) or not system_index.ENTRY_KEY.match(value):
            bad(f"{name} {value!r} is not an entry key")
    if not isinstance(d.target_layer, str) or not system_index.SYSTEM_NAME.match(d.target_layer):
        bad(f"target_layer {d.target_layer!r} is not a layer id")
    if d.mode not in system_index.RELATION_MODES:
        bad(f"mode {d.mode!r} is not one of {', '.join(system_index.RELATION_MODES)}")
    if d.status not in system_index.RELATION_STATUSES:
        bad(f"status {d.status!r} is not one of {', '.join(system_index.RELATION_STATUSES)}")
    if not isinstance(d.decided, str) or (d.decided and not system_index.DATE.match(d.decided)):
        bad(f"decided {d.decided!r} is not a date")
    if not isinstance(d.decider, str):
        bad("decider is not text")
    if not isinstance(d.declared_sha256, str) or (d.declared_sha256 and not system_index.HEX64.match(d.declared_sha256)):
        bad(f"declared_sha256 {d.declared_sha256!r} is not a unit hash")
    for key, section in ((d.entry_key, d.entry_section), (d.target_key, d.target_section)):
        if section is not None and key.startswith("rec:"):
            bad(f"{key} is a record, which takes no section")


def read_declarations(conn, layer: str) -> list:
    """Every declaration a schema-3 layer's database records, in item order, with the build of each target layer it
    was validated against (its layer_info.depends_on). Raises SystemIndexError, naming the fix, when the tables a
    schema-3 database must hold are missing or malformed: a layered layer's relations are never guessed absent."""
    import json
    import sqlite3
    try:
        info = conn.execute("SELECT depends_on FROM layer_info").fetchall()
        rows = conn.execute("SELECT item, entry_key, entry_section, target_layer, target_key, target_section, mode, "
                            "status, decided, decider, declared_sha256 FROM relations ORDER BY item").fetchall()
        if len(info) != 1:
            raise ValueError(f"layer_info holds {len(info)} rows, not one")
        deps = json.loads(info[0][0] or "{}")
        if not isinstance(deps, dict):
            raise ValueError("layer_info.depends_on is not a mapping")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in deps.items()):
            raise ValueError("layer_info.depends_on does not map layer ids to build ids")
        out = [Declaration(layer, r[0], r[1], _section(r[2]), r[3], r[4], _section(r[5]), r[6], r[7],
                           r[8] or "", r[9] or "", r[10] or "", str(deps.get(r[3]) or "")) for r in rows]
        for d in out:                     # validated BEFORE any is rendered: a broken row never reaches the output
            _check_declaration(d)
    except (sqlite3.Error, ValueError, TypeError) as e:
        raise system_index.SystemIndexError(f"{layer}: its schema-3 database has unreadable layer tables ({e}); rebuild "
                                            f"it (build_indexes.py --system {layer})")
    return out


def scope(declarations: list, chain_modules: list) -> tuple:
    """(declarations inside the chain, the number outside it). Active-chain scoping: a declaration counts only when
    its declaring layer and its target layer are both in the active chain; the rest are ignored, and counted."""
    inside = [d for d in declarations if d.layer in chain_modules and d.target_layer in chain_modules]
    return inside, len(declarations) - len(inside)


def assess(d: Declaration, conns: dict, builds: dict) -> list:
    """The status words for one in-chain declaration, recomputed now against the target layer's database from the
    SAME snapshot (`conns`: {layer: open connection}, `builds`: {layer: snapshot build id}). Never "governs", never
    "verified": currentness of the pin, whether the target still resolves, and the build validated against."""
    words = [d.status]
    conn = conns.get(d.target_layer)
    if conn is None:
        words.append(f"the target layer {d.target_layer} is not searched in this chain; currentness unknown")
    else:
        now, why = system_index.resolve_unit(conn, system_index.Address(d.target_layer, d.target_key,
                                                                         d.target_section))
        if why:
            words.append(f"[!] ORPHANED — the target no longer resolves ({why})")
        elif not d.declared_sha256:
            words.append("unpinned, currentness unknown")
        elif d.declared_sha256 != now:
            words.append("[!] target changed since declared")
        else:
            words.append("pinned; the target is unchanged since declared")
    live = builds.get(d.target_layer)
    if live and d.validated_build and d.validated_build != live:
        words.append(f"validated against an older build of {d.target_layer} ({d.validated_build}; now {live})")
    elif live and not d.validated_build:
        words.append(f"the build of {d.target_layer} it was validated against is not recorded")
    who = f" by {d.decider}" if d.decider else ""
    when = f" on {d.decided}" if d.decided else ""
    words.append(f"self-declared{who}{when} in {d.layer} relations.yaml item {d.item}")
    return words


def target_lines(hit_layer: str, hit_key: str, inside: list, conns: dict, builds: dict, higher: list) -> list:
    """The relation lines for one hit, from the declarations that name it (its layer and entry key), in chain order
    (`inside` is already in chain order). `higher` lists the searched layers above the hit's layer. A hit no
    declaration names says so — no override recorded — which is explicitly not a claim that it governs."""
    naming = [d for d in inside if d.target_layer == hit_layer and d.target_key == hit_key]
    lines = []
    if not naming:
        lines.append(NO_OVERRIDE)
    units = {}                        # by canonical identity: equivalent heading spellings are one unit
    for d in naming:
        units.setdefault(unit_identity(d.target_layer, d.target_key, d.target_section), []).append(d)
    shown = 0
    for group in units.values():
        section = group[0].target_section                  # the first declaration's own spelling labels the unit
        where = f"§ {section[0]!r} (level {section[1]}): " if section else ""
        for d in group:
            if shown < MAX_RELATION_LINES:
                phrase = MODE_PHRASES[d.mode].format(layer=d.layer)       # modes are validated when read
                spelt = (f" [declared as § {d.target_section[0]!r}]" if section and d.target_section[0] != section[0]
                         else "")
                lines.append(f"{where}{phrase} ({d.entry_label()}){spelt} — " + "; ".join(assess(d, conns, builds)))
            shown += 1
        if len(group) > 1:
            overrides = sum(d.mode == "override" for d in group)
            lines.append(f"{where}[!] conflicting declarations: unresolved ({len(group)} declarations, {overrides} "
                         f"override(s); search does not reconcile them)" if overrides else
                         f"{where}several declarations ({len(group)}): unresolved — search does not reconcile them")
    if shown > MAX_RELATION_LINES:
        lines.append(f"+{shown - MAX_RELATION_LINES} more declaration(s) name this entry, not shown "
                     f"(build_indexes.py --relations <layer> lists them)")
    undeclared = [h for h in higher if not any(d.layer == h for d in naming)]
    if undeclared:
        lines.append(f"higher layer present, relation undeclared: {', '.join(undeclared)}")
    return lines


def entry_lines(hit_layer: str, hit_key: str, inside: list, conns: dict, builds: dict) -> list:
    """What a hit itself declares: one line per in-chain declaration whose entry is this hit, capped and counted."""
    own = [d for d in inside if d.layer == hit_layer and d.entry_key == hit_key]
    lines = []
    for d in own[:MAX_RELATION_LINES]:
        where = f"§ {d.entry_section[0]!r} (level {d.entry_section[1]}) " if d.entry_section else ""
        lines.append(f"{where}declares {d.mode} of {d.target_label()} — " + "; ".join(assess(d, conns, builds)))
    if len(own) > MAX_RELATION_LINES:
        lines.append(f"+{len(own) - MAX_RELATION_LINES} more declaration(s) by this entry, not shown "
                     f"(build_indexes.py --relations {hit_layer} lists them)")
    return lines

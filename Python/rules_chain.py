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

Command line arguments: none (library module).

# changed 2026-11-12: created (chain-aware search stage 2; design Working_Documents/Chain_Search_Design_Proposal_v2.md,
#   decisions Codex 938, approval Codex 945).
# changed 2026-11-12: Codex 947 fixes — module ids from the builder's identity rule (system_index.known_modules);
#   adaptation currency requires coverage of every layer manifest and sidecar plus a matching homebrew declaration;
#   path safety and containment for every profile-named path; registry entries validated before use.
# changed 2026-11-12: Codex 949 fixes — an indexed layer's index.cfg comes from its contained, validated folder
#   (_freshness no longer runs find_cfg); a null registry entry is malformed, and a malformed entry refuses a selected
#   layer before the declared-loaded branch.
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
        return None, f"{path.name} has no readable fenced YAML block"
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
        a.status = f"{rel} has no readable fenced YAML profile; retrieval is non-authoritative"
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

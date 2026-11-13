#!/usr/bin/env python3
"""
system_index.py — Per-module (game-system) search databases: config, records, fingerprint and registry.

Shared by build_indexes.py (which builds and publishes module databases) and search_mcp_server.py (which resolves
and reads them). Neither writes a module database any other way.

A game-system module declares what to index in a strict index.cfg at its own root:

    [system]
    module = <module id>                  # must match <dir>/<module>.md's manifest

    [representation verbatim]             # verbatim | compact | dataset
    path = source/srd                     # module-relative; must stay inside the module
    authority = source                    # source | derived
    include = *.md                        # comma list of filename globs; each must match a file
    exclude_keys = a, b                   # dataset only: record keys left out of the search text
    row_refs = a, b                       # dataset only: fields holding row references (see below)

Publication is by immutable generation: each build writes index/systems/<module>.<build_id>.db, and
index/systems/registry.json — replaced atomically, under a lock — is the single pointer to the live generation. A
reader never sees a half-built database, and a failure before the registry swap publishes nothing.

Record contract for dataset (JSONL) files: every record is a JSON object with non-empty string `id`, `name` and
`dataset`; every record in a file declares the same dataset, and no two files declare the same one; ids are unique
across the module; `kind` and `source` (an object with `file` and `anchors`) are optional.

Row references. A record read from one row of a table often has no source of its own: the table's lines belong to
an index record, and the row record only points at it. `row_refs` names the fields that hold those pointers — lists
of objects with a string `index` (a record id in this module) and an integer `line`, extra keys allowed. They are
read ONLY on a record with no `source`: the same field names can mean something else on a sourced record (an index
record's own table rows), so a record with a direct source always keeps it. With row_refs declared, every
source-less record must carry exactly one of the fields, non-empty; every reference must resolve to a record that
has a direct source (one hop, never inherited through another source-less record); and a line must fall inside
that source's line_start..line_end when it has them. The resolved provenance is stored as
{"via_row_refs": [{"index", "rows", "source"}]}, one entry per table in first-reference order, and is displayed as
inherited, never as the record's own.

Layers (chain-aware search, stage 1). A module is also a LAYER that a campaign's rules chain can stack: a system, a
variant of one, a third-party supplement, or the user's own homebrew. Its manifest's fenced YAML may declare

    kind: system | variant | thirdparty | homebrew    # absent = system (every existing module validates unchanged)
    extends: <layer id>                               # required for variant, thirdparty and homebrew

and the module root may hold an optional relations.yaml declaring how its entries relate to entries of other
layers, in the adaptation profile's vocabulary (see parse_relations). Search reports such declarations; it never
infers one, and nothing here decides which rule governs. A layer that declares neither `extends` nor relations is a
LEGACY layer: schema 2, fingerprinted and published exactly as before, so an existing module rebuilt by this code
stays byte-compatible with every reader. A layer that declares either is LAYERED: schema 3, with a relations table,
a layer_info row and a fingerprint that also covers its manifest, its relations and the build ids of the layers it
depends on (dependencies(): its extends parent and every relation target layer), each resolved from one registry
snapshot. The server reads schema 2 only until the chain-search stage, so a layered database is refused there.

Private roots. Besides Game_Systems/<dir>/index.cfg, discovery also reads <root>/<dir>/index.cfg for each private
layer root the corpus config declares ([rules_layers] private_roots in indexer.cfg; see validate_private_roots).
The corpus build excludes the same roots from its search index, so a user's own rules are searched through their
layer only, never through lore search.

Unit hashes. A relation pins its target by content: unit_hash() over canonical bytes (see canonical_unit_bytes), for
a whole document, one section of it, or one dataset record, read from the target layer's published database.

# changed 2026-09-24: created (Eclipse Phase import, phase 7 — per-module search).
# changed 2026-09-25: row_refs — provenance for records read from table rows, resolved one hop at build time.
# changed 2026-10-18: layers — manifest kind/extends with legacy defaults, relations.yaml (strict, layer-qualified
#   addresses with explicit section selectors, pinned by canonical unit hashes), schema 3 for layered modules only,
#   the layered fingerprint with dependency commitments, dependency ordering, and private layer roots
#   (chain-aware search stage 1; design: Working_Documents/Chain_Search_Design_Proposal_v2.md, Codex 936/938).
#   Review fix (Codex 940): an existing private root may hold only rules-layer folders, so existing lore cannot be
#   declared one and hidden from lore search.
# changed 2026-11-12: chain-aware search stage 2 — known_modules (every module, indexed or not, by its
#   folder-named manifest), parse_rules_layers (the strict [rules_layers] section, shared by the builder and the
#   server, now with not_searched), and check_publication (a read-only registry/database consistency check).
# changed 2026-11-12: Codex 947 — known_modules identifies an indexable folder by its index.cfg's declared id, with
#   the builder's conflict rule; the folder-named manifest is the fallback for folders without one.
# changed 2026-11-12: Codex 949 — known_modules is contained: a discovery root, module folder, index.cfg or manifest
#   that resolves out of the corpus (or its root/folder) is never listed or read.
# changed 2026-11-12: Codex 951 — builder-side containment: discover (behind cfgs_for, find_cfg, --all-systems and
#   pruning) offers no root, module folder or index.cfg that leads out; load_system_cfg never opens an index.cfg,
#   manifest or relations.yaml that resolves outside its module folder.
# changed 2026-11-13: Codex 961 — containment at the open of a published generation: contained_real and
#   open_contained (resolve with links and junctions followed, open the resolved file, re-check once open), used by
#   check_publication and, through the server's _snapshot_generation, by every server-side module open.
"""

import fnmatch
import hashlib
import json
import os
import re
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cfg_loader import CfgError, load_cfg

SCHEMA_VERSION = 2          # the legacy schema: every module that declares no layering, and the registry format
SCHEMA_LAYERED = 3          # a module declaring `extends` or relations
REPRESENTATIONS = ("verbatim", "compact", "dataset")
LAYER_KINDS = ("system", "variant", "thirdparty", "homebrew")
RELATIONS_FILE = "relations.yaml"
# The adaptation profile's vocabulary (Game_Systems adaptation profiles), so search and the compile speak one language.
RELATION_MODES = ("override", "add", "extend", "partition", "fall_through", "n_a")
RELATION_STATUSES = ("derived", "settled", "open")
RELATION_KEYS = {"entry", "target", "mode", "status", "decided", "decider", "target_sha256", "note"}
ADDRESS_KEYS = {"key", "section"}
TARGET_KEYS = {"layer", "key", "section"}
SECTION_KEYS = {"heading", "level"}
ENTRY_KEY = re.compile(r"^(?:doc:[^\s#]+|rec:[^\s/#]+/[^\s#]+)$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
UNIT_HASH_DOMAIN = b"rules-layer-unit/v1\n"
PIN_STATES = ("pinned", "unpinned", "changed")
# The database schemas a layer may depend on: a dependency of any other schema cannot be validated against.
SUPPORTED_DEPENDENCY_SCHEMAS = (SCHEMA_VERSION, SCHEMA_LAYERED)
# Besides layer folders and dotfiles, the only file an existing private layer root may hold.
LAYER_ROOT_ALLOWED_FILES = ("readme.md",)
# The keys the corpus config's [rules_layers] section may hold.
RULES_LAYERS_KEYS = ("private_roots", "not_searched")
# The heading rules get_section uses (search_mcp_server); kept identical so a relation selects the section a reader
# fetches. test_layers checks the two implementations agree.
_ATX_RE = re.compile(r"^(#{1,6})[ \t]+(\S.*?)[ \t]*#*$")
_FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
AUTHORITIES = ("source", "derived")
SYSTEM_NAME = re.compile(r"^[a-z0-9_]+$")
GENERATION = re.compile(r"^(?P<module>[a-z0-9_]+)\.(?P<build>[A-Za-z0-9_-]+)\.db$")
SYSTEMS_SUBDIR = "systems"
REGISTRY = "registry.json"
LOCK = "registry.lock"
LOCK_TIMEOUT_S = 120
LOCK_STALE_S = 600
MANIFEST_FENCE = re.compile(r"(?ms)^```ya?ml[ \t]*\n(.*?)^```[ \t]*$")
# Keys shown first in a record's search text, in this order; every other key follows in sorted order.
LEAD_KEYS = ("name", "kind", "category", "id")


class SystemIndexError(Exception):
    """A module's configuration, sources or registry is unusable. The message names the file and the problem."""


class DependencyCycle(SystemIndexError):
    """Layers that cannot be ordered: a cycle, and every layer depending on one. `members` names them all."""

    def __init__(self, members):
        self.members = sorted(members)
        super().__init__("dependency cycle among layers: " + ", ".join(self.members)
                         + " — a layer may not extend or relate to a layer that depends on it")


@dataclass
class Representation:
    name: str
    rel: str                 # module-relative path, as declared
    path: Path               # resolved absolute path
    authority: str
    include: list
    exclude_keys: tuple = ()
    row_refs: tuple = ()
    files: list = field(default_factory=list)   # sorted absolute paths, filled by collect()


@dataclass(frozen=True)
class Address:
    """A unit in some layer: an entry key (doc:<module-relative path> or rec:<dataset>/<record id>) and, for a
    document only, an optional section (heading, level). Anchors are never part of a key."""
    layer: str
    key: str
    section: tuple = None    # (heading, level) or None

    def label(self) -> str:
        s = f"{self.layer}:{self.key}"
        return s + (f" § {self.section[0]!r} (level {self.section[1]})" if self.section else "")


@dataclass
class Relation:
    index: int               # 1-based item number in relations.yaml, for messages
    entry: Address
    target: Address
    mode: str
    status: str
    decided: str = ""
    decider: str = ""        # SELF-DECLARED by the layer's author; never verified approval
    target_sha256: str = ""  # the pinned target content hash; "" = unpinned


@dataclass
class SystemCfg:
    module: str
    module_dir: Path
    cfg_path: Path
    cfg_sha256: str
    representations: list
    kind: str = ""                      # as declared; "" = not declared (a legacy module: effectively "system")
    extends: str = ""
    manifest_path: Path = None
    manifest_sha256: str = ""
    relations_path: Path = None         # the module's relations.yaml, if it has one
    relations_sha256: str = ""
    relations: list = field(default_factory=list)

    @property
    def layered(self) -> bool:
        """A layered module declares extends or relations; everything else is a legacy module."""
        return bool(self.extends) or self.relations_path is not None

    @property
    def schema_version(self) -> int:
        return SCHEMA_LAYERED if self.layered else SCHEMA_VERSION

    @property
    def effective_kind(self) -> str:
        return self.kind or "system"

    def dependencies(self) -> list:
        """The layers this one depends on: its extends parent and every relation target layer, sorted."""
        deps = {r.target.layer for r in self.relations}
        if self.extends:
            deps.add(self.extends)
        return sorted(deps)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _read_manifest(manifest_path: Path):
    """The manifest's first fenced YAML block as a mapping, or None if the file, the block or the YAML is unusable."""
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = MANIFEST_FENCE.search(text)
    if not m:
        return None
    import yaml
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _manifest_module(manifest_path: Path):
    data = _read_manifest(manifest_path)
    return str(data.get("module")) if data is not None and data.get("module") is not None else None


def _layer_fields(data: dict, module: str, manifest_name: str, has_relations: bool) -> tuple:
    """(kind, extends, problems) from a manifest mapping. Absent kind and extends mean a legacy system module, so
    every existing manifest validates unchanged. Each problem names the key and the fix."""
    problems = []
    kind = data.get("kind")
    extends = data.get("extends")
    kind = "" if kind is None else kind
    extends = "" if extends is None else extends
    if not isinstance(kind, str) or (kind and kind not in LAYER_KINDS):
        problems.append(f"{manifest_name}: kind {kind!r} is not one of {', '.join(LAYER_KINDS)} — use homebrew for "
                        f"your own rules, thirdparty for a published supplement, variant for a setting or conversion "
                        f"built on a system, system for a standalone system")
        kind = ""
    if not isinstance(extends, str) or (extends and not SYSTEM_NAME.match(extends)):
        problems.append(f"{manifest_name}: extends {extends!r} must be one layer id matching {SYSTEM_NAME.pattern}")
        extends = ""
    if extends and extends == module:
        problems.append(f"{manifest_name}: extends names the layer itself; name the layer this one builds on")
    if extends and not kind:
        problems.append(f"{manifest_name}: extends is declared but kind is not — add kind: homebrew, thirdparty or "
                        f"variant")
    if kind in ("variant", "thirdparty", "homebrew") and not extends:
        problems.append(f"{manifest_name}: kind {kind} needs extends: <the layer it builds on or modifies>")
    if has_relations and not kind:
        problems.append(f"{manifest_name}: the layer has a {RELATIONS_FILE} but its manifest declares no kind — add "
                        f"kind (and extends, unless it is a standalone system)")
    return kind, extends, problems


def load_system_cfg(cfg_path) -> SystemCfg:
    """Parse and validate a module's index.cfg strictly. Raises SystemIndexError on any problem.

    CONTAINMENT (Codex 951). The index.cfg, the module's manifest and its relations.yaml must each resolve inside the
    module folder, links followed, before they are read; one that leads out is never opened and fails validation,
    so a build refuses before publishing and a freshness check reports it. Representation files were already held
    inside the module (collect)."""
    cfg_path = Path(cfg_path)
    where = f"{cfg_path.parent.name}/{cfg_path.name}"
    if not _inside(cfg_path, cfg_path.parent):
        raise SystemIndexError(f"{where} resolves outside its module folder (through a link); it is not read — "
                               f"replace the link with the file itself")
    try:
        cfg = load_cfg(cfg_path, strict=True)
    except (CfgError, FileNotFoundError) as e:
        raise SystemIndexError(f"{where}: {e}")

    problems = []
    for section, body in cfg.items():
        for pattern in body["patterns"]:
            problems.append(f"malformed line in [{section}] (not key = value): {pattern!r}")
    if "system" not in cfg:
        problems.append("missing [system] section")
    else:
        extra = sorted(set(cfg["system"]["settings"]) - {"module"})
        problems += [f"unknown key '{k}' in [system]" for k in extra]
        if "module" not in cfg["system"]["settings"]:
            problems.append("missing required key 'module' in [system]")
    module = str(cfg.get("system", {}).get("settings", {}).get("module", "")).strip()
    module_dir = cfg_path.parent
    layer_kind = layer_extends = ""      # not `kind`: the representation loop below reuses that name
    relations, relations_path = [], None
    if (module_dir / RELATIONS_FILE).is_file():
        if _inside(module_dir / RELATIONS_FILE, module_dir):
            relations_path = module_dir / RELATIONS_FILE
        else:
            problems.append(f"{RELATIONS_FILE} resolves outside the module (through a link); it is not read — replace "
                            f"the link with the file itself")
    if module and not SYSTEM_NAME.match(module):
        problems.append(f"module id {module!r} must match {SYSTEM_NAME.pattern}")
    elif module and not _inside(module_dir / f"{module}.md", module_dir):
        problems.append(f"the manifest {module}.md resolves outside the module (through a link); it is not read — "
                        f"replace the link with the file itself")
    elif module:
        data = _read_manifest(module_dir / f"{module}.md")
        declared = (str(data.get("module")) if data is not None and data.get("module") is not None else None)
        if declared != module:
            problems.append(f"module {module!r} does not match the module's manifest "
                            f"({module}.md declares {declared!r})")
        else:
            layer_kind, layer_extends, more = _layer_fields(data, module, f"{module}.md",
                                                            relations_path is not None)
            problems += more
        if relations_path is not None:
            relations, more = parse_relations(relations_path, module)
            problems += more

    reps = []
    for section, body in cfg.items():
        if section == "system":
            continue
        kind, _, name = section.partition(" ")
        if kind != "representation" or not name:
            problems.append(f"unknown section [{section}]")
            continue
        if name not in REPRESENTATIONS:
            problems.append(f"unknown representation '{name}' (known: {', '.join(REPRESENTATIONS)})")
            continue
        settings = {k: str(v).strip() for k, v in body["settings"].items()}
        allowed = {"path", "authority", "include"} | ({"exclude_keys", "row_refs"} if name == "dataset" else set())
        problems += [f"unknown key '{k}' in [{section}]" for k in sorted(set(settings) - allowed)]
        missing = [k for k in ("path", "authority", "include") if not settings.get(k)]
        problems += [f"missing required key '{k}' in [{section}]" for k in missing]
        if missing:
            continue
        rel = settings["path"].replace("\\", "/")
        target = module_dir / rel
        if Path(rel).is_absolute() or not _inside(target, module_dir):
            problems.append(f"[{section}] path {rel!r} resolves outside the module")
            continue
        if not target.is_dir():
            problems.append(f"[{section}] path {rel!r} does not exist")
            continue
        if settings["authority"] not in AUTHORITIES:
            problems.append(f"[{section}] authority must be one of {', '.join(AUTHORITIES)}")
            continue
        include = [p.strip() for p in settings["include"].split(",") if p.strip()]
        exclude = tuple(k.strip() for k in settings.get("exclude_keys", "").split(",") if k.strip())
        row_refs = tuple(k.strip() for k in settings.get("row_refs", "").split(",") if k.strip())
        if "row_refs" in settings and not row_refs:
            problems.append(f"[{section}] row_refs is empty")
        problems += [f"[{section}] row_refs lists {k!r} twice" for k in sorted({k for k in row_refs
                                                                               if row_refs.count(k) > 1})]
        reps.append(Representation(name, rel, target.resolve(), settings["authority"], include, exclude, row_refs))
    if not reps and "system" in cfg:
        problems.append("no [representation ...] section")
    for i, a in enumerate(reps):
        for b in reps[i + 1:]:
            if a.path == b.path or a.path in b.path.parents or b.path in a.path.parents:
                problems.append(f"representations '{a.name}' ({a.rel}) and '{b.name}' ({b.rel}) overlap")
    if problems:
        raise SystemIndexError(f"{where}: " + "; ".join(problems))

    manifest_path = (module_dir / f"{module}.md").resolve()
    cfg_obj = SystemCfg(module, module_dir.resolve(), cfg_path.resolve(),
                        hashlib.sha256(cfg_path.read_bytes()).hexdigest(), reps,
                        kind=layer_kind, extends=layer_extends, manifest_path=manifest_path,
                        manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                        relations_path=relations_path.resolve() if relations_path is not None else None,
                        relations_sha256=(hashlib.sha256(relations_path.read_bytes()).hexdigest()
                                          if relations_path is not None else ""),
                        relations=relations)
    collect(cfg_obj)
    return cfg_obj


def collect(cfg: SystemCfg) -> None:
    """Fill each representation's files: every file below its path matching an include glob, in a stable order.
    Each include must match at least one file, and every file must resolve inside the module."""
    problems = []
    for rep in cfg.representations:
        matched = {pattern: 0 for pattern in rep.include}
        files = []
        for where, dirs, names in os.walk(rep.path):
            dirs.sort()
            for n in sorted(names):
                hits = [p for p in rep.include if fnmatch.fnmatch(n.lower(), p.lower())]
                if not hits:
                    continue
                full = Path(where) / n
                if not _inside(full, cfg.module_dir):
                    problems.append(f"{full} resolves outside the module")
                    continue
                for p in hits:
                    matched[p] += 1
                files.append(full)
        rep.files = sorted(files, key=lambda p: rel_path(cfg, p))
        problems += [f"[representation {rep.name}] include {p!r} matches no file" for p, n in matched.items() if not n]
    if problems:
        raise SystemIndexError(f"{cfg.module_dir.name}/index.cfg: " + "; ".join(problems))


def rel_path(cfg: SystemCfg, path: Path) -> str:
    return Path(path).resolve().relative_to(cfg.module_dir).as_posix()


def source_fingerprint(cfg: SystemCfg) -> str:
    """Deterministic over the schema version, the config's bytes, and every input's normalised module-relative
    path and content hash, in a stable order. Never modification times."""
    h = hashlib.sha256()
    h.update(f"schema:{SCHEMA_VERSION}\n".encode())
    h.update(b"cfg:" + cfg.cfg_path.read_bytes() + b"\n")
    for rep in cfg.representations:
        h.update(f"rep:{rep.name}\n".encode())
        for f in rep.files:
            h.update(f"{rel_path(cfg, f)}\0{hashlib.sha256(f.read_bytes()).hexdigest()}\n".encode())
    return h.hexdigest()


def layered_fingerprint(cfg: SystemCfg, depends_on: dict) -> str:
    """A layered module's fingerprint: everything source_fingerprint covers, plus the manifest's and the relations
    file's bytes and the build id of every layer it depends on (`depends_on`: {layer: build_id}, from one registry
    snapshot). Deterministic; never modification times. Only ever used for a layered module."""
    h = hashlib.sha256()
    h.update(f"schema:{SCHEMA_LAYERED}\n".encode())
    h.update(b"cfg:" + cfg.cfg_path.read_bytes() + b"\n")
    h.update(b"manifest:" + cfg.manifest_path.read_bytes() + b"\n")
    h.update(b"relations:" + (cfg.relations_path.read_bytes() if cfg.relations_path is not None else b"\0none")
             + b"\n")
    for rep in cfg.representations:
        h.update(f"rep:{rep.name}\n".encode())
        for f in rep.files:
            h.update(f"{rel_path(cfg, f)}\0{hashlib.sha256(f.read_bytes()).hexdigest()}\n".encode())
    for layer in sorted(depends_on):
        h.update(f"depends_on:{layer}={depends_on[layer]}\n".encode())
    return h.hexdigest()


def fingerprint(cfg: SystemCfg, depends_on: dict = None) -> str:
    """The fingerprint a module's build records: source_fingerprint, unchanged, for a legacy module (so an existing
    module is never reported stale merely because the code changed); layered_fingerprint for a layered one."""
    if not cfg.layered:
        return source_fingerprint(cfg)
    return layered_fingerprint(cfg, depends_on or {})


# ---------------------------------------------------------------------------
# Layers: relations, canonical unit hashes, dependency order
# ---------------------------------------------------------------------------

def _address(raw, where: str, module: str, own: bool, problems: list):
    """One relations.yaml address, validated, or None. `own` = an entry in this layer (no `layer` key allowed)."""
    allowed = ADDRESS_KEYS if own else TARGET_KEYS
    if not isinstance(raw, dict):
        problems.append(f"{where}: must be a mapping with {', '.join(sorted(allowed))}")
        return None
    extra = sorted(set(raw) - allowed)
    if extra:
        hint = " — an entry is always in this layer, so it takes no layer" if own and "layer" in extra else ""
        problems.append(f"{where}: unknown key(s) {', '.join(extra)}{hint}")
    layer = module
    if not own:
        layer = raw.get("layer")
        if not isinstance(layer, str) or not SYSTEM_NAME.match(layer):
            problems.append(f"{where}: layer must be a layer id matching {SYSTEM_NAME.pattern}")
            return None
        if layer == module:
            problems.append(f"{where}: a relation's target must be in another layer, not {module!r} itself")
            return None
    key = raw.get("key")
    if not isinstance(key, str) or not key:
        problems.append(f"{where}: key is required: doc:<module-relative path> or rec:<dataset>/<record id>")
        return None
    if "#" in key:
        problems.append(f"{where}: key {key!r} contains '#'; anchors are not part of an entry key — give the "
                        f"document key and a section: {{heading: ..., level: ...}}")
        return None
    if not ENTRY_KEY.match(key):
        problems.append(f"{where}: key {key!r} must be doc:<module-relative path> or rec:<dataset>/<record id>, "
                        f"exactly as a search hit prints it")
        return None
    section = None
    if "section" in raw:
        sec = raw["section"]
        if key.startswith("rec:"):
            problems.append(f"{where}: a record key takes no section; remove it")
            return None
        if not isinstance(sec, dict) or set(sec) != SECTION_KEYS:
            problems.append(f"{where}: section must be {{heading: <exact heading text>, level: <1-6>}}")
            return None
        heading, level = sec["heading"], sec["level"]
        if not isinstance(heading, str) or not norm_heading(heading):
            problems.append(f"{where}: section heading must be the heading's text")
            return None
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 6:
            problems.append(f"{where}: section level must be an integer from 1 to 6 (the number of #s)")
            return None
        section = (heading, level)
    return Address(layer, key, section)


def parse_relations(path: Path, module: str) -> tuple:
    """(relations, problems) from a layer's relations.yaml: a YAML list of mappings

        - entry:  {key: <this layer's entry key>, section: {heading: ..., level: N}}    # section optional, docs only
          target: {layer: <other layer id>, key: <its entry key>, section: {...}}
          mode: override | add | extend | partition | fall_through | n_a
          status: derived | settled | open
          decided: YYYY-MM-DD          # required when settled
          decider: <who>               # required when settled; SELF-DECLARED, reported as such, never verified
          target_sha256: <64 hex>      # optional pin of the target unit's content (unit_hash); absent = unpinned
          note: <free text>            # optional

    Strict: unknown keys, malformed values and a repeated (entry, target) pair are all problems, each naming the
    item and the fix. Whether entries and targets exist is checked at build, against real databases."""
    import yaml
    where = f"{Path(path).parent.name}/{RELATIONS_FILE}"
    problems = []
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        return [], [f"{where}: unreadable YAML ({e})"]
    if data is None:
        data = []
    if not isinstance(data, list):
        return [], [f"{where}: must be a YAML list of relations (each item starting with '- entry:')"]
    out, seen = [], set()
    for i, item in enumerate(data, 1):
        at = f"{where} item {i}"
        if not isinstance(item, dict):
            problems.append(f"{at}: must be a mapping")
            continue
        extra = sorted(set(item) - RELATION_KEYS)
        if extra:
            problems.append(f"{at}: unknown key(s) {', '.join(extra)} (allowed: {', '.join(sorted(RELATION_KEYS))})")
        missing = [k for k in ("entry", "target", "mode", "status") if k not in item]
        if missing:
            problems.append(f"{at}: missing {', '.join(missing)}")
            continue
        entry = _address(item["entry"], f"{at} entry", module, True, problems)
        target = _address(item["target"], f"{at} target", module, False, problems)
        mode, status = item["mode"], item["status"]
        if mode not in RELATION_MODES:
            problems.append(f"{at}: mode {mode!r} is not one of {', '.join(RELATION_MODES)}")
        if status not in RELATION_STATUSES:
            problems.append(f"{at}: status {status!r} is not one of {', '.join(RELATION_STATUSES)}")
        decided, decider = item.get("decided", ""), item.get("decider", "")
        decided = decided.isoformat() if hasattr(decided, "isoformat") else decided
        if decided != "" and (not isinstance(decided, str) or not DATE.match(decided)):
            problems.append(f"{at}: decided must be a date, YYYY-MM-DD")
        if decider != "" and (not isinstance(decider, str) or not decider.strip()):
            problems.append(f"{at}: decider must be a name")
        if status == "settled" and (not decided or not decider):
            problems.append(f"{at}: a settled relation needs decided (YYYY-MM-DD) and decider")
        pin = item.get("target_sha256", "")
        if pin != "" and not isinstance(pin, str):
            problems.append(f"{at}: target_sha256 must be quoted, e.g. target_sha256: \"<hash>\" — unquoted, YAML "
                            f"can read a hash as a number")
        elif pin != "" and not HEX64.match(pin):
            problems.append(f"{at}: target_sha256 must be 64 lower-case hex digits (the target's unit hash)")
        note = item.get("note", "")
        if not isinstance(note, str):
            problems.append(f"{at}: note must be text")
        if entry is None or target is None:
            continue
        pair = (entry, target)
        if pair in seen:
            problems.append(f"{at}: repeats an earlier relation between {entry.label()} and {target.label()}")
            continue
        seen.add(pair)
        out.append(Relation(i, entry, target, str(mode), str(status), str(decided or ""), str(decider or ""),
                            str(pin or "")))
    return out, problems


def norm_heading(s: str) -> str:
    """get_section's heading normalisation (search_mcp_server._norm_heading), identical by design."""
    for a, b in (("—", "-"), ("–", "-"), ("’", "'"),
                 ("‘", "'"), ("“", '"'), ("”", '"')):
        s = s.replace(a, b)
    return " ".join(s.casefold().split()).strip(" -:#")


def _iter_headings(content: str, level: int):
    in_fence = False
    fence = ""
    for i, line in enumerate(content.splitlines()):
        m = _FENCE_RE.match(line)
        if m:
            if not in_fence:
                in_fence, fence = True, m.group(1)
            elif line.strip().startswith(fence):
                in_fence, fence = False, ""
            continue
        if in_fence:
            continue
        h = _ATX_RE.match(line)
        if h and len(h.group(1)) == level:
            yield i, h.group(2).strip()


def split_sections(content: str, level: int = 2, lead_title: str = None) -> list:
    """get_section's section split (search_mcp_server._split_sections), identical by design: [(title, body)] at ATX
    headings of `level`, deeper headings kept inside, text before the first heading as a leading section."""
    lines = content.splitlines(keepends=True)
    marks = list(_iter_headings(content, level))
    if not marks:
        return []
    out = []
    first = marks[0][0]
    if first > 0:
        preamble = "".join(lines[:first])
        if preamble.strip():
            h1 = next((t for _, t in _iter_headings(content, 1)), None)
            out.append((h1 or lead_title or "(opening)", preamble))
    starts = [i for i, _ in marks]
    for (start, title), end in zip(marks, starts[1:] + [len(lines)]):
        out.append((title, "".join(lines[start:end])))
    return out


def normalize_unit_text(text: str) -> str:
    """Line endings to LF, trailing whitespace removed from every line, leading and trailing blank lines dropped.
    No Unicode normalisation: a differently composed character is a change."""
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def canonical_unit_bytes(kind: str, text: str, heading: str = "", level: int = 0) -> bytes:
    """The exact bytes a unit hash covers, domain-separated by kind so equal text in different kinds never collides:

        record:   DOMAIN "record\\n" + the payload as canonical JSON (keys sorted, no whitespace, UTF-8)
        document: DOMAIN "document\\n" + normalize_unit_text(the document's indexed content)
        section:  DOMAIN "section\\n" + "<level>\\n" + norm_heading(heading) + "\\n" + normalize_unit_text(body)

    A document's indexed content is its text without YAML frontmatter, exactly as the database stores it."""
    if kind == "record":
        body = json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return UNIT_HASH_DOMAIN + b"record\n" + body.encode("utf-8")
    if kind == "document":
        return UNIT_HASH_DOMAIN + b"document\n" + normalize_unit_text(text).encode("utf-8")
    if kind == "section":
        return (UNIT_HASH_DOMAIN + b"section\n" + f"{level}\n".encode() + norm_heading(heading).encode("utf-8")
                + b"\n" + normalize_unit_text(text).encode("utf-8"))
    raise ValueError(f"unknown unit kind {kind!r}")


def unit_hash(kind: str, text: str, heading: str = "", level: int = 0) -> str:
    return hashlib.sha256(canonical_unit_bytes(kind, text, heading, level)).hexdigest()


def resolve_unit(conn, address: Address) -> tuple:
    """(hash, None) for the unit an address names in an open module database, or (None, why) when it does not
    resolve: no such entry, a section that matches no heading or more than one at its level."""
    if address.key.startswith("rec:"):
        row = conn.execute("SELECT payload FROM corpus_meta WHERE entry_key = ? AND representation = 'dataset'",
                           (address.key,)).fetchone()
        if row is None:
            return None, f"no record {address.key} in {address.layer}"
        return unit_hash("record", row[0]), None
    row = conn.execute("SELECT f.content, f.name FROM corpus_fts f JOIN corpus_meta m ON m.entry_key = f.entry_key "
                       "WHERE f.entry_key = ? AND m.representation != 'dataset'", (address.key,)).fetchone()
    if row is None:
        return None, f"no document {address.key} in {address.layer}"
    content, name = row[0] or "", row[1]
    if address.section is None:
        return unit_hash("document", content), None
    heading, level = address.section
    sections = split_sections(content, level, lead_title=name)
    hits = [(t, b) for t, b in sections if norm_heading(t) == norm_heading(heading)]
    if len(hits) != 1:
        found = ", ".join(repr(t) for t, _ in sections) or "none"
        return None, (f"{'no' if not hits else 'more than one'} level-{level} section {heading!r} in "
                      f"{address.layer}:{address.key} (sections at that level: {found})")
    title, body = hits[0]
    return unit_hash("section", body, title, level), None


def dependency_order(cfgs: list) -> list:
    """The given module configs in build order: every layer after the layers it depends on (dependencies(): extends
    and relation targets) that are among them, ties broken by module id. A cycle is refused, naming its members;
    a dependency outside the list is left to the build, which requires it to be registered already."""
    by_id = {c.module: c for c in cfgs}
    pending = {c.module: {d for d in c.dependencies() if d in by_id} for c in cfgs}
    order = []
    while pending:
        ready = sorted(m for m, deps in pending.items() if not deps)
        if not ready:
            raise DependencyCycle(pending)
        for m in ready:
            order.append(by_id[m])
            del pending[m]
        for deps in pending.values():
            deps.difference_update(ready)
    return order


# ---------------------------------------------------------------------------
# Discovery: Game_Systems and the declared private layer roots
# ---------------------------------------------------------------------------

def _root_content_problems(root_dir: Path, raw) -> list:
    """An EXISTING private root may hold only rules-layer folders — each with its own index.cfg — plus an optional
    README.md and dotfiles (.gitkeep and the like). Anything else, a folder without an index.cfg or any other file,
    means the folder is, or contains, something other than rules layers: typically existing lore, which declaring it
    would silently hide from lore search. That refuses, naming what was found and the fix. A root that does not
    exist yet, or is empty, holds nothing to hide and is accepted."""
    if not root_dir.exists():
        return []
    if not root_dir.is_dir():
        return [f"private root {raw!r} is a file, not a folder"]
    strays = []
    for child in sorted(root_dir.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            if not (child / "index.cfg").is_file():
                strays.append(child.name + "/")
        elif child.name.lower() not in LAYER_ROOT_ALLOWED_FILES:
            strays.append(child.name)
    if not strays:
        return []
    shown = ", ".join(strays[:5]) + (f" and {len(strays) - 5} more" if len(strays) > 5 else "")
    return [f"private root {raw!r} holds {shown}, which is not a rules layer: a private root may hold only layer "
            f"folders (each with its own index.cfg) and an optional README.md. If this is existing lore, declare a "
            f"dedicated folder instead (e.g. World_Building/Rules_Layers); if it is a layer still being written, add "
            f"its index.cfg first"]


def validate_private_roots(root: Path, raw_roots) -> tuple:
    """The declared private layer roots, normalised to corpus-relative POSIX paths, or SystemIndexError.

    Each root must be a relative path of at least two segments inside the corpus root (never a top-level directory),
    outside Game_Systems and the index directory, without '..', and neither equal to nor nested in another declared
    root. Two segments alone do not make a folder safe to hide, so an existing root must also hold only rules-layer
    folders (_root_content_problems): an existing tree of lore is refused. A root that does not exist yet, or is
    empty, is allowed: it holds no layers, and its exclusion matches nothing."""
    out, problems = [], []
    for raw in raw_roots:
        given = str(raw).strip().replace("\\", "/")
        r = given.strip("/")
        if not r:
            continue
        parts = r.split("/")
        if given.startswith("/") or re.match(r"^[A-Za-z]:", r) or ".." in parts or "." in parts:
            problems.append(f"private root {raw!r} must be a relative path inside the corpus, without '..'")
            continue
        if len(parts) < 2:
            problems.append(f"private root {raw!r} is a top-level directory; name a folder inside one, e.g. "
                            f"{parts[0]}/Rules_Layers")
            continue
        if parts[0].lower() in ("game_systems", "index", "python", ".git"):
            problems.append(f"private root {raw!r} may not be inside {parts[0]}/")
            continue
        if not _inside(Path(root) / r, Path(root)):
            problems.append(f"private root {raw!r} resolves outside the corpus")
            continue
        content = _root_content_problems(Path(root) / r, raw)
        if content:
            problems += content
            continue
        out.append(r)
    lowered = [r.lower() for r in out]
    for i, a in enumerate(lowered):
        for b in lowered[i + 1:]:
            if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                problems.append(f"private roots {a!r} and {b!r} overlap; declare each folder once")
    if problems:
        raise SystemIndexError("; ".join(problems))
    return tuple(out)


def known_modules(root: Path, private_roots=()) -> tuple:
    """({module id: module directory}, ambiguous ids) for every module the corpus holds, indexed or not. The
    module's manifest is always <directory>/<id>.md.

    Folders directly under Game_Systems/ and each private root are read in one of two ways:
      - A folder WITH an index.cfg is an indexable module, identified exactly as the builder identifies it: its id is
        the one the index.cfg declares (declared_module), which must match SYSTEM_NAME, and its <id>.md manifest must
        hold a fenced YAML block declaring that same `module:` (load_system_cfg's rule). The folder's name plays no
        part in the id, so Display_Name/index.cfg declaring stable_id is the module stable_id.
      - A folder WITHOUT one is a legacy module only when its manifest is <folder name in lower case>.md with a fenced
        YAML block (Baseline/baseline.md, DnD5e/dnd5e.md); a manifest that also declares `module:` must declare that
        same id.
    A folder that satisfies neither is not a module, and its id is never guessed.

    Conflicts follow the builder's find_cfg: an index.cfg claims both the id it declares and its folder's name
    (cfgs_for), and a legacy folder claims its id. An id claimed by more than one folder — within one tree or across
    Game_Systems and the private roots — is ambiguous, is never resolved to any of them, and is returned in the second
    element. A claim by an invalid index.cfg still counts, because the builder would also see it.

    CONTAINMENT. Nothing outside the corpus is opened, with links and junctions followed: a discovery root must
    resolve inside the corpus, a module folder inside its discovery root, and its index.cfg and manifest inside that
    folder, each checked before it is listed or read. A folder that leads out is not a module and claims nothing; an
    index.cfg or manifest that leads out is never read, so its folder is not a module (an escaping index.cfg still
    lets the folder claim its own name, which needs no read)."""
    claims, valid = {}, {}
    for base in _layer_bases(root, private_roots):
        if not base.is_dir() or not _inside(base, Path(root)):
            continue
        base_r = base.resolve()
        for d in sorted(base.iterdir(), key=lambda p: p.name.lower()):
            if not d.is_dir() or not _inside(d, base_r):
                continue
            folder, where = d.name.lower(), d.resolve()
            if (d / "index.cfg").is_file():
                declared = declared_module(d / "index.cfg") if _inside(d / "index.cfg", where) else None
                for i in {folder, declared} - {None}:
                    if SYSTEM_NAME.match(i):
                        claims.setdefault(i, set()).add(where)
                if declared is None or not SYSTEM_NAME.match(declared) or not _inside(d / f"{declared}.md", where):
                    continue
                data = _read_manifest(d / f"{declared}.md")
                if data is not None and data.get("module") is not None and str(data.get("module")) == declared:
                    valid[declared] = where
                continue
            if not SYSTEM_NAME.match(folder) or not _inside(d / f"{folder}.md", where):
                continue
            data = _read_manifest(d / f"{folder}.md")
            if data is None or (data.get("module") is not None and str(data.get("module")) != folder):
                continue
            claims.setdefault(folder, set()).add(where)
            valid[folder] = where
    ambiguous = {i for i, dirs in claims.items() if len(dirs) > 1}
    return {i: d for i, d in valid.items() if i not in ambiguous}, ambiguous


def parse_rules_layers(cfg: dict, root: Path) -> tuple:
    """(private roots, not-searched module ids) from the corpus config's [rules_layers] section.

    No section means neither: every output is then exactly what it was before layers existed. A section that IS
    present is strict, so a typo can never silently switch a guarantee off: a key other than private_roots and
    not_searched, a line that is not key = value, a key present but empty, or a section declaring neither, each
    raises SystemIndexError naming the problem and the fix. private_roots is validated by validate_private_roots;
    not_searched must name known modules (known_modules), case-insensitively, each once. A not-searched module is
    DECLARED loaded and not searched: nothing can verify that a caller has it in context."""
    if "rules_layers" not in cfg:
        return (), ()
    section = cfg["rules_layers"]
    settings = section.get("settings", {})
    problems = [f"line {p!r} is not key = value (write: private_roots = {p.strip().rstrip('/')})"
                for p in section.get("patterns", [])]
    for key in sorted(set(settings) - set(RULES_LAYERS_KEYS)):
        problems.append(f"unknown key {key!r} (the keys are {' and '.join(RULES_LAYERS_KEYS)})")
    lists = {}
    for key in RULES_LAYERS_KEYS:
        if key in settings:
            lists[key] = [x.strip() for x in str(settings[key] if settings[key] is not None else "").split(",")
                          if x.strip()]
    if "private_roots" in lists and not lists["private_roots"]:
        problems.append("private_roots names no folder; name at least one (e.g. private_roots = "
                        "World_Building/Rules_Layers), or remove the key")
    if "not_searched" in lists and not lists["not_searched"]:
        problems.append("not_searched names no module; name at least one (e.g. not_searched = baseline), or remove "
                        "the key")
    if not lists and not problems:
        problems.append("[rules_layers] declares neither private_roots nor not_searched; declare one, or remove the "
                        "section")
    if problems:
        raise SystemIndexError("; ".join(problems))
    private = validate_private_roots(root, lists.get("private_roots", []))
    names = [n.lower() for n in lists.get("not_searched", [])]
    known, ambiguous = known_modules(root, private)
    bad = []
    for n in sorted(set(names)):
        if names.count(n) > 1:
            bad.append(f"not_searched names {n!r} twice")
        if n in ambiguous:
            bad.append(f"not_searched names {n!r}, which more than one folder declares")
        elif n not in known:
            bad.append(f"not_searched names {n!r}, which is no known module (known: {', '.join(sorted(known)) or 'none'})")
    if bad:
        raise SystemIndexError("; ".join(bad))
    return private, tuple(dict.fromkeys(names))


def check_publication(sdir: Path, module: str, entry: dict) -> tuple:
    """(database path, {build_id, module, schema_version}, None) when a registry entry names a present generation
    whose own db_info agrees with it (build id, module, schema) and whose schema this code reads
    (SUPPORTED_DEPENDENCY_SCHEMAS); otherwise (None, None, why). Read-only. The generation is opened through
    open_contained, so a file that has become a link leading out of index/systems is refused, never read."""
    try:
        path = resolve_db(sdir, module, entry)
    except SystemIndexError as e:
        return None, None, str(e)
    if not path.exists():
        return None, None, f"its database {path.name} is missing; rebuild it (build_indexes.py --system {module})"
    import sqlite3
    try:
        conn, why = open_contained(path, sdir, lambda real: sqlite3.connect(f"{real.as_uri()}?mode=ro", uri=True))
        if conn is None:                    # containment enforced at the open itself
            return None, None, f"its database {why}"
        try:
            row = conn.execute("SELECT build_id, module, schema_version FROM db_info LIMIT 1").fetchone()
        finally:
            conn.close()
    except sqlite3.Error as e:
        return None, None, f"its database cannot be read ({e}); rebuild it (build_indexes.py --system {module})"
    if row is None or row[0] != entry.get("build_id") or row[1] != module:
        return None, None, (f"its database does not match the registry (a stale or wrong publication); rebuild it "
                            f"(build_indexes.py --system {module})")
    if row[2] != entry.get("schema_version"):
        return None, None, (f"the registry says schema {entry.get('schema_version')!r} but its database says "
                            f"{row[2]!r}; rebuild it (build_indexes.py --system {module})")
    if row[2] not in SUPPORTED_DEPENDENCY_SCHEMAS:
        return None, None, (f"its schema {row[2]!r} is not one this code reads "
                            f"({', '.join(map(str, SUPPORTED_DEPENDENCY_SCHEMAS))}); rebuild it")
    return path, {"build_id": row[0], "module": row[1], "schema_version": row[2]}, None


def _layer_bases(root: Path, private_roots=()) -> list:
    return [Path(root) / "Game_Systems"] + [Path(root) / r for r in private_roots]


def discover(root: Path, private_roots=()) -> list:
    """Every Game_Systems/<dir>/index.cfg, and every <private root>/<dir>/index.cfg, one level deep, in a stable
    order. With no private roots and no links leading out, this is exactly the original discovery.

    CONTAINMENT (Codex 951). Every builder lookup goes through here (cfgs_for, find_cfg, --all-systems, pruning), so
    nothing outside the corpus is ever offered to a reader: a discovery root must resolve inside the corpus, a module
    folder inside its discovery root, and its index.cfg inside that folder, links and junctions followed. Anything
    that leads out is left out, before any config is read, and is treated as absent."""
    found = []
    for base in _layer_bases(root, private_roots):
        if not base.is_dir() or not _inside(base, Path(root)):
            continue
        base_r = base.resolve()
        found += [p for p in sorted(base.glob("*/index.cfg"))
                  if _inside(p.parent, base_r) and _inside(p, p.parent.resolve())]
    return found


def declared_module(cfg_path: Path):
    """The module id an index.cfg declares, read without validating the rest (None if it declares none)."""
    try:
        text = Path(cfg_path).read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"(?m)^\s*module\s*=\s*([A-Za-z0-9_]+)\s*(?:#.*)?$", text)
    return m.group(1) if m else None


def cfgs_for(root: Path, module: str, private_roots=()) -> list:
    """Every index.cfg that claims `module`: by declaring it, or by sitting in a directory named like it."""
    return [p for p in discover(root, private_roots)
            if declared_module(p) == module or p.parent.name.lower() == module]


def find_cfg(root: Path, module: str, private_roots=()):
    """The one index.cfg for `module`, or None. Two claiming the same module — in one tree or across Game_Systems
    and the private roots — is an error: the later build would otherwise silently replace the first module's
    registry entry."""
    found = cfgs_for(root, module, private_roots)
    if len(found) > 1:
        raise SystemIndexError(f"module {module!r} is declared by more than one index.cfg: "
                               + ", ".join(f"{p.parent.name}/{p.name}" for p in found))
    if found and not any(_inside(found[0], base) for base in _layer_bases(root, private_roots)):
        raise SystemIndexError(f"{found[0]} resolves outside Game_Systems and the declared private roots")
    return found[0] if found else None


def temp_path(sdir: Path, module: str, build_id: str) -> Path:
    """Where a generation is built. The leading dot and .tmp suffix keep it outside GENERATION, so garbage
    collection can never mistake another build's work in progress for an unreferenced generation."""
    return Path(sdir) / f".{module}.{build_id}.tmp.db"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

def _flatten(prefix: str, value, out: list) -> None:
    if isinstance(value, dict):
        for k in sorted(value, key=str):
            _flatten(f"{prefix}.{k}" if prefix else str(k), value[k], out)
    elif isinstance(value, list):
        for item in value:
            _flatten(prefix, item, out)
    elif value is not None and value != "":
        out.append(f"{prefix}: {value}")


def project_record(record: dict, exclude_keys) -> str:
    """The record's search text: labelled lines for every key not excluded, lead keys first, then the rest in
    sorted order, nested maps and lists flattened. Deterministic for a given record."""
    out = []
    keys = [k for k in LEAD_KEYS if k in record] + sorted(k for k in record if k not in LEAD_KEYS)
    for k in keys:
        if k in exclude_keys:
            continue
        _flatten(k, record[k], out)
    return "\n".join(out)


def read_records(cfg: SystemCfg, rep: Representation):
    """Yield (relpath, dataset, raw_line, record) for every record, enforcing the record contract.

    Dataset identity is DECLARED, not inferred from the file name: every record carries `dataset`, every record in
    a file carries the same one, and no two files declare the same dataset. (Chosen over "the file stem is
    canonical" on the evidence of the first real module, whose datasets are named co-morphs in files named
    co_morphs.jsonl — the declared name is the one its own tooling uses.)"""
    seen, owner = {}, {}
    for f in rep.files:
        rel = rel_path(cfg, f)
        dataset = None
        with f.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                raw = line.rstrip("\n").rstrip("\r")
                if not raw.strip():
                    continue
                where = f"{rel}:{lineno}"
                try:
                    rec = json.loads(raw)
                except ValueError as e:
                    raise SystemIndexError(f"{where}: malformed record ({e})")
                if not isinstance(rec, dict):
                    raise SystemIndexError(f"{where}: a record must be a JSON object")
                rid, name = rec.get("id"), rec.get("name")
                if not isinstance(rid, str) or not rid.strip():
                    raise SystemIndexError(f"{where}: record has no id")
                if not isinstance(name, str) or not name.strip():
                    raise SystemIndexError(f"{where}: record {rid!r} has no name")
                declared = rec.get("dataset")
                if not isinstance(declared, str) or not declared.strip():
                    raise SystemIndexError(f"{where}: record {rid!r} has no dataset")
                if dataset is None:
                    dataset = declared
                    if dataset in owner:
                        raise SystemIndexError(f"{where}: dataset {dataset!r} is also declared by {owner[dataset]}")
                    owner[dataset] = rel
                elif declared != dataset:
                    raise SystemIndexError(f"{where}: record {rid!r} names dataset {declared!r}, which disagrees "
                                           f"with the rest of its file ({dataset!r})")
                if "source" in rec:
                    src = rec["source"]
                    if not (isinstance(src, dict) and isinstance(src.get("file"), str) and src["file"].strip()
                            and isinstance(src.get("anchors"), dict) and src["anchors"]):
                        raise SystemIndexError(f"{where}: record {rid!r} has a malformed source (it must be an "
                                               f"object with a non-empty file and non-empty anchors)")
                if rid in seen:
                    raise SystemIndexError(f"{where}: duplicate record id {rid!r} (first at {seen[rid]})")
                seen[rid] = where
                yield rel, dataset, raw, rec


def resolve_row_refs(rep: Representation, records: list) -> dict:
    """Provenance for source-less records, by id: {"via_row_refs": [{"index", "rows", "source"}]}, one entry per
    referenced table in first-reference order, rows sorted. records is every (relpath, dataset, raw, record) of
    the representation, since a reference may point into any of its files. Raises SystemIndexError naming every
    problem (up to five) — see the module docstring for the rules. Without row_refs, returns {}."""
    if not rep.row_refs:
        return {}
    by_id = {rec["id"]: rec for _, _, _, rec in records}
    resolved, used, problems = {}, set(), []
    for rel, _, _, rec in records:
        if "source" in rec:
            continue                      # a direct source governs; same-named fields are not references here
        where = f"{rel}: record {rec['id']!r}"
        present = [f for f in rep.row_refs if f in rec]
        used.update(present)
        if not present:
            problems.append(f"{where} has no source and no row reference ({', '.join(rep.row_refs)})")
            continue
        if len(present) > 1:
            problems.append(f"{where} has no source and {', '.join(present)}; it must have exactly one")
            continue
        field_name, refs = present[0], rec[present[0]]
        if not isinstance(refs, list) or not refs:
            problems.append(f"{where}: {field_name} must be a non-empty list of row references")
            continue
        tables, bad = {}, None
        for n, ref in enumerate(refs):
            at = f"{where}: {field_name}[{n}]"
            if not isinstance(ref, dict):
                bad = f"{at} must be an object with index and line"
            elif not isinstance(ref.get("index"), str) or not ref["index"].strip():
                bad = f"{at} has no index (the id of the record that owns the table)"
            elif isinstance(ref.get("line"), bool) or not isinstance(ref.get("line"), int):
                bad = f"{at} has no integer line"
            elif ref["index"] not in by_id:
                bad = f"{at}: index {ref['index']!r} does not resolve to a record in this module"
            elif not isinstance(by_id[ref["index"]].get("source"), dict):
                bad = f"{at}: {ref['index']!r} has no direct source (row references are one hop, never inherited)"
            else:
                src = by_id[ref["index"]]["source"]
                lo, hi = src.get("line_start"), src.get("line_end")
                if isinstance(lo, int) and isinstance(hi, int) and not lo <= ref["line"] <= hi:
                    bad = f"{at}: line {ref['line']} is outside {ref['index']!r}'s lines {lo}-{hi}"
            if bad:
                break
            tables.setdefault(ref["index"], set()).add(ref["line"])
        if bad:
            problems.append(bad)
            continue
        resolved[rec["id"]] = {"via_row_refs": [{"index": i, "rows": sorted(lines), "source": by_id[i]["source"]}
                                                for i, lines in tables.items()]}
    problems += [f"row_refs field {f!r} is used by no source-less record" for f in rep.row_refs if f not in used]
    if problems:
        more = f"; and {len(problems) - 5} more" if len(problems) > 5 else ""
        raise SystemIndexError("row references: " + "; ".join(problems[:5]) + more)
    return resolved


# ---------------------------------------------------------------------------
# Registry and generations
# ---------------------------------------------------------------------------

def systems_dir(index_dir: Path) -> Path:
    return Path(index_dir) / SYSTEMS_SUBDIR


def new_build_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def read_registry(sdir: Path) -> dict:
    """The registry, or an empty one if none exists yet. A registry that exists but cannot be read is an error:
    overwriting it would silently unpublish every module."""
    path = Path(sdir) / REGISTRY
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "systems": {}}
    try:
        reg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemIndexError(f"{path} is unreadable ({e}); fix or remove it by hand")
    if not isinstance(reg, dict) or not isinstance(reg.get("systems"), dict):
        raise SystemIndexError(f"{path} has no 'systems' mapping")
    return reg


def write_registry(sdir: Path, reg: dict) -> None:
    """Replace registry.json in one step. Raises OSError if it cannot be replaced."""
    path = Path(sdir) / REGISTRY
    tmp = Path(sdir) / f".{REGISTRY}.{os.getpid()}.tmp"
    try:
        tmp.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


@contextmanager
def registry_lock(sdir: Path):
    """Serialise registry read-modify-write across processes with an exclusive lock file. A lock older than
    LOCK_STALE_S is presumed abandoned by a crashed build and broken."""
    path = Path(sdir) / LOCK
    deadline = time.monotonic() + LOCK_TIMEOUT_S
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time():.0f}\n".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > LOCK_STALE_S:
                    path.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise SystemIndexError(f"timed out waiting for {path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def resolve_db(sdir: Path, module: str, entry: dict) -> Path:
    """The generation file a registry entry names, which must be a generation of that module inside sdir."""
    name = str(entry.get("db", ""))
    m = GENERATION.match(Path(name).name)
    target = (Path(sdir) / name)
    if not m or m["module"] != module or Path(name).name != name or not _inside(target, Path(sdir)):
        raise SystemIndexError(f"registry entry for {module!r} names {name!r}, which is outside index/systems or "
                               f"not a generation of that module")
    return target


# Why open_contained refused a file that resolved inside sdir before the open but not to the same file after it.
CHANGED_DURING_OPEN = "changed while being opened, so nothing was read from it"


def contained_real(path: Path, sdir: Path) -> tuple:
    """(its real path, None) when a generation file still resolves inside sdir, links and junctions followed;
    otherwise (None, why), `why` a phrase without its subject ("now resolves outside index/systems …").

    CONTAINMENT AT THE OPEN (Codex 957, 959, 961). resolve_db checks the name a registry entry gives, but the file can
    become a link leading out of index/systems between that check and the open. So every reader of a published
    generation calls this immediately before the open, opens the real path it returns, and calls it again once the
    file is open, before anything is read: open_contained does all three."""
    try:
        real = Path(path).resolve(strict=True)
    except OSError as e:
        return None, f"can no longer be opened ({e})"
    if not _inside(real, Path(sdir)):
        return None, "now resolves outside index/systems (through a link or junction), so it was not opened"
    return real, None


def open_contained(path: Path, sdir: Path, opener) -> tuple:
    """(connection, None), or (None, why): opener(real path) runs only once contained_real accepts the file, and the
    connection is closed unread when the file no longer resolves to the same place once open (CHANGED_DURING_OPEN)."""
    real, why = contained_real(path, sdir)
    if real is None:
        return None, why
    conn = opener(real)
    if contained_real(path, sdir)[0] != real:
        conn.close()
        return None, CHANGED_DURING_OPEN
    return conn, None


def collect_garbage(sdir: Path, reg: dict) -> list:
    """Remove generation files no registry entry names, best-effort: one still held open is left for later."""
    named = {str(e.get("db")) for e in reg.get("systems", {}).values()}
    removed = []
    for f in sorted(Path(sdir).glob("*.db")):
        if GENERATION.match(f.name) and f.name not in named:
            try:
                f.unlink()
                removed.append(f.name)
            except OSError:
                pass
    return removed

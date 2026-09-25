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

# changed 2026-09-24: created (Eclipse Phase import, phase 7 — per-module search).
# changed 2026-09-25: row_refs — provenance for records read from table rows, resolved one hop at build time.
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

SCHEMA_VERSION = 2
REPRESENTATIONS = ("verbatim", "compact", "dataset")
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


@dataclass
class SystemCfg:
    module: str
    module_dir: Path
    cfg_path: Path
    cfg_sha256: str
    representations: list


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _manifest_module(manifest_path: Path):
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
    return str(data.get("module")) if isinstance(data, dict) and data.get("module") is not None else None


def load_system_cfg(cfg_path) -> SystemCfg:
    """Parse and validate a module's index.cfg strictly. Raises SystemIndexError on any problem."""
    cfg_path = Path(cfg_path)
    where = f"{cfg_path.parent.name}/{cfg_path.name}"
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
    if module and not SYSTEM_NAME.match(module):
        problems.append(f"module id {module!r} must match {SYSTEM_NAME.pattern}")
    elif module:
        declared = _manifest_module(module_dir / f"{module}.md")
        if declared != module:
            problems.append(f"module {module!r} does not match the module's manifest "
                            f"({module}.md declares {declared!r})")

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

    cfg_obj = SystemCfg(module, module_dir.resolve(), cfg_path.resolve(),
                        hashlib.sha256(cfg_path.read_bytes()).hexdigest(), reps)
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


def discover(root: Path) -> list:
    """Every Game_Systems/<dir>/index.cfg, one level deep, in a stable order."""
    base = Path(root) / "Game_Systems"
    return sorted(base.glob("*/index.cfg")) if base.is_dir() else []


def declared_module(cfg_path: Path):
    """The module id an index.cfg declares, read without validating the rest (None if it declares none)."""
    try:
        text = Path(cfg_path).read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"(?m)^\s*module\s*=\s*([A-Za-z0-9_]+)\s*(?:#.*)?$", text)
    return m.group(1) if m else None


def cfgs_for(root: Path, module: str) -> list:
    """Every index.cfg that claims `module`: by declaring it, or by sitting in a directory named like it."""
    return [p for p in discover(root) if declared_module(p) == module or p.parent.name.lower() == module]


def find_cfg(root: Path, module: str):
    """The one index.cfg for `module`, or None. Two claiming the same module is an error: the later build would
    otherwise silently replace the first module's registry entry."""
    found = cfgs_for(root, module)
    if len(found) > 1:
        raise SystemIndexError(f"module {module!r} is declared by more than one index.cfg: "
                               + ", ".join(f"{p.parent.name}/{p.name}" for p in found))
    if found and not _inside(found[0], Path(root) / "Game_Systems"):
        raise SystemIndexError(f"{found[0]} resolves outside Game_Systems")
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

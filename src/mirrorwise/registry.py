"""Mirror catalog: loading, merging and validating the JSON data files."""

import json
import os
import pkgutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TRUST_LEVELS = ("upstream", "vendor", "community", "user")
EXPECT_TYPES = ("any", "contains", "regex", "json_key")
SCHEMA_VERSION = 1
DEFAULT_TRUST_ALLOWED = frozenset({"upstream", "vendor", "user"})


class DataError(Exception):
    """Raised when a mirrors file cannot be used."""


@dataclass(frozen=True)
class Mirror:
    id: str
    name: str
    eco: str
    url: str
    region: str = ""
    trust: str = "community"
    evidence: Tuple[str, ...] = ()
    confirmed: bool = False
    notes: str = ""
    upstream: bool = False

    @property
    def probe_base(self) -> str:
        """URL used for probing (cargo's ``sparse+`` prefix removed)."""
        return self.url[len("sparse+"):] if self.url.startswith("sparse+") else self.url


@dataclass(frozen=True)
class ProbeSpec:
    path: str
    expect_type: str = "any"
    expect_value: str = ""
    ok_status: Tuple[int, ...] = (200,)
    accept: str = ""
    max_bytes: int = 262144


@dataclass
class Ecosystem:
    key: str
    title: str
    probe: ProbeSpec
    upstream: Mirror
    mirrors: List[Mirror] = field(default_factory=list)

    def all_sources(self) -> List[Mirror]:
        return [self.upstream] + list(self.mirrors)

    def find(self, mirror_id: str) -> Optional[Mirror]:
        for m in self.all_sources():
            if m.id == mirror_id:
                return m
        return None


class Catalog:
    def __init__(self, ecosystems: Dict[str, Ecosystem], updated: str = ""):
        self.ecosystems = ecosystems
        self.updated = updated

    def keys(self) -> List[str]:
        return list(self.ecosystems)

    def get(self, key: str) -> Ecosystem:
        return self.ecosystems[key]

    def identify(self, eco: str, url: Optional[str]) -> Optional[Mirror]:
        """Find the catalog entry whose URL equals ``url`` (ignoring trailing slash)."""
        if not url or eco not in self.ecosystems:
            return None
        want = _norm(url)
        for m in self.ecosystems[eco].all_sources():
            if _norm(m.url) == want:
                return m
        return None


def _norm(url: str) -> str:
    return url.strip().rstrip("/").lower()


BUNDLED_NAME = "mirrors.json"


def bundled_path() -> Path:
    """Path used in messages only; the data itself is read with pkgutil so zipapps work."""
    return Path(__file__).resolve().parent / "data" / BUNDLED_NAME


def load_bundled_doc() -> dict:
    raw = pkgutil.get_data("mirrorwise", "data/" + BUNDLED_NAME)
    if raw is None:
        raise DataError("bundled mirrors.json is missing")
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise DataError("bundled mirrors.json is invalid JSON: %s" % exc)


def user_data_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "mirrorwise" / "mirrors.json"


def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise DataError("file not found: %s" % path)
    except json.JSONDecodeError as exc:
        raise DataError("%s: invalid JSON: %s" % (path, exc))


def _mirror_from_dict(eco: str, d: dict, upstream: bool, default_trust: str = "community") -> Mirror:
    return Mirror(
        id=str(d.get("id", "")),
        name=str(d.get("name", d.get("id", ""))),
        eco=eco,
        url=str(d.get("url", "")),
        region=str(d.get("region", "")),
        trust=str(d.get("trust", "upstream" if upstream else default_trust)),
        evidence=tuple(d.get("evidence", []) or []),
        confirmed=bool(d.get("confirmed", False)),
        notes=str(d.get("notes", "")),
        upstream=upstream,
    )


def _probe_from_dict(d: dict) -> ProbeSpec:
    expect = d.get("expect") or {"type": "any"}
    return ProbeSpec(
        path=str(d.get("path", "")),
        expect_type=str(expect.get("type", "any")),
        expect_value=str(expect.get("value", "")),
        ok_status=tuple(int(x) for x in d.get("ok_status", [200])),
        accept=str(d.get("accept", "")),
        max_bytes=int(d.get("max_bytes", 262144)),
    )


def validate_document(doc: dict, source: str = "<data>", user_overlay: bool = False) -> List[str]:
    """Return a list of human-readable problems (empty list means valid)."""
    problems: List[str] = []

    def bad(msg):
        problems.append("%s: %s" % (source, msg))

    if not isinstance(doc, dict):
        return ["%s: top level must be an object" % source]
    if doc.get("schema_version") != SCHEMA_VERSION:
        bad("schema_version must be %d" % SCHEMA_VERSION)
    ecos = doc.get("ecosystems")
    if not isinstance(ecos, dict) or not ecos:
        bad("'ecosystems' must be a non-empty object")
        return problems

    seen_ids = set()
    for key, spec in ecos.items():
        where = "ecosystems.%s" % key
        if not isinstance(spec, dict):
            bad("%s must be an object" % where)
            continue
        if not user_overlay:
            probe = spec.get("probe")
            if not isinstance(probe, dict) or "path" not in probe:
                bad("%s.probe.path is required" % where)
            else:
                expect = probe.get("expect") or {}
                if expect.get("type", "any") not in EXPECT_TYPES:
                    bad("%s.probe.expect.type must be one of %s" % (where, EXPECT_TYPES))
                if expect.get("type") in ("contains", "regex", "json_key") and not expect.get("value"):
                    bad("%s.probe.expect.value is required for type %s" % (where, expect.get("type")))
            if not isinstance(spec.get("upstream"), dict):
                bad("%s.upstream is required" % where)
        entries = []
        if isinstance(spec.get("upstream"), dict):
            entries.append(("upstream", spec["upstream"], True))
        for i, m in enumerate(spec.get("mirrors", []) or []):
            if isinstance(m, dict):
                entries.append(("mirrors[%d]" % i, m, False))
            else:
                bad("%s.mirrors[%d] must be an object" % (where, i))
        for label, m, is_up in entries:
            w = "%s.%s" % (where, label)
            mid = m.get("id")
            if not mid or not isinstance(mid, str):
                bad("%s.id is required" % w)
            elif mid in seen_ids:
                bad("%s.id '%s' is duplicated" % (w, mid))
            else:
                seen_ids.add(mid)
            url = m.get("url", "")
            if not isinstance(url, str) or not url:
                bad("%s.url is required" % w)
            else:
                check = url[len("sparse+"):] if url.startswith("sparse+") else url
                if not check.startswith("https://"):
                    bad("%s.url must start with https:// (got %r)" % (w, url))
                if key == "cargo" and not url.startswith("sparse+"):
                    bad("%s.url must start with sparse+ for cargo" % w)
                if key == "cargo" and not url.endswith("/"):
                    bad("%s.url must end with / for cargo" % w)
            trust = m.get("trust", "upstream" if is_up else ("user" if user_overlay else "community"))
            if trust not in TRUST_LEVELS:
                bad("%s.trust must be one of %s" % (w, TRUST_LEVELS))
            if is_up and trust != "upstream":
                bad("%s.trust must be 'upstream'" % w)
            if not is_up and trust == "upstream":
                bad("%s.trust 'upstream' is reserved for the official registry" % w)
            ev = m.get("evidence", [])
            if not isinstance(ev, list) or any(not str(e).startswith("https://") for e in ev):
                bad("%s.evidence must be a list of https:// URLs" % w)
            elif not ev and not user_overlay and m.get("confirmed", False) is not True and not is_up:
                bad("%s needs at least one evidence URL (or confirmed=true)" % w)
    return problems


def _build_catalog(doc: dict, overlay: bool = False, base: Optional[Catalog] = None) -> Catalog:
    ecosystems: Dict[str, Ecosystem] = dict(base.ecosystems) if base else {}
    for key, spec in doc["ecosystems"].items():
        if overlay and key in ecosystems:
            eco = ecosystems[key]
            eco = Ecosystem(eco.key, eco.title, eco.probe, eco.upstream, list(eco.mirrors))
            disabled = set(spec.get("disable", []) or [])
            eco.mirrors = [m for m in eco.mirrors if m.id not in disabled]
            for md in spec.get("mirrors", []) or []:
                new = _mirror_from_dict(key, md, False, default_trust="user")
                eco.mirrors = [m for m in eco.mirrors if m.id != new.id] + [new]
            ecosystems[key] = eco
        elif overlay:
            warn("mirrorwise: ignoring unknown ecosystem '%s' in an overlay data file" % key)
            continue
        else:
            ecosystems[key] = Ecosystem(
                key=key,
                title=str(spec.get("title", key)),
                probe=_probe_from_dict(spec["probe"]),
                upstream=_mirror_from_dict(key, spec["upstream"], True),
                mirrors=[_mirror_from_dict(key, m, False) for m in spec.get("mirrors", []) or []],
            )
    return Catalog(ecosystems, updated=str(doc.get("updated", "")) if not overlay else (base.updated if base else ""))


def load_catalog(extra_paths: Optional[List[str]] = None, use_user_file: bool = True) -> Catalog:
    """Bundled data, then the user file, then any ``--data`` files (later wins)."""
    doc = load_bundled_doc()
    problems = validate_document(doc, str(bundled_path()))
    if problems:
        raise DataError("; ".join(problems))
    catalog = _build_catalog(doc)

    overlays: List[Path] = []
    if use_user_file:
        up = user_data_path()
        if up.exists():
            overlays.append(up)
    for p in extra_paths or []:
        overlays.append(Path(p))

    for p in overlays:
        odoc = _load_json(p)
        problems = validate_document(odoc, str(p), user_overlay=True)
        if problems:
            raise DataError("; ".join(problems))
        catalog = _build_catalog(odoc, overlay=True, base=catalog)
    return catalog


def custom_mirror(eco: str, url: str, mirror_id: str = "custom") -> Mirror:
    return Mirror(id=mirror_id, name="custom URL", eco=eco, url=url, region="", trust="user", evidence=(), confirmed=False, upstream=False)


def lint_file(path: Optional[str], overlay: bool = False) -> Tuple[List[str], Optional[Catalog]]:
    """Validate ``path``; ``None`` means the bundled file.

    With ``overlay=True`` the file is checked the way ``--data`` files are
    loaded: it may only extend or disable entries of the bundled catalog.
    """
    try:
        doc = load_bundled_doc() if path is None else _load_json(Path(path))
    except DataError as exc:
        return [str(exc)], None
    path = path or str(bundled_path())
    if not overlay:
        problems = validate_document(doc, path)
        if problems:
            return problems, None
        return [], _build_catalog(doc)

    problems = validate_document(doc, path, user_overlay=True)
    if problems:
        return problems, None
    base = _build_catalog(load_bundled_doc())
    for key, spec in doc["ecosystems"].items():
        eco = base.ecosystems.get(key)
        if eco is None:
            problems.append("%s: ecosystems.%s: unknown ecosystem (known: %s)" % (path, key, ", ".join(sorted(base.ecosystems))))
            continue
        known = {m.id for m in eco.all_sources()}
        for mid in spec.get("disable", []) or []:
            if mid not in known:
                problems.append("%s: ecosystems.%s.disable: unknown mirror id '%s'" % (path, key, mid))
    if problems:
        return problems, None
    return [], _build_catalog(doc, overlay=True, base=base)


def warn(msg: str) -> None:
    sys.stderr.write(msg + "\n")

"""Backend interface: one class per ecosystem knows where its config lives and how to edit it."""

import difflib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .. import fsutil
from ..registry import Mirror


class ConflictError(Exception):
    """The existing config cannot be edited safely by a program."""


@dataclass
class Outcome:
    path: Optional[Path]
    old_text: Optional[str]
    new_text: Optional[str]
    wrote: bool
    diff: str = ""
    note_key: Optional[str] = None
    command: Optional[str] = None  # set by backends that run a tool instead of writing a file


SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
KV_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*[=:]\s*(.*?)\s*$")


def parse_sections(text: str) -> Dict[str, Dict[str, str]]:
    """Very small INI/TOML-lite reader: section -> {key: value}. Good enough for status output."""
    result: Dict[str, Dict[str, str]] = {"": {}}
    section = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        m = SECTION_RE.match(raw)
        if m:
            section = m.group(1).strip().replace(" ", "")
            result.setdefault(section, {})
            continue
        kv = KV_RE.match(raw)
        if kv:
            value = kv.group(2)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            result.setdefault(section, {})[kv.group(1)] = value
    return result


def unified(old: Optional[str], new: str, path: Path) -> str:
    return "".join(
        difflib.unified_diff(
            (old or "").splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=str(path) + (" (current)" if old is not None else " (does not exist)"),
            tofile=str(path) + " (new)",
        )
    )


def detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


class Backend:
    eco = ""
    note_key: Optional[str] = None

    # --- to be provided by subclasses -------------------------------------------------
    def default_path(self) -> Path:
        raise NotImplementedError

    def read_current(self, path_override: Optional[str] = None) -> Tuple[Optional[str], str]:
        """Return ``(url_or_None, human readable source)`` for the active setting."""
        raise NotImplementedError

    def render(self, url: str, existing: Optional[str]) -> str:
        raise NotImplementedError

    def env_vars(self, url: str) -> Dict[str, str]:
        return {}

    # --- shared behaviour --------------------------------------------------------------
    def path(self, override: Optional[str] = None) -> Path:
        return Path(override).expanduser() if override else self.default_path()

    def apply(self, mirror: Mirror, path_override: Optional[str] = None, dry_run: bool = False) -> Outcome:
        path = self.path(path_override)
        old = fsutil.read_text(path)
        new = self.render(mirror.url, old)
        diff = unified(old, new, path)
        if dry_run or new == old:
            return Outcome(path, old, new, False, diff, self.note_key)
        entry = fsutil.backup_target(self.eco, path, mirror.id)
        try:
            fsutil.atomic_write(path, new)
        except BaseException:
            fsutil.discard_entry(entry)
            raise
        return Outcome(path, old, new, True, diff, self.note_key)


def home() -> Path:
    return Path(os.path.expanduser("~"))

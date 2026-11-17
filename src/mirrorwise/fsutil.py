"""Safe file handling: atomic writes, backups and an undo manifest."""

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


def state_dir() -> Path:
    override = os.environ.get("MIRRORWISE_STATE_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "mirrorwise"
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "mirrorwise"


def atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` through a temp file in the same directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = None
    if path.exists():
        mode = path.stat().st_mode & 0o777
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_text(path: Path) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


@dataclass
class Entry:
    eco: str
    target: str
    backup: Optional[str]  # None => the target did not exist before
    created: str
    mirror_id: str
    reverted: bool = False


def _manifest_path() -> Path:
    return state_dir() / "manifest.json"


def load_manifest() -> List[Entry]:
    text = read_text(_manifest_path())
    if not text:
        return []
    try:
        return [Entry(**e) for e in json.loads(text)]
    except (ValueError, TypeError):
        return []


def _save_manifest(entries: List[Entry]) -> None:
    atomic_write(_manifest_path(), json.dumps([e.__dict__ for e in entries], indent=2) + "\n")


def backup_target(eco: str, target: Path, mirror_id: str) -> Entry:
    """Copy ``target`` (if it exists) into the state dir and record how to undo."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path: Optional[Path] = None
    if Path(target).exists():
        folder = state_dir() / "backups" / eco
        folder.mkdir(parents=True, exist_ok=True)
        backup_path = folder / ("%s-%s" % (stamp, Path(target).name))
        n = 1
        while backup_path.exists():
            n += 1
            backup_path = folder / ("%s-%d-%s" % (stamp, n, Path(target).name))
        shutil.copy2(str(target), str(backup_path))
    entry = Entry(
        eco=eco,
        target=str(target),
        backup=str(backup_path) if backup_path else None,
        created=time.strftime("%Y-%m-%dT%H:%M:%S"),
        mirror_id=mirror_id,
    )
    entries = load_manifest()
    entries.append(entry)
    _save_manifest(entries)
    return entry


def is_managed(eco: str) -> bool:
    for e in reversed(load_manifest()):
        if e.eco == eco:
            return not e.reverted
    return False


def revert_last(eco: str):
    """Undo the most recent un-reverted change for ``eco``.

    Returns ``(kind, path)`` with kind in {"restored", "deleted", None}.
    """
    entries = load_manifest()
    for e in reversed(entries):
        if e.eco == eco and not e.reverted:
            target = Path(e.target)
            if e.backup is None:
                try:
                    target.unlink()
                except FileNotFoundError:
                    pass
                kind = "deleted"
            else:
                text = read_text(Path(e.backup))
                if text is None:
                    raise FileNotFoundError("backup is missing: %s" % e.backup)
                atomic_write(target, text)
                kind = "restored"
            e.reverted = True
            _save_manifest(entries)
            return kind, target
    return None, None


def revert_all(eco: str):
    """Undo every un-reverted change for ``eco``, newest first.

    Returns the list of ``(kind, path)`` results (empty when there was nothing to undo).
    """
    done = []
    while True:
        kind, path = revert_last(eco)
        if kind is None:
            return done
        done.append((kind, path))


def discard_entry(entry: Entry) -> None:
    """Forget a just-created backup entry (used when the write that followed it failed)."""
    entries = [e for e in load_manifest() if not (e.eco == entry.eco and e.created == entry.created and e.backup == entry.backup)]
    _save_manifest(entries)
    if entry.backup:
        try:
            os.unlink(entry.backup)
        except OSError:
            pass

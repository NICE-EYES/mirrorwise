import os
import re
from pathlib import Path
from typing import Optional, Tuple

from .. import fsutil
from .base import Backend, ConflictError, detect_newline, home, parse_sections

BEGIN = "# >>> mirrorwise (managed). Undo: mirrorwise revert cargo >>>"
END = "# <<< mirrorwise <<<"
SOURCE_TABLE_RE = re.compile(r"^\s*\[\s*source\s*\.\s*crates-io\s*\]", re.M)
INLINE_RE = re.compile(r"^\s*crates-io\s*=\s*\{", re.M)


class CargoBackend(Backend):
    eco = "cargo"
    note_key = None

    def default_path(self) -> Path:
        base = Path(os.environ.get("CARGO_HOME") or (home() / ".cargo"))
        legacy = base / "config"
        modern = base / "config.toml"
        if legacy.exists() and not modern.exists():
            return legacy
        return modern

    def read_current(self, path_override: Optional[str] = None) -> Tuple[Optional[str], str]:
        path = self.path(path_override)
        text = fsutil.read_text(path)
        if text:
            sections = parse_sections(text)
            name = sections.get("source.crates-io", {}).get("replace-with")
            if name:
                reg = sections.get("source." + name, {}).get("registry")
                if reg:
                    return reg, str(path)
        return None, str(path)

    @staticmethod
    def _split_block(text: str):
        start = text.find(BEGIN)
        end = text.find(END)
        if start != -1 and end != -1 and end > start:
            end_line = text.find("\n", end)
            end_line = len(text) if end_line == -1 else end_line + 1
            return text[:start], text[end_line:]
        return None

    def render(self, url: str, existing: Optional[str]) -> str:
        text = existing or ""
        nl = detect_newline(text)
        block = nl.join(
            [
                BEGIN,
                "[source.crates-io]",
                'replace-with = "mirrorwise"',
                "",
                "[source.mirrorwise]",
                'registry = "%s"' % url,
                END,
            ]
        ) + nl
        parts = self._split_block(text)
        if parts is not None:
            before, after = parts
            outside = before + after
        else:
            before, after, outside = text, "", text
        if SOURCE_TABLE_RE.search(outside) or INLINE_RE.search(outside):
            raise ConflictError(
                "config already replaces crates-io outside the mirrorwise block; merge by hand or remove that section"
            )
        if parts is not None:
            return before + block + after
        if before and not before.endswith(("\n", "\r")):
            before += nl
        if before.strip():
            before += nl
        return before + block

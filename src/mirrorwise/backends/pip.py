import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

from .. import fsutil
from .base import Backend, SECTION_RE, detect_newline, home, parse_sections

MARK = "# mirrorwise: managed. Undo: mirrorwise revert pip"


def _is_index_key(line: str) -> bool:
    stripped = line.lstrip().lower()
    for name in ("index-url", "index_url"):
        if stripped.startswith(name):
            rest = stripped[len(name):].lstrip()
            return rest[:1] in ("=", ":")
    return False


class PipBackend(Backend):
    eco = "pip"

    def default_path(self) -> Path:
        env = os.environ.get("PIP_CONFIG_FILE")
        if env and env.lower() != os.devnull.lower():
            return Path(env)
        if os.name == "nt":
            base = os.environ.get("APPDATA") or str(home() / "AppData" / "Roaming")
            return Path(base) / "pip" / "pip.ini"
        if sys.platform == "darwin":
            lib = home() / "Library" / "Application Support" / "pip"
            if lib.is_dir():
                return lib / "pip.conf"
        base = os.environ.get("XDG_CONFIG_HOME") or str(home() / ".config")
        return Path(base) / "pip" / "pip.conf"

    def read_current(self, path_override: Optional[str] = None) -> Tuple[Optional[str], str]:
        env = os.environ.get("PIP_INDEX_URL")
        if env:
            return env, "env PIP_INDEX_URL"
        path = self.path(path_override)
        text = fsutil.read_text(path)
        if text:
            sections = parse_sections(text)
            for name in ("install", "global"):
                for key in ("index-url", "index_url"):
                    if key in sections.get(name, {}):
                        return sections[name][key], str(path)
        return None, str(path)

    def render(self, url: str, existing: Optional[str]) -> str:
        text = existing or ""
        nl = detect_newline(text)
        lines = [l for l in text.splitlines() if l.strip() != MARK]
        out = []
        section = None
        global_header = None
        replaced_global = False
        skipping = False
        for line in lines:
            if skipping:
                if line[:1] in (" ", "\t") and line.strip() and not line.lstrip().startswith(("#", ";")):
                    continue
                skipping = False
            m = SECTION_RE.match(line)
            if m:
                section = m.group(1).strip().lower()
                out.append(line)
                if section == "global" and global_header is None:
                    global_header = len(out) - 1
                continue
            if section in ("global", "install") and _is_index_key(line):
                if section == "global":
                    if replaced_global:
                        skipping = True
                        continue
                    replaced_global = True
                out.append(MARK)
                out.append("index-url = " + url)
                skipping = True
                continue
            out.append(line)
        if not replaced_global:
            if global_header is not None:
                out[global_header + 1:global_header + 1] = [MARK, "index-url = " + url]
            else:
                if out and out[-1].strip():
                    out.append("")
                out += ["[global]", MARK, "index-url = " + url]
        return nl.join(out) + nl

    def env_vars(self, url: str) -> Dict[str, str]:
        return {"PIP_INDEX_URL": url, "UV_INDEX_URL": url}

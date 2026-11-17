import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from .. import fsutil
from .base import Backend, detect_newline, home

MARK = "; mirrorwise: managed. Undo: mirrorwise revert npm"
REG_RE = re.compile(r"^\s*registry\s*=\s*(.*?)\s*$")


class NpmBackend(Backend):
    eco = "npm"

    def default_path(self) -> Path:
        env = os.environ.get("NPM_CONFIG_USERCONFIG") or os.environ.get("npm_config_userconfig")
        return Path(env) if env else home() / ".npmrc"

    def read_current(self, path_override: Optional[str] = None) -> Tuple[Optional[str], str]:
        for var in ("npm_config_registry", "NPM_CONFIG_REGISTRY"):
            if os.environ.get(var):
                return os.environ[var], "env " + var
        path = self.path(path_override)
        text = fsutil.read_text(path)
        if text:
            found = None
            for line in text.splitlines():
                m = REG_RE.match(line)
                if m:
                    found = m.group(1)
            if found:
                return found, str(path)
        return None, str(path)

    def render(self, url: str, existing: Optional[str]) -> str:
        text = existing or ""
        nl = detect_newline(text)
        lines = [l for l in text.splitlines() if l.strip() != MARK]
        out = []
        placed = False
        for line in lines:
            if REG_RE.match(line):
                if not placed:
                    out.append(MARK)
                    out.append("registry=" + url)
                    placed = True
                continue
            out.append(line)
        if not placed:
            out.append(MARK)
            out.append("registry=" + url)
        return nl.join(out) + nl

    def env_vars(self, url: str) -> Dict[str, str]:
        return {"npm_config_registry": url}

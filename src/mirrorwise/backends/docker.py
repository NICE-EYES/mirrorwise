import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from .. import fsutil
from .base import Backend, ConflictError, home


class DockerBackend(Backend):
    eco = "docker"
    note_key = "restart_docker"

    def default_path(self) -> Path:
        if os.name == "nt" or sys.platform == "darwin":
            return home() / ".docker" / "daemon.json"
        return Path("/etc/docker/daemon.json")

    def read_current(self, path_override: Optional[str] = None) -> Tuple[Optional[str], str]:
        path = self.path(path_override)
        text = fsutil.read_text(path)
        if text and text.strip():
            try:
                data = json.loads(text)
            except ValueError:
                return None, str(path)
            mirrors = data.get("registry-mirrors") if isinstance(data, dict) else None
            if mirrors:
                return str(mirrors[0]), str(path)
        return None, str(path)

    def render(self, url: str, existing: Optional[str]) -> str:
        data = {}
        if existing and existing.strip():
            try:
                data = json.loads(existing)
            except ValueError as exc:
                raise ConflictError("daemon.json is not valid JSON (%s)" % exc)
            if not isinstance(data, dict):
                raise ConflictError("daemon.json must contain a JSON object")
        data["registry-mirrors"] = [url.rstrip("/")]
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

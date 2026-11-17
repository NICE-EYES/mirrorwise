import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

from .. import fsutil
from ..registry import Mirror
from .base import Backend, ConflictError, Outcome


class GoMissing(Exception):
    pass


def _go(*args: str) -> str:
    exe = shutil.which("go")
    if not exe:
        raise GoMissing("go not found")
    proc = subprocess.run([exe] + list(args), capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise ConflictError("`go %s` failed: %s" % (" ".join(args), (proc.stderr or proc.stdout).strip()))
    return proc.stdout.strip()


class GoBackend(Backend):
    """Go keeps its settings in a file managed by `go env -w`, so we call the tool itself."""

    eco = "go"

    def default_path(self) -> Path:
        try:
            out = _go("env", "GOENV")
            if out:
                return Path(out)
        except (GoMissing, ConflictError, OSError, subprocess.SubprocessError):
            pass
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path(os.path.expanduser("~")) / ".config")
        return Path(base) / "go" / "env"

    def read_current(self, path_override: Optional[str] = None) -> Tuple[Optional[str], str]:
        env = os.environ.get("GOPROXY")
        if env:
            return env.replace("|", ",").split(",")[0], "env GOPROXY"
        try:
            value = _go("env", "GOPROXY")
            if value:
                return value.replace("|", ",").split(",")[0], "go env GOPROXY"
        except (GoMissing, ConflictError, OSError, subprocess.SubprocessError):
            pass
        return None, "go not available"

    def render(self, url: str, existing: Optional[str]) -> str:
        raise NotImplementedError("go uses `go env -w`")

    def env_vars(self, url: str) -> Dict[str, str]:
        return {"GOPROXY": url + ",direct"}

    def apply(self, mirror: Mirror, path_override: Optional[str] = None, dry_run: bool = False) -> Outcome:
        value = mirror.url.rstrip("/") + ",direct" if not mirror.upstream else "https://proxy.golang.org,direct"
        command = "go env -w GOPROXY=%s" % value
        path = self.path(path_override)
        if dry_run:
            return Outcome(path, None, None, False, "", None, command)
        if not shutil.which("go"):
            raise GoMissing("go not found")
        entry = fsutil.backup_target(self.eco, path, mirror.id)
        try:
            _go("env", "-w", "GOPROXY=" + value)
        except BaseException:
            fsutil.discard_entry(entry)
            raise
        return Outcome(path, None, None, True, "", None, command)

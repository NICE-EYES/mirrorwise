from typing import Dict

from .base import Backend, ConflictError, Outcome
from .cargo import CargoBackend
from .docker import DockerBackend
from .go import GoBackend, GoMissing
from .npm import NpmBackend
from .pip import PipBackend

BACKENDS: Dict[str, Backend] = {
    "pip": PipBackend(),
    "npm": NpmBackend(),
    "go": GoBackend(),
    "cargo": CargoBackend(),
    "docker": DockerBackend(),
}

__all__ = ["BACKENDS", "Backend", "ConflictError", "Outcome", "GoMissing"]

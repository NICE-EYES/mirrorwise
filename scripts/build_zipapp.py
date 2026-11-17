#!/usr/bin/env python3
"""Build dist/mirrorwise.pyz: a single file you can copy around and run with any Python 3.9+.

    python scripts/build_zipapp.py
    python dist/mirrorwise.pyz doctor

Useful exactly when `pip install` is the thing that does not work: download the file from a
release, a USB stick or a chat, and run it.
"""
import shutil
import sys
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    out = ROOT / "dist" / "mirrorwise.pyz"
    out.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(
            ROOT / "src" / "mirrorwise",
            Path(tmp) / "mirrorwise",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        zipapp.create_archive(tmp, str(out), main="mirrorwise.cli:main", interpreter="/usr/bin/env python3", compressed=True)
    print("built %s (%d KB)" % (out, out.stat().st_size // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ZipappTests(unittest.TestCase):
    def test_pyz_runs_and_finds_bundled_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "mirrorwise.pyz"
            import shutil
            import zipapp

            pkg = Path(tmp) / "pkg"
            shutil.copytree(ROOT / "src" / "mirrorwise", pkg / "mirrorwise", ignore=shutil.ignore_patterns("__pycache__"))
            zipapp.create_archive(str(pkg), str(out), main="mirrorwise.cli:main")
            env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
            proc = subprocess.run([sys.executable, str(out), "lint-data"], capture_output=True, text=True, env=env, cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("mirrors data OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()

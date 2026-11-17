#!/usr/bin/env python3
"""Generate docs/demo.txt: a reproducible transcript that never touches your real configs or the internet.

Part 1 runs the REAL probe against local fixture servers (a server that drops connections the way a
filtering box does, one that answers correctly, one that serves a captive-portal page).
Part 2 replays a full outage -> switch -> failback cycle with SIMULATED probe results, because a
script cannot take pypi.org down. Everything else (planning, diff, backup, revert) is the real code.

    python scripts/demo.py [en|ru] > docs/demo.txt
"""
import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from mirrorwise import cli  # noqa: E402
from tests.helpers import FixtureServer, RawServer  # noqa: E402
from tests.test_cli import fake_probe  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "en"


def show(argv, patched=None, shown=None):
    cmd = shown or "mirrorwise " + " ".join(argv)
    print("$ " + cmd)
    buf = io.StringIO()  # one buffer for stdout and stderr keeps the real order of lines
    ctx = mock.patch.object(cli, "probe_many", patched) if patched else contextlib.nullcontext()
    with ctx, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = cli.main(["--lang", LANG, "--no-user-data"] + argv)
    text = buf.getvalue().replace(os.environ["PIP_CONFIG_FILE"], "~/.config/pip/pip.conf")
    print(text.rstrip("\n"))
    print("[exit code %d]\n" % code)
    return code


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        os.environ.update(
            HOME=str(root),
            MIRRORWISE_STATE_DIR=str(root / "state"),
            PIP_CONFIG_FILE=str(root / "pip.conf"),
            NPM_CONFIG_USERCONFIG=str(root / ".npmrc"),
        )
        for var in ("PIP_INDEX_URL", "npm_config_registry"):
            os.environ.pop(var, None)
        (root / "pip.conf").write_text("[global]\ntimeout = 60\n")

        print("# Part 1 - real probes against local fixture servers\n")
        routes = {"/simple/pip/": (200, "<a href='pip-24.0.tar.gz'>pip-24.0.tar.gz</a>", {})}
        portal = {"/simple/pip/": (200, "<html>Please log in to the guest Wi-Fi</html>", {})}
        with RawServer("reset") as dropped, FixtureServer(routes) as good, FixtureServer(portal) as captive:
            show(["probe", "pip", "--no-proxy", "--timeout", "3", "--url", "https://127.0.0.1:%d/simple/" % dropped.port],
                 shown="mirrorwise probe pip --url https://<host-that-drops-the-TLS-handshake>/simple/")
            show(["probe", "pip", "--no-proxy", "--timeout", "3", "--url", good.url + "/simple/"],
                 shown="mirrorwise probe pip --url http://<healthy-mirror>/simple/")
            show(["probe", "pip", "--no-proxy", "--timeout", "3", "--url", captive.url + "/simple/"],
                 shown="mirrorwise probe pip --url http://<captive-portal>/simple/")

        print("# Part 2 - outage, switch and failback (SIMULATED probe results, real planning and file handling)\n")
        down = fake_probe(
            down={"pypi", "yandex-pypi-alt"},
            latency={"yandex-pypi": 140.0, "tuna-pypi": 420.0, "aliyun-pypi": 610.0, "depkit-pypi": 90.0},
        )
        up = fake_probe(latency={"pypi": 180.0})
        show(["doctor", "pip"], down)
        show(["apply", "pip", "--dry-run"], down)
        show(["apply", "pip", "--yes"], down)
        print("$ cat ~/.config/pip/pip.conf")
        print((root / "pip.conf").read_text().rstrip() + "\n")
        show(["status", "pip"], down)
        show(["apply", "pip", "--yes"], up)
        print("$ cat ~/.config/pip/pip.conf")
        print((root / "pip.conf").read_text().rstrip())


if __name__ == "__main__":
    main()

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mirrorwise import cli, fsutil
from mirrorwise.probe import ProbeResult

from .helpers import FixtureServer


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(["--lang", "en", "--no-user-data"] + list(argv))
    return code, out.getvalue(), err.getvalue()


def fake_probe(down=(), slow=None, latency=None):
    """Return a replacement for probe_many: every source is healthy unless listed in ``down``."""
    slow = slow or {}
    latency = latency or {}

    def _probe(items, timeout=6.0, use_proxy=True, workers=12):
        results = []
        for mirror, _spec in items:
            ok = mirror.id not in down
            ms = slow.get(mirror.id, latency.get(mirror.id, 100.0))
            results.append(
                ProbeResult(
                    mirror_id=mirror.id,
                    eco=mirror.eco,
                    url=mirror.url,
                    ok=ok,
                    stage="ok" if ok else "tls",
                    detail="" if ok else "connection dropped during TLS handshake (ConnectionResetError)",
                    status=200 if ok else None,
                    latency_ms=ms,
                    size=1000 if ok else 0,
                    kb_per_s=500.0 if ok else None,
                )
            )
        return results

    return _probe


class CliBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.root = root
        env = {
            "HOME": str(root / "home"),
            "USERPROFILE": str(root / "home"),
            "MIRRORWISE_STATE_DIR": str(root / "state"),
            "PIP_CONFIG_FILE": str(root / "pip.conf"),
            "NPM_CONFIG_USERCONFIG": str(root / ".npmrc"),
            "CARGO_HOME": str(root / "cargo"),
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        for var in ("PIP_INDEX_URL", "npm_config_registry", "NPM_CONFIG_REGISTRY", "GOPROXY"):
            os.environ.pop(var, None)
        (root / "home").mkdir()
        self.pip_conf = root / "pip.conf"
        self.npmrc = root / ".npmrc"


class BasicCommandTests(CliBase):
    def test_lint_data(self):
        code, out, _ = run("lint-data")
        self.assertEqual(code, 0)
        self.assertIn("mirrors data OK", out)

    def test_lint_overlay_file(self):
        doc = {"schema_version": 1, "ecosystems": {"pip": {
            "mirrors": [{"id": "corp", "name": "Corp", "url": "https://nexus.example.com/pypi/simple/"}],
            "disable": ["depkit-pypi"]}}}
        path = Path(self.tmp.name) / "overlay.json"
        path.write_text(json.dumps(doc))
        code, out, _ = run("lint-data", "--overlay", str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("OK", out)
        # the same file is not a valid *full* document
        code, out, _ = run("lint-data", str(path))
        self.assertEqual(code, 2)
        self.assertIn("upstream is required", out)

    def test_lint_overlay_reports_typos(self):
        doc = {"schema_version": 1, "ecosystems": {
            "pipp": {"mirrors": []},
            "pip": {"disable": ["no-such-mirror"]}}}
        path = Path(self.tmp.name) / "bad_overlay.json"
        path.write_text(json.dumps(doc))
        code, out, _ = run("lint-data", "--overlay", str(path))
        self.assertEqual(code, 2)
        self.assertIn("unknown ecosystem", out)
        self.assertIn("unknown mirror id 'no-such-mirror'", out)

    def test_list_json(self):
        code, out, _ = run("list", "pip", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["pip"][0]["id"], "pypi")

    def test_unknown_ecosystem(self):
        code, _, err = run("list", "maven")
        self.assertEqual(code, 2)
        self.assertIn("unknown ecosystem", err)

    def test_status_reports_unset(self):
        code, out, _ = run("status", "pip", "npm")
        self.assertEqual(code, 0)
        self.assertIn("not configured", out)

    def test_russian_output(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            cli.main(["--lang", "ru", "--no-user-data", "status", "pip"])
        self.assertIn("Текущая конфигурация", out.getvalue())
        cli.set_lang("en")


class ExplicitApplyTests(CliBase):
    def test_apply_url_then_status_then_revert(self):
        routes = {"/simple/pip/": (200, "pip", {})}
        with FixtureServer(routes) as srv:
            url = srv.url + "/simple/"
            code, out, err = run("apply", "pip", "--url", url, "--allow-insecure", "--yes", "--no-proxy")
            self.assertEqual(code, 0, out + err)
            self.assertIn(url, self.pip_conf.read_text())
            code, out, _ = run("status", "pip")
            self.assertIn("custom", out)
            self.assertIn("managed by mirrorwise", out)
            code, out, _ = run("revert", "pip")
            self.assertEqual(code, 0)
            self.assertFalse(self.pip_conf.exists())

    def test_refuses_http_without_flag(self):
        code, _, err = run("apply", "pip", "--url", "http://127.0.0.1:1/simple/", "--yes")
        self.assertEqual(code, 2)
        self.assertIn("non-HTTPS", err)
        self.assertFalse(self.pip_conf.exists())

    def test_unhealthy_explicit_url_is_refused_unless_forced(self):
        with FixtureServer({}) as srv:  # always 404
            url = srv.url + "/simple/"
            code, _, err = run("apply", "pip", "--url", url, "--allow-insecure", "--yes", "--no-proxy", "--timeout", "2")
            self.assertEqual(code, 1)
            self.assertIn("--force", err)
            self.assertFalse(self.pip_conf.exists())
            code, _, _ = run("apply", "pip", "--url", url, "--allow-insecure", "--yes", "--no-proxy", "--timeout", "2", "--force")
            self.assertEqual(code, 0)
            self.assertTrue(self.pip_conf.exists())

    def test_dry_run_shows_diff_and_writes_nothing(self):
        routes = {"/simple/pip/": (200, "pip", {})}
        with FixtureServer(routes) as srv:
            code, out, _ = run("apply", "pip", "--url", srv.url + "/simple/", "--allow-insecure", "--dry-run", "--no-proxy")
        self.assertEqual(code, 0)
        self.assertIn("+index-url", out)
        self.assertIn("dry-run", out)
        self.assertFalse(self.pip_conf.exists())

    def test_non_interactive_needs_yes(self):
        routes = {"/simple/pip/": (200, "pip", {})}
        with FixtureServer(routes) as srv:
            with mock.patch("sys.stdin.isatty", return_value=False):
                code, _, err = run("apply", "pip", "--url", srv.url + "/simple/", "--allow-insecure", "--no-proxy")
        self.assertEqual(code, 2)
        self.assertIn("--yes", err)
        self.assertFalse(self.pip_conf.exists())

    def test_unknown_mirror_id(self):
        code, _, err = run("apply", "pip", "--mirror", "nope", "--yes")
        self.assertEqual(code, 2)
        self.assertIn("unknown mirror id", err)


class AutoModeTests(CliBase):
    def test_upstream_down_switches_to_fastest_vendor_mirror(self):
        probe = fake_probe(down={"pypi"}, latency={"tuna-pypi": 80.0, "yandex-pypi": 300.0, "depkit-pypi": 5.0})
        with mock.patch.object(cli, "probe_many", probe):
            code, out, _ = run("apply", "pip", "--yes")
        self.assertEqual(code, 0, out)
        self.assertIn("tuna-pypi", out)
        text = self.pip_conf.read_text()
        self.assertIn("https://pypi.tuna.tsinghua.edu.cn/simple/", text)
        self.assertNotIn("depkit", text)  # community mirror is opt-in

    def test_failback_when_upstream_recovers(self):
        with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi"})):
            run("apply", "pip", "--yes")
        self.assertTrue(self.pip_conf.exists())
        with mock.patch.object(cli, "probe_many", fake_probe()):
            code, out, _ = run("apply", "pip", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("restoring", out)
        self.assertFalse(self.pip_conf.exists())

    def test_upstream_healthy_changes_nothing(self):
        with mock.patch.object(cli, "probe_many", fake_probe()):
            code, out, _ = run("apply", "pip", "npm", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("nothing to change", out)
        self.assertFalse(self.pip_conf.exists())
        self.assertFalse(self.npmrc.exists())

    def test_nothing_healthy_exit_code(self):
        down = {"pypi", "yandex-pypi", "yandex-pypi-alt", "tuna-pypi", "aliyun-pypi", "depkit-pypi"}
        with mock.patch.object(cli, "probe_many", fake_probe(down=down)):
            code, out, _ = run("apply", "pip", "--yes", "--allow-community")
        self.assertEqual(code, 1)
        self.assertIn("no healthy source", out)
        self.assertFalse(self.pip_conf.exists())

    def test_allow_community_opt_in(self):
        down = {"pypi", "yandex-pypi", "yandex-pypi-alt", "tuna-pypi", "aliyun-pypi"}
        with mock.patch.object(cli, "probe_many", fake_probe(down=down)):
            code, _, _ = run("apply", "pip", "--yes")
            self.assertEqual(code, 1)
            code, out, _ = run("apply", "pip", "--yes", "--allow-community")
        self.assertEqual(code, 0)
        self.assertIn("pypi.depkit.ru", self.pip_conf.read_text())

    def test_all_ecosystems_in_one_run(self):
        down = {"pypi", "npmjs"}
        with mock.patch.object(cli, "probe_many", fake_probe(down=down)):
            with mock.patch("mirrorwise.backends.go.shutil.which", return_value=None):
                code, out, err = run("apply", "pip", "npm", "--yes")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(self.pip_conf.exists())
        self.assertTrue(self.npmrc.exists())

    def test_cargo_conflict_is_reported_not_overwritten(self):
        cargo = self.root / "cargo"
        cargo.mkdir()
        original = '[source.crates-io]\nreplace-with = "vendored"\n'
        (cargo / "config.toml").write_text(original)
        with mock.patch.object(cli, "probe_many", fake_probe(down={"crates-io"})):
            code, out, err = run("apply", "cargo", "--yes")
        self.assertEqual(code, 2)
        self.assertIn("cannot edit automatically", err)
        self.assertEqual((cargo / "config.toml").read_text(), original)


class CurrentSourceTests(CliBase):
    def test_healthy_custom_source_is_left_alone(self):
        original = "[global]\nindex-url = https://nexus.corp.example/simple/\n"
        self.pip_conf.write_text(original)
        with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi"})):
            code, out, _ = run("apply", "pip", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("configured source works", out)
        self.assertEqual(self.pip_conf.read_text(), original)

    def test_broken_custom_source_is_replaced_by_working_upstream(self):
        self.pip_conf.write_text("[global]\nindex-url = https://nexus.corp.example/simple/\n")
        with mock.patch.object(cli, "probe_many", fake_probe(down={"current"})):
            code, out, _ = run("apply", "pip", "--yes")
        self.assertEqual(code, 0)
        self.assertIn("configured source is broken", out)
        self.assertIn("https://pypi.org/simple/", self.pip_conf.read_text())

    def test_no_flapping_between_mirrors(self):
        # A mirror we installed keeps working while the official registry is still down.
        with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi"}, latency={"tuna-pypi": 50.0, "yandex-pypi": 300.0})):
            run("apply", "pip", "--yes")
            first = self.pip_conf.read_text()
        with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi"}, latency={"tuna-pypi": 900.0, "yandex-pypi": 100.0})):
            code, out, _ = run("apply", "pip", "--yes")
            self.assertEqual(code, 0)
            self.assertEqual(self.pip_conf.read_text(), first)
            code, out, _ = run("apply", "pip", "--yes", "--fastest")
            self.assertIn("mirror.yandex.ru", self.pip_conf.read_text())

    def test_apply_without_ecosystem_is_refused(self):
        code, _, err = run("apply", "--yes")
        self.assertEqual(code, 2)
        self.assertIn("choose an ecosystem", err)

    def test_env_override_warning(self):
        with mock.patch.dict(os.environ, {"PIP_INDEX_URL": "https://override.example/simple/"}):
            with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi", "current"})):
                code, out, err = run("apply", "pip", "--yes")
        self.assertIn("overrides the config file", err)


class WriteFailureTests(CliBase):
    def test_failed_write_leaves_no_phantom_backup(self):
        self.pip_conf.write_text("[global]\ntimeout = 5\n")
        real = fsutil.atomic_write

        def flaky(path, text):
            if Path(path) == self.pip_conf:  # fail only the config write, not the manifest write
                raise PermissionError(13, "denied", str(path))
            return real(path, text)

        with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi"})):
            with mock.patch("mirrorwise.fsutil.atomic_write", side_effect=flaky):
                code, _, err = run("apply", "pip", "--yes")
        self.assertEqual(code, 2)
        self.assertIn("no permission", err)
        self.assertFalse(fsutil.is_managed("pip"))
        self.assertEqual(fsutil.load_manifest(), [])
        backups = list((self.root / "state" / "backups").rglob("*")) if (self.root / "state" / "backups").exists() else []
        self.assertEqual([b for b in backups if b.is_file()], [])
        self.assertEqual(self.pip_conf.read_text(), "[global]\ntimeout = 5\n")


class ProbeUrlTests(CliBase):
    def test_probe_custom_url_ok_and_fail(self):
        routes = {"/simple/pip/": (200, "pip", {})}
        with FixtureServer(routes) as srv:
            code, out, _ = run("probe", "pip", "--url", srv.url + "/simple/", "--no-proxy")
            self.assertEqual(code, 0)
            self.assertIn("custom", out)
            self.assertIn("ok", out)
            code, out, _ = run("probe", "pip", "--url", srv.url + "/nope/", "--no-proxy", "--json")
            data = json.loads(out)
            self.assertFalse(data[0]["ok"])
            self.assertEqual(data[0]["status"], 404)

    def test_probe_url_needs_exactly_one_ecosystem(self):
        code, _, _ = run("probe", "--url", "https://x.test/")
        self.assertEqual(code, 2)


class DoctorTests(CliBase):
    def test_exit_codes(self):
        with mock.patch.object(cli, "probe_many", fake_probe()):
            code, out, _ = run("doctor", "pip")
        self.assertEqual(code, 0)
        self.assertIn("OK", out)
        with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi"})):
            code, out, _ = run("doctor", "pip")
        self.assertEqual(code, 1)
        self.assertIn("Run: mirrorwise apply pip", out)
        down = {"pypi", "yandex-pypi", "yandex-pypi-alt", "tuna-pypi", "aliyun-pypi", "depkit-pypi"}
        with mock.patch.object(cli, "probe_many", fake_probe(down=down)):
            code, out, _ = run("doctor", "pip")
        self.assertEqual(code, 2)

    def test_degraded(self):
        with mock.patch.object(cli, "probe_many", fake_probe(slow={"pypi": 9000.0}, latency={"tuna-pypi": 400.0})):
            code, out, _ = run("doctor", "pip")
        self.assertEqual(code, 1)
        self.assertIn("DEGRADED", out)

    def test_json(self):
        with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi"})):
            code, out, _ = run("doctor", "pip", "--json")
        data = json.loads(out)
        self.assertEqual(data[0]["eco"], "pip")
        self.assertFalse(data[0]["ok"])
        self.assertTrue(data[0]["suggested"])

    def test_configured_custom_source_is_probed(self):
        self.pip_conf.write_text("[global]\nindex-url = https://nexus.corp.example/simple/\n")
        seen = []

        def spy(items, timeout=6.0, use_proxy=True, workers=12):
            seen.extend(m.id for m, _ in items)
            return fake_probe(down={"current"})(items)

        with mock.patch.object(cli, "probe_many", spy):
            code, out, _ = run("doctor", "pip")
        self.assertIn("current", seen)
        self.assertIn("configured source", out)
        self.assertEqual(code, 1)  # configured source is down, a mirror is available


class EnvTests(CliBase):
    def test_sh_format_skips_healthy_upstream(self):
        with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi"})):
            code, out, err = run("env", "pip", "npm")
        self.assertEqual(code, 0)
        self.assertIn("export PIP_INDEX_URL='https://", out)
        self.assertNotIn("npm_config_registry", out)
        self.assertIn("npm:", err)

    def test_github_format_has_no_comments(self):
        with mock.patch.object(cli, "probe_many", fake_probe(down={"npmjs"})):
            code, out, _ = run("env", "npm", "--format", "github")
        lines = [l for l in out.splitlines() if l]
        self.assertTrue(all("=" in l and not l.startswith("#") for l in lines))
        self.assertTrue(lines[0].startswith("npm_config_registry=https://"))

    def test_go_gets_direct_fallback(self):
        with mock.patch.object(cli, "probe_many", fake_probe(down={"goproxy-official"})):
            code, out, _ = run("env", "go", "--format", "json")
        self.assertTrue(json.loads(out)["GOPROXY"].endswith(",direct"))

    def test_unsupported_ecosystem(self):
        code, _, err = run("env", "cargo")
        self.assertEqual(code, 2)
        self.assertIn("not supported", err)

    def test_requires_ecosystem(self):
        code, _, err = run("env")
        self.assertEqual(code, 2)

    def test_powershell_quotes(self):
        with mock.patch.object(cli, "probe_many", fake_probe(down={"pypi"})):
            code, out, _ = run("env", "pip", "--format", "powershell")
        self.assertIn("$env:PIP_INDEX_URL = 'https://", out)


class ShellQuoteTests(unittest.TestCase):
    def test_quote(self):
        self.assertEqual(cli._quote_sh("a'b"), "'a'\"'\"'b'")


if __name__ == "__main__":
    unittest.main()

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mirrorwise import fsutil
from mirrorwise.backends import BACKENDS, ConflictError
from mirrorwise.backends import cargo as cargo_mod
from mirrorwise.backends.pip import MARK as PIP_MARK
from mirrorwise.registry import Mirror


def mirror(eco, url, upstream=False):
    return Mirror(id="m", name="m", eco=eco, url=url, trust="vendor", upstream=upstream)


class TempState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        patcher = mock.patch.dict(os.environ, {"MIRRORWISE_STATE_DIR": str(self.root / "state")})
        patcher.start()
        self.addCleanup(patcher.stop)


class PipRenderTests(unittest.TestCase):
    be = BACKENDS["pip"]
    URL = "https://m.test/simple/"

    def test_empty_file(self):
        out = self.be.render(self.URL, None)
        self.assertEqual(out, "[global]\n%s\nindex-url = %s\n" % (PIP_MARK, self.URL))

    def test_keeps_other_keys_and_inserts_into_existing_global(self):
        src = "[global]\ntimeout = 60\n\n[install]\nuser = true\n"
        out = self.be.render(self.URL, src)
        self.assertEqual(out.count("[global]"), 1)
        self.assertIn("timeout = 60", out)
        self.assertIn("user = true", out)
        self.assertIn("index-url = " + self.URL, out)
        self.assertLess(out.index("index-url"), out.index("[install]"))

    def test_replaces_existing_index_url_and_continuation(self):
        src = "[global]\nindex-url = https://old.test/simple/\n  continued\ntimeout = 5\n"
        out = self.be.render(self.URL, src)
        self.assertNotIn("old.test", out)
        self.assertNotIn("continued", out)
        self.assertIn("timeout = 5", out)
        self.assertEqual(out.count("index-url"), 1)

    def test_also_overrides_install_section(self):
        src = "[install]\nindex-url = https://old.test/simple/\n"
        out = self.be.render(self.URL, src)
        self.assertEqual(out.count("index-url = " + self.URL), 2)  # [install] and the new [global]
        self.assertNotIn("old.test", out)

    def test_idempotent(self):
        once = self.be.render(self.URL, "[global]\ntimeout = 1\n")
        twice = self.be.render(self.URL, once)
        self.assertEqual(once, twice)

    def test_preserves_crlf(self):
        out = self.be.render(self.URL, "[global]\r\ntimeout = 1\r\n")
        self.assertIn("\r\n", out)
        self.assertNotIn("\n\n", out.replace("\r\n", ""))

    def test_result_parses_with_configparser_like_pip(self):
        import configparser

        for src in (None, "[global]\ntimeout = 60\n", "[global]\nindex-url = https://old/\n[install]\nindex-url = https://old2/\n"):
            cp = configparser.RawConfigParser()  # pip uses RawConfigParser, which rejects duplicate sections
            cp.read_string(self.be.render(self.URL, src))
            self.assertEqual(cp.get("global", "index-url"), self.URL)


class NpmRenderTests(unittest.TestCase):
    be = BACKENDS["npm"]

    def test_new_file(self):
        out = self.be.render("https://m.test/", None)
        self.assertIn("registry=https://m.test/", out)

    def test_replaces_registry_but_not_scoped(self):
        src = "registry=https://old/\n@corp:registry=https://corp.example/\n//corp.example/:_authToken=abc\n"
        out = self.be.render("https://m.test/", src)
        self.assertIn("@corp:registry=https://corp.example/", out)
        self.assertIn("_authToken=abc", out)
        self.assertNotIn("registry=https://old/", out)
        self.assertEqual(sum(1 for l in out.splitlines() if l.startswith("registry=")), 1)

    def test_idempotent(self):
        once = self.be.render("https://m.test/", "foo=bar\n")
        self.assertEqual(once, self.be.render("https://m.test/", once))


class CargoRenderTests(unittest.TestCase):
    be = BACKENDS["cargo"]
    URL = "sparse+https://m.test/index/"

    def test_adds_block(self):
        out = self.be.render(self.URL, "[net]\nretry = 3\n")
        self.assertIn("[net]\nretry = 3", out)
        self.assertIn('registry = "%s"' % self.URL, out)
        self.assertIn(cargo_mod.BEGIN, out)

    def test_replaces_own_block_only(self):
        first = self.be.render(self.URL, "[net]\nretry = 3\n")
        second = self.be.render("sparse+https://other.test/index/", first)
        self.assertNotIn("m.test", second)
        self.assertIn("other.test", second)
        self.assertEqual(second.count(cargo_mod.BEGIN), 1)
        self.assertIn("retry = 3", second)

    def test_refuses_foreign_source_replacement(self):
        with self.assertRaises(ConflictError):
            self.be.render(self.URL, '[source.crates-io]\nreplace-with = "vendored"\n')

    def test_valid_toml(self):
        if sys.version_info < (3, 11):
            self.skipTest("tomllib needs 3.11")
        import tomllib

        data = tomllib.loads(self.be.render(self.URL, "[net]\nretry = 3\n"))
        self.assertEqual(data["source"]["crates-io"]["replace-with"], "mirrorwise")
        self.assertEqual(data["source"]["mirrorwise"]["registry"], self.URL)


class DockerRenderTests(unittest.TestCase):
    be = BACKENDS["docker"]

    def test_merge_keeps_other_keys(self):
        out = json.loads(self.be.render("https://mirror.gcr.io", '{"log-level": "warn"}'))
        self.assertEqual(out["log-level"], "warn")
        self.assertEqual(out["registry-mirrors"], ["https://mirror.gcr.io"])

    def test_empty(self):
        self.assertEqual(json.loads(self.be.render("https://mirror.gcr.io/", None))["registry-mirrors"], ["https://mirror.gcr.io"])

    def test_invalid_json_is_a_conflict(self):
        with self.assertRaises(ConflictError):
            self.be.render("https://mirror.gcr.io", "{oops")


class ApplyRevertTests(TempState):
    def test_pip_apply_backup_revert_restores_exact_bytes(self):
        cfg = self.root / "pip.conf"
        original = "[global]\ntimeout = 60\n"
        cfg.write_text(original)
        out = BACKENDS["pip"].apply(mirror("pip", "https://m.test/simple/"), str(cfg))
        self.assertTrue(out.wrote)
        self.assertIn("m.test", cfg.read_text())
        self.assertTrue(fsutil.is_managed("pip"))
        res = fsutil.revert_all("pip")
        self.assertEqual(res[0][0], "restored")
        self.assertEqual(cfg.read_text(), original)
        self.assertFalse(fsutil.is_managed("pip"))

    def test_revert_deletes_file_that_did_not_exist(self):
        cfg = self.root / "sub" / ".npmrc"
        BACKENDS["npm"].apply(mirror("npm", "https://m.test/"), str(cfg))
        self.assertTrue(cfg.exists())
        res = fsutil.revert_all("npm")
        self.assertEqual(res[0][0], "deleted")
        self.assertFalse(cfg.exists())

    def test_two_applies_revert_back_to_original(self):
        cfg = self.root / "pip.conf"
        cfg.write_text("[global]\ntimeout = 9\n")
        be = BACKENDS["pip"]
        be.apply(mirror("pip", "https://a.test/simple/"), str(cfg))
        be.apply(mirror("pip", "https://b.test/simple/"), str(cfg))
        fsutil.revert_all("pip")
        self.assertEqual(cfg.read_text(), "[global]\ntimeout = 9\n")

    def test_dry_run_writes_nothing_and_shows_diff(self):
        cfg = self.root / "pip.conf"
        out = BACKENDS["pip"].apply(mirror("pip", "https://m.test/simple/"), str(cfg), dry_run=True)
        self.assertFalse(out.wrote)
        self.assertFalse(cfg.exists())
        self.assertIn("+index-url = https://m.test/simple/", out.diff)
        self.assertEqual(fsutil.load_manifest(), [])

    def test_same_content_does_not_create_backup(self):
        cfg = self.root / "pip.conf"
        be = BACKENDS["pip"]
        be.apply(mirror("pip", "https://m.test/simple/"), str(cfg))
        n = len(fsutil.load_manifest())
        out = be.apply(mirror("pip", "https://m.test/simple/"), str(cfg))
        self.assertFalse(out.wrote)
        self.assertEqual(len(fsutil.load_manifest()), n)

    def test_file_mode_is_preserved(self):
        if os.name == "nt":
            self.skipTest("posix modes")
        cfg = self.root / ".npmrc"
        cfg.write_text("foo=bar\n")
        os.chmod(cfg, 0o600)
        BACKENDS["npm"].apply(mirror("npm", "https://m.test/"), str(cfg))
        self.assertEqual(stat.S_IMODE(cfg.stat().st_mode), 0o600)

    def test_read_current(self):
        cfg = self.root / "pip.conf"
        BACKENDS["pip"].apply(mirror("pip", "https://m.test/simple/"), str(cfg))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PIP_INDEX_URL", None)
            url, source = BACKENDS["pip"].read_current(str(cfg))
        self.assertEqual(url, "https://m.test/simple/")
        self.assertEqual(source, str(cfg))


@unittest.skipIf(os.name == "nt", "fake go is a shell script")
class GoBackendTests(TempState):
    def make_fake_go(self):
        bindir = self.root / "bin"
        bindir.mkdir()
        envfile = self.root / "goenv"
        script = bindir / "go"
        script.write_text(
            "#!/bin/sh\n"
            'ENVFILE="%s"\n'
            'if [ "$1" = env ] && [ "$2" = GOENV ]; then echo "$ENVFILE"; exit 0; fi\n'
            'if [ "$1" = env ] && [ "$2" = -w ]; then echo "$3" > "$ENVFILE"; exit 0; fi\n'
            'if [ "$1" = env ] && [ "$2" = GOPROXY ]; then '
            '  if [ -f "$ENVFILE" ]; then sed "s/^GOPROXY=//" "$ENVFILE"; else echo https://proxy.golang.org,direct; fi; exit 0; fi\n'
            "exit 1\n" % envfile
        )
        script.chmod(0o755)
        return bindir, envfile

    def test_apply_and_revert(self):
        bindir, envfile = self.make_fake_go()
        env = {"PATH": str(bindir) + os.pathsep + os.environ["PATH"]}
        with mock.patch.dict(os.environ, env):
            os.environ.pop("GOPROXY", None)
            m = mirror("go", "https://goproxy.test/")
            dry = BACKENDS["go"].apply(m, dry_run=True)
            self.assertEqual(dry.command, "go env -w GOPROXY=https://goproxy.test,direct")
            self.assertFalse(envfile.exists())
            out = BACKENDS["go"].apply(m)
            self.assertTrue(out.wrote)
            self.assertEqual(envfile.read_text().strip(), "GOPROXY=https://goproxy.test,direct")
            self.assertEqual(BACKENDS["go"].read_current()[0], "https://goproxy.test")
            fsutil.revert_all("go")
            self.assertFalse(envfile.exists())

    def test_missing_go(self):
        from mirrorwise.backends import GoMissing

        with mock.patch.dict(os.environ, {"PATH": str(self.root)}):
            with self.assertRaises(GoMissing):
                BACKENDS["go"].apply(mirror("go", "https://goproxy.test/"))


class EnvVarTests(unittest.TestCase):
    def test_env_vars(self):
        self.assertEqual(BACKENDS["pip"].env_vars("https://m/simple/")["PIP_INDEX_URL"], "https://m/simple/")
        self.assertEqual(BACKENDS["npm"].env_vars("https://m/")["npm_config_registry"], "https://m/")
        self.assertEqual(BACKENDS["go"].env_vars("https://m"), {"GOPROXY": "https://m,direct"})
        self.assertEqual(BACKENDS["cargo"].env_vars("x"), {})
        self.assertEqual(BACKENDS["docker"].env_vars("x"), {})


if __name__ == "__main__":
    unittest.main()

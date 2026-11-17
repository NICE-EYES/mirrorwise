import unittest

from mirrorwise.probe import build_probe_url, probe_many, probe_url
from mirrorwise.registry import Mirror, ProbeSpec

from .helpers import FixtureServer, RawServer, free_port

PIP_SPEC = ProbeSpec(path="pip/", expect_type="contains", expect_value="pip")


class ProbeTests(unittest.TestCase):
    def test_build_probe_url(self):
        self.assertEqual(build_probe_url("https://x.test/simple/", "pip/"), "https://x.test/simple/pip/")
        self.assertEqual(build_probe_url("https://x.test", "/v2/"), "https://x.test/v2/")

    def test_ok(self):
        routes = {"/simple/pip/": (200, "<a>pip-24.0.tar.gz</a>", {})}
        with FixtureServer(routes) as srv:
            r = probe_url(srv.url + "/simple/pip/", PIP_SPEC, timeout=3, use_proxy=False)
        self.assertTrue(r.ok, r.detail)
        self.assertEqual(r.stage, "ok")
        self.assertEqual(r.status, 200)
        self.assertGreater(r.size, 0)
        self.assertIsNotNone(r.latency_ms)

    def test_http_error(self):
        with FixtureServer({}) as srv:
            r = probe_url(srv.url + "/simple/pip/", PIP_SPEC, timeout=3, use_proxy=False)
        self.assertFalse(r.ok)
        self.assertEqual(r.stage, "http")
        self.assertEqual(r.status, 404)

    def test_content_mismatch(self):
        routes = {"/simple/pip/": (200, "<html>captive portal</html>", {})}
        with FixtureServer(routes) as srv:
            r = probe_url(srv.url + "/simple/pip/", PIP_SPEC, timeout=3, use_proxy=False)
        self.assertFalse(r.ok)
        self.assertEqual(r.stage, "content")

    def test_accepted_alternative_status(self):
        spec = ProbeSpec(path="v2/", ok_status=(200, 401))
        routes = {"/v2/": (401, "{}", {"WWW-Authenticate": "Bearer"})}
        with FixtureServer(routes) as srv:
            r = probe_url(srv.url + "/v2/", spec, timeout=3, use_proxy=False)
        self.assertTrue(r.ok, r.detail)
        self.assertEqual(r.status, 401)

    def test_json_key(self):
        spec = ProbeSpec(path="config.json", expect_type="json_key", expect_value="dl")
        good = {"/config.json": (200, '{"dl": "https://x/{crate}", "api": "https://y"}', {})}
        bad = {"/config.json": (200, '{"nope": 1}', {})}
        with FixtureServer(good) as srv:
            self.assertTrue(probe_url(srv.url + "/config.json", spec, 3, False).ok)
        with FixtureServer(bad) as srv:
            r = probe_url(srv.url + "/config.json", spec, 3, False)
        self.assertEqual(r.stage, "content")

    def test_regex(self):
        spec = ProbeSpec(path="x", expect_type="regex", expect_value=r"(?m)^v\d+\.\d+\.\d+")
        with FixtureServer({"/x": (200, "v1.2.3\nv1.3.0\n", {})}) as srv:
            self.assertTrue(probe_url(srv.url + "/x", spec, 3, False).ok)

    def test_connection_refused(self):
        r = probe_url("http://127.0.0.1:%d/" % free_port(), PIP_SPEC, timeout=2, use_proxy=False)
        self.assertFalse(r.ok)
        self.assertEqual(r.stage, "connect")

    def test_dns_failure(self):
        r = probe_url("https://no-such-host.invalid/", PIP_SPEC, timeout=3, use_proxy=False)
        self.assertFalse(r.ok)
        self.assertEqual(r.stage, "dns")

    def test_tls_dropped_is_classified_as_tls(self):
        # The server accepts the TCP connection and closes it: what a filtering box looks like.
        with RawServer("reset") as srv:
            r = probe_url("https://127.0.0.1:%d/simple/pip/" % srv.port, PIP_SPEC, timeout=3, use_proxy=False)
        self.assertFalse(r.ok)
        self.assertEqual(r.stage, "tls", r.detail)

    def test_silent_server_is_timeout_or_tls(self):
        # TLS handshake never completes on a server that never answers.
        with RawServer("blackhole") as srv:
            r = probe_url("https://127.0.0.1:%d/" % srv.port, PIP_SPEC, timeout=1, use_proxy=False)
        self.assertFalse(r.ok)
        self.assertIn(r.stage, ("tls", "timeout"))

    def test_plain_http_timeout(self):
        with RawServer("blackhole") as srv:
            r = probe_url("http://127.0.0.1:%d/" % srv.port, PIP_SPEC, timeout=1, use_proxy=False)
        self.assertFalse(r.ok)
        self.assertEqual(r.stage, "timeout")

    def test_probe_many_keeps_order_and_ids(self):
        routes = {"/simple/pip/": (200, "pip", {})}
        with FixtureServer(routes) as srv:
            m1 = Mirror(id="a", name="a", eco="pip", url=srv.url + "/simple/", trust="user")
            m2 = Mirror(id="b", name="b", eco="pip", url="http://127.0.0.1:%d/simple/" % free_port(), trust="user")
            res = probe_many([(m1, PIP_SPEC), (m2, PIP_SPEC)], timeout=2, use_proxy=False)
        self.assertEqual([r.mirror_id for r in res], ["a", "b"])
        self.assertTrue(res[0].ok)
        self.assertFalse(res[1].ok)
        self.assertEqual(res[0].eco, "pip")


if __name__ == "__main__":
    unittest.main()

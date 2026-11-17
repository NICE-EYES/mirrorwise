import unittest

from mirrorwise.probe import ProbeResult
from mirrorwise.registry import Ecosystem, Mirror, ProbeSpec
from mirrorwise.selection import choose


def mk(mid, trust="vendor", upstream=False):
    return Mirror(id=mid, name=mid, eco="pip", url="https://%s.test/simple/" % mid, trust=trust, upstream=upstream)


def res(mid, ok=True, ms=100.0, stage=None):
    return ProbeResult(mirror_id=mid, eco="pip", url="x", ok=ok, stage="ok" if ok else (stage or "tls"), latency_ms=ms)


ECO = Ecosystem(
    key="pip",
    title="pip",
    probe=ProbeSpec(path="pip/"),
    upstream=mk("up", "upstream", True),
    mirrors=[mk("fast"), mk("slow"), mk("comm", "community")],
)


def results(**kw):
    return {k: v for k, v in kw.items()}


class ChooseTests(unittest.TestCase):
    def test_upstream_healthy_wins(self):
        r = results(up=res("up", True, 200), fast=res("fast", True, 50), slow=res("slow", True, 400), comm=res("comm", True, 10))
        c = choose(ECO, r)
        self.assertEqual(c.mirror.id, "up")
        self.assertEqual(c.reason, "upstream_ok")

    def test_upstream_down_picks_fastest_allowed(self):
        r = results(up=res("up", False), fast=res("fast", True, 80), slow=res("slow", True, 300), comm=res("comm", True, 5))
        c = choose(ECO, r)
        self.assertEqual(c.mirror.id, "fast")
        self.assertEqual(c.reason, "best_mirror")

    def test_community_needs_opt_in(self):
        r = results(up=res("up", False), fast=res("fast", False), slow=res("slow", False), comm=res("comm", True, 5))
        c = choose(ECO, r)
        self.assertIsNone(c.mirror)
        self.assertEqual(c.only_community.id, "comm")
        c2 = choose(ECO, r, allowed_trust={"upstream", "vendor", "user", "community"})
        self.assertEqual(c2.mirror.id, "comm")

    def test_nothing_healthy(self):
        r = results(up=res("up", False), fast=res("fast", False), slow=res("slow", False), comm=res("comm", False))
        c = choose(ECO, r)
        self.assertIsNone(c.mirror)
        self.assertEqual(c.reason, "none")
        self.assertIsNone(c.only_community)

    def test_degraded_upstream_switches_only_when_clearly_faster(self):
        r = results(up=res("up", True, 5000), fast=res("fast", True, 900), slow=res("slow", False), comm=res("comm", False))
        self.assertEqual(choose(ECO, r).reason, "degraded")
        r2 = results(up=res("up", True, 5000), fast=res("fast", True, 3000), slow=res("slow", False), comm=res("comm", False))
        self.assertEqual(choose(ECO, r2).reason, "upstream_ok")

    def test_fastest_mode(self):
        r = results(up=res("up", True, 200), fast=res("fast", True, 50), slow=res("slow", True, 400), comm=res("comm", True, 10))
        c = choose(ECO, r, fastest=True)
        self.assertEqual(c.mirror.id, "fast")
        self.assertEqual(c.reason, "fastest")

    def test_fastest_prefers_upstream_on_tie(self):
        r = results(up=res("up", True, 100), fast=res("fast", True, 100), slow=res("slow", False), comm=res("comm", False))
        self.assertEqual(choose(ECO, r, fastest=True).mirror.id, "up")

    def test_missing_results_are_treated_as_down(self):
        c = choose(ECO, {})
        self.assertIsNone(c.mirror)


if __name__ == "__main__":
    unittest.main()

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from mirrorwise import registry


class BundledDataTests(unittest.TestCase):
    def setUp(self):
        self.doc = registry.load_bundled_doc()

    def test_bundled_data_is_valid(self):
        self.assertEqual(registry.validate_document(self.doc), [])

    def test_all_ecosystems_present(self):
        self.assertEqual(set(self.doc["ecosystems"]), {"pip", "npm", "go", "cargo", "docker"})

    def test_every_mirror_has_evidence_or_is_confirmed(self):
        for eco, spec in self.doc["ecosystems"].items():
            for m in spec["mirrors"]:
                self.assertTrue(m["evidence"] or m.get("confirmed"), "%s/%s has no evidence" % (eco, m["id"]))

    def test_nothing_is_marked_confirmed_without_a_check(self):
        # Honesty guard: flip this only together with a real probe log in the PR.
        for spec in self.doc["ecosystems"].values():
            for m in spec["mirrors"]:
                self.assertFalse(m.get("confirmed"), m["id"])

    def test_ids_are_unique(self):
        ids = []
        for spec in self.doc["ecosystems"].values():
            ids.append(spec["upstream"]["id"])
            ids += [m["id"] for m in spec["mirrors"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_load_catalog(self):
        cat = registry.load_catalog(use_user_file=False)
        self.assertEqual(cat.get("pip").upstream.id, "pypi")
        self.assertTrue(cat.get("cargo").upstream.url.startswith("sparse+https://"))
        self.assertEqual(cat.get("cargo").upstream.probe_base, "https://index.crates.io/")

    def test_identify_ignores_trailing_slash_and_case(self):
        cat = registry.load_catalog(use_user_file=False)
        self.assertEqual(cat.identify("npm", "https://registry.npmmirror.com").id, "npmmirror")
        self.assertEqual(cat.identify("pip", "HTTPS://PYPI.ORG/simple").id, "pypi")
        self.assertIsNone(cat.identify("pip", "https://nexus.corp/simple/"))


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.doc = registry.load_bundled_doc()

    def problems(self, mutate):
        doc = copy.deepcopy(self.doc)
        mutate(doc)
        return registry.validate_document(doc, "t")

    def test_rejects_http_url(self):
        p = self.problems(lambda d: d["ecosystems"]["pip"]["mirrors"][0].update(url="http://x.test/simple/"))
        self.assertTrue(any("https://" in x for x in p))

    def test_rejects_missing_evidence(self):
        p = self.problems(lambda d: d["ecosystems"]["pip"]["mirrors"][0].update(evidence=[]))
        self.assertTrue(any("evidence" in x for x in p))

    def test_rejects_duplicate_id(self):
        p = self.problems(lambda d: d["ecosystems"]["npm"]["mirrors"][0].update(id="pypi"))
        self.assertTrue(any("duplicated" in x for x in p))

    def test_cargo_needs_sparse_prefix_and_trailing_slash(self):
        p = self.problems(lambda d: d["ecosystems"]["cargo"]["mirrors"][0].update(url="https://x.test/index"))
        self.assertTrue(any("sparse+" in x for x in p))
        p = self.problems(lambda d: d["ecosystems"]["cargo"]["mirrors"][0].update(url="sparse+https://x.test/index"))
        self.assertTrue(any("end with /" in x for x in p))

    def test_rejects_bad_trust(self):
        p = self.problems(lambda d: d["ecosystems"]["pip"]["mirrors"][0].update(trust="trustme"))
        self.assertTrue(any("trust" in x for x in p))

    def test_upstream_trust_reserved(self):
        p = self.problems(lambda d: d["ecosystems"]["pip"]["mirrors"][0].update(trust="upstream"))
        self.assertTrue(any("reserved" in x for x in p))

    def test_wrong_schema_version(self):
        p = self.problems(lambda d: d.update(schema_version=99))
        self.assertTrue(any("schema_version" in x for x in p))


class OverlayTests(unittest.TestCase):
    def write(self, doc):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        Path(path).write_text(json.dumps(doc), encoding="utf-8")
        self.addCleanup(os.unlink, path)
        return path

    def test_user_file_adds_and_disables(self):
        path = self.write(
            {
                "schema_version": 1,
                "ecosystems": {
                    "pip": {
                        "mirrors": [{"id": "corp-nexus", "name": "Corp", "url": "https://nexus.corp.example/pypi/simple/"}],
                        "disable": ["depkit-pypi"],
                    }
                },
            }
        )
        cat = registry.load_catalog([path], use_user_file=False)
        ids = [m.id for m in cat.get("pip").mirrors]
        self.assertIn("corp-nexus", ids)
        self.assertNotIn("depkit-pypi", ids)
        self.assertEqual(cat.get("pip").find("corp-nexus").trust, "user")

    def test_overlay_cannot_use_http(self):
        path = self.write(
            {"schema_version": 1, "ecosystems": {"pip": {"mirrors": [{"id": "x", "url": "http://insecure.example/simple/"}]}}}
        )
        with self.assertRaises(registry.DataError):
            registry.load_catalog([path], use_user_file=False)

    def test_bad_json(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        Path(path).write_text("{nope", encoding="utf-8")
        self.addCleanup(os.unlink, path)
        with self.assertRaises(registry.DataError):
            registry.load_catalog([path], use_user_file=False)


if __name__ == "__main__":
    unittest.main()

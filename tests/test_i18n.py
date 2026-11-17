import re
import unittest

from mirrorwise import i18n

PLACEHOLDER = re.compile(r"\{(\w+)[^}]*\}")


class CatalogTests(unittest.TestCase):
    def test_every_language_has_every_key(self):
        langs = sorted(i18n.MESSAGES)
        self.assertGreaterEqual(len(langs), 2)
        reference = set(i18n.MESSAGES[langs[0]])
        for lang in langs[1:]:
            keys = set(i18n.MESSAGES[lang])
            self.assertEqual(reference - keys, set(), "missing in %s" % lang)
            self.assertEqual(keys - reference, set(), "extra in %s" % lang)

    def test_placeholders_match_between_languages(self):
        langs = sorted(i18n.MESSAGES)
        base = i18n.MESSAGES[langs[0]]
        for lang in langs[1:]:
            for key, text in i18n.MESSAGES[lang].items():
                self.assertEqual(
                    set(PLACEHOLDER.findall(text)),
                    set(PLACEHOLDER.findall(base[key])),
                    "placeholder mismatch for %r in %s" % (key, lang),
                )


if __name__ == "__main__":
    unittest.main()

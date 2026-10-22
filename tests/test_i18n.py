import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rkarrousel import i18n


class I18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("fr")

    def test_both_languages_define_the_same_keys(self):
        self.assertEqual(set(i18n.STRINGS["fr"]), set(i18n.STRINGS["en"]))

    def test_placeholders_match_between_languages(self):
        field = re.compile(r"{(\w+)")
        for key, fr in i18n.STRINGS["fr"].items():
            self.assertEqual(set(field.findall(fr)), set(field.findall(i18n.STRINGS["en"][key])), key)

    def test_every_key_used_in_the_code_exists(self):
        used = set()
        for path in (ROOT / "rkarrousel" / "gui").rglob("*.py"):
            used |= set(re.findall(r"\bt\(\s*[\"']([\w-]+)[\"']", path.read_text(encoding="utf-8")))
        used |= {"set_kind_part1", "set_kind_part2", "kind_part_n", "width_original", "width_px"}
        used |= {f"fmt_{k}" for k in ("3x4", "4x5", "1x1", "9x16")}
        used |= {f"upd_{step}" for step in ("downloading", "verifying", "installing")}
        used |= {f"pos_{p}" for p in ("bottom-right", "bottom-center", "bottom-left")}
        used |= {f"kind_{k}" for k in ("framed", "with_sig", "part1", "part2", "part1_with_sig", "part2_with_sig", "crop34")}
        missing = sorted(key for key in used if key not in i18n.STRINGS["fr"])
        self.assertEqual(missing, [])

    def test_switching_language(self):
        i18n.set_language("en")
        self.assertEqual(i18n.t("about"), "About")
        i18n.set_language("fr")
        self.assertEqual(i18n.t("about"), "À propos")

    def test_unknown_language_falls_back_to_french(self):
        self.assertEqual(i18n.set_language("xx"), "fr")
        self.assertEqual(i18n.t("no_such_key"), "no_such_key")


if __name__ == "__main__":
    unittest.main()

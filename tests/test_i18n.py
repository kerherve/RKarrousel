import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import i18n


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
        for name in ("photo_splitter_gui.py", "order_window.py", "image_viewer.py", "crop_editor.py", "update_dialog.py"):
            used |= set(re.findall(r"\bt\(\s*[\"']([\w-]+)[\"']", (ROOT / name).read_text(encoding="utf-8")))
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

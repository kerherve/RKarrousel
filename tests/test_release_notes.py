import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from release_notes import section_for
from rkarrousel.services.updater import plain_notes
from rkarrousel.version import __version__

SAMPLE = "# Titre\n\n## v0.2.0\n\n- B\n\n## v0.1.0\n\n- A\n"


class ReleaseNotesTests(unittest.TestCase):
    def test_section_is_extracted_up_to_the_next_heading(self):
        self.assertEqual(section_for("v0.2.0", SAMPLE), "- B")
        self.assertEqual(section_for("0.1.0", SAMPLE), "- A")
        self.assertEqual(section_for("v9.9.9", SAMPLE), "")

    def test_the_changelog_describes_the_current_version(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertTrue(section_for(__version__, text), f"CHANGELOG.md sans section v{__version__}")
        self.assertEqual(re.findall(r"^## (v[\d.]+)$", text, re.M)[0], f"v{__version__}")

    def test_plain_notes_strips_markdown_and_the_auto_changelog_link(self):
        raw = "## Nouveautés\r\n\r\n* **Gras** et `code`\r\n- autre\r\n\r\n\r\n**Full Changelog**: https://x/compare/a...b"
        self.assertEqual(plain_notes(raw), "Nouveautés\n\n• Gras et code\n• autre")
        self.assertEqual(plain_notes("**Full Changelog**: https://x"), "")

    def test_plain_notes_keeps_only_the_wanted_language(self):
        raw = "### English\n\n- Hello\n\n### Français\n\n- Bonjour"
        self.assertEqual(plain_notes(raw, "fr"), "\u2022 Bonjour")
        self.assertEqual(plain_notes(raw, "en"), "\u2022 Hello")
        self.assertEqual(plain_notes(raw, "de"), "\u2022 Hello")  # langue inconnue : anglais
        self.assertEqual(plain_notes("- seul", "fr"), "\u2022 seul")  # notes sans parties par langue

    def test_every_changelog_section_has_both_languages(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for version in re.findall(r"^## (v[\d.]+)$", text, re.M):
            body = section_for(version, text)
            self.assertIn("### English", body, version)
            self.assertIn("### Français", body, version)
            self.assertLess(body.index("### English"), body.index("### Français"), version)


if __name__ == "__main__":
    unittest.main()

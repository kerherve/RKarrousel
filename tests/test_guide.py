import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rkarrousel.i18n.guide import MARKDOWN_FILES, get_guide, to_markdown

BLOCK_KINDS = {"p", "h", "note", "bullets", "steps"}


class GuideTests(unittest.TestCase):
    def test_both_languages_have_the_same_topics_and_block_layout(self):
        fr, en = get_guide("fr")[1], get_guide("en")[1]
        self.assertEqual([tid for tid, _, _ in fr], [tid for tid, _, _ in en])
        for (tid, _, fr_blocks), (_, _, en_blocks) in zip(fr, en):
            self.assertEqual([(k, len(c) if isinstance(c, list) else 0) for k, c in fr_blocks],
                             [(k, len(c) if isinstance(c, list) else 0) for k, c in en_blocks], tid)

    def test_blocks_are_well_formed(self):
        for lang in ("fr", "en"):
            for tid, title, blocks in get_guide(lang)[1]:
                self.assertTrue(title and blocks, tid)
                for kind, content in blocks:
                    self.assertIn(kind, BLOCK_KINDS, tid)
                    self.assertTrue(content, tid)
                    self.assertEqual(isinstance(content, list), kind in ("bullets", "steps"), tid)

    def test_backticks_are_balanced(self):
        for lang in ("fr", "en"):
            self.assertEqual(to_markdown(lang).count("`") % 2, 0)

    def test_markdown_files_are_up_to_date(self):
        for lang, name in MARKDOWN_FILES.items():
            self.assertEqual((ROOT / name).read_text(encoding="utf-8"), to_markdown(lang),
                             f"{name} périmé : lancer python tools/build_docs.py")

    def test_internal_links_of_the_docs_resolve(self):
        for path in list((ROOT / "docs").glob("*.md")) + [ROOT / "README.md"]:
            for target in re.findall(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)", path.read_text(encoding="utf-8")):
                self.assertTrue((path.parent / target).exists(), f"{path.name} → {target}")


if __name__ == "__main__":
    unittest.main()

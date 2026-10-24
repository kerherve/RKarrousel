"""Place des images « photo entière » d'un paysage dans le carrousel : avant / après le découpage, à la fin, aucune."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())

from rkarrousel import outputs, pipeline
from rkarrousel.gui.session import Session
from rkarrousel.kinds import placement_of
from tests.helpers import make_image


def kinds_of(items):
    return [kind for _, kind in items]


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.a = make_image(self.dir, "a.jpg", (900, 600))  # paysage 3:2
        self.b = make_image(self.dir, "b.jpg", (900, 600))

    def test_defaults_put_the_whole_photo_before_the_split(self):
        self.assertEqual(outputs.kinds_for_ratio("landscape_2_3", {}), ["part1_with_sig", "part1", "part2", "part2_with_sig"])
        self.assertEqual(placement_of({}, "part1_with_sig"), "before")
        self.assertEqual(placement_of({}, "part2_with_sig"), "inline")

    def test_each_place_for_the_upright_whole_photo(self):
        for place, expected in (
            ("before", ["part1_with_sig", "part1", "part2", "part2_with_sig"]),
            ("inline", ["part1", "part2", "part1_with_sig", "part2_with_sig"]),
            ("end", ["part1", "part2", "part2_with_sig", "part1_with_sig"]),
        ):
            config = {"kind_placement": {"part1_with_sig": place}}
            self.assertEqual(outputs.kinds_for_ratio("landscape_2_3", config), expected, place)

    def test_rotated_images_at_the_end_follow_the_photo_order(self):
        config = {"kind_placement": {"part2_with_sig": "end"}}
        items = pipeline.planned_items([self.a, self.b], config)
        self.assertEqual(kinds_of(items), ["part1_with_sig", "part1", "part2"] * 2 + ["part2_with_sig"] * 2)
        self.assertEqual([p.name for p, k in items if k == "part2_with_sig"], ["a.jpg", "b.jpg"])

    def test_default_keeps_each_photo_together(self):
        items = pipeline.planned_items([self.a, self.b], {})
        self.assertEqual([p.name for p, _ in items], ["a.jpg"] * 4 + ["b.jpg"] * 4)

    def test_none_is_the_disabled_kind(self):
        config = {"disabled_kinds": ["part2_with_sig"]}
        self.assertNotIn("part2_with_sig", kinds_of(pipeline.planned_items([self.a], config)))

    def test_numbering_follows_the_placement(self):
        out = self.dir / "out"
        pipeline.process_batch([self.a, self.b], out, {"frame_ratio": 0.03, "kind_placement": {"part2_with_sig": "end"}},
                               number_files=True)
        names = sorted(p.name for p in out.iterdir())
        self.assertIn("07_a_part2_with_sig.jpg", names)
        self.assertIn("08_b_part2_with_sig.jpg", names)
        self.assertIn("01_a_part1_with_sig.jpg", names)

    def test_invalid_placements_fall_back_to_the_defaults(self):
        self.assertEqual(placement_of({"kind_placement": {"part1_with_sig": "nowhere"}}, "part1_with_sig"), "before")
        self.assertEqual(placement_of({"kind_placement": "garbage"}, "part2_with_sig"), "inline")

    def test_changing_the_layout_resets_the_chosen_order(self):
        session = Session()
        session.order = ["x|part1"]
        session.sync_layout({})
        self.assertEqual(session.order, ["x|part1"])  # même disposition : l'ordre choisi est conservé
        session.sync_layout({"kind_placement": {"part2_with_sig": "end"}})
        self.assertEqual(session.order, [])


if __name__ == "__main__":
    unittest.main()

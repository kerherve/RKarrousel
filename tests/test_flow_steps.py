"""Règles du flux en étapes (sans écran) : quand peut-on avancer ?"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, Path(__file__).resolve().parent.parent.as_posix())

from rkarrousel.gui.flow.steps import LAST_STEP, STEP_IDS, blocker, last_reachable


class StepRulesTests(unittest.TestCase):
    def test_the_four_steps_in_order(self):
        self.assertEqual(STEP_IDS, ("photos", "order", "adjust", "export"))
        self.assertEqual(LAST_STEP, 3)

    def test_without_photos_or_destination_you_stay_on_the_first_step(self):
        self.assertEqual(last_reachable(False, True, None), 0)
        self.assertEqual(last_reachable(True, False, None), 0)
        self.assertEqual(blocker(False, True, None), "flow_need_photos")
        self.assertEqual(blocker(True, False, None), "flow_need_photos")

    def test_with_photos_and_destination_everything_is_reachable_until_the_grid_says_otherwise(self):
        self.assertEqual(last_reachable(True, True, None), LAST_STEP)  # grille pas encore calculée : on ne bloque pas
        self.assertEqual(last_reachable(True, True, 12), LAST_STEP)
        self.assertIsNone(blocker(True, True, None))
        self.assertIsNone(blocker(True, True, 12))

    def test_when_every_image_is_excluded_you_cannot_go_past_the_order_step(self):
        self.assertEqual(last_reachable(True, True, 0), 1)
        self.assertEqual(blocker(True, True, 0), "flow_need_images")


if __name__ == "__main__":
    unittest.main()

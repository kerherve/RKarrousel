"""Logique du viewer sans écran : zoom et déplacement, décision après un glisser, calculs en arrière-plan."""
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())

from rkarrousel.gui.viewer.carousel import SWIPE_FRACTION, SWIPE_MIN_FLICK, SWIPE_VELOCITY, swipe_decision
from rkarrousel.gui.viewer.render_jobs import RenderJobs
from rkarrousel.gui.viewer.viewport import MAX_SCALE, MIN_SCALE, Viewport
from tests.helpers import make_image


class ViewportTests(unittest.TestCase):
    def test_fit_centres_the_whole_image(self):
        view = Viewport()
        view.fit((1000, 2000), (500, 500))
        self.assertTrue(view.fit_mode)
        self.assertAlmostEqual(view.zoom, 0.25)
        self.assertEqual(view.visible_box((1000, 2000), (500, 500)), (0, 0, 1000, 2000))

    def test_zoom_keeps_the_point_under_the_cursor_fixed(self):
        view = Viewport()
        view.fit((1000, 1000), (500, 500))
        before = (view.ox + 200 / view.zoom, view.oy + 100 / view.zoom)
        self.assertTrue(view.zoom_at(200, 100, 2.0))
        self.assertFalse(view.fit_mode)
        after = (view.ox + 200 / view.zoom, view.oy + 100 / view.zoom)
        self.assertAlmostEqual(before[0], after[0])
        self.assertAlmostEqual(before[1], after[1])

    def test_zoom_is_clamped_and_reports_no_change_at_the_limits(self):
        view = Viewport()
        self.assertTrue(view.zoom_at(0, 0, 1e9))
        self.assertEqual(view.zoom, MAX_SCALE)
        self.assertFalse(view.zoom_at(0, 0, 2.0))
        view.zoom_at(0, 0, 1e-12)
        self.assertEqual(view.zoom, MIN_SCALE)

    def test_zoom_to_100_percent(self):
        view = Viewport()
        view.fit((4000, 3000), (800, 600))
        view.zoom_to(1.0, (800, 600))
        self.assertAlmostEqual(view.zoom, 1.0)

    def test_visible_box_is_cropped_to_the_image(self):
        view = Viewport()
        view.zoom, view.ox, view.oy = 1.0, -50.0, -50.0
        self.assertEqual(view.visible_box((100, 100), (300, 300)), (0, 0, 100, 100))
        view.ox = 500.0
        self.assertIsNone(view.visible_box((100, 100), (300, 300)))


class SwipeDecisionTests(unittest.TestCase):
    D = 500.0

    def test_short_slow_drag_springs_back(self):
        self.assertEqual(swipe_decision(-0.1 * self.D, self.D, 0, True, True), 0)

    def test_far_drag_changes_image_in_the_dragged_direction(self):
        far = (SWIPE_FRACTION + 0.05) * self.D
        self.assertEqual(swipe_decision(-far, self.D, 0, True, True), 1)   # vers la gauche : suivante
        self.assertEqual(swipe_decision(far, self.D, 0, True, True), -1)   # vers la droite : précédente

    def test_fast_flick_needs_a_minimum_distance(self):
        flick = (SWIPE_MIN_FLICK + 0.03) * self.D
        self.assertEqual(swipe_decision(-flick, self.D, -SWIPE_VELOCITY * 2, True, True), 1)
        tiny = (SWIPE_MIN_FLICK / 2) * self.D
        self.assertEqual(swipe_decision(-tiny, self.D, -SWIPE_VELOCITY * 2, True, True), 0)

    def test_no_neighbour_on_that_side_means_no_change(self):
        far = (SWIPE_FRACTION + 0.3) * self.D
        self.assertEqual(swipe_decision(-far, self.D, 0, True, False), 0)
        self.assertEqual(swipe_decision(far, self.D, 0, False, True), 0)

    def test_flick_in_the_opposite_direction_of_the_drag_does_not_count(self):
        slow = (SWIPE_MIN_FLICK + 0.05) * self.D
        self.assertEqual(swipe_decision(-slow, self.D, SWIPE_VELOCITY * 2, True, True), 0)


class RenderJobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.a = make_image(self.dir, "a.jpg", (300, 400))
        self.b = make_image(self.dir, "b.jpg", (300, 400))

    def collect(self, jobs, kinds, seconds=10):
        got, end = [], time.time() + seconds
        while time.time() < end and not kinds <= {k for k, _ in got}:
            got += jobs.drain()
            time.sleep(0.02)
        return got

    def test_main_image_and_neighbours_are_delivered(self):
        jobs = RenderJobs()
        jobs.launch(self.a, "framed", {"frame_ratio": 0.03}, {1: (self.b, "framed")})
        got = self.collect(jobs, {"image", "neighbor"})
        self.assertEqual({k for k, _ in got}, {"image", "neighbor"})
        delta, image = next(p for k, p in got if k == "neighbor")
        self.assertEqual(delta, 1)
        self.assertIsNotNone(image)

    def test_results_of_a_replaced_request_are_dropped(self):
        jobs = RenderJobs()
        jobs.launch(self.a, "framed", {"frame_ratio": 0.03}, {})
        time.sleep(0.5)  # le premier rendu a abouti, mais un réglage plus récent est demandé
        jobs.launch(self.b, "framed", {"frame_ratio": 0.05}, {})
        got = self.collect(jobs, {"image"})
        self.assertEqual([k for k, _ in got], ["image"])  # une seule image : celle de la dernière demande

    def test_a_failing_render_reports_an_error(self):
        jobs = RenderJobs()
        jobs.launch(self.dir / "absent.jpg", "framed", {}, {})
        self.assertIn("error", {k for k, _ in self.collect(jobs, {"error"})})


if __name__ == "__main__":
    unittest.main()

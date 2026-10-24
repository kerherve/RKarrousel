"""Logique du viewer sans écran : zoom et déplacement, décision après un glisser, calculs en arrière-plan."""
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())

from rkarrousel.gui.viewer.carousel import SWIPE_FRACTION, SWIPE_MIN_FLICK, SWIPE_VELOCITY, swipe_decision
from rkarrousel.gui.viewer.loader import PreviewCache
from rkarrousel.gui.viewer.render_jobs import PREVIEW_SIDE, RenderJobs
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


try:
    import tkinter as tk

    tk.Tk().destroy()
    HAVE_DISPLAY = True
except Exception:  # pas d'écran (CI Linux) : ce test est ignoré
    HAVE_DISPLAY = False


@unittest.skipUnless(HAVE_DISPLAY, "pas d'affichage graphique")
class DebouncerTests(unittest.TestCase):
    def test_only_the_last_trigger_fires_after_the_delay_and_cancel_stops_it(self):
        from rkarrousel.gui.widgets import Debouncer

        root = tk.Tk()
        try:
            calls = []
            debounce = Debouncer(root, 40, lambda *args: calls.append(args))
            for value in (1, 2, 3):  # trois demandes rapprochées : un seul appel, avec la dernière valeur
                debounce.trigger(value)
            self.assertTrue(debounce.pending)
            end = time.time() + 2
            while time.time() < end and not calls:
                root.update()
                time.sleep(0.01)
            self.assertEqual(calls, [(3,)])
            self.assertFalse(debounce.pending)
            debounce.trigger(4)
            debounce.cancel()
            root.update()
            time.sleep(0.1)
            root.update()
            self.assertEqual(calls, [(3,)])  # annulé : rien de plus
        finally:
            root.destroy()


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
        delta, image, source, kind = next(p for k, p in got if k == "neighbor")
        self.assertEqual((delta, source, kind), (1, self.b, "framed"))
        self.assertIsNotNone(image)

    def test_results_of_a_replaced_request_are_dropped(self):
        jobs = RenderJobs()
        jobs.launch(self.a, "framed", {"frame_ratio": 0.03}, {})
        time.sleep(0.5)  # le premier rendu a abouti, mais un réglage plus récent est demandé
        jobs.launch(self.b, "framed", {"frame_ratio": 0.05}, {})
        got = self.collect(jobs, {"image"})
        self.assertEqual([k for k, _ in got], ["image"])  # une seule image : celle de la dernière demande

    def test_the_main_image_is_an_ideal_preview_unless_the_full_resolution_is_asked(self):
        big = make_image(self.dir, "big.jpg", (3600, 4800))
        jobs = RenderJobs()
        jobs.launch(big, "framed", {"frame_ratio": 0.03}, {})
        [(_, (preview, full, _, _))] = [e for e in self.collect(jobs, {"image"}) if e[0] == "image"]
        self.assertFalse(full)
        self.assertLessEqual(max(preview.size), PREVIEW_SIDE * 1.1)  # aperçu : cadre compris, un peu plus que le côté demandé
        jobs.launch(big, "framed", {"frame_ratio": 0.03}, {}, full=True)
        [(_, (whole, full, _, _))] = [e for e in self.collect(jobs, {"image"}) if e[0] == "image"]
        self.assertTrue(full)
        self.assertGreater(whole.height, 4800)  # pleine résolution : la photo entière, encadrée

    def test_the_cache_hands_back_a_preview_until_a_setting_changes(self):
        cache = PreviewCache(size=2)
        image = make_image(self.dir, "x.jpg", (100, 100))
        from PIL import Image
        preview = Image.new("RGB", (10, 10))
        config = {"frame_ratio": 0.03}
        self.assertIsNone(cache.get(image, "framed", config))
        cache.put(image, "framed", config, preview)
        self.assertIs(cache.get(image, "framed", config), preview)
        self.assertIsNone(cache.get(image, "framed", {"frame_ratio": 0.05}))  # un réglage a changé : plus valable
        self.assertIsNone(cache.get(image, "crop34", config))                  # autre type d'image
        cache.put(image, "a", config, preview)
        cache.put(image, "b", config, preview)  # trop plein : le plus ancien part
        self.assertEqual(len(cache), 2)
        self.assertIsNone(cache.get(image, "framed", config))

    def test_a_failing_render_reports_an_error(self):
        jobs = RenderJobs()
        jobs.launch(self.dir / "absent.jpg", "framed", {}, {})
        self.assertIn("error", {k for k, _ in self.collect(jobs, {"error"})})


if __name__ == "__main__":
    unittest.main()

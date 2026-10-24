"""Logique du viewer sans écran : zoom et déplacement, décision après un glisser, calculs en arrière-plan."""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT.as_posix())

from rkarrousel.gui.viewer.carousel import SWIPE_FRACTION, SWIPE_MIN_FLICK, SWIPE_VELOCITY, swipe_decision
from rkarrousel.gui.viewer.preview_cache import PREVIEW, STRIP, PreviewCache, weight
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


class FakeWidget:
    """Un widget sans écran : `after` range le rappel, que les tests n'exécutent pas."""

    def after(self, ms, callback=None):
        return "job"

    def after_cancel(self, job):
        pass


class FakeNavigator:
    """Une grille de n images (tuiles 0…n-1) dont la sélection se déplace."""

    def __init__(self, count):
        from types import SimpleNamespace

        self.tiles = [SimpleNamespace(source=Path(f"/photos/{i}.jpg"), kind="framed") for i in range(count)]
        self.selected = 0

    def viewer_peek(self, delta):
        index = self.selected + delta
        return self.tiles[index] if 0 <= index < len(self.tiles) else None

    def viewer_preview(self, tile, config):
        return None


class LoaderArrivalTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace

        from rkarrousel.gui.viewer.loader import ImageLoader

        self.navigator = FakeNavigator(8)
        self.carousel = SimpleNamespace(neighbors={}, set_neighbor=lambda delta, image: self.carousel.neighbors.__setitem__(delta, image))
        self.loader = ImageLoader(FakeWidget(), self.navigator, self.carousel, lambda *a: None, lambda *a: None, lambda: None)
        self.loader.jobs.close()  # aucun vrai calcul : on fournit nous-mêmes les résultats
        self.loader.jobs.launch = lambda *args, **kwargs: 1
        self.loader.jobs.prefetch = lambda *args, **kwargs: None
        self.config = {"frame_ratio": 0.03}

    def launch(self, reach):
        self.loader.launch(self.navigator.tiles[self.navigator.selected].source, "framed", self.config, False, False, reach=reach)

    def test_a_result_requested_from_another_position_still_shows_where_the_image_is_now(self):
        from PIL import Image

        self.navigator.selected = 3
        self.launch(reach=1)
        tile4 = self.navigator.tiles[4]  # demandée comme voisine +1…
        self.navigator.selected = 2  # … puis on bouge : elle est maintenant à +2
        self.launch(reach=2)
        self.assertIsNone(self.carousel.neighbors.get(2))
        arrived = Image.new("RGB", (50, 70))
        self.loader._neighbor_arrived(1, arrived, tile4.source, "framed")  # le résultat porte l'ancienne position (+1)
        self.assertIs(self.carousel.neighbors[2], arrived)  # il s'affiche quand même à la bonne place (+2)

    def test_a_result_for_an_image_no_longer_in_view_goes_to_the_cache_only(self):
        from PIL import Image

        self.navigator.selected = 0
        self.launch(reach=1)
        far = self.navigator.tiles[6]
        arrived = Image.new("RGB", (50, 70))
        self.loader._neighbor_arrived(1, arrived, far.source, "framed")
        self.assertNotIn(arrived, self.carousel.neighbors.values())
        self.assertIs(self.loader.cache.get(far.source, "framed", self.loader._config), arrived)  # mais il est gardé

    def test_far_neighbours_get_a_small_preview_in_the_background_not_a_sharp_job(self):
        self.navigator.selected = 0
        queued = []
        with mock.patch.object(self.loader.jobs, "launch", side_effect=lambda *a, **k: queued.append((a, k)) or 1), \
                mock.patch.object(self.loader.jobs, "prefetch") as prefetch:
            self.launch(reach=6)
        sharp = set(queued[0][0][3]) if queued else set()
        self.assertTrue(sharp <= {1, 2, 3})  # des aperçus nets seulement tout près du centre (+ la suivante)
        background = prefetch.call_args[0][1]
        self.assertGreaterEqual(len(background), 3)  # les plus lointaines sont préparées en petit, en arrière-plan


class RenderJobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.a = make_image(self.dir, "a.jpg", (300, 400))
        self.b = make_image(self.dir, "b.jpg", (300, 400))

    def collect_all(self, jobs, kind, count, seconds=15):
        got, end = [], time.time() + seconds
        while time.time() < end and len([g for g in got if g[0] == kind]) < count:
            got += jobs.drain()
            time.sleep(0.02)
        return [g for g in got if g[0] == kind]

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
        from PIL import Image

        cache = PreviewCache()
        image = make_image(self.dir, "x.jpg", (100, 100))
        preview = Image.new("RGB", (10, 10))
        config = {"frame_ratio": 0.03}
        self.assertIsNone(cache.get(image, "framed", config))
        cache.put(image, "framed", config, preview)
        self.assertIs(cache.get(image, "framed", config), preview)
        self.assertIsNone(cache.get(image, "framed", {"frame_ratio": 0.05}))  # un réglage a changé : plus valable
        self.assertIsNone(cache.get(image, "crop34", config))                  # autre type d'image

    def test_a_small_preview_never_replaces_a_sharp_one_and_can_be_refused(self):
        from PIL import Image

        cache = PreviewCache()
        source, config = self.a, {"frame_ratio": 0.03}
        strip, sharp = Image.new("RGB", (10, 10)), Image.new("RGB", (40, 40))
        cache.put(source, "framed", config, strip, STRIP)
        self.assertIs(cache.get(source, "framed", config), strip)            # un petit aperçu fait l'affaire…
        self.assertIsNone(cache.get(source, "framed", config, PREVIEW))      # … sauf si l'on veut un aperçu net
        cache.put(source, "framed", config, sharp, PREVIEW)
        cache.put(source, "framed", config, strip, STRIP)                    # ne remplace pas le net
        self.assertIs(cache.get(source, "framed", config, PREVIEW), sharp)

    def test_the_memory_limit_drops_small_previews_before_sharp_ones(self):
        from PIL import Image

        sharp = Image.new("RGB", (100, 100))
        small = Image.new("RGB", (50, 50))
        cache = PreviewCache(max_bytes=weight(sharp) + 2 * weight(small))
        config = {"frame_ratio": 0.03}
        cache.put(self.a, "k1", config, sharp, PREVIEW)
        for name in ("s1", "s2", "s3", "s4"):
            cache.put(self.a, name, config, small, STRIP)  # trop : les plus anciens petits partent
        self.assertLessEqual(cache.total_bytes, cache.max_bytes)
        self.assertIs(cache.get(self.a, "k1", config, PREVIEW), sharp)       # le net est resté
        self.assertIsNone(cache.get(self.a, "s1", config))
        self.assertIsNotNone(cache.get(self.a, "s4", config))
        self.assertEqual(len(cache), 3)

    def test_there_is_no_limit_on_the_number_of_images_only_on_memory(self):
        from PIL import Image

        cache = PreviewCache()
        for index in range(200):
            cache.put(self.a, f"k{index}", {"x": 1}, Image.new("RGB", (30, 30)), STRIP)
        self.assertEqual(len(cache), 200)

    def test_the_background_prefetch_prepares_a_small_preview_of_every_image(self):
        jobs = RenderJobs()
        photos = [make_image(self.dir, f"p{i}.jpg", (1200, 1600)) for i in range(5)]
        jobs.prefetch({"frame_ratio": 0.03}, [(p, "framed") for p in photos])
        got = self.collect_all(jobs, "strip", 5)
        self.assertEqual({source for _, (_, source, _) in got}, set(photos))
        self.assertTrue(all(max(image.size) <= 1000 for _, (image, _, _) in got))  # petits : environ 900 px

    def test_a_newer_prefetch_request_replaces_the_previous_one(self):
        jobs = RenderJobs()
        photos = [make_image(self.dir, f"q{i}.jpg", (3000, 4000)) for i in range(6)]
        jobs.prefetch({"frame_ratio": 0.03}, [(p, "framed") for p in photos[:3]])
        jobs.prefetch({"frame_ratio": 0.03}, [(p, "framed") for p in photos[3:]])  # la 2e demande remplace la 1re
        wanted, seen, end = set(photos[3:]), set(), time.time() + 30
        while time.time() < end and not wanted <= seen:
            seen |= {source for kind, (_, source, _) in jobs.drain() if kind == "strip"}
            time.sleep(0.02)
        self.assertTrue(wanted <= seen)  # les images de la 2e demande sont toutes préparées
        self.assertFalse(set(photos[:3]) <= seen)  # la 1re demande a été abandonnée avant la fin

    def test_a_failing_render_reports_an_error(self):
        jobs = RenderJobs()
        jobs.launch(self.dir / "absent.jpg", "framed", {}, {})
        self.assertIn("error", {k for k, _ in self.collect(jobs, {"error"})})


if __name__ == "__main__":
    unittest.main()

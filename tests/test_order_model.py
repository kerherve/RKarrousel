"""Modèle et géométrie de la grille d'ordre (sans interface graphique)."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from rkarrousel.gui.order.grid_layout import COLUMNS, GridLayout
from rkarrousel.gui.order.model import OrderModel, cache_key, render_signature
from rkarrousel.outputs import item_key
from tests.helpers import make_image


class OrderModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.a = make_image(self.dir, "a.jpg", (900, 1200))     # 3:4 → 1 image
        self.b = make_image(self.dir, "b.jpg", (1500, 1000))    # 3:2 → 4 images
        self.model = OrderModel([self.a, self.b])
        self.pending = self.model.rebuild({}, [], lambda key, path: None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rebuild_lists_every_output_and_reports_photos_to_render(self):
        self.assertEqual(len(self.model.tiles), 5)
        self.assertEqual(self.pending, [self.a, self.b])
        self.assertEqual(self.model.counts(), (5, 0, 0, False))

    def test_cached_thumbnails_are_reused(self):
        thumb = Image.new("RGB", (10, 10))
        model = OrderModel([self.a, self.b])
        pending = model.rebuild({}, [], lambda key, path: thumb if path == self.a else None)
        self.assertEqual(pending, [self.b])
        self.assertEqual(model.counts()[1], 1)

    def test_user_order_is_kept_and_new_items_follow(self):
        keys = self.model.keys()
        wanted = [keys[3], keys[0]]
        self.model.rebuild({}, wanted, lambda key, path: None)
        self.assertEqual(self.model.keys()[:2], wanted)
        self.assertEqual(len(self.model.tiles), 5)

    def test_move_keeps_the_selection_on_the_moved_tile(self):
        first = self.model.tiles[0].key
        self.model.select(0)
        self.assertTrue(self.model.move(0, 3))
        self.assertEqual(self.model.selected, 3)
        self.assertEqual(self.model.tiles[3].key, first)
        self.assertFalse(self.model.move(2, 2))

    def test_exclusion_toggles_and_numbering_skips_excluded(self):
        self.assertFalse(self.model.toggle_selected_exclusion())  # rien de sélectionné
        self.model.select(1)
        self.assertTrue(self.model.toggle_selected_exclusion())
        self.assertIn(self.model.tiles[1].key, self.model.excluded)
        self.assertEqual([self.model.number_of(i) for i in (0, 2, 3)], [1, 2, 3])
        self.model.toggle_selected_exclusion()
        self.assertEqual(self.model.excluded, set())

    def test_exclusions_of_vanished_items_are_dropped_on_rebuild(self):
        model = OrderModel([self.a], excluded={item_key(self.b, "part1"), item_key(self.a, "framed")})
        model.rebuild({}, [], lambda key, path: None)
        self.assertEqual(model.excluded, {item_key(self.a, "framed")})

    def test_errors_are_attached_to_tiles_without_a_thumbnail(self):
        self.model.set_error(self.b, "boom")
        self.assertTrue(self.model.counts()[3])
        self.assertEqual(sum(1 for t in self.model.tiles if t.error == "boom"), 4)
        self.model.set_thumb(self.model.tiles[1].key, Image.new("RGB", (5, 5)))
        self.assertEqual(self.model.tiles[1].error, "")

    def test_cache_key_changes_with_the_crop_position(self):
        key = item_key(self.a, "crop34")
        base = cache_key(key, self.a, {})
        moved = cache_key(key, self.a, {"crop_offsets": {str(self.a): 0.9}})
        self.assertNotEqual(base, moved)
        self.assertEqual(cache_key(item_key(self.a, "framed"), self.a, {}), cache_key(item_key(self.a, "framed"), self.a, {"crop_offsets": {str(self.a): 0.9}}))

    def test_render_signature_ignores_unrelated_settings(self):
        self.assertEqual(render_signature({"frame_ratio": 0.02}), render_signature({"frame_ratio": 0.02, "language": "en"}))
        self.assertNotEqual(render_signature({"frame_ratio": 0.02}), render_signature({"frame_ratio": 0.03}))


class GridLayoutTests(unittest.TestCase):
    def test_tiles_grow_with_the_window_but_stay_three_columns(self):
        layout = GridLayout(1.0, (3, 4))
        base = layout.tile_w
        self.assertFalse(layout.fit_width(100))  # jamais plus petit que la taille de base
        self.assertEqual(layout.tile_w, base)
        self.assertTrue(layout.fit_width(1500))
        self.assertGreater(layout.tile_w, base)
        self.assertLessEqual(layout.canvas_width, 1500)
        self.assertGreaterEqual(layout.canvas_width, 1500 - COLUMNS)  # les trois colonnes remplissent la largeur
        self.assertAlmostEqual(layout.tile_h / layout.tile_w, 4 / 3, places=2)
        self.assertEqual(layout.tile_at(layout.slot_origin(5)[0] + 1, layout.slot_origin(5)[1] + 1, 9), 5)
        self.assertFalse(layout.fit_width(1500))  # même largeur : rien à refaire

    def test_thumbnails_are_large_enough_for_a_wide_window(self):
        layout = GridLayout(1.0, (3, 4))
        self.assertGreaterEqual(layout.max_thumb_size()[0], 800)

    def test_tile_shape_follows_the_output_format(self):
        self.assertAlmostEqual(GridLayout(1.0, (3, 4)).tile_h / GridLayout(1.0, (3, 4)).tile_w, 4 / 3, places=2)
        self.assertEqual(GridLayout(1.0, (1, 1)).tile_h, GridLayout(1.0, (1, 1)).tile_w)

    def test_hit_testing(self):
        layout = GridLayout(1.0, (3, 4))
        for index in range(7):
            x, y = layout.slot_origin(index)
            self.assertEqual(layout.tile_at(x + 5, y + 5, 7), index)
        self.assertIsNone(layout.tile_at(2, 2, 7))                       # dans l'interstice
        x, y = layout.slot_origin(7)
        self.assertIsNone(layout.tile_at(x + 5, y + 5, 7))               # après la dernière vignette
        self.assertIsNone(layout.tile_at(-50, 10, 7))

    def test_slot_at_is_clamped_to_the_grid(self):
        layout = GridLayout(1.0, (3, 4))
        self.assertEqual(layout.slot_at(-100, -100, 5), 0)
        self.assertEqual(layout.slot_at(10_000, 10_000, 5), 4)

    def test_cross_hit(self):
        layout = GridLayout(1.0, (3, 4))
        x0, y0, x1, y1 = layout.cross_rect(*layout.slot_origin(0))
        self.assertTrue(layout.hits_cross(0, (x0 + x1) / 2, (y0 + y1) / 2))
        self.assertFalse(layout.hits_cross(0, layout.slot_origin(0)[0] + 5, layout.slot_origin(0)[1] + 5))

    def test_content_height_and_width(self):
        layout = GridLayout(1.0, (3, 4))
        self.assertEqual(layout.content_height(0), layout.gap + 0 * (layout.tile_h + layout.gap))
        self.assertEqual(layout.content_height(COLUMNS + 1), layout.gap + 2 * (layout.tile_h + layout.gap))
        self.assertEqual(layout.canvas_width, COLUMNS * layout.tile_w + (COLUMNS + 1) * layout.gap)


if __name__ == "__main__":
    unittest.main()

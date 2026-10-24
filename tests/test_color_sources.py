"""Modes complémentaire et contraste, sources de la couleur de référence et couleur de cadre propre à une photo."""
import colorsys
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from rkarrousel import config as conf, outputs as produce, pipeline
from rkarrousel.gui.order.model import render_signature
from rkarrousel.imaging import colors
from tests.helpers import make_image


def hue(color):
    return colorsys.rgb_to_hls(*(c / 255 for c in color))[0]


class StyleTests(unittest.TestCase):
    def test_complement_has_the_opposite_hue(self):
        blue = (30, 90, 200)
        comp = colors.styled_color(blue, "complement")
        diff = abs(hue(comp) - hue(blue))
        self.assertAlmostEqual(min(diff, 1 - diff), 0.5, delta=0.02)

    def test_complement_is_tempered_for_extreme_colours(self):
        for color in ((0, 0, 255), (255, 0, 0), (5, 5, 5), (250, 250, 250)):
            _, light, sat = colorsys.rgb_to_hls(*(c / 255 for c in colors.styled_color(color, "complement")))
            self.assertGreaterEqual(light, 0.29)
            self.assertLessEqual(light, 0.76)
            self.assertLessEqual(sat, 0.66)

    def test_contrast_is_light_on_dark_photos_and_dark_on_light_ones(self):
        self.assertGreater(colors.luminance(colors.styled_color((20, 30, 60), "contrast")), 0.85)
        self.assertLess(colors.luminance(colors.styled_color((230, 220, 200), "contrast")), 0.15)


class SourceTests(unittest.TestCase):
    def photo(self):
        img = Image.new("RGB", (400, 300), (20, 40, 200))  # centre bleu…
        img.paste((240, 230, 40), (0, 0, 400, 24))          # …bords jaunes : haut,
        img.paste((240, 230, 40), (0, 276, 400, 300))       # bas,
        img.paste((240, 230, 40), (0, 0, 24, 300))          # gauche,
        img.paste((240, 230, 40), (376, 0, 400, 300))       # droite
        return img

    def test_dominant_edges_and_average_differ(self):
        img = self.photo()
        self.assertEqual(colors.reference_color(img, "dominant"), (20, 40, 200))
        edges = colors.reference_color(img, "edges")
        self.assertGreater(edges[0], 200)
        self.assertLess(edges[2], 80)
        average = colors.reference_color(img, "average")
        self.assertNotEqual(average, colors.reference_color(img, "dominant"))
        self.assertNotEqual(average, edges)

    def test_unknown_source_falls_back_to_dominant(self):
        self.assertEqual(conf.color_source_of({"color_source": "nope"}), "dominant")
        self.assertEqual(colors.reference_color(self.photo(), "nope"), (20, 40, 200))

    def test_the_source_changes_the_resolved_frame_colour(self):
        img = self.photo()
        cfg = {"border_color_mode": "dominant"}
        centre = colors.resolve_photo_colors(img, cfg)["border_color"]
        edges = colors.resolve_photo_colors(img, {**cfg, "color_source": "edges"})["border_color"]
        self.assertNotEqual(centre, edges)

    def test_default_source_keeps_the_previous_result(self):
        img = self.photo()
        for mode in ("dominant", "light", "dark"):
            expected = colors.to_hex(colors.styled_color(colors.dominant_color(img), mode))
            self.assertEqual(colors.resolve_photo_colors(img, {"border_color_mode": mode})["border_color"], expected)


class PerPhotoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.a = make_image(self.dir, "a.jpg", (600, 800), (40, 80, 160))
        self.b = make_image(self.dir, "b.jpg", (600, 800), (40, 80, 160))
        self.config = {"frame_ratio": 0.05, "border_color": "#FFFFFF",
                       "photo_overrides": {str(self.a): {"border_color_mode": "fixed", "border_color": "#FF0000"}}}

    def frame_pixel(self, path):
        image = produce.render_output(path, self.config, "framed")
        return image.convert("RGB").getpixel((3, 3))

    def test_only_the_photo_with_an_override_changes(self):
        self.assertEqual(self.frame_pixel(self.a), (255, 0, 0))
        self.assertEqual(self.frame_pixel(self.b), (255, 255, 255))

    def test_exported_files_use_the_override_too(self):
        out = self.dir / "out"
        pipeline.process_batch([self.a, self.b], out, self.config)
        a = Image.open(out / "a_framed.jpg").convert("RGB").getpixel((3, 3))
        b = Image.open(out / "b_framed.jpg").convert("RGB").getpixel((3, 3))
        self.assertGreater(a[0], 200)
        self.assertLess(a[1], 60)
        self.assertGreater(min(b), 200)

    def test_override_accepts_only_allowed_keys(self):
        cfg = {"photo_overrides": {"x.jpg": {"border_color": "#00FF00", "frame_ratio": 0.5, "junk": 1}}}
        self.assertEqual(conf.photo_override_for(cfg, "x.jpg"), {"border_color": "#00FF00"})
        self.assertEqual(conf.config_for_photo(cfg, "other.jpg"), cfg)
        self.assertEqual(conf.photo_override_for({"photo_overrides": "garbage"}, "x.jpg"), {})

    def test_override_with_a_photo_mode(self):
        self.config["photo_overrides"][str(self.a)] = {"border_color_mode": "contrast", "border_color": "#000000"}
        light = self.frame_pixel(self.a)  # photo sombre : cadre presque blanc, teinté
        self.assertGreater(colors.luminance(light), 0.85)
        self.assertNotEqual(light, (255, 255, 255))

    def test_preview_cache_is_invalidated_by_colour_settings(self):
        base = render_signature(self.config)
        for change in ({"border_color_mode": "contrast"}, {"background_color_mode": "dark"}, {"color_source": "edges"},
                       {"photo_overrides": {str(self.b): {"border_color_mode": "dark", "border_color": "#000000"}}}):
            self.assertNotEqual(render_signature({**self.config, **change}), base, change)

    def test_overrides_survive_a_json_round_trip(self):
        self.assertEqual(json.loads(json.dumps(self.config))["photo_overrides"], self.config["photo_overrides"])


if __name__ == "__main__":
    unittest.main()

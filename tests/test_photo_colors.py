"""Couleur du cadre et du fond uni tirée de la photo."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from rkarrousel import config as conf, outputs as produce
from rkarrousel.imaging import colors
from tests.helpers import make_image


class ColorMathTests(unittest.TestCase):
    def test_dominant_color_of_a_solid_image(self):
        self.assertEqual(colors.dominant_color(Image.new("RGB", (300, 200), (30, 90, 160))), (30, 90, 160))

    def test_dominant_color_ignores_a_small_accent(self):
        img = Image.new("RGB", (400, 400), (200, 40, 40))
        img.paste((255, 255, 255), (0, 0, 40, 40))  # 1 % de la surface
        r, g, b = colors.dominant_color(img)
        self.assertGreater(r, 150)
        self.assertLess(g, 100)

    def test_alpha_images_are_handled(self):
        self.assertEqual(colors.dominant_color(Image.new("RGBA", (50, 50), (10, 20, 30, 255))), (10, 20, 30))

    def test_styles(self):
        base = (100, 150, 200)
        self.assertEqual(colors.styled_color(base, "dominant"), base)
        light, dark = colors.styled_color(base, "light"), colors.styled_color(base, "dark")
        self.assertTrue(all(l > b for l, b in zip(light, base)))
        self.assertTrue(all(d < b for d, b in zip(dark, base)))
        self.assertEqual(colors.to_hex((255, 0, 128)), "#FF0080")

    def test_mode_validation(self):
        self.assertEqual(conf.color_mode_of({}, "border_color_mode"), "fixed")
        self.assertEqual(conf.color_mode_of({"border_color_mode": "light"}, "border_color_mode"), "light")
        self.assertEqual(conf.color_mode_of({"border_color_mode": "nonsense"}, "border_color_mode"), "fixed")


class ResolveTests(unittest.TestCase):
    def test_fixed_modes_leave_the_config_untouched(self):
        config = {"border_color": "#FFFFFF"}
        self.assertIs(colors.resolve_photo_colors(Image.new("RGB", (10, 10), (1, 2, 3)), config), config)

    def test_photo_modes_replace_only_the_chosen_colors(self):
        img = Image.new("RGB", (100, 100), (20, 80, 140))
        resolved = colors.resolve_photo_colors(img, {"border_color_mode": "dominant", "border_color": "#FFFFFF", "background_color": "#123456"})
        self.assertEqual(resolved["border_color"], "#14508C")
        self.assertEqual(resolved["background_color"], "#123456")  # fond resté fixe
        both = colors.resolve_photo_colors(img, {"border_color_mode": "light", "background_color_mode": "dark"})
        self.assertNotEqual(both["border_color"], both["background_color"])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_frame_takes_the_photo_color_per_photo(self):
        red = make_image(self.dir, "red.jpg", (600, 800), (200, 30, 30))
        blue = make_image(self.dir, "blue.jpg", (600, 800), (30, 40, 200))
        config = {"frame_ratio": 0.05, "border_color_mode": "dominant"}
        a = produce.render_output(red, config, "framed")
        b = produce.render_output(blue, config, "framed")
        pa, pb = a.getpixel((2, a.height // 2)), b.getpixel((2, b.height // 2))
        self.assertGreater(pa[0], 150)   # cadre rougeâtre
        self.assertGreater(pb[2], 150)   # cadre bleuâtre
        self.assertNotEqual(pa, pb)

    def test_default_rendering_is_unchanged(self):
        src = make_image(self.dir, "p.jpg", (600, 800), (200, 30, 30))
        img = produce.render_output(src, {"frame_ratio": 0.05}, "framed")
        self.assertEqual(img.getpixel((2, img.height // 2)), (255, 255, 255))

    def test_solid_background_can_follow_the_photo(self):
        src = make_image(self.dir, "land.jpg", (900, 600), (20, 120, 60))
        config = {"landscape_fill_mode": "black", "background_color_mode": "dominant", "frame_ratio": 0.03}
        img = produce.render_output(src, config, "part1_with_sig")
        self.assertEqual(img.getpixel((img.width // 2, img.height // 10)), (20, 120, 60))  # bande de fond, sous le cadre
        self.assertEqual(img.getpixel((0, 0)), (255, 255, 255))  # le cadre entoure toute l'image

    def test_every_output_of_a_photo_shares_its_color(self):
        src = make_image(self.dir, "land.jpg", (900, 600), (200, 100, 30))
        config = {"border_color_mode": "dominant", "frame_ratio": 0.03, "landscape_fill_mode": "blur"}  # le cadre entoure toutes les sorties
        corner = {kind: img.getpixel((1, 1)) for kind, img in produce.render_outputs(src, config)}
        self.assertEqual(len(set(corner.values())), 1)

    def test_preview_and_full_resolution_agree(self):
        src = self.dir / "gradient.jpg"
        img = Image.new("RGB", (2400, 1600))
        for x in range(0, 2400, 8):
            img.paste((x // 10 % 256, 90, 200 - x // 20 % 100), (x, 0, x + 8, 1600))
        img.save(src, quality=95)
        config = {"border_color_mode": "dominant", "frame_ratio": 0.03}
        full = produce.render_output(src, config, "part1")
        preview = dict(produce.render_outputs(src, config, max_side=400))["part1"]
        a, b = full.getpixel((1, 1)), preview.getpixel((1, 1))
        self.assertTrue(all(abs(x - y) <= 6 for x, y in zip(a, b)), (a, b))


if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

import utils


def make_image(directory: Path, name: str, size, color=(120, 60, 200)) -> Path:
    path = directory / name
    Image.new("RGB", size, color).save(path, quality=90)
    return path


class RatioDetectionTests(unittest.TestCase):
    def test_detects_supported_ratios(self):
        self.assertEqual(utils.detect_ratio_type(1200, 1600), "portrait_3_4")
        self.assertEqual(utils.detect_ratio_type(1200, 1800), "portrait_2_3")
        self.assertEqual(utils.detect_ratio_type(1800, 1200), "landscape_2_3")

    def test_unsupported_ratio(self):
        self.assertIsNone(utils.detect_ratio_type(1000, 1000))

    def test_kinds_per_ratio(self):
        self.assertEqual(utils.kinds_for_ratio("portrait_3_4", {}), ["framed"])
        self.assertEqual(utils.kinds_for_ratio("portrait_2_3", {}), ["framed"])
        self.assertEqual(utils.kinds_for_ratio("portrait_2_3", {"signature_path": "s.png"}), ["with_sig"])
        self.assertEqual(len(utils.kinds_for_ratio("landscape_2_3", {})), 4)
        self.assertEqual(utils.kinds_for_ratio(None, {}), [])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_framed_portrait_is_larger_by_twice_the_border(self):
        src = make_image(self.dir, "p.jpg", (600, 800))
        (kind, img), = utils.render_outputs(src, {"frame_ratio": 0.05})
        border = round(600 * 0.05)
        self.assertEqual(kind, "framed")
        self.assertEqual(img.size, (600 + 2 * border, 800 + 2 * border))

    def test_border_color_is_applied(self):
        src = make_image(self.dir, "p.jpg", (300, 400))
        (_, img), = utils.render_outputs(src, {"frame_ratio": 0.1, "border_color": "#FF0000"})
        self.assertEqual(img.getpixel((0, 0)), (255, 0, 0))

    def test_landscape_gives_four_three_four_images(self):
        src = make_image(self.dir, "l.jpg", (900, 600))
        outputs = utils.render_outputs(src, {"frame_ratio": 0.03})
        self.assertEqual([k for k, _ in outputs], ["part1", "part2", "part1_with_sig", "part2_with_sig"])
        for _, img in outputs:
            self.assertAlmostEqual(img.width / img.height, 3 / 4, delta=0.01)

    def test_blur_strength_changes_the_result(self):
        src = self.dir / "l.jpg"
        img = Image.effect_noise((900, 600), 80).convert("RGB")
        img.save(src, quality=95)
        base = {"frame_ratio": 0.03, "landscape_fill_mode": "blur"}
        weak = dict(utils.render_outputs(src, {**base, "blur_strength": 0.3}))["part1_with_sig"]
        strong = dict(utils.render_outputs(src, {**base, "blur_strength": 4.0}))["part1_with_sig"]
        self.assertNotEqual(weak.tobytes(), strong.tobytes())

    def test_preview_downscale_keeps_ratio_and_type(self):
        src = make_image(self.dir, "p.jpg", (1200, 1600))
        (_, img), = utils.render_outputs(src, {"frame_ratio": 0.04}, max_side=400)
        self.assertLess(max(img.size), 500)

    def test_exif_orientation_is_considered_when_peeking(self):
        src = self.dir / "rot.jpg"
        img = Image.new("RGB", (1600, 1200))  # stocké en paysage...
        exif = Image.Exif()
        exif[0x0112] = 6  # ...mais à afficher en portrait
        img.save(src, exif=exif)
        self.assertEqual(utils.peek_ratio_type(src), "portrait_3_4")


class OrderingTests(unittest.TestCase):
    def test_merge_order_keeps_user_order_and_appends_new(self):
        a, b = Path("a.jpg"), Path("b.jpg")
        items = [(a, "part1"), (a, "part2"), (b, "framed")]
        keys = [utils.item_key(*i) for i in items]
        merged = utils.merge_order([keys[2], "gone|framed", keys[0]], items)
        self.assertEqual(merged, [keys[2], keys[0], keys[1]])

    def test_pieces_of_one_photo_can_be_interleaved(self):
        a, b = Path("a.jpg"), Path("b.jpg")
        items = [(a, "part1"), (a, "part2"), (b, "framed")]
        wanted = [utils.item_key(a, "part1"), utils.item_key(b, "framed"), utils.item_key(a, "part2")]
        prefixes = utils.build_prefixes(utils.merge_order(wanted, items))
        self.assertEqual(prefixes[wanted[0]], "01_")
        self.assertEqual(prefixes[wanted[1]], "02_")
        self.assertEqual(prefixes[wanted[2]], "03_")

    def test_prefix_width_grows_with_count(self):
        keys = [f"k{i}" for i in range(120)]
        self.assertEqual(utils.build_prefixes(keys)["k0"], "001_")


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_names_are_unchanged(self):
        src = make_image(self.dir, "shot.jpg", (600, 800))
        (result,) = utils.process_batch([src], self.out, {"frame_ratio": 0.03})
        self.assertEqual(result.status, "ok")
        self.assertEqual([p.name for p in result.outputs], ["shot_framed.jpg"])

    def test_numbering_follows_custom_order(self):
        a = make_image(self.dir, "a.jpg", (600, 800))
        b = make_image(self.dir, "b.jpg", (900, 600))
        order = [
            utils.item_key(a, "framed"),
            utils.item_key(b, "part1"),
            utils.item_key(b, "part1_with_sig"),
            utils.item_key(b, "part2"),
        ]
        utils.process_batch([a, b], self.out, {"frame_ratio": 0.03}, order=order, number_files=True)
        names = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(
            names,
            ["01_a_framed.jpg", "02_b_part1.jpg", "03_b_part1_with_sig.jpg", "04_b_part2.jpg", "05_b_part2_with_sig.jpg"],
        )

    def test_unsupported_and_broken_files_are_reported(self):
        odd = make_image(self.dir, "odd.jpg", (1000, 1000))
        broken = self.dir / "broken.jpg"
        broken.write_bytes(b"not an image")
        results = utils.process_batch([odd, broken], self.out, {})
        self.assertEqual([r.status for r in results], ["skipped", "error"])
        self.assertTrue(results[1].message)

    def test_cancel_stops_before_processing(self):
        src = make_image(self.dir, "a.jpg", (600, 800))
        cancel = threading.Event()
        cancel.set()
        (result,) = utils.process_batch([src], self.out, {}, cancel=cancel)
        self.assertEqual(result.status, "cancelled")
        self.assertFalse(list(self.out.glob("*.jpg")))

    def test_parallel_matches_sequential(self):
        files = [make_image(self.dir, f"p{i}.jpg", (600, 800), (i * 20, 50, 90)) for i in range(5)]
        seq_out, par_out = self.dir / "seq", self.dir / "par"
        utils.process_batch(files, seq_out, {"frame_ratio": 0.03}, workers=1)
        utils.process_batch(files, par_out, {"frame_ratio": 0.03}, workers=4)
        for p in sorted(seq_out.iterdir()):
            self.assertEqual(p.read_bytes(), (par_out / p.name).read_bytes())

    def test_progress_callback_reports_every_file(self):
        files = [make_image(self.dir, f"p{i}.jpg", (600, 800)) for i in range(3)]
        seen = []
        utils.process_batch(files, self.out, {}, progress=lambda d, t, p: seen.append((d, t)), workers=2)
        self.assertEqual(sorted(seen), [(1, 3), (2, 3), (3, 3)])


class ExclusionAndColorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "out"
        self.land = make_image(self.dir, "l.jpg", (900, 600))

    def tearDown(self):
        self.tmp.cleanup()

    def test_excluded_items_are_not_generated_nor_numbered(self):
        excluded = {utils.item_key(self.land, "part2_with_sig")}
        utils.process_batch([self.land], self.out, {"frame_ratio": 0.03}, number_files=True, excluded=excluded)
        self.assertEqual(
            sorted(p.name for p in self.out.iterdir()),
            ["01_l_part1.jpg", "02_l_part2.jpg", "03_l_part1_with_sig.jpg"],
        )

    def test_numbering_skips_excluded_in_the_middle(self):
        excluded = {utils.item_key(self.land, "part2")}
        utils.process_batch([self.land], self.out, {"frame_ratio": 0.03}, number_files=True, excluded=excluded)
        self.assertIn("02_l_part1_with_sig.jpg", {p.name for p in self.out.iterdir()})

    def test_all_excluded_file_is_reported_as_excluded(self):
        every = {utils.item_key(self.land, k) for k in utils.OPTIONAL_KINDS}
        (result,) = utils.process_batch([self.land], self.out, {}, excluded=every)
        self.assertEqual(result.status, "excluded")
        self.assertFalse(list(self.out.glob("*.jpg")))

    def test_disabled_kinds_are_neither_planned_nor_rendered(self):
        config = {"disabled_kinds": ["part2_with_sig", "part1"]}
        self.assertEqual(utils.kinds_for_ratio("landscape_2_3", config), ["part2", "part1_with_sig"])
        self.assertEqual([k for k, _ in utils.render_outputs(self.land, config)], ["part2", "part1_with_sig"])

    def test_render_output_returns_one_kind_or_none(self):
        self.assertIsNotNone(utils.render_output(self.land, {}, "part2"))
        self.assertIsNone(utils.render_output(self.land, {"disabled_kinds": ["part2"]}, "part2"))

    def test_solid_background_color_is_applied(self):
        config = {"frame_ratio": 0.03, "landscape_fill_mode": "black", "background_color": "#00FF00"}
        img = utils.render_output(self.land, config, "part1_with_sig")
        self.assertEqual(img.getpixel((0, 0)), (0, 255, 0))

    def test_default_background_is_still_black(self):
        img = utils.render_output(self.land, {"frame_ratio": 0.03}, "part1_with_sig")
        self.assertEqual(img.getpixel((0, 0)), (0, 0, 0))

    def test_measure_border(self):
        src = make_image(self.dir, "p.jpg", (600, 800))
        img = utils.render_output(src, {"frame_ratio": 0.05, "border_color": "#FFFFFF"}, "framed")
        self.assertEqual(utils.measure_border(img, (255, 255, 255)), round(600 * 0.05))


    def test_measure_border_skips_a_solid_background(self):
        config = {"frame_ratio": 0.03, "landscape_fill_mode": "black", "background_color": "#1E3A5F"}
        img = utils.render_output(self.land, config, "part1_with_sig")
        measured = utils.measure_border(img, (255, 255, 255), skip_color=utils.background_color_of(config))
        self.assertGreater(measured, 0)
        self.assertEqual(utils.measure_border(img, (255, 255, 255)), 0)


class ConfigTests(unittest.TestCase):
    def test_parse_color(self):
        self.assertEqual(utils.parse_color("#ff0000"), (255, 0, 0))
        self.assertEqual(utils.parse_color("0f0"), (0, 255, 0))
        self.assertEqual(utils.parse_color("zzz"), utils.DEFAULT_BORDER_COLOR)
        self.assertEqual(utils.parse_color(None), utils.DEFAULT_BORDER_COLOR)

    def test_settings_are_clamped(self):
        self.assertEqual(utils.jpeg_quality_of({"jpeg_quality": 500}), 100)
        self.assertEqual(utils.jpeg_quality_of({"jpeg_quality": "abc"}), utils.DEFAULT_JPEG_QUALITY)
        self.assertEqual(utils.signature_position_of({"signature_position": "nowhere"}), "bottom-right")

    def test_wsl_and_windows_paths_are_converted(self):
        if utils.os.name == "nt":
            self.assertEqual(utils.normalize_path("/mnt/c/Users/x"), "C:/Users/x")
        else:
            self.assertEqual(utils.normalize_path("C:\\Users\\x"), "/mnt/c/Users/x")
            self.assertEqual(utils.normalize_path("/home/x"), "/home/x")

    def test_config_roundtrip_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            utils.save_config(path, {"language": "fr", "last_dest_dir": "/tmp/é"})
            self.assertEqual(utils.load_config(path)["last_dest_dir"], "/tmp/é")


if __name__ == "__main__":
    unittest.main()

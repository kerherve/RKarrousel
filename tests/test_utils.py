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

    def test_every_other_format_is_classified(self):
        table = {
            (1000, 1000): "square", (1250, 1000): "square", (800, 1000): "portrait_other",  # 4:5
            (900, 1600): "portrait_other", (1200, 900): "landscape_other",                   # 9:16, 4:3
            (1600, 900): "landscape_other", (3000, 1000): "landscape_other",                 # 16:9, 3:1
        }
        for size, expected in table.items():
            self.assertEqual(utils.detect_ratio_type(*size), expected, size)
        self.assertIsNone(utils.detect_ratio_type(0, 100))

    def test_legacy_formats_keep_their_tolerance(self):
        self.assertEqual(utils.detect_ratio_type(1200, 1590), "portrait_3_4")
        self.assertEqual(utils.detect_ratio_type(1000, 1500), "portrait_2_3")
        self.assertEqual(utils.detect_ratio_type(1500, 1000), "landscape_2_3")

    def test_kinds_per_ratio(self):
        self.assertEqual(utils.kinds_for_ratio("portrait_3_4", {}), ["framed"])
        self.assertEqual(utils.kinds_for_ratio("portrait_2_3", {}), ["framed", "crop34"])
        self.assertEqual(utils.kinds_for_ratio("portrait_2_3", {"signature_path": "s.png"}), ["with_sig", "crop34"])
        self.assertEqual(utils.kinds_for_ratio("portrait_2_3", {"disabled_kinds": ["crop34"]}), ["framed"])
        self.assertEqual(len(utils.kinds_for_ratio("landscape_2_3", {})), 4)
        self.assertEqual(utils.kinds_for_ratio(None, {}), [])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_framed_portrait_is_exactly_3_4_once_framed(self):
        # un 3:4 d'origine est rogné de moins de 1 % pour que, cadre compris, l'image soit exactement en 3:4
        src = make_image(self.dir, "p.jpg", (600, 800))
        (kind, img), = utils.render_outputs(src, {"frame_ratio": 0.05})
        self.assertEqual(kind, "framed")
        self.assertAlmostEqual(img.width / img.height, 3 / 4, delta=0.002)
        self.assertLess(abs(img.width - (600 + 2 * 30)), 20)  # ~ la taille d'origine plus le cadre

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
        self.assertEqual(utils.peek_size(src), (1200, 1600))  # l'orientation EXIF échange largeur et hauteur
        self.assertEqual(utils.detect_ratio_type(*utils.peek_size(src)), "portrait_3_4")


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

    def test_too_panoramic_and_broken_files_are_reported(self):
        panorama = make_image(self.dir, "pano.jpg", (12000, 400))
        broken = self.dir / "broken.jpg"
        broken.write_bytes(b"not an image")
        results = utils.process_batch([panorama, broken], self.out, {})
        self.assertEqual([r.status for r in results], ["error", "error"])
        self.assertIn("panoramique", results[0].message)
        self.assertTrue(results[1].message)

    def test_a_square_photo_is_now_processed(self):
        square = make_image(self.dir, "sq.jpg", (1000, 1000))
        (result,) = utils.process_batch([square], self.out, {})
        self.assertEqual(result.status, "ok")
        self.assertEqual(sorted(p.name for p in result.outputs), ["sq_crop34.jpg", "sq_framed.jpg"])

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
        _, crop_w, _ = utils.crop_box_for(600, 800, 0.05)
        self.assertEqual(utils.measure_border(img, (255, 255, 255)), utils.border_px_for(crop_w, 0.05))


    def test_measure_border_skips_a_solid_background(self):
        config = {"frame_ratio": 0.03, "landscape_fill_mode": "black", "background_color": "#1E3A5F"}
        img = utils.render_output(self.land, config, "part1_with_sig")
        measured = utils.measure_border(img, (255, 255, 255), skip_color=utils.background_color_of(config))
        self.assertGreater(measured, 0)
        self.assertEqual(utils.measure_border(img, (255, 255, 255)), 0)


class AnyFormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_panorama_part_count(self):
        self.assertEqual(utils.panorama_parts(1200, 900), 2)    # 4:3
        self.assertEqual(utils.panorama_parts(1600, 900), 3)    # 16:9
        self.assertEqual(utils.panorama_parts(3000, 1000), 4)   # 3:1
        with self.assertRaises(ValueError):
            utils.panorama_parts(12000, 400)

    def test_kinds_per_new_format(self):
        self.assertEqual(utils.kinds_for_size(1000, 1000, {}), ["framed", "crop34"])
        self.assertEqual(utils.kinds_for_size(800, 1000, {"signature_path": "s.png"}), ["with_sig", "crop34"])
        self.assertEqual(
            utils.kinds_for_size(1600, 900, {}),
            ["part1", "part2", "part3", "part1_with_sig", "part2_with_sig", "crop34"],
        )

    def test_disabled_kinds_apply_to_panorama_parts(self):
        config = {"disabled_kinds": ["part2", "crop34"]}  # part2 règle toutes les tranches après la première
        self.assertEqual(utils.kinds_for_size(1600, 900, config), ["part1", "part1_with_sig", "part2_with_sig"])
        self.assertEqual(utils.kinds_for_size(1600, 900, {"disabled_kinds": ["part1"]})[0], "part2")

    def test_every_output_of_every_format_is_3_4(self):
        for size in ((1000, 1000), (800, 1000), (900, 1600), (1200, 900), (1600, 900), (3000, 1000), (1250, 1000)):
            src = make_image(self.dir, f"{size[0]}x{size[1]}.jpg", size)
            for mode in ("black", "blur"):
                for frame in (True, False):
                    config = {"frame_ratio": 0.03, "frame_enabled": frame, "landscape_fill_mode": mode}
                    outputs = utils.render_outputs(src, config)
                    self.assertTrue(outputs, size)
                    for kind, img in outputs:
                        self.assertAlmostEqual(img.width / img.height, 3 / 4, delta=0.004, msg=f"{size} {kind} {mode} {frame}")

    def test_panorama_parts_reassemble_the_photo_without_frame(self):
        img = Image.new("RGB", (3000, 1000))
        for x in range(0, 3000, 10):
            img.paste((x // 12 % 256, (x // 7) % 256, (x // 5) % 256), (x, 0, x + 10, 1000))
        src = self.dir / "pano.jpg"
        img.save(src, quality=100, subsampling=0)
        config = {"frame_enabled": False}
        parts = [im for kind, im in utils.render_outputs(src, config) if kind.startswith("part") and "sig" not in kind]
        self.assertEqual(len(parts), 4)
        self.assertEqual(sum(p.width for p in parts), 3000)  # tranches contiguës : rien perdu, rien dupliqué
        self.assertEqual({p.height for p in parts}, {parts[0].height})

    def test_panorama_frame_surrounds_only_top_bottom_and_ends(self):
        src = make_image(self.dir, "pano.jpg", (3000, 1000), (10, 20, 30))
        parts = [im for kind, im in utils.render_outputs(src, {"frame_ratio": 0.03}) if kind.startswith("part") and "sig" not in kind]
        b = utils.border_px_for(3000 // 4, 0.03)
        self.assertEqual(parts[0].getpixel((0, parts[0].height // 2)), (255, 255, 255))     # bord extérieur gauche
        self.assertEqual(parts[-1].getpixel((parts[-1].width - 1, parts[-1].height // 2)), (255, 255, 255))
        self.assertEqual(parts[1].getpixel((0, parts[1].height // 2)), (10, 20, 30))         # jonction : pas de cadre
        self.assertEqual(parts[1].getpixel((parts[1].width // 2, 0)), (255, 255, 255))       # haut encadré
        self.assertGreater(b, 0)

    def test_horizontal_crop_for_landscapes_and_squares(self):
        src = make_image(self.dir, "l43.jpg", (1200, 900))
        self.assertEqual(utils.crop_box_for(1200, 900, 0.0), ("x", 675, 900))
        self.assertEqual(utils.crop_box_for(800, 1600, 0.0)[0], "y")
        bare = utils.render_output(src, {"frame_enabled": False}, "crop34")
        self.assertEqual(bare.size, (675, 900))
        left = utils.render_output(src, {"frame_enabled": False, "crop_offsets": {str(src): 0.0}}, "crop34")
        right = utils.render_output(src, {"frame_enabled": False, "crop_offsets": {str(src): 1.0}}, "crop34")
        self.assertEqual(left.size, right.size)

    def test_horizontal_crop_position_moves_the_window(self):
        img = Image.new("RGB", (1200, 900))
        for x in range(1200):
            img.paste((x // 5 % 256, 40, 40), (x, 0, x + 1, 900))
        src = self.dir / "grad.jpg"
        img.save(src, quality=100, subsampling=0)
        left = utils.render_output(src, {"frame_enabled": False, "crop_offsets": {str(src): 0.0}}, "crop34")
        right = utils.render_output(src, {"frame_enabled": False, "crop_offsets": {str(src): 1.0}}, "crop34")
        self.assertLess(left.getpixel((10, 450))[0], right.getpixel((10, 450))[0])

    def test_batch_handles_a_mixed_folder(self):
        files = [
            make_image(self.dir, "a.jpg", (1200, 1600)), make_image(self.dir, "b.jpg", (1200, 900)),
            make_image(self.dir, "c.jpg", (1600, 900)), make_image(self.dir, "d.jpg", (1000, 1000)),
        ]
        results = utils.process_batch(files, self.dir / "out", {"frame_ratio": 0.03}, number_files=True)
        self.assertEqual([r.status for r in results], ["ok"] * 4)
        names = sorted(p.name for p in (self.dir / "out").iterdir())
        self.assertEqual(names[0], "01_a_framed.jpg")
        self.assertEqual(len(names), 1 + 5 + 6 + 2)  # 3:4 → 1 ; 4:3 → 2 tranches + 2 entières + recadrage ; 16:9 → 3 + 2 + 1 ; carré → 2
        self.assertTrue(all(n[:2].isdigit() for n in names))


class OutputFormatTests(unittest.TestCase):
    SOURCES = ((1000, 1000), (800, 1000), (900, 1600), (1000, 1500), (1500, 1000), (1200, 900), (1600, 900), (3000, 1000))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_format_and_width_helpers(self):
        self.assertEqual(utils.output_format_of({}), (3, 4))
        self.assertEqual(utils.output_format_of({"output_format": "4:5"}), (4, 5))
        self.assertEqual(utils.output_format_of({"output_format": "9:16"}), (9, 16))
        self.assertEqual(utils.output_format_of({"output_format": "nonsense"}), (3, 4))
        self.assertEqual(utils.output_width_of({"output_width": 1080}), 1080)
        self.assertEqual(utils.output_width_of({"output_width": "x"}), 0)
        self.assertEqual(utils.output_width_of({"output_width": 50}), 0)
        self.assertEqual(utils.format_tag((9, 16)), "916")

    def test_every_output_matches_the_chosen_format(self):
        for fmt, (tw, th) in utils.OUTPUT_FORMATS.items():
            for size in self.SOURCES:
                src = make_image(self.dir, f"{size[0]}x{size[1]}_{fmt[0]}.jpg", size)
                for mode in ("black", "blur"):
                    config = {"output_format": fmt, "frame_ratio": 0.03, "landscape_fill_mode": mode}
                    outputs = utils.render_outputs(src, config)
                    self.assertTrue(outputs, (fmt, size))
                    for kind, img in outputs:
                        self.assertAlmostEqual(img.width / img.height, tw / th, delta=0.005, msg=f"{fmt} {size} {kind} {mode}")

    def test_photo_already_at_the_format_is_exact_once_framed(self):
        for fmt, (tw, th) in utils.OUTPUT_FORMATS.items():
            goal = tw / th
            for deviation in (-0.02, 0.0, 0.02):
                width = 1200
                src = make_image(self.dir, f"m_{fmt[0]}_{deviation}.jpg", (width, round(width / (goal * (1 + deviation)))))
                for frame in (0.01, 0.02, 0.05):
                    img = utils.render_output(src, {"output_format": fmt, "frame_ratio": frame}, "framed")
                    self.assertAlmostEqual(img.width / img.height, goal, delta=0.002, msg=f"{fmt} {deviation} {frame}")
                    self.assertGreater(utils.measure_border(img, (255, 255, 255)), 0)

    def test_matching_photo_is_untouched_without_frame(self):
        src = make_image(self.dir, "m.jpg", (600, 800))
        img = utils.render_output(src, {"frame_enabled": False}, "framed")
        self.assertEqual(img.size, (600, 800))

    def test_crop_box_falls_back_to_the_width_when_the_height_cannot_hold_the_frame(self):
        axis, crop_w, crop_h = utils.crop_box_for(1000, 1340, 0.05)  # à peine plus étroit que 3:4
        self.assertEqual((axis, crop_h), ("x", 1340))
        self.assertLess(crop_w, 1000)

    def test_width_gives_exact_instagram_dimensions(self):
        expected = {"3:4": (1080, 1440), "4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920)}
        for fmt, dims in expected.items():
            for size in ((2400, 3600), (4000, 3000), (7200, 2400)):
                src = make_image(self.dir, f"{size[0]}x{size[1]}_{fmt[0]}.jpg", size)
                config = {"output_format": fmt, "output_width": 1080, "frame_ratio": 0.02}
                widths = []
                for kind in utils.kinds_for_size(*size, config):
                    img = utils.render_output(src, config, kind)
                    widths.append(img.width)
                    self.assertLessEqual(img.width, 1080)  # jamais d'agrandissement
                    if img.width == 1080:
                        self.assertEqual(img.size, dims, f"{fmt} {size} {kind}")
                self.assertIn(1080, widths, f"{fmt} {size}")  # au moins une image atteint la largeur demandée

    def test_never_upscales_and_leaves_matching_photos_undistorted(self):
        small = make_image(self.dir, "small.jpg", (600, 800))
        img = utils.render_output(small, {"output_width": 1080, "frame_enabled": False}, "framed")
        self.assertEqual(img.size, (600, 800))
        odd = Image.new("RGB", (2000, 2800))  # 0,714 : proche du 3:4 mais pas exact
        self.assertEqual(utils.finalize_size(odd, {"output_width": 1000}).size, (1000, 1400))

    def test_crop_file_suffix_follows_the_format(self):
        src = self.dir / "p.jpg"
        self.assertEqual(utils.output_name(src, "crop34", "", {}), "p_crop34.jpg")
        self.assertEqual(utils.output_name(src, "crop34", "", {"output_format": "4:5"}), "p_crop45.jpg")
        self.assertEqual(utils.output_name(src, "framed", "01_", {"output_format": "1:1"}), "01_p_framed.jpg")

    def test_panorama_parts_depend_on_the_format(self):
        self.assertEqual(utils.panorama_parts(3000, 1000, (3, 4)), 4)
        self.assertEqual(utils.panorama_parts(3000, 1000, (4, 5)), 4)
        self.assertEqual(utils.panorama_parts(3000, 1000, (1, 1)), 3)
        self.assertEqual(utils.panorama_parts(3000, 1000, (9, 16)), 6)

    def test_a_3_2_photo_uses_the_generic_panorama_in_other_formats(self):
        kinds = utils.kinds_for_size(1500, 1000, {"output_format": "4:5"})
        self.assertEqual(kinds, ["part1", "part2", "part1_with_sig", "part2_with_sig", "crop34"])

    def test_batch_writes_sized_files_with_the_format_suffix(self):
        src = make_image(self.dir, "p23.jpg", (2000, 3000))
        config = {"output_format": "4:5", "output_width": 1080, "frame_ratio": 0.02}
        (result,) = utils.process_batch([src], self.dir / "out", config, number_files=True)
        self.assertEqual(sorted(p.name for p in result.outputs), ["01_p23_framed.jpg", "02_p23_crop45.jpg"])
        for path in result.outputs:
            self.assertEqual(Image.open(path).size, (1080, 1350))


class NoFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_frame_ratio_helpers(self):
        self.assertEqual(utils.frame_ratio_of({"frame_ratio": 0.03}), 0.03)
        self.assertEqual(utils.frame_ratio_of({"frame_ratio": 0.03, "frame_enabled": False}), 0.0)
        self.assertEqual(utils.border_px_for(1000, 0.0), 0)
        self.assertEqual(utils.border_px_for(10, 0.001), 1)  # avec cadre : jamais moins de 1 px

    def test_framed_portrait_keeps_its_size_without_frame(self):
        src = make_image(self.dir, "p.jpg", (600, 800))
        (_, img), = utils.render_outputs(src, {"frame_enabled": False, "frame_ratio": 0.05})
        self.assertEqual(img.size, (600, 800))

    def test_every_output_is_3_4_without_frame(self):
        config = {"frame_enabled": False, "frame_ratio": 0.05, "landscape_fill_mode": "blur"}
        sources = {
            "land": make_image(self.dir, "l.jpg", (900, 600)),
            "p23": make_image(self.dir, "p23.jpg", (600, 900)),
        }
        for mode in ("blur", "black"):
            for path in sources.values():
                for kind, img in utils.render_outputs(path, {**config, "landscape_fill_mode": mode}):
                    self.assertAlmostEqual(img.width / img.height, 3 / 4, delta=0.002, msg=f"{path.name} {kind} {mode}")

    def test_crop_without_frame_is_the_bare_crop(self):
        src = make_image(self.dir, "p23.jpg", (600, 900))
        img = utils.render_output(src, {"frame_enabled": False}, "crop34")
        self.assertEqual(img.size, (600, 800))

    def test_no_white_border_is_measurable(self):
        src = make_image(self.dir, "p.jpg", (600, 800), (10, 20, 30))
        framed = utils.render_output(src, {"frame_ratio": 0.05}, "framed")
        bare = utils.render_output(src, {"frame_ratio": 0.05, "frame_enabled": False}, "framed")
        self.assertGreater(utils.measure_border(framed, (255, 255, 255)), 0)
        self.assertEqual(utils.measure_border(bare, (255, 255, 255)), 0)


class CropTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "out"
        # dégradé vertical : la position du recadrage se voit dans la couleur
        img = Image.new("RGB", (600, 900))
        for y in range(900):
            for x in range(0, 600, 50):
                img.paste((y // 4 % 256, 80, 160), (x, y, x + 50, y + 1))
        self.src = self.dir / "p23.jpg"
        img.save(self.src, quality=95)

    def tearDown(self):
        self.tmp.cleanup()

    def test_portrait_2_3_now_yields_main_image_and_crop(self):
        kinds = [k for k, _ in utils.render_outputs(self.src, {"frame_ratio": 0.03})]
        self.assertEqual(kinds, ["framed", "crop34"])

    def test_crop_is_exactly_3_4_after_the_frame(self):
        img = utils.render_output(self.src, {"frame_ratio": 0.03}, "crop34")
        self.assertAlmostEqual(img.width / img.height, 3 / 4, delta=0.002)

    def test_crop_keeps_the_full_width(self):
        config = {"frame_ratio": 0.03}
        img = utils.render_output(self.src, config, "crop34")
        border = round(600 * 0.03)
        self.assertEqual(img.width, 600 + 2 * border)

    def test_offset_moves_the_crop(self):
        top = utils.render_output(self.src, {"frame_ratio": 0.03, "crop_offsets": {str(self.src): 0.0}}, "crop34")
        bottom = utils.render_output(self.src, {"frame_ratio": 0.03, "crop_offsets": {str(self.src): 1.0}}, "crop34")
        self.assertNotEqual(top.tobytes(), bottom.tobytes())
        self.assertLess(top.getpixel((top.width // 2, top.height // 2))[0], bottom.getpixel((bottom.width // 2, bottom.height // 2))[0])

    def test_offset_defaults_to_centre_and_is_clamped(self):
        self.assertEqual(utils.crop_offset_for({}, self.src), 0.5)
        self.assertEqual(utils.crop_offset_for({"crop_offsets": {str(self.src): 7}}, self.src), 1.0)
        self.assertEqual(utils.crop_offset_for({"crop_offsets": {str(self.src): "x"}}, self.src), 0.5)

    def test_crop_is_never_signed(self):
        sig = self.dir / "sig.png"
        Image.new("RGBA", (200, 80), (255, 0, 0, 255)).save(sig)
        plain = utils.render_output(self.src, {"frame_ratio": 0.03}, "crop34")
        signed = utils.render_output(self.src, {"frame_ratio": 0.03, "signature_path": str(sig)}, "crop34")
        self.assertEqual(plain.tobytes(), signed.tobytes())
        # ...alors que l'image principale du portrait 2/3, elle, est signée
        main_plain = utils.render_output(self.src, {"frame_ratio": 0.03}, "framed")
        main_signed = utils.render_output(self.src, {"frame_ratio": 0.03, "signature_path": str(sig)}, "with_sig")
        self.assertNotEqual(main_plain.tobytes(), main_signed.tobytes())

    def test_crop_is_saved_and_numbered_with_the_batch(self):
        utils.process_batch([self.src], self.out, {"frame_ratio": 0.03}, number_files=True)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["01_p23_framed.jpg", "02_p23_crop34.jpg"])

    def test_crop_can_be_excluded_or_disabled(self):
        utils.process_batch([self.src], self.out, {}, excluded={utils.item_key(self.src, "crop34")})
        self.assertEqual([p.name for p in self.out.iterdir()], ["p23_framed.jpg"])
        self.assertEqual([k for k, _ in utils.render_outputs(self.src, {"disabled_kinds": ["crop34"]})], ["framed"])


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

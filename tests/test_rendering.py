"""Rendu des images : cadre, couleurs, recadrage, panoramas, formats et tailles de sortie."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from rkarrousel import config as conf, formats, kinds, outputs as produce, pipeline
from rkarrousel.imaging import frames
from tests.helpers import make_image


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_framed_portrait_is_exactly_3_4_once_framed(self):
        # un 3:4 d'origine est rogné de moins de 1 % pour que, cadre compris, l'image soit exactement en 3:4
        src = make_image(self.dir, "p.jpg", (600, 800))
        (kind, img), = produce.render_outputs(src, {"frame_ratio": 0.05})
        self.assertEqual(kind, "framed")
        self.assertAlmostEqual(img.width / img.height, 3 / 4, delta=0.002)
        self.assertLess(abs(img.width - (600 + 2 * 30)), 20)  # ~ la taille d'origine plus le cadre

    def test_border_color_is_applied(self):
        src = make_image(self.dir, "p.jpg", (300, 400))
        (_, img), = produce.render_outputs(src, {"frame_ratio": 0.1, "border_color": "#FF0000"})
        self.assertEqual(img.getpixel((0, 0)), (255, 0, 0))

    def test_landscape_gives_four_three_four_images(self):
        src = make_image(self.dir, "l.jpg", (900, 600))
        outputs = produce.render_outputs(src, {"frame_ratio": 0.03})
        self.assertEqual([k for k, _ in outputs], ["part1", "part2", "part1_with_sig", "part2_with_sig"])
        for _, img in outputs:
            self.assertAlmostEqual(img.width / img.height, 3 / 4, delta=0.01)

    def test_blur_strength_changes_the_result(self):
        src = self.dir / "l.jpg"
        img = Image.effect_noise((900, 600), 80).convert("RGB")
        img.save(src, quality=95)
        base = {"frame_ratio": 0.03, "landscape_fill_mode": "blur"}
        weak = dict(produce.render_outputs(src, {**base, "blur_strength": 0.3}))["part1_with_sig"]
        strong = dict(produce.render_outputs(src, {**base, "blur_strength": 4.0}))["part1_with_sig"]
        self.assertNotEqual(weak.tobytes(), strong.tobytes())

    def test_preview_downscale_keeps_ratio_and_type(self):
        src = make_image(self.dir, "p.jpg", (1200, 1600))
        (_, img), = produce.render_outputs(src, {"frame_ratio": 0.04}, max_side=400)
        self.assertLess(max(img.size), 500)

    def test_exif_orientation_is_considered_when_peeking(self):
        src = self.dir / "rot.jpg"
        img = Image.new("RGB", (1600, 1200))  # stocké en paysage...
        exif = Image.Exif()
        exif[0x0112] = 6  # ...mais à afficher en portrait
        img.save(src, exif=exif)
        self.assertEqual(pipeline.peek_size(src), (1200, 1600))  # l'orientation EXIF échange largeur et hauteur
        self.assertEqual(formats.detect_ratio_type(*pipeline.peek_size(src)), "portrait_3_4")


class NoFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_frame_ratio_helpers(self):
        self.assertEqual(conf.frame_ratio_of({"frame_ratio": 0.03}), 0.03)
        self.assertEqual(conf.frame_ratio_of({"frame_ratio": 0.03, "frame_enabled": False}), 0.0)
        self.assertEqual(formats.border_px_for(1000, 0.0), 0)
        self.assertEqual(formats.border_px_for(10, 0.001), 1)  # avec cadre : jamais moins de 1 px

    def test_framed_portrait_keeps_its_size_without_frame(self):
        src = make_image(self.dir, "p.jpg", (600, 800))
        (_, img), = produce.render_outputs(src, {"frame_enabled": False, "frame_ratio": 0.05})
        self.assertEqual(img.size, (600, 800))

    def test_every_output_is_3_4_without_frame(self):
        config = {"frame_enabled": False, "frame_ratio": 0.05, "landscape_fill_mode": "blur"}
        sources = {
            "land": make_image(self.dir, "l.jpg", (900, 600)),
            "p23": make_image(self.dir, "p23.jpg", (600, 900)),
        }
        for mode in ("blur", "black"):
            for path in sources.values():
                for kind, img in produce.render_outputs(path, {**config, "landscape_fill_mode": mode}):
                    self.assertAlmostEqual(img.width / img.height, 3 / 4, delta=0.002, msg=f"{path.name} {kind} {mode}")

    def test_crop_without_frame_is_the_bare_crop(self):
        src = make_image(self.dir, "p23.jpg", (600, 900))
        img = produce.render_output(src, {"frame_enabled": False}, "crop34")
        self.assertEqual(img.size, (600, 800))

    def test_no_white_border_is_measurable(self):
        src = make_image(self.dir, "p.jpg", (600, 800), (10, 20, 30))
        framed = produce.render_output(src, {"frame_ratio": 0.05}, "framed")
        bare = produce.render_output(src, {"frame_ratio": 0.05, "frame_enabled": False}, "framed")
        self.assertGreater(frames.measure_border(framed, (255, 255, 255)), 0)
        self.assertEqual(frames.measure_border(bare, (255, 255, 255)), 0)


class ExclusionAndColorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "out"
        self.land = make_image(self.dir, "l.jpg", (900, 600))

    def tearDown(self):
        self.tmp.cleanup()

    def test_excluded_items_are_not_generated_nor_numbered(self):
        excluded = {produce.item_key(self.land, "part2_with_sig")}
        pipeline.process_batch([self.land], self.out, {"frame_ratio": 0.03}, number_files=True, excluded=excluded)
        self.assertEqual(
            sorted(p.name for p in self.out.iterdir()),
            ["01_l_part1_with_sig.jpg", "02_l_part1.jpg", "03_l_part2.jpg"],  # la photo entière d'abord
        )

    def test_numbering_skips_excluded_in_the_middle(self):
        excluded = {produce.item_key(self.land, "part2")}
        pipeline.process_batch([self.land], self.out, {"frame_ratio": 0.03}, number_files=True, excluded=excluded)
        self.assertEqual(  # photo entière, tranche 1, (tranche 2 exclue), photo pivotée : numérotation sans trou
            {p.name for p in self.out.iterdir()}, {"01_l_part1_with_sig.jpg", "02_l_part1.jpg", "03_l_part2_with_sig.jpg"})

    def test_all_excluded_file_is_reported_as_excluded(self):
        every = {produce.item_key(self.land, k) for k in kinds.OPTIONAL_KINDS}
        (result,) = pipeline.process_batch([self.land], self.out, {}, excluded=every)
        self.assertEqual(result.status, "excluded")
        self.assertFalse(list(self.out.glob("*.jpg")))

    def test_disabled_kinds_are_neither_planned_nor_rendered(self):
        config = {"disabled_kinds": ["part2_with_sig", "part1"]}
        self.assertEqual(produce.kinds_for_ratio("landscape_2_3", config), ["part1_with_sig", "part2"])
        self.assertEqual(sorted(k for k, _ in produce.render_outputs(self.land, config)), ["part1_with_sig", "part2"])

    def test_render_output_returns_one_kind_or_none(self):
        self.assertIsNotNone(produce.render_output(self.land, {}, "part2"))
        self.assertIsNone(produce.render_output(self.land, {"disabled_kinds": ["part2"]}, "part2"))

    def test_solid_background_color_is_applied(self):
        config = {"frame_ratio": 0.03, "landscape_fill_mode": "black", "background_color": "#00FF00"}
        img = produce.render_output(self.land, config, "part1_with_sig")
        self.assertEqual(img.getpixel((img.width // 2, img.height // 10)), (0, 255, 0))  # bande de fond, sous le cadre

    def test_default_background_is_still_black(self):
        img = produce.render_output(self.land, {"frame_ratio": 0.03}, "part1_with_sig")
        self.assertEqual(img.getpixel((img.width // 2, img.height // 10)), (0, 0, 0))

    def test_measure_border(self):
        src = make_image(self.dir, "p.jpg", (600, 800))
        img = produce.render_output(src, {"frame_ratio": 0.05, "border_color": "#FFFFFF"}, "framed")
        _, crop_w, _ = formats.crop_box_for(600, 800, 0.05)
        self.assertEqual(frames.measure_border(img, (255, 255, 255)), formats.border_px_for(crop_w, 0.05))


    def test_the_frame_surrounds_the_whole_image_on_a_solid_background_like_on_a_blurred_one(self):
        for fill in ("black", "blur"):
            config = {"frame_ratio": 0.03, "landscape_fill_mode": fill, "background_color": "#1E3A5F"}
            img = produce.render_output(self.land, config, "part1_with_sig")
            self.assertEqual(img.getpixel((0, 0)), (255, 255, 255), fill)                 # cadre au bord de l'image
            self.assertEqual(img.getpixel((img.width - 1, img.height - 1)), (255, 255, 255), fill)
            self.assertGreater(frames.measure_border(img, (255, 255, 255)), 0, fill)
        black = produce.render_output(self.land, {"frame_ratio": 0.03, "landscape_fill_mode": "black"}, "part1_with_sig")
        blur = produce.render_output(self.land, {"frame_ratio": 0.03, "landscape_fill_mode": "blur"}, "part1_with_sig")
        self.assertEqual(black.size, blur.size)  # même format exact, même épaisseur de cadre
        self.assertEqual(frames.measure_border(black, (255, 255, 255)), frames.measure_border(blur, (255, 255, 255)))

    def test_a_2_3_portrait_on_a_solid_background_is_framed_all_around_and_keeps_the_exact_format(self):
        src = make_image(self.dir, "p23.jpg", (600, 900))
        for fmt in ("3:4", "4:5", "1:1", "9:16"):
            img = produce.render_output(src, {"frame_ratio": 0.03, "output_format": fmt, "signature_path": ""}, "framed")
            tw, th = formats.OUTPUT_FORMATS[fmt]
            self.assertAlmostEqual(img.width / img.height, tw / th, delta=0.004, msg=fmt)
            self.assertEqual(img.getpixel((0, 0)), (255, 255, 255), fmt)


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
        kinds = [k for k, _ in produce.render_outputs(self.src, {"frame_ratio": 0.03})]
        self.assertEqual(kinds, ["framed", "crop34"])

    def test_crop_is_exactly_3_4_after_the_frame(self):
        img = produce.render_output(self.src, {"frame_ratio": 0.03}, "crop34")
        self.assertAlmostEqual(img.width / img.height, 3 / 4, delta=0.002)

    def test_crop_keeps_the_full_width(self):
        config = {"frame_ratio": 0.03}
        img = produce.render_output(self.src, config, "crop34")
        border = round(600 * 0.03)
        self.assertEqual(img.width, 600 + 2 * border)

    def test_offset_moves_the_crop(self):
        top = produce.render_output(self.src, {"frame_ratio": 0.03, "crop_offsets": {str(self.src): 0.0}}, "crop34")
        bottom = produce.render_output(self.src, {"frame_ratio": 0.03, "crop_offsets": {str(self.src): 1.0}}, "crop34")
        self.assertNotEqual(top.tobytes(), bottom.tobytes())
        self.assertLess(top.getpixel((top.width // 2, top.height // 2))[0], bottom.getpixel((bottom.width // 2, bottom.height // 2))[0])

    def test_offset_defaults_to_centre_and_is_clamped(self):
        self.assertEqual(conf.crop_offset_for({}, self.src), 0.5)
        self.assertEqual(conf.crop_offset_for({"crop_offsets": {str(self.src): 7}}, self.src), 1.0)
        self.assertEqual(conf.crop_offset_for({"crop_offsets": {str(self.src): "x"}}, self.src), 0.5)

    def test_crop_is_never_signed(self):
        sig = self.dir / "sig.png"
        Image.new("RGBA", (200, 80), (255, 0, 0, 255)).save(sig)
        plain = produce.render_output(self.src, {"frame_ratio": 0.03}, "crop34")
        signed = produce.render_output(self.src, {"frame_ratio": 0.03, "signature_path": str(sig)}, "crop34")
        self.assertEqual(plain.tobytes(), signed.tobytes())
        # ...alors que l'image principale du portrait 2/3, elle, est signée
        main_plain = produce.render_output(self.src, {"frame_ratio": 0.03}, "framed")
        main_signed = produce.render_output(self.src, {"frame_ratio": 0.03, "signature_path": str(sig)}, "with_sig")
        self.assertNotEqual(main_plain.tobytes(), main_signed.tobytes())

    def test_crop_is_saved_and_numbered_with_the_batch(self):
        pipeline.process_batch([self.src], self.out, {"frame_ratio": 0.03}, number_files=True)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["01_p23_framed.jpg", "02_p23_crop34.jpg"])

    def test_crop_can_be_excluded_or_disabled(self):
        pipeline.process_batch([self.src], self.out, {}, excluded={produce.item_key(self.src, "crop34")})
        self.assertEqual([p.name for p in self.out.iterdir()], ["p23_framed.jpg"])
        self.assertEqual([k for k, _ in produce.render_outputs(self.src, {"disabled_kinds": ["crop34"]})], ["framed"])


class AnyFormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_panorama_part_count(self):
        self.assertEqual(formats.panorama_parts(1200, 900), 2)    # 4:3
        self.assertEqual(formats.panorama_parts(1600, 900), 3)    # 16:9
        self.assertEqual(formats.panorama_parts(3000, 1000), 4)   # 3:1
        with self.assertRaises(ValueError):
            formats.panorama_parts(12000, 400)

    def test_kinds_per_new_format(self):
        self.assertEqual(produce.kinds_for_size(1000, 1000, {}), ["framed", "crop34"])
        self.assertEqual(produce.kinds_for_size(800, 1000, {"signature_path": "s.png"}), ["with_sig", "crop34"])
        self.assertEqual(
            produce.kinds_for_size(1600, 900, {}),
            ["part1_with_sig", "part1", "part2", "part3", "part2_with_sig", "crop34"],
        )

    def test_disabled_kinds_apply_to_panorama_parts(self):
        config = {"disabled_kinds": ["part2", "crop34"]}  # part2 règle toutes les tranches après la première
        self.assertEqual(produce.kinds_for_size(1600, 900, config), ["part1_with_sig", "part1", "part2_with_sig"])
        self.assertEqual(produce.kinds_for_size(1600, 900, {"disabled_kinds": ["part1"]})[1], "part2")

    def test_every_output_of_every_format_is_3_4(self):
        for size in ((1000, 1000), (800, 1000), (900, 1600), (1200, 900), (1600, 900), (3000, 1000), (1250, 1000)):
            src = make_image(self.dir, f"{size[0]}x{size[1]}.jpg", size)
            for mode in ("black", "blur"):
                for frame in (True, False):
                    config = {"frame_ratio": 0.03, "frame_enabled": frame, "landscape_fill_mode": mode}
                    outputs = produce.render_outputs(src, config)
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
        parts = [im for kind, im in produce.render_outputs(src, config) if kind.startswith("part") and "sig" not in kind]
        self.assertEqual(len(parts), 4)
        self.assertEqual(sum(p.width for p in parts), 3000)  # tranches contiguës : rien perdu, rien dupliqué
        self.assertEqual({p.height for p in parts}, {parts[0].height})

    def test_panorama_frame_surrounds_only_top_bottom_and_ends(self):
        src = make_image(self.dir, "pano.jpg", (3000, 1000), (10, 20, 30))
        parts = [im for kind, im in produce.render_outputs(src, {"frame_ratio": 0.03}) if kind.startswith("part") and "sig" not in kind]
        b = formats.border_px_for(3000 // 4, 0.03)
        self.assertEqual(parts[0].getpixel((0, parts[0].height // 2)), (255, 255, 255))     # bord extérieur gauche
        self.assertEqual(parts[-1].getpixel((parts[-1].width - 1, parts[-1].height // 2)), (255, 255, 255))
        self.assertEqual(parts[1].getpixel((0, parts[1].height // 2)), (10, 20, 30))         # jonction : pas de cadre
        self.assertEqual(parts[1].getpixel((parts[1].width // 2, 0)), (255, 255, 255))       # haut encadré
        self.assertGreater(b, 0)

    def test_horizontal_crop_for_landscapes_and_squares(self):
        src = make_image(self.dir, "l43.jpg", (1200, 900))
        self.assertEqual(formats.crop_box_for(1200, 900, 0.0), ("x", 675, 900))
        self.assertEqual(formats.crop_box_for(800, 1600, 0.0)[0], "y")
        bare = produce.render_output(src, {"frame_enabled": False}, "crop34")
        self.assertEqual(bare.size, (675, 900))
        left = produce.render_output(src, {"frame_enabled": False, "crop_offsets": {str(src): 0.0}}, "crop34")
        right = produce.render_output(src, {"frame_enabled": False, "crop_offsets": {str(src): 1.0}}, "crop34")
        self.assertEqual(left.size, right.size)

    def test_horizontal_crop_position_moves_the_window(self):
        img = Image.new("RGB", (1200, 900))
        for x in range(1200):
            img.paste((x // 5 % 256, 40, 40), (x, 0, x + 1, 900))
        src = self.dir / "grad.jpg"
        img.save(src, quality=100, subsampling=0)
        left = produce.render_output(src, {"frame_enabled": False, "crop_offsets": {str(src): 0.0}}, "crop34")
        right = produce.render_output(src, {"frame_enabled": False, "crop_offsets": {str(src): 1.0}}, "crop34")
        self.assertLess(left.getpixel((10, 450))[0], right.getpixel((10, 450))[0])

    def test_batch_handles_a_mixed_folder(self):
        files = [
            make_image(self.dir, "a.jpg", (1200, 1600)), make_image(self.dir, "b.jpg", (1200, 900)),
            make_image(self.dir, "c.jpg", (1600, 900)), make_image(self.dir, "d.jpg", (1000, 1000)),
        ]
        results = pipeline.process_batch(files, self.dir / "out", {"frame_ratio": 0.03}, number_files=True)
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
        self.assertEqual(formats.output_format_of({}), (3, 4))
        self.assertEqual(formats.output_format_of({"output_format": "4:5"}), (4, 5))
        self.assertEqual(formats.output_format_of({"output_format": "9:16"}), (9, 16))
        self.assertEqual(formats.output_format_of({"output_format": "nonsense"}), (3, 4))
        self.assertEqual(formats.output_width_of({"output_width": 1080}), 1080)
        self.assertEqual(formats.output_width_of({"output_width": "x"}), 0)
        self.assertEqual(formats.output_width_of({"output_width": 50}), 0)
        self.assertEqual(formats.format_tag((9, 16)), "916")

    def test_every_output_matches_the_chosen_format(self):
        for fmt, (tw, th) in formats.OUTPUT_FORMATS.items():
            for size in self.SOURCES:
                src = make_image(self.dir, f"{size[0]}x{size[1]}_{fmt[0]}.jpg", size)
                for mode in ("black", "blur"):
                    config = {"output_format": fmt, "frame_ratio": 0.03, "landscape_fill_mode": mode}
                    outputs = produce.render_outputs(src, config)
                    self.assertTrue(outputs, (fmt, size))
                    for kind, img in outputs:
                        self.assertAlmostEqual(img.width / img.height, tw / th, delta=0.005, msg=f"{fmt} {size} {kind} {mode}")

    def test_photo_already_at_the_format_is_exact_once_framed(self):
        for fmt, (tw, th) in formats.OUTPUT_FORMATS.items():
            goal = tw / th
            for deviation in (-0.02, 0.0, 0.02):
                width = 1200
                src = make_image(self.dir, f"m_{fmt[0]}_{deviation}.jpg", (width, round(width / (goal * (1 + deviation)))))
                for frame in (0.01, 0.02, 0.05):
                    img = produce.render_output(src, {"output_format": fmt, "frame_ratio": frame}, "framed")
                    self.assertAlmostEqual(img.width / img.height, goal, delta=0.002, msg=f"{fmt} {deviation} {frame}")
                    self.assertGreater(frames.measure_border(img, (255, 255, 255)), 0)

    def test_matching_photo_is_untouched_without_frame(self):
        src = make_image(self.dir, "m.jpg", (600, 800))
        img = produce.render_output(src, {"frame_enabled": False}, "framed")
        self.assertEqual(img.size, (600, 800))

    def test_crop_box_falls_back_to_the_width_when_the_height_cannot_hold_the_frame(self):
        axis, crop_w, crop_h = formats.crop_box_for(1000, 1340, 0.05)  # à peine plus étroit que 3:4
        self.assertEqual((axis, crop_h), ("x", 1340))
        self.assertLess(crop_w, 1000)

    def test_width_gives_exact_instagram_dimensions(self):
        expected = {"3:4": (1080, 1440), "4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920)}
        for fmt, dims in expected.items():
            for size in ((2400, 3600), (4000, 3000), (7200, 2400)):
                src = make_image(self.dir, f"{size[0]}x{size[1]}_{fmt[0]}.jpg", size)
                config = {"output_format": fmt, "output_width": 1080, "frame_ratio": 0.02}
                widths = []
                for kind in produce.kinds_for_size(*size, config):
                    img = produce.render_output(src, config, kind)
                    widths.append(img.width)
                    self.assertLessEqual(img.width, 1080)  # jamais d'agrandissement
                    if img.width == 1080:
                        self.assertEqual(img.size, dims, f"{fmt} {size} {kind}")
                self.assertIn(1080, widths, f"{fmt} {size}")  # au moins une image atteint la largeur demandée

    def test_never_upscales_and_leaves_matching_photos_undistorted(self):
        small = make_image(self.dir, "small.jpg", (600, 800))
        img = produce.render_output(small, {"output_width": 1080, "frame_enabled": False}, "framed")
        self.assertEqual(img.size, (600, 800))
        odd = Image.new("RGB", (2000, 2800))  # 0,714 : proche du 3:4 mais pas exact
        self.assertEqual(produce.finalize_size(odd, {"output_width": 1000}).size, (1000, 1400))

    def test_crop_file_suffix_follows_the_format(self):
        src = self.dir / "p.jpg"
        self.assertEqual(produce.output_name(src, "crop34", "", {}), "p_crop34.jpg")
        self.assertEqual(produce.output_name(src, "crop34", "", {"output_format": "4:5"}), "p_crop45.jpg")
        self.assertEqual(produce.output_name(src, "framed", "01_", {"output_format": "1:1"}), "01_p_framed.jpg")

    def test_panorama_parts_depend_on_the_format(self):
        self.assertEqual(formats.panorama_parts(3000, 1000, (3, 4)), 4)
        self.assertEqual(formats.panorama_parts(3000, 1000, (4, 5)), 4)
        self.assertEqual(formats.panorama_parts(3000, 1000, (1, 1)), 3)
        self.assertEqual(formats.panorama_parts(3000, 1000, (9, 16)), 6)

    def test_a_3_2_photo_uses_the_generic_panorama_in_other_formats(self):
        kinds = produce.kinds_for_size(1500, 1000, {"output_format": "4:5"})
        self.assertEqual(kinds, ["part1_with_sig", "part1", "part2", "part2_with_sig", "crop34"])

    def test_batch_writes_sized_files_with_the_format_suffix(self):
        src = make_image(self.dir, "p23.jpg", (2000, 3000))
        config = {"output_format": "4:5", "output_width": 1080, "frame_ratio": 0.02}
        (result,) = pipeline.process_batch([src], self.dir / "out", config, number_files=True)
        self.assertEqual(sorted(p.name for p in result.outputs), ["01_p23_framed.jpg", "02_p23_crop45.jpg"])
        for path in result.outputs:
            self.assertEqual(Image.open(path).size, (1080, 1350))


if __name__ == "__main__":
    unittest.main()

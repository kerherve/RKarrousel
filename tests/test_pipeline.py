"""Traitement par lots : ordre, numérotation, exclusion, annulation et rapports."""
import tempfile
import threading
import unittest
from pathlib import Path

from rkarrousel import outputs as produce, pipeline
from tests.helpers import make_image


class OrderingTests(unittest.TestCase):
    def test_merge_order_keeps_user_order_and_appends_new(self):
        a, b = Path("a.jpg"), Path("b.jpg")
        items = [(a, "part1"), (a, "part2"), (b, "framed")]
        keys = [produce.item_key(*i) for i in items]
        merged = pipeline.merge_order([keys[2], "gone|framed", keys[0]], items)
        self.assertEqual(merged, [keys[2], keys[0], keys[1]])

    def test_pieces_of_one_photo_can_be_interleaved(self):
        a, b = Path("a.jpg"), Path("b.jpg")
        items = [(a, "part1"), (a, "part2"), (b, "framed")]
        wanted = [produce.item_key(a, "part1"), produce.item_key(b, "framed"), produce.item_key(a, "part2")]
        prefixes = pipeline.build_prefixes(pipeline.merge_order(wanted, items))
        self.assertEqual(prefixes[wanted[0]], "01_")
        self.assertEqual(prefixes[wanted[1]], "02_")
        self.assertEqual(prefixes[wanted[2]], "03_")

    def test_prefix_width_grows_with_count(self):
        keys = [f"k{i}" for i in range(120)]
        self.assertEqual(pipeline.build_prefixes(keys)["k0"], "001_")


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_names_are_unchanged(self):
        src = make_image(self.dir, "shot.jpg", (600, 800))
        (result,) = pipeline.process_batch([src], self.out, {"frame_ratio": 0.03})
        self.assertEqual(result.status, "ok")
        self.assertEqual([p.name for p in result.outputs], ["shot_framed.jpg"])

    def test_numbering_follows_custom_order(self):
        a = make_image(self.dir, "a.jpg", (600, 800))
        b = make_image(self.dir, "b.jpg", (900, 600))
        order = [
            produce.item_key(a, "framed"),
            produce.item_key(b, "part1"),
            produce.item_key(b, "part1_with_sig"),
            produce.item_key(b, "part2"),
        ]
        pipeline.process_batch([a, b], self.out, {"frame_ratio": 0.03}, order=order, number_files=True)
        names = sorted(p.name for p in self.out.iterdir())
        self.assertEqual(
            names,
            ["01_a_framed.jpg", "02_b_part1.jpg", "03_b_part1_with_sig.jpg", "04_b_part2.jpg", "05_b_part2_with_sig.jpg"],
        )

    def test_too_panoramic_and_broken_files_are_reported(self):
        panorama = make_image(self.dir, "pano.jpg", (12000, 400))
        broken = self.dir / "broken.jpg"
        broken.write_bytes(b"not an image")
        results = pipeline.process_batch([panorama, broken], self.out, {})
        self.assertEqual([r.status for r in results], ["error", "error"])
        self.assertIn("panoramique", results[0].message)
        self.assertTrue(results[1].message)

    def test_a_square_photo_is_now_processed(self):
        square = make_image(self.dir, "sq.jpg", (1000, 1000))
        (result,) = pipeline.process_batch([square], self.out, {})
        self.assertEqual(result.status, "ok")
        self.assertEqual(sorted(p.name for p in result.outputs), ["sq_crop34.jpg", "sq_framed.jpg"])

    def test_cancel_stops_before_processing(self):
        src = make_image(self.dir, "a.jpg", (600, 800))
        cancel = threading.Event()
        cancel.set()
        (result,) = pipeline.process_batch([src], self.out, {}, cancel=cancel)
        self.assertEqual(result.status, "cancelled")
        self.assertFalse(list(self.out.glob("*.jpg")))

    def test_parallel_matches_sequential(self):
        files = [make_image(self.dir, f"p{i}.jpg", (600, 800), (i * 20, 50, 90)) for i in range(5)]
        seq_out, par_out = self.dir / "seq", self.dir / "par"
        pipeline.process_batch(files, seq_out, {"frame_ratio": 0.03}, workers=1)
        pipeline.process_batch(files, par_out, {"frame_ratio": 0.03}, workers=4)
        for p in sorted(seq_out.iterdir()):
            self.assertEqual(p.read_bytes(), (par_out / p.name).read_bytes())

    def test_progress_callback_reports_every_file(self):
        files = [make_image(self.dir, f"p{i}.jpg", (600, 800)) for i in range(3)]
        seen = []
        pipeline.process_batch(files, self.out, {}, progress=lambda d, t, p: seen.append((d, t)), workers=2)
        self.assertEqual(sorted(seen), [(1, 3), (2, 3), (3, 3)])


if __name__ == "__main__":
    unittest.main()

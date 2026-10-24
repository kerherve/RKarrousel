import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageChops

from rkarrousel import outputs


def gradient(path: Path, size) -> Path:
    img = Image.new("RGB", size)
    img.putdata([((x * 255) // size[0], (y * 255) // size[1], 90) for y in range(size[1]) for x in range(size[0])])
    img.save(path, quality=95)
    return path


class KindFeaturesTests(unittest.TestCase):
    """`kind_features` doit dire vrai : un réglage déclaré sans effet ne change réellement aucun pixel."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.sig = d / "sig.png"
        Image.new("RGBA", (300, 120), (255, 255, 255, 255)).save(self.sig)
        self.photos = {name: gradient(d / f"{name}.jpg", size) for name, size in {
            "p34": (600, 800), "p23": (600, 900), "l32": (900, 600), "pano": (1600, 600), "square": (700, 700)}.items()}
        self.base = {"frame_ratio": 0.03, "signature_path": str(self.sig), "landscape_fill_mode": "blur"}

    def render(self, photo, kind, **changes):
        return outputs.render_output(self.photos[photo], {**self.base, **changes}, kind)

    def differ(self, a, b) -> bool:
        return ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is not None

    def test_features_match_what_actually_changes_the_pixels(self):
        checked = 0
        for name, path in self.photos.items():
            width, height = Image.open(path).size
            for kind in outputs.kinds_for_size(width, height, self.base):
                features = outputs.kind_features(width, height, kind, self.base)
                fill_changes = self.differ(self.render(name, kind), self.render(name, kind, landscape_fill_mode="black"))
                sig_changes = self.differ(self.render(name, kind), self.render(name, kind, signature_scale=2.0))
                self.assertEqual("fill" in features, fill_changes, f"{name}/{kind} fond")
                self.assertEqual("signature" in features, sig_changes, f"{name}/{kind} signature")
                checked += 1
        self.assertGreaterEqual(checked, 15)

    def test_examples(self):
        cfg = {"output_format": "3:4"}
        self.assertEqual(outputs.kind_features(900, 1200, "framed", cfg), frozenset())
        self.assertEqual(outputs.kind_features(1000, 1500, "framed", cfg), frozenset({"fill"}))
        self.assertEqual(outputs.kind_features(1000, 1500, "with_sig", cfg), frozenset({"fill", "signature"}))
        self.assertEqual(outputs.kind_features(1500, 1000, "part1", cfg), frozenset())
        self.assertEqual(outputs.kind_features(1000, 1500, "crop34", cfg), frozenset())


if __name__ == "__main__":
    unittest.main()

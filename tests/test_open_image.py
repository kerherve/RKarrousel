"""Ouverture des photos : orientation EXIF et décodage JPEG à taille réduite."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, Path(__file__).resolve().parent.parent.as_posix())

from PIL import Image

from rkarrousel.imaging.frames import open_image


class OpenImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def jpeg(self, name, size, orientation=1):
        path = self.dir / name
        image = Image.new("RGB", size, (200, 100, 50))
        exif = image.getexif()
        exif[0x0112] = orientation
        image.save(path, quality=90, exif=exif)
        return path

    def test_without_max_side_the_photo_is_decoded_in_full(self):
        self.assertEqual(open_image(self.jpeg("a.jpg", (4000, 3000))).size, (4000, 3000))

    def test_a_reduced_decode_stays_at_least_as_large_as_requested(self):
        for size in ((4000, 3000), (3000, 4000), (6000, 1500)):
            img = open_image(self.jpeg(f"{size[0]}x{size[1]}.jpg", size), max_side=800)
            self.assertGreaterEqual(max(img.size), 800, size)  # jamais en dessous de la taille voulue
            self.assertLess(max(img.size), max(size), size)    # mais bien plus petit que l'original
            self.assertAlmostEqual(img.width / img.height, size[0] / size[1], delta=0.02)

    def test_the_exif_orientation_still_applies_to_a_reduced_decode(self):
        img = open_image(self.jpeg("rot.jpg", (4000, 3000), orientation=6), max_side=800)  # tournée de 90°
        self.assertGreater(img.height, img.width)

    def test_small_photos_and_other_formats_are_left_alone(self):
        self.assertEqual(open_image(self.jpeg("small.jpg", (300, 200)), max_side=800).size, (300, 200))
        png = self.dir / "p.png"
        Image.new("RGB", (2000, 1000)).save(png)
        self.assertEqual(open_image(png, max_side=500).size, (2000, 1000))  # pas de décodage réduit : la réduction vient après


if __name__ == "__main__":
    unittest.main()

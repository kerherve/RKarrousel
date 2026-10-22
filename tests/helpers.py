"""Outils partagés par les tests."""
from pathlib import Path

from PIL import Image


def make_image(directory: Path, name: str, size, color=(120, 60, 200)) -> Path:
    """Crée une image JPEG unie de la taille voulue et renvoie son chemin."""
    path = directory / name
    Image.new("RGB", size, color).save(path, quality=90)
    return path

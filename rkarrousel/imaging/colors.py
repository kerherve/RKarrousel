"""Couleurs tirées de la photo : couleur dominante et variantes claire / sombre pour le cadre et le fond uni."""
from pathlib import Path
from typing import Tuple

from PIL import Image

from rkarrousel.config import color_mode_of

Color = Tuple[int, int, int]
LIGHT_MIX = 0.65   # part de blanc de la variante claire
DARK_MIX = 0.65    # part de noir de la variante sombre


def dominant_color(img: Image.Image) -> Color:
    """Couleur la plus présente de la photo : image réduite, réduite encore à 6 couleurs (médiane), la plus fréquente gagne."""
    small = img.convert("RGB")
    small.thumbnail((96, 96), Image.Resampling.BOX)
    quantized = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    count, index = max(quantized.getcolors())
    palette = quantized.getpalette()
    return (palette[index * 3], palette[index * 3 + 1], palette[index * 3 + 2])


def styled_color(color: Color, style: str) -> Color:
    """Variante de la couleur : `dominant` (telle quelle), `light` (éclaircie vers le blanc), `dark` (assombrie)."""
    if style == "light":
        return tuple(round(c + (255 - c) * LIGHT_MIX) for c in color)  # type: ignore[return-value]
    if style == "dark":
        return tuple(round(c * (1 - DARK_MIX)) for c in color)  # type: ignore[return-value]
    return color


def to_hex(color: Color) -> str:
    return "#%02X%02X%02X" % color


def resolve_photo_colors(img: Image.Image, config: dict) -> dict:
    """Config effective pour UNE photo : si le cadre ou le fond uni est réglé sur « couleur de la photo », leur
    couleur fixe est remplacée par celle calculée depuis `img`. Sans cela, `config` est renvoyée telle quelle."""
    modes = {key: color_mode_of(config, f"{key}_mode") for key in ("border_color", "background_color")}
    if all(mode == "fixed" for mode in modes.values()):
        return config
    dominant = dominant_color(img)
    resolved = dict(config)
    for key, mode in modes.items():
        if mode != "fixed":
            resolved[key] = to_hex(styled_color(dominant, mode))
    return resolved


def resolve_photo_colors_for_path(path: Path, config: dict) -> dict:
    """Comme `resolve_photo_colors`, depuis un fichier (lecture réduite, rapide même pour un gros JPEG)."""
    if all(color_mode_of(config, f"{key}_mode") == "fixed" for key in ("border_color", "background_color")):
        return config
    with Image.open(path) as img:
        img.draft("RGB", (256, 256))
        return resolve_photo_colors(img, config)

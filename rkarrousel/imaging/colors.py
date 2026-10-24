"""Couleurs tirées de la photo pour le cadre et le fond uni : une couleur de référence (dominante, moyenne ou des
bords) et ses variantes claire, sombre, complémentaire et de contraste."""
import colorsys
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageStat

from rkarrousel.config import border_tweak_of, color_mode_of, color_source_of

Color = Tuple[int, int, int]
LIGHT_MIX = 0.65   # part de blanc de la variante claire
DARK_MIX = 0.65    # part de noir de la variante sombre
CONTRAST_LIGHT = 0.82      # contraste sur photo sombre : clair (clarté HLS), à la teinte de la photo
CONTRAST_DARK = 0.14       # contraste sur photo claire : foncé
CONTRAST_SATURATION = (0.25, 0.6)  # saturation minimale et maximale : une teinte lisible, jamais un blanc ou un noir pur
EDGE_FRACTION = 0.06       # épaisseur de la bande de bord, en fraction du plus petit côté


def dominant_color(img: Image.Image) -> Color:
    """Couleur la plus présente de la photo : image réduite, réduite encore à 6 couleurs (médiane), la plus fréquente gagne."""
    small = img.convert("RGB")
    small.thumbnail((96, 96), Image.Resampling.BOX)
    quantized = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    count, index = max(quantized.getcolors())
    palette = quantized.getpalette()
    return (palette[index * 3], palette[index * 3 + 1], palette[index * 3 + 2])


def average_color(img: Image.Image) -> Color:
    """Couleur moyenne de toute la photo."""
    small = img.convert("RGB")
    small.thumbnail((96, 96), Image.Resampling.BOX)
    return tuple(round(v) for v in ImageStat.Stat(small).mean[:3])  # type: ignore[return-value]


def edge_color(img: Image.Image) -> Color:
    """Couleur moyenne d'une bande le long des quatre bords : ce que le cadre touche vraiment."""
    small = img.convert("RGB")
    small.thumbnail((96, 96), Image.Resampling.BOX)
    width, height = small.size
    band = max(1, round(min(width, height) * EDGE_FRACTION))
    strips = [(0, 0, width, band), (0, height - band, width, height), (0, band, band, height - band),
              (width - band, band, width, height - band)]
    totals, count = [0.0, 0.0, 0.0], 0
    for box in strips:
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        region = small.crop(box)
        pixels = region.size[0] * region.size[1]
        for channel, mean in enumerate(ImageStat.Stat(region).mean[:3]):
            totals[channel] += mean * pixels
        count += pixels
    return tuple(round(total / count) for total in totals)  # type: ignore[return-value]


def reference_color(img: Image.Image, source: str = "dominant") -> Color:
    """Couleur de référence de la photo, selon la source choisie (`dominant`, `edges` ou `average`)."""
    if source == "edges":
        return edge_color(img)
    if source == "average":
        return average_color(img)
    return dominant_color(img)


def luminance(color: Color) -> float:
    """Luminosité perçue, de 0 (noir) à 1 (blanc)."""
    r, g, b = color
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def styled_color(color: Color, style: str) -> Color:
    """Variante de la couleur : `dominant` (telle quelle), `light` (éclaircie vers le blanc), `dark` (assombrie),
    `complement` (teinte opposée, saturation et clarté tempérées) ou `contrast` (clair sur une photo sombre, foncé sur
    une photo claire, à la teinte de la photo : un pastel ou un brun profond plutôt qu'un blanc ou un noir pur)."""
    if style == "light":
        return tuple(round(c + (255 - c) * LIGHT_MIX) for c in color)  # type: ignore[return-value]
    if style == "dark":
        return tuple(round(c * (1 - DARK_MIX)) for c in color)  # type: ignore[return-value]
    if style == "complement":
        h, light, s = colorsys.rgb_to_hls(*(c / 255 for c in color))
        r, g, b = colorsys.hls_to_rgb((h + 0.5) % 1.0, min(0.75, max(0.3, light)), min(0.65, s))
        return (round(r * 255), round(g * 255), round(b * 255))
    if style == "contrast":
        h, _, s = colorsys.rgb_to_hls(*(c / 255 for c in color))
        light = CONTRAST_LIGHT if luminance(color) < 0.5 else CONTRAST_DARK
        low, high = CONTRAST_SATURATION
        r, g, b = colorsys.hls_to_rgb(h, light, 0.0 if s < 0.05 else min(high, max(low, s)))  # un gris reste neutre
        return (round(r * 255), round(g * 255), round(b * 255))
    return color


def tweak_color(color: Color, hue: float = 0.0, saturation: float = 0.0, lightness: float = 0.0) -> Color:
    """Retouche fine : décale la teinte (en degrés), la saturation et la clarté (en fraction), pour affiner à l'œil."""
    if not (hue or saturation or lightness):
        return color
    h, light, sat = colorsys.rgb_to_hls(*(c / 255 for c in color))
    r, g, b = colorsys.hls_to_rgb((h + hue / 360) % 1.0, min(1.0, max(0.0, light + lightness)),
                                  min(1.0, max(0.0, sat + saturation)))
    return (round(r * 255), round(g * 255), round(b * 255))


def to_hex(color: Color) -> str:
    return "#%02X%02X%02X" % color


def resolve_photo_colors(img: Image.Image, config: dict) -> dict:
    """Config effective pour UNE photo : si le cadre ou le fond uni est réglé sur « couleur de la photo », leur
    couleur fixe est remplacée par celle calculée depuis `img`. Sans cela, `config` est renvoyée telle quelle."""
    modes = {key: color_mode_of(config, f"{key}_mode") for key in ("border_color", "background_color")}
    if all(mode == "fixed" for mode in modes.values()):
        return config
    reference = reference_color(img, color_source_of(config))
    resolved = dict(config)
    for key, mode in modes.items():
        if mode != "fixed":
            color = styled_color(reference, mode)
            if key == "border_color":
                color = tweak_color(color, *border_tweak_of(config))  # retouche fine du cadre, à la main
            resolved[key] = to_hex(color)
    return resolved


def resolve_photo_colors_for_path(path: Path, config: dict) -> dict:
    """Comme `resolve_photo_colors`, depuis un fichier (lecture réduite, rapide même pour un gros JPEG)."""
    if all(color_mode_of(config, f"{key}_mode") == "fixed" for key in ("border_color", "background_color")):
        return config
    with Image.open(path) as img:
        img.draft("RGB", (256, 256))
        return resolve_photo_colors(img, config)

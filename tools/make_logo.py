#!/usr/bin/env python3
"""Dessine le logo de RKarrousel et en tire les fichiers de `rkarrousel/assets/` :

    python tools/make_logo.py

Le logo : trois photos encadrées côte à côte, comme un carrousel Instagram. La photo du milieu a le cadre blanc, ses
voisines un cadre d'une autre couleur (une couleur de cadre par photo, comme dans l'appli), et trois points rappellent
les pastilles d'un post à plusieurs images. Tout est dessiné ici, sans image source : le logo se régénère à l'identique.
"""
from pathlib import Path
from typing import List, Sequence, Tuple

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "rkarrousel" / "assets"
SIZE = 1024
SUPERSAMPLE = 2

Color = Tuple[int, int, int]


def lerp(a: Color, b: Color, t: float) -> Color:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def gradient(size: Tuple[int, int], stops: Sequence[Tuple[float, Color]]) -> Image.Image:
    """Dégradé vertical à plusieurs étapes [(position 0..1, couleur), …]."""
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                draw.line([(0, y), (width, y)], fill=lerp(c0, c1, (t - t0) / max(1e-9, t1 - t0)))
                break
    return image


def rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def photo(width: int, height: int, sky: Sequence[Tuple[float, Color]], hill: Color, sun: Color) -> Image.Image:
    """Une « photo » : un ciel en dégradé, un soleil bas et deux collines, pour qu'on lise une vraie photo même en petit."""
    image = gradient((width, height), sky)
    draw = ImageDraw.Draw(image)
    cx, cy, r = int(width * 0.62), int(height * 0.58), int(width * 0.16)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=sun)
    far = [(0, height * 0.70), (width * 0.30, height * 0.56), (width * 0.55, height * 0.68), (width * 0.80, height * 0.60),
           (width, height * 0.70), (width, height), (0, height)]
    near = [(0, height * 0.82), (width * 0.35, height * 0.72), (width * 0.70, height * 0.84), (width, height * 0.76),
            (width, height), (0, height)]
    draw.polygon(far, fill=lerp(hill, sky[-1][1], 0.35))
    draw.polygon(near, fill=hill)
    return image


def framed_card(width: int, height: int, frame: Color, sky, hill: Color, sun: Color) -> Image.Image:
    """Une photo 3:4 avec son cadre, aux coins légèrement arrondis (RGBA)."""
    border = round(width * 0.075)
    card = Image.new("RGB", (width, height), frame)
    card.paste(photo(width - 2 * border, height - 2 * border, sky, hill, sun), (border, border))
    out = card.convert("RGBA")
    out.putalpha(rounded_mask((width, height), round(width * 0.07)))
    return out


def draw_logo(size: int = SIZE) -> Image.Image:
    s = size * SUPERSAMPLE
    background = gradient((s, s), [(0.0, (34, 42, 84)), (1.0, (12, 14, 30))]).convert("RGBA")
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    canvas.paste(background, (0, 0), rounded_mask((s, s), round(s * 0.22)))

    centre_w, centre_h = round(s * 0.36), round(s * 0.36 * 4 / 3)
    side_w, side_h = round(s * 0.27), round(s * 0.27 * 4 / 3)
    tuck = round(s * 0.05)  # les photos voisines passent derrière celle du milieu
    cy = round(s * 0.485)
    cx = s // 2

    left = framed_card(side_w, side_h, (64, 201, 198), [(0, (70, 120, 200)), (1, (150, 90, 190))], (28, 40, 90), (255, 214, 140))
    right = framed_card(side_w, side_h, (255, 118, 117), [(0, (255, 170, 120)), (1, (230, 90, 140))], (70, 30, 80), (255, 240, 190))
    centre = framed_card(centre_w, centre_h, (255, 255, 255),
                         [(0, (255, 159, 67)), (0.55, (238, 90, 138)), (1, (95, 39, 205))], (28, 20, 70), (255, 236, 170))

    canvas.alpha_composite(left, (cx - centre_w // 2 - side_w + tuck, cy - side_h // 2))
    canvas.alpha_composite(right, (cx + centre_w // 2 - tuck, cy - side_h // 2))
    # ombre portée de la photo du milieu, pour qu'elle passe devant ses voisines
    shadow = Image.new("RGBA", (centre_w + 40, centre_h + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([20, 20, centre_w + 20, centre_h + 20], radius=round(centre_w * 0.07),
                                             fill=(0, 0, 0, 120))
    canvas.alpha_composite(shadow, (cx - centre_w // 2 - 20, cy - centre_h // 2 - 8))
    canvas.alpha_composite(centre, (cx - centre_w // 2, cy - centre_h // 2))

    dots = ImageDraw.Draw(canvas)
    dot_y, dot_r, spacing = round(s * 0.885), round(s * 0.017), round(s * 0.058)
    for index, offset in enumerate((-spacing, 0, spacing)):
        color = (255, 255, 255, 255) if index == 1 else (255, 255, 255, 110)
        r = dot_r if index == 1 else round(dot_r * 0.8)
        dots.ellipse([cx + offset - r, dot_y - r, cx + offset + r, dot_y + r], fill=color)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def write_assets() -> List[Path]:
    ASSETS.mkdir(parents=True, exist_ok=True)
    logo = draw_logo(SIZE)
    written = []
    for name, side in (("logo_256.png", 256), ("logo_64.png", 64)):
        path = ASSETS / name
        logo.resize((side, side), Image.Resampling.LANCZOS).save(path, optimize=True)
        written.append(path)
    ico = ASSETS / "icon.ico"
    logo.save(ico, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    written.append(ico)
    preview = ROOT / "docs" / "logo.png"
    preview.parent.mkdir(exist_ok=True)
    logo.resize((512, 512), Image.Resampling.LANCZOS).save(preview, optimize=True)
    written.append(preview)
    return written


if __name__ == "__main__":
    for path in write_assets():
        print(f"écrit : {path.relative_to(ROOT)}")

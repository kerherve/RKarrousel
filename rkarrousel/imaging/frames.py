"""Ouverture, cadre et enregistrement des images."""

from pathlib import Path

from PIL import Image, ImageOps

from rkarrousel.config import DEFAULT_BORDER_COLOR, DEFAULT_JPEG_QUALITY


def open_image(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode not in {"RGB", "RGBA", "L"}:
        img = img.convert("RGB")
    return img


def frame_image(img: Image.Image, border_px: int, color=DEFAULT_BORDER_COLOR) -> Image.Image:
    if border_px <= 0:
        return img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img.copy()
    if img.mode == "RGBA":
        framed = Image.new("RGBA", (img.width + 2 * border_px, img.height + 2 * border_px), (*color, 255))
    else:
        framed = Image.new("RGB", (img.width + 2 * border_px, img.height + 2 * border_px), color)
        if img.mode != "RGB":
            img = img.convert("RGB")
    framed.paste(img, (border_px, border_px))
    return framed


def frame_image_with_outer_edge(img: Image.Image, border_px: int, outer_side: str, color=DEFAULT_BORDER_COLOR) -> Image.Image:
    if img.mode != "RGB" and img.mode != "RGBA":
        img = img.convert("RGB")

    if outer_side == "left":
        border = (border_px, border_px, 0, border_px)
    elif outer_side == "right":
        border = (0, border_px, border_px, border_px)
    else:
        border = (border_px, border_px, border_px, border_px)

    return ImageOps.expand(img, border=border, fill=color)


def save_image(img: Image.Image, output_path: Path, quality: int = DEFAULT_JPEG_QUALITY) -> None:
    params = {}
    suffix = output_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        if img.mode == "RGBA":
            img = img.convert("RGB")
        params = {"quality": quality, "subsampling": 0, "optimize": True}
    elif suffix == ".png":
        params = {"compress_level": 0}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, **params)


def measure_border(img: Image.Image, color, tolerance: int = 12, skip_color=None) -> int:
    """Épaisseur (px) du cadre de la couleur donnée, mesurée depuis le bord haut au milieu de l'image.
    `skip_color` : couleur d'un fond uni qui entoure le cadre (ignoré avant d'atteindre le cadre)."""
    rgb = img.convert("RGB")
    color = tuple(color)
    skip = tuple(skip_color) if skip_color is not None else None
    x = rgb.width // 2

    def close(pixel, target):
        return all(abs(pixel[i] - target[i]) <= tolerance for i in range(3))

    count = 0
    for y in range(rgb.height):
        pixel = rgb.getpixel((x, y))
        if close(pixel, color):
            count += 1
        elif count == 0 and skip is not None and close(pixel, skip):
            continue
        else:
            break
    return count

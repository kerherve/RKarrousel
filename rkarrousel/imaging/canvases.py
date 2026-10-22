"""Rendus « une image au format de sortie » : photo déjà au bon format, photo entière sur un fond uni ou
flouté, recadrage."""

from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageFilter

from rkarrousel.config import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_BLUR_STRENGTH,
    DEFAULT_BORDER_COLOR,
    DEFAULT_CROP_OFFSET,
    DEFAULT_FRAME_RATIO,
    DEFAULT_LANDSCAPE_FILL_MODE,
    DEFAULT_SIGNATURE_POSITION,
    DEFAULT_SIGNATURE_SCALE,
    background_color_of,
    blur_strength_of,
    border_color_of,
    frame_ratio_of,
    signature_position_of,
    signature_scale_of,
)
from rkarrousel.formats import DEFAULT_TARGET, border_px_for, crop_box_for, output_format_of
from rkarrousel.imaging.frames import frame_image
from rkarrousel.imaging.signature import add_signature_to_image


LANDSCAPE_SIGNATURE_SIZE_FACTOR = 1.2
LANDSCAPE_SIGNATURE_MARGIN_RATIO = 0.03


def render_portrait_3_4(img: Image.Image, config: dict) -> Image.Image:
    """Image déjà au format de sortie (±3 %). Encadrée telle quelle, elle n'aurait plus tout à fait le bon format
    (le cadre s'ajoute sur les quatre côtés) et Instagram rognerait le cadre de façon inégale : on la rogne donc
    d'une fraction de pour cent, au centre, pour que l'image encadrée ait EXACTEMENT le format de sortie."""
    frame_ratio = frame_ratio_of(config)
    width, height = img.size
    if frame_ratio <= 0:
        return frame_image(img, 0, border_color_of(config))
    axis, crop_w, crop_h = crop_box_for(width, height, frame_ratio, output_format_of(config))
    left, top = (width - crop_w) // 2, (height - crop_h) // 2
    cropped = img.crop((left, top, left + crop_w, top + crop_h))
    return frame_image(cropped, border_px_for(crop_w, frame_ratio), border_color_of(config))


def render_portrait_2_3(img: Image.Image, config: dict) -> Image.Image:
    sig_path = config.get("signature_path")
    sig_path = Path(sig_path) if sig_path else None
    color = border_color_of(config)
    position = signature_position_of(config)
    sig_scale = signature_scale_of(config)
    if config.get("landscape_fill_mode", DEFAULT_LANDSCAPE_FILL_MODE) == "blur":
        return create_portrait_with_landscape_blur_fill(
            img,
            sig_path,
            frame_ratio=frame_ratio_of(config),
            signature_on_photo=True,
            border_color=color,
            blur_strength=blur_strength_of(config),
            sig_position=position,
            sig_scale=sig_scale,
            target=output_format_of(config),
        )

    signed = add_signature_to_image(img, sig_path, position=position, user_scale=sig_scale)

    src_w, src_h = signed.size
    border_px = border_px_for(min(src_w, src_h), frame_ratio_of(config))
    framed = frame_image(signed, border_px, color)

    min_width = framed.width
    min_height = framed.height

    # Place the framed photo onto a canvas of the output format (3/4 by default)
    tw, th = output_format_of(config)
    if min_width * th >= min_height * tw:
        portrait_width = min_width
        portrait_height = int(round(portrait_width * th / tw))
    else:
        portrait_height = min_height
        portrait_width = int(round(portrait_height * tw / th))

    # Keep the final canvas at least as large as the framed image
    portrait_width = max(portrait_width, min_width)
    portrait_height = max(portrait_height, min_height)

    background = Image.new("RGB", (portrait_width, portrait_height), background_color_of(config))
    x_offset = (portrait_width - framed.width) // 2
    y_offset = (portrait_height - framed.height) // 2
    background.paste(framed, (x_offset, y_offset))
    return background


def render_crop_3_4(img: Image.Image, config: dict, offset: float = DEFAULT_CROP_OFFSET) -> Image.Image:
    """Recadre n'importe quelle image au format de sortie (3/4 par défaut) (position `offset` de 0 à 1 le long de l'axe libre) puis l'encadre :
    le résultat est un portrait 3/4 prêt pour Instagram. Pas de signature : seules les photos portrait d'origine
    sont signées, pas les images redimensionnées."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    frame_ratio = frame_ratio_of(config)
    width, height = img.size
    axis, crop_w, crop_h = crop_box_for(width, height, frame_ratio, output_format_of(config))
    border = border_px_for(crop_w, frame_ratio)
    offset = max(0.0, min(1.0, offset))
    if axis == "y":
        top = int(round((height - crop_h) * offset))
        box = (0, top, width, top + crop_h)
    else:
        left = int(round((width - crop_w) * offset))
        box = (left, 0, left + crop_w, height)
    return frame_image(img.crop(box), border, border_color_of(config))


def create_portrait_with_landscape_content(
    img: Image.Image,
    signature_path: Optional[Path],
    frame_ratio: float = DEFAULT_FRAME_RATIO,
    border_color=DEFAULT_BORDER_COLOR,
    sig_position: str = DEFAULT_SIGNATURE_POSITION,
    sig_scale: float = DEFAULT_SIGNATURE_SCALE,
    background_color=DEFAULT_BACKGROUND_COLOR,
    target: Tuple[int, int] = DEFAULT_TARGET,
) -> Image.Image:
    """
    Crée une image au format de sortie (3/4 par défaut) avec l'image paysage complète centrée, signée, encadrée et placée sur fond uni (noir par défaut).
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Sign before scaling/framing so the signature stays anchored to the
    # photo's own corner (not the page corner), and scales/rotates with it.
    signed = add_signature_to_image(img, signature_path, position=sig_position, user_scale=sig_scale)
    src_w, src_h = signed.size
    border_px = border_px_for(min(src_w, src_h), frame_ratio)

    # determine the canvas size (output format) to fit the source image plus frame
    tw, th = target
    portrait_width = max(src_w + 2 * border_px, int(round((src_h + 2 * border_px) * tw / th)))
    portrait_height = int(round(portrait_width * th / tw))

    inner_w = portrait_width - 2 * border_px
    inner_h = portrait_height - 2 * border_px

    scaled_w = src_w
    scaled_h = src_h
    if src_w > inner_w or src_h > inner_h:
        scale = min(inner_w / src_w, inner_h / src_h)
        scaled_w = max(1, int(round(src_w * scale)))
        scaled_h = max(1, int(round(src_h * scale)))

    signed_scaled = signed.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    framed = frame_image(signed_scaled, border_px, border_color)

    background = Image.new("RGB", (portrait_width, portrait_height), background_color)
    x_offset = (portrait_width - framed.width) // 2
    y_offset = (portrait_height - framed.height) // 2
    background.paste(framed, (x_offset, y_offset))

    return background


def create_portrait_with_landscape_blur_fill(
    img: Image.Image,
    signature_path: Optional[Path],
    frame_ratio: float = DEFAULT_FRAME_RATIO,
    signature_rotation: int = 0,
    signature_on_photo: bool = False,
    border_color=DEFAULT_BORDER_COLOR,
    blur_strength: float = DEFAULT_BLUR_STRENGTH,
    sig_position: str = DEFAULT_SIGNATURE_POSITION,
    sig_scale: float = DEFAULT_SIGNATURE_SCALE,
    target: Tuple[int, int] = DEFAULT_TARGET,
) -> Image.Image:
    """
    Crée une image au format de sortie (3/4 par défaut) avec la photo nette étendue jusqu'aux bords (largeur
    pleine si la photo est large, hauteur pleine si elle est étroite/pivotée), le reste
    comblé par une version agrandie et floutée de la même photo, puis encadre l'ensemble
    du canevas (comme les portraits 3/4 classiques). La signature est apposée en dernier,
    sur la bande floutée (pas sur la photo nette) ; si signature_rotation est non nul,
    elle est tournée avec la photo et placée sur le bord correspondant.
    Avec signature_on_photo, la signature est apposée sur la photo nette elle-même
    (coin bas-droit, comme les portraits 2/3 sur fond noir) au lieu de la bande floutée.
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    src_w, src_h = img.size

    # Extend on whichever axis the source photo is short on, so the final
    # canvas is exactly 3/4 regardless of how wide or narrow the photo is.
    # frame_image() adds the border symmetrically afterwards, which nudges a
    # content canvas that's exactly 3/4 up towards square (same effect as in
    # split_2_3_to_3_4) -- so the content size is solved to pre-compensate for
    # that border and land on exactly 3/4 once framed, matching the other 3/4
    # outputs pixel-for-pixel in proportion.
    tw, th = target
    target_ratio = tw / th
    extra = th + 2 * frame_ratio * (th - tw)  # pré-compense le cadre : (largeur+2b)/(hauteur+2b) = tw/th
    if src_w / src_h >= target_ratio:
        content_width = src_w
        content_height = max(int(round(content_width * extra / tw)), src_h)
    else:
        content_height = src_h
        content_width = max(int(round(content_height * tw / extra)), src_w)

    # Cover-fit the (unsigned) photo over the content canvas, then blur it.
    scale = max(content_width / img.width, content_height / img.height)
    bg_w = max(content_width, int(round(img.width * scale)))
    bg_h = max(content_height, int(round(img.height * scale)))
    background = img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    crop_x = (bg_w - content_width) // 2
    crop_y = (bg_h - content_height) // 2
    background = background.crop((crop_x, crop_y, crop_x + content_width, crop_y + content_height))
    blur_radius = max(20, int(round(min(content_width, content_height) * 0.015)))
    blur_radius = max(1, int(round(blur_radius * blur_strength)))
    background = background.filter(ImageFilter.GaussianBlur(blur_radius))

    x_offset = (content_width - src_w) // 2
    y_offset = (content_height - src_h) // 2
    # The blurred fill is built from the unsigned photo so no smeared copy of
    # the signature shows up in the margins.
    sharp = (
        add_signature_to_image(img, signature_path, position=sig_position, user_scale=sig_scale)
        if signature_on_photo
        else img
    )
    background.paste(sharp, (x_offset, y_offset))

    border_px = border_px_for(min(content_width, content_height), frame_ratio)
    framed = frame_image(background, border_px, border_color)
    if signature_on_photo:
        return framed

    # Sign the finished canvas (not the raw photo) so the signature always
    # lands in the blurred margin instead of on top of the sharp photo.
    position = "left-center" if signature_rotation else "bottom-center"
    return add_signature_to_image(
        framed,
        signature_path,
        position=position,
        size_factor=LANDSCAPE_SIGNATURE_SIZE_FACTOR,
        margin_ratio=LANDSCAPE_SIGNATURE_MARGIN_RATIO,
        rotate=signature_rotation,
        user_scale=sig_scale,
    )

"""Découpage d'un paysage en images contiguës (panorama) et versions « photo entière » d'un paysage."""

from pathlib import Path
from typing import Collection, Iterator, Optional, Tuple

from PIL import Image, ImageOps

from rkarrousel.config import (
    DEFAULT_LANDSCAPE_FILL_MODE,
    background_color_of,
    blur_strength_of,
    border_color_of,
    frame_ratio_of,
    signature_position_of,
    signature_scale_of,
)
from rkarrousel.formats import border_px_for, output_format_of
from rkarrousel.imaging.canvases import (
    create_portrait_with_landscape_blur_fill,
    create_portrait_with_landscape_content,
)
from rkarrousel.imaging.frames import frame_image_with_outer_edge
from rkarrousel.imaging.signature import add_signature_to_image
from rkarrousel.kinds import OPTIONAL_KINDS


def _iter_full_portraits(img: Image.Image, config: dict, wanted) -> Iterator[Tuple[str, Image.Image]]:
    """Les deux versions « photo entière » en portrait 3/4 d'un paysage : droite (`part1_with_sig`) et pivotée
    (`part2_with_sig`)."""
    frame_ratio = frame_ratio_of(config)
    color = border_color_of(config)
    sig_path = config.get("signature_path")
    sig_path = Path(sig_path) if sig_path else None
    position = signature_position_of(config)
    sig_scale = signature_scale_of(config)
    fill_mode = config.get("landscape_fill_mode", DEFAULT_LANDSCAPE_FILL_MODE)

    blur = blur_strength_of(config)
    bg = background_color_of(config)
    target = output_format_of(config)

    if "part1_with_sig" in wanted:
        if fill_mode == "blur":
            yield "part1_with_sig", create_portrait_with_landscape_blur_fill(
                img, sig_path, frame_ratio=frame_ratio, border_color=color, blur_strength=blur, sig_scale=sig_scale,
                target=target,
            )
        else:
            yield "part1_with_sig", create_portrait_with_landscape_content(
                img, sig_path, frame_ratio=frame_ratio, border_color=color, sig_position=position,
                sig_scale=sig_scale, background_color=bg, target=target,
            )

    if "part2_with_sig" in wanted:
        if fill_mode == "blur":
            img_rotated = img.transpose(Image.Transpose.ROTATE_270)
            yield "part2_with_sig", create_portrait_with_landscape_blur_fill(
                img_rotated,
                sig_path,
                frame_ratio=frame_ratio,
                signature_rotation=270,
                border_color=color,
                blur_strength=blur,
                sig_scale=sig_scale,
                target=target,
            )
        else:
            # Sign the upright photo first, then rotate the signed result as one block
            # so the signature turns together with the photo instead of staying upright.
            signed_for_rotation = add_signature_to_image(img, sig_path, position=position, user_scale=sig_scale)
            img_rotated = signed_for_rotation.transpose(Image.Transpose.ROTATE_270)
            yield "part2_with_sig", create_portrait_with_landscape_content(
                img_rotated, None, frame_ratio=frame_ratio, border_color=color, background_color=bg, target=target
            )


def iter_split_2_3_to_3_4(
    img: Image.Image, config: dict, only: Optional[Collection[str]] = None
) -> Iterator[Tuple[str, Image.Image]]:
    """Génère (kind, image) pour un paysage 2/3 : deux moitiés encadrées (panorama)
    puis les deux versions portrait 3/4 de la photo entière."""
    width, height = img.size
    frame_ratio = frame_ratio_of(config)
    color = border_color_of(config)
    target_width = width // 2
    # Border thickness is based on the crop's own width (the short side),
    # same basis as every other 3/4 output in the app (frame_ratio * short
    # side) so the frame reads the same thickness everywhere.
    border_px = border_px_for(target_width, frame_ratio)
    # The frame is added asymmetrically (left/top/bottom only, nothing on the
    # shared inner edge) so the pair reassembles without a double border in the
    # middle. That means the border itself skews the ratio: it adds border_px
    # once to the width but twice to the height. Solve for the crop height so
    # that, once that border is added, the final image lands on exactly 3/4 —
    # otherwise Instagram re-crops it and the border ends up uneven.
    target_height = int(round((4 * target_width - 2 * border_px) / 3))

    if target_height > height:
        raise ValueError(
            f"Taille impossible : hauteur {height}px insuffisante pour deux portraits 3/4 de largeur {target_width}px"
        )

    crop_top = (height - target_height) // 2
    left_crop = img.crop((0, crop_top, target_width, crop_top + target_height))
    right_crop = img.crop((target_width, crop_top, width, crop_top + target_height))
    wanted = set(OPTIONAL_KINDS) if only is None else set(only)
    # apply frame on three sides: top, bottom and outer vertical edge only
    if "part1" in wanted:
        yield "part1", frame_image_with_outer_edge(left_crop, border_px, "left", color)
    if "part2" in wanted:
        yield "part2", frame_image_with_outer_edge(right_crop, border_px, "right", color)
    if not wanted & {"part1_with_sig", "part2_with_sig"}:
        return
    yield from _iter_full_portraits(img, config, wanted)


def iter_landscape_other(
    img: Image.Image, config: dict, parts: int, only: Optional[Collection[str]] = None
) -> Iterator[Tuple[str, Image.Image]]:
    """Paysage de format quelconque : `parts` tranches contiguës encadrées (le cadre n'entoure que le haut, le
    bas et les deux extrémités, pour que le panorama se recompose sans double bordure), toutes en 3/4 une fois
    encadrées, puis les deux versions « photo entière »."""
    width, height = img.size
    frame_ratio = frame_ratio_of(config)
    color = border_color_of(config)
    border = border_px_for(width // parts, frame_ratio)
    frame_w = (width + 2 * border) / parts                 # largeur finale de chaque image (extrémités : contenu - bordure)
    tw, th = output_format_of(config)
    content_h = int(round(frame_w * th / tw - 2 * border))
    if content_h > height:
        raise ValueError(f"Taille impossible : hauteur {height}px insuffisante pour {parts} images {tw}:{th}")
    top = (height - content_h) // 2
    edges = [0] + [int(round(i * frame_w - border)) for i in range(1, parts)] + [width]
    wanted = set(only) if only is not None else {f"part{i}" for i in range(1, parts + 1)} | set(OPTIONAL_KINDS)
    for index in range(parts):
        kind = f"part{index + 1}"
        if kind not in wanted:
            continue
        piece = img.crop((edges[index], top, edges[index + 1], top + content_h))
        if index == 0:
            yield kind, frame_image_with_outer_edge(piece, border, "left", color)
        elif index == parts - 1:
            yield kind, frame_image_with_outer_edge(piece, border, "right", color)
        else:
            yield kind, ImageOps.expand(piece.convert("RGB") if piece.mode not in ("RGB", "RGBA") else piece,
                                        border=(0, border, 0, border), fill=color)
    if wanted & {"part1_with_sig", "part2_with_sig"}:
        yield from _iter_full_portraits(img, config, wanted)

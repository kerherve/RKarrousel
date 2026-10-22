"""Pose de la signature sur une image."""

import logging
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger("imagesplitter")


def add_signature_to_image(
    img: Image.Image,
    signature_path: Optional[Path],
    position: str = "bottom-right",
    size_factor: float = 1.0,
    margin_ratio: Optional[float] = None,
    rotate: int = 0,
    user_scale: float = 1.0,
) -> Image.Image:
    if not signature_path or not signature_path.exists():
        return img
    try:
        sig = Image.open(signature_path).convert("RGBA")
        # Base the bound on the photo's short side so the signature size
        # doesn't collapse depending on whether width or height is smaller.
        short_side = min(img.width, img.height)
        max_sig_width = int(round(short_side // 4 * size_factor))
        max_sig_height = int(round(short_side // 6 * size_factor))
        if size_factor != 1.0:
            # Explicit sizing request: scale to fill the bound in both directions,
            # not just shrink when oversized.
            scale = min(max_sig_width / sig.width, max_sig_height / sig.height)
            sig = sig.resize(
                (max(1, int(round(sig.width * scale))), max(1, int(round(sig.height * scale)))),
                Image.Resampling.LANCZOS,
            )
        elif sig.width > max_sig_width or sig.height > max_sig_height:
            sig.thumbnail((max_sig_width, max_sig_height), Image.Resampling.LANCZOS)

        # User-chosen size multiplier, applied on top of the automatic sizing above.
        if user_scale != 1.0:
            sig = sig.resize(
                (max(1, int(round(sig.width * user_scale))), max(1, int(round(sig.height * user_scale)))),
                Image.Resampling.LANCZOS,
            )

        if rotate == 90:
            sig = sig.transpose(Image.Transpose.ROTATE_90)
        elif rotate == 180:
            sig = sig.transpose(Image.Transpose.ROTATE_180)
        elif rotate == 270:
            sig = sig.transpose(Image.Transpose.ROTATE_270)

        if img.mode != "RGBA":
            img = img.convert("RGBA")

        margin = int(round(short_side * margin_ratio)) if margin_ratio is not None else 10
        if position == "bottom-center":
            paste_x = (img.width - sig.width) // 2
            paste_y = img.height - sig.height - margin
        elif position == "left-center":
            paste_x = margin
            paste_y = (img.height - sig.height) // 2
        elif position == "bottom-left":
            paste_x = margin
            paste_y = img.height - sig.height - margin
        else:
            paste_x = img.width - sig.width - margin
            paste_y = img.height - sig.height - margin
        img.paste(sig, (paste_x, paste_y), sig)
        return img.convert("RGB") if img.mode == "RGBA" else img
    except Exception:
        logger.exception("Signature ignorée (%s)", signature_path)
        return img

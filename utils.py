#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageFilter, ImageOps

CONFIG_FILE_NAME = ".image_splitter_config.json"
# When frozen by PyInstaller (--onefile), __file__ lives in a temp extraction
# folder that's wiped on exit, so the config must live next to the executable.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
PROJECT_CONFIG_PATH = APP_DIR / CONFIG_FILE_NAME
LEGACY_CONFIG_PATH = Path.home() / CONFIG_FILE_NAME
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
DEFAULT_FRAME_RATIO = 0.04
DEFAULT_BORDER_COLOR = (255, 255, 255)
RATIO_TOLERANCE = 0.03
DEFAULT_LANDSCAPE_FILL_MODE = "black"
LANDSCAPE_FILL_MODES = {"black", "blur"}
LANDSCAPE_SIGNATURE_SIZE_FACTOR = 1.2
LANDSCAPE_SIGNATURE_MARGIN_RATIO = 0.03


def resolve_config_path() -> Path:
    if PROJECT_CONFIG_PATH.exists():
        return PROJECT_CONFIG_PATH
    if LEGACY_CONFIG_PATH.exists():
        try:
            LEGACY_CONFIG_PATH.replace(PROJECT_CONFIG_PATH)
        except Exception:
            pass
    return PROJECT_CONFIG_PATH


CONFIG_PATH = resolve_config_path()


def load_config(config_path: Path) -> dict:
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except Exception:
            return {}
    return {}


def save_config(config_path: Path, config: dict) -> None:
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(f"⚠️ Impossible de sauvegarder la configuration: {exc}")


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def detect_ratio_type(width: int, height: int) -> Optional[str]:
    ratio = width / height
    if abs(ratio - 3 / 4) / (3 / 4) <= RATIO_TOLERANCE:
        return "portrait_3_4"
    if abs(ratio - 2 / 3) / (2 / 3) <= RATIO_TOLERANCE:
        return "portrait_2_3"
    if abs(ratio - 3 / 2) / (3 / 2) <= RATIO_TOLERANCE:
        return "landscape_2_3"
    return None


def open_image(path: Path) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode not in {"RGB", "RGBA", "L"}:
        img = img.convert("RGB")
    return img


def frame_image(img: Image.Image, border_px: int, color=DEFAULT_BORDER_COLOR) -> Image.Image:
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


def save_image(img: Image.Image, output_path: Path) -> None:
    params = {}
    suffix = output_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        params = {"quality": 100, "subsampling": 0, "optimize": True}
    elif suffix == ".png":
        params = {"compress_level": 0}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, **params)


def portrait_3_4_output(img: Image.Image, output_path: Path, config: dict) -> List[Path]:
    border_px = max(1, int(round(min(img.size) * config.get("frame_ratio", DEFAULT_FRAME_RATIO))))
    framed = frame_image(img, border_px)
    save_image(framed, output_path)
    return [output_path]


def portrait_2_3_output(img: Image.Image, output_path: Path, config: dict) -> List[Path]:
    sig_path = config.get("signature_path")
    sig_path = Path(sig_path) if sig_path else None
    if config.get("landscape_fill_mode", DEFAULT_LANDSCAPE_FILL_MODE) == "blur":
        framed = create_portrait_with_landscape_blur_fill(
            img,
            sig_path,
            frame_ratio=config.get("frame_ratio", DEFAULT_FRAME_RATIO),
            signature_on_photo=True,
        )
        save_image(framed, output_path)
        return [output_path]

    signed = add_signature_to_image(img, sig_path)

    src_w, src_h = signed.size
    border_px = max(1, int(round(min(src_w, src_h) * config.get("frame_ratio", DEFAULT_FRAME_RATIO))))
    framed = frame_image(signed, border_px)

    min_width = framed.width
    min_height = framed.height

    # Place the framed 2/3 portrait onto a 3/4 portrait canvas
    if min_width * 4 >= min_height * 3:
        portrait_width = min_width
        portrait_height = int(round(portrait_width * 4 / 3))
    else:
        portrait_height = min_height
        portrait_width = int(round(portrait_height * 3 / 4))

    # Keep the final canvas at least as large as the framed image
    portrait_width = max(portrait_width, min_width)
    portrait_height = max(portrait_height, min_height)

    background = Image.new("RGB", (portrait_width, portrait_height), (0, 0, 0))
    x_offset = (portrait_width - framed.width) // 2
    y_offset = (portrait_height - framed.height) // 2
    background.paste(framed, (x_offset, y_offset))

    save_image(background, output_path)
    return [output_path]


def add_signature_to_image(
    img: Image.Image,
    signature_path: Optional[Path],
    position: str = "bottom-right",
    size_factor: float = 1.0,
    margin_ratio: Optional[float] = None,
    rotate: int = 0,
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
        else:
            paste_x = img.width - sig.width - margin
            paste_y = img.height - sig.height - margin
        img.paste(sig, (paste_x, paste_y), sig)
        return img.convert("RGB") if img.mode == "RGBA" else img
    except Exception:
        return img


def create_portrait_with_landscape_content(img: Image.Image, signature_path: Optional[Path], frame_ratio: float = DEFAULT_FRAME_RATIO) -> Image.Image:
    """
    Crée une image portrait 3/4 avec l'image paysage complète centrée, signée, encadrée et placée sur fond noir.
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Sign before scaling/framing so the signature stays anchored to the
    # photo's own corner (not the page corner), and scales/rotates with it.
    signed = add_signature_to_image(img, signature_path)
    src_w, src_h = signed.size
    border_px = max(1, int(round(min(src_w, src_h) * frame_ratio)))

    # determine 3/4 portrait size to fit the source image plus frame
    portrait_width = max(src_w + 2 * border_px, int(round((src_h + 2 * border_px) * 3 / 4)))
    portrait_height = int(round(portrait_width * 4 / 3))

    inner_w = portrait_width - 2 * border_px
    inner_h = portrait_height - 2 * border_px

    scaled_w = src_w
    scaled_h = src_h
    if src_w > inner_w or src_h > inner_h:
        scale = min(inner_w / src_w, inner_h / src_h)
        scaled_w = max(1, int(round(src_w * scale)))
        scaled_h = max(1, int(round(src_h * scale)))

    signed_scaled = signed.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    framed = frame_image(signed_scaled, border_px)

    background = Image.new("RGB", (portrait_width, portrait_height), (0, 0, 0))
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
) -> Image.Image:
    """
    Crée une image portrait 3/4 avec la photo nette étendue jusqu'aux bords (largeur
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
    target_ratio = 3 / 4
    if src_w / src_h >= target_ratio:
        content_width = src_w
        content_height = max(int(round(content_width * (4 + 2 * frame_ratio) / 3)), src_h)
    else:
        content_height = src_h
        content_width = max(int(round(content_height * 3 / (4 + 2 * frame_ratio))), src_w)

    # Cover-fit the (unsigned) photo over the content canvas, then blur it.
    scale = max(content_width / img.width, content_height / img.height)
    bg_w = max(content_width, int(round(img.width * scale)))
    bg_h = max(content_height, int(round(img.height * scale)))
    background = img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    crop_x = (bg_w - content_width) // 2
    crop_y = (bg_h - content_height) // 2
    background = background.crop((crop_x, crop_y, crop_x + content_width, crop_y + content_height))
    blur_radius = max(20, int(round(min(content_width, content_height) * 0.015)))
    background = background.filter(ImageFilter.GaussianBlur(blur_radius))

    x_offset = (content_width - src_w) // 2
    y_offset = (content_height - src_h) // 2
    # The blurred fill is built from the unsigned photo so no smeared copy of
    # the signature shows up in the margins.
    sharp = add_signature_to_image(img, signature_path) if signature_on_photo else img
    background.paste(sharp, (x_offset, y_offset))

    border_px = max(1, int(round(min(content_width, content_height) * frame_ratio)))
    framed = frame_image(background, border_px)
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
    )


def split_2_3_to_3_4(img: Image.Image, output_dir: Path, base_name: str, ext: str, config: dict) -> List[Path]:
    width, height = img.size
    frame_ratio = config.get("frame_ratio", DEFAULT_FRAME_RATIO)
    target_width = width // 2
    # Border thickness is based on the crop's own width (the short side),
    # same basis as every other 3/4 output in the app (frame_ratio * short
    # side) so the frame reads the same thickness everywhere.
    border_px = max(1, int(round(target_width * frame_ratio)))
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
    # apply frame on three sides: top, bottom and outer vertical edge only
    left_framed = frame_image_with_outer_edge(left_crop, border_px, "left")
    right_framed = frame_image_with_outer_edge(right_crop, border_px, "right")

    left_path = output_dir / f"{base_name}_part1{ext}"
    right_path = output_dir / f"{base_name}_part2{ext}"
    save_image(left_framed, left_path)
    save_image(right_framed, right_path)

    sig_path = config.get("signature_path")
    if sig_path:
        sig_path = Path(sig_path)
    else:
        sig_path = None

    fill_mode = config.get("landscape_fill_mode", DEFAULT_LANDSCAPE_FILL_MODE)

    if fill_mode == "blur":
        left_with_sig = create_portrait_with_landscape_blur_fill(img, sig_path, frame_ratio=frame_ratio)
        img_rotated = img.transpose(Image.Transpose.ROTATE_270)
        right_with_sig = create_portrait_with_landscape_blur_fill(
            img_rotated, sig_path, frame_ratio=frame_ratio, signature_rotation=270
        )
    else:
        left_with_sig = create_portrait_with_landscape_content(img, sig_path, frame_ratio=frame_ratio)
        # Sign the upright photo first, then rotate the signed result as one block
        # so the signature turns together with the photo instead of staying upright.
        signed_for_rotation = add_signature_to_image(img, sig_path)
        img_rotated = signed_for_rotation.transpose(Image.Transpose.ROTATE_270)
        right_with_sig = create_portrait_with_landscape_content(img_rotated, None, frame_ratio=frame_ratio)

    left_sig_path = output_dir / f"{base_name}_part1_with_sig{ext}"
    right_sig_path = output_dir / f"{base_name}_part2_with_sig{ext}"
    save_image(left_with_sig, left_sig_path)
    save_image(right_with_sig, right_sig_path)

    return [left_path, right_path, left_sig_path, right_sig_path]


def process_image(input_path: Path, output_dir: Path, config: dict) -> List[Path]:
    img = open_image(input_path)
    width, height = img.size
    ratio_type = detect_ratio_type(width, height)
    base_name = input_path.stem
    ext = input_path.suffix or ".jpg"
    output_files: List[Path] = []

    if ratio_type == "portrait_3_4":
        print(f"→ {input_path.name} : portrait 3/4 détecté")
        output_files = portrait_3_4_output(img, output_dir / f"{base_name}_framed{ext}", config)
    elif ratio_type == "portrait_2_3":
        print(f"→ {input_path.name} : portrait 2/3 détecté")
        if config.get("signature_path"):
            output_plugin = output_dir / f"{base_name}_with_sig{ext}"
        else:
            output_plugin = output_dir / f"{base_name}_framed{ext}"
        output_files = portrait_2_3_output(img, output_plugin, config)
    elif ratio_type == "landscape_2_3":
        print(f"→ {input_path.name} : paysage 2/3 détecté")
        output_files = split_2_3_to_3_4(img, output_dir, base_name, ext, config)
    else:
        print(f"⚠️ Ignoré : ratio non supporté pour {input_path.name} ({width}x{height})")

    return output_files


def gather_input_files(paths: List[str]) -> List[Path]:
    result: List[Path] = []
    for raw in paths:
        source = Path(raw).expanduser()
        if not source.exists():
            print(f"⚠️ Chemin introuvable : {raw}")
            continue
        if source.is_dir():
            for candidate in sorted(source.iterdir()):
                if candidate.is_file() and is_supported_image(candidate):
                    result.append(candidate)
        elif source.is_file():
            if is_supported_image(source):
                result.append(source)
            else:
                print(f"⚠️ Format non supporté : {source.name}")
        else:
            print(f"⚠️ Ignoré : {raw}")
    return result

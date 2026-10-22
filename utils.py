#!/usr/bin/env python3
import json
import logging
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Collection, Dict, Iterator, List, Optional, Sequence, Tuple

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
DEFAULT_BORDER_COLOR_HEX = "#FFFFFF"
DEFAULT_BACKGROUND_COLOR = (0, 0, 0)
DEFAULT_BACKGROUND_COLOR_HEX = "#000000"
OPTIONAL_KINDS = ("part1", "part2", "part1_with_sig", "part2_with_sig")
KIND_CROP = "crop34"  # recadrage 3/4 d'un portrait 2/3
DEFAULT_CROP_OFFSET = 0.5
DEFAULT_BLUR_STRENGTH = 1.0
DEFAULT_JPEG_QUALITY = 100
DEFAULT_SIGNATURE_POSITION = "bottom-right"
SIGNATURE_POSITIONS = ("bottom-right", "bottom-center", "bottom-left")
DEFAULT_SIGNATURE_SCALE = 1.0
DEFAULT_NUMBER_FILES = True
PATH_CONFIG_KEYS = ("last_source_dir", "last_dest_dir", "signature_path")
LOG_FILE_NAME = "image_splitter.log"
LOG_PATH = APP_DIR / LOG_FILE_NAME
GDRIVE_TOKEN_PATH = APP_DIR / "gdrive_token.json"  # jeton Google Drive, à côté de l'exécutable

logger = logging.getLogger("imagesplitter")


def say(message: str) -> None:
    """print() qui ne plante jamais : consoles Windows en cp1252 (→, ⚠️ non encodables) ou sans console (exe fenêtré)."""
    try:
        print(message)
    except Exception:
        pass


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


_WSL_PATH = re.compile(r"^/mnt/([a-zA-Z])(?:/(.*))?$")
_WIN_PATH = re.compile(r"^([a-zA-Z]):[\\/]*(.*)$")


def normalize_path(value: str) -> str:
    """Convertit un chemin WSL (/mnt/c/...) en chemin Windows (C:/...) et inversement,
    selon le système courant, pour qu'une config écrite d'un côté reste valable de l'autre."""
    if not value or not isinstance(value, str):
        return value
    if os.name == "nt":
        match = _WSL_PATH.match(value)
        if match:
            return f"{match.group(1).upper()}:/{match.group(2) or ''}"
    else:
        match = _WIN_PATH.match(value)
        if match:
            return f"/mnt/{match.group(1).lower()}/{match.group(2).replace(chr(92), '/')}"
    return value


def load_config(config_path: Path) -> dict:
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if isinstance(config, dict):
            for key in PATH_CONFIG_KEYS:
                if key in config:
                    config[key] = normalize_path(config[key])
            return config
    return {}


def save_config(config_path: Path, config: dict) -> None:
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        logger.warning("Impossible de sauvegarder la configuration: %s", exc)


def parse_color(value, default=DEFAULT_BORDER_COLOR) -> Tuple[int, int, int]:
    """Accepte '#RRGGBB' / 'RRGGBB' ou un triplet RGB ; renvoie `default` si invalide."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return tuple(max(0, min(255, int(v))) for v in value)  # type: ignore[return-value]
        except (TypeError, ValueError):
            return default
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) == 3:
            text = "".join(ch * 2 for ch in text)
        if len(text) == 6:
            try:
                return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
            except ValueError:
                return default
    return default


def _number(config: dict, key: str, default: float, low: float, high: float) -> float:
    try:
        value = float(config.get(key, default))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def border_color_of(config: dict) -> Tuple[int, int, int]:
    return parse_color(config.get("border_color"), DEFAULT_BORDER_COLOR)


def background_color_of(config: dict) -> Tuple[int, int, int]:
    """Couleur du fond uni (quand le fond flouté n'est pas choisi)."""
    return parse_color(config.get("background_color"), DEFAULT_BACKGROUND_COLOR)


def disabled_kinds_of(config: dict) -> set:
    value = config.get("disabled_kinds") or []
    return {str(kind) for kind in value} if isinstance(value, (list, tuple, set)) else set()


def frame_ratio_of(config: dict) -> float:
    """Épaisseur du cadre en fraction du plus petit côté ; 0 si l'utilisateur ne veut pas de cadre."""
    if config.get("frame_enabled", True) is False:
        return 0.0
    try:
        return max(0.0, float(config.get("frame_ratio", DEFAULT_FRAME_RATIO)))
    except (TypeError, ValueError):
        return DEFAULT_FRAME_RATIO


def border_px_for(side: float, frame_ratio: float) -> int:
    """Épaisseur du cadre en pixels : 0 sans cadre, sinon au moins 1 px."""
    return 0 if frame_ratio <= 0 else max(1, int(round(side * frame_ratio)))


def crop_offset_for(config: dict, path) -> float:
    """Position verticale (0 = haut, 1 = bas) du recadrage 3/4 choisi pour cette photo."""
    offsets = config.get("crop_offsets") or {}
    try:
        value = float(offsets.get(str(path), DEFAULT_CROP_OFFSET))
    except (TypeError, ValueError, AttributeError):
        return DEFAULT_CROP_OFFSET
    return max(0.0, min(1.0, value))


def crop_height_for(width: int, height: int, frame_ratio: float) -> int:
    """Hauteur de la zone conservée pour que, une fois encadrée, l'image soit exactement en 3/4.
    L'épaisseur du cadre suit la règle des autres sorties : frame_ratio × plus petit côté (la largeur)."""
    border = border_px_for(width, frame_ratio)
    return min(height, int(round((4 * width + 2 * border) / 3)))


def blur_strength_of(config: dict) -> float:
    return _number(config, "blur_strength", DEFAULT_BLUR_STRENGTH, 0.2, 5.0)


def jpeg_quality_of(config: dict) -> int:
    return int(_number(config, "jpeg_quality", DEFAULT_JPEG_QUALITY, 50, 100))


def signature_scale_of(config: dict) -> float:
    return _number(config, "signature_scale", DEFAULT_SIGNATURE_SCALE, 0.3, 3.0)


def signature_position_of(config: dict) -> str:
    position = config.get("signature_position", DEFAULT_SIGNATURE_POSITION)
    return position if position in SIGNATURE_POSITIONS else DEFAULT_SIGNATURE_POSITION


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


def render_portrait_3_4(img: Image.Image, config: dict) -> Image.Image:
    border_px = border_px_for(min(img.size), frame_ratio_of(config))
    return frame_image(img, border_px, border_color_of(config))


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
        )

    signed = add_signature_to_image(img, sig_path, position=position, user_scale=sig_scale)

    src_w, src_h = signed.size
    border_px = border_px_for(min(src_w, src_h), frame_ratio_of(config))
    framed = frame_image(signed, border_px, color)

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

    background = Image.new("RGB", (portrait_width, portrait_height), background_color_of(config))
    x_offset = (portrait_width - framed.width) // 2
    y_offset = (portrait_height - framed.height) // 2
    background.paste(framed, (x_offset, y_offset))
    return background


def render_crop_3_4(img: Image.Image, config: dict, offset: float = DEFAULT_CROP_OFFSET) -> Image.Image:
    """Recadre un portrait 2/3 en 3/4 (largeur complète, hauteur réduite, position verticale `offset`)
    puis l'encadre : le résultat est un portrait 3/4 prêt pour Instagram. Pas de signature : seules les
    photos portrait d'origine sont signées, pas les images redimensionnées."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    frame_ratio = frame_ratio_of(config)
    width, height = img.size
    border = border_px_for(width, frame_ratio)
    crop_h = crop_height_for(width, height, frame_ratio)
    top = int(round((height - crop_h) * max(0.0, min(1.0, offset))))
    cropped = img.crop((0, top, width, top + crop_h))
    return frame_image(cropped, border, border_color_of(config))


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


def create_portrait_with_landscape_content(
    img: Image.Image,
    signature_path: Optional[Path],
    frame_ratio: float = DEFAULT_FRAME_RATIO,
    border_color=DEFAULT_BORDER_COLOR,
    sig_position: str = DEFAULT_SIGNATURE_POSITION,
    sig_scale: float = DEFAULT_SIGNATURE_SCALE,
    background_color=DEFAULT_BACKGROUND_COLOR,
) -> Image.Image:
    """
    Crée une image portrait 3/4 avec l'image paysage complète centrée, signée, encadrée et placée sur fond uni (noir par défaut).
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Sign before scaling/framing so the signature stays anchored to the
    # photo's own corner (not the page corner), and scales/rotates with it.
    signed = add_signature_to_image(img, signature_path, position=sig_position, user_scale=sig_scale)
    src_w, src_h = signed.size
    border_px = border_px_for(min(src_w, src_h), frame_ratio)

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

    sig_path = config.get("signature_path")
    sig_path = Path(sig_path) if sig_path else None
    position = signature_position_of(config)
    sig_scale = signature_scale_of(config)
    fill_mode = config.get("landscape_fill_mode", DEFAULT_LANDSCAPE_FILL_MODE)

    blur = blur_strength_of(config)
    bg = background_color_of(config)

    if "part1_with_sig" in wanted:
        if fill_mode == "blur":
            yield "part1_with_sig", create_portrait_with_landscape_blur_fill(
                img, sig_path, frame_ratio=frame_ratio, border_color=color, blur_strength=blur, sig_scale=sig_scale
            )
        else:
            yield "part1_with_sig", create_portrait_with_landscape_content(
                img, sig_path, frame_ratio=frame_ratio, border_color=color, sig_position=position,
                sig_scale=sig_scale, background_color=bg,
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
            )
        else:
            # Sign the upright photo first, then rotate the signed result as one block
            # so the signature turns together with the photo instead of staying upright.
            signed_for_rotation = add_signature_to_image(img, sig_path, position=position, user_scale=sig_scale)
            img_rotated = signed_for_rotation.transpose(Image.Transpose.ROTATE_270)
            yield "part2_with_sig", create_portrait_with_landscape_content(
                img_rotated, None, frame_ratio=frame_ratio, border_color=color, background_color=bg
            )


def kinds_for_ratio(ratio_type: Optional[str], config: dict) -> List[str]:
    """Types de sorties produites pour un ratio donné (sans rien calculer), hors types désactivés."""
    if ratio_type == "portrait_3_4":
        return ["framed"]
    if ratio_type == "portrait_2_3":
        kinds = ["with_sig" if config.get("signature_path") else "framed"]
        if KIND_CROP not in disabled_kinds_of(config):
            kinds.append(KIND_CROP)
        return kinds
    if ratio_type == "landscape_2_3":
        disabled = disabled_kinds_of(config)
        return [kind for kind in OPTIONAL_KINDS if kind not in disabled]
    return []


def iter_outputs(
    img: Image.Image,
    config: dict,
    only: Optional[Collection[str]] = None,
    crop_offset: float = DEFAULT_CROP_OFFSET,
) -> Iterator[Tuple[str, Image.Image]]:
    """Génère (kind, image) pour une image déjà ouverte, sans rien écrire sur disque.
    `only` limite aux types demandés (les autres ne sont pas calculés) ; par défaut, tous les types actifs."""
    ratio_type = detect_ratio_type(*img.size)
    wanted = [k for k in kinds_for_ratio(ratio_type, config) if only is None or k in only]
    if not wanted:
        return
    if ratio_type == "portrait_3_4":
        yield "framed", render_portrait_3_4(img, config)
    elif ratio_type == "portrait_2_3":
        for kind in wanted:
            if kind == KIND_CROP:
                yield kind, render_crop_3_4(img, config, crop_offset)
            else:
                yield kind, render_portrait_2_3(img, config)
    elif ratio_type == "landscape_2_3":
        yield from iter_split_2_3_to_3_4(img, config, only=wanted)


def peek_ratio_type(path: Path) -> Optional[str]:
    """Détecte le type de ratio en ne lisant que l'en-tête de l'image (orientation EXIF comprise)."""
    with Image.open(path) as img:
        width, height = img.size
        try:
            orientation = img.getexif().get(0x0112, 1)
        except Exception:
            orientation = 1
    if orientation in (5, 6, 7, 8):
        width, height = height, width
    return detect_ratio_type(width, height)


def item_key(source: Path, kind: str) -> str:
    return f"{source}|{kind}"


def output_name(source: Path, kind: str, prefix: str = "") -> str:
    return f"{prefix}{source.stem}_{kind}{source.suffix or '.jpg'}"


def planned_items(files: Sequence[Path], config: dict) -> List[Tuple[Path, str]]:
    """Liste à plat (source, kind) de toutes les images de sortie prévues, dans l'ordre naturel."""
    items: List[Tuple[Path, str]] = []
    for path in files:
        try:
            ratio_type = peek_ratio_type(path)
        except Exception:
            logger.exception("Lecture impossible : %s", path)
            continue
        for kind in kinds_for_ratio(ratio_type, config):
            items.append((path, kind))
    return items


def merge_order(order: Sequence[str], items: Sequence[Tuple[Path, str]]) -> List[str]:
    """Ordre final des clés : l'ordre choisi par l'utilisateur d'abord (sans les éléments disparus),
    puis les nouveaux éléments à la suite dans l'ordre naturel."""
    available = [item_key(path, kind) for path, kind in items]
    available_set = set(available)
    merged = [key for key in order if key in available_set]
    seen = set(merged)
    merged.extend(key for key in available if key not in seen)
    return merged


def build_prefixes(ordered_keys: Sequence[str]) -> Dict[str, str]:
    width = max(2, len(str(len(ordered_keys))))
    return {key: f"{index:0{width}d}_" for index, key in enumerate(ordered_keys, start=1)}


def render_outputs(path: Path, config: dict, max_side: Optional[int] = None) -> List[Tuple[str, Image.Image]]:
    """Rend toutes les sorties d'une photo en mémoire. `max_side` réduit la source (aperçus rapides)."""
    img = open_image(path)
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return list(iter_outputs(img, config, crop_offset=crop_offset_for(config, path)))


def render_output(path: Path, config: dict, kind: str, max_side: Optional[int] = None) -> Optional[Image.Image]:
    """Rend une seule sortie (pleine résolution par défaut), ou None si ce type n'existe pas pour cette photo."""
    img = open_image(path)
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    for found, out in iter_outputs(img, config, only={kind}, crop_offset=crop_offset_for(config, path)):
        if found == kind:
            return out
    return None


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


def process_image(
    input_path: Path,
    output_dir: Path,
    config: dict,
    prefixes: Optional[Dict[str, str]] = None,
    excluded: Optional[Collection[str]] = None,
) -> List[Path]:
    img = open_image(input_path)
    width, height = img.size
    ratio_type = detect_ratio_type(width, height)
    labels = {
        "portrait_3_4": "portrait 3/4",
        "portrait_2_3": "portrait 2/3",
        "landscape_2_3": "paysage 2/3",
    }
    if ratio_type is None:
        say(f"⚠️ Ignoré : ratio non supporté pour {input_path.name} ({width}x{height})")
        return []
    say(f"→ {input_path.name} : {labels[ratio_type]} détecté")

    quality = jpeg_quality_of(config)
    output_files: List[Path] = []
    wanted = [k for k in kinds_for_ratio(ratio_type, config) if item_key(input_path, k) not in (excluded or ())]
    for kind, out_img in iter_outputs(img, config, only=wanted, crop_offset=crop_offset_for(config, input_path)):
        prefix = (prefixes or {}).get(item_key(input_path, kind), "")
        out_path = output_dir / output_name(input_path, kind, prefix)
        save_image(out_img, out_path, quality)
        output_files.append(out_path)
    return output_files


@dataclass
class FileResult:
    path: Path
    status: str  # "ok" | "skipped" | "excluded" | "error" | "cancelled"
    outputs: List[Path] = field(default_factory=list)
    message: str = ""


def process_batch(
    files: Sequence[Path],
    output_dir: Path,
    config: dict,
    order: Optional[Sequence[str]] = None,
    number_files: bool = False,
    progress: Optional[Callable[[int, int, Path], None]] = None,
    cancel: Optional[threading.Event] = None,
    workers: int = 1,
    excluded: Optional[Collection[str]] = None,
) -> List[FileResult]:
    """Traite un lot de photos. Si `number_files`, chaque sortie reçoit un préfixe 01_, 02_… selon
    `order` (liste de clés item_key ; les éléments absents suivent dans l'ordre naturel).
    `excluded` : clés item_key des images de sortie à ne pas produire (elles ne sont pas numérotées)."""
    excluded = set(excluded or ())
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefixes = None
    if number_files:
        items = [item for item in planned_items(files, config) if item_key(*item) not in excluded]
        prefixes = build_prefixes(merge_order(order or [], items))

    total = len(files)
    results: Dict[Path, FileResult] = {}
    lock = threading.Lock()
    done = 0

    def work(path: Path) -> FileResult:
        if cancel is not None and cancel.is_set():
            return FileResult(path, "cancelled")
        try:
            outputs = process_image(path, output_dir, config, prefixes, excluded)
        except Exception as exc:
            logger.exception("Erreur sur %s", path)
            return FileResult(path, "error", message=str(exc) or exc.__class__.__name__)
        if not outputs:
            if any(key.startswith(f"{path}|") for key in excluded):
                return FileResult(path, "excluded", message="toutes les images exclues")
            return FileResult(path, "skipped", message="ratio non supporté")
        return FileResult(path, "ok", outputs)

    def finished(result: FileResult) -> None:
        nonlocal done
        with lock:
            results[result.path] = result
            done += 1
            count = done
        if progress is not None:
            progress(count, total, result.path)

    workers = max(1, min(workers, total or 1))
    if workers == 1:
        for path in files:
            finished(work(path))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(work, path) for path in files]
            for future in as_completed(futures):
                finished(future.result())

    return [results[path] for path in files if path in results]


def gather_input_files(paths: List[str]) -> List[Path]:
    result: List[Path] = []
    for raw in paths:
        source = Path(raw).expanduser()
        if not source.exists():
            say(f"⚠️ Chemin introuvable : {raw}")
            continue
        if source.is_dir():
            for candidate in sorted(source.iterdir()):
                if candidate.is_file() and is_supported_image(candidate):
                    result.append(candidate)
        elif source.is_file():
            if is_supported_image(source):
                result.append(source)
            else:
                say(f"⚠️ Format non supporté : {source.name}")
        else:
            say(f"⚠️ Ignoré : {raw}")
    return result

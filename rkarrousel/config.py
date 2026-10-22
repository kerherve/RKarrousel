"""Réglages : lecture/écriture du fichier JSON, valeurs par défaut et accesseurs qui valident chaque réglage."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Tuple

logger = logging.getLogger("imagesplitter")


DEFAULT_FRAME_RATIO = 0.04
DEFAULT_BORDER_COLOR = (255, 255, 255)
DEFAULT_LANDSCAPE_FILL_MODE = "black"
LANDSCAPE_FILL_MODES = {"black", "blur"}
DEFAULT_BORDER_COLOR_HEX = "#FFFFFF"
DEFAULT_BACKGROUND_COLOR = (0, 0, 0)
DEFAULT_BACKGROUND_COLOR_HEX = "#000000"
DEFAULT_CROP_OFFSET = 0.5
DEFAULT_BLUR_STRENGTH = 1.0
DEFAULT_JPEG_QUALITY = 100
DEFAULT_SIGNATURE_POSITION = "bottom-right"
SIGNATURE_POSITIONS = ("bottom-right", "bottom-center", "bottom-left")
DEFAULT_SIGNATURE_SCALE = 1.0
DEFAULT_NUMBER_FILES = True
PATH_CONFIG_KEYS = ("last_source_dir", "last_dest_dir", "signature_path")
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


def crop_offset_for(config: dict, path) -> float:
    """Position verticale (0 = haut, 1 = bas) du recadrage 3/4 choisi pour cette photo."""
    offsets = config.get("crop_offsets") or {}
    try:
        value = float(offsets.get(str(path), DEFAULT_CROP_OFFSET))
    except (TypeError, ValueError, AttributeError):
        return DEFAULT_CROP_OFFSET
    return max(0.0, min(1.0, value))


def blur_strength_of(config: dict) -> float:
    return _number(config, "blur_strength", DEFAULT_BLUR_STRENGTH, 0.2, 5.0)


def jpeg_quality_of(config: dict) -> int:
    return int(_number(config, "jpeg_quality", DEFAULT_JPEG_QUALITY, 50, 100))


def signature_scale_of(config: dict) -> float:
    return _number(config, "signature_scale", DEFAULT_SIGNATURE_SCALE, 0.3, 3.0)


def signature_position_of(config: dict) -> str:
    position = config.get("signature_position", DEFAULT_SIGNATURE_POSITION)
    return position if position in SIGNATURE_POSITIONS else DEFAULT_SIGNATURE_POSITION

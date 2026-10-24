"""Préréglages nommés : jeux de réglages d'apparence que l'on enregistre et rappelle d'un clic.

Un préréglage ne contient que le « look » (cadre, fond, signature, format, taille) : ni la langue, ni le thème,
ni les dossiers, ni les réglages Google Drive ou de mise à jour. Les préréglages fournis (`builtin`) ne modifient que
les réglages qu'ils citent ; ceux de l'utilisateur sont stockés dans la config, sous la clé `presets`.
"""
import copy
from dataclasses import dataclass
from typing import Dict, List, Optional

PRESET_KEYS = (
    "frame_enabled", "frame_ratio", "border_color", "border_color_mode", "color_source",
    "landscape_fill_mode", "background_color", "background_color_mode", "blur_strength",
    "signature_path", "signature_position", "signature_scale",
    "output_format", "output_width", "jpeg_quality", "disabled_kinds", "kind_placement",
)
MAX_NAME_LENGTH = 40

BUILTIN_VALUES = {
    "classic": {
        "frame_enabled": True, "frame_ratio": 0.02, "border_color": "#FFFFFF", "border_color_mode": "fixed",
        "landscape_fill_mode": "blur", "blur_strength": 1.0,
    },
    "dark": {
        "frame_enabled": True, "frame_ratio": 0.015, "border_color": "#FFFFFF", "border_color_mode": "fixed",
        "landscape_fill_mode": "black", "background_color": "#000000", "background_color_mode": "fixed",
    },
    "photo_color": {
        "frame_enabled": True, "frame_ratio": 0.03, "border_color_mode": "light",
        "landscape_fill_mode": "black", "background_color_mode": "dark",
    },
    "no_frame": {"frame_enabled": False, "landscape_fill_mode": "blur"},
}


@dataclass(frozen=True)
class Preset:
    id: str                 # clé de traduction pour un préréglage fourni, nom choisi pour celui de l'utilisateur
    values: Dict[str, object]
    builtin: bool = False


def builtin_presets() -> List[Preset]:
    return [Preset(key, copy.deepcopy(values), builtin=True) for key, values in BUILTIN_VALUES.items()]


def user_presets(config: dict) -> List[Preset]:
    stored = config.get("presets") or {}
    return [Preset(name, copy.deepcopy(values)) for name, values in sorted(stored.items(), key=lambda kv: kv[0].lower())
            if isinstance(values, dict)]


def all_presets(config: dict) -> List[Preset]:
    return builtin_presets() + user_presets(config)


def extract(config: dict) -> Dict[str, object]:
    """Les réglages d'apparence de `config`, prêts à être enregistrés dans un préréglage."""
    return {key: copy.deepcopy(config[key]) for key in PRESET_KEYS if key in config}


def clean_name(name: str) -> str:
    cleaned = " ".join((name or "").split())[:MAX_NAME_LENGTH]
    if not cleaned:
        raise ValueError("Le nom d'un préréglage ne peut pas être vide.")
    return cleaned


def save_user_preset(config: dict, name: str, values: Dict[str, object]) -> str:
    """Enregistre (ou remplace) un préréglage de l'utilisateur ; renvoie le nom retenu."""
    name = clean_name(name)
    config.setdefault("presets", {})[name] = {key: copy.deepcopy(values[key]) for key in PRESET_KEYS if key in values}
    return name


def delete_user_preset(config: dict, name: str) -> bool:
    return (config.get("presets") or {}).pop(name, None) is not None


def _same(a: object, b: object) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) < 1e-6
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return sorted(map(str, a)) == sorted(map(str, b))
    return a == b


def find_matching(config: dict) -> Optional[Preset]:
    """Le préréglage dont tous les réglages sont ceux de `config` (celui de l'utilisateur d'abord), s'il y en a un."""
    for preset in user_presets(config) + builtin_presets():
        if all(key in config and _same(config[key], value) for key, value in preset.values.items()):
            return preset
    return None

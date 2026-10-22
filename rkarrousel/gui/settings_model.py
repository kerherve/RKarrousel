"""Modèle des réglages : variables Tk liées aux champs de l'interface, lues depuis la config et réécrites dedans."""
import tkinter as tk
from typing import Dict

from rkarrousel import i18n
from rkarrousel.config import (
    COLOR_MODES,
    DEFAULT_BACKGROUND_COLOR_HEX,
    DEFAULT_BLUR_STRENGTH,
    DEFAULT_BORDER_COLOR_HEX,
    DEFAULT_FRAME_RATIO,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_LANDSCAPE_FILL_MODE,
    DEFAULT_NUMBER_FILES,
    DEFAULT_SIGNATURE_POSITION,
    DEFAULT_SIGNATURE_SCALE,
    disabled_kinds_of,
)
from rkarrousel.formats import OUTPUT_FORMATS
from rkarrousel.kinds import KIND_CROP, OPTIONAL_KINDS

ALL_KINDS = OPTIONAL_KINDS + (KIND_CROP,)


def var_value(var: tk.Variable, default):
    """Lit une variable Tk saisie à la main (Spinbox) sans planter si le champ est vide ou invalide."""
    try:
        return var.get()
    except (tk.TclError, ValueError):
        return default


class SettingsModel:
    """Toutes les variables de réglages. `collect(config)` les recopie dans la config (valeurs invalides → défaut)."""

    def __init__(self, cfg: dict):
        self.source_dir = tk.StringVar(value=cfg.get("last_source_dir", ""))
        self.dest_dir = tk.StringVar(value=cfg.get("last_dest_dir", "output"))
        self.number_files = tk.BooleanVar(value=cfg.get("number_files", DEFAULT_NUMBER_FILES))
        # épaisseur affichée en pourcentage du plus petit côté (1 = 1 %) ; stockée en ratio (0.01) dans la config
        self.frame_percent = tk.DoubleVar(value=round(float(cfg.get("frame_ratio", DEFAULT_FRAME_RATIO)) * 100, 2))
        self.no_frame = tk.BooleanVar(value=cfg.get("frame_enabled", True) is False)
        self.border_color = tk.StringVar(value=cfg.get("border_color", DEFAULT_BORDER_COLOR_HEX))
        self.border_color_mode = tk.StringVar(value=cfg.get("border_color_mode", "fixed"))
        self.landscape_fill_mode = tk.StringVar(value=cfg.get("landscape_fill_mode", DEFAULT_LANDSCAPE_FILL_MODE))
        self.background_color = tk.StringVar(value=cfg.get("background_color", DEFAULT_BACKGROUND_COLOR_HEX))
        self.background_color_mode = tk.StringVar(value=cfg.get("background_color_mode", "fixed"))
        self.blur_strength = tk.DoubleVar(value=cfg.get("blur_strength", DEFAULT_BLUR_STRENGTH))
        self.signature_path = tk.StringVar(value=cfg.get("signature_path", ""))
        self.signature_position = tk.StringVar(value=cfg.get("signature_position", DEFAULT_SIGNATURE_POSITION))
        self.signature_scale = tk.DoubleVar(value=cfg.get("signature_scale", DEFAULT_SIGNATURE_SCALE))
        self.jpeg_quality = tk.IntVar(value=cfg.get("jpeg_quality", DEFAULT_JPEG_QUALITY))
        self.output_format = tk.StringVar(value=cfg.get("output_format", "3:4"))
        self.output_width = tk.IntVar(value=int(cfg.get("output_width", 0) or 0))
        disabled = disabled_kinds_of(cfg)
        self.kind_vars: Dict[str, tk.BooleanVar] = {kind: tk.BooleanVar(value=kind not in disabled) for kind in ALL_KINDS}
        self.gdrive_enabled = tk.BooleanVar(value=bool(cfg.get("gdrive_enabled", False)))
        self.gdrive_folder = tk.StringVar(value=cfg.get("gdrive_folder", "RKarrousel"))
        self.update_check = tk.BooleanVar(value=bool(cfg.get("update_check", True)))

    @staticmethod
    def _mode(var: tk.StringVar) -> str:
        return var.get() if var.get() in COLOR_MODES else "fixed"

    def apply(self, values: dict) -> None:
        """Applique un préréglage (ou toute série de réglages) aux champs de l'écran : seules les clés citées changent."""
        text_vars = {
            "border_color": self.border_color, "border_color_mode": self.border_color_mode,
            "landscape_fill_mode": self.landscape_fill_mode, "background_color": self.background_color,
            "background_color_mode": self.background_color_mode, "signature_path": self.signature_path,
            "signature_position": self.signature_position, "output_format": self.output_format,
        }
        for key, var in text_vars.items():
            if key in values:
                var.set(str(values[key]))
        converters = (
            ("frame_ratio", self.frame_percent, lambda v: round(float(v) * 100, 2)),
            ("blur_strength", self.blur_strength, float),
            ("signature_scale", self.signature_scale, float),
            ("jpeg_quality", self.jpeg_quality, int),
            ("output_width", self.output_width, int),
        )
        for key, var, convert in converters:
            if key in values:
                try:
                    var.set(convert(values[key]))
                except (TypeError, ValueError):
                    pass  # valeur illisible : on garde le réglage actuel
        if "frame_enabled" in values:
            self.no_frame.set(values["frame_enabled"] is False)
        if "disabled_kinds" in values:
            disabled = {str(kind) for kind in values["disabled_kinds"] or ()}
            for kind, var in self.kind_vars.items():
                var.set(kind not in disabled)

    def collect(self, cfg: dict) -> dict:
        """Recopie les réglages de l'écran dans `cfg` et renvoie `cfg`."""
        cfg["last_source_dir"] = self.source_dir.get()
        cfg["last_dest_dir"] = self.dest_dir.get()
        cfg["frame_enabled"] = not self.no_frame.get()
        cfg["frame_ratio"] = round(
            max(0.001, min(0.2, var_value(self.frame_percent, DEFAULT_FRAME_RATIO * 100) / 100)), 6
        )
        cfg["landscape_fill_mode"] = self.landscape_fill_mode.get()
        cfg["signature_path"] = self.signature_path.get()
        cfg["number_files"] = bool(self.number_files.get())
        cfg["border_color"] = self.border_color.get()
        cfg["border_color_mode"] = self._mode(self.border_color_mode)
        cfg["background_color"] = self.background_color.get()
        cfg["background_color_mode"] = self._mode(self.background_color_mode)
        cfg["disabled_kinds"] = [kind for kind, var in self.kind_vars.items() if not var.get()]
        cfg["blur_strength"] = var_value(self.blur_strength, DEFAULT_BLUR_STRENGTH)
        cfg["jpeg_quality"] = var_value(self.jpeg_quality, DEFAULT_JPEG_QUALITY)
        cfg["output_format"] = self.output_format.get() if self.output_format.get() in OUTPUT_FORMATS else "3:4"
        cfg["output_width"] = int(var_value(self.output_width, 0) or 0)
        cfg["signature_position"] = self.signature_position.get()
        cfg["signature_scale"] = var_value(self.signature_scale, DEFAULT_SIGNATURE_SCALE)
        cfg["update_check"] = bool(self.update_check.get())
        cfg.pop("last_update_check", None)  # ancien réglage : la vérification a lieu à chaque démarrage
        cfg.pop("github_token", None)  # ancien réglage supprimé : on n'en garde aucune trace dans la config
        cfg["gdrive_enabled"] = bool(self.gdrive_enabled.get())
        cfg["gdrive_folder"] = self.gdrive_folder.get().strip() or "RKarrousel"
        cfg["language"] = i18n.get_language()
        cfg.setdefault("theme", "auto")
        return cfg

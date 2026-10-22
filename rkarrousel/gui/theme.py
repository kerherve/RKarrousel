"""Apparence : thème clair/sombre, styles, échelle d'écran et placement de la fenêtre principale."""
import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from rkarrousel.gui.system import sv_ttk, system_prefers_dark

logger = logging.getLogger("imagesplitter")

THEME_CHOICES = ("auto", "light", "dark")


@dataclass
class Theme:
    dark: bool
    scale: float            # échelle d'écran Windows (1.0, 1.25, 1.5…)
    accent_style: str       # style du bouton principal

    def surface_color(self) -> str:
        return ttk.Style().lookup("TFrame", "background") or ("#1c1c1c" if self.dark else "#fafafa")


def apply_theme(choice: str, root: tk.Misc) -> Theme:
    """Applique le thème (`auto` suit Windows) et les styles de l'appli ; renvoie les paramètres d'affichage."""
    dark = system_prefers_dark() if choice == "auto" else choice == "dark"
    if sv_ttk is not None:
        try:
            sv_ttk.set_theme("dark" if dark else "light")
        except Exception:
            logger.exception("Thème indisponible")
    style = ttk.Style()
    style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
    style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#8a8a8a")
    style.configure("Hint.TLabel", font=("Segoe UI", 9), foreground="#8a8a8a")
    scale = max(1.0, root.winfo_fpixels("1i") / 96)
    return Theme(dark=dark, scale=scale, accent_style="Accent.TButton" if sv_ttk is not None else "TButton")


def place_main_window(root: tk.Misc, scale: float) -> None:
    """Taille adaptée à l'écran (échelle Windows comprise) et fenêtre centrée, barre des tâches exclue."""
    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    width = min(int(1120 * scale), screen_w - 40)
    height = min(int(760 * scale), screen_h - 140)
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2 - 30)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(min(int(980 * scale), width), min(int(600 * scale), height))

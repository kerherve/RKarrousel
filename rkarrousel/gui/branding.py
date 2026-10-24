"""Le logo de l'appli : icône des fenêtres et image de l'en-tête (fichiers de `rkarrousel/assets/`, voir
`tools/make_logo.py`). Tout est facultatif : sans les fichiers, l'appli s'affiche simplement sans logo."""
import logging
import os
import tkinter as tk
from pathlib import Path
from typing import Optional

from PIL import Image, ImageTk

logger = logging.getLogger("imagesplitter")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"  # dans l'exécutable : rkarrousel/assets (voir build_windows.bat)
ICON_PATH = ASSETS_DIR / "icon.ico"
LOGO_256 = ASSETS_DIR / "logo_256.png"
LOGO_64 = ASSETS_DIR / "logo_64.png"


def apply_window_icon(root: tk.Tk) -> None:
    """Remplace la plume de Tk par le logo, pour la fenêtre principale et toutes les fenêtres secondaires."""
    try:
        if os.name == "nt" and ICON_PATH.exists():
            root.iconbitmap(default=str(ICON_PATH))
        elif LOGO_64.exists():
            root._icon_photo = tk.PhotoImage(master=root, file=str(LOGO_64))  # la référence évite que l'image soit libérée
            root.iconphoto(True, root._icon_photo)
    except tk.TclError:
        logger.exception("Icône de fenêtre indisponible")


def header_logo(master: tk.Misc, height: int) -> Optional[ImageTk.PhotoImage]:
    """Le logo à `height` pixels de haut, pour l'en-tête (None si le fichier manque)."""
    try:
        with Image.open(LOGO_256) as image:
            return ImageTk.PhotoImage(image.resize((height, height), Image.Resampling.LANCZOS), master=master)
    except OSError:
        return None

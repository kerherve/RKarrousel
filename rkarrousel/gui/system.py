"""Environnement d'exécution de l'interface : dépendances optionnelles, journal, DPI et fenêtre racine."""
import logging
import os
import sys
import tkinter as tk
from logging.handlers import RotatingFileHandler

from rkarrousel.paths import LOG_PATH
from rkarrousel.services import updater

# Le glisser-déposer de fichiers est optionnel : sans `tkinterdnd2`, l'appli fonctionne comme avant.
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # pragma: no cover - dépend de l'installation
    DND_FILES = None
    TkinterDnD = None

# Thème moderne (Sun Valley) optionnel : sans `sv_ttk`, l'appli garde le thème Tk de base.
try:
    import sv_ttk
except Exception:  # pragma: no cover - dépend de l'installation
    sv_ttk = None

logger = logging.getLogger("imagesplitter")

FROZEN = bool(getattr(sys, "frozen", False))  # exécutable PyInstaller : seul cas où on peut se remplacer soi-même
UPDATE_REPO = os.environ.get("RKARROUSEL_UPDATE_REPO", updater.REPO)  # surcharges pour les tests
UPDATE_API = os.environ.get("RKARROUSEL_UPDATE_API", updater.API_URL)


def setup_logging() -> None:
    """Journal à côté de l'exécutable : en mode fenêtré il n'y a pas de console pour voir les erreurs."""
    logger.setLevel(logging.INFO)
    if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        return
    try:
        handler = RotatingFileHandler(LOG_PATH, maxBytes=500_000, backupCount=1, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    except OSError:
        pass


def system_prefers_dark() -> bool:
    """Vrai si Windows est réglé sur le mode d'application sombre."""
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        ) as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def enable_dpi_awareness() -> None:
    """Évite le texte flou sur les écrans mis à l'échelle (125 %, 150 %…) sous Windows."""
    if os.name != "nt":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def create_root() -> tk.Tk:
    """Fenêtre racine avec glisser-déposer si `tkinterdnd2` est disponible, sinon Tk standard."""
    enable_dpi_awareness()
    if TkinterDnD is not None:
        try:
            return TkinterDnD.Tk()
        except Exception:
            logger.exception("tkinterdnd2 indisponible, retour à Tk standard")
    return tk.Tk()

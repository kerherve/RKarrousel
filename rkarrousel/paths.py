"""Emplacements des fichiers de l'appli (config, journal, jeton Drive).

En exécutable PyInstaller (--onefile), `__file__` pointe vers un dossier temporaire effacé à la fermeture : ces
fichiers vivent donc à côté de l'exécutable."""

import sys
from pathlib import Path


CONFIG_FILE_NAME = ".image_splitter_config.json"


# When frozen by PyInstaller (--onefile), __file__ lives in a temp extraction
# folder that's wiped on exit, so the config must live next to the executable.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent  # racine du dépôt (lancement depuis les sources)


PROJECT_CONFIG_PATH = APP_DIR / CONFIG_FILE_NAME
LEGACY_CONFIG_PATH = Path.home() / CONFIG_FILE_NAME
LOG_FILE_NAME = "image_splitter.log"
LOG_PATH = APP_DIR / LOG_FILE_NAME
GDRIVE_TOKEN_PATH = APP_DIR / "gdrive_token.json"  # jeton Google Drive, à côté de l'exécutable


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

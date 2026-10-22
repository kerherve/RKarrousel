"""Contexte partagé par les onglets et les contrôleurs : fenêtre, config, réglages, thème, session et état global."""
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from rkarrousel.config import save_config
from rkarrousel.gui.events import EventBus
from rkarrousel.gui.session import Session
from rkarrousel.gui.settings_model import SettingsModel
from rkarrousel.gui.theme import Theme
from rkarrousel.paths import CONFIG_PATH


class AppContext:
    def __init__(self, root: tk.Tk, config: dict, theme: Theme, config_path: Path = CONFIG_PATH):
        self.root = root
        self.config_path = config_path
        self.config = config
        self.theme = theme
        self.model = SettingsModel(config)
        self.session = Session()
        self.bus = EventBus(root)
        self.status_text = tk.StringVar(value="")
        self.progress_value = tk.DoubleVar(value=0)
        self.cancel_event = threading.Event()
        self._processing = False
        self.on_processing_changed: Optional[Callable[[], None]] = None

    # --- état « traitement en cours » (désactive les boutons, change le bouton principal)
    @property
    def processing(self) -> bool:
        return self._processing

    def set_processing(self, value: bool) -> None:
        self._processing = value
        if self.on_processing_changed:
            self.on_processing_changed()

    # --- barre d'état et progression
    def set_status(self, text: str) -> None:
        self.status_text.set(text)

    def set_progress(self, percent: float) -> None:
        self.progress_value.set(percent)

    # --- configuration
    def collect_config(self) -> dict:
        """Recopie les réglages de l'écran dans la config et la renvoie."""
        return self.model.collect(self.config)

    def save_config(self) -> None:
        save_config(self.config_path, self.config)

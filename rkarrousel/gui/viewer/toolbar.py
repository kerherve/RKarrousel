"""Barre d'outils de la visionneuse : zoom, rang dans la grille, aperçu carrousel, recadrage et réglages."""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from rkarrousel.gui.viewer.viewport import ZOOM_STEP
from rkarrousel.i18n import t


class ViewerToolbar(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        on_fit: Callable[[], None],
        on_zoom_100: Callable[[], None],
        on_zoom_by: Callable[[float], None],
        on_toggle_settings: Optional[Callable[[], None]] = None,
        on_crop: Optional[Callable[[], None]] = None,
    ):
        """`on_toggle_settings` et `on_crop` n'ont de bouton que s'ils sont fournis (panneau de réglages, grille)."""
        super().__init__(parent)
        ttk.Button(self, text=t("viewer_fit"), command=on_fit).pack(side=tk.LEFT)
        ttk.Button(self, text=t("viewer_100"), command=on_zoom_100).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(self, text="−", width=3, command=lambda: on_zoom_by(1 / ZOOM_STEP)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(self, text="+", width=3, command=lambda: on_zoom_by(ZOOM_STEP)).pack(side=tk.LEFT, padx=(6, 0))
        self.zoom_label = ttk.Label(self, text="")
        self.zoom_label.pack(side=tk.LEFT, padx=(12, 0))
        self.position_label = ttk.Label(self, text="")
        self.position_label.pack(side=tk.LEFT, padx=(16, 0))
        if on_toggle_settings is not None:
            ttk.Button(self, text=t("viewer_settings"), command=on_toggle_settings).pack(side=tk.RIGHT, padx=(0, 8))
        self.crop_button: Optional[ttk.Button] = None
        if on_crop is not None:
            self.crop_button = ttk.Button(self, text=t("order_crop"), command=on_crop)
            self.crop_button.pack(side=tk.RIGHT, padx=(0, 8))

    def add_carousel_toggle(self, variable: tk.BooleanVar, command: Callable[[], None]) -> None:
        ttk.Checkbutton(self, text=t("viewer_carousel"), variable=variable, command=command).pack(
            side=tk.LEFT, padx=(16, 0))

    def set_zoom(self, zoom: float) -> None:
        self.zoom_label.configure(text=t("viewer_zoom", percent=zoom * 100))

    def set_position(self, number: int, total: int) -> None:
        self.position_label.configure(text=f"{number} / {total}" if total else "")

    def set_crop_enabled(self, enabled: bool) -> None:
        if self.crop_button is not None:
            self.crop_button.state(["!disabled"] if enabled else ["disabled"])

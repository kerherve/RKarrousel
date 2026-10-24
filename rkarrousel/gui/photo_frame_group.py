"""Couleur du cadre propre à UNE photo (dans la visionneuse) : elle remplace le réglage général pour cette photo."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

from rkarrousel.config import COLOR_MODES, photo_override_for
from rkarrousel.gui.context import AppContext
from rkarrousel.gui.settings_groups import color_mode_labels
from rkarrousel.gui.widgets import ChoiceBox, ColorPicker, HintLabel, bind_trace
from rkarrousel.i18n import t

GLOBAL = "global"  # pas de réglage propre à la photo : on suit les réglages généraux


class PhotoFrameGroup(ttk.LabelFrame):
    def __init__(self, parent, ctx: AppContext, source: Path, on_change: Callable[[], None]):
        super().__init__(parent, text=t("photo_group"), padding=12)
        self.ctx, self.source, self.on_change = ctx, source, on_change
        current = photo_override_for(ctx.config, source)
        self.mode = tk.StringVar(value=current.get("border_color_mode", GLOBAL))
        self.color = tk.StringVar(value=current.get("border_color", ctx.model.border_color.get()))
        self.columnconfigure(1, weight=1)
        self.box = ChoiceBox(
            self, self.mode, (GLOBAL,) + COLOR_MODES, [t("photo_color_global")] + color_mode_labels(), width=30
        )
        self.box.grid(row=0, column=0, columnspan=2, sticky=tk.W)
        self.picker = ColorPicker(self, self.color, (255, 255, 255), t("choose_color"))
        self.picker.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))
        HintLabel(self, t("photo_group_hint")).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))
        bind_trace(self, self.mode, self._changed)
        bind_trace(self, self.color, self._changed)
        bind_trace(self, ctx.model.no_frame, self.refresh_state)
        self.refresh_state()

    def refresh_state(self) -> None:
        """Sans cadre, il n'y a rien à colorier ; la couleur fixe n'a de sens que pour le mode « couleur fixe »."""
        framed = not self.ctx.model.no_frame.get()
        self.box.state(["!disabled"] if framed else ["disabled"])
        self.picker.set_enabled(framed and self.mode.get() == "fixed")

    def _changed(self) -> None:
        self.store()
        self.refresh_state()
        self.on_change()

    def store(self) -> None:
        """Enregistre (ou retire) le réglage de cette photo dans la config, conservée d'une session à l'autre."""
        overrides = self.ctx.config.setdefault("photo_overrides", {})
        key = str(self.source)
        if self.mode.get() == GLOBAL:
            overrides.pop(key, None)
        else:
            overrides[key] = {"border_color_mode": self.mode.get(), "border_color": self.color.get()}
        self.ctx.save_config()

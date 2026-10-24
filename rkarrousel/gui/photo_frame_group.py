"""Couleur du cadre propre à UNE photo (dans la visionneuse) : choix de la couleur, couleur obtenue, retouche fine.
Ces réglages remplacent les réglages généraux pour cette photo seulement."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Tuple

from rkarrousel.config import COLOR_MODES, TWEAK_LIMITS, border_tweak_of, photo_override_for
from rkarrousel.gui.context import AppContext
from rkarrousel.gui.settings_groups import color_mode_labels
from rkarrousel.gui.widgets import ChoiceBox, ColorPicker, HintLabel, bind_trace
from rkarrousel.i18n import t

GLOBAL = "global"  # pas de réglage propre à la photo : on suit les réglages généraux
TWEAK_DELAY_MS = 200  # on attend la fin du geste du curseur avant d'enregistrer et de recalculer


class PhotoFrameGroup(ttk.LabelFrame):
    def __init__(self, parent, ctx: AppContext, source: Path, on_change: Callable[[], None]):
        super().__init__(parent, text=t("photo_group"), padding=12)
        self.ctx, self.source, self.on_change = ctx, source, on_change
        self._loading = False
        self._tweak_job = None
        current = photo_override_for(ctx.config, source)
        self.mode = tk.StringVar(value=current.get("border_color_mode", GLOBAL))
        self.color = tk.StringVar(value=current.get("border_color", ctx.model.border_color.get()))
        self.tweaks = [tk.DoubleVar(value=0.0) for _ in TWEAK_LIMITS]  # curseurs de -1 à +1 (× limite de chaque réglage)
        self.columnconfigure(1, weight=1)
        self.box = ChoiceBox(
            self, self.mode, (GLOBAL,) + COLOR_MODES, [t("photo_color_global")] + color_mode_labels(), width=30
        )
        self.box.grid(row=0, column=0, columnspan=3, sticky=tk.W)
        self.picker = ColorPicker(self, self.color, (255, 255, 255), t("choose_color"))
        self.picker.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

        ttk.Label(self, text=t("photo_resolved")).grid(row=2, column=0, sticky=tk.W, pady=(12, 0))
        self.resolved_swatch = tk.Label(self, width=4, relief=tk.SOLID, borderwidth=1)
        self.resolved_swatch.grid(row=2, column=1, sticky=tk.W, pady=(12, 0), padx=8)
        self.resolved_text = ttk.Label(self, text="")
        self.resolved_text.grid(row=2, column=2, sticky=tk.W, pady=(12, 0))

        ttk.Label(self, text=t("tweak_title"), style="Hint.TLabel").grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))
        self.scales = []
        for row, (label, var) in enumerate(zip(("tweak_hue", "tweak_sat", "tweak_light"), self.tweaks), start=4):
            name = ttk.Label(self, text=t(label))
            name.grid(row=row, column=0, sticky=tk.W)
            scale = ttk.Scale(self, from_=-1.0, to=1.0, variable=var, orient=tk.HORIZONTAL)
            scale.grid(row=row, column=1, columnspan=2, sticky=tk.EW, padx=(8, 0))
            self.scales.append(scale)
            for widget in (name, scale):  # double-clic sur la ligne : retour à la valeur par défaut (au milieu)
                widget.bind("<Double-Button-1>", lambda e, v=var: self._reset_one(v))
            bind_trace(self, var, self._tweak_changed)
        self.reset_button = ttk.Button(self, text=t("tweak_reset"), command=self.reset_tweak)
        self.reset_button.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(6, 0))
        HintLabel(self, t("photo_group_hint")).grid(row=8, column=0, columnspan=3, sticky=tk.EW, pady=(8, 0))
        bind_trace(self, self.mode, self._changed)
        bind_trace(self, self.color, self._changed)
        bind_trace(self, ctx.model.no_frame, self.refresh_state)
        bind_trace(self, ctx.model.border_color_mode, self.refresh_state)
        self.set_source(source)

    # ------------------------------------------------------------------ lecture / affichage
    def set_source(self, source: Path) -> None:
        """Passe à une autre photo : affiche son réglage propre (sans rien enregistrer)."""
        self.source = source
        current = photo_override_for(self.ctx.config, source)
        tweak = border_tweak_of(current)
        self._loading = True
        try:
            self.mode.set(current.get("border_color_mode", GLOBAL))
            self.color.set(current.get("border_color", self.ctx.model.border_color.get()))
            for var, value, limit in zip(self.tweaks, tweak, TWEAK_LIMITS):
                var.set(value / limit)
        finally:
            self._loading = False
        self.refresh_state()

    def show_resolved(self, color: Tuple[int, int, int]) -> None:
        """La couleur réellement obtenue pour cette photo (calculée, retouche comprise)."""
        hex_color = "#%02X%02X%02X" % tuple(color)
        self.resolved_swatch.configure(bg=hex_color)
        self.resolved_text.configure(text=hex_color)

    def effective_mode(self) -> str:
        mode = self.mode.get()
        return self.ctx.model.border_color_mode.get() if mode == GLOBAL else mode

    def refresh_state(self) -> None:
        """Sans cadre il n'y a rien à colorier ; la couleur fixe n'a de sens qu'en mode « couleur fixe » et la retouche
        fine seulement pour une couleur tirée de la photo."""
        framed = not self.ctx.model.no_frame.get()
        self.box.state(["!disabled"] if framed else ["disabled"])
        self.picker.set_enabled(framed and self.mode.get() == "fixed")
        tweakable = framed and self.effective_mode() != "fixed"
        for scale in self.scales:
            scale.state(["!disabled"] if tweakable else ["disabled"])
        self.reset_button.state(["!disabled"] if tweakable else ["disabled"])

    # ------------------------------------------------------------------ modifications
    def tweak_values(self) -> list:
        return [round(var.get() * limit, 3) for var, limit in zip(self.tweaks, TWEAK_LIMITS)]

    def _reset_one(self, var: tk.DoubleVar) -> str:
        var.set(0.0)
        return "break"  # le curseur ne doit pas aller se placer sous la souris après la remise à zéro

    def reset_tweak(self) -> None:
        for var in self.tweaks:
            var.set(0.0)

    def _changed(self) -> None:
        if self._loading:
            return
        self.store()
        self.refresh_state()
        self.on_change()

    def _tweak_changed(self) -> None:
        if self._loading:
            return
        if self._tweak_job is not None:
            self.after_cancel(self._tweak_job)
        self._tweak_job = self.after(TWEAK_DELAY_MS, self._commit_tweak)

    def _commit_tweak(self) -> None:
        self._tweak_job = None
        self.store()
        self.on_change()

    def store(self) -> None:
        """Enregistre (ou retire) le réglage de cette photo dans la config, conservée d'une session à l'autre."""
        overrides = self.ctx.config.setdefault("photo_overrides", {})
        key = str(self.source)
        entry = {}
        if self.mode.get() != GLOBAL:
            entry.update(border_color_mode=self.mode.get(), border_color=self.color.get())
        tweak = self.tweak_values()
        if any(tweak):
            entry["border_tweak"] = tweak
        if entry:
            overrides[key] = entry
        else:
            overrides.pop(key, None)
        self.ctx.save_config()

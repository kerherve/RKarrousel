"""Panneau de réglages de la visionneuse : préréglages, cadre, couleur propre à la photo, fond et signature. Ce sont les groupes de
l'onglet Réglages, branchés sur les mêmes variables : ce qu'on y règle vaut pour toutes les photos."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable

from rkarrousel.gui.photo_frame_group import PhotoFrameGroup
from rkarrousel.gui.settings_groups import FillGroup, FrameGroup, PresetsGroup, SignatureGroup
from rkarrousel.gui.widgets import bind_trace, make_scrollable
from rkarrousel.i18n import t

PANEL_WIDTH = 450  # pixels à 96 ppp


class SettingsPanel:
    def __init__(self, parent: tk.Misc, ctx, source: Path, scale: float, background: str, on_change: Callable[[], None]):
        """`on_change` est appelé à chaque modification d'un réglage (la fenêtre recalcule alors l'image)."""
        model = ctx.model
        self.frame = ttk.Frame(parent, width=int(PANEL_WIDTH * scale))
        self.frame.pack_propagate(False)  # largeur fixe ; le panneau défile quand la fenêtre est trop basse
        inner = make_scrollable(self.frame, ttk.Style().lookup("TFrame", "background") or background)
        inner.configure(padding=(0, 0, 8, 0))
        PresetsGroup(inner, ctx).pack(fill=tk.X, pady=(0, 10))
        FrameGroup(inner, ctx).pack(fill=tk.X)
        self.photo_group = PhotoFrameGroup(inner, ctx, source, on_change)
        self.photo_group.pack(fill=tk.X, pady=(10, 0))
        self.fill_group = FillGroup(inner, ctx)
        self.signature_group = SignatureGroup(inner, ctx)
        self.fill_group.pack(fill=tk.X, pady=(10, 0))
        self.signature_group.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(inner, text=t("viewer_settings_hint"), style="Hint.TLabel", wraplength=int(400 * scale),
                  justify=tk.LEFT).pack(fill=tk.X, pady=(10, 0))
        for variable in (
            model.frame_percent, model.no_frame, model.border_color, model.border_color_mode,
            model.landscape_fill_mode, model.background_color, model.background_color_mode, model.blur_strength,
            model.signature_path, model.signature_position, model.signature_scale, model.color_source,
        ):
            bind_trace(self.frame, variable, on_change)

    def apply_features(self, features: frozenset) -> None:
        """Grise ce que l'image affichée n'utilise pas (fond, signature)."""
        self.fill_group.set_applicable("fill" in features)
        self.signature_group.set_applicable("signature" in features)

    def set_source(self, source: Path) -> None:
        self.photo_group.set_source(source)

    def show_resolved(self, color) -> None:
        self.photo_group.show_resolved(color)

    def toggle(self, before: tk.Misc) -> None:
        """Masque le panneau, ou le remet à droite (avant `before` dans l'ordre d'empilement)."""
        if self.frame.winfo_ismapped():
            self.frame.pack_forget()
        else:
            self.frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0), before=before)

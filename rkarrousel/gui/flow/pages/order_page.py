"""Étape « Ordre » : la grille des images de sortie (à réordonner, exclure, recadrer) et le choix des images produites."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, List, Optional, Set

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.flow.pages.base import Page
from rkarrousel.gui.order.view import OrderView
from rkarrousel.gui.settings_groups import KindsGroup
from rkarrousel.gui.widgets import bind_trace

SIDE_WIDTH = 380  # pixels à 96 ppp : colonne des images produites
RELOAD_DELAY_MS = 300  # on attend la fin des modifications des cases avant de refaire la grille


class OrderPage(Page):
    def __init__(self, parent: tk.Misc, ctx: AppContext, on_adjust: Callable[[], None], on_change: Callable[[], None]):
        """`on_adjust` : « Ajuster cette image » ; `on_change` : l'ordre ou les exclusions ont changé."""
        super().__init__(parent)
        self.ctx, self.on_adjust, self.on_change = ctx, on_adjust, on_change
        self.view: Optional[OrderView] = None
        self._reload_job = None
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.holder = ttk.Frame(self)
        self.holder.grid(row=0, column=0, sticky=tk.NSEW)
        side = ttk.Frame(self, width=int(SIDE_WIDTH * ctx.theme.scale))
        side.grid(row=0, column=1, sticky=tk.NS, padx=(14, 0))
        side.pack_propagate(False)
        KindsGroup(side, ctx).pack(fill=tk.X)
        model = ctx.model
        for variable in list(model.kind_vars.values()) + list(model.placements.values()):
            bind_trace(self, variable, self._kinds_changed)

    # ------------------------------------------------------------------ la grille
    def ensure_view(self) -> OrderView:
        """Crée la grille au premier passage ; ensuite elle est mise à jour (photos, format, réglages)."""
        ctx, session = self.ctx, self.ctx.session
        files = session.selected_files()
        config = dict(ctx.collect_config())
        session.sync_layout(config)  # la place des photos entières a pu changer : l'ordre naturel est recalculé
        if self.view is None:
            self.view = OrderView(
                self.holder, files, config, session.order, session.preview_cache,
                on_change=self._set_order, get_config=lambda: dict(ctx.collect_config()),
                dark=ctx.theme.dark, excluded=session.excluded, on_crop=self._set_crop_offset, on_adjust=self.on_adjust,
            )
            self.view.pack(fill=tk.BOTH, expand=True)
        else:
            self.view.reload(files, config, session.order, session.excluded)
        return self.view

    def on_show(self) -> None:
        self.ensure_view()

    def _kinds_changed(self) -> None:
        if self.view is None:
            return
        if self._reload_job is not None:
            self.after_cancel(self._reload_job)
        self._reload_job = self.after(RELOAD_DELAY_MS, self._reload)

    def _reload(self) -> None:
        self._reload_job = None
        if self.view is not None:
            self.ensure_view()

    # ------------------------------------------------------------------ mémorisation
    def _set_order(self, order: List[str], excluded: Set[str]) -> None:
        self.ctx.session.order = list(order)
        self.ctx.session.excluded = set(excluded)
        self.on_change()

    def _set_crop_offset(self, path: Path, offset: float) -> None:
        """Mémorise le recadrage choisi pour une photo (conservé d'une session à l'autre)."""
        self.ctx.config.setdefault("crop_offsets", {})[str(path)] = round(float(offset), 4)
        self.ctx.save_config()

    def included_images(self) -> Optional[int]:
        """Nombre d'images à produire (hors exclues) si la grille est calculée, sinon None."""
        if self.view is None:
            return None
        total, _, excluded, _ = self.view.model.counts()
        return total - excluded

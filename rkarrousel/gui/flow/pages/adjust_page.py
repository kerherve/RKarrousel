"""Étape « Ajustements » : la visionneuse de l'image sélectionnée, avec le carrousel et le panneau de réglages."""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.flow.pages.base import Page
from rkarrousel.gui.order.view import OrderView
from rkarrousel.gui.viewer import ViewerView
from rkarrousel.i18n import t


class AdjustPage(Page):
    def __init__(self, parent: tk.Misc, ctx: AppContext, get_order_view: Callable[[], Optional[OrderView]]):
        super().__init__(parent)
        self.ctx, self.get_order_view = ctx, get_order_view
        self.viewer: Optional[ViewerView] = None
        self.empty = ttk.Label(self, text=t("adjust_empty"), style="Hint.TLabel", justify=tk.LEFT)

    def on_show(self) -> None:
        order = self.get_order_view()
        tile = self._tile_to_show(order)
        if tile is None:  # rien à ajuster (tout est exclu)
            if self.viewer is not None:
                self.viewer.pack_forget()
            self.empty.pack(anchor=tk.W, pady=20)
            return
        self.empty.pack_forget()
        config = dict(self.ctx.collect_config())
        if self.viewer is None:
            self.viewer = ViewerView(
                self, tile.source, tile.kind, config, dark=self.ctx.theme.dark, ctx=self.ctx,
                on_settings_changed=order.refresh, navigator=order,
            )
        else:
            self.viewer.show(tile.source, tile.kind)
        self.viewer.pack(fill=tk.BOTH, expand=True)
        self.viewer.activate()

    @staticmethod
    def _tile_to_show(order: Optional[OrderView]):
        """L'image sélectionnée dans la grille, sinon la première image qui n'est pas exclue."""
        if order is None:
            return None
        tile = order.model.selected_tile()
        if tile is not None and not tile.excluded:
            return tile
        index = order.model.step_from_selection(1) if order.model.selected is not None else None
        if index is None:
            index = next((i for i, candidate in enumerate(order.model.tiles) if not candidate.excluded), None)
        if index is None:
            return None
        order.select(index)
        return order.model.tiles[index]

    def on_hide(self) -> None:
        if self.viewer is not None:
            self.viewer.deactivate()
            self.viewer.flush_changes()  # la grille d'ordre est rafraîchie si des réglages ont changé ici

"""Étape « Export » : récapitulatif, qualité et taille des fichiers, numérotation et envoi sur Google Drive. Le bouton
« Lancer le traitement » est dans la barre du bas."""
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from rkarrousel.formats import INSTAGRAM_MAX_IMAGES
from rkarrousel.gui.context import AppContext
from rkarrousel.gui.flow.pages.base import Page
from rkarrousel.gui.order.view import OrderView
from rkarrousel.gui.settings_groups import DriveGroup, OutputGroup
from rkarrousel.gui.widgets import bind_trace, make_scrollable
from rkarrousel.i18n import t


class ExportPage(Page):
    def __init__(self, parent: tk.Misc, ctx: AppContext, drive, get_order_view: Callable[[], Optional[OrderView]]):
        super().__init__(parent)
        self.ctx, self.get_order_view = ctx, get_order_view
        inner = make_scrollable(self, ctx.theme.surface_color())
        inner.columnconfigure(0, weight=1)
        self.recap = ttk.LabelFrame(inner, text=t("export_title"), padding=12)
        self.recap.grid(row=0, column=0, sticky=tk.EW)
        self.recap_text = tk.StringVar()
        ttk.Label(self.recap, textvariable=self.recap_text, justify=tk.LEFT, wraplength=int(900 * ctx.theme.scale)).pack(
            anchor=tk.W)
        self.warning = tk.StringVar()
        ttk.Label(self.recap, textvariable=self.warning, foreground="#f0a030", font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W, pady=(6, 0))
        OutputGroup(inner, ctx).grid(row=1, column=0, sticky=tk.EW, pady=(10, 0))
        DriveGroup(inner, ctx, drive).grid(row=2, column=0, sticky=tk.EW, pady=(10, 0))
        bind_trace(self, ctx.model.number_files, self.refresh_recap)

    def on_show(self) -> None:
        self.refresh_recap()

    def refresh_recap(self) -> None:
        """Ce qui va être produit : nombre d'images, exclues, destination, numérotation."""
        ctx = self.ctx
        view = self.get_order_view()
        total, _, excluded, _ = view.model.counts() if view is not None else (0, 0, 0, False)
        included = total - excluded
        lines = [t("export_recap", images=included, photos=len(ctx.session.selected_files()), dest=ctx.model.dest_dir.get())]
        if excluded:
            lines.append(t("export_excluded", count=excluded))
        lines.append(t("export_numbered" if ctx.model.number_files.get() else "export_not_numbered"))
        self.recap_text.set("\n".join(lines))
        self.warning.set(t("export_over_limit", limit=INSTAGRAM_MAX_IMAGES) if included > INSTAGRAM_MAX_IMAGES else "")

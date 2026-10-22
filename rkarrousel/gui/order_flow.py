"""Fenêtre « Aperçu et ordre » : ouverture et mémorisation de l'ordre, des exclusions et des recadrages."""
from pathlib import Path
from tkinter import messagebox
from typing import List, Optional, Set

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.order.window import OrderWindow
from rkarrousel.i18n import t


class OrderController:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.window: Optional[OrderWindow] = None

    def open(self) -> None:
        ctx, session = self.ctx, self.ctx.session
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            return
        if not session.selected_paths:
            messagebox.showwarning(t("dlg_no_file_title"), t("dlg_no_file"))
            return
        files = session.selected_files()
        if not files:
            messagebox.showwarning(t("dlg_no_file_title"), t("status_no_image"))
            return
        self.window = OrderWindow(
            ctx.root,
            files,
            dict(ctx.collect_config()),
            session.order,
            session.preview_cache,
            dark=ctx.theme.dark,
            excluded=session.excluded,
            on_crop=self.set_crop_offset,
            on_change=self.set_order,
            get_config=lambda: dict(ctx.collect_config()),
        )

    def close(self) -> None:
        if self.window is not None:
            self.window.close()
            self.window = None

    def set_crop_offset(self, path: Path, offset: float) -> None:
        """Mémorise le recadrage choisi pour une photo (conservé d'une session à l'autre)."""
        self.ctx.config.setdefault("crop_offsets", {})[str(path)] = round(float(offset), 4)
        self.ctx.save_config()

    def set_order(self, order: List[str], excluded: Set[str]) -> None:
        self.ctx.session.order = list(order)
        self.ctx.session.excluded = set(excluded)

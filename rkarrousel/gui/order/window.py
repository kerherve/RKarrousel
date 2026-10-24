"""Fenêtre « grille Instagram » : aperçu du rendu final de chaque image de sortie, réordonnable par glisser-déposer.
L'ordre sert ensuite à numéroter les fichiers (01_, 02_…)."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from PIL import Image

from rkarrousel.formats import output_format_of
from rkarrousel.gui.crop_editor import CropEditor
from rkarrousel.gui.viewer import ImageViewer
from rkarrousel.gui.order.grid_canvas import GridCanvas
from rkarrousel.gui.order.grid_layout import GridLayout
from rkarrousel.gui.order.model import OrderModel, render_signature
from rkarrousel.gui.order.thumbnails import ThumbnailService
from rkarrousel.i18n import t
from rkarrousel.kinds import KIND_CROP


class OrderWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        files: Sequence[Path],
        config: dict,
        order: Sequence[str],
        cache: Dict[str, Tuple[str, Image.Image]],
        on_change: Callable[[List[str], Set[str]], None],
        get_config: Callable[[], dict],
        dark: bool = False,
        excluded: Optional[Set[str]] = None,
        on_crop: Optional[Callable[[Path, float], None]] = None,
        settings_ctx=None,
    ):
        super().__init__(parent)
        scale = max(1.0, self.winfo_fpixels("1i") / 96)
        self.scale, self.dark = scale, dark
        self.config_snapshot = dict(config)
        self.on_change, self.get_config, self.on_crop = on_change, get_config, on_crop
        self.settings_ctx = settings_ctx  # contexte de l'appli : la visionneuse y règle cadre et fond
        self.layout = GridLayout(scale, output_format_of(config))
        self.model = OrderModel(files, excluded)
        self.thumbs = ThumbnailService(cache, self.layout.max_thumb_size())  # assez grandes pour une fenêtre très large
        self._closing = False

        self.title(t("order_title"))
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.transient(parent)
        self.start(order)
        self.after(80, self._poll)

    # ------------------------------------------------------------------ interface
    def _build_ui(self) -> None:
        layout, scale = self.layout, self.scale
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = min(layout.canvas_width + int(60 * scale), screen_w - 40)
        height = min(int(800 * scale), screen_h - 120)
        x, y = max(0, (screen_w - width) // 2), max(0, (screen_h - height) // 2 - 30)
        self.geometry(f"{width}x{height}+{x}+{y}")  # centrée sur l'écran
        self.minsize(min(layout.canvas_width + int(60 * scale), width), min(int(440 * scale), height))

        frame = ttk.Frame(self, padding=(16, 12, 16, 14))
        frame.pack(fill=tk.BOTH, expand=True)
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text=t("order_refresh"), command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(toolbar, text=t("order_reset"), command=self.reset_order).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text=t("order_close"), command=self.close).pack(side=tk.RIGHT)
        self.exclude_btn = ttk.Button(toolbar, text=t("order_exclude"), command=self.toggle_exclude)
        self.exclude_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self.crop_btn = ttk.Button(toolbar, text=t("order_crop"), command=self.crop_selected)
        self.crop_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self.view_btn = ttk.Button(toolbar, text=t("order_view"), command=self.view_selected)
        self.view_btn.pack(side=tk.RIGHT, padx=(0, 8))

        hint = ttk.Label(frame, text=t("order_hint"), justify=tk.LEFT, wraplength=layout.canvas_width)
        hint.pack(fill=tk.X)
        hint.bind("<Configure>", lambda e: hint.configure(wraplength=max(200, e.width - 4)))  # suit la largeur de la fenêtre
        self.status = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status, style="Hint.TLabel").pack(fill=tk.X, pady=(4, 8))

        body = ttk.Frame(frame)
        body.pack(fill=tk.BOTH, expand=True)
        self.grid_canvas = GridCanvas(
            body, layout, self.model, self.dark,
            on_select=self.select, on_toggle_exclude=self.toggle_exclude, on_reorder=self.reorder,
            on_open=self.open_tile, on_context=self._popup_menu,
        )
        scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.grid_canvas.yview)
        self.grid_canvas.configure(yscrollcommand=scrollbar.set)
        self.grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0))

        self.bind("<Delete>", lambda e: self.toggle_exclude())
        self.bind("<Return>", lambda e: self.view_selected())
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label=t("order_view"), command=self.view_selected)
        self.menu.add_command(label=t("order_exclude"), command=self.toggle_exclude)
        self.menu.add_command(label=t("order_crop"), command=self.crop_selected)
        self._update_buttons()

    # ------------------------------------------------------------------ contenu
    @property
    def tiles(self):
        return self.model.tiles

    def start(self, order: Sequence[str]) -> None:
        """(Re)construit la liste des vignettes et lance le calcul des aperçus manquants."""
        config = self.config_snapshot
        signature = render_signature(config)
        pending = self.model.rebuild(config, order, lambda key, path: self.thumbs.lookup(key, path, config, signature))
        self._notify()
        self.grid_canvas.redraw()
        self._update_status()
        self._update_buttons()
        self.thumbs.stop()
        if pending:
            self.thumbs.start(pending, config, signature)

    def _poll(self) -> None:
        if self._closing:
            return
        config = self.config_snapshot
        events = self.thumbs.drain()
        for event in events:
            if event[0] == "thumb":
                _, key, path, signature, thumb = event
                self.thumbs.store(key, path, config, signature, thumb)
                self.model.set_thumb(key, thumb)
            elif event[0] == "error":
                self.model.set_error(event[1], event[2])
        if events:
            self.grid_canvas.redraw()
            self._update_status()
        self.after(80, self._poll)

    def _notify(self) -> None:
        self.on_change(self.model.keys(), set(self.model.excluded))

    def _update_status(self) -> None:
        total, ready, excluded, failed = self.model.counts()
        if ready < total and not failed:
            self.status.set(t("order_rendering", done=ready, total=total))
        elif excluded:
            self.status.set(t("order_count_excluded", total=total, excluded=excluded))
        else:
            self.status.set(t("order_count", total=total))

    def _update_buttons(self) -> None:
        tile = self.model.selected_tile()
        state = ["!disabled"] if tile else ["disabled"]
        self.view_btn.state(state)
        self.exclude_btn.state(state)
        can_crop = bool(tile and tile.kind == KIND_CROP and self.on_crop)
        self.crop_btn.state(["!disabled"] if can_crop else ["disabled"])
        label = t("order_restore") if tile and tile.excluded else t("order_exclude")
        self.exclude_btn.configure(text=label)
        self.menu.entryconfigure(1, label=label)
        self.menu.entryconfigure(2, state=tk.NORMAL if can_crop else tk.DISABLED)

    # ------------------------------------------------------------------ actions
    def select(self, index: Optional[int]) -> None:
        self.model.select(index)
        self._update_buttons()
        self.grid_canvas.redraw()

    def toggle_exclude(self) -> None:
        if self.model.toggle_selected_exclusion():
            self._notify()
            self._update_buttons()
            self._update_status()
            self.grid_canvas.redraw()

    def reorder(self, source: int, target: int) -> None:
        if self.model.move(source, target):
            self._notify()
            self._update_buttons()

    def view_selected(self) -> None:
        tile = self.model.selected_tile()
        if tile is not None:
            ImageViewer(
                self, tile.source, tile.kind, self.config_snapshot, dark=self.dark,
                ctx=self.settings_ctx, on_settings_changed=self.refresh, navigator=self,
            )

    # ------------------------------------------------------------------ navigation de la visionneuse
    def viewer_step(self, delta: int):
        """Passe à l'image affichée suivante (+1) ou précédente (-1) : la sélectionne et la renvoie, sinon None."""
        index = self.model.step_from_selection(delta)
        if index is None:
            return None
        self.select(index)
        return self.model.tiles[index]

    def viewer_peek(self, delta: int):
        """La vignette voisine (sans changer la sélection), pour l'aperçu en carrousel de la visionneuse."""
        index = self.model.step_from_selection(delta)
        return None if index is None else self.model.tiles[index]

    def viewer_can_step(self, delta: int) -> bool:
        return self.model.step_from_selection(delta) is not None

    def viewer_position(self):
        return self.model.position_of_selection()

    def crop_selected(self) -> None:
        tile = self.model.selected_tile()
        if tile is None or tile.kind != KIND_CROP or self.on_crop is None:
            return
        source, key = tile.source, tile.key

        def apply(offset: float) -> None:
            self.on_crop(source, offset)
            self.config_snapshot = dict(self.get_config())
            self.start(self.model.keys())
            index = self.model.index_of(key)
            if index is not None:
                self.select(index)

        CropEditor(self, source, self.config_snapshot, apply, dark=self.dark)

    def open_tile(self, index: int) -> None:
        """Double-clic : le réglage du cadrage pour un recadrage, sinon la visionneuse."""
        if self.model.tiles[index].kind == KIND_CROP and self.on_crop:
            self.crop_selected()
        else:
            self.view_selected()

    def _popup_menu(self, index: int, x_root: int, y_root: int) -> None:
        self.menu.tk_popup(x_root, y_root)

    def refresh(self) -> None:
        self.config_snapshot = dict(self.get_config())
        self.start(self.model.keys())

    def reset_order(self) -> None:
        self.start([])

    def close(self) -> None:
        self._closing = True
        self.thumbs.stop()
        self.destroy()

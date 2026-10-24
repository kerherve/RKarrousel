"""Étape « Ordre » : la grille des images de sortie, avec le rendu final de chacune, réordonnable par glisser-déposer.
L'ordre sert ensuite à numéroter les fichiers (01_, 02_…)."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from PIL import Image

from rkarrousel.formats import INSTAGRAM_MAX_IMAGES, output_format_of
from rkarrousel.gui.crop_editor import CropEditor
from rkarrousel.gui.order.grid_canvas import GridCanvas
from rkarrousel.gui.order.grid_layout import GridLayout
from rkarrousel.gui.order.model import OrderModel, render_signature
from rkarrousel.gui.order.thumbnails import ThumbnailService
from rkarrousel.i18n import t
from rkarrousel.kinds import KIND_CROP


class OrderView(ttk.Frame):
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
        on_adjust: Optional[Callable[[], None]] = None,
    ):
        """`on_adjust` : « Ajuster cette image » (la vignette sélectionnée) ; `on_change` : l'ordre ou les exclusions
        ont changé ; `get_config` : les réglages à jour (recalculés à la demande)."""
        super().__init__(parent)
        scale = max(1.0, self.winfo_fpixels("1i") / 96)
        self.scale, self.dark = scale, dark
        self.config_snapshot = dict(config)
        self.on_change, self.get_config, self.on_crop, self.on_adjust = on_change, get_config, on_crop, on_adjust
        self.files = list(files)
        self.layout = GridLayout(scale, output_format_of(config))
        self.model = OrderModel(files, excluded)
        self.thumbs = ThumbnailService(cache, (self.layout.tile_w * 2, self.layout.tile_h * 2))  # marge pour un affichage net
        self._closing = False

        self._build_ui()
        self.bind("<Destroy>", lambda e: self._on_destroy() if e.widget is self else None, add="+")
        self.start(order)
        self._poll_job = self.after(80, self._poll)

    # ------------------------------------------------------------------ interface
    def _build_ui(self) -> None:
        layout = self.layout
        frame = self
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text=t("order_refresh"), command=self.refresh).pack(side=tk.LEFT)
        ttk.Button(toolbar, text=t("order_reset"), command=self.reset_order).pack(side=tk.LEFT, padx=(8, 0))
        self.exclude_btn = ttk.Button(toolbar, text=t("order_exclude"), command=self.toggle_exclude)
        self.exclude_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self.crop_btn = ttk.Button(toolbar, text=t("order_crop"), command=self.crop_selected)
        self.crop_btn.pack(side=tk.RIGHT, padx=(0, 8))
        self.view_btn = ttk.Button(toolbar, text=t("order_adjust"), command=self.adjust_selected)
        self.view_btn.pack(side=tk.RIGHT, padx=(0, 8))

        hint = ttk.Label(frame, text=t("order_hint"), justify=tk.LEFT, wraplength=layout.canvas_width)
        hint.pack(fill=tk.X)
        hint.bind("<Configure>", lambda e: hint.configure(wraplength=max(200, e.width - 4)))  # suit la largeur de la fenêtre
        self.status = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status, style="Hint.TLabel").pack(fill=tk.X, pady=(4, 0))
        self.warning = tk.StringVar(value="")  # avertissement : plus de 20 images (limite d'un carrousel Instagram)
        warning = ttk.Label(frame, textvariable=self.warning, foreground="#f0a030", justify=tk.LEFT,
                            font=("Segoe UI", 10, "bold"), wraplength=layout.canvas_width)
        warning.pack(fill=tk.X, pady=(2, 8))
        warning.bind("<Configure>", lambda e: warning.configure(wraplength=max(200, e.width - 4)))

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

        self.grid_canvas.bind("<Delete>", lambda e: self.toggle_exclude())
        self.grid_canvas.bind("<Return>", lambda e: self.adjust_selected())
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label=t("order_adjust"), command=self.adjust_selected)
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
        self._poll_job = self.after(80, self._poll)

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
        included = total - excluded
        self.warning.set(
            t("order_too_many", count=included, limit=INSTAGRAM_MAX_IMAGES, first=INSTAGRAM_MAX_IMAGES + 1)
            if included > INSTAGRAM_MAX_IMAGES else ""
        )

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

    def adjust_selected(self) -> None:
        """Passe à l'étape « Ajustements » sur l'image sélectionnée."""
        if self.model.selected_tile() is not None and self.on_adjust is not None:
            self.on_adjust()

    # ------------------------------------------------------------------ navigation de la visionneuse
    def viewer_step(self, delta: int):
        """Passe à l'image affichée suivante (+1) ou précédente (-1) : la sélectionne et la renvoie, sinon None."""
        index = self.model.step_from_selection(delta)
        if index is None:
            return None
        self.select(index)
        return self.model.tiles[index]

    def viewer_preview(self, tile, config: dict):
        """Aperçu déjà calculé pour la grille (valable si les réglages n'ont pas changé), ou None : la visionneuse
        l'affiche tout de suite, en attendant le rendu en pleine résolution."""
        return self.thumbs.lookup(tile.key, tile.source, config, render_signature(config))

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
        if tile is not None and tile.kind == KIND_CROP and self.on_crop is not None:
            self._open_crop_editor(tile, self, None)

    def viewer_crop(self, parent: tk.Misc, on_applied: Callable[[], None]) -> None:
        """« Recadrer… » depuis la visionneuse : l'image affichée est la vignette sélectionnée."""
        tile = self.model.selected_tile()
        if tile is not None and tile.kind == KIND_CROP and self.on_crop is not None:
            self._open_crop_editor(tile, parent, on_applied)

    def _open_crop_editor(self, tile, parent: tk.Misc, on_applied: Optional[Callable[[], None]]) -> None:
        source, key = tile.source, tile.key

        def apply(offset: float) -> None:
            self.on_crop(source, offset)
            self.config_snapshot = dict(self.get_config())
            self.start(self.model.keys())
            index = self.model.index_of(key)
            if index is not None:
                self.select(index)
            if on_applied is not None:
                on_applied()

        CropEditor(parent.winfo_toplevel(), source, self.config_snapshot, apply, dark=self.dark)

    def open_tile(self, index: int) -> None:
        """Double-clic : le réglage du cadrage pour un recadrage, sinon la visionneuse."""
        if self.model.tiles[index].kind == KIND_CROP and self.on_crop:
            self.crop_selected()
        else:
            self.adjust_selected()

    def _popup_menu(self, index: int, x_root: int, y_root: int) -> None:
        self.menu.tk_popup(x_root, y_root)

    def refresh(self) -> None:
        self.config_snapshot = dict(self.get_config())
        self.start(self.model.keys())

    def reset_order(self) -> None:
        self.start([])

    def reload(self, files: Sequence[Path], config: dict, order: Sequence[str], excluded: Set[str]) -> None:
        """Retour sur l'étape : même photos et même format, on rafraîchit seulement ; sinon la grille est refaite."""
        self.config_snapshot = dict(config)
        if list(files) != self.files or output_format_of(config) != self.layout_format:
            self.files = list(files)
            self.model = OrderModel(files, excluded)
            self.layout.reshape(output_format_of(config))
            self.thumbs.thumb_size = (self.layout.tile_w * 2, self.layout.tile_h * 2)
            self.grid_canvas.model = self.model
        self.start(order)

    @property
    def layout_format(self):
        return self.layout.target

    def _on_destroy(self) -> None:
        self._closing = True
        self.thumbs.stop()
        try:
            self.after_cancel(self._poll_job)
        except (tk.TclError, ValueError):
            pass

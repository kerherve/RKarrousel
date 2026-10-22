#!/usr/bin/env python3
"""Fenêtre « grille Instagram » : aperçu du rendu final de chaque image de sortie, réordonnable
par glisser-déposer. L'ordre sert ensuite à numéroter les fichiers (01_, 02_…)."""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from PIL import Image, ImageTk

from i18n import kind_label, t
from crop_editor import CropEditor
from image_viewer import ImageViewer
from utils import KIND_CROP, crop_offset_for, item_key, merge_order, planned_items, render_outputs

COLUMNS = 3
BASE_TILE_W = 210
BASE_TILE_H = 280  # 3:4, comme la grille de profil Instagram
BASE_GAP = 4
PREVIEW_SOURCE_SIDE = 1600  # la source est réduite avant rendu : cadre et flou sont relatifs, le rendu reste fidèle
DRAG_THRESHOLD = 6

RENDER_KEYS = (
    "frame_ratio",
    "landscape_fill_mode",
    "signature_path",
    "border_color",
    "blur_strength",
    "signature_position",
    "signature_scale",
    "background_color",
    "disabled_kinds",
)


def render_signature(config: dict) -> str:
    """Empreinte des réglages qui changent le rendu (sert à invalider le cache d'aperçus)."""
    return json.dumps({key: config.get(key) for key in RENDER_KEYS}, sort_keys=True)


@dataclass
class Tile:
    key: str
    source: Path
    kind: str
    thumb: Optional[Image.Image] = None
    photo: Optional[ImageTk.PhotoImage] = None
    error: str = ""
    excluded: bool = False


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
    ):
        super().__init__(parent)
        scale = max(1.0, self.winfo_fpixels("1i") / 96)
        self.scale = scale
        self.TILE_W = int(BASE_TILE_W * scale)
        self.TILE_H = int(BASE_TILE_H * scale)
        self.GAP = max(2, int(BASE_GAP * scale))
        self.dark = dark
        self.bg = "#000000" if dark else "#ffffff"  # fond de la grille, comme Instagram
        self.title(t("order_title"))
        self.files = list(files)
        self.config_snapshot = dict(config)
        self.cache = cache  # key -> (empreinte, miniature), partagé entre ouvertures
        self.on_change = on_change
        self.excluded: Set[str] = set(excluded or ())
        self.on_crop = on_crop
        self.selected: Optional[int] = None
        self.get_config = get_config

        self.tiles: List[Tile] = []
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: Optional[threading.Thread] = None
        self.drag: Optional[dict] = None
        self._closing = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.transient(parent)
        self.start(order)
        self.after(80, self._poll)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        canvas_width = COLUMNS * self.TILE_W + (COLUMNS + 1) * self.GAP
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = min(canvas_width + int(60 * self.scale), screen_w - 40)
        height = min(int(800 * self.scale), screen_h - 120)
        x, y = max(0, (screen_w - width) // 2), max(0, (screen_h - height) // 2 - 30)
        self.geometry(f"{width}x{height}+{x}+{y}")  # centrée sur l'écran
        self.minsize(min(canvas_width + int(60 * self.scale), width), min(int(440 * self.scale), height))

        root_frame = ttk.Frame(self, padding=(16, 12, 16, 14))
        root_frame.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(root_frame)
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
        self._update_buttons()

        self.hint = ttk.Label(root_frame, text=t("order_hint"), justify=tk.LEFT, wraplength=canvas_width)
        self.hint.pack(fill=tk.X)
        self.status = tk.StringVar(value="")
        ttk.Label(root_frame, textvariable=self.status, style="Hint.TLabel").pack(fill=tk.X, pady=(4, 8))

        body = ttk.Frame(root_frame)
        body.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(body, width=canvas_width, bg=self.bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0))

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<ButtonPress-3>", self._on_context)
        self.bind("<Delete>", lambda e: self.toggle_exclude())
        self.bind("<Return>", lambda e: self.view_selected())
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label=t("order_view"), command=self.view_selected)
        self.menu.add_command(label=t("order_exclude"), command=self.toggle_exclude)
        self.menu.add_command(label=t("order_crop"), command=self.crop_selected)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))

    # ------------------------------------------------------------------ data / rendering
    def start(self, order: Sequence[str]) -> None:
        """(Re)construit la liste des tuiles et lance le rendu des aperçus manquants."""
        self._stop_worker()
        planned = planned_items(self.files, self.config_snapshot)
        ordered_keys = merge_order(order, planned)
        by_key = {item_key(path, kind): (path, kind) for path, kind in planned}

        signature = render_signature(self.config_snapshot)
        self.tiles = []
        pending: Dict[Path, List[str]] = {}
        for key in ordered_keys:
            path, kind = by_key[key]
            tile = Tile(key, path, kind, excluded=key in self.excluded)
            cached = self.cache.get(self._cache_key(key, path))
            if cached and cached[0] == signature:
                self._set_thumb(tile, cached[1])
            else:
                pending.setdefault(path, []).append(key)
            self.tiles.append(tile)
        self.excluded &= {tile.key for tile in self.tiles}
        self.selected = None
        self._notify()
        self.redraw()
        self._update_status()

        if pending:
            self.stop_event = threading.Event()
            self.worker = threading.Thread(
                target=self._render_worker,
                args=(list(pending), dict(self.config_snapshot), signature, self.stop_event),
                daemon=True,
            )
            self.worker.start()

    def _notify(self) -> None:
        self.on_change([tile.key for tile in self.tiles], set(self.excluded))

    def _cache_key(self, key: str, path: Path) -> str:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0
        offset = ""
        if key.endswith(f"|{KIND_CROP}"):
            offset = f"|{crop_offset_for(self.config_snapshot, path):.4f}"
        return f"{key}|{mtime}{offset}"

    def _render_worker(self, paths: List[Path], config: dict, signature: str, stop: threading.Event) -> None:
        for path in paths:
            if stop.is_set():
                return
            try:
                for kind, image in render_outputs(path, config, max_side=PREVIEW_SOURCE_SIDE):
                    thumb = image.copy()
                    thumb.thumbnail((self.TILE_W * 2, self.TILE_H * 2), Image.Resampling.LANCZOS)  # marge pour un affichage net
                    if stop.is_set():
                        return
                    self.events.put(("thumb", item_key(path, kind), path, signature, thumb))
            except Exception as exc:
                self.events.put(("error", path, str(exc) or exc.__class__.__name__))
        self.events.put(("done",))

    def _poll(self) -> None:
        if self._closing:
            return
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "thumb":
                    _, key, path, signature, thumb = event
                    self.cache[self._cache_key(key, path)] = (signature, thumb)
                    for tile in self.tiles:
                        if tile.key == key:
                            self._set_thumb(tile, thumb)
                    self.redraw()
                elif event[0] == "error":
                    _, path, message = event
                    for tile in self.tiles:
                        if tile.source == path and tile.thumb is None:
                            tile.error = message
                    self.redraw()
                self._update_status()
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _set_thumb(self, tile: Tile, thumb: Image.Image) -> None:
        fitted = thumb.copy()
        fitted.thumbnail((self.TILE_W, self.TILE_H), Image.Resampling.LANCZOS)
        tile.thumb = thumb
        tile.photo = ImageTk.PhotoImage(fitted)
        tile.error = ""

    def _stop_worker(self) -> None:
        self.stop_event.set()
        self.worker = None

    def _update_status(self) -> None:
        ready = sum(1 for tile in self.tiles if tile.thumb is not None)
        if ready < len(self.tiles) and not any(tile.error for tile in self.tiles if tile.thumb is None):
            self.status.set(t("order_rendering", done=ready, total=len(self.tiles)))
        else:
            excluded = sum(1 for tile in self.tiles if tile.excluded)
            if excluded:
                self.status.set(t("order_count_excluded", total=len(self.tiles), excluded=excluded))
            else:
                self.status.set(t("order_count", total=len(self.tiles)))

    # ------------------------------------------------------------------ actions
    def _selected_tile(self) -> Optional[Tile]:
        if self.selected is not None and 0 <= self.selected < len(self.tiles):
            return self.tiles[self.selected]
        return None

    def _update_buttons(self) -> None:
        tile = self._selected_tile()
        state = ["!disabled"] if tile else ["disabled"]
        self.view_btn.state(state)
        self.exclude_btn.state(state)
        self.crop_btn.state(["!disabled"] if tile and tile.kind == KIND_CROP and self.on_crop else ["disabled"])
        self.exclude_btn.configure(text=t("order_restore") if tile and tile.excluded else t("order_exclude"))
        if hasattr(self, "menu"):
            self.menu.entryconfigure(1, label=t("order_restore") if tile and tile.excluded else t("order_exclude"))
            self.menu.entryconfigure(
                2, state=tk.NORMAL if tile and tile.kind == KIND_CROP and self.on_crop else tk.DISABLED
            )

    def select(self, index: Optional[int]) -> None:
        self.selected = index
        self._update_buttons()
        self.redraw()

    def toggle_exclude(self) -> None:
        tile = self._selected_tile()
        if tile is None:
            return
        tile.excluded = not tile.excluded
        (self.excluded.add if tile.excluded else self.excluded.discard)(tile.key)
        self._notify()
        self._update_buttons()
        self._update_status()
        self.redraw()

    def view_selected(self) -> None:
        tile = self._selected_tile()
        if tile is None:
            return
        ImageViewer(self, tile.source, tile.kind, self.config_snapshot, dark=self.dark)

    def crop_selected(self) -> None:
        tile = self._selected_tile()
        if tile is None or tile.kind != KIND_CROP or self.on_crop is None:
            return
        source = tile.source

        def apply(offset: float) -> None:
            self.on_crop(source, offset)
            self.config_snapshot = dict(self.get_config())
            keep = tile.key
            self.start([t_.key for t_ in self.tiles])
            for index, other in enumerate(self.tiles):
                if other.key == keep:
                    self.select(index)

        CropEditor(self, source, self.config_snapshot, apply, dark=self.dark)

    def _on_double_click(self, event) -> None:
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        index = self._tile_at(x, y)
        if self._click_cross(index, x, y):  # deux clics rapides sur la croix : pas de visionneuse
            return
        if index is not None:
            self.select(index)
            if self.tiles[index].kind == KIND_CROP and self.on_crop:
                self.crop_selected()  # double-clic sur un recadrage : on règle le cadrage
            else:
                self.view_selected()

    def _on_context(self, event) -> None:
        index = self._tile_at(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if index is None:
            return
        self.select(index)
        self.menu.tk_popup(event.x_root, event.y_root)

    def refresh(self) -> None:
        self.config_snapshot = dict(self.get_config())
        self.start([tile.key for tile in self.tiles])

    def reset_order(self) -> None:
        self.start([])

    def close(self) -> None:
        self._closing = True
        self._stop_worker()
        self.destroy()

    # ------------------------------------------------------------------ drawing
    def _slot_origin(self, index: int) -> Tuple[int, int]:
        col, row = index % COLUMNS, index // COLUMNS
        return self.GAP + col * (self.TILE_W + self.GAP), self.GAP + row * (self.TILE_H + self.GAP)

    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        number = 0
        for index, tile in enumerate(self.tiles):
            if not tile.excluded:
                number += 1
            x, y = self._slot_origin(index)
            self._draw_tile(tile, index, x, y, number)
        rows = (len(self.tiles) + COLUMNS - 1) // COLUMNS
        height = self.GAP + rows * (self.TILE_H + self.GAP)
        canvas.configure(scrollregion=(0, 0, COLUMNS * self.TILE_W + (COLUMNS + 1) * self.GAP, max(height, 1)))

    def _cross_rect(self, x: int, y: int) -> Tuple[int, int, int, int]:
        """Zone cliquable de la croix (exclure / réintégrer), en haut à droite d'une tuile."""
        d, m = int(28 * self.scale), int(8 * self.scale)
        return x + self.TILE_W - m - d, y + m, x + self.TILE_W - m, y + m + d

    def _draw_tile(self, tile: Tile, index: int, x: int, y: int, number: int) -> None:
        canvas = self.canvas
        dragging = self.drag is not None and self.drag.get("moved") and self.drag["index"] == index
        canvas.create_rectangle(x, y, x + self.TILE_W, y + self.TILE_H, fill="#1e1e1e" if not self.dark else "#161616", outline="")
        if tile.photo is not None:
            canvas.create_image(x + self.TILE_W // 2, y + self.TILE_H // 2, image=tile.photo)
            if dragging:
                canvas.create_rectangle(x, y, x + self.TILE_W, y + self.TILE_H, fill="#ffffff", stipple="gray50", outline="")
        elif tile.error:
            canvas.create_text(
                x + self.TILE_W // 2, y + self.TILE_H // 2, text=t("order_error", message=tile.error),
                fill="#ff8888", width=self.TILE_W - 16, justify=tk.CENTER,
            )
        else:
            canvas.create_text(x + self.TILE_W // 2, y + self.TILE_H // 2, text="…", fill="#777777", font=("Segoe UI", 20))

        s = self.scale
        if tile.excluded:
            canvas.create_rectangle(x, y, x + self.TILE_W, y + self.TILE_H, fill="#000000", stipple="gray75", outline="")
            canvas.create_text(
                x + self.TILE_W // 2, y + self.TILE_H // 2 - int(14 * s), text="✕", fill="#ff5a5a", font=("Segoe UI", 44, "bold")
            )
            canvas.create_text(
                x + self.TILE_W // 2, y + self.TILE_H // 2 + int(26 * s), text=t("order_excluded"), fill="#ffffff",
                font=("Segoe UI", 10, "bold"),
            )
        # numéro d'ordre (celui qui préfixera le fichier) ; les images exclues ne sont pas numérotées
        m, d = int(8 * s), int(30 * s)
        badge = "#6b6b6b" if tile.excluded else "#0095f6"
        canvas.create_oval(x + m, y + m, x + m + d, y + m + d, fill=badge, outline="#ffffff", width=2)
        canvas.create_text(
            x + m + d // 2, y + m + d // 2, text="–" if tile.excluded else str(number), fill="#ffffff",
            font=("Segoe UI", 10, "bold"),
        )
        x0, y0, x1, y1 = self._cross_rect(x, y)
        canvas.create_oval(x0, y0, x1, y1, fill="#2e7d32" if tile.excluded else "#222222", outline="#ffffff", width=2)
        canvas.create_text(
            (x0 + x1) // 2, (y0 + y1) // 2, text="↺" if tile.excluded else "✕", fill="#ffffff",
            font=("Segoe UI", 11, "bold"),
        )
        if index == self.selected:
            canvas.create_rectangle(
                x + 2, y + 2, x + self.TILE_W - 2, y + self.TILE_H - 2, outline="#0095f6", width=max(3, int(4 * s))
            )
        # légende
        cap = int(36 * s)
        canvas.create_rectangle(x, y + self.TILE_H - cap, x + self.TILE_W, y + self.TILE_H, fill="#000000", stipple="gray50", outline="")
        canvas.create_text(
            x + int(8 * s), y + self.TILE_H - cap // 2, anchor=tk.W, fill="#ffffff", font=("Segoe UI", 8),
            text=f"{tile.source.name}\n{kind_label(tile.kind)}", width=self.TILE_W - int(16 * s),
        )

    # ------------------------------------------------------------------ drag and drop
    def _tile_at(self, x: float, y: float) -> Optional[int]:
        col = int((x - self.GAP) // (self.TILE_W + self.GAP))
        row = int((y - self.GAP) // (self.TILE_H + self.GAP))
        if not 0 <= col < COLUMNS or row < 0:
            return None
        index = row * COLUMNS + col
        return index if index < len(self.tiles) else None

    def _slot_at(self, x: float, y: float) -> int:
        col = min(COLUMNS - 1, max(0, int((x - self.GAP) // (self.TILE_W + self.GAP))))
        row = max(0, int((y - self.GAP) // (self.TILE_H + self.GAP)))
        return min(len(self.tiles) - 1, row * COLUMNS + col)

    def _click_cross(self, index: Optional[int], x: float, y: float) -> bool:
        """Si le clic tombe sur la croix d'une tuile, l'exclut / la réintègre et renvoie True."""
        if index is None:
            return False
        cx0, cy0, cx1, cy1 = self._cross_rect(*self._slot_origin(index))
        if cx0 <= x <= cx1 and cy0 <= y <= cy1:
            self.select(index)
            self.toggle_exclude()
            return True
        return False

    def _on_press(self, event) -> None:
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        index = self._tile_at(x, y)
        if self._click_cross(index, x, y):
            self.drag = None
            return
        self.drag = None if index is None else {"index": index, "x0": event.x, "y0": event.y, "moved": False}

    def _on_motion(self, event) -> None:
        if not self.drag:
            return
        if not self.drag["moved"]:
            if abs(event.x - self.drag["x0"]) + abs(event.y - self.drag["y0"]) < DRAG_THRESHOLD:
                return
            self.drag["moved"] = True
            self.redraw()
        canvas = self.canvas
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        canvas.delete("ghost")
        tile = self.tiles[self.drag["index"]]
        if tile.photo is not None:
            canvas.create_image(x, y, image=tile.photo, tags="ghost")
            canvas.create_rectangle(
                x - self.TILE_W // 2, y - self.TILE_H // 2, x + self.TILE_W // 2, y + self.TILE_H // 2,
                outline="#0095f6", width=3, tags="ghost",
            )
        target = self._slot_at(x, y)
        self.drag["target"] = target
        tx, ty = self._slot_origin(target)
        canvas.delete("slot")
        canvas.create_rectangle(tx, ty, tx + self.TILE_W, ty + self.TILE_H, outline="#ffb400", width=4, tags="slot")
        canvas.tag_raise("ghost")
        # défilement automatique près des bords
        if event.y < 30:
            canvas.yview_scroll(-1, "units")
        elif event.y > canvas.winfo_height() - 30:
            canvas.yview_scroll(1, "units")

    def _on_release(self, event) -> None:
        drag, self.drag = self.drag, None
        if not drag:
            return
        if not drag["moved"]:
            self.select(drag["index"])
            return
        source, target = drag["index"], drag.get("target", drag["index"])
        if source != target:
            tile = self.tiles.pop(source)
            self.tiles.insert(target, tile)
            self.selected = target
            self._notify()
        self.redraw()

    def _on_wheel(self, event) -> None:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

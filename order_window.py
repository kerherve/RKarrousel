#!/usr/bin/env python3
"""Fenêtre « grille Instagram » : aperçu du rendu final de chaque image de sortie, réordonnable
par glisser-déposer. L'ordre sert ensuite à numéroter les fichiers (01_, 02_…)."""
import json
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageTk

from i18n import kind_label, t
from utils import item_key, merge_order, planned_items, render_outputs

COLUMNS = 3
TILE_W = 210
TILE_H = 280  # 3:4, comme la grille de profil Instagram
GAP = 4
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


class OrderWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        files: Sequence[Path],
        config: dict,
        order: Sequence[str],
        cache: Dict[str, Tuple[str, Image.Image]],
        on_change: Callable[[List[str]], None],
        get_config: Callable[[], dict],
    ):
        super().__init__(parent)
        self.title(t("order_title"))
        self.files = list(files)
        self.config_snapshot = dict(config)
        self.cache = cache  # key -> (empreinte, miniature), partagé entre ouvertures
        self.on_change = on_change
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
        canvas_width = COLUMNS * TILE_W + (COLUMNS + 1) * GAP
        self.geometry(f"{canvas_width + 40}x760")
        self.minsize(canvas_width + 40, 420)

        toolbar = tk.Frame(self, padx=8, pady=6)
        toolbar.pack(fill=tk.X)
        tk.Button(toolbar, text=t("order_refresh"), command=self.refresh).pack(side=tk.LEFT)
        tk.Button(toolbar, text=t("order_reset"), command=self.reset_order).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(toolbar, text=t("order_close"), command=self.close).pack(side=tk.RIGHT)

        self.hint = tk.Label(self, text=t("order_hint"), anchor=tk.W, justify=tk.LEFT, wraplength=canvas_width, padx=8)
        self.hint.pack(fill=tk.X)
        self.status = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status, anchor=tk.W, padx=8, fg="#555555").pack(fill=tk.X)

        body = tk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 8))
        self.canvas = tk.Canvas(body, width=canvas_width, bg="#ffffff", highlightthickness=1, highlightbackground="#bbbbbb")
        scrollbar = tk.Scrollbar(body, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
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
            tile = Tile(key, path, kind)
            cached = self.cache.get(self._cache_key(key, path))
            if cached and cached[0] == signature:
                self._set_thumb(tile, cached[1])
            else:
                pending.setdefault(path, []).append(key)
            self.tiles.append(tile)
        self.on_change([tile.key for tile in self.tiles])
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

    def _cache_key(self, key: str, path: Path) -> str:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0
        return f"{key}|{mtime}"

    def _render_worker(self, paths: List[Path], config: dict, signature: str, stop: threading.Event) -> None:
        for path in paths:
            if stop.is_set():
                return
            try:
                for kind, image in render_outputs(path, config, max_side=PREVIEW_SOURCE_SIDE):
                    thumb = image.copy()
                    thumb.thumbnail((TILE_W * 2, TILE_H * 2), Image.Resampling.LANCZOS)  # marge pour un affichage net
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
        fitted.thumbnail((TILE_W, TILE_H), Image.Resampling.LANCZOS)
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
            self.status.set(t("order_count", total=len(self.tiles)))

    # ------------------------------------------------------------------ actions
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
        return GAP + col * (TILE_W + GAP), GAP + row * (TILE_H + GAP)

    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        for index, tile in enumerate(self.tiles):
            x, y = self._slot_origin(index)
            self._draw_tile(tile, index, x, y)
        rows = (len(self.tiles) + COLUMNS - 1) // COLUMNS
        height = GAP + rows * (TILE_H + GAP)
        canvas.configure(scrollregion=(0, 0, COLUMNS * TILE_W + (COLUMNS + 1) * GAP, max(height, 1)))

    def _draw_tile(self, tile: Tile, index: int, x: int, y: int) -> None:
        canvas = self.canvas
        dragging = self.drag is not None and self.drag.get("moved") and self.drag["index"] == index
        canvas.create_rectangle(x, y, x + TILE_W, y + TILE_H, fill="#1e1e1e", outline="")
        if tile.photo is not None:
            canvas.create_image(x + TILE_W // 2, y + TILE_H // 2, image=tile.photo)
            if dragging:
                canvas.create_rectangle(x, y, x + TILE_W, y + TILE_H, fill="#ffffff", stipple="gray50", outline="")
        elif tile.error:
            canvas.create_text(
                x + TILE_W // 2, y + TILE_H // 2, text=t("order_error", message=tile.error),
                fill="#ff8888", width=TILE_W - 16, justify=tk.CENTER,
            )
        else:
            canvas.create_text(x + TILE_W // 2, y + TILE_H // 2, text="…", fill="#aaaaaa", font=("Segoe UI", 20))

        # numéro d'ordre (celui qui préfixera le fichier)
        canvas.create_oval(x + 6, y + 6, x + 34, y + 34, fill="#0095f6", outline="#ffffff", width=2)
        canvas.create_text(x + 20, y + 20, text=str(index + 1), fill="#ffffff", font=("Segoe UI", 10, "bold"))
        # légende
        canvas.create_rectangle(x, y + TILE_H - 34, x + TILE_W, y + TILE_H, fill="#000000", stipple="gray50", outline="")
        canvas.create_text(
            x + 6, y + TILE_H - 17, anchor=tk.W, fill="#ffffff", font=("Segoe UI", 8),
            text=f"{tile.source.name}\n{kind_label(tile.kind)}", width=TILE_W - 12,
        )

    # ------------------------------------------------------------------ drag and drop
    def _tile_at(self, x: float, y: float) -> Optional[int]:
        col = int((x - GAP) // (TILE_W + GAP))
        row = int((y - GAP) // (TILE_H + GAP))
        if not 0 <= col < COLUMNS or row < 0:
            return None
        index = row * COLUMNS + col
        return index if index < len(self.tiles) else None

    def _slot_at(self, x: float, y: float) -> int:
        col = min(COLUMNS - 1, max(0, int((x - GAP) // (TILE_W + GAP))))
        row = max(0, int((y - GAP) // (TILE_H + GAP)))
        return min(len(self.tiles) - 1, row * COLUMNS + col)

    def _on_press(self, event) -> None:
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        index = self._tile_at(x, y)
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
                x - TILE_W // 2, y - TILE_H // 2, x + TILE_W // 2, y + TILE_H // 2,
                outline="#0095f6", width=3, tags="ghost",
            )
        target = self._slot_at(x, y)
        self.drag["target"] = target
        tx, ty = self._slot_origin(target)
        canvas.delete("slot")
        canvas.create_rectangle(tx, ty, tx + TILE_W, ty + TILE_H, outline="#ffb400", width=4, tags="slot")
        canvas.tag_raise("ghost")
        # défilement automatique près des bords
        if event.y < 30:
            canvas.yview_scroll(-1, "units")
        elif event.y > canvas.winfo_height() - 30:
            canvas.yview_scroll(1, "units")

    def _on_release(self, event) -> None:
        drag, self.drag = self.drag, None
        if not drag or not drag["moved"]:
            return
        source, target = drag["index"], drag.get("target", drag["index"])
        if source != target:
            tile = self.tiles.pop(source)
            self.tiles.insert(target, tile)
            self.on_change([tile.key for tile in self.tiles])
        self.redraw()

    def _on_wheel(self, event) -> None:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

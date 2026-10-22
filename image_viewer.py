#!/usr/bin/env python3
"""Visionneuse d'une image de sortie, en pleine résolution : zoom, déplacement et règle pour mesurer
(par exemple l'épaisseur du cadre blanc)."""
import math
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Optional

from PIL import Image, ImageTk

from i18n import kind_label, t
from utils import background_color_of, border_color_of, measure_border, render_output

MIN_SCALE = 0.02
MAX_SCALE = 32.0
ZOOM_STEP = 1.25


class ImageViewer(tk.Toplevel):
    def __init__(self, parent: tk.Misc, source: Path, kind: str, config: dict, dark: bool = False):
        super().__init__(parent)
        self.title(f"{source.name} — {kind_label(kind)}")
        self.source, self.kind, self.config_snapshot = source, kind, dict(config)
        self.scale_ui = max(1.0, self.winfo_fpixels("1i") / 96)
        self.bg = "#111111" if dark else "#2b2b2b"

        self.image: Optional[Image.Image] = None
        self.photo: Optional[ImageTk.PhotoImage] = None
        self.zoom = 1.0
        self.ox = 0.0  # coin haut-gauche de la zone visible, en pixels de l'image
        self.oy = 0.0
        self.fit_mode = True
        self.pan: Optional[tuple] = None
        self.ruler: Optional[tuple] = None
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self._closing = False

        self._build_ui()
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self._load, daemon=True).start()
        self.after(80, self._poll)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        s = self.scale_ui
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(int(980 * s), screen_w - 60), min(int(860 * s), screen_h - 120)
        self.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 2 - 30)}")
        self.minsize(int(480 * s), int(360 * s))

        frame = ttk.Frame(self, padding=(12, 10, 12, 10))
        frame.pack(fill=tk.BOTH, expand=True)

        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(bar, text=t("viewer_fit"), command=self.fit).pack(side=tk.LEFT)
        ttk.Button(bar, text=t("viewer_100"), command=lambda: self.set_zoom(1.0)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(bar, text="−", width=3, command=lambda: self.zoom_by(1 / ZOOM_STEP)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(bar, text="+", width=3, command=lambda: self.zoom_by(ZOOM_STEP)).pack(side=tk.LEFT, padx=(6, 0))
        self.zoom_label = ttk.Label(bar, text="")
        self.zoom_label.pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(bar, text=t("order_close"), command=self.close).pack(side=tk.RIGHT)

        self.info = tk.StringVar(value=t("viewer_loading"))
        ttk.Label(frame, textvariable=self.info).pack(fill=tk.X)
        self.measure = tk.StringVar(value=t("viewer_hint"))
        ttk.Label(frame, textvariable=self.measure, style="Hint.TLabel").pack(fill=tk.X, pady=(2, 8))

        self.canvas = tk.Canvas(frame, bg=self.bg, highlightthickness=0, cursor="fleur")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self._on_resize())
        self.canvas.bind("<ButtonPress-1>", self._pan_start)
        self.canvas.bind("<B1-Motion>", self._pan_move)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "pan", None))
        self.canvas.bind("<ButtonPress-3>", self._ruler_start)
        self.canvas.bind("<B3-Motion>", self._ruler_move)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, ZOOM_STEP))
        self.canvas.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 1 / ZOOM_STEP))

    # ------------------------------------------------------------------ chargement
    def _load(self) -> None:
        try:
            image = render_output(self.source, self.config_snapshot, self.kind)
            self.events.put(("image", image))
        except Exception as exc:
            self.events.put(("error", str(exc) or exc.__class__.__name__))

    def _poll(self) -> None:
        if self._closing:
            return
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "image" and event[1] is not None:
                    self.image = event[1].convert("RGB")
                    self._describe()
                    self.fit()
                elif event[0] == "error":
                    self.info.set(t("order_error", message=event[1]))
                else:
                    self.info.set(t("order_error", message="?"))
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _describe(self) -> None:
        assert self.image is not None
        width, height = self.image.size
        border = measure_border(
            self.image, border_color_of(self.config_snapshot), skip_color=background_color_of(self.config_snapshot)
        )
        if border:
            percent = 100 * border / min(width, height)
            self.info.set(t("viewer_info", width=width, height=height, border=border, percent=percent))
        else:
            self.info.set(t("viewer_info_noborder", width=width, height=height))

    # ------------------------------------------------------------------ zoom / déplacement
    def _viewport(self) -> tuple:
        return max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())

    def fit(self) -> None:
        if self.image is None:
            return
        vw, vh = self._viewport()
        self.fit_mode = True
        self.zoom = min(MAX_SCALE, max(MIN_SCALE, min(vw / self.image.width, vh / self.image.height)))
        self._center()
        self.redraw()

    def _center(self) -> None:
        assert self.image is not None
        vw, vh = self._viewport()
        self.ox = self.image.width / 2 - vw / (2 * self.zoom)
        self.oy = self.image.height / 2 - vh / (2 * self.zoom)

    def set_zoom(self, zoom: float) -> None:
        if self.image is None:
            return
        vw, vh = self._viewport()
        self._zoom_at(vw / 2, vh / 2, zoom / self.zoom)

    def zoom_by(self, factor: float) -> None:
        vw, vh = self._viewport()
        self._zoom_at(vw / 2, vh / 2, factor)

    def _zoom_at(self, cx: float, cy: float, factor: float) -> None:
        if self.image is None:
            return
        new_zoom = min(MAX_SCALE, max(MIN_SCALE, self.zoom * factor))
        if new_zoom == self.zoom:
            return
        # le point sous le curseur reste fixe
        ix, iy = self.ox + cx / self.zoom, self.oy + cy / self.zoom
        self.zoom = new_zoom
        self.ox, self.oy = ix - cx / new_zoom, iy - cy / new_zoom
        self.fit_mode = False
        self.redraw()

    def _on_wheel(self, event) -> None:
        self._zoom_at(event.x, event.y, ZOOM_STEP if event.delta > 0 else 1 / ZOOM_STEP)

    def _on_resize(self) -> None:
        if self.image is None:
            return
        if self.fit_mode:
            self.fit()
        else:
            self.redraw()

    def _pan_start(self, event) -> None:
        self.pan = (event.x, event.y, self.ox, self.oy)

    def _pan_move(self, event) -> None:
        if not self.pan or self.image is None:
            return
        x0, y0, ox, oy = self.pan
        self.ox = ox - (event.x - x0) / self.zoom
        self.oy = oy - (event.y - y0) / self.zoom
        self.fit_mode = False
        self.redraw()

    # ------------------------------------------------------------------ règle
    def _ruler_start(self, event) -> None:
        self.ruler = (event.x, event.y, event.x, event.y)
        self._draw_ruler()

    def _ruler_move(self, event) -> None:
        if self.ruler:
            self.ruler = (self.ruler[0], self.ruler[1], event.x, event.y)
            self._draw_ruler()

    def _draw_ruler(self) -> None:
        self.canvas.delete("ruler")
        if not self.ruler:
            return
        x0, y0, x1, y1 = self.ruler
        self.canvas.create_line(x0, y0, x1, y1, fill="#ffb400", width=2, tags="ruler")
        for x, y in ((x0, y0), (x1, y1)):
            self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline="#ffb400", width=2, tags="ruler")
        dx, dy = abs(x1 - x0) / self.zoom, abs(y1 - y0) / self.zoom
        self.measure.set(t("viewer_measure", length=math.hypot(dx, dy), dx=dx, dy=dy))

    # ------------------------------------------------------------------ rendu
    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("img")
        self.zoom_label.configure(text=t("viewer_zoom", percent=self.zoom * 100))
        if self.image is None:
            return
        vw, vh = self._viewport()
        iw, ih = self.image.size
        # zone visible, rognée aux limites de l'image
        left, top = max(0.0, self.ox), max(0.0, self.oy)
        right, bottom = min(float(iw), self.ox + vw / self.zoom), min(float(ih), self.oy + vh / self.zoom)
        if right - left < 1e-6 or bottom - top < 1e-6:
            return
        box = (int(math.floor(left)), int(math.floor(top)), int(math.ceil(right)), int(math.ceil(bottom)))
        crop = self.image.crop(box)
        out_w = max(1, int(round((box[2] - box[0]) * self.zoom)))
        out_h = max(1, int(round((box[3] - box[1]) * self.zoom)))
        resample = Image.Resampling.NEAREST if self.zoom >= 1 else Image.Resampling.BILINEAR
        self.photo = ImageTk.PhotoImage(crop.resize((out_w, out_h), resample))
        canvas.create_image((box[0] - self.ox) * self.zoom, (box[1] - self.oy) * self.zoom, anchor=tk.NW,
                            image=self.photo, tags="img")
        canvas.tag_lower("img")
        if self.ruler:
            self._draw_ruler()

    def close(self) -> None:
        self._closing = True
        self.destroy()

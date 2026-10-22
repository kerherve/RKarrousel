#!/usr/bin/env python3
"""Éditeur de recadrage 3/4 d'un portrait 2/3 : on fait glisser le cadre 3/4 sur la photo pour choisir
la zone conservée, avec un aperçu du résultat final (cadre blanc compris)."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

from PIL import Image, ImageTk

from i18n import t
from utils import crop_box_for, crop_offset_for, frame_ratio_of, open_image, render_crop_3_4

WORK_SIDE = 1100  # la photo est réduite pour l'édition : le recadrage est relatif, le rendu reste fidèle


class CropEditor(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        source: Path,
        config: dict,
        on_apply: Callable[[float], None],
        dark: bool = False,
    ):
        super().__init__(parent)
        self.title(t("crop_title", name=source.name))
        self.source, self.config_snapshot, self.on_apply = source, dict(config), on_apply
        self.scale_ui = max(1.0, self.winfo_fpixels("1i") / 96)
        self.bg = "#111111" if dark else "#2b2b2b"
        self.offset = crop_offset_for(config, source)

        img = open_image(source).convert("RGB")
        img.thumbnail((WORK_SIDE, WORK_SIDE), Image.Resampling.LANCZOS)
        self.work = img
        self.photo: Optional[ImageTk.PhotoImage] = None
        self.preview_photo: Optional[ImageTk.PhotoImage] = None
        self.grab_dy = 0.0

        self._build_ui()
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.apply())
        for key, delta in (("Up", -0.01), ("Left", -0.01), ("Down", 0.01), ("Right", 0.01)):
            self.bind(f"<{key}>", lambda e, d=delta: self._nudge(d))
            self.bind(f"<Shift-{key}>", lambda e, d=delta: self._nudge(d * 5))
        self.transient(parent)
        self.grab_set()
        self.redraw()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        s = self.scale_ui
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        self.view_h = min(int(640 * s), screen_h - int(260 * s))
        self.view_w = int(self.view_h * self.work.width / self.work.height)
        self.disp_scale = self.view_h / self.work.height
        self.preview_h = min(int(560 * s), self.view_h)
        self.preview_w = int(self.preview_h * 3 / 4)

        width = self.view_w + self.preview_w + int(110 * s)
        height = self.view_h + int(150 * s)
        x, y = max(0, (screen_w - width) // 2), max(0, (screen_h - height) // 2 - 30)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=(16, 12, 16, 14))
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=t("crop_hint"), wraplength=width - int(60 * s)).pack(fill=tk.X, pady=(0, 10))

        row = ttk.Frame(frame)
        row.pack()
        self.canvas = tk.Canvas(row, width=self.view_w, height=self.view_h, bg=self.bg, highlightthickness=0, cursor="fleur")
        self.canvas.pack(side=tk.LEFT)
        side = ttk.Frame(row)
        side.pack(side=tk.LEFT, padx=(16, 0), anchor=tk.N)
        ttk.Label(side, text=t("crop_preview"), style="Hint.TLabel").pack(anchor=tk.W, pady=(0, 6))
        self.preview = tk.Canvas(side, width=self.preview_w, height=self.preview_h, bg=self.bg, highlightthickness=0)
        self.preview.pack()

        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(bar, text=t("crop_top"), command=lambda: self.set_offset(0.0)).pack(side=tk.LEFT)
        ttk.Button(bar, text=t("crop_center"), command=lambda: self.set_offset(0.5)).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(bar, text=t("crop_bottom"), command=lambda: self.set_offset(1.0)).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(bar, text=t("crop_apply"), command=self.apply, style="Accent.TButton").pack(side=tk.RIGHT)
        ttk.Button(bar, text=t("crop_cancel"), command=self.destroy).pack(side=tk.RIGHT, padx=(0, 8))

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<MouseWheel>", lambda e: self._nudge(-0.02 if e.delta > 0 else 0.02))
        self.canvas.bind("<Button-4>", lambda e: self._nudge(-0.02))
        self.canvas.bind("<Button-5>", lambda e: self._nudge(0.02))

    # ------------------------------------------------------------------ géométrie du cadre
    def _box(self):
        """(axe libre, largeur, hauteur) du cadre 3/4 en pixels d'affichage."""
        axis, crop_w, crop_h = crop_box_for(self.work.width, self.work.height, frame_ratio_of(self.config_snapshot))
        return axis, crop_w * self.disp_scale, crop_h * self.disp_scale

    def _free(self) -> float:
        axis, rw, rh = self._box()
        return (self.view_h - rh) if axis == "y" else (self.view_w - rw)

    def _rect_pos(self) -> float:
        return self.offset * self._free()

    def _rect_size(self) -> float:
        axis, rw, rh = self._box()
        return rh if axis == "y" else rw

    def set_offset(self, offset: float) -> None:
        self.offset = max(0.0, min(1.0, offset))
        self.redraw()

    def _nudge(self, delta: float) -> None:
        self.set_offset(self.offset + delta)

    def _coord(self, event) -> float:
        return event.y if self._box()[0] == "y" else event.x

    def _press(self, event) -> None:
        pos, size = self._rect_pos(), self._rect_size()
        # dans le cadre : on le saisit là où on a cliqué ; en dehors : il se centre sur le clic
        self.grab_dy = self._coord(event) - pos if pos <= self._coord(event) <= pos + size else size / 2
        self._drag(event)

    def _drag(self, event) -> None:
        free = self._free()
        if free <= 0:
            return
        self.set_offset((self._coord(event) - self.grab_dy) / free)

    def apply(self) -> None:
        self.on_apply(self.offset)
        self.destroy()

    # ------------------------------------------------------------------ rendu
    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        shown = self.work.resize((self.view_w, self.view_h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(shown)
        canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        axis, rw, rh = self._box()
        pos = self._rect_pos()
        shade = dict(fill="#000000", stipple="gray75", outline="")
        if axis == "y":  # zones écartées assombries, cadre pleine largeur
            canvas.create_rectangle(0, 0, self.view_w, pos, **shade)
            canvas.create_rectangle(0, pos + rh, self.view_w, self.view_h, **shade)
            canvas.create_rectangle(1, pos, self.view_w - 1, pos + rh, outline="#ffb400", width=3)
        else:            # cadre pleine hauteur, glissé horizontalement
            canvas.create_rectangle(0, 0, pos, self.view_h, **shade)
            canvas.create_rectangle(pos + rw, 0, self.view_w, self.view_h, **shade)
            canvas.create_rectangle(pos, 1, pos + rw, self.view_h - 1, outline="#ffb400", width=3)

        result = render_crop_3_4(self.work, self.config_snapshot, self.offset)
        result.thumbnail((self.preview_w, self.preview_h), Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(result)
        self.preview.delete("all")
        self.preview.create_image(self.preview_w // 2, self.preview_h // 2, image=self.preview_photo)

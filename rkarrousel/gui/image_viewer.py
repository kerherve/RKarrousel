#!/usr/bin/env python3
"""Visionneuse d'une image de sortie, en pleine résolution : zoom, déplacement et règle pour mesurer
(par exemple l'épaisseur du cadre blanc). Un panneau latéral règle le cadre et le fond sans quitter la fenêtre :
l'image se recalcule au fil des changements (les réglages sont ceux de l'onglet Réglages)."""
import math
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

from PIL import Image, ImageTk

from rkarrousel.gui.photo_frame_group import PhotoFrameGroup
from rkarrousel.gui.settings_groups import FillGroup, FrameGroup, SignatureGroup
from rkarrousel.gui.widgets import bind_trace, make_scrollable
from rkarrousel.i18n import kind_label, t
from rkarrousel.imaging.colors import resolve_photo_colors_for_path
from rkarrousel.config import background_color_of, border_color_of, config_for_photo
from rkarrousel.imaging.frames import measure_border
from rkarrousel.outputs import kind_features, render_output
from rkarrousel.pipeline import peek_size

MIN_SCALE = 0.02
MAX_SCALE = 32.0
ZOOM_STEP = 1.25
NEIGHBOR_SIDE = 1400  # les voisines du carrousel sont rendues à partir d'une source réduite : c'est un simple aperçu
CAROUSEL_GAP = 0.02   # écart entre deux images du carrousel, en fraction de la largeur
MAX_NEIGHBOR_DISPLAY = 2600  # au-delà (zoom fort), on ne dessine plus les voisines
RERENDER_DELAY_MS = 450  # on attend la fin de la frappe / du geste avant de recalculer l'image en pleine résolution


class ImageViewer(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        source: Path,
        kind: str,
        config: dict,
        dark: bool = False,
        ctx=None,
        on_settings_changed: Optional[Callable[[], None]] = None,
        navigator=None,
    ):
        """`ctx` (AppContext) active le panneau de réglages ; `on_settings_changed` est appelé à la fermeture si
        des réglages ont été modifiés (pour rafraîchir la grille d'ordre). `navigator` (la grille d'ordre) permet de
        passer à l'image suivante ou précédente : `viewer_step(±1)` renvoie la vignette voulue, `viewer_position()`
        le rang (n, total)."""
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
        self.ctx, self.on_settings_changed, self.navigator = ctx, on_settings_changed, navigator
        self.generation = 0  # numéro du dernier rendu demandé : les résultats plus anciens sont ignorés
        self.loaded_once = False
        self.settings_changed = False
        self.neighbors = {-1: None, 1: None}  # images voisines (PIL), pour l'aperçu en carrousel
        self._neighbor_photos = {}
        self._rerender_job = None

        self._build_ui()
        self.bind("<Escape>", lambda e: self.close())
        if navigator is not None:
            self.bind("<Left>", lambda e: self._key_step(-1))
            self.bind("<Right>", lambda e: self._key_step(1))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._launch(self.generation, dict(config))
        self.after(80, self._poll)
        self._update_position()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        s = self.scale_ui
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        wide = int(500 * s) if self.ctx is not None else 0  # place du panneau de réglages
        width, height = min(int(980 * s) + wide, screen_w - 60), min(int(860 * s), screen_h - 120)
        self.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 2 - 30)}")
        self.minsize(int(480 * s), int(360 * s))

        body = ttk.Frame(self, padding=(12, 10, 12, 10))
        body.pack(fill=tk.BOTH, expand=True)
        self.side = None
        if self.ctx is not None:
            self.side = self._build_settings_panel(body)
            self.side.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        frame = self.main = ttk.Frame(body)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(bar, text=t("viewer_fit"), command=self.fit).pack(side=tk.LEFT)
        ttk.Button(bar, text=t("viewer_100"), command=lambda: self.set_zoom(1.0)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(bar, text="−", width=3, command=lambda: self.zoom_by(1 / ZOOM_STEP)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(bar, text="+", width=3, command=lambda: self.zoom_by(ZOOM_STEP)).pack(side=tk.LEFT, padx=(6, 0))
        self.zoom_label = ttk.Label(bar, text="")
        self.zoom_label.pack(side=tk.LEFT, padx=(12, 0))
        self.position_label = ttk.Label(bar, text="")
        self.position_label.pack(side=tk.LEFT, padx=(16, 0))
        self.carousel = tk.BooleanVar(value=True)
        if self.navigator is not None:
            ttk.Checkbutton(bar, text=t("viewer_carousel"), variable=self.carousel, command=self.redraw).pack(
                side=tk.LEFT, padx=(16, 0))
        ttk.Button(bar, text=t("order_close"), command=self.close).pack(side=tk.RIGHT)
        if self.side is not None:
            self.settings_button = ttk.Button(bar, text=t("viewer_settings"), command=self.toggle_settings)
            self.settings_button.pack(side=tk.RIGHT, padx=(0, 8))

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
        self.canvas.tag_bind("nav_prev", "<ButtonPress-1>", lambda e: self.step(-1))
        self.canvas.tag_bind("nav_next", "<ButtonPress-1>", lambda e: self.step(1))
        self._update_position()

    def _build_settings_panel(self, parent: tk.Misc) -> ttk.Frame:
        """Cadre et fond : les mêmes groupes que l'onglet Réglages, branchés sur les mêmes variables."""
        model = self.ctx.model
        side = ttk.Frame(parent, width=int(480 * self.scale_ui))
        side.pack_propagate(False)  # largeur fixe ; le panneau défile quand la fenêtre est trop basse
        inner = make_scrollable(side, ttk.Style().lookup("TFrame", "background") or self.bg)
        inner.configure(padding=(0, 0, 8, 0))
        FrameGroup(inner, self.ctx).pack(fill=tk.X)
        self.photo_group = PhotoFrameGroup(inner, self.ctx, self.source, self._schedule_rerender)
        self.photo_group.pack(fill=tk.X, pady=(10, 0))
        self.fill_group = FillGroup(inner, self.ctx)
        self.signature_group = SignatureGroup(inner, self.ctx)
        self.fill_group.pack(fill=tk.X, pady=(10, 0))
        self.signature_group.pack(fill=tk.X, pady=(10, 0))
        self._apply_features()
        ttk.Label(inner, text=t("viewer_settings_hint"), style="Hint.TLabel", wraplength=int(430 * self.scale_ui),
                  justify=tk.LEFT).pack(fill=tk.X, pady=(10, 0))
        for variable in (
            model.frame_percent, model.no_frame, model.border_color, model.border_color_mode,
            model.landscape_fill_mode, model.background_color, model.background_color_mode, model.blur_strength,
            model.signature_path, model.signature_position, model.signature_scale, model.color_source,
        ):
            bind_trace(side, variable, self._schedule_rerender)
        return side

    def _apply_features(self) -> None:
        """Grise ce que l'image affichée n'utilise pas (fond, signature)."""
        features = self._features()
        self.fill_group.set_applicable("fill" in features)
        self.signature_group.set_applicable("signature" in features)

    def _features(self) -> frozenset:
        try:
            return kind_features(*peek_size(self.source), self.kind, self.config_snapshot)
        except Exception:
            return frozenset({"fill", "signature"})  # illisible : on ne grise rien

    def toggle_settings(self) -> None:
        if self.side.winfo_ismapped():
            self.side.pack_forget()
        else:
            self.side.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0), before=self.main)

    def _schedule_rerender(self) -> None:
        if self._closing:
            return
        if self._rerender_job is not None:
            self.after_cancel(self._rerender_job)
        self._rerender_job = self.after(RERENDER_DELAY_MS, self._rerender)

    def _rerender(self) -> None:
        self._rerender_job = None
        if self._closing:
            return
        try:
            config = dict(self.ctx.collect_config())
        except Exception:  # saisie en cours (champ vide…) : on attend la prochaine modification
            return
        self.config_snapshot = config
        self.settings_changed = True
        self.generation += 1
        self.info.set(t("viewer_loading"))
        self._launch(self.generation, config)

    # ------------------------------------------------------------------ chargement
    def _launch(self, generation: int, config: dict) -> None:
        """Calcule l'image affichée (pleine résolution) et, en réduit, ses voisines de la grille (carrousel)."""
        threading.Thread(target=self._load, args=(generation, config), daemon=True).start()
        peeks = {}
        if self.navigator is not None:
            for delta in (-1, 1):
                tile = self.navigator.viewer_peek(delta)
                if tile is not None:
                    peeks[delta] = (tile.source, tile.kind)
        for delta in (-1, 1):
            if delta not in peeks:
                self.neighbors[delta] = None
        if peeks:
            threading.Thread(target=self._load_neighbors, args=(generation, config, peeks), daemon=True).start()

    def _load_neighbors(self, generation: int, config: dict, peeks: dict) -> None:
        for delta, (source, kind) in peeks.items():
            try:
                image = render_output(source, config, kind, max_side=NEIGHBOR_SIDE)
            except Exception:
                image = None
            self.events.put(("neighbor", (delta, image), generation))

    def _load(self, generation: int, config: dict) -> None:
        try:
            image = render_output(self.source, config, self.kind)
            self.events.put(("image", image, generation))
        except Exception as exc:
            self.events.put(("error", str(exc) or exc.__class__.__name__, generation))

    def _poll(self) -> None:
        if self._closing:
            return
        try:
            while True:
                event = self.events.get_nowait()
                if event[2] != self.generation:
                    continue  # résultat d'un rendu déjà remplacé par un réglage plus récent
                if event[0] == "neighbor":
                    delta, image = event[1]
                    self.neighbors[delta] = image.convert("RGB") if image is not None else None
                    self._neighbor_photos.pop(delta, None)
                    if self.image is not None:
                        self.redraw()
                    continue
                if event[0] == "image" and event[1] is not None:
                    self.image = event[1].convert("RGB")
                    self._describe()
                    if self.loaded_once:
                        self.redraw()  # on garde le zoom et la position pendant qu'on règle
                    else:
                        self.loaded_once = True
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
        config = resolve_photo_colors_for_path(self.source, config_for_photo(self.config_snapshot, self.source))  # couleurs « de la photo » comprises
        if self.side is not None:
            self.photo_group.show_resolved(border_color_of(config))
        border = measure_border(self.image, border_color_of(config), skip_color=background_color_of(config))
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
        self._draw_nav()
        if self.image is None:
            return
        if self.fit_mode:
            self.fit()
        else:
            self.redraw()

    def _pan_start(self, event) -> None:
        if "nav" in self.canvas.gettags("current"):
            return  # clic sur une flèche de navigation
        self.pan = (event.x, event.y, self.ox, self.oy)

    def _pan_move(self, event) -> None:
        if not self.pan or self.image is None:
            return
        x0, y0, ox, oy = self.pan
        self.ox = ox - (event.x - x0) / self.zoom
        self.oy = oy - (event.y - y0) / self.zoom
        self.fit_mode = False
        self.redraw()

    # ------------------------------------------------------------------ carrousel
    def _draw_neighbors(self) -> None:
        """Les images précédente et suivante de la grille, de part et d'autre de l'image affichée, comme quand on fait
        défiler un post Instagram : on juge le rendu d'ensemble (tranches d'un panorama qui se raccordent…)."""
        if self.navigator is None or not self.carousel.get() or self.image is None:
            return
        iw, ih = self.image.size
        if iw * self.zoom > MAX_NEIGHBOR_DISPLAY:
            return
        vw, vh = self._viewport()
        gap = iw * CAROUSEL_GAP
        for delta in (-1, 1):
            image = self.neighbors.get(delta)
            if image is None:
                continue
            dw = max(1, int(round(iw * self.zoom)))
            dh = max(1, int(round(dw * image.height / image.width)))
            x = ((-(gap + iw) if delta < 0 else iw + gap) - self.ox) * self.zoom
            y = -self.oy * self.zoom
            if x + dw < 0 or x > vw or y + dh < 0 or y > vh:
                continue  # hors de la zone visible
            cached = self._neighbor_photos.get(delta)
            if cached is None or cached[0] != (dw, dh):
                resized = image.resize((dw, dh), Image.Resampling.BILINEAR)
                cached = ((dw, dh), ImageTk.PhotoImage(resized))
                self._neighbor_photos[delta] = cached
            self.canvas.create_image(x, y, anchor=tk.NW, image=cached[1], tags="neigh")
        self.canvas.tag_lower("neigh")

    # ------------------------------------------------------------------ navigation entre les images
    def _draw_nav(self) -> None:
        """Flèches rondes sur les bords gauche et droit de l'image : précédente / suivante (absentes aux extrémités)."""
        canvas = self.canvas
        canvas.delete("nav")
        if self.navigator is None:
            return
        vw, vh = self._viewport()
        s = self.scale_ui
        radius = int(24 * s)
        for delta, tag, x, symbol in ((-1, "nav_prev", radius + int(10 * s), "‹"),
                                       (1, "nav_next", vw - radius - int(10 * s), "›")):
            if not self.navigator.viewer_can_step(delta):
                continue
            y = vh // 2
            canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#202020", outline="#9a9a9a",
                               width=2, tags=("nav", tag))
            canvas.create_text(x, y - int(3 * s), text=symbol, fill="#ffffff", font=("Segoe UI", int(24 * s), "bold"),
                               tags=("nav", tag))
        canvas.tag_raise("nav")
        canvas.configure(cursor="fleur")
        for tag in ("nav_prev", "nav_next"):
            canvas.tag_bind(tag, "<Enter>", lambda e: canvas.configure(cursor="hand2"))
            canvas.tag_bind(tag, "<Leave>", lambda e: canvas.configure(cursor="fleur"))

    def _update_position(self) -> None:
        if self.navigator is None:
            return
        number, total = self.navigator.viewer_position()
        self.position_label.configure(text=f"{number} / {total}" if total else "")

    def _key_step(self, delta: int) -> None:
        """Flèches du clavier : on n'intercepte pas la frappe quand on édite un champ du panneau de réglages."""
        try:
            focused = self.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Spinbox, ttk.Spinbox, ttk.Combobox)):
            return
        self.step(delta)

    def step(self, delta: int) -> None:
        tile = self.navigator.viewer_step(delta) if self.navigator is not None else None
        if tile is not None:
            self.show(tile.source, tile.kind)

    def show(self, source: Path, kind: str) -> None:
        """Affiche une autre image dans la même fenêtre (zoom et règle repartent de zéro)."""
        if self._rerender_job is not None:
            self.after_cancel(self._rerender_job)
            self._rerender_job = None
        self.source, self.kind = source, kind
        self.title(f"{source.name} — {kind_label(kind)}")
        self.image = self.photo = None
        self.loaded_once = False
        self.ruler = self.pan = None
        self.fit_mode = True
        self.neighbors = {-1: None, 1: None}
        self._neighbor_photos = {}
        self.canvas.delete("img", "neigh", "ruler")
        self.measure.set(t("viewer_hint"))
        self.info.set(t("viewer_loading"))
        self.config_snapshot = dict(self.ctx.collect_config()) if self.ctx is not None else self.config_snapshot
        if self.side is not None:
            self.photo_group.set_source(source)
            self._apply_features()
        self.generation += 1
        self._launch(self.generation, dict(self.config_snapshot))
        self._update_position()
        self._draw_nav()

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
        canvas.delete("img", "neigh")
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
        self._draw_neighbors()
        if self.ruler:
            self._draw_ruler()
        canvas.tag_raise("nav")

    def close(self) -> None:
        self._closing = True
        changed = self.settings_changed and self.on_settings_changed is not None
        self.destroy()
        if changed:
            self.on_settings_changed()

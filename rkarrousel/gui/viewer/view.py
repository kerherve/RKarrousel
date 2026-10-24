"""Étape « Ajustements » : l'image de sortie en pleine résolution, avec zoom, déplacement et règle pour mesurer
(par exemple l'épaisseur du cadre). Un panneau latéral règle le cadre et le fond, et un carrousel montre les images
voisines de la grille comme sur un post Instagram.

Les pièces vivent à côté : `viewport` (zoom), `render_jobs` (calculs en arrière-plan), `carousel`, `ruler` et
`settings_panel`. Cette classe les assemble."""
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

from PIL import Image, ImageTk

from rkarrousel.gui.viewer.carousel import CAROUSEL_GAP, Carousel
from rkarrousel.gui.viewer.frame_report import report_for
from rkarrousel.gui.viewer.loader import ImageLoader
from rkarrousel.gui.viewer.render_jobs import NEIGHBOR_SIDE
from rkarrousel.gui.viewer.ruler import Ruler
from rkarrousel.gui.viewer.settings_panel import SettingsPanel
from rkarrousel.gui.viewer.toolbar import ViewerToolbar
from rkarrousel.gui.viewer.viewport import ZOOM_STEP, Viewport
from rkarrousel.i18n import kind_label, t
from rkarrousel.kinds import KIND_CROP
from rkarrousel.outputs import kind_features
from rkarrousel.pipeline import peek_size

FULL_RES_DELAY_MS = 250  # en feuilletant, la pleine résolution n'est calculée qu'une fois qu'on s'arrête
RERENDER_DELAY_MS = 450  # on attend la fin de la frappe / du geste avant de recalculer l'image en pleine résolution


class ViewerView(ttk.Frame):
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
        """`ctx` (AppContext) active le panneau de réglages ; `on_settings_changed` est appelé par `flush_changes()`
        (en quittant l'étape) si des réglages ont été modifiés, pour rafraîchir la grille d'ordre. `navigator` (la grille
        d'ordre) donne les images voisines : `viewer_peek(±1)`, `viewer_step(±1)`, `viewer_can_step(±1)`,
        `viewer_preview(tuile, config)`, `viewer_crop(parent, quand_validé)` et `viewer_position()`."""
        super().__init__(parent)
        self.source, self.kind, self.config_snapshot = source, kind, dict(config)
        self.scale_ui = max(1.0, self.winfo_fpixels("1i") / 96)
        self.bg = "#111111" if dark else "#2b2b2b"
        self.ctx, self.on_settings_changed, self.navigator = ctx, on_settings_changed, navigator

        self.image: Optional[Image.Image] = None
        self.photo: Optional[ImageTk.PhotoImage] = None
        self.view = Viewport()
        self.pan: Optional[tuple] = None
        self.loaded_once = False
        self.placeholder = False  # l'image affichée est un aperçu réduit, la pleine résolution arrive
        self.settings_changed = False
        self._closing = False
        self._rerender_job = None
        self._full_job = None
        self.loader: Optional[ImageLoader] = None

        self.panel: Optional[SettingsPanel] = None
        self._build_ui()
        if self.panel is not None:
            self.panel.apply_features(self._features())  # grise ce que cette image n'utilise pas
        self.ruler = Ruler(self.canvas, self.measure, lambda: self.view.zoom)
        self.carousel = Carousel(self.canvas, navigator, self.scale_ui, self._slide_distance, self._commit_step)
        self.loader = ImageLoader(self, navigator, self.carousel, self._show_rendered, self._show_error, self._neighbor_arrived)
        self._finish_toolbar()
        self._bind_events()
        self._keys = []  # liaisons clavier de l'étape (voir `activate`)
        self.bind("<Destroy>", lambda e: self._on_destroy() if e.widget is self else None, add="+")
        self._launch(main=True, keep_neighbors=False)
        self.loader.start_polling()

    # ------------------------------------------------------------------ interface
    def _build_ui(self) -> None:
        body = self
        if self.ctx is not None:
            self.panel = SettingsPanel(body, self.ctx, self.source, self.scale_ui, self.bg, self._schedule_rerender)
            self.panel.frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        self.main = ttk.Frame(body)
        self.main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_toolbar(self.main)

        self.caption = tk.StringVar(value=self._caption())
        ttk.Label(self.main, textvariable=self.caption, font=("Segoe UI", 11, "bold")).pack(fill=tk.X)
        self.info = tk.StringVar(value=t("viewer_loading"))
        ttk.Label(self.main, textvariable=self.info).pack(fill=tk.X)
        self.measure = tk.StringVar(value=t("viewer_hint"))
        ttk.Label(self.main, textvariable=self.measure, style="Hint.TLabel").pack(fill=tk.X, pady=(2, 8))
        self.canvas = tk.Canvas(self.main, bg=self.bg, highlightthickness=0, cursor="fleur")
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _build_toolbar(self, parent: ttk.Frame) -> None:
        self.toolbar = ViewerToolbar(
            parent, self.fit, lambda: self.set_zoom(1.0), self.zoom_by,
            on_toggle_settings=(lambda: self.panel.toggle(self.main)) if self.panel is not None else None,
            on_crop=self._open_crop if self.navigator is not None else None,
        )
        self.toolbar.pack(fill=tk.X, pady=(0, 8))

    def _finish_toolbar(self) -> None:
        """Éléments qui dépendent du carrousel, créé après la barre."""
        if self.navigator is not None:
            self.toolbar.add_carousel_toggle(self.carousel.enabled, self.redraw)
        self._update_position()
        self._update_crop_button()

    def _bind_events(self) -> None:
        canvas = self.canvas
        canvas.bind("<Configure>", lambda e: self._on_resize())
        canvas.bind("<ButtonPress-1>", self._press)
        canvas.bind("<B1-Motion>", self._drag)
        canvas.bind("<ButtonRelease-1>", self._release)
        canvas.bind("<ButtonPress-3>", lambda e: self.ruler.start(e.x, e.y))
        canvas.bind("<B3-Motion>", lambda e: self.ruler.move(e.x, e.y))
        canvas.bind("<MouseWheel>", lambda e: self._zoom_at(e.x, e.y, ZOOM_STEP if e.delta > 0 else 1 / ZOOM_STEP))
        canvas.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, ZOOM_STEP))
        canvas.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 1 / ZOOM_STEP))
        canvas.tag_bind("nav_prev", "<ButtonPress-1>", lambda e: self.step(-1))
        canvas.tag_bind("nav_next", "<ButtonPress-1>", lambda e: self.step(1))

    def activate(self) -> None:
        """L'étape devient visible : ← et → feuillettent les images."""
        if self.navigator is None or self._keys:
            return
        top = self.winfo_toplevel()
        self._keys = [("<Left>", top.bind("<Left>", lambda e: self._key_step(-1), add="+")),
                      ("<Right>", top.bind("<Right>", lambda e: self._key_step(1), add="+"))]

    def deactivate(self) -> None:
        """L'étape est quittée : les touches ← et → ne sont plus à nous."""
        top = self.winfo_toplevel()
        for sequence, _ in self._keys:
            top.unbind(sequence)
        self._keys = []

    def _caption(self) -> str:
        return f"{self.source.name} — {kind_label(self.kind)}"

    # ------------------------------------------------------------------ calcul de l'image
    def _launch(self, main: bool, keep_neighbors: bool) -> None:
        self.loader.launch(self.source, self.kind, self.config_snapshot, main, keep_neighbors)

    def _neighbor_arrived(self) -> None:
        if self.image is not None:
            self.redraw()

    def _show_error(self, message: str) -> None:
        self.info.set(t("order_error", message=message))

    def _show_rendered(self, image: Image.Image) -> None:
        self.image = image
        self._describe()
        if self.placeholder:
            self.placeholder = False
            self.fit()  # même taille d'affichage que l'aperçu réduit : la netteté arrive sans saut
        elif self.loaded_once:
            self.redraw()  # on garde le zoom et la position pendant qu'on règle
        else:
            self.loaded_once = True
            self.fit()

    def _describe(self) -> None:
        """Dimensions, couleur du cadre obtenue et épaisseur mesurée dans l'image."""
        assert self.image is not None
        report = report_for(self.image, self.source, self.config_snapshot)
        if self.panel is not None:
            self.panel.show_resolved(report.color)
        if report.border:
            self.info.set(t("viewer_info", width=report.width, height=report.height, border=report.border,
                            percent=report.percent))
        else:
            self.info.set(t("viewer_info_noborder", width=report.width, height=report.height))

    # ------------------------------------------------------------------ réglages en direct
    def _features(self) -> frozenset:
        try:
            return kind_features(*peek_size(self.source), self.kind, self.config_snapshot)
        except Exception:
            return frozenset({"fill", "signature"})  # illisible : on ne grise rien

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
        self.info.set(t("viewer_loading"))
        self._launch(main=True, keep_neighbors=False)

    # ------------------------------------------------------------------ zoom / déplacement
    def _view_size(self) -> tuple:
        return max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())

    def fit(self) -> None:
        if self.image is None:
            return
        self.view.fit(self.image.size, self._view_size())
        self.redraw()

    def set_zoom(self, zoom: float) -> None:
        if self.image is not None and self.view.zoom_to(zoom, self._view_size()):
            self.redraw()

    def zoom_by(self, factor: float) -> None:
        vw, vh = self._view_size()
        self._zoom_at(vw / 2, vh / 2, factor)

    def _zoom_at(self, cx: float, cy: float, factor: float) -> None:
        if self.image is not None and self.view.zoom_at(cx, cy, factor):
            self.redraw()

    def _on_resize(self) -> None:
        self.carousel.draw_arrows(self._view_size())
        if self.image is None:
            return
        if self.view.fit_mode:
            self.fit()
        else:
            self.redraw()

    def _press(self, event) -> None:
        if "nav" in self.canvas.gettags("current") or self.carousel.animating:
            return  # clic sur une flèche de navigation, ou animation en cours
        if self.navigator is not None and self.view.fit_mode:
            self.carousel.begin_swipe(event.x)  # image entière à l'écran : on fait défiler le carrousel
            return
        self.pan = (event.x, event.y, self.view.ox, self.view.oy)  # zoomée : le glisser déplace l'image

    def _drag(self, event) -> None:
        if self.carousel.swiping:
            self.carousel.swipe_move(event.x)
            return
        if not self.pan or self.image is None:
            return
        x0, y0, ox, oy = self.pan
        self.view.pan_to(ox - (event.x - x0) / self.view.zoom, oy - (event.y - y0) / self.view.zoom)
        self.redraw()

    def _release(self, event) -> None:
        self.pan = None
        self.carousel.end_swipe()

    # ------------------------------------------------------------------ navigation entre les images
    def _slide_distance(self) -> float:
        """Écart entre deux images du carrousel, en pixels écran."""
        if self.image is None:
            return float(self._view_size()[0])
        return self.image.width * self.view.zoom * (1 + CAROUSEL_GAP)

    def _update_crop_button(self) -> None:
        self.toolbar.set_crop_enabled(self.kind == KIND_CROP)

    def _open_crop(self) -> None:
        """« Recadrer… » : le même éditeur que dans la grille ; l'image se recalcule une fois le cadrage validé."""
        if self.navigator is not None and self.kind == KIND_CROP:
            self.navigator.viewer_crop(self, self._rerender)

    def _update_position(self) -> None:
        if self.navigator is None:
            return
        self.toolbar.set_position(*self.navigator.viewer_position())

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
        """Image suivante (+1) ou précédente (-1) : en carrousel, elle arrive en glissant."""
        if self.carousel.animating or not self.carousel.can_step(delta):
            return
        if (self.carousel.enabled.get() and self.view.fit_mode and self.image is not None
                and self.carousel.neighbors.get(delta) is not None):
            self.carousel.step(delta)
            return
        tile = self.navigator.viewer_step(delta)
        if tile is not None:
            self.show(tile.source, tile.kind, placeholder=self.loader.preview(tile, self.config_snapshot))

    def _commit_step(self, delta: int) -> None:
        """Le glissement est terminé : l'image voisine devient l'image affichée, sans passer par un écran vide."""
        old, incoming = self.image, self.carousel.neighbors.get(delta)
        tile = self.navigator.viewer_step(delta)
        if tile is None:
            self.carousel.reset()
            return
        incoming = incoming or self.loader.preview(tile, self.config_snapshot)
        behind = None
        if old is not None:
            behind = old.copy()
            behind.thumbnail((NEIGHBOR_SIDE, NEIGHBOR_SIDE), Image.Resampling.BILINEAR)
        self.show(tile.source, tile.kind, placeholder=incoming, behind=(-delta, behind))

    def show(self, source: Path, kind: str, placeholder=None, behind=None) -> None:
        """Affiche une autre image dans la même fenêtre (zoom et règle repartent de zéro). `placeholder` : aperçu réduit
        montré en attendant la pleine résolution ; `behind` : (côté, image réduite) de l'image qu'on vient de quitter."""
        for job in (self._rerender_job, self._full_job):
            if job is not None:
                self.after_cancel(job)
        self._rerender_job = self._full_job = None
        self.source, self.kind = source, kind
        self.caption.set(self._caption())
        self.image = self.photo = None
        self.loaded_once = False
        self.pan = None
        self.view.fit_mode = True
        self.carousel.reset(behind)
        self.ruler.clear()
        self.canvas.delete("img", "neigh")
        self.measure.set(t("viewer_hint"))
        self.info.set(t("viewer_loading"))
        self.placeholder = placeholder is not None
        if placeholder is not None:
            self.image = placeholder
            self.loaded_once = True
            self.fit()
        if self.ctx is not None:
            self.config_snapshot = dict(self.ctx.collect_config())
        if self.panel is not None:
            self.panel.set_source(source)
            self.panel.apply_features(self._features())
        self._launch(main=False, keep_neighbors=True)  # voisines tout de suite (aperçus de la grille)
        self._full_job = self.after(FULL_RES_DELAY_MS, self._launch_full)  # pleine résolution une fois arrêté
        self._update_position()
        self._update_crop_button()
        self.carousel.draw_arrows(self._view_size())

    def _launch_full(self) -> None:
        self._full_job = None
        if not self._closing:
            self._launch(main=True, keep_neighbors=True)

    # ------------------------------------------------------------------ dessin
    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("img", "neigh")
        self.toolbar.set_zoom(self.view.zoom)
        if self.image is None:
            return
        view, size = self.view, self._view_size()
        box = view.visible_box(self.image.size, size)
        if box is None:
            return
        crop = self.image.crop(box)
        out_w = max(1, int(round((box[2] - box[0]) * view.zoom)))
        out_h = max(1, int(round((box[3] - box[1]) * view.zoom)))
        resample = Image.Resampling.NEAREST if view.zoom >= 1 else Image.Resampling.BILINEAR
        self.photo = ImageTk.PhotoImage(crop.resize((out_w, out_h), resample))
        canvas.create_image((box[0] - view.ox) * view.zoom + self.carousel.slide_px, (box[1] - view.oy) * view.zoom,
                            anchor=tk.NW, image=self.photo, tags="img")
        canvas.tag_lower("img")
        self.carousel.draw(self.image, view, size)
        self.ruler.draw()
        canvas.tag_raise("nav")

    def flush_changes(self) -> None:
        """En quittant l'étape : si des réglages ont changé ici, la grille d'ordre est rafraîchie."""
        if self.settings_changed and self.on_settings_changed is not None:
            self.settings_changed = False
            self.on_settings_changed()

    def _on_destroy(self) -> None:
        self._closing = True
        for job in (self._rerender_job, self._full_job):  # pas de rappel sur une fenêtre détruite
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self.carousel.close()
        self.loader.close()

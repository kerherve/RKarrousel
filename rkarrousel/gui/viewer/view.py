"""Étape « Ajustements » : l'image de sortie en pleine résolution, avec zoom, déplacement et règle pour mesurer
(par exemple l'épaisseur du cadre). Un panneau latéral règle le cadre et le fond, et un carrousel montre les images
voisines de la grille comme sur un post Instagram.

Les pièces vivent à côté : `viewport` (zoom), `render_jobs` (calculs en arrière-plan), `carousel`, `ruler` et
`settings_panel`. Cette classe les assemble."""
import math
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

from PIL import Image, ImageTk

from rkarrousel.gui.viewer.browsing import BrowsingMixin
from rkarrousel.gui.viewer.carousel import CAROUSEL_GAP, Carousel
from rkarrousel.gui.viewer.frame_report import report_for
from rkarrousel.gui.viewer.loader import ImageLoader
from rkarrousel.gui.viewer.resolution import Resolution
from rkarrousel.gui.viewer.ruler import Ruler
from rkarrousel.gui.viewer.settings_panel import SettingsPanel
from rkarrousel.gui.viewer.toolbar import ViewerToolbar
from rkarrousel.gui.viewer.viewport import ZOOM_STEP, Viewport
from rkarrousel.gui.widgets import Debouncer
from rkarrousel.i18n import kind_label, t
from rkarrousel.outputs import kind_features
from rkarrousel.pipeline import peek_size

MAX_REACH = 60          # voisines affichées de chaque côté, au plus (la fenêtre et le nombre d'images limitent bien avant)
PREVIEW_DELAY_MS = 100   # en feuilletant, l'aperçu net n'est calculé qu'une fois qu'on s'arrête
RERENDER_DELAY_MS = 450  # on attend la fin de la frappe / du geste avant de recalculer l'image


class ViewerView(BrowsingMixin, ttk.Frame):
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
        self.placeholder = False  # l'image affichée est un aperçu provisoire (flou), l'aperçu net arrive
        self.resolution = Resolution()  # aperçu ou pleine résolution (voir resolution.py)
        self.settings_changed = False
        self._closing = False
        self._reach = 1  # voisines affichées de chaque côté (selon la largeur de la fenêtre)
        self._kept_ratio = None  # zoom relatif de l'image précédente, à appliquer à la nouvelle quand elle arrive
        self._rerender = Debouncer(self, RERENDER_DELAY_MS, self._recalculate)  # attend la fin d'un geste sur les réglages
        self._main_delay = Debouncer(self, PREVIEW_DELAY_MS, self._launch_main)  # attend qu'on cesse de feuilleter
        self.loader: Optional[ImageLoader] = None

        self.panel: Optional[SettingsPanel] = None
        self._build_ui()
        if self.panel is not None:
            self.panel.apply_features(self._features())  # grise ce que cette image n'utilise pas
        self.ruler = Ruler(self.canvas, self.measure, lambda: self.view.zoom / self.resolution.factor)  # en pixels réels
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

    def _caption(self) -> str:
        return f"{self.source.name} — {kind_label(self.kind)}"

    # ------------------------------------------------------------------ calcul de l'image
    def _launch(self, main: bool, keep_neighbors: bool, full: bool = False) -> None:
        self._reach = self._neighbors_in_view()
        self.loader.launch(self.source, self.kind, self.config_snapshot, main, keep_neighbors, full, self._reach)

    def _neighbors_in_view(self) -> int:
        """Combien d'images de chaque côté entrent dans la fenêtre (selon le zoom et la position de l'image) : on en charge
        autant, au moins une."""
        if self.navigator is None or self.image is None:
            return 1
        width = self.image.width * self.view.zoom  # largeur de l'image affichée, à l'écran
        step = width + self.image.width * CAROUSEL_GAP * self.view.zoom  # d'une image à la suivante
        if step <= 0:
            return 1
        left = -self.view.ox * self.view.zoom + self.carousel.slide_px  # bord gauche de l'image affichée
        free_left, free_right = left, self._view_size()[0] - (left + width)  # place libre de chaque côté
        return max(1, min(MAX_REACH, math.ceil(max(free_left, free_right, 0) / step)))

    def _ensure_reach(self) -> None:
        """La fenêtre a changé de taille (ou l'image vient d'arriver) : on charge plus de voisines si elles tiennent."""
        if self.image is not None and self._neighbors_in_view() > self._reach:
            self._launch(main=False, keep_neighbors=True)
            self._neighbor_arrived()

    def _neighbor_arrived(self) -> None:
        """Une voisine vient d'arriver : on ne redessine qu'elle, pas toute l'image (ce qui ferait clignoter)."""
        if self.image is not None:
            self.carousel.redraw(self.image, self.view, self._view_size())

    def _show_error(self, message: str) -> None:
        self.info.set(t("order_error", message=message))

    def _show_rendered(self, image: Image.Image, full: bool = False) -> None:
        """L'image affichée est prête : un aperçu net, ou (à la demande) la pleine résolution."""
        unchanged = image is self.image  # le même aperçu est déjà à l'écran (il venait du cache) : rien à redessiner
        self.image = image
        previous = self.resolution.update(image, full, self.source, self.config_snapshot)
        if full:
            Resolution.rescale_view(self.view, previous)
            self.view.set_geometry(image.size, self._view_size())  # pleine résolution : l'image est plus grande
        self._describe()
        if self.placeholder:
            self.placeholder = False
            if not unchanged:
                self._place_image()  # même taille d'affichage que l'aperçu provisoire : la netteté arrive sans saut
        elif self.loaded_once:
            if full and self.view.fit_mode:
                self.fit()
            elif not (unchanged and not full):
                self.redraw()  # on garde le zoom et la position pendant qu'on règle
        else:
            self.loaded_once = True
            self._place_image()
        self._check_full()

    def _check_full(self) -> None:
        """Zoomer au-delà de l'aperçu le rendrait flou : on charge alors la pleine résolution (une fois)."""
        if self.image is not None and self.resolution.wants_full(self.view.zoom):
            self.resolution.pending = True
            self._launch(main=True, keep_neighbors=False, full=True)

    def _describe(self) -> None:
        """Dimensions, couleur du cadre obtenue et épaisseur mesurée dans l'image."""
        assert self.image is not None
        report = report_for(self.image, self.source, self.config_snapshot)
        if self.panel is not None:
            self.panel.show_resolved(report.color)
        factor = self.resolution.factor  # un aperçu est plus petit que l'image finale : on annonce les dimensions réelles (estimées)
        width, height, border = round(report.width * factor), round(report.height * factor), round(report.border * factor)
        if report.border:
            self.info.set(t("viewer_info", width=width, height=height, border=border, percent=report.percent))
        else:
            self.info.set(t("viewer_info_noborder", width=width, height=height))

    # ------------------------------------------------------------------ réglages en direct
    def _features(self) -> frozenset:
        try:
            return kind_features(*peek_size(self.source), self.kind, self.config_snapshot)
        except Exception:
            return frozenset({"fill", "signature"})  # illisible : on ne grise rien

    def _schedule_rerender(self) -> None:
        if not self._closing:
            self._rerender.trigger()

    def _recalculate(self) -> None:
        if self._closing:
            return
        try:
            config = dict(self.ctx.collect_config())
        except Exception:  # saisie en cours (champ vide…) : on attend la prochaine modification
            return
        self.config_snapshot = config
        self.settings_changed = True
        self.info.set(t("viewer_loading"))
        self._launch(main=True, keep_neighbors=False, full=self.resolution.full_loaded)

    # ------------------------------------------------------------------ zoom / déplacement
    def _view_size(self) -> tuple:
        return max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())

    def fit(self) -> None:
        if self.image is None:
            return
        self.view.fit(self.image.size, self._view_size())
        self.redraw()
        self._ensure_reach()

    def _place_image(self) -> None:
        """Met l'image affichée dans la vue : ajustée à la fenêtre, ou au zoom choisi pour l'image précédente (dézoomé, on
        garde la même rangée de photos en passant à la suivante)."""
        if self.image is None:
            return
        ratio = self._kept_ratio if self._kept_ratio is not None else self.view.ratio
        self._kept_ratio = None
        if abs(ratio - 1.0) < 1e-3:
            self.fit()
            return
        self.view.apply_ratio(self.image.size, self._view_size(), ratio)
        self.redraw()
        self._ensure_reach()

    def set_zoom(self, zoom: float) -> None:
        """Zoom en pixels réels (1 = 100 %) : sur un aperçu, c'est un zoom plus fort, donc la pleine résolution est chargée."""
        if self.image is not None and self.view.zoom_to(zoom * self.resolution.factor, self._view_size()):
            self.redraw()
            self._check_full()
            self._ensure_reach()

    def zoom_by(self, factor: float) -> None:
        vw, vh = self._view_size()
        self._zoom_at(vw / 2, vh / 2, factor)

    def _zoom_at(self, cx: float, cy: float, factor: float) -> None:
        if self.image is not None and self.view.zoom_at(cx, cy, factor):
            self.redraw()
            self._check_full()
            self._ensure_reach()  # dézoomer fait tenir plus d'images dans la fenêtre : on les charge

    def _on_resize(self) -> None:
        self.carousel.draw_arrows(self._view_size())
        if self.image is None:
            return
        if self.view.zoomed_in:
            self.view.set_geometry(self.image.size, self._view_size())
            self.redraw()
        else:
            self._place_image()  # ajusté ou dézoomé : on garde le même zoom relatif et on recentre
            self._ensure_reach()

    def _press(self, event) -> None:
        if "nav" in self.canvas.gettags("current") or self.carousel.animating:
            return  # clic sur une flèche de navigation, ou animation en cours
        if self.navigator is not None and not self.view.zoomed_in:
            self.carousel.begin_swipe(event.x)  # image entière à l'écran (ajustée ou dézoomée) : on fait défiler le carrousel
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

    # ------------------------------------------------------------------ dessin
    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("img", "neigh")
        self.toolbar.set_zoom(self.view.zoom / self.resolution.factor)
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
        self.carousel.close()
        self.loader.close()

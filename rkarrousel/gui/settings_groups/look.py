"""Apparence des images : cadre, fond et signature (et les listes de couleurs tirées de la photo)."""
import os
import tkinter as tk
from tkinter import filedialog, ttk

from rkarrousel.config import COLOR_MODES, COLOR_SOURCES, SIGNATURE_POSITIONS
from rkarrousel.gui.context import AppContext
from rkarrousel.gui.widgets import ChoiceBox, ColorPicker, HintLabel, bind_trace, set_tree_enabled
from rkarrousel.i18n import t


def color_mode_labels():
    return [t(f"color_mode_{mode}") for mode in COLOR_MODES]


def color_source_labels():
    return [t(f"color_source_{source}") for source in COLOR_SOURCES]


def color_source_row(group: ttk.LabelFrame, model, row: int, pady: int = 8) -> ChoiceBox:
    """« Couleur prise sur : … » : d'où vient la couleur de référence des modes « tirée de la photo »."""
    ttk.Label(group, text=t("color_source")).grid(row=row, column=0, sticky=tk.W, pady=(pady, 0))
    box = ChoiceBox(group, model.color_source, COLOR_SOURCES, color_source_labels(), width=22)
    box.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=(pady, 0), padx=8)
    return box


class FrameGroup(ttk.LabelFrame):
    """Épaisseur et couleur du cadre (fixe ou tirée de la photo), ou pas de cadre."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, text=t("frame_group"), padding=12)
        model = self.model = ctx.model
        self.columnconfigure(2, weight=1)
        ttk.Label(self, text=t("frame_ratio")).grid(row=0, column=0, sticky=tk.W)
        self.spin = ttk.Spinbox(
            self, from_=0.1, to=20, increment=0.1, format="%.1f", textvariable=model.frame_percent, width=8
        )
        self.spin.grid(row=0, column=1, padx=8)
        HintLabel(self, t("frame_ratio_hint")).grid(row=0, column=2, sticky=tk.EW)
        ttk.Label(self, text=t("frame_color")).grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.mode = ChoiceBox(self, model.border_color_mode, COLOR_MODES, color_mode_labels(), width=22)
        self.mode.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=(8, 0), padx=8)
        self.color = ColorPicker(self, model.border_color, (255, 255, 255), t("choose_color"))
        self.color.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=(8, 0), padx=8)
        self.source = color_source_row(self, model, 3)
        ttk.Checkbutton(self, text=t("no_frame"), variable=model.no_frame, command=self.refresh_state).grid(
            row=4, column=0, columnspan=3, sticky=tk.W, pady=(10, 0)
        )
        bind_trace(self, model.border_color_mode, self.refresh_state)
        bind_trace(self, model.no_frame, self.refresh_state)  # aussi quand un préréglage change la case
        self.refresh_state()

    def refresh_state(self) -> None:
        """Sans cadre, l'épaisseur et la couleur n'ont plus de sens ; une couleur « de la photo » remplace le sélecteur."""
        framed = not self.model.no_frame.get()
        self.spin.state(["!disabled"] if framed else ["disabled"])
        self.mode.state(["!disabled"] if framed else ["disabled"])
        from_photo = self.model.border_color_mode.get() != "fixed"
        self.color.set_enabled(framed and not from_photo)
        self.source.state(["!disabled"] if framed and from_photo else ["disabled"])


class FillGroup(ttk.LabelFrame):
    """Fond de l'image de sortie : uni (couleur fixe ou tirée de la photo) ou flouté (intensité)."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, text=t("fill_group"), padding=12)
        model = self.model = ctx.model
        ttk.Radiobutton(self, text=t("fill_black"), value="black", variable=model.landscape_fill_mode).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 16)
        )
        ttk.Radiobutton(self, text=t("fill_blur"), value="blur", variable=model.landscape_fill_mode).grid(
            row=0, column=1, sticky=tk.W
        )
        ttk.Label(self, text=t("bg_color")).grid(row=1, column=0, sticky=tk.W, padx=(0, 12), pady=(10, 0))
        self.mode = ChoiceBox(self, model.background_color_mode, COLOR_MODES, color_mode_labels(), width=22)
        self.mode.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=(10, 0))
        self.background = ColorPicker(self, model.background_color, (0, 0, 0), t("bg_color"))
        self.background.grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=(8, 0))
        self.source = color_source_row(self, model, 3, pady=8)
        ttk.Label(self, text=t("blur_strength")).grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
        blur_row = ttk.Frame(self)
        blur_row.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=(10, 0))
        self.blur_spin = ttk.Spinbox(blur_row, from_=0.2, to=5.0, increment=0.1, textvariable=model.blur_strength, width=6)
        self.blur_spin.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(blur_row, text=t("blur_strength_hint")).pack(side=tk.LEFT)
        bind_trace(self, model.landscape_fill_mode, self.refresh_state)
        bind_trace(self, model.background_color_mode, self.refresh_state)
        self.refresh_state()

    def set_applicable(self, applicable: bool) -> None:
        """Hors de la visionneuse tout est applicable ; sur une image sans fond (tranche, recadrage…), tout est grisé."""
        self.applicable = applicable
        set_tree_enabled(self, applicable)
        self.configure(text=t("fill_group") + ("" if applicable else " — " + t("viewer_not_applicable")))
        if applicable:
            self.refresh_state()

    def refresh_state(self) -> None:
        """La couleur ne sert qu'au fond uni et l'intensité qu'au fond flouté : on grise l'autre."""
        if not getattr(self, "applicable", True):
            return
        solid = self.model.landscape_fill_mode.get() != "blur"
        self.mode.state(["!disabled"] if solid else ["disabled"])
        from_photo = self.model.background_color_mode.get() != "fixed"
        self.background.set_enabled(solid and not from_photo)
        self.source.state(["!disabled"] if solid and from_photo else ["disabled"])
        self.blur_spin.state(["disabled"] if solid else ["!disabled"])


class SignatureGroup(ttk.LabelFrame):
    """Image de signature, position et taille."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, text=t("signature_group"), padding=12)
        model = self.model = ctx.model
        self.columnconfigure(0, weight=1)
        row = ttk.Frame(self)
        row.grid(row=0, column=0, columnspan=4, sticky=tk.EW)
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=model.signature_path, state="readonly").grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        ttk.Button(row, text=t("choose_signature"), command=self.choose).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(row, text=t("clear"), command=lambda: model.signature_path.set("")).grid(row=0, column=2)
        ttk.Label(self, text=t("signature_position")).grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        position_box = ChoiceBox(
            self, model.signature_position, SIGNATURE_POSITIONS, [t(f"pos_{p}") for p in SIGNATURE_POSITIONS], width=16
        )
        position_box.grid(row=1, column=1, sticky=tk.W, pady=(8, 0), padx=8)
        ttk.Label(self, text=t("signature_scale")).grid(row=1, column=2, sticky=tk.E, pady=(8, 0))
        ttk.Spinbox(self, from_=0.3, to=3.0, increment=0.1, textvariable=model.signature_scale, width=6).grid(
            row=1, column=3, sticky=tk.W, pady=(8, 0), padx=8
        )

    def set_applicable(self, applicable: bool) -> None:
        """Sur une image sans signature (tranche, recadrage, photo au bon format), le groupe est grisé."""
        set_tree_enabled(self, applicable)
        self.configure(text=t("signature_group") + ("" if applicable else " — " + t("viewer_not_applicable")))

    def choose(self) -> None:
        path = filedialog.askopenfilename(
            title=t("dlg_select_signature"),
            initialdir=os.path.dirname(self.model.signature_path.get()) or os.path.expanduser("~"),
            filetypes=[("PNG", "*.png"), (t("filetype_images"), "*.jpg *.jpeg *.bmp"), (t("filetype_all"), "*.*")],
        )
        if path:
            self.model.signature_path.set(path)

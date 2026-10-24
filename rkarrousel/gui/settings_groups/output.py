"""Fichiers produits : format des images, qualité, largeur, numérotation, et types d'images."""
import tkinter as tk
from tkinter import ttk

from rkarrousel.formats import OUTPUT_FORMATS, OUTPUT_WIDTHS
from rkarrousel.gui.context import AppContext
from rkarrousel.gui.settings_model import CHECKBOX_KINDS, PLACEMENT_CHOICES
from rkarrousel.gui.widgets import ChoiceBox, HintLabel
from rkarrousel.i18n import kind_setting_label, t


class FormatGroup(ttk.LabelFrame):
    """Format des images produites (3:4, 4:5, 1:1, 9:16) : il conditionne tout le reste, donc il se choisit d'entrée."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, text=t("format_group"), padding=12)
        format_keys = list(OUTPUT_FORMATS)
        self.format_box = ChoiceBox(
            self, ctx.model.output_format, format_keys, [t(f"fmt_{key.replace(':', 'x')}") for key in format_keys], width=34
        )
        self.format_box.pack(anchor=tk.W)
        HintLabel(self, t("format_hint")).pack(fill=tk.X, pady=(6, 0))


class OutputGroup(ttk.LabelFrame):
    """Qualité JPEG, largeur des images produites et numérotation des fichiers."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, text=t("output_group"), padding=12)
        model = ctx.model
        self.columnconfigure(2, weight=1)
        ttk.Label(self, text=t("jpeg_quality")).grid(row=0, column=0, sticky=tk.W)
        ttk.Spinbox(self, from_=50, to=100, increment=1, textvariable=model.jpeg_quality, width=6).grid(row=0, column=1, padx=8)
        ttk.Label(self, text=t("jpeg_quality_hint")).grid(row=0, column=2, sticky=tk.W)


        ttk.Label(self, text=t("output_width")).grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        self.width_box = ChoiceBox(
            self, model.output_width, list(OUTPUT_WIDTHS),
            [t("width_original") if w == 0 else t("width_px", px=w) for w in OUTPUT_WIDTHS], width=34,
        )
        self.width_box.grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=8, pady=(10, 0))
        HintLabel(self, t("output_width_hint")).grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(4, 0))

        ttk.Checkbutton(self, text=t("number_files"), variable=model.number_files).grid(
            row=4, column=0, columnspan=3, sticky=tk.W, pady=(12, 0)
        )
        HintLabel(self, t("number_files_hint")).grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(2, 0))


class KindsGroup(ttk.LabelFrame):
    """Types d'images produites pour chaque photo : cases à cocher, et pour les deux « photos entières » d'un paysage
    une liste (avant / après le découpage, à la fin du carrousel, aucune). Tout est empilé : le groupe vit dans une
    colonne étroite, à côté de la grille d'ordre."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, text=t("kinds_group"), padding=12)
        model = ctx.model
        self.columnconfigure(0, weight=1)
        row = 0
        for kind in CHECKBOX_KINDS:
            ttk.Checkbutton(self, text=kind_setting_label(kind), variable=model.kind_vars[kind]).grid(
                row=row, column=0, sticky=tk.W, pady=2)
            row += 1
        labels = [t(f"placement_{choice}") for choice in PLACEMENT_CHOICES]
        for kind, var in model.placements.items():
            ttk.Label(self, text=kind_setting_label(kind) + " :").grid(row=row, column=0, sticky=tk.W, pady=(10, 2))
            ChoiceBox(self, var, PLACEMENT_CHOICES, labels, width=28).grid(row=row + 1, column=0, sticky=tk.W)
            row += 2
        HintLabel(self, t("kinds_hint")).grid(row=row, column=0, sticky=tk.EW, pady=(10, 0))

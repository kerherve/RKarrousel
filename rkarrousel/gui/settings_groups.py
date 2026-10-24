"""Les groupes de l'onglet « Réglages », chacun dans sa classe : apparence, cadre, fond, signature, sortie,
images produites, Google Drive et mises à jour."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from rkarrousel import i18n
from rkarrousel import presets
from rkarrousel.config import COLOR_MODES, SIGNATURE_POSITIONS
from rkarrousel.formats import OUTPUT_FORMATS, OUTPUT_WIDTHS
from rkarrousel.gui.context import AppContext
from rkarrousel.gui.settings_model import ALL_KINDS
from rkarrousel.gui.theme import THEME_CHOICES
from rkarrousel.gui.widgets import ChoiceBox, ColorPicker, HintLabel, bind_trace
from rkarrousel.i18n import kind_setting_label, t
from rkarrousel.version import __version__


class PresetsGroup(ttk.LabelFrame):
    """Préréglages nommés : choisir un jeu de réglages d'un clic, ou enregistrer les réglages actuels sous un nom."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, text=t("presets_group"), padding=12)
        self.ctx = ctx
        self.entries = []
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text=t("preset_label")).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.box = ttk.Combobox(self, state="readonly")
        self.box.bind("<<ComboboxSelected>>", lambda e: self.apply_selected())
        self.box.grid(row=0, column=1, sticky=tk.EW)
        buttons = ttk.Frame(self)
        buttons.grid(row=1, column=1, sticky=tk.W, pady=(8, 0))
        ttk.Button(buttons, text=t("preset_save"), command=self.save).pack(side=tk.LEFT, padx=(0, 8))
        self.delete_button = ttk.Button(buttons, text=t("preset_delete"), command=self.delete)
        self.delete_button.pack(side=tk.LEFT)
        HintLabel(self, t("preset_hint")).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))
        match = presets.find_matching(ctx.collect_config())
        self.reload(select=match.id if match else None)

    @staticmethod
    def label(preset: presets.Preset) -> str:
        return t(f"preset_{preset.id}") if preset.builtin else preset.id

    def reload(self, select=None) -> None:
        """Relit la liste (fournis puis personnels) et sélectionne `select`, ou « réglages personnalisés »."""
        self.entries = presets.all_presets(self.ctx.config)
        self.box.configure(values=[self.label(p) for p in self.entries])
        index = next((i for i, p in enumerate(self.entries) if p.id == select), None)
        if index is None:
            self.box.set(t("preset_custom"))
        else:
            self.box.current(index)
        self._update_delete_button()

    def selected(self):
        index = self.box.current()
        return self.entries[index] if 0 <= index < len(self.entries) else None

    def _update_delete_button(self) -> None:
        preset = self.selected()
        self.delete_button.state(["!disabled"] if preset and not preset.builtin else ["disabled"])

    def apply_selected(self) -> None:
        preset = self.selected()
        if preset is None:
            return
        self.ctx.model.apply(preset.values)
        self._update_delete_button()
        self.ctx.set_status(t("preset_applied", name=self.label(preset)))

    def save(self) -> None:
        name = simpledialog.askstring(t("preset_name_title"), t("preset_name_prompt"), parent=self.winfo_toplevel())
        try:
            name = presets.clean_name(name or "")
        except ValueError:
            return
        exists = any(p.id == name and not p.builtin for p in self.entries)
        if exists and not messagebox.askyesno(t("presets_group"), t("preset_overwrite", name=name)):
            return
        saved = presets.save_user_preset(self.ctx.config, name, presets.extract(self.ctx.collect_config()))
        self.ctx.save_config()
        self.reload(select=saved)
        self.ctx.set_status(t("preset_saved", name=saved))

    def delete(self) -> None:
        preset = self.selected()
        if preset is None or preset.builtin:
            return
        if not messagebox.askyesno(t("presets_group"), t("preset_delete_confirm", name=preset.id)):
            return
        presets.delete_user_preset(self.ctx.config, preset.id)
        self.ctx.save_config()
        self.reload()


class AppearanceGroup(ttk.LabelFrame):
    """Langue et thème (clair / sombre / auto)."""

    def __init__(self, parent, ctx: AppContext, on_language: Callable[[int], None], on_theme: Callable[[int], None]):
        super().__init__(parent, text=t("appearance_group"), padding=12)
        ttk.Label(self, text=t("language")).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        language_box = ttk.Combobox(
            self, state="readonly", width=12, values=[i18n.LANGUAGES[code] for code in i18n.LANGUAGES]
        )
        language_box.set(i18n.LANGUAGES[i18n.get_language()])
        language_box.bind("<<ComboboxSelected>>", lambda e: on_language(language_box.current()))
        language_box.grid(row=0, column=1, padx=(0, 28))
        ttk.Label(self, text=t("theme")).grid(row=0, column=2, sticky=tk.W, padx=(0, 8))
        theme_box = ttk.Combobox(
            self, state="readonly", width=10, values=[t("theme_auto"), t("theme_light"), t("theme_dark")]
        )
        current = ctx.config.get("theme", "auto")
        theme_box.current(THEME_CHOICES.index(current) if current in THEME_CHOICES else 0)
        theme_box.bind("<<ComboboxSelected>>", lambda e: on_theme(theme_box.current()))
        theme_box.grid(row=0, column=3)


def color_mode_labels():
    return [t(f"color_mode_{mode}") for mode in COLOR_MODES]


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
        ttk.Checkbutton(self, text=t("no_frame"), variable=model.no_frame, command=self.refresh_state).grid(
            row=3, column=0, columnspan=3, sticky=tk.W, pady=(10, 0)
        )
        bind_trace(self, model.border_color_mode, self.refresh_state)
        bind_trace(self, model.no_frame, self.refresh_state)  # aussi quand un préréglage change la case
        self.refresh_state()

    def refresh_state(self) -> None:
        """Sans cadre, l'épaisseur et la couleur n'ont plus de sens ; une couleur « de la photo » remplace le sélecteur."""
        framed = not self.model.no_frame.get()
        self.spin.state(["!disabled"] if framed else ["disabled"])
        self.mode.state(["!disabled"] if framed else ["disabled"])
        self.color.set_enabled(framed and self.model.border_color_mode.get() == "fixed")


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
        ttk.Label(self, text=t("blur_strength")).grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        blur_row = ttk.Frame(self)
        blur_row.grid(row=3, column=1, columnspan=2, sticky=tk.W, pady=(10, 0))
        self.blur_spin = ttk.Spinbox(blur_row, from_=0.2, to=5.0, increment=0.1, textvariable=model.blur_strength, width=6)
        self.blur_spin.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(blur_row, text=t("blur_strength_hint")).pack(side=tk.LEFT)
        bind_trace(self, model.landscape_fill_mode, self.refresh_state)
        bind_trace(self, model.background_color_mode, self.refresh_state)
        self.refresh_state()

    def refresh_state(self) -> None:
        """La couleur ne sert qu'au fond uni et l'intensité qu'au fond flouté : on grise l'autre."""
        solid = self.model.landscape_fill_mode.get() != "blur"
        self.mode.state(["!disabled"] if solid else ["disabled"])
        self.background.set_enabled(solid and self.model.background_color_mode.get() == "fixed")
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

    def choose(self) -> None:
        path = filedialog.askopenfilename(
            title=t("dlg_select_signature"),
            initialdir=os.path.dirname(self.model.signature_path.get()) or os.path.expanduser("~"),
            filetypes=[("PNG", "*.png"), (t("filetype_images"), "*.jpg *.jpeg *.bmp"), (t("filetype_all"), "*.*")],
        )
        if path:
            self.model.signature_path.set(path)


class OutputGroup(ttk.LabelFrame):
    """Qualité JPEG, format, largeur des images produites et numérotation des fichiers."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, text=t("output_group"), padding=12)
        model = ctx.model
        self.columnconfigure(2, weight=1)
        ttk.Label(self, text=t("jpeg_quality")).grid(row=0, column=0, sticky=tk.W)
        ttk.Spinbox(self, from_=50, to=100, increment=1, textvariable=model.jpeg_quality, width=6).grid(row=0, column=1, padx=8)
        ttk.Label(self, text=t("jpeg_quality_hint")).grid(row=0, column=2, sticky=tk.W)

        ttk.Label(self, text=t("output_format")).grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        format_keys = list(OUTPUT_FORMATS)
        self.format_box = ChoiceBox(
            self, model.output_format, format_keys, [t(f"fmt_{key.replace(':', 'x')}") for key in format_keys], width=34
        )
        self.format_box.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=8, pady=(10, 0))

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
    """Types d'images produites pour chaque photo (cases à cocher)."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, text=t("kinds_group"), padding=12)
        self.columnconfigure(1, weight=1)
        for position, kind in enumerate(ALL_KINDS):
            ttk.Checkbutton(self, text=kind_setting_label(kind), variable=ctx.model.kind_vars[kind]).grid(
                row=position // 2, column=position % 2, sticky=tk.W, padx=(0, 24), pady=2
            )
        HintLabel(self, t("kinds_hint")).grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))


class DriveGroup(ttk.LabelFrame):
    """Envoi des images sur Google Drive : activation, identifiants, connexion et dossier."""

    def __init__(self, parent, ctx: AppContext, drive):
        super().__init__(parent, text=t("gd_group"), padding=12)
        self.columnconfigure(0, weight=1)
        ttk.Checkbutton(self, text=t("gd_enable"), variable=ctx.model.gdrive_enabled).grid(
            row=0, column=0, columnspan=4, sticky=tk.W
        )
        ttk.Label(self, textvariable=drive.status).grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        buttons = ttk.Frame(self)
        buttons.grid(row=2, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Button(buttons, text=t("gd_load"), command=drive.choose_credentials).pack(side=tk.LEFT, padx=(0, 8))
        self.connect_button = ttk.Button(buttons, text=t("gd_connect"), command=drive.connect)
        self.connect_button.pack(side=tk.LEFT, padx=(0, 8))
        drive.connect_button = self.connect_button
        ttk.Button(buttons, text=t("gd_disconnect"), command=drive.disconnect).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text=t("gd_help_btn"), command=drive.show_help).pack(side=tk.LEFT)
        folder_row = ttk.Frame(self)
        folder_row.grid(row=3, column=0, sticky=tk.EW, pady=(10, 0))
        folder_row.columnconfigure(1, weight=1)
        ttk.Label(folder_row, text=t("gd_folder")).grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(folder_row, textvariable=ctx.model.gdrive_folder).grid(row=0, column=1, sticky=tk.EW)
        HintLabel(self, t("gd_folder_hint")).grid(row=4, column=0, sticky=tk.EW, pady=(4, 0))
        drive.refresh_status()


class UpdateGroup(ttk.LabelFrame):
    """Recherche de mises à jour."""

    def __init__(self, parent, ctx: AppContext, on_check_now: Callable[[], None]):
        super().__init__(parent, text=t("upd_group"), padding=12)
        self.columnconfigure(1, weight=1)
        ttk.Checkbutton(self, text=t("upd_check_startup"), variable=ctx.model.update_check).grid(
            row=0, column=0, columnspan=3, sticky=tk.W
        )
        ttk.Label(self, text=t("upd_current", version=__version__)).grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        ttk.Button(self, text=t("upd_check_now"), command=on_check_now).grid(
            row=1, column=1, sticky=tk.W, padx=(12, 0), pady=(10, 0)
        )

"""Préréglages nommés : choisir un jeu de réglages d'un clic, ou enregistrer les réglages actuels."""
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from rkarrousel import presets
from rkarrousel.gui.context import AppContext
from rkarrousel.gui.widgets import HintLabel
from rkarrousel.i18n import t


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

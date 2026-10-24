"""Envoi des images sur Google Drive : activation, identifiants, connexion et dossier."""
import tkinter as tk
from tkinter import ttk

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.widgets import HintLabel
from rkarrousel.i18n import t


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

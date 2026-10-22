"""Onglet « Réglages » : assemble les groupes dans une zone défilante."""
import tkinter as tk
from tkinter import ttk
from typing import Callable

from rkarrousel.gui.context import AppContext
from rkarrousel.gui.settings_groups import (
    AppearanceGroup,
    DriveGroup,
    FillGroup,
    FrameGroup,
    KindsGroup,
    OutputGroup,
    SignatureGroup,
    UpdateGroup,
)
from rkarrousel.gui.widgets import make_scrollable


class SettingsTab(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        ctx: AppContext,
        drive,
        on_language: Callable[[int], None],
        on_theme: Callable[[int], None],
        on_check_updates: Callable[[], None],
    ):
        super().__init__(parent)
        inner = make_scrollable(self, ctx.theme.surface_color())
        inner.columnconfigure(0, weight=1)
        self.appearance = AppearanceGroup(inner, ctx, on_language, on_theme)
        self.frame = FrameGroup(inner, ctx)
        self.fill = FillGroup(inner, ctx)
        self.signature = SignatureGroup(inner, ctx)
        self.output = OutputGroup(inner, ctx)
        self.kinds = KindsGroup(inner, ctx)
        self.drive = DriveGroup(inner, ctx, drive)
        self.updates = UpdateGroup(inner, ctx, on_check_updates)
        groups = (self.appearance, self.frame, self.fill, self.signature, self.output, self.kinds, self.drive, self.updates)
        for row, group in enumerate(groups):
            group.grid(row=row, column=0, sticky=tk.EW, pady=(0, 8))

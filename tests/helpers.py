"""Outils partagés par les tests."""
from pathlib import Path

from PIL import Image


def make_image(directory: Path, name: str, size, color=(120, 60, 200)) -> Path:
    """Crée une image JPEG unie de la taille voulue et renvoie son chemin."""
    path = directory / name
    Image.new("RGB", size, color).save(path, quality=90)
    return path


def build_settings_groups(root, ctx):
    """Les groupes de réglages (préréglages, cadre, fond, format, sortie) dans une fenêtre à part : ils ne vivent plus
    dans un onglet fixe mais dans les étapes du flux, et on veut les tester seuls."""
    import tkinter as tk
    from types import SimpleNamespace

    from rkarrousel.gui.settings_groups import FillGroup, FormatGroup, FrameGroup, OutputGroup, PresetsGroup

    top = tk.Toplevel(root)
    return SimpleNamespace(
        top=top, presets=PresetsGroup(top, ctx), frame=FrameGroup(top, ctx), fill=FillGroup(top, ctx),
        output=OutputGroup(top, ctx), format=FormatGroup(top, ctx),
    )

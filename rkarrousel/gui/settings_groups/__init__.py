"""Les groupes de l'onglet « Réglages », chacun dans sa classe, rangés par thème."""
from rkarrousel.gui.settings_groups.appearance import AppearanceGroup, UpdateGroup
from rkarrousel.gui.settings_groups.drive_group import DriveGroup
from rkarrousel.gui.settings_groups.look import (
    FillGroup, FrameGroup, SignatureGroup, color_mode_labels, color_source_labels, color_source_row,
)

from rkarrousel.gui.settings_groups.output import FormatGroup, KindsGroup, OutputGroup
from rkarrousel.gui.settings_groups.presets_group import PresetsGroup

__all__ = [
    "AppearanceGroup", "DriveGroup", "FillGroup", "FormatGroup", "FrameGroup", "KindsGroup", "OutputGroup", "PresetsGroup",
    "SignatureGroup", "UpdateGroup", "color_mode_labels", "color_source_labels", "color_source_row",
]

# SPDX-License-Identifier: MIT


from dioptas.model.OverlayModel import OverlayModel
from dioptas.widgets.plot_widgets import PatternWidget


class OverlayInPatternController:
    def __init__(self, pattern_widget: PatternWidget, overlay_model: OverlayModel):
        self.model = overlay_model
        self.pattern_widget = pattern_widget

        self.connect()

    def connect(self):
        self.model.overlay_added.connect(self.overlay_added)
        self.model.overlay_removed.connect(self.overlay_removed)
        self.model.overlay_changed.connect(self.overlay_changed)

    def overlay_added(self):
        overlay = self.model.get_overlay(len(self.model.overlays) - 1)
        color = self.model.get_overlay_color(len(self.model.overlays) - 1)
        if overlay is not None:
            self.pattern_widget.add_overlay(overlay, color)

    def overlay_removed(self, index: int):
        self.pattern_widget.remove_overlay(index)

    def overlay_changed(self, index: int):
        overlay = self.model.get_overlay(index)
        if overlay is not None:
            self.pattern_widget.update_overlay(index, overlay)

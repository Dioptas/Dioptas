"""Automated screenshot capture for Dioptas documentation.

Launches Dioptas on-screen, loads test data, and captures screenshots
of all views and control panels.

Usage:
    uv run python docs/take_screenshots.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtpy import QtWidgets
from qt_material import apply_stylesheet

from dioptas.paths import style_path

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source", "images")
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dioptas",
    "tests",
    "data",
)

test_image = os.path.join(DATA_DIR, "CeO2_Pilatus1M.tif")
test_calibration = os.path.join(DATA_DIR, "CeO2_Pilatus1M.poni")
test_jcpds_dir = os.path.join(DATA_DIR, "jcpds")
test_overlay_1 = os.path.join(DATA_DIR, "pattern_001.xy")
test_overlay_2 = os.path.join(DATA_DIR, "pattern_002.xy")


def wait(app, ms=500):
    """Process events and wait."""
    deadline = time.time() + ms / 1000.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def save(widget, name):
    """Grab a widget and save as PNG."""
    pixmap = widget.grab()
    path = os.path.join(IMG_DIR, name)
    pixmap.save(path)
    print(f"  Saved {name} ({pixmap.width()}x{pixmap.height()})")


def main():
    app = QtWidgets.QApplication(sys.argv)

    theme_path = os.path.join(style_path, "dark_orange.xml")
    qss_path = os.path.join(style_path, "qt_material.css")
    apply_stylesheet(
        app, theme=theme_path, css_file=qss_path, extra={"density_scale": -2}
    )

    from dioptas.controller.MainController import MainController

    controller = MainController(use_settings=False)
    controller.show_window()
    controller.widget.resize(1200, 800)

    # Load test data (image first to set dimensions, then calibration)
    controller.model.img_model.load(test_image)
    controller.model.calibration_model.load(test_calibration)

    # Load phases for realistic screenshots
    for jcpds_file in ["au_Anderson.jcpds", "pt.jcpds", "ag.jcpds"]:
        path = os.path.join(test_jcpds_dir, jcpds_file)
        if os.path.exists(path):
            controller.model.phase_model.add_jcpds(path)

    # Load overlays
    if os.path.exists(test_overlay_1):
        controller.model.overlay_model.add_overlay_file(test_overlay_1)
    if os.path.exists(test_overlay_2):
        controller.model.overlay_model.add_overlay_file(test_overlay_2)

    # Enable mask for integration
    controller.model.mask_model.mask_ellipse(520, 490, 50, 50)
    controller.model.mask_model.mask_rect(0, 0, 50, 981)
    controller.model.use_mask = True

    wait(app, 1500)

    # =============================================
    # INTEGRATION VIEW
    # =============================================
    print("Integration view screenshots...")
    controller.widget.integration_mode_btn.click()
    wait(app, 800)

    save(controller.widget, "integration_view.png")
    save(controller.widget, "integration_view_modules.png")
    save(controller.widget, "integration_view_project_controls.png")

    # Show configuration panel
    controller.widget.configuration_widget.setVisible(True)
    wait(app, 500)
    save(controller.widget, "integration_view_configuration.png")
    controller.widget.configuration_widget.setVisible(False)
    wait(app, 300)

    # Control panel tabs
    int_widget = controller.widget.integration_widget
    control = int_widget.integration_control_widget

    # Overlay tab
    control.tab_widget_1.setCurrentWidget(control.overlay_control_widget)
    wait(app, 300)
    save(control.tab_widget_1, "overlay_control.png")

    # Phase tab
    control.tab_widget_1.setCurrentWidget(control.phase_control_widget)
    wait(app, 300)
    save(control.tab_widget_1, "phase_control.png")

    # Corrections tab
    control.tab_widget_1.setCurrentWidget(control.corrections_control_widget)
    wait(app, 300)
    save(control.tab_widget_1, "cor_control.png")

    # Background tab
    control.tab_widget_1.setCurrentWidget(control.background_control_widget)
    wait(app, 300)
    save(control.tab_widget_1, "background_control.png")

    # Options (X) tab
    control.tab_widget_1.setCurrentWidget(control.integration_options_widget)
    wait(app, 300)
    save(control.tab_widget_1, "integration_options.png")

    # Image display widget
    save(int_widget.integration_image_widget, "image_widget_qa.png")

    # Pattern display widget
    save(int_widget.integration_pattern_widget, "background_inspect.png")

    # =============================================
    # CALIBRATION VIEW
    # =============================================
    print("Calibration view screenshots...")
    controller.widget.calibration_mode_btn.click()
    wait(app, 800)

    cal_widget = controller.widget.calibration_widget
    cal_control = cal_widget.calibration_control_widget
    cal_params = cal_control.calibration_parameters_widget

    # Full calibration view
    save(controller.widget, "peak_selection2.png")

    # Start values panel
    save(cal_params.start_values_gb, "start_values.png")

    # Peak selection panel
    save(cal_params.peak_selection_gb, "peak_selection.png")

    # Refinement options
    save(cal_params.refinement_options_gb, "refinement_options.png")

    # =============================================
    # MASK VIEW
    # =============================================
    print("Mask view screenshots...")
    controller.widget.mask_mode_btn.click()
    wait(app, 800)
    save(controller.widget, "mask_view.png")

    # =============================================
    # MAP VIEW
    # =============================================
    print("Map view screenshots...")
    controller.widget.map_mode_btn.click()
    wait(app, 800)
    save(controller.widget, "map_view.png")

    print("\nDone! All screenshots saved to docs/source/images/")

    controller.widget.close()
    del controller
    app.quit()


if __name__ == "__main__":
    main()

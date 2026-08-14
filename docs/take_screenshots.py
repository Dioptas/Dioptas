"""Automated screenshot capture for Dioptas documentation.

Launches Dioptas on-screen, loads test data, and captures screenshots
of all views and control panels.

Usage:
    uv run python docs/take_screenshots.py

Set ``DIOPTAS_SCREENSHOTS`` to a comma-separated list of PNG names to update
only selected screenshots, for example ``eos_database.png,phase_editor.png``.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qtpy import QtWidgets
from qt_material import apply_stylesheet

from dioptas.paths import style_path

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source", "images")
SCREENSHOT_NAMES = {
    name.strip()
    for name in os.environ.get("DIOPTAS_SCREENSHOTS", "").split(",")
    if name.strip()
}
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
    if SCREENSHOT_NAMES and name not in SCREENSHOT_NAMES:
        return
    pixmap = widget.grab()
    path = os.path.join(IMG_DIR, name)
    pixmap.save(path)
    print(f"  Saved {name} ({pixmap.width()}x{pixmap.height()})")


def main():
    app = QtWidgets.QApplication(sys.argv)

    # modal message boxes (e.g. the detector-shape-mismatch warning when the
    # calibration section swaps test images) would block the run forever
    QtWidgets.QMessageBox.critical = (
        lambda *args, **kwargs: QtWidgets.QMessageBox.Ok
    )

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

    # Bundled EoS database browser
    from dioptas.controller.integration.phase.EosDatabaseController import (
        EosDatabaseController,
    )

    eos_database_controller = EosDatabaseController(controller.widget)
    eos_database_controller.dialog.search_input.setText("gold")
    eos_database_controller.dialog.show()
    wait(app, 500)
    save(eos_database_controller.dialog, "eos_database.png")
    eos_database_controller.dialog.close()

    # Phase Editor, populated with a database material so the record and
    # thermal-model workflow is visible rather than only the legacy fields.
    from dioptas.model import eos

    material = next(
        material
        for material in eos_database_controller.materials
        if material.name.casefold() == "gold"
    )
    database_phase = eos.build_jcpds(
        material,
        material.default_eos_index,
        wavelength_angstrom=controller.model.calibration_model.wavelength * 1e10,
        origin="bundled",
    )
    controller.model.phase_model.add_jcpds_object(database_phase)
    phase_editor_controller = (
        controller.integration_controller.phase_controller.phase_editor_controller
    )
    phase_editor_controller.show_phase(database_phase)
    phase_editor_controller.show_view()
    phase_editor_controller.jcpds_widget.resize(1000, 680)
    wait(app, 500)
    save(phase_editor_controller.jcpds_widget, "phase_editor.png")
    phase_editor_controller.close_view()

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

    # =============================================
    # CALIBRATION VIEW (wizard)
    # =============================================
    # last, because it walks the LaB6 example through the wizard steps and
    # thereby replaces the loaded image, calibration and phases
    print("Calibration view screenshots...")
    controller.widget.calibration_mode_btn.click()
    wait(app, 800)

    cal_widget = controller.widget.calibration_widget
    cal_controller = controller.calibration_controller

    # start from a clean slate so the wizard shows the first-time flow
    controller.model.reset()
    wait(app, 500)

    lab6_image = os.path.join(DATA_DIR, "LaB6_40keV_MarCCD.tif")
    lab6_poni = os.path.join(DATA_DIR, "LaB6_40keV_MarCCD.poni")

    # step 1: image & detector
    controller.model.img_model.load(lab6_image)
    cal_controller.go_to_wizard_step(0)
    wait(app, 500)
    save(controller.widget, "calibration_step1_image.png")

    # step 2: peaks picked on the first two rings, ring 2 highlighted
    cal_controller.go_to_wizard_step(1)
    cal_controller.search_peaks(1179.6, 1129.4)
    cal_controller.search_peaks(1268.5, 1119.8)
    cal_widget.peak_num_sb.setValue(2)
    wait(app, 500)
    save(controller.widget, "calibration_step2_pick_rings.png")

    # step 3: start values, fit constraints and refinement options
    cal_controller.go_to_wizard_step(2)
    wait(app, 500)
    save(cal_widget.calibration_control_widget, "calibration_step3_panel.png")

    # step 4: validation with calibrant overlays and the linked marker
    controller.model.calibration_model.load(lab6_poni)
    cal_controller.update_all()
    cal_controller.validation_pattern_click(6.05, 0)
    wait(app, 800)
    save(controller.widget, "calibration_step4_validation.png")

    # the stepper alone, cropped from the full-width bar
    if not SCREENSHOT_NAMES or "calibration_stepper.png" in SCREENSHOT_NAMES:
        stepper_pixmap = controller.widget.grab()
        stepper_pixmap.copy(
            controller.widget.width() - 540, 0, 540, 44
        ).save(os.path.join(IMG_DIR, "calibration_stepper.png"))
        print("  Saved calibration_stepper.png (540x44)")

    print("\nDone! All screenshots saved to docs/source/images/")

    controller.widget.close()
    del controller
    app.quit()


if __name__ == "__main__":
    main()

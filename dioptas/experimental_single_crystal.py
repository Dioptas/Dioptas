# SPDX-License-Identifier: MIT
"""Explicit development launcher for a rotation series; normal settings stay separate."""

import argparse
from qtpy import QtCore, QtWidgets


def main():
    parser = argparse.ArgumentParser(
        description="Open experimental rotation-series position hunting."
    )
    parser.add_argument("frame", help="Any numbered detector frame in the run")
    parser.add_argument(
        "--sidecar-angles",
        action="store_true",
        help="Interpret omega0 as start and omegaR as exposure width",
    )
    parser.add_argument("--omega-start", type=float)
    parser.add_argument("--omega-step", type=float)
    parser.add_argument("--omega-width", type=float)
    parser.add_argument("--find-positions", action="store_true")
    parser.add_argument(
        "--calibration", help="PONI file to prefill the blind cell-search dialog"
    )
    parser.add_argument("--exclude-zero-padding", action="store_true")
    parser.add_argument(
        "--saturation", type=float, help="Flag pixels at this detector count level"
    )
    args = parser.parse_args()
    angles = (args.omega_start, args.omega_step, args.omega_width)
    if args.sidecar_angles and any(v is not None for v in angles):
        parser.error("Choose sidecar angles or three manual angles, not both.")
    if not args.sidecar_angles and not all(v is not None for v in angles):
        parser.error(
            "Specify --sidecar-angles or all of --omega-start, --omega-step, --omega-width."
        )
    from . import MainController, _apply_application_stylesheet, _set_application_icon
    from .model.rotation_series import import_series
    from phasesmith import _core

    if not hasattr(_core, "experimental_rotation_link"):
        parser.error(
            "Install the PhaseSmith experimental-spots wheel with rotation support first."
        )
    try:
        series = import_series(
            args.frame, manual_angles=None if args.sidecar_angles else angles
        )
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    app = QtWidgets.QApplication([])
    app.setApplicationName("Dioptas Experimental")
    _set_application_icon(app)
    _apply_application_stylesheet(app)
    controller = MainController(use_settings=False, experimental_single_crystal=True)
    controller.widget.resize(1500, 1000)
    controller.widget.single_crystal_mode_btn.click()
    controller.single_crystal_controller.load_series(series)
    if args.calibration:
        controller.single_crystal_controller.cell_calibration_filename = (
            args.calibration
        )
    controller.widget.single_crystal_widget.zero_padding.setChecked(
        args.exclude_zero_padding
    )
    if args.saturation is not None:
        controller.widget.single_crystal_widget.saturation.setValue(args.saturation)
        controller.widget.single_crystal_widget.saturation_enabled.setChecked(True)
    controller.widget.setWindowTitle("Dioptas — experimental rotation-series positions")
    controller.show_window()
    print(f"Opened {len(series.files)} frames. {series.angle_source}", flush=True)
    if args.find_positions:
        QtCore.QTimer.singleShot(300, controller.single_crystal_controller.detect)
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

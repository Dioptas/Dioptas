# SPDX-License-Identifier: MIT

import logging
import os
import sys
from sys import platform as _platform

from .log import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

# If QT_API is not set, use PyQt6 by default
if "QT_API" not in os.environ:
    try:
        import PyQt6.QtCore
    except ImportError:
        pass

from qtpy import QtWidgets
from qt_material import apply_stylesheet

try:
    from pyshortcuts import make_shortcut
except ImportError:
    make_shortcut = None

try:
    from ._version import version as __version__
except Exception:
    try:
        from importlib.metadata import version as _pkg_version
        __version__ = _pkg_version("dioptas")
    except Exception:
        __version__ = "0.0.0"

from .paths import resources_path, calibrants_path, icons_path, data_path, style_path
from .excepthook import excepthook
from .controller.MainController import MainController


theme_path = os.path.join(style_path, "dark_orange.xml")
qss_path = os.path.join(style_path, "qt_material.css")

_dioptrin_available = False


def _check_dioptrin_license():
    """Check dioptrin license at startup. Returns True if usable."""
    try:
        import dioptrin

        dioptrin.validate_license()
        return True
    except ImportError:
        return False
    except dioptrin.LicenseNotFoundError:
        return False
    except dioptrin.LicenseExpiredError:
        QtWidgets.QMessageBox.warning(
            None,
            "Dioptrin License Expired",
            "Your Dioptrin license has expired. "
            "Dioptas will use pyFAI for integration.\n\n"
            "Please renew your license to continue using Dioptrin.",
        )
        return False
    except dioptrin.LicenseError:
        return False


def _set_application_icon(app):
    """Application-wide icon, inherited by every top-level window.

    On Windows the .ico is used: it carries pre-rendered 16-256 px entries,
    which the shell can consume directly for the taskbar and Alt-Tab. The
    other platforms take the SVG, which scales to any size Qt asks for.
    """
    from qtpy import QtGui

    icon_file = "icon.ico" if _platform == "win32" else "icon.svg"
    app.setWindowIcon(QtGui.QIcon(os.path.join(icons_path, icon_file)))


def main():
    global _dioptrin_available

    if _platform == "win32":
        # Windows resolves the taskbar button's icon through the application
        # identity, not the window; without an explicit one it has to guess,
        # which comes up empty on the first run of a fresh executable.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "com.dioptas.Dioptas"
        )

    app = QtWidgets.QApplication([])
    _set_application_icon(app)

    apply_stylesheet(
        app,
        theme=theme_path,
        css_file=qss_path,
        extra={"density_scale": -2},
    )
    sys.excepthook = excepthook
    logger.info("Dioptas %s", __version__)

    _dioptrin_available = _check_dioptrin_license()

    if len(sys.argv) == 1:  # normal start
        controller = MainController()
        controller.show_window()
        app.exec_()
    else:  # with command line arguments
        if sys.argv[1] == "test":
            # Exercise packaged EoS data as part of the release smoke test.
            # Constructing MainController alone does not open the database
            # browser, where the Peritheos library is normally loaded lazily.
            from .model.eos.database import load_materials

            materials = load_materials()
            if not materials:
                raise RuntimeError("Peritheos EoS material library is empty")
            logger.info(
                "Loaded %d EoS materials from Peritheos", len(materials)
            )
            controller = MainController(use_settings=False)
            controller.show_window()

        elif sys.argv[1].startswith("makeshortcut"):
            if make_shortcut is None:
                raise ImportError("pyshortcuts not installed.  Try `pip install pyshortcuts`")
            make_shortcut(
                "-m dioptas",
                name="Dioptas",
                description="Dioptas 2D XRD {}".format(__version__),
                icon=os.path.join(icons_path, "icon"),
                terminal=False,
            )

        elif sys.argv[1].startswith("version"):
            print(__version__)

        elif sys.argv[1].endswith(".json"):
            controller = MainController(config_file=sys.argv[1])
            controller.show_window()
            app.exec_()
    del app

# SPDX-License-Identifier: MIT

import os
import sys
from sys import platform as _platform

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


def main():
    global _dioptrin_available

    app = QtWidgets.QApplication([])

    apply_stylesheet(
        app,
        theme=theme_path,
        css_file=qss_path,
        extra={"density_scale": -2},
    )
    sys.excepthook = excepthook
    print("Dioptas {}".format(__version__))

    _dioptrin_available = _check_dioptrin_license()

    if len(sys.argv) == 1:  # normal start
        controller = MainController()
        controller.show_window()
        app.exec_()
    else:  # with command line arguments
        if sys.argv[1] == "test":
            controller = MainController(use_settings=False)
            controller.show_window()

        elif sys.argv[1].startswith("makeshortcut"):
            if make_shortcut is None:
                raise ImportError("pyshortcuts not installed.  Try `pip install pyshortcuts`")
            binary_dir = "Scripts" if os.name == "nt" else "bin"
            make_shortcut(
                os.path.join(sys.exec_prefix, binary_dir, "dioptas"),
                name = "Dioptas",
                description="Dioptas 2D XRD {}".format(__version__),
                icon=os.path.join(icons_path, "icon")
                )

        elif sys.argv[1].startswith("version"):
            print(__version__)

        elif sys.argv[1].endswith(".json"):
            controller = MainController(config_file=sys.argv[1])
            controller.show_window()
            app.exec_()
    del app

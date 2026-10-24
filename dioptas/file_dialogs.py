# SPDX-License-Identifier: MIT
"""Process-local workaround for macOS native open/save panel initialization stalls."""

import os
import sys
from qtpy import QtCore, QtWidgets


def configure_file_dialogs(*, experimental=False):
    """Use Qt panels in the macOS experiment, or by explicit process opt-in.

    The application flag also covers directory choosers and direct QFileDialog
    calls. It changes no macOS service, user preference or saved application state.
    """
    if (experimental and sys.platform == "darwin") or os.environ.get(
        "DIOPTAS_QT_FILE_DIALOGS"
    ) == "1":
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_DontUseNativeDialogs, True)


def file_dialog_kwargs():
    if QtCore.QCoreApplication.testAttribute(QtCore.Qt.AA_DontUseNativeDialogs):
        return {
            "options": QtWidgets.QFileDialog.DontUseNativeDialog
            | QtWidgets.QFileDialog.DontUseCustomDirectoryIcons
        }
    return {}

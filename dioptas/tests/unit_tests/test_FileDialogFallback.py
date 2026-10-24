"""Native panels are bypassed only in the Mac experiment or explicit opt-in."""

from unittest.mock import Mock
import pytest
from qtpy import QtCore, QtWidgets
from dioptas import file_dialogs
from dioptas.widgets.UtilityWidgets import (
    open_file_dialog,
    open_files_dialog,
    save_file_dialog,
)


@pytest.fixture(autouse=True)
def restore_dialog_attribute():
    attribute = QtCore.Qt.AA_DontUseNativeDialogs
    before = QtCore.QCoreApplication.testAttribute(attribute)
    QtCore.QCoreApplication.setAttribute(attribute, False)
    yield
    QtCore.QCoreApplication.setAttribute(attribute, before)


@pytest.mark.parametrize(
    "platform,experimental,override,expected",
    [
        ("darwin", True, "", True),
        ("darwin", False, "", False),
        ("linux", True, "", False),
        ("win32", True, "", False),
        ("linux", False, "1", True),
        ("darwin", False, "1", True),
    ],
)
def test_scoped_dialog_policy(monkeypatch, platform, experimental, override, expected):
    monkeypatch.setattr(file_dialogs.sys, "platform", platform)
    monkeypatch.setenv("DIOPTAS_QT_FILE_DIALOGS", override)
    file_dialogs.configure_file_dialogs(experimental=experimental)
    assert (
        QtCore.QCoreApplication.testAttribute(QtCore.Qt.AA_DontUseNativeDialogs)
        is expected
    )
    if expected:
        options = file_dialogs.file_dialog_kwargs()["options"]
        assert options & QtWidgets.QFileDialog.DontUseNativeDialog
        assert options & QtWidgets.QFileDialog.DontUseCustomDirectoryIcons
    else:
        assert file_dialogs.file_dialog_kwargs() == {}


def test_open_multi_save_and_cancel_contracts(qapp, monkeypatch):
    monkeypatch.setenv("DIOPTAS_QT_FILE_DIALOGS", "1")
    file_dialogs.configure_file_dialogs()
    single = Mock(return_value=("/tmp/counts.tif", "Images (*.tif)"))
    multi = Mock(return_value=(["/tmp/a.tif", "/tmp/b.tif"], "Images (*.tif)"))
    save = Mock(return_value=("/tmp/report", "JSON (*.json)"))
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", single)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames", multi)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", save)
    assert open_file_dialog(None, "Open", "/tmp") == "/tmp/counts.tif"
    assert open_files_dialog(None, "Open", "/tmp") == ["/tmp/a.tif", "/tmp/b.tif"]
    assert save_file_dialog(None, "Save", "/tmp") == "/tmp/report.json"
    for method in (single, multi, save):
        assert (
            method.call_args.kwargs["options"]
            & QtWidgets.QFileDialog.DontUseNativeDialog
        )
    single.return_value = ("", "")
    save.return_value = ("", "")
    assert open_file_dialog(None, "Open", "/tmp") == ""
    assert save_file_dialog(None, "Save", "/tmp") == ""

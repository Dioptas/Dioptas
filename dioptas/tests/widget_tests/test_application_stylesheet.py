# SPDX-License-Identifier: MIT

import builtins

import pytest
from qt_material import apply_stylesheet

from dioptas import _apply_application_stylesheet, qss_path, theme_path
from dioptas.widgets.CustomWidgets import render_icon


@pytest.mark.parametrize("encoding", ["gbk", "big5", "cp1252", "ascii"])
def test_application_resources_are_independent_of_system_encoding(
    qapp, monkeypatch, encoding
):
    """Exercise bundled CSS and SVGs under non-UTF-8 text-open defaults."""
    original_open = builtins.open
    default_encoding = "utf-8"

    def locale_open(
        file, mode="r", buffering=-1, encoding=None, errors=None,
        newline=None, closefd=True, opener=None,
    ):
        if "b" not in mode and encoding is None:
            encoding = default_encoding
        return original_open(
            file, mode, buffering, encoding, errors, newline, closefd, opener
        )

    monkeypatch.setattr(builtins, "open", locale_open)
    previous_stylesheet = qapp.styleSheet()
    previous_palette = qapp.palette()
    previous_style = qapp.style().objectName()
    try:
        # Preserve the appearance and theme-variable substitution of the
        # original startup path when it runs with a UTF-8 system encoding.
        apply_stylesheet(
            qapp, theme=theme_path, css_file=qss_path,
            extra={"density_scale": -2},
        )
        expected_stylesheet = qapp.styleSheet()
        qapp.setStyleSheet("")

        default_encoding = encoding
        _apply_application_stylesheet(qapp)

        assert qapp.styleSheet() == expected_stylesheet
        assert "#phase_table_widget" in qapp.styleSheet()
        assert "{QTMATERIAL_" not in qapp.styleSheet()
        icon = render_icon("mask_imprint.svg", color="#ff8800")
        assert not icon.isNull()
    finally:
        qapp.setStyle(previous_style)
        qapp.setStyleSheet(previous_stylesheet)
        qapp.setPalette(previous_palette)

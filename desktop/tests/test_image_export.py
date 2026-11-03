"""Image saving follows the Qt controller's data and orientation conventions."""

import base64
import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dioptas.desktop.session import DesktopSession

DATA = Path(__file__).resolve().parents[2] / "dioptas/tests/data"


def call(session, **payload):
    result = session.invoke("integration_save_image", payload)
    assert result["ok"], result.get("error")
    return result


@pytest.fixture
def session():
    session = DesktopSession()
    assert session.invoke("example")["ok"]
    assert session.invoke("open_calibration", {"path": str(DATA / "CeO2_Pilatus1M.poni")})["ok"]
    assert session.invoke("integration_settings", {"bins": 120, "cake_bins": 30})["ok"]
    return session


@pytest.mark.parametrize("source", ["image", "cake"])
def test_tiff_matches_qt_int32_orientation_and_preserves_science(session, tmp_path, source):
    c = session.configuration
    data = c.img_model.img_data if source == "image" else c.calibration_model.cake_img
    before = data.copy()
    roi = c.roi
    path = tmp_path / f"{source}.tiff"
    result = call(session, source=source, path=str(path))
    assert result["savedPath"] == str(path)
    with Image.open(path) as image:
        np.testing.assert_array_equal(np.asarray(image), np.flipud(np.int32(before)))
    np.testing.assert_array_equal(data, before)
    assert c.roi == roi


@pytest.mark.parametrize("suffix,delimiter", [("txt", " "), ("csv", ",")])
def test_cake_text_has_radial_header_azimuth_column_and_qt_precision(session, tmp_path, suffix, delimiter):
    path = tmp_path / f"cake.{suffix}"
    call(session, source="cake", path=str(path))
    matrix = np.loadtxt(path, delimiter=delimiter)
    c = session.configuration.calibration_model
    np.testing.assert_allclose(matrix[0, 1:], c.cake_tth, atol=.00051)
    np.testing.assert_allclose(matrix[1:, 0], c.cake_azi, atol=.0051)
    np.testing.assert_allclose(matrix[1:, 1:], c.cake_img, atol=.501)


def test_png_keeps_view_rendering_and_adds_default_suffix(session, tmp_path):
    image = Image.new("RGBA", (2048, 768), (30, 60, 90, 255))
    data = io.BytesIO()
    image.save(data, format="PNG")
    encoded = base64.b64encode(data.getvalue()).decode("ascii")
    result = call(session, path=str(tmp_path / "view"), png_data=encoded)
    assert Path(result["savedPath"]).suffix == ".png"
    assert Path(result["savedPath"]).read_bytes() == data.getvalue()


def test_invalid_export_does_not_write_files(session, tmp_path):
    for source, name, payload in [
        ("other", "bad.tiff", {}),
        ("image", "bad.txt", {}),
        ("cake", "bad.jpg", {}),
        ("image", "bad.png", {}),
        ("image", "bad.png", {"png_data": "not a PNG"}),
    ]:
        path = tmp_path / name
        result = session.invoke("integration_save_image", {"source": source, "path": str(path), **payload})
        assert not result["ok"]
        assert not path.exists()


def test_empty_and_unintegrated_cake_rejected_and_dialog_cancel_is_noop(tmp_path):
    session = DesktopSession(choose_file=lambda kind, save: None)
    assert not session.invoke("integration_save_image", {"path": str(tmp_path / "empty.tiff")})["ok"]
    assert session.invoke("example")["ok"]
    assert not session.invoke("integration_save_image", {"source": "cake", "path": str(tmp_path / "cake.tiff")})["ok"]
    result = call(session)
    assert result["cancelled"]
    assert not list(tmp_path.iterdir())

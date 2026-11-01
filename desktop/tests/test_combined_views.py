"""Cross-view checks for the combined Mask, Integration and Map session."""

from pathlib import Path

import numpy as np

from dioptas.desktop.session import DesktopSession


DATA = Path(__file__).resolve().parents[2] / "dioptas/tests/data"


def call(session, command, **payload):
    result = session.invoke(command, payload)
    assert result["ok"], result.get("error")
    return result


def test_mask_integration_and_map_share_settings_and_project_state(tmp_path):
    session = DesktopSession()
    call(session, "example")
    call(session, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    initial = call(
        session, "integration_settings", bins=250, cake_bins=30,
        unit="q_A^-1", trim_zeros=False,
    )
    edited = call(
        session, "mask_edit", operation="rectangle", points=[[400, 0], [980.5, 1042.5]],
    )
    assert edited["state"]["maskedPixels"] > 0
    assert not np.allclose(
        np.asarray(initial["pattern"]["y"], dtype=float),
        np.asarray(edited["pattern"]["y"], dtype=float), equal_nan=True,
    )
    mask = edited["mask"]["data"]
    expected = edited["pattern"]

    mapped = call(session, "map_load", paths=[str(DATA / "CeO2_Pilatus1M.tif")] * 2)
    assert mapped["map"]["points"] == 2
    np.testing.assert_allclose(mapped["pattern"]["x"], expected["x"])
    np.testing.assert_allclose(
        np.asarray(mapped["pattern"]["y"], dtype=float),
        np.asarray(expected["y"], dtype=float), equal_nan=True,
    )
    assert mapped["mask"]["data"] == mask

    project = tmp_path / "all-views.dio"
    call(session, "save_project", path=str(project))
    reopened = call(DesktopSession(), "open_project", path=str(project))
    assert reopened["map"]["points"] == 2
    assert reopened["mask"]["data"] == mask
    assert reopened["state"]["bins"] == 250
    assert reopened["state"]["unit"] == "q_A^-1"
    assert reopened["state"]["integration"]["cakeBins"] == 30
    assert reopened["state"]["calibrated"]

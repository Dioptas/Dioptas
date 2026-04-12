# SPDX-License-Identifier: MIT

import json
from unittest.mock import patch, MagicMock

from dioptas.model.UpdateChecker import check_for_update


def _mock_response(tag_name, html_url="https://github.com/CPrescher/Dioptas/releases/tag/0.9.0"):
    """Create a mock urllib response with the given tag name."""
    data = json.dumps({"tag_name": tag_name, "html_url": html_url}).encode()
    resp = MagicMock()
    resp.read.return_value = data
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


@patch("dioptas.model.UpdateChecker.urllib.request.urlopen")
def test_update_available(mock_urlopen):
    mock_urlopen.return_value = _mock_response("1.0.0")
    result = check_for_update("0.8.4")
    assert result is not None
    assert result["version"] == "1.0.0"
    assert "releases" in result["url"]


@patch("dioptas.model.UpdateChecker.urllib.request.urlopen")
def test_no_update_when_current(mock_urlopen):
    mock_urlopen.return_value = _mock_response("0.8.4")
    result = check_for_update("0.8.4")
    assert result is None


@patch("dioptas.model.UpdateChecker.urllib.request.urlopen")
def test_no_update_when_ahead(mock_urlopen):
    mock_urlopen.return_value = _mock_response("0.8.3")
    result = check_for_update("0.8.4")
    assert result is None


@patch("dioptas.model.UpdateChecker.urllib.request.urlopen")
def test_network_error_returns_none(mock_urlopen):
    mock_urlopen.side_effect = OSError("no network")
    result = check_for_update("0.8.4")
    assert result is None


def test_invalid_current_version_returns_none():
    result = check_for_update("not-a-version")
    assert result is None


@patch("dioptas.model.UpdateChecker.urllib.request.urlopen")
def test_invalid_remote_tag_returns_none(mock_urlopen):
    mock_urlopen.return_value = _mock_response("invalid-tag")
    result = check_for_update("0.8.4")
    assert result is None

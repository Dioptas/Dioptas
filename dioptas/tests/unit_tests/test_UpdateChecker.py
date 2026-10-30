# SPDX-License-Identifier: MIT

import json
import urllib.error
from unittest.mock import patch, MagicMock

from dioptas.model.UpdateChecker import check_for_update


def _mock_response(tag_name, html_url="https://github.com/Dioptas/Dioptas/releases/tag/0.9.0"):
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
    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://api.github.com/repos/Dioptas/Dioptas/releases/latest"
    assert request.get_header("User-agent") == "Dioptas/0.8.4"
    assert mock_urlopen.call_args.kwargs["timeout"] == 5


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


@patch("dioptas.model.UpdateChecker.urllib.request.urlopen")
def test_feed_failure_is_logged_instead_of_silently_appearing_current(mock_urlopen, caplog):
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://api.github.com/repos/CPrescher/Dioptas/releases/latest",
        404, "Not Found", {}, None,
    )
    assert check_for_update("0.10.0") is None
    assert "Update check failed" in caplog.text
    assert "404" in caplog.text


@patch("dioptas.model.UpdateChecker.urllib.request.urlopen")
def test_malformed_feed_is_handled(mock_urlopen):
    response = _mock_response("1.0.0")
    mock_urlopen.return_value = response
    for payload in (b"not json", b"[]", b"null", b"\xff"):
        response.read.return_value = payload
        assert check_for_update("0.10.0") is None


@patch("dioptas.model.UpdateChecker.urllib.request.urlopen")
def test_update_without_a_download_page_does_not_open_an_empty_link(mock_urlopen):
    mock_urlopen.return_value = _mock_response("1.0.0", html_url="")
    assert check_for_update("0.10.0") is None

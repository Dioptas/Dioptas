# SPDX-License-Identifier: MIT

import logging
import json
import urllib.request
import urllib.error
from packaging.version import Version

logger = logging.getLogger(__name__)

GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/CPrescher/Dioptas/releases/latest"
)


def check_for_update(current_version: str) -> dict | None:
    """Check GitHub for a newer Dioptas release.

    Returns a dict with 'version' and 'url' keys if a newer version is
    available, or None if the current version is up-to-date or the check fails.

    This function performs a network request and should be called from a
    background thread.
    """
    try:
        current = Version(current_version)
    except Exception:
        logger.debug("Cannot parse current version: %s", current_version)
        return None

    try:
        req = urllib.request.Request(
            GITHUB_RELEASES_URL,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        logger.debug("Update check failed: %s", e)
        return None

    tag = data.get("tag_name", "")
    html_url = data.get("html_url", "")

    try:
        latest = Version(tag)
    except Exception:
        logger.debug("Cannot parse remote version tag: %s", tag)
        return None

    if latest > current:
        return {"version": str(latest), "url": html_url}
    return None

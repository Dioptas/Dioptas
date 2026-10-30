# SPDX-License-Identifier: MIT

import logging
import json
import urllib.request
import urllib.error
from packaging.version import Version

logger = logging.getLogger(__name__)

GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/Dioptas/Dioptas/releases/latest"
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
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"Dioptas/{current_version}",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, UnicodeError, json.JSONDecodeError) as e:
        logger.warning("Update check failed for %s: %s", GITHUB_RELEASES_URL, e)
        return None

    if not isinstance(data, dict):
        logger.warning("Update check returned an invalid release record")
        return None
    tag = data.get("tag_name", "")
    html_url = data.get("html_url", "")

    try:
        latest = Version(tag)
    except Exception:
        logger.debug("Cannot parse remote version tag: %s", tag)
        return None

    if latest > current and isinstance(html_url, str) and html_url:
        logger.info("Dioptas update available: %s → %s", current, latest)
        return {"version": str(latest), "url": html_url}
    logger.info("Dioptas update check: installed %s, latest release %s", current, latest)
    return None

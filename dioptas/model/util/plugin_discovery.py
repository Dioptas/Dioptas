# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.metadata
import importlib.util
import inspect
import logging
import sys
from pathlib import Path

from .MaskPlugin import MaskPluginBase

logger = logging.getLogger(__name__)

MASK_PLUGIN_ENTRY_POINT_GROUP = "dioptas.plugins.masks"
USER_PLUGIN_DIR = Path.home() / ".dioptas" / "plugins" / "masks"


def discover_mask_plugins() -> list[type[MaskPluginBase]]:
    """Discover mask plugin classes from entry points and user directory."""
    plugins: list[type[MaskPluginBase]] = []

    # Tier 1: entry points (pip-installed plugins)
    plugins.extend(_discover_from_entry_points())

    # Tier 2: user plugin directory (~/.dioptas/plugins/masks/)
    plugins.extend(_discover_from_directory(USER_PLUGIN_DIR))

    return plugins


def _discover_from_entry_points() -> list[type[MaskPluginBase]]:
    plugins = []
    try:
        eps = importlib.metadata.entry_points(group=MASK_PLUGIN_ENTRY_POINT_GROUP)
    except TypeError:
        # Python 3.9 compatibility: entry_points() doesn't accept group kwarg
        eps = importlib.metadata.entry_points().get(MASK_PLUGIN_ENTRY_POINT_GROUP, [])

    for ep in eps:
        try:
            cls = ep.load()
            if isinstance(cls, type) and issubclass(cls, MaskPluginBase):
                plugins.append(cls)
                logger.info("Discovered mask plugin from entry point: %s", cls.name)
            else:
                logger.warning(
                    "Entry point %s does not point to a MaskPluginBase subclass",
                    ep.name,
                )
        except Exception:
            logger.exception("Failed to load mask plugin entry point: %s", ep.name)

    return plugins


def _discover_from_directory(plugin_dir: Path) -> list[type[MaskPluginBase]]:
    plugins = []
    if not plugin_dir.is_dir():
        return plugins

    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            module_name = f"dioptas_user_mask_plugin_{py_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, MaskPluginBase)
                    and obj is not MaskPluginBase
                    and obj.__module__ == module_name
                ):
                    plugins.append(obj)
                    logger.info(
                        "Discovered mask plugin from %s: %s", py_file.name, obj.name
                    )
        except Exception:
            logger.exception("Failed to load mask plugin from %s", py_file)

    return plugins

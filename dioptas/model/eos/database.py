# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
Loader and search for the bundled EoS material database.

The database ships with Dioptas as one JSON file per material in
``resources/eos_database/`` (see material.py for the schema). It is
curated in the repository like the calibrant files: new materials or
literature references are added by pull request and become part of the
next release — versioned, citable, and available offline.
"""

from __future__ import annotations

import json
import logging
import os

from ...paths import resources_path
from .material import Material

logger = logging.getLogger(__name__)

eos_database_path = os.path.join(resources_path, "eos_database")

# Common-name shortcuts for friendlier search
_ALIASES = {
    "gold": "Au", "silver": "Ag", "iron": "Fe", "copper": "Cu",
    "aluminium": "Al", "magnesium": "Mg", "titanium": "Ti",
    "osmium": "Os", "manganese": "Mn",
    "platinum": "Pt", "iridium": "Ir", "rhenium": "Re", "tungsten": "W",
    "neon": "Ne", "argon": "Ar",
    "alumina": "Al2O3", "corundum": "Al2O3",
    "magnesia": "MgO", "periclase": "MgO",
    "hematite": "Fe2O3", "boron carbide": "B4C",
    "wollastonite": "CaSiO3", "perovskite": "CaSiO3",
    "akimotoite": "MgSiO3", "orthoenstatite": "MgSiO3",
    "enstatite": "MgSiO3", "pyrope": "Mg3Al2Si3O12",
    "almandine": "Fe3Al2Si3O12", "fayalite": "Fe2SiO4",
    "seifertite": "SiO2",
}

_cache: dict = {}


def load_materials(directory: str | None = None) -> list:
    """
    All materials of the bundled database (or of *directory*), sorted by
    name. Loaded once per directory and cached; unreadable files are
    skipped with a warning rather than breaking the whole database.
    """
    directory = directory or eos_database_path
    if directory in _cache:
        return _cache[directory]

    materials = []
    try:
        filenames = sorted(os.listdir(directory))
    except OSError as e:
        logger.warning("EoS database directory unreadable: %s", e)
        filenames = []
    for filename in filenames:
        if not filename.endswith(".json"):
            continue
        path = os.path.join(directory, filename)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                materials.append(Material.from_dict(json.load(fh)))
        except (OSError, ValueError, KeyError) as e:
            logger.warning("Skipping unreadable EoS database file %s: %s",
                           filename, e)
    materials.sort(key=lambda m: m.name.lower())
    _cache[directory] = materials
    return materials


def search_materials(query: str, materials: list | None = None) -> list:
    """
    Case-insensitive substring search over name and formula, with
    common-name aliases ('gold' finds Au). An empty query returns
    everything.
    """
    if materials is None:
        materials = load_materials()
    query = (query or "").strip()
    if not query:
        return list(materials)
    terms = {query.lower()}
    alias = _ALIASES.get(query.lower())
    if alias:
        terms.add(alias.lower())
    return [
        m for m in materials
        if any(term in m.name.lower() or term in m.formula.lower()
               for term in terms)
    ]

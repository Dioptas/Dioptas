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
import math
import os

from ...paths import resources_path
from .material import Material, _parse_formula

logger = logging.getLogger(__name__)

eos_database_path = os.path.join(resources_path, "eos_database")

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
    Ranked material search over names, formulas, and material-owned aliases.

    A query that is itself a chemical formula additionally finds formulas
    with equivalent stoichiometry, the same set of elements, or (for queries
    containing at least two elements) a superset of the requested elements.
    This makes both ``MgFeO`` and the shorter ``MgFe`` find ``Mg2Fe3O5``
    while more specific formula and textual matches remain first. An empty
    query returns all materials in their original order.
    """
    if materials is None:
        materials = load_materials()
    query = (query or "").strip()
    if not query:
        return list(materials)

    ranked = []
    for original_index, material in enumerate(materials):
        rank = _material_search_rank(query, material)
        if rank is not None:
            ranked.append((rank, original_index, material))
    ranked.sort(key=lambda hit: (hit[0], hit[1]))
    return [material for _, _, material in ranked]


def _material_search_rank(query: str, material: Material) -> int | None:
    """Best match category for *material*; lower values rank first."""
    query_text = query.casefold()
    name = material.name.casefold()
    formula = material.formula.casefold()
    aliases = [alias.casefold() for alias in material.aliases]

    if query_text == formula and formula:
        return 0
    if query_text == name or query_text in aliases:
        return 1

    formula_rank = _formula_search_rank(query, material.formula)
    if formula_rank == 2:
        return formula_rank

    searchable_text = [name, formula, *aliases]
    if any(value.startswith(query_text) for value in searchable_text):
        return 3
    if any(query_text in value for value in searchable_text):
        return 4
    return formula_rank


def _formula_search_rank(query: str, formula: str) -> int | None:
    """Rank equivalent, same-element, and multi-element subset matches."""
    query_composition = _formula_composition(query)
    material_composition = _formula_composition(formula)
    if not query_composition or not material_composition:
        return None

    query_elements = set(query_composition)
    material_elements = set(material_composition)
    if query_elements != material_elements:
        if len(query_elements) >= 2 and query_elements < material_elements:
            return 6
        return None

    query_total = sum(query_composition.values())
    material_total = sum(material_composition.values())
    equivalent = all(math.isclose(
        query_composition[element] / query_total,
        material_composition[element] / material_total,
        rel_tol=1e-9,
        abs_tol=1e-12,
    ) for element in query_composition)
    return 2 if equivalent else 5


def _formula_composition(formula: str) -> dict[str, float]:
    """Aggregate a parsed formula into one amount per element."""
    composition = {}
    for element, amount in _parse_formula(formula):
        composition[element] = composition.get(element, 0.0) + float(amount)
    return composition

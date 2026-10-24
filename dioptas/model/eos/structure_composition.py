# SPDX-License-Identifier: MIT
"""Occupancy-weighted cell composition and a formula-relative crystallographic Z.

This is a derived diagnostic. It never changes a source formula, stored Z, or
the normalization of an EoS record.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from math import fsum, isfinite
import re

import numpy as np
import xraydb

from ..util.phasesmith import _space_group_info


POSITION_TOLERANCE = 1e-10  # Same fractional-coordinate tolerance as diffraction.
COMPOSITION_RTOL = 1e-4
COMPOSITION_ATOL = 1e-8


def _element(symbol):
    # This comparison is elemental, not isotopic; D and T count as hydrogen.
    symbol = 'H' if symbol in ('D', 'T') else symbol
    number = xraydb.atomic_number(symbol)
    if not number:
        raise ValueError(f'Unknown element {symbol!r}.')
    return xraydb.atomic_symbol(number)


def formula_composition(formula):
    """Parse fixed stoichiometries, groups, decimals and middle-dot hydrates.

    Unsupported charges, isotope notation and variable compositions fail as a
    whole. A period is a decimal point; hydrate separators must use ``·``.
    """
    text = re.sub(r'\s+', '', str(formula or '')).translate(
        str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789'))
    position = 0

    def amount():
        nonlocal position
        match = re.match(r'(?:\d+(?:\.\d*)?|\.\d+)', text[position:])
        if not match:
            return 1.
        position += len(match[0])
        value = float(match[0])
        if not isfinite(value):
            raise ValueError('Formula coefficients must be finite.')
        return value

    def sequence(closing=None, depth=0):
        nonlocal position
        if depth > 32:
            raise ValueError('Formula grouping is too deeply nested.')
        counts = defaultdict(float)
        terms = 0
        while position < len(text) and text[position] not in ')]·':
            char = text[position]
            if char in '([':
                position += 1
                part = sequence(')' if char == '(' else ']', depth + 1)
            else:
                match = re.match(r'[A-Z][a-z]?', text[position:])
                if not match:
                    raise ValueError('Formula needs fixed element counts, e.g. CaMgSi2O6.')
                position += len(match[0])
                part = {_element(match[0]): 1.}
            factor = amount()
            for element, count in part.items():
                counts[element] += count * factor
            terms += 1
        if not terms:
            raise ValueError('Formula contains an empty group or component.')
        if closing:
            if position >= len(text) or text[position] != closing:
                raise ValueError('Formula has unmatched grouping brackets.')
            position += 1
        return counts

    counts = defaultdict(float)
    while position < len(text):
        factor = amount()
        if factor <= 0:
            raise ValueError('Formula component multipliers must be positive.')
        for element, count in sequence().items():
            counts[element] += count * factor
        if position < len(text):
            if text[position] != '·' or position == len(text) - 1:
                raise ValueError('Formula has unsupported or unmatched syntax.')
            position += 1
    if not counts or not any(counts.values()) or not all(map(isfinite, counts.values())):
        raise ValueError('No fixed chemical formula is available.')
    return {element: count for element, count in counts.items() if count > 0}


@dataclass
class StructureComposition:
    status: str  # consistent, mismatch, or unavailable
    message: str
    z: float | None = None
    cell_counts: dict = field(default_factory=dict)
    formula_counts: dict = field(default_factory=dict)
    multiplicities: tuple = ()
    ratios: dict = field(default_factory=dict)

    def details(self):
        def counts_text(counts):
            return ', '.join(f'{element}: {value:.6g}' for element, value in counts.items())

        lines = [self.message]
        if self.cell_counts:
            lines.append('Atoms per cell: ' + counts_text(self.cell_counts))
        if self.formula_counts:
            lines.append('Atoms per formula: ' + counts_text(self.formula_counts))
        if self.ratios:
            lines.append('Cell / formula by element: ' + counts_text(self.ratios))
        if self.multiplicities:
            lines.append('Site multiplicities (table order): '
                         + ', '.join(map(str, self.multiplicities)))
        lines.extend([
            'Cell counts = sum of symmetry multiplicity × occupancy for each element.',
            'Formula comparison tolerance: 0.01% relative, 1e-8 atoms absolute. '
            'Fractional-coordinate tolerance: 1e-10.',
            'D and T count as H in this elemental comparison. '
            'Z depends on the formula normalization; fractional average occupancies are retained.',
            'The stored Z and EoS parameters are retained.',
        ])
        return '\n'.join(lines)


def assess_structure_composition(document):
    """Expand the asymmetric unit and require one Z for every formula element.

    Special positions are deduplicated within each site by PhaseSmith. Distinct
    rows on the same symmetry orbit remain additive (mixed occupancy), but total
    occupancy above one is reported as unavailable instead of assigning a Z.
    """
    result = StructureComposition('unavailable', 'No atomic sites or space group available.')
    sites = document.get('atom_sites') or []
    if not sites or not document.get('space_group'):
        return result
    try:
        group = _space_group_info(document['space_group'],
                                  document.get('space_group_number')).space_group
        coordinates = np.array([[float(site[key]) for key in ('x', 'y', 'z')]
                                for site in sites])
        occupancies = np.array([float(site.get('occupancy', 1.)) for site in sites])
        if not np.isfinite(occupancies).all() or np.any((occupancies < 0) | (occupancies > 1)):
            raise ValueError('Site occupancies must be finite and between zero and one.')
        elements = [_element(str(site.get('element') or '').strip()) for site in sites]
        expanded = group.expand_sites(coordinates, tolerance=POSITION_TOLERANCE)
        multiplicities = np.bincount(expanded.source_site, minlength=len(sites))
        result.multiplicities = tuple(map(int, multiplicities))
        cell_counts = defaultdict(float)
        orbits = []
        for index, (element, occupancy) in enumerate(zip(elements, occupancies)):
            if occupancy == 0:
                continue
            positions = expanded.fractional_xyz[expanded.source_site == index]
            for orbit in orbits:
                delta = np.abs(orbit[0] - positions[0])
                if np.any(np.all(np.minimum(delta, 1. - delta) <= POSITION_TOLERANCE, axis=1)):
                    orbit[1] += occupancy
                    if orbit[1] > 1. + COMPOSITION_ATOL:
                        raise ValueError('Symmetry-equivalent site rows have total occupancy above one. '
                                         'Check duplicate sites or mixed occupancies.')
                    break
            else:
                orbits.append([positions, occupancy])
            cell_counts[element] += int(multiplicities[index]) * occupancy
        result.cell_counts = dict(cell_counts)
        if not cell_counts:
            raise ValueError('All site occupancies are zero.')
        result.formula_counts = formula_composition(document.get('formula'))
        result.ratios = {element: cell_counts.get(element, 0.) / count
                         for element, count in result.formula_counts.items()}
        if cell_counts.keys() != result.formula_counts.keys():
            result.status = 'mismatch'
            result.message = 'Structure and formula contain different elements; no common Z.'
            return result
        z = fsum(result.ratios.values()) / len(result.ratios)
        if not all(np.isclose(cell_counts[element], z * count,
                              rtol=COMPOSITION_RTOL, atol=COMPOSITION_ATOL)
                   for element, count in result.formula_counts.items()):
            result.status = 'mismatch'
            result.message = 'Element ratios disagree; no single Z matches the chemical formula.'
            return result
        result.status = 'consistent'
        result.z = z
        result.message = 'The occupancy-weighted cell composition matches the chemical formula.'
    except (ValueError, TypeError, KeyError, RuntimeError, OverflowError) as error:
        result.message = str(error)
    return result

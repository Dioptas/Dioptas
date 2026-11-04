# SPDX-License-Identifier: MIT
"""Derived site labels in the declared setting, without inferring a new group."""
from fractions import Fraction
from functools import lru_cache
from itertools import product
import json
from pathlib import Path
import re

import numpy as np

TOLERANCE = 1e-10  # Same fractional-coordinate tolerance as PhaseSmith expansion.
SHIFTS = np.asarray(list(product(range(-2, 3), repeat=3)), dtype=float)


def hall_key(symbol):
    # Moyo uses = for the double-prime axis; PhaseSmith prints its Hall quote.
    # Token boundaries distinguish e.g. P 32 (screw) from P 3 2.
    return ' '.join(symbol.replace('=', '"').split())


@lru_cache(maxsize=1)
def wyckoff_settings():
    path = Path(__file__).resolve().parents[1] / 'resources/data/wyckoff/positions.json'
    settings = json.loads(path.read_text())['settings']
    return {(hall_key(s['hall']), s['setting']): s for s in settings}


@lru_cache(maxsize=4096)
def affine_space(coordinates):
    linear = np.zeros((3, 3))
    origin = np.zeros(3)
    for row, expression in enumerate(coordinates.replace(' ', '').split(',')):
        for token in re.findall(r'[+-]?[^+-]+', expression):
            match = re.fullmatch(r'([+-]?)(\d*)([xyz])', token)
            if match:
                sign, coefficient, variable = match.groups()
                linear[row, 'xyz'.index(variable)] += (-1 if sign == '-' else 1) * int(coefficient or 1)
            else:
                origin[row] += float(Fraction(token))
    projection = np.eye(3) - linear @ np.linalg.pinv(linear)
    return linear, origin, projection


@lru_cache(maxsize=8192)
def classify_site(symbol, expected_number, xyz):
    from dioptas.model.util.phasesmith import _space_group_info
    if symbol.isdigit():
        from dioptas.model.util.phasesmith import resolve_space_group
        _, info = resolve_space_group(symbol)
        if expected_number is not None and info.number != expected_number:
            raise ValueError('The declared group number does not match the symbol.')
    else:
        info = _space_group_info(symbol, expected_number)
    return classify_with_info(info, xyz)


def classify_with_info(info, xyz):
    key = hall_key(info.hall_symbol)
    setting = wyckoff_settings().get((key, getattr(info, 'setting', '')))
    if setting is None:
        candidates = [s for (hall, _), s in wyckoff_settings().items() if hall == key and s['number'] == info.number]
        if len(candidates) == 1:
            setting = candidates[0]
    orbit = info.space_group.expand_sites(np.asarray([xyz]), tolerance=TOLERANCE).fractional_xyz
    multiplicity = len(orbit)
    if not setting or setting['number'] != info.number:
        return dict(label=None, multiplicity=multiplicity, detail='No Wyckoff table for this explicit Hall setting.')
    # Matching against every equivalent position keeps classification independent
    # of chemistry, duplicate/partly occupied sites and origin representatives.
    for count, letter, symmetry, coordinates in setting['positions']:
        if count != multiplicity:
            continue
        _, origin, projection = affine_space(coordinates)
        differences = np.asarray(orbit)[:, None, :] - origin + SHIFTS[None, :, :]
        residual = differences @ projection.T
        if np.any(np.max(np.abs(residual), axis=-1) <= TOLERANCE):
            return dict(label=f'{count}{letter}', multiplicity=count,
                detail=f'Calculated from {info.hm_symbol} (No. {info.number}), Hall {info.hall_symbol}; site symmetry {symmetry}.')
    return dict(label=None, multiplicity=multiplicity, detail='No Wyckoff position matched at fractional tolerance 1e-10.')


def site_labels(document):
    symbol = document.get('space_group') or ''
    number = document.get('space_group_number')
    result = []
    for site in document.get('atom_sites') or []:
        try:
            xyz = tuple(float(site[k]) for k in ('x', 'y', 'z'))
            if not np.isfinite(xyz).all():
                raise ValueError('Non-finite coordinates')
            result.append(classify_site(symbol, number, xyz))
        except (ValueError, KeyError, RuntimeError) as error:
            result.append(dict(label=None, multiplicity=None, detail=str(error)))
    return result


@lru_cache(maxsize=1)
def element_choices():
    import xraydb
    from dioptas.model.util.phasesmith import normalize_element_symbol
    result = []
    for number in range(1, 119):
        symbol = xraydb.atomic_symbol(number)
        try:
            normalize_element_symbol(symbol)
            enabled = True
        except ValueError:
            enabled = False
        result.append(dict(number=number, symbol=symbol, name=xraydb.atomic_name(symbol).capitalize(), enabled=enabled))
    return result

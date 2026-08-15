# -*- coding: utf-8 -*-
"""
Support for calculating D spacing for powder diffraction lines as
as function of pressure and temperature, given symmetry, zero-pressure lattice
constants and equation of state parameters.

Author:
  Mark Rivers

Created:
   Sept. 10, 2002 from older IDL version

Modifications:
    Sept. 26, 2002 MLR
        - Implemented Birch-Murnaghan solver using CARSnp.newton root finder
    Mai 27, 2014 Clemens Prescher
        - changed np function to numpy versions,
        - using scipy optimize for solving the inverse Birch-Murnaghan problem
        - fixed a bug which was causing a gamma0 to be 0 for cubic unit cell
    August 22, 2014 Clemens Prescher
        - calculation of d spacings is now done by using arrays
        - added several new utility function -- calculate_d0, add_reflection
        - updated the write_file function to be able to use new standard
    August 26, 2014 Clemens Prescher
        - added sorting functions
        - fixed the d spacing calculation for triclinic structure - equation used was wrong...
    August 27, 2014 Clemens Prescher
        - added modified flag and the surrounding functions. When an attribute is changed, it will set it to true and the
          filename and name will have an asterisk appended to indicate that this is not the original jcpds loaded
        - added a reload function
        - renamed read and write to load and save
        - the load function will now reset all parameters (previously parameters not set in the newly loaded file, were
          taken over from the previous state of the object)

"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import dataclasses
import string
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize, OptimizeResult
import os


class EosCalculationError(ArithmeticError):
    """The selected EoS cannot produce a physical state at the request."""


class jcpds_reflection:
    """
    Class that defines a reflection.
    Attributes:
       d0:     Zero-pressure lattice spacing
       d:      Lattice spacing at P and T
       inten:  Relative intensity to most intense reflection for this material
       h:      H index for this reflection
       k:      K index for this reflection
       l:      L index for this reflection

    """

    def __init__(self, h: float = 0., k: float = 0., l: float = 0., intensity: float = 0., d: float = 0.) -> None:
        self.d0: float = d
        self.d: float = d
        self.intensity: float = intensity
        self.h: float = h
        self.k: float = k
        self.l: float = l

    def __str__(self) -> str:
        return "{:2d},{:2d},{:2d}\t{:.2f}\t{:.3f}".format(self.h, self.k, self.l, self.intensity, self.d0)


@dataclass
class CrystalState:
    """The state of a jcpds phase — what a user sets or a file provides.

    Everything else the old params dict carried (a, b, c, alpha, beta,
    gamma, v, k0p, alpha_t) is *derived*: computed by compute_d for the
    current pressure and temperature. Reflections are state as
    (h, k, l, intensity, d0); their d values are derived too.

    A plain dataclass on purpose: the generic state layer (params_to_dict/
    params_from_dict) serializes it, undo snapshots capture it, and copying
    it cannot trip any write hook — the class of bug the old dict subclass
    invited (deepcopy replayed items through the auto-flagging __setitem__).
    """

    version: float = 0
    comments: list = field(default_factory=list)
    symmetry: str = ""
    k0: float = 0.0
    k0p0: float = 0.0
    #: K0'' (1/GPa) — only used by 4th-order equations (BM4, Modified
    #: Tait); stays 0 for everything else
    k0pp0: float = 0.0
    dk0dt: float = 0.0
    dk0pdt: float = 0.0
    alpha_t0: float = 0.0
    d_alpha_dt: float = 0.0
    a0: float = 0.0
    b0: float = 0.0
    c0: float = 0.0
    alpha0: float = 0.0
    beta0: float = 0.0
    gamma0: float = 0.0
    v0: float = 0.0
    pressure: float = 0.0
    temperature: float = 298.0
    #: equation of state used to compute the volume at pressure — a
    #: peritheos.eos.rt class name (see model/util/eos_phase.py). Legacy
    #: JCPDS files imply 3rd-order Birch-Murnaghan; phases from the EoS
    #: database carry their own.
    eos_type: str = "BM3"
    #: Holzapfel only: atoms per chemical formula (n), summed/effective atomic
    #: number parameter of the formula (z), and formula units per unit cell (zc,
    #: the crystallographic Z). Set for material-backed phases; None for
    #: legacy files, which then fall back to BM3.
    #: A literature record may override z (the Sokolova MgO workbook uses
    #: an effective value of 10.34 rather than the integer electron sum).
    n: float | None = None
    z: float | None = None
    zc: int | None = None
    #: thermal model on top of the equation of state. "" means the
    #: classic constant-coefficient correction (alpha_t0/d_alpha_dt/
    #: dk0dt/dk0pdt as effective-pressure shift — a no-op when they are
    #: zero, which keeps every legacy file and project behaving as
    #: before). A peritheos.eos.thermal class name ('MieGruneisenDebye',
    #: 'MieGruneisenEinstein', 'Sokolova2016') switches to the full thermal
    #: engine. The complete constructor dictionary is retained below;
    #: the scalar fields remain for the editable Debye/Einstein UI and
    #: backward-compatible projects.
    thermal_type: str = ""
    thermal_parameters: dict = field(default_factory=dict)
    thermal_parameter_errors: dict = field(default_factory=dict)
    thermal_fixed_parameters: list = field(default_factory=list)
    theta_t0: float = 0.0   # Debye/Einstein temperature (K)
    gamma_t0: float = 0.0   # Grüneisen parameter at V0
    q_t0: float = 1.0       # volume exponent of the Grüneisen parameter
    t_ref: float = 298.15   # reference temperature of the fit (K)
    #: the material's chemical formula and its EoS records (dicts, schema
    #: in model/eos/material.py), for the per-phase reference switcher.
    #: Set for material-backed phases; empty for legacy jcpds files. State so
    #: that the switcher survives project
    #: save/load and undo.
    chemistry: str = ""
    eos_records: list = field(default_factory=list)
    eos_current_index: int = 0
    #: Runtime ownership for each EoS record. ``bundled`` records are
    #: immutable; ``file`` and ``custom`` records are user-owned. Ownership
    #: survives a project round trip but is intentionally absent from
    #: portable .eosmat documents.
    eos_record_origins: list = field(default_factory=list)
    #: True after record management changes. Selecting another published
    #: reference is not itself an edit, but must not hide earlier unsaved
    #: custom-record changes by clearing the phase's modified marker.
    eos_records_modified: bool = False
    #: Preferred record for a user-owned material. Kept separately from the
    #: record dicts so choosing a local default never mutates a bundled record.
    eos_default_index: int = 0
    #: Canonical material structure/provenance without the EoS record list.
    #: Together with ``eos_records`` this is sufficient to export the phase as
    #: a full-fidelity .eosmat document.
    material_document: dict = field(default_factory=dict)
    #: ``bundled``, ``file``, ``cif``, ``custom`` or ``legacy``.
    material_origin: str = "legacy"
    #: Source-reported errors (same units as the record's EoS parameters)
    #: and the names of parameters held fixed in that fit.  These mirror the
    #: active record so downstream tools need not re-inspect eos_records.
    eos_parameter_errors: dict = field(default_factory=dict)
    eos_fixed_parameters: list = field(default_factory=list)
    #: Serializable structure input used to extend PhaseSmith reflection
    #: coverage after a new calibration or pattern increases the measured Q
    #: range. Empty for legacy/manual JCPDS phases.
    reflection_source: dict = field(default_factory=dict)
    reflection_q_max: float = 0.0
    reflection_wavelength: float = 0.0
    reflection_intensity_cutoff: float = 0.5
    #: whether the phase no longer matches the file it came from (the
    #: asterisk in the GUI); flipped by the params view on state writes
    modified: bool = False


#: state keys whose direct edit marks the phase as modified (the asterisk)
_FLAGGING_KEYS = frozenset(
    ["comments", "a0", "b0", "c0", "alpha0", "beta0", "gamma0", "symmetry",
     "k0", "k0p0", "k0pp0", "dk0dt", "dk0pdt", "alpha_t0", "d_alpha_dt",
     "reflections", "eos_type",
     "thermal_type", "thermal_parameters", "theta_t0", "gamma_t0",
     "q_t0", "t_ref"]
)

_STATE_KEYS = frozenset(f.name for f in dataclasses.fields(CrystalState))


class _ParamsView(MutableMapping):
    """Dict-style access onto a CrystalState plus a derived-value cache.

    The whole codebase (and the JCPDS editor in particular) reads and writes
    ``phase.params['k0']``; this view keeps that surface intact while the
    state lives in the dataclass. Derived keys (a..gamma, v, k0p, alpha_t —
    written by compute_d) and anything unknown go to a side cache that is
    never treated as state.
    """

    def __init__(self, state: CrystalState) -> None:
        self._state = state
        self._derived: dict[str, Any] = {}

    def __getitem__(self, key: str) -> Any:
        if key in _STATE_KEYS:
            return getattr(self._state, key)
        return self._derived[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in _FLAGGING_KEYS:
            self._state.modified = True
        if key in _STATE_KEYS:
            setattr(self._state, key, value)
        else:
            self._derived[key] = value

    def __delitem__(self, key: str) -> None:
        del self._derived[key]

    def __iter__(self):
        yield from _STATE_KEYS
        yield from self._derived

    def __len__(self) -> int:
        return len(_STATE_KEYS) + len(self._derived)

    def __contains__(self, key: object) -> bool:
        return key in _STATE_KEYS or key in self._derived


class jcpds:
    def __init__(self) -> None:
        self._filename: str = ''
        self._name: str = ''
        #: the phase's true state; params is the dict-style view over it
        self.state: CrystalState = CrystalState()
        self.params: _ParamsView = _ParamsView(self.state)
        # derived values, recomputed by compute_d for the current P and T
        for key in ('k0p', 'alpha_t', 'a', 'b', 'c', 'alpha', 'beta',
                    'gamma', 'v'):
            self.params[key] = 0.
        self.reflections: list[jcpds_reflection] = []
        self.state.modified = False

    def load_file(self, filename: str) -> None:
        """
        Reads a JCPDS file into the JCPDS object.

        Procedure::

           This procedure read the JCPDS file.  There are several versions of the
           formats used for JCPDS files.  Versions 1, 2 and 3 used a fixed
           format, where a particular entry had to be in a specific location on
           a specific line.  Versions 2 and 3 were used only by Dan Shim.
           This routine can read these old files, but no new files should be
           created in this format, they should be converted to Version 4.
           Version 4 is a "keyword" driven format.  Each line in the file is of
           the form:
           KEYWORD: value
           The order of the lines is not important, except that the first line of
           the file must be "VERSION: 4".
           The following keywords are currently supported:
               COMMENT:    Any information describing the material, literature
                           references, etc.  There can be multiple comment lines
                           per file.
               K0:         The bulk modulus in GPa.
               K0P:        The change in K0 with pressure, for Birch-Murnaghan
                           equation of state.  Dimensionless.
               DK0DT:      The temperature derivative of K0, GPa/K.
               DK0PDT:     The temperature derivative of K0P, 1/K.
               SYMMETRY:   One of CUBIC, TETRAGONAL, HEXAGONAL, RHOMBOHEDRAL,
                           ORTHORHOMBIC, MONOCLINIC or TRICLINIC
               A:          The unit cell dimension A
               B:          The unit cell dimension B
               C:          The unit cell dimension C
               ALPHA:      The unit cell angle ALPHA
               BETA:       The unit cell angle BETA
               GAMMA:      The unit cell angle GAMMA
               VOLUME:     The unit cell volume
               ALPHAT:     The thermal expansion coefficient, 1/K
               DALPHADT:   The temperature derivative of the thermal expansion
                           coefficient, 1/K^2
               DIHKL:      For each reflection, the D spacing in Angstrom, the
                           relative intensity (0-100), and the H, K, L indices.

           This procedure calculates the D spacing of each relfection, using the
           symmetry and unit cell parameters from the file.  It compares the
           calculated D spacing with the input D spacing for each line.  If they
           disagree by more than 0.1% then a warning message is printed.
           The following is an example JCPDS file in the Version 4 format:
               VERSION:  4
               COMMENT: Alumina (JCPDS 0-173, EOS n/a)
               K0:          194.000
               K0P:           5.000
               SYMMETRY: HEXAGONAL
               A:            4.758
               C:            12.99
               VOLUME:        22.0640
               ALPHAT:    2.000e-6
               DIHKL:        3.4790      75.0   0   1   2
               DIHKL:        2.5520      90.0   1   0   4
               DIHKL:        2.3790      40.0   1   1   0
               DIHKL:        2.0850     100.0   1   1   3
               DIHKL:        1.7400      45.0   0   2   4
               DIHKL:        1.6010      80.0   1   1   6
               DIHKL:        1.4040      30.0   2   1   4
               DIHKL:        1.3740      50.0   3   0   0
               DIHKL:        1.2390      16.0   1   0  10

           Note that B and ALPHA, BETA and GAMMA are not present, since they are
           not needed for a hexagonal material, and will be simple ignored if
           they are present.
        """
        self.__init__()
        # Initialize variables
        self._filename = filename
        # Construct base name = file without path and without extension
        name = os.path.basename(filename)
        pos = name.find('.')
        if (pos >= 0): name = name[0:pos]
        self._name = name
        self.params['comments'] = []
        self.reflections = []

        # Determine what version JCPDS file this is
        # In current files have the first line starts with the string VERSION:
        fp = open(filename, 'r')
        line = fp.readline()
        parts = line.split(maxsplit=1)
        tag = parts[0].upper() if parts else ''
        value = parts[1].strip() if len(parts) > 1 else ''
        if tag == 'VERSION:':
            self.version = value
            # This is the current, keyword based version of JCPDS file
            while (1):
                line = fp.readline()
                if line == '': break
                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    continue
                tag = parts[0].upper()
                value = parts[1].strip()
                if tag == 'COMMENT:':
                    self.params['comments'].append(value)
                elif tag == 'K0:':
                    self.params['k0'] = float(value)
                elif tag == 'K0P:':
                    self.params['k0p0'] = float(value)
                elif tag == 'DK0DT:':
                    self.params['dk0dt'] = float(value)
                elif tag == 'DK0PDT:':
                    self.params['dk0pdt'] = float(value)
                elif tag == 'SYMMETRY:':
                    self.params['symmetry'] = value.upper()
                elif tag == 'A:':
                    self.params['a0'] = float(value)
                elif tag == 'B:':
                    self.params['b0'] = float(value)
                elif tag == 'C:':
                    self.params['c0'] = float(value)
                elif tag == 'ALPHA:':
                    self.params['alpha0'] = float(value)
                elif tag == 'BETA:':
                    self.params['beta0'] = float(value)
                elif tag == 'GAMMA:':
                    self.params['gamma0'] = float(value)
                elif tag == 'VOLUME:':
                    self.params['v0'] = float(value)
                elif tag == 'ALPHAT:':
                    self.params['alpha_t0'] = float(value)
                elif tag == 'DALPHADT:':
                    self.params['d_alpha_dt'] = float(value)
                elif tag == 'DIHKL:':
                    dtemp = value.split()
                    dtemp = list(map(float, dtemp))
                    reflection = jcpds_reflection()
                    reflection.d0 = dtemp[0]
                    reflection.intensity = dtemp[1]
                    reflection.h = int(dtemp[2])
                    reflection.k = int(dtemp[3])
                    reflection.l = int(dtemp[4])
                    self.reflections.append(reflection)
        elif tag in ('2', '3'):
            # Version 2/3 (Dan Shim's format): the bare version number,
            # a title line, a "symmetry_code K0 K0'" line, a lattice-
            # constant line whose length depends on the symmetry, a
            # placeholder line, a column-label line, and the peak table.
            self.version = float(tag)
            self.params['comments'].append(fp.readline().strip())
            temp = fp.readline().replace(',', ' ').split()
            symmetry_code = int(float(temp[0]))
            self.params['symmetry'] = {
                1: 'CUBIC', 2: 'HEXAGONAL', 3: 'TETRAGONAL',
                4: 'ORTHORHOMBIC', 5: 'MONOCLINIC', 6: 'TRICLINIC',
            }.get(symmetry_code, 'CUBIC')
            self.params['k0'] = float(temp[1])
            self.params['k0p0'] = float(temp[2])

            lat = [float(v) for v in fp.readline().replace(',', ' ').split()]
            self.params['a0'] = lat[0]
            if len(lat) >= 6:
                # full set incl. angles (whatever the symmetry code says)
                self.params['b0'], self.params['c0'] = lat[1], lat[2]
                (self.params['alpha0'], self.params['beta0'],
                 self.params['gamma0']) = lat[3], lat[4], lat[5]
            elif len(lat) == 4:      # monoclinic: a b c beta
                self.params['b0'], self.params['c0'] = lat[1], lat[2]
                self.params['beta0'] = lat[3]
            elif len(lat) == 3:      # orthorhombic: a b c
                self.params['b0'], self.params['c0'] = lat[1], lat[2]
            elif len(lat) == 2:      # hexagonal/tetragonal: a c
                self.params['c0'] = lat[1]
            # remaining constants and angles follow from the symmetry
            # (compute_v0 normalizes them)

            fp.readline()   # "(blank for future use)"
            fp.readline()   # column labels
            while 1:
                line = fp.readline()
                if line == '': break
                dtemp = list(map(float, line.replace(',', ' ').split()[0:5]))
                if len(dtemp) < 5:
                    continue
                self.reflections.append(jcpds_reflection(
                    h=int(dtemp[2]), k=int(dtemp[3]), l=int(dtemp[4]),
                    intensity=dtemp[1], d=dtemp[0]))

        else:
            # This is an old format JCPDS file
            self.version = 1.
            header = ''
            self.params['comments'].append(line)  # Read above
            line = fp.readline()
            # Replace any commas with blanks, split at blanks
            temp = line.replace(',', ' ').split()
            temp = list(map(float, temp[0:5]))
            # The symmetry codes are as follows:
            #   1 -- cubic
            #   2 -- hexagonal
            if temp[0] == 1:
                self.params['symmetry'] = 'CUBIC'
            elif temp[0] == 2:
                self.params['symmetry'] = 'HEXAGONAL'
            self.params['a0'] = temp[1]
            self.params['k0'] = temp[2]
            self.params['k0p0'] = temp[3]
            c0a0 = temp[4]
            self.params['c0'] = self.params['a0'] * c0a0
            line = fp.readline()  # Ignore, just column labels

            while 1:
                line = fp.readline()
                if line == '': break
                dtemp = line.split()
                dtemp = list(map(float, dtemp))
                reflection = jcpds_reflection()
                reflection.d0 = dtemp[0]
                reflection.intensity = dtemp[1]
                reflection.h = int(dtemp[2])
                reflection.k = int(dtemp[3])
                reflection.l = int(dtemp[4])
                self.reflections.append(reflection)

        fp.close()
        self.compute_v0()
        self.params['a'] = self.params['a0']
        self.params['b'] = self.params['b0']
        self.params['c'] = self.params['c0']
        self.params['alpha'] = self.params['alpha0']
        self.params['beta'] = self.params['beta0']
        self.params['gamma'] = self.params['gamma0']
        self.params['v'] = self.params['v0']
        # Compute D spacings, make sure they are consistent with the input values

        self.compute_d()
        for reflection in self.reflections:
            reflection.d0 = reflection.d

        self.params['modified'] = False

        ## we just removed this check because it should be better to care more about the actual a,b,c values than
        # individual d spacings
        # reflections = self.get_reflections()
        # for r in reflections:
        #     diff = abs(r.d0 - r.d) / r.d0
        #     if (diff > .001):
        #         logger.info(('Reflection ', r.h, r.k, r.l, \
        #             ': calculated D ', r.d, \
        #             ') differs by more than 0.1% from input D (', r.d0, ')'))

    def save_file(self, filename: str) -> None:
        """
        Writes a JCPDS object to a file.

        Procedure::

           This procedure writes a JCPDS file.  It always writes files in the
           current, keyword-driven format (Version 4).  See the documentation for
           read_file() for information on the file format.

        Example:
           This reads an old format file, writes a new format file.
           j = jcpds.jcpds()
           j.read_file('alumina_old.jcpds')
           j.write_file('alumina_new.jcpds')
        """
        fp = open(filename, 'w')
        fp.write('VERSION:   4\n')
        for comment in self.params['comments']:
            fp.write('COMMENT: ' + comment + '\n')
        fp.write('K0:       ' + str(self.params['k0']) + '\n')
        fp.write('K0P:      ' + str(self.params['k0p0']) + '\n')
        fp.write('DK0DT:    ' + str(self.params['dk0dt']) + '\n')
        fp.write('DK0PDT:   ' + str(self.params['dk0pdt']) + '\n')
        fp.write('SYMMETRY: ' + self.params['symmetry'] + '\n')
        fp.write('A:        ' + str(self.params['a0']) + '\n')
        fp.write('B:        ' + str(self.params['b0']) + '\n')
        fp.write('C:        ' + str(self.params['c0']) + '\n')
        fp.write('ALPHA:    ' + str(self.params['alpha0']) + '\n')
        fp.write('BETA:     ' + str(self.params['beta0']) + '\n')
        fp.write('GAMMA:    ' + str(self.params['gamma0']) + '\n')
        fp.write('VOLUME:   ' + str(self.params['v0']) + '\n')
        fp.write('ALPHAT:   ' + str(self.params['alpha_t0']) + '\n')
        fp.write('DALPHADT: ' + str(self.params['d_alpha_dt']) + '\n')
        reflections = self.get_reflections()
        for r in reflections:
            fp.write('DIHKL:    {0:g}\t{1:g}\t{2:g}\t{3:g}\t{4:g}\n'.format(r.d0, r.intensity, r.h, r.k, r.l))
        fp.close()

        self._filename = filename
        name = os.path.basename(filename)
        pos = name.find('.')
        if pos >= 0: name = name[0:pos]
        self._name = name

        self.params['modified'] = False

    def reload_file(self) -> None:
        pressure = self.params['pressure']
        temperature = self.params['temperature']
        self.load_file(self._filename)
        self.params['pressure'] = pressure
        self.params['temperature'] = temperature
        self.compute_d()

    # def __setattr__(self, key, value):
    #     if key in ['comments', 'a0', 'b0', 'c0', 'alpha0', 'beta0', 'gamma0',
    #                'symmetry', 'k0', 'k0p0', 'dk0dt', 'dk0pdt',
    #                'alpha_t0', 'd_alpha_dt', 'reflections']:
    #         self.modified = True
    #     super(jcpds, self).__setattr__(key, value)

    @property
    def filename(self) -> str:
        if self.params['modified']:
            return self._filename + '*'
        else:
            return self._filename

    @filename.setter
    def filename(self, value: str) -> None:
        self._filename = value

    @property
    def name(self) -> str:
        if self.params['modified']:
            return self._name + '*'
        else:
            return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def compute_v0(self) -> None:
        """
        Computes the unit cell volume of the material at zero pressure and
        temperature from the unit cell parameters.
        """
        if self.params['symmetry'] == 'CUBIC':
            self.params['b0'] = self.params['a0']
            self.params['c0'] = self.params['a0']
            self.params['alpha0'] = 90.
            self.params['beta0'] = 90.
            self.params['gamma0'] = 90.

        elif self.params['symmetry'] == 'TETRAGONAL':
            self.params['b0'] = self.params['a0']
            self.params['alpha0'] = 90.
            self.params['beta0'] = 90.
            self.params['gamma0'] = 90.

        elif self.params['symmetry'] == 'ORTHORHOMBIC':
            self.params['alpha0'] = 90.
            self.params['beta0'] = 90.
            self.params['gamma0'] = 90.

        elif self.params['symmetry'] == 'HEXAGONAL' or self.params['symmetry'] == "TRIGONAL":
            self.params['b0'] = self.params['a0']
            self.params['alpha0'] = 90.
            self.params['beta0'] = 90.
            self.params['gamma0'] = 120.

        elif self.params['symmetry'] == 'RHOMBOHEDRAL':
            self.params['b0'] = self.params['a0']
            self.params['c0'] = self.params['a0']
            self.params['beta0'] = self.params['alpha0']
            self.params['gamma0'] = self.params['alpha0']

        elif self.params['symmetry'] == 'MONOCLINIC':
            self.params['alpha0'] = 90.
            self.params['gamma0'] = 90.

        elif self.params['symmetry'] == 'TRICLINIC':
            pass

        dtor = np.pi / 180.
        self.params['v0'] = (self.params['a0'] * self.params['b0'] * self.params['c0'] *
                             np.sqrt(1. -
                                     np.cos(self.params['alpha0'] * dtor) ** 2 -
                                     np.cos(self.params['beta0'] * dtor) ** 2 -
                                     np.cos(self.params['gamma0'] * dtor) ** 2 +
                                     2. * (np.cos(self.params['alpha0'] * dtor) *
                                           np.cos(self.params['beta0'] * dtor) *
                                           np.cos(self.params['gamma0'] * dtor))))

    def compute_volume(self, pressure: float | None = None, temperature: float | None = None) -> None:
        """Compute the unit-cell volume at a pressure and temperature.

        The calculation starts from the zero-pressure, room-temperature
        lattice volume. It applies the selected thermal correction and then
        the active equation of state. If no explicit values are supplied, the
        phase's current pressure and temperature are used.
        """
        if pressure is None:
            pressure = self.params['pressure']
        else:
            self.params['pressure'] = pressure

        if temperature is None:
            temperature = self.params['temperature']
        else:
            self.params['temperature'] = temperature

        if not np.isfinite(pressure):
            raise EosCalculationError("Pressure must be finite")
        if not np.isfinite(temperature) or temperature < 0:
            raise EosCalculationError(
                "Temperature must be finite and non-negative")

        # Assume 0 K really means room T
        if temperature == 0: temperature = 298.

        # A peritheos thermal model (Mie-Grüneisen-Debye, ...) handles
        # the temperature inside the engine — no coefficient corrections
        # or effective-pressure shift. Failures (Peritheos missing, or
        # parameters incomplete — the UI asks for them) fall through to
        # the legacy path below, which then behaves like a phase without
        # thermal expansion.
        if self.params.get('thermal_type') and pressure >= 0:
            if self._thermal_engine_volume(pressure, temperature):
                return

        # Compute values of K0, K0P and alphat at this temperature
        self.params['alpha_t'] = self.params['alpha_t0'] + self.params['d_alpha_dt'] * (temperature - 298.)
        self.params['k0p'] = self.params['k0p0'] + self.params['dk0pdt'] * (temperature - 298.)

        k0 = self.params['k0'] + self.params['dk0dt'] * (temperature - 298.)
        k0p = self.params['k0p']

        if pressure == 0.:
            self.params['v'] = self.params['v0'] * (1 + self.params['alpha_t'] * (temperature - 298.))
        elif pressure < 0:
            if self.params['k0'] <= 0.:
                logger.info('K0 is zero, computing zero pressure volume')
                self.params['v'] = self.params['v0']
            else:
                self.params['v'] = self.params['v0'] * (1 - pressure / self.params['k0'])
        else:
            if self.params['k0'] <= 0.:
                logger.info('K0 is zero, computing zero pressure volume')
                self.params['v'] = self.params['v0']
            else:
                self.mod_pressure = pressure - \
                                    self.params['alpha_t'] * k0 * (temperature - 298.)
                self.params['v'] = self._solve_volume_at_pressure(
                    k0, k0p, self.mod_pressure)

        self._require_physical_volume(self.params['v'])

    @staticmethod
    def _require_physical_volume(volume: float) -> None:
        if not np.isfinite(volume) or volume <= 0:
            raise EosCalculationError(
                f"Equation of state returned a non-physical volume: {volume}")

    def _thermal_engine_volume(self, pressure: float, temperature: float) -> bool:
        """
        Compute the volume through the phase's peritheos thermal model
        (params['thermal_type'], e.g. Mie-Grüneisen-Debye over the
        configured rt equation). Returns True when the volume was set;
        False when the engine is unavailable or not constructible, so
        compute_volume falls back to the legacy path.
        """
        thermal_type = str(self.params.get('thermal_type') or '')
        try:
            from .eos_phase import EosPhase
        except ImportError as e:
            logger.warning(
                "Peritheos is not available (%s); ignoring thermal model "
                "'%s'.", e, thermal_type)
            return False
        try:
            eos = EosPhase.from_jcpds(self, with_thermal=True)
        except ValueError as e:
            logger.warning(
                "Thermal model '%s' cannot be constructed for phase '%s' "
                "(%s); computing without it.",
                thermal_type, self.name, e)
            return False
        # the temperature dependence lives in the engine now — keep the
        # derived coefficient values meaningful for displays
        self.params['alpha_t'] = self.params['alpha_t0']
        self.params['k0p'] = self.params['k0p0']
        try:
            volume = eos.volume(pressure, temperature)
        except (ArithmeticError, RuntimeError, ValueError) as error:
            raise EosCalculationError(str(error)) from error
        self._require_physical_volume(volume)
        self.params['v'] = volume
        return True

    def _solve_volume_at_pressure(self, k0: float, k0p: float, pressure: float) -> float:
        """
        Solve for the unit-cell volume at the given (thermal-corrected)
        pressure using the configured equation of state.

        The Peritheos library is used as the live calculation engine,
        dispatching on ``params['eos_type']`` (a peritheos.eos.rt class
        name). Only two failures fall back to the legacy 3rd-order
        Birch-Murnaghan solver — Peritheos not importable, or the EoS not
        constructible from the phase's parameters (the UI disables such
        choices up front) — anything else propagates. The test suite
        cross-validates the legacy solver against Peritheos' BM3.
        """
        eos_type = str(self.params.get('eos_type') or 'BM3')
        try:
            from .eos_phase import EosPhase
        except ImportError as e:
            logger.warning(
                "Peritheos is not available (%s); computing '%s' with the "
                "legacy BM3 solver instead.", e, eos_type)
            return self._legacy_bm3_volume(k0, k0p, pressure)
        try:
            eos = EosPhase.from_jcpds(self, eos_type=eos_type,
                                      k0=k0, k0p=k0p)
        except ValueError as e:
            logger.warning(
                "EoS '%s' cannot be constructed for phase '%s' (%s); "
                "computing with the legacy BM3 solver instead.",
                eos_type, self.name, e)
            return self._legacy_bm3_volume(k0, k0p, pressure)
        try:
            volume = eos.volume(pressure)
        except (ArithmeticError, RuntimeError, ValueError) as error:
            raise EosCalculationError(str(error)) from error
        self._require_physical_volume(volume)
        return volume

    def _legacy_bm3_volume(self, k0: float, k0p: float, pressure: float) -> float:
        """
        Original Dioptas 3rd-order Birch-Murnaghan solve (scipy minimize on
        the squared pressure residual). Retained as a Peritheos-free
        fallback and as the independent reference in the cross-validation
        tests.
        """
        res = minimize(self.bm3_inverse, 1.,
                       args=(k0, k0p, pressure),
                       method='Nelder-Mead')
        if not res.success:
            raise EosCalculationError(
                "Legacy BM3 volume inversion did not converge")
        return self.params['v0'] / float(res.x[0])

    def bm3_inverse(self, v0_v: float, k0: float, k0p: float, pressure: float) -> float:
        """
        Returns the value of the third order Birch-Murnaghan equation minus
        pressure.  It is used to solve for V0/V for a given P, K0 and K0'.

        Procedure:
           This procedure simply computes the pressure using V0/V, K0 and K0',
           and then subtracts the input pressure.
        """

        return (1.5 * k0 * (v0_v ** (7. / 3.) - v0_v ** (5. / 3.)) *
                (1 + 0.75 * (k0p - 4.) * (v0_v ** (2. / 3.) - 1.0)) -
                pressure) ** 2

    def compute_d0(self) -> None:
        """
        Computes d0 values based on the current lattice parameters.
        """
        a = self.params['a0']
        b = self.params['b0']
        c = self.params['c0']
        degree_to_radians = np.pi / 180.
        alpha = self.params['alpha0'] * degree_to_radians
        beta = self.params['beta0'] * degree_to_radians
        gamma = self.params['gamma0'] * degree_to_radians

        h = np.zeros(len(self.reflections))
        k = np.zeros(len(self.reflections))
        l = np.zeros(len(self.reflections))

        for ind, reflection in enumerate(self.reflections):
            h[ind] = reflection.h
            k[ind] = reflection.k
            l[ind] = reflection.l

        if self.params['symmetry'] == 'CUBIC':
            d2inv = (h ** 2 + k ** 2 + l ** 2) / a ** 2
        elif self.params['symmetry'] == 'TETRAGONAL':
            d2inv = (h ** 2 + k ** 2) / a ** 2 + l ** 2 / c ** 2
        elif self.params['symmetry'] == 'ORTHORHOMBIC':
            d2inv = h ** 2 / a ** 2 + k ** 2 / b ** 2 + l ** 2 / c ** 2
        elif self.params['symmetry'] == 'HEXAGONAL' or self.params['symmetry'] == 'TRIGONAL':
            d2inv = (h ** 2 + h * k + k ** 2) * 4. / 3. / a ** 2 + l ** 2 / c ** 2
        elif self.params['symmetry'] == 'RHOMBOHEDRAL':
            d2inv = (((1. + np.cos(alpha)) * ((h ** 2 + k ** 2 + l ** 2) -
                                              (1 - np.tan(0.5 * alpha) ** 2) * (h * k + k * l + l * h))) /
                     (a ** 2 * (1 + np.cos(alpha) - 2 * np.cos(alpha) ** 2)))
        elif self.params['symmetry'] == 'MONOCLINIC':
            d2inv = (h ** 2 / np.sin(beta) ** 2 / a ** 2 +
                     k ** 2 / b ** 2 +
                     l ** 2 / np.sin(beta) ** 2 / c ** 2 +
                     2 * h * l * np.cos(beta) / (a * c * np.sin(beta) ** 2))
        elif self.params['symmetry'] == 'TRICLINIC':
            V = (a * b * c *
                 np.sqrt(1. - np.cos(alpha) ** 2 - np.cos(beta) ** 2 -
                         np.cos(gamma) ** 2 +
                         2 * np.cos(alpha) * np.cos(beta) * np.cos(gamma)))
            s11 = b ** 2 * c ** 2 * np.sin(alpha) ** 2
            s22 = a ** 2 * c ** 2 * np.sin(beta) ** 2
            s33 = a ** 2 * b ** 2 * np.sin(gamma) ** 2
            s12 = a * b * c ** 2 * (np.cos(alpha) * np.cos(beta) -
                                    np.cos(gamma))
            s23 = a ** 2 * b * c * (np.cos(beta) * np.cos(gamma) -
                                    np.cos(alpha))
            s31 = a * b ** 2 * c * (np.cos(gamma) * np.cos(alpha) -
                                    np.cos(beta))
            d2inv = (s11 * h ** 2 + s22 * k ** 2 + s33 * l ** 2 +
                     2. * s12 * h * k + 2. * s23 * k * l + 2. * s31 * l * h) / V ** 2
        else:
            logger.error(('Unknown crystal symmetry = ' + self.params['symmetry']))
            d2inv = 1
        d_spacings = np.sqrt(1. / d2inv)

        for ind in range(len(self.reflections)):
            self.reflections[ind].d0 = d_spacings[ind]

    def compute_d(self, pressure: float | None = None, temperature: float | None = None) -> None:
        """
        Computes the D spacings of the material.
        It can compute D spacings at different pressures and temperatures.

        Procedure:
            This procedure first calls jcpds.compute_volume().
            It then assumes that each lattice dimension fractionally changes by
            the cube root of the fractional change in the volume.
            Using the equations for the each symmetry class it then computes the
            change in D spacing of each reflection.
        """
        self.compute_volume(pressure, temperature)

        # Assume each cell dimension changes by the same fractional amount = cube
        # root of volume change ratio
        ratio = float((self.params['v'] / self.params['v0']) ** (1.0 / 3.0))
        self.params['a'] = self.params['a0'] * ratio
        self.params['b'] = self.params['b0'] * ratio
        self.params['c'] = self.params['c0'] * ratio

        a = self.params['a']
        b = self.params['b']
        c = self.params['c']
        dtor = np.pi / 180.
        alpha = self.params['alpha0'] * dtor
        beta = self.params['beta0'] * dtor
        gamma = self.params['gamma0'] * dtor

        h = np.zeros(len(self.reflections))
        k = np.zeros(len(self.reflections))
        l = np.zeros(len(self.reflections))

        for ind, reflection in enumerate(self.reflections):
            h[ind] = reflection.h
            k[ind] = reflection.k
            l[ind] = reflection.l

        if self.params['symmetry'] == 'CUBIC':
            d2inv = (h ** 2 + k ** 2 + l ** 2) / a ** 2
        elif self.params['symmetry'] == 'TETRAGONAL':
            d2inv = (h ** 2 + k ** 2) / a ** 2 + l ** 2 / c ** 2
        elif self.params['symmetry'] == 'ORTHORHOMBIC':
            d2inv = h ** 2 / a ** 2 + k ** 2 / b ** 2 + l ** 2 / c ** 2
        elif self.params['symmetry'] == 'HEXAGONAL' or self.params['symmetry'] == 'TRIGONAL':
            d2inv = (h ** 2 + h * k + k ** 2) * 4. / 3. / a ** 2 + l ** 2 / c ** 2
        elif self.params['symmetry'] == 'RHOMBOHEDRAL':
            d2inv = (((1. + np.cos(alpha)) * ((h ** 2 + k ** 2 + l ** 2) -
                                              (1 - np.tan(0.5 * alpha) ** 2) * (h * k + k * l + l * h))) /
                     (a ** 2 * (1 + np.cos(alpha) - 2 * np.cos(alpha) ** 2)))
        elif self.params['symmetry'] == 'MONOCLINIC':
            d2inv = (h ** 2 / (np.sin(beta) ** 2 * a ** 2) +
                     k ** 2 / b ** 2 +
                     l ** 2 / (np.sin(beta) ** 2 * c ** 2) -
                     2 * h * l * np.cos(beta) / (a * c * np.sin(beta) ** 2))
        elif self.params['symmetry'] == 'TRICLINIC':
            V = (a * b * c *
                 np.sqrt(1. - np.cos(alpha) ** 2 - np.cos(beta) ** 2 -
                         np.cos(gamma) ** 2 +
                         2 * np.cos(alpha) * np.cos(beta) * np.cos(gamma)))
            s11 = b ** 2 * c ** 2 * np.sin(alpha) ** 2
            s22 = a ** 2 * c ** 2 * np.sin(beta) ** 2
            s33 = a ** 2 * b ** 2 * np.sin(gamma) ** 2
            s12 = a * b * c ** 2 * (np.cos(alpha) * np.cos(beta) -
                                    np.cos(gamma))
            s23 = a ** 2 * b * c * (np.cos(beta) * np.cos(gamma) -
                                    np.cos(alpha))
            s31 = a * b ** 2 * c * (np.cos(gamma) * np.cos(alpha) -
                                    np.cos(beta))
            d2inv = (s11 * h ** 2 + s22 * k ** 2 + s33 * l ** 2 +
                     2. * s12 * h * k + 2. * s23 * k * l + 2. * s31 * l * h) / V ** 2
        else:
            logger.error(('Unknown crystal symmetry = ' + self.params['symmetry']))
            d2inv = 1
        d_spacings = np.sqrt(1. / d2inv)
        for ind in range(len(self.reflections)):
            self.reflections[ind].d = d_spacings[ind]

    def add_reflection(self, h: float = 0., k: float = 0., l: float = 0., intensity: float = 0., d: float = 0.) -> None:
        new_reflection = jcpds_reflection(h, k, l, intensity, d)
        self.reflections.append(new_reflection)
        self.params['modified'] = True

    def delete_reflection(self, ind: int) -> None:
        del self.reflections[ind]
        self.params['modified'] = True

    def get_reflections(self) -> list[jcpds_reflection]:
        """
        Returns the information for each reflection for the material.
        This information is an array of elements of class jcpds_reflection.
        """
        return self.reflections

    def reorder_reflections_by_index(self, ind_list: NDArray[np.intp] | list[int], reversed_toggle: bool = False) -> None:
        if reversed_toggle:
            ind_list = ind_list[::-1]
        new_reflections = []
        for ind in ind_list:
            new_reflections.append(self.reflections[ind])

        modified_flag = self.params['modified']
        self.reflections = new_reflections
        self.params['modified'] = modified_flag

    def sort_reflections_by_h(self, reversed_toggle: bool = False) -> None:
        h_list = []
        for reflection in self.reflections:
            h_list.append(reflection.h)
        sorted_ind = np.argsort(h_list)
        self.reorder_reflections_by_index(sorted_ind, reversed_toggle)

    def sort_reflections_by_k(self, reversed_toggle: bool = False) -> None:
        k_list = []
        for reflection in self.reflections:
            k_list.append(reflection.k)
        sorted_ind = np.argsort(k_list)
        self.reorder_reflections_by_index(sorted_ind, reversed_toggle)

    def sort_reflections_by_l(self, reversed_toggle: bool = False) -> None:
        l_list = []
        for reflection in self.reflections:
            l_list.append(reflection.l)
        sorted_ind = np.argsort(l_list)
        self.reorder_reflections_by_index(sorted_ind, reversed_toggle)

    def sort_reflections_by_intensity(self, reversed_toggle: bool = False) -> None:
        intensity_list = []
        for reflection in self.reflections:
            intensity_list.append(reflection.intensity)
        sorted_ind = np.argsort(intensity_list)
        self.reorder_reflections_by_index(sorted_ind, reversed_toggle)

    def sort_reflections_by_d(self, reversed_toggle: bool = False) -> None:
        d_list = []
        for reflection in self.reflections:
            d_list.append(reflection.d0)
        sorted_ind = np.argsort(d_list)
        self.reorder_reflections_by_index(sorted_ind, reversed_toggle)

    def has_thermal_expansion(self) -> bool:
        return (self.params['alpha_t0'] != 0) or (self.params['d_alpha_dt'] != 0) \
            or bool(self.params['thermal_type'])


def lookup_jcpds_line(in_string: str,
                      pressure: float = 0.,
                      temperature: float = 0.,
                      path: str | None = os.getenv('JCPDS_PATH')) -> float | None:
    """
    Returns the d-spacing in Angstroms for a particular lattice plane.

    Inputs:
       Diffaction_plane: A string of the form 'Compound HKL', where Compound
       is the name of a material (e.g. 'gold', and HKL is the diffraction
       plane (e.g. 220).
       There must be a space between Compound and HKL.
         Examples of Diffraction_plane:
             'gold 111' - Gold 111 plane
             'si 220'   - Silicon 220 plane

    Keywords:
       path:
          The path in which to look for the file 'Compound.jcpds'.  The
          default is to search in the directory pointed to by the
          environment variable JCPDS_PATH.

       pressure:
          The pressure at which to compute the d-spacing.  Not yet
          implemented, zero pressure d-spacing is always returned.

       temperature:
           The temperature at which to compute the d-spacing.  Not yet
           implemented.  Room-temperature d-spacing is always returned.

    Restrictions:
       This function attempts to locate the file 'Compound.jcpds', where
       'Compound' is the name of the material specified in the input parameter
       'Diffraction_plane'.  For example:
           d = lookup_jcpds_line('gold 220')
       will look for the file gold.jcpds.  It will either look in the file
       specified in the PATH keyword parameter to this function, or in the
       the directory pointed to by the environtment variable JCPDS_PATH
       if the PATH keyword is not specified.  Note that the filename will be
       case sensitive on Unix systems, but not on Windows.

       This function is currently only able to handle HKL values from 0-9.
       The parser will need to be improved to handle 2-digit values of H,
       K or L.

    Procedure:
       This function calls jcpds.read_file() and searches for the specified HKL plane
       and returns its d-spacing;

    Example:
       d = lookup_jcpds_line('gold 111')   # Look up gold 111 line
       d = lookup_jcpds_line('quartz 220') # Look up the quartz 220 line
    """

    temp = in_string.split()
    if len(temp) < 2:
        return None
    file = temp[0]
    nums = temp[1].split()
    n = len(nums)
    if n == 1:
        if len(nums[0]) == 3:
            try:
                hkl = (int(nums[0][0]), int(nums[0][1]), int(nums[0][2]))
            except (ValueError, IndexError):
                return None
        else:
            return None
    elif n == 3:
        hkl = list(map(int, nums))
    else:
        return None

    full_file = path + file + '.jcpds'
    try:
        j = jcpds()
        j.load_file(full_file)
        refl = j.get_reflections()
        for r in refl:
            if r.h == hkl[0] and r.k == hkl[1] and r.l == hkl[2]:
                return r.d0
        return None
    except Exception:
        return None

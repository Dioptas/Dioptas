# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division, unicode_literals

import os
import itertools
from math import degrees

from cif_new import CifPhase
from CifFile import ReadCif
from jcpds import jcpds

import numpy as np
import json

with open(os.path.join(os.path.dirname(__file__),
                       "data/atomic_scattering_params.json")) as f:
    ATOMIC_SCATTERING_PARAMS = json.load(f)

with open(os.path.join(os.path.dirname(__file__),
                       "data/periodic_table.json")) as f:
    PERIODIC_TABLE = json.load(f)


class CifConverter(object):
    # Tolerance in which to treat two peaks as having the same two theta.
    TWO_THETA_TOL = 1e-5

    def __init__(self, wavelength, min_d_spacing=0.5, min_intensity=0.5):
        """
        Calculates the x-ray diffraction intensities for a specific cif phase.
        :param wavelength: Wavelength for the two theta calculation
        :param min_d_spacing: all calculated reflections will have a d-spacing above this value
        :param min_intensity: all calculated reflections will have an intensity greater than this value
        :return:
        """
        self.wavelength = wavelength
        self.min_d_spacing = min_d_spacing
        self.min_intensity = min_intensity

    def convert_cif_to_jcpds(self, filename):
        """
        Reads a cif file and returns a jcpds with correct reflection and intensities
        :param filename:  cif filename
        :return: converted jcpds object
        :rtype: jcpds
        """
        cif_file = ReadCif(filename)
        cif_phase = CifPhase(cif_file[cif_file.keys()[0]])
        jcpds_phase = self.convert_cif_phase_to_jcpds(cif_phase)
        jcpds_phase.filename = filename
        jcpds_phase.name = os.path.splitext(os.path.basename(filename))[0]
        jcpds_phase.modified = False

        return jcpds_phase

    def convert_cif_phase_to_jcpds(self, cif_phase):
        """
        Converts a CifPhase into a jcpds object by calculating the intensities and multiplicities for all reflections
        :param cif_phase: input CifPhase
        :type cif_phase: CifPhase
        :return: converted jcpds object
        :rtype: jcpds
        """
        reflections = self._calculate_hkl_within_sphere_and_min_d_spacing(cif_phase)
        xrd_reflections = self._calculate_reflection_intensities(cif_phase, reflections)
        jcpds_phase = self._create_jcpds_from_cif_parameters(cif_phase)

        for reflection in xrd_reflections:
            jcpds_phase.add_reflection(reflection.h,
                                       reflection.k,
                                       reflection.l,
                                       reflection.intensity,
                                       reflection.d_spacing)
        return jcpds_phase

    def _create_jcpds_from_cif_parameters(self, cif_phase):
        """
        Creates a jcpds object from a cif_phase using cell parameters, symmetries, and file information. Does not
        calculate intensities for any reflection e.g. the jcpds will have 0 reflections
        :param cif_phase:
        :type cif_phase: CifPhase
        :return:
        """
        jcpds_phase = jcpds()

        jcpds_phase.a0 = cif_phase.a
        jcpds_phase.b0 = cif_phase.b
        jcpds_phase.c0 = cif_phase.c
        jcpds_phase.alpha0 = cif_phase.alpha
        jcpds_phase.beta0 = cif_phase.beta
        jcpds_phase.gamma0 = cif_phase.gamma
        jcpds_phase.v0 = cif_phase.volume
        jcpds_phase.symmetry = cif_phase.symmetry
        jcpds_phase.comments = cif_phase.comments

        return jcpds_phase

    def _calculate_hkl_within_sphere_and_min_d_spacing(self, cif_phase):
        """
        Generates a list of hkl reflections which can satisfy the diffraction condition using the given wavelength and
        also the minimum d spacing
        :return: list of reflections
        :rtype: list[Reflection]
        """
        max_h = np.floor(2 * cif_phase.a / self.wavelength)
        max_k = np.floor(2 * cif_phase.b / self.wavelength)
        max_l = np.floor(2 * cif_phase.c / self.wavelength)

        h = reversed(np.arange(-max_h + 1, max_h, 1))
        k = reversed(np.arange(-max_k + 1, max_k, 1))
        l = reversed(np.arange(-max_l + 1, max_l, 1))
        s = [h, k, l]

        reciprocal_hkl = np.array(list(itertools.product(*s)))
        h = reciprocal_hkl[:, 0]
        k = reciprocal_hkl[:, 1]
        l = reciprocal_hkl[:, 2]

        d_hkl = compute_d_hkl(h, k, l, cif_phase)
        good_indices = np.argwhere(d_hkl > self.min_d_spacing)

        reflections = []
        for i in good_indices:
            reflections.append(Reflection(int(h[i][0]), int(k[i][0]), int(l[i][0]), d_hkl[i][0]))

        return reflections

    def _calculate_reflection_intensities(self, cif_phase, base_reflections):
        """
        :param cif_phase:
        :param base_reflections:
        :return:
        """
        # provide atom parameters as lists
        atom_numbers = []
        form_coefficients = []
        fractional_coordinates = []
        occupations = []
        for atom in cif_phase.atoms:
            atom_numbers.append(PERIODIC_TABLE[atom[0]]['Atomic no'])
            try:
                c = ATOMIC_SCATTERING_PARAMS[atom[0]]
            except KeyError:
                raise ValueError("Unable to calculate XRD pattern as "
                                 "there is no scattering coefficients for"
                                 " %s." % atom[0])
            form_coefficients.append(c)
            fractional_coordinates.append(atom[1:])
            occupations.append(1)

        atom_numbers = np.array(atom_numbers)
        form_coefficients = np.array(form_coefficients)
        fractional_coordinates = np.array(fractional_coordinates)
        occupations = np.array(occupations)

        two_thetas = []
        peaks = {}

        for reflection in base_reflections:
            d_hkl = reflection.d_spacing
            g_hkl = 1. / d_hkl
            if g_hkl != 0:
                hkl = np.array([reflection.h, reflection.k, reflection.l])

                s = g_hkl * 0.5
                s2 = s ** 2

                theta = np.arcsin(self.wavelength * g_hkl * 0.5)
                two_theta = degrees(2 * theta)

                g_dot_r = np.dot(fractional_coordinates, np.transpose([hkl])).T[0]

                fs = atom_numbers - 41.78214 * s2 * np.sum(
                    form_coefficients[:, :, 0] * np.exp(-form_coefficients[:, :, 1] * s2), axis=1)
                f_hkl = np.sum(fs * occupations * np.exp(2j * np.pi * g_dot_r))
                i_hkl = (f_hkl * f_hkl.conjugate()).real

                ind = np.where(np.abs(np.subtract(two_thetas, two_theta)) < CifConverter.TWO_THETA_TOL)

                lorentz_factor = (1 + np.cos(2 * theta) ** 2) / (np.sin(theta) ** 2 * np.cos(theta))

                if len(ind[0]) > 0:
                    peaks[two_thetas[ind[0]]][0] += i_hkl * lorentz_factor
                    peaks[two_thetas[ind[0]]][1].append(tuple(hkl))
                else:
                    peaks[two_theta] = [i_hkl * lorentz_factor, [tuple(hkl)], d_hkl]
                    two_thetas.append(two_theta)

        max_intensity = max([v[0] for v in peaks.values()])
        calculated_reflections = []
        for k in sorted(peaks.keys()):
            v = peaks[k]
            scaled_intensity = v[0] / max_intensity * 100
            fam = get_unique_families(v[1])
            if scaled_intensity > self.min_intensity:
                calculated_reflections.append(
                    Reflection(
                        *fam.keys()[0],
                        d_spacing=v[2],
                        intensity=scaled_intensity,
                        multiplicity=fam[fam.keys()[0]]
                    )
                )

        return calculated_reflections


class Reflection():
    def __init__(self, h, k, l, d_spacing, intensity=None, multiplicity=1):
        self.h = h
        self.k = k
        self.l = l
        self.multiplicity = multiplicity
        self.d_spacing = d_spacing
        self.intensity = intensity

    def __repr__(self):
        return "({},{},{}) x {} {:.5f} - {}".format(self.h, self.k, self.l, self.multiplicity,
                                                    self.d_spacing, self.intensity)


def compute_d_hkl(h, k, l, cif_phase):
    a = cif_phase.a
    b = cif_phase.b
    c = cif_phase.c
    alpha = cif_phase.alpha
    beta = cif_phase.beta
    gamma = cif_phase.gamma

    symmetry = cif_phase.symmetry

    if (symmetry == 'CUBIC'):
        d2inv = (h ** 2 + k ** 2 + l ** 2) / a ** 2
    elif (symmetry == 'TETRAGONAL'):
        d2inv = (h ** 2 + k ** 2) / a ** 2 + l ** 2 / c ** 2
    elif (symmetry == 'ORTHORHOMBIC'):
        d2inv = h ** 2 / a ** 2 + k ** 2 / b ** 2 + l ** 2 / c ** 2
    elif (symmetry == 'HEXAGONAL'):
        d2inv = (h ** 2 + h * k + k ** 2) * 4. / 3. / a ** 2 + l ** 2 / c ** 2
    elif (symmetry == 'RHOMBOHEDRAL'):
        d2inv = (((1. + np.cos(alpha)) * ((h ** 2 + k ** 2 + l ** 2) -
                                          (1 - np.tan(0.5 * alpha) ** 2) * (h * k + k * l + l * h))) /
                 (a ** 2 * (1 + np.cos(alpha) - 2 * np.cos(alpha) ** 2)))
    elif (symmetry == 'MONOCLINIC'):
        d2inv = (h ** 2 / np.sin(beta) ** 2 / a ** 2 +
                 k ** 2 / b ** 2 +
                 l ** 2 / np.sin(beta) ** 2 / c ** 2 +
                 2 * h * l * np.cos(beta) / (a * c * np.sin(beta) ** 2))
    elif (symmetry == 'TRICLINIC'):
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
    d_spacings = np.sqrt(1. / d2inv)

    return d_spacings


def get_unique_families(hkls):
    """
    Returns unique families of Miller indices. Families must be permutations
    of each other.

    Args:
        hkls ([h, k, l]): List of Miller indices.

    Returns:
        {hkl: multiplicity}: A dict with unique hkl and multiplicity.
    """

    # TODO: Definitely can be sped up.
    def is_perm(hkl1, hkl2):
        h1 = map(abs, hkl1)
        h2 = map(abs, hkl2)
        return all([i == j for i, j in zip(sorted(h1), sorted(h2))])

    unique = {}
    for hkl1 in hkls:
        found = False
        for hkl2 in unique.keys():
            if is_perm(hkl1, hkl2):
                found = True
                unique[hkl2] += 1
                break
        if not found:
            unique[hkl1] = 1

    return unique

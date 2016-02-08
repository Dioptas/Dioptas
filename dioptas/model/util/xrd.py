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

import numpy as np
import json

with open(os.path.join(os.path.dirname(__file__),
                       "data/atomic_scattering_params.json")) as f:
    ATOMIC_SCATTERING_PARAMS = json.load(f)

with open(os.path.join(os.path.dirname(__file__),
                       "data/periodic_table.json")) as f:
    PERIODIC_TABLE = json.load(f)


class XRDCalculator(object):
    # Tolerance in which to treat two peaks as having the same two theta.
    TWO_THETA_TOL = 1e-5

    # Tolerance in which to treat a peak as effectively 0 if the scaled
    # intensity is less than this number. Since the max intensity is 100,
    # this means the peak must be less than 1e-5 of the peak intensity to be
    # considered as zero. This deals with numerical issues where systematic
    # absences do not cancel exactly to zero.

    def __init__(self, cif_phase, wavelength, min_d_spacing=0.5, min_intensity=0.5):
        self.cif_phase = cif_phase
        self.wavelength = wavelength
        self.min_d_spacing = min_d_spacing
        self.min_intensity = min_intensity

        self.reflections = self.calculate_hkl_within_sphere_and_min_d_spacing()
        self.calculate_reflection_intensities()

    def calculate_hkl_within_sphere_and_min_d_spacing(self):
        max_h = np.floor(2 * self.cif_phase.a / self.wavelength)
        max_k = np.floor(2 * self.cif_phase.b / self.wavelength)
        max_l = np.floor(2 * self.cif_phase.c / self.wavelength)

        h = reversed(np.arange(-max_h + 1, max_h, 1))
        k = reversed(np.arange(-max_k + 1, max_k, 1))
        l = reversed(np.arange(-max_l + 1, max_l, 1))
        s = [h, k, l]

        reciprocal_hkl = np.array(list(itertools.product(*s)))
        h = reciprocal_hkl[:, 0]
        k = reciprocal_hkl[:, 1]
        l = reciprocal_hkl[:, 2]

        d_hkl = compute_d_hkl(h, k, l, self.cif_phase)
        good_indices = np.argwhere(d_hkl > self.min_d_spacing)

        reflections = []
        for i in good_indices:
            reflections.append(Reflection(int(h[i][0]), int(k[i][0]), int(l[i][0]), d_hkl[i][0]))

        return reflections

    def calculate_reflection_intensities(self):

        # lets get first the atom parameters
        zs = []
        coeffs = []
        fcoords = []
        occus = []
        for atom in self.cif_phase.atoms:
            zs.append(PERIODIC_TABLE[atom[0]]['Atomic no'])
            try:
                c = ATOMIC_SCATTERING_PARAMS[atom[0]]
            except KeyError:
                raise ValueError("Unable to calculate XRD pattern as "
                                 "there is no scattering coefficients for"
                                 " %s." % atom[0])
            coeffs.append(c)
            fcoords.append(atom[1:])
            occus.append(1)

        zs = np.array(zs)
        coeffs = np.array(coeffs)
        fcoords = np.array(fcoords)
        occus = np.array(occus)


        two_thetas = []
        peaks = {}

        for reflection in self.reflections:
            d_hkl = reflection.d_spacing
            g_hkl = 1. / d_hkl
            if g_hkl != 0:
                hkl = np.array([reflection.h, reflection.k, reflection.l])

                s = g_hkl * 0.5
                s2 = s ** 2

                theta = np.arcsin(self.wavelength * g_hkl * 0.5)
                two_theta = degrees(2 * theta)

                g_dot_r = np.dot(fcoords, np.transpose([hkl])).T[0]

                fs = zs - 41.78214 * s2 * np.sum(coeffs[:, :, 0] * np.exp(-coeffs[:, :, 1] * s2), axis=1)
                f_hkl = np.sum(fs * occus * np.exp(2j * np.pi * g_dot_r))
                i_hkl = (f_hkl * f_hkl.conjugate()).real

                ind = np.where(np.abs(np.subtract(two_thetas, two_theta)) < XRDCalculator.TWO_THETA_TOL)

                lorentz_factor = (1 + np.cos(2 * theta) ** 2) / (np.sin(theta) ** 2 * np.cos(theta))

                if len(ind[0]) > 0:
                    peaks[two_thetas[ind[0]]][0] += i_hkl * lorentz_factor
                    peaks[two_thetas[ind[0]]][1].append(tuple(hkl))
                else:
                    peaks[two_theta] = [i_hkl * lorentz_factor, [tuple(hkl)], d_hkl]
                    two_thetas.append(two_theta)

        max_intensity = max([v[0] for v in peaks.values()])
        data = []
        for k in sorted(peaks.keys()):
            v = peaks[k]
            scaled_intensity = v[0] / max_intensity * 100
            fam = get_unique_families(v[1])
            if scaled_intensity > self.min_intensity:
                data.append([k, scaled_intensity, fam, v[2]])

        self.peaks = data



class Reflection():
    def __init__(self, h, k, l, d_spacing, intensity=None):
        self.h = h
        self.k = k
        self.l = l
        self.d_spacing = d_spacing
        self.intensity = intensity

    def __repr__(self):
        return "({},{},{}) {:.5f} - {}".format(self.h, self.k, self.l, self.d_spacing, self.intensity)


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
    #TODO: Definitely can be sped up.
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
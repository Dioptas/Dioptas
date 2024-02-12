# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
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

import os
import itertools
from math import degrees
from urllib.request import pathname2url

from CifFile import ReadCif
from .jcpds import jcpds
from ... import data_path

import numpy as np
import json

with open(os.path.join(data_path, "atomic_scattering_params.json")) as f:
    ATOMIC_SCATTERING_PARAMS = json.load(f)

with open(os.path.join(data_path, "periodic_table.json")) as f:
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
        file_url = 'file:' + pathname2url(filename)
        cif_file = ReadCif(file_url)
        cif_phase = CifPhase(cif_file[cif_file.keys()[0]])
        jcpds_phase = self.convert_cif_phase_to_jcpds(cif_phase)
        jcpds_phase.filename = filename
        jcpds_phase.name = os.path.splitext(os.path.basename(filename))[0]
        jcpds_phase.params['modified'] = False

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

        jcpds_phase.params['a0'] = cif_phase.a
        jcpds_phase.params['b0'] = cif_phase.b
        jcpds_phase.params['c0'] = cif_phase.c
        jcpds_phase.params['alpha0'] = cif_phase.alpha
        jcpds_phase.params['beta0'] = cif_phase.beta
        jcpds_phase.params['gamma0'] = cif_phase.gamma
        jcpds_phase.params['v0'] = cif_phase.volume
        jcpds_phase.params['symmetry'] = cif_phase.symmetry
        jcpds_phase.params['comments'] = [cif_phase.comments]

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
        occupancies = []
        for atom in cif_phase.atoms:
            atom_numbers.append(PERIODIC_TABLE[atom[0]]['Atomic no'])
            try:
                c = ATOMIC_SCATTERING_PARAMS[atom[0]]
            except KeyError:
                raise ValueError("Unable to calculate XRD pattern as "
                                 "there is no scattering coefficients for"
                                 " %s." % atom[0])
            form_coefficients.append(c)
            fractional_coordinates.append(atom[1:4])
            occupancies.append(atom[4])

        atom_numbers = np.array(atom_numbers)
        form_coefficients = np.array(form_coefficients)
        fractional_coordinates = np.array(fractional_coordinates)
        occupancies = np.array(occupancies)

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
                f_hkl = np.sum(fs * occupancies * np.exp(2j * np.pi * g_dot_r))
                i_hkl = (f_hkl * f_hkl.conjugate()).real

                ind = np.where(np.abs(np.subtract(two_thetas, two_theta)) < CifConverter.TWO_THETA_TOL)

                lorentz_factor = (1 + np.cos(2 * theta) ** 2) / (np.sin(theta) ** 2 * np.cos(theta))

                if len(ind[0]) > 0:
                    peak_ind = two_thetas[ind[0][0]]
                    peaks[peak_ind][0] += i_hkl * lorentz_factor
                    peaks[peak_ind][1].append(tuple(hkl))
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
                        *list(fam.keys())[0],
                        d_spacing=v[2],
                        intensity=scaled_intensity,
                        multiplicity=fam[list(fam.keys())[0]]
                    )
                )

        return calculated_reflections


class Reflection:
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
    alpha = np.deg2rad(cif_phase.alpha)
    beta = np.deg2rad(cif_phase.beta)
    gamma = np.deg2rad(cif_phase.gamma)

    symmetry = cif_phase.symmetry

    if symmetry == 'CUBIC':
        d2inv = (h ** 2 + k ** 2 + l ** 2) / a ** 2
    elif symmetry == 'TETRAGONAL':
        d2inv = (h ** 2 + k ** 2) / a ** 2 + l ** 2 / c ** 2
    elif symmetry == 'ORTHORHOMBIC':
        d2inv = h ** 2 / a ** 2 + k ** 2 / b ** 2 + l ** 2 / c ** 2
    elif symmetry == 'HEXAGONAL' or symmetry == 'TRIGONAL':
        d2inv = (h ** 2 + h * k + k ** 2) * 4. / 3. / a ** 2 + l ** 2 / c ** 2
    elif symmetry == 'RHOMBOHEDRAL':
        d2inv = (((1. + np.cos(alpha)) * ((h ** 2 + k ** 2 + l ** 2) -
                                          (1 - np.tan(0.5 * alpha) ** 2) * (h * k + k * l + l * h))) /
                 (a ** 2 * (1 + np.cos(alpha) - 2 * np.cos(alpha) ** 2)))
    elif symmetry == 'MONOCLINIC':
        d2inv = (h ** 2 / np.sin(beta) ** 2 / a ** 2 +
                 k ** 2 / b ** 2 +
                 l ** 2 / np.sin(beta) ** 2 / c ** 2 +
                 2 * h * l * np.cos(beta) / (a * c * np.sin(beta) ** 2))
    elif symmetry == 'TRICLINIC':
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


class CifPhase(object):
    """
    Phase created from a cif dictionary (a cif file can have several phases which can be read as a list by PyCifRw)

    This automatically creates symmetry equivalent position of atoms for further processing of the file.
    """

    def __init__(self, cif_dictionary):
        """

        :param cif_dictionary:
        :return:
        """
        self.cif_dictionary = cif_dictionary

        self.a = convert_cif_number_to_float(cif_dictionary['_cell_length_a'])
        self.b = convert_cif_number_to_float(cif_dictionary['_cell_length_b'])
        self.c = convert_cif_number_to_float(cif_dictionary['_cell_length_c'])

        self.alpha = convert_cif_number_to_float(cif_dictionary['_cell_angle_alpha'])
        self.beta = convert_cif_number_to_float(cif_dictionary['_cell_angle_beta'])
        self.gamma = convert_cif_number_to_float(cif_dictionary['_cell_angle_gamma'])

        if '_cell_volume' in cif_dictionary.keys():
            self.volume = convert_cif_number_to_float(cif_dictionary['_cell_volume'])
        else:
            self.volume = calculate_cell_volume(self.a, self.b, self.c,
                                                np.deg2rad(self.alpha), np.deg2rad(self.beta), np.deg2rad(self.gamma))

        if '_symmetry_space_group_name_h-m' in cif_dictionary.keys():
            self.space_group = cif_dictionary['_symmetry_space_group_name_h-m']
        elif '_symmetry_space_group_name_h-m_alt' in cif_dictionary.keys():
            self.space_group = cif_dictionary['_symmetry_space_group_name_h-m_alt']
        else:
            self.space_group = None

        if '_symmetry_Int_Tables_number'.lower() in cif_dictionary.keys():
            self.space_group_number = cif_dictionary.get('_symmetry_Int_Tables_number'.lower())
        elif '_space_group_IT_number'.lower() in cif_dictionary.keys():
            self.space_group_number = cif_dictionary.get('_space_group_IT_number'.lower())
        else:
            self.space_group_number = None

        if self.space_group_number is not None:
            self.space_group_number = int(self.space_group_number)

        self.symmetry = self.get_symmetry_from_space_group_number(self.space_group_number)

        self.comments = ''
        self.read_file_information()

        if '_symmetry_equiv_pos_as_xyz' in cif_dictionary.keys():
            self.symmetry_operations = cif_dictionary['_symmetry_equiv_pos_as_xyz']
        elif '_space_group_symop_operation_xyz' in cif_dictionary.keys():
            self.symmetry_operations = cif_dictionary['_space_group_symop_operation_xyz']

        for i in range(len(self.symmetry_operations)):
            self.symmetry_operations[i] = self.symmetry_operations[i].replace("/", "./")

        self._atom_labels = cif_dictionary['_atom_site_label']
        self._atom_x = [float(convert_cif_number_to_float(s)) for s in cif_dictionary['_atom_site_fract_x']]
        self._atom_y = [float(convert_cif_number_to_float(s)) for s in cif_dictionary['_atom_site_fract_y']]
        self._atom_z = [float(convert_cif_number_to_float(s)) for s in cif_dictionary['_atom_site_fract_z']]
        if '_atom_site_occupancy' in cif_dictionary.keys():
            self._atom_occupancy = [float(convert_cif_number_to_float(s)) for s in
                                    cif_dictionary['_atom_site_occupancy']]
        else:
            self._atom_occupancy = [1] * len(self._atom_labels)

        # Create a list of 4-tuples, where each tuple is an atom:
        # [ ('Si', 0.4697, 0.0, 0.0),  ('O', 0.4135, 0.2669, 0.1191),  ... ]
        self.atoms = [(self._atom_labels[i], self._atom_x[i], self._atom_y[i], self._atom_z[i],
                       self._atom_occupancy[i]) for i in range(len(self._atom_labels))]
        self.clean_atoms()
        self.generate_symmetry_equivalents()

    def clean_atoms(self):
        """
        Cleaning all atom labels and check atom positions
        """
        for i in range(len(self.atoms)):
            (name, xn, yn, zn, occu) = self.atoms[i]
            xn = (xn + 10.0) % 1.0
            yn = (yn + 10.0) % 1.0
            zn = (zn + 10.0) % 1.0
            name = self.convert_element(name)
            self.atoms[i] = (name, xn, yn, zn, occu)

    def generate_symmetry_equivalents(self):
        # The CIF file consists of a few atom positions plus several "symmetry
        # operations" that indicate the other atom positions within the unit cell.  So
        # using these operations, create copies of the atoms until no new copies can be
        # made.

        # Two atoms are on top of each other if they are less than "eps" away.
        eps = 0.0001  # in Angstrom

        # For each atom, apply each symmetry operation to create a new atom.
        i = 0
        while (i < len(self.atoms)):

            label, x, y, z, occu = self.atoms[i]

            for op in self.symmetry_operations:

                # Python is awesome: calling e.g. eval('x,y,1./2+z') will convert the
                # string into a 3-tuple using the current values for x,y,z!
                xn, yn, zn = eval(op)

                # Make sure that the new atom lies within the unit cell.
                xn = (xn + 10.0) % 1.0
                yn = (yn + 10.0) % 1.0
                zn = (zn + 10.0) % 1.0

                # Check if the new position is actually new, or the same as a previous
                # atom.
                new_atom = True
                for at in self.atoms:
                    if (abs(at[1] - xn) < eps and abs(at[2] - yn) < eps and abs(at[3] - zn) < eps) \
                            and at[0] == label:
                        new_atom = False

                # If the atom is new, add it to the list!
                if (new_atom):
                    self.atoms.append((label, xn, yn, zn, occu))  # add a 4-tuple

            # Update the loop iterator.
            i += 1

        # Sort the atoms according to type alphabetically.
        self.atoms = sorted(self.atoms, key=lambda at: at[0])
        self.atoms.reverse()

    def convert_element(self, label):
        """
        Convert atom labels such as 'Oa1' into 'O'.
        """

        elem2 = ['He', 'Li', 'Be', 'Ne', 'Na', 'Mg', 'Al', 'Si', 'Cl', 'Ar', 'Ca', 'Sc', 'Ti',
                 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr',
                 'Rb', 'Sr', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
                 'Sb', 'Te', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd',
                 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu', 'Hf', 'Ta', 'Re', 'Os', 'Ir', 'Pt',
                 'Au', 'Hg', 'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn', 'Fr', 'Ra', 'Ac', 'Th', 'Pa',
                 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr']

        if (label[0:2] in elem2):
            return label[0:2]

        elem1 = ['H', 'B', 'C', 'N', 'O', 'F', 'P', 'S', 'K', 'V', 'Y', 'I', 'W', 'U']

        if (label[0] in elem1):
            return label[0]

        print('WARNING: could not convert "%s" into element name!' % label)
        return label

    def get_symmetry_from_space_group_number(self, number):
        if number is not None:
            if number in [146, 148, 155, 160, 161, 166, 167]:
                if self.a != self.c:
                    return "HEXAGONAL"
                else:
                    return "RHOMBOHEDRAL"
            if number_between(number, 1, 2):
                return "TRICLINIC"
            if number_between(number, 3, 15):
                return "MONOCLINIC"
            if number_between(number, 16, 74):
                return "ORTHORHOMBIC"
            if number_between(number, 75, 142):
                return "TETRAGONAL"
            if number_between(number, 143, 167):
                return "TRIGONAL"
            if number_between(number, 168, 194):
                return "HEXAGONAL"
            if number_between(number, 195, 230):
                if self.alpha == 90 and self.beta == 90 and self.gamma == 90:
                    return "CUBIC"
                else:
                    return "RHOMBOHEDRAL"
        else:
            if self.alpha == 90 and self.beta == 90 and self.gamma == 90:
                if self.a == self.c and self.a == self.b:
                    return 'CUBIC'
                elif self.a == self.b:
                    return 'TETRAGONAL'
                else:
                    return 'ORTHORHOMBIC'
            elif self.alpha == 90 and self.beta == 90 and self.gamma == 120:
                if '6' in self.space_group:
                    return 'HEXAGONAL'
                elif '3' in self.space_group:
                    return 'TRIGONAL'
            elif self.alpha == 90 and self.gamma == 90:
                return 'MONOCLINIC'
            elif self.alpha == 90 and self.beta == 90:
                return 'MONOCLINIC'
        return 'TRICLINIC'

    def read_file_information(self):
        """
        Reads in all the header information and tries to build a good description of the phase.
        """
        if self.cif_dictionary.get('_chemical_formula_structural'):
            self.comments += self.cif_dictionary['_chemical_formula_structural'].replace(" ", "")
        elif self.cif_dictionary.get('_chemical_formula_analytical'):
            self.comments += self.cif_dictionary['_chemical_formula_analytical'].replace(" ", "")
        elif self.cif_dictionary.get('_chemical_formula_sum'):
            self.comments += self.cif_dictionary['_chemical_formula_sum'].replace(" ", "")

        if self.cif_dictionary.get('_symmetry_space_group_name_H-M'):
            if self.comments == '':
                self.comments += self.cif_dictionary.get('_symmetry_space_group_name_H-M').replace(" ", "")
            else:
                self.comments += ', ' + self.cif_dictionary.get('_symmetry_space_group_name_H-M').replace(" ", "")

        if self.cif_dictionary.get('_chemical_name_structure_type'):
            self.comments += ' - '
            self.comments += self.cif_dictionary['_chemical_name_structure_type']
            self.comments += ' structure type'
        if self.cif_dictionary.get('_database_code_icsd'):
            self.comments = self.comments.strip()
            if self.comments != '':
                self.comments += ', ICSD '
            else:
                self.comments += 'ICSD '
            self.comments += self.cif_dictionary['_database_code_icsd']
        elif self.cif_dictionary.get('_database_code_amcsd'):
            if self.comments != '':
                self.comments += ', amcsd '
            else:
                self.comments += 'amcsd '
            self.comments += self.cif_dictionary['_database_code_amcsd']


def number_between(number, low, high):
    """
    Tests if a number is in between low and high, whereby low and high are included  [low, high]
    :return: Boolean result for the result
    """
    if low <= number <= high:
        return True
    return False


def convert_cif_number_to_float(cif_number):
    return float(cif_number.split('(')[0])


def calculate_cell_volume(a, b, c, alpha, beta, gamma):
    """
    Calculates the cell volume using formula: 
    V = a*b*c*sqrt(1 + 2*cos(alpha)*cos(beta)*cos(gamma)-cos^2(alpha)-cos^2(beta)-cos^2(gamma))

    :param a: lattice parameter a
    :param b: lattice parameter b
    :param c: lattice parameter c
    :param alpha: lattice angle alpha in radians
    :param beta: lattice angle beta in radians
    :param gamma: lattice angle gamma in radians
    :return: cell volume
    """
    base = a * b * c
    part1 = np.cos(alpha) * np.cos(beta) * np.cos(gamma)
    part2 = np.cos(alpha) ** 2 + np.cos(beta) ** 2 + np.cos(gamma) ** 2
    return base * np.sqrt(1 + 2 * part1 - part2)

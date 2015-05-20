# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import os

import numpy as np
from pymatgen.core.structure import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.analysis.diffraction.xrd import XRDCalculator

from .jcpds import jcpds


def read_cif(filename, intensity_cutoff=0.5, minimum_d_spacing=0.5):
    """
    Reads in a cif file and converts it into a jcpds object. The X-ray reflections are calculated based on atomic positions,
    whereby the saved reflections have to have relative intensities above the an intensity cutoff.
    :param structure: pymatgen structure object e.g. obtained from read_cif
    :param intensity_cutoff: only reflections with relative intensities above this value are included in the jcpds
    :param minimum_d_spacing: only reflections with a d_spacing above this value are included in the jcpds object
    :return: jcpds object
    :type structure: Structure
    """
    structure = Structure.from_file(filename)
    jcpds_obj = jcpds()
    jcpds_obj._filename = filename
    jcpds_obj._name = ''.join(os.path.basename(filename).split('.')[:-1])
    jcpds_obj.comments.append("Composition: {}".format(structure.composition.reduced_formula))

    # getting the lattice parameter right:
    jcpds_obj.a0 = structure.lattice.a
    jcpds_obj.b0 = structure.lattice.b
    jcpds_obj.c0 = structure.lattice.c
    jcpds_obj.alpha0 = structure.lattice.alpha
    jcpds_obj.beta0 = structure.lattice.beta
    jcpds_obj.gamma0 = structure.lattice.gamma
    jcpds_obj.compute_v0()
    jcpds_obj.symmetry = get_symmetry_from_space_group_number(SpacegroupAnalyzer(structure).get_spacegroup_number())

    xrd_analyzer = XRDCalculator(wavelength=0.4)
    max_two_theta = 2 * np.arcsin(0.4 / (2. * minimum_d_spacing)) / np.pi * 180
    xrd_reflections = xrd_analyzer.get_xrd_data(structure, two_theta_range=(0, max_two_theta))
    for reflection in xrd_reflections:
        h, k, l = reflection[2].keys()[0]
        intensity = reflection[1]
        d_spacing = reflection[3]
        if intensity >= intensity_cutoff:
            jcpds_obj.add_reflection(h, k, l, intensity, d_spacing)
    return jcpds_obj


def get_symmetry_from_space_group_number(number):
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
        return "CUBIC"
    return None


def number_between(num, num_low, num_high):
    """
    Tests if a number is in between num_low and num_high, whereby num_low and num_high are included  [num_low, num_high]
    :return: Boolean result for the result
    """
    if num >= num_low and num <= num_high:
        return True
    return False

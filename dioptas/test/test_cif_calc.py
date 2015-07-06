# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import unittest
import os

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, 'data')
cif_path = os.path.join(data_path, "test.cif")
cif_path_hcp = os.path.join(data_path, "hcp.cif")
cif_path_fcc = os.path.join(data_path, "fcc2.cif")

import model.Helper.cif as cif
from model.Helper.jcpds import jcpds


class CifCalcTest(unittest.TestCase):
    def test_convert_structure_to_jcpds_file(self):
        jcpds_obj = cif.read_cif(cif_path)
        self.assertIsInstance(jcpds_obj, jcpds)
        self.assertEqual(jcpds_obj.name, "test*")
        self.assertEqual(jcpds_obj.comments[0], "Composition: Fe3C")

        self.assertEqual(jcpds_obj.a0, 4.5152)
        self.assertEqual(jcpds_obj.b0, 5.0807)
        self.assertEqual(jcpds_obj.c0, 6.753)
        self.assertEqual(jcpds_obj.alpha0, 90)
        self.assertEqual(jcpds_obj.beta0, 90)
        self.assertEqual(jcpds_obj.gamma0, 90)
        self.assertAlmostEqual(jcpds_obj.v0, 154.92, places=2)

        self.assertEqual(jcpds_obj.symmetry, "ORTHORHOMBIC")
        self.assertGreater(len(jcpds_obj.reflections), 0)

    def test_get_symmetry_group_from_space_group_number(self):
        self.assertEqual(cif.get_symmetry_from_space_group_number(1), "TRICLINIC")
        self.assertEqual(cif.get_symmetry_from_space_group_number(3), "MONOCLINIC")
        self.assertEqual(cif.get_symmetry_from_space_group_number(62), "ORTHORHOMBIC")
        self.assertEqual(cif.get_symmetry_from_space_group_number(150), "TRIGONAL")
        self.assertEqual(cif.get_symmetry_from_space_group_number(180), "HEXAGONAL")
        self.assertEqual(cif.get_symmetry_from_space_group_number(230), "CUBIC")
        self.assertEqual(cif.get_symmetry_from_space_group_number(231), None)
        self.assertEqual(cif.get_symmetry_from_space_group_number(0), None)

    def test_reading_hcp_cif_files(self):
        cif.read_cif(cif_path_hcp)

    def test_reading_fcc_cif_files(self):

        for i in range(195, 231):
            filename = os.path.join(data_path, str(i)+".cif")
            jcpds_obj = cif.read_cif(filename)

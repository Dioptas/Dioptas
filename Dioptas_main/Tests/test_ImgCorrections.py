# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'



import unittest
import numpy as np

from Data.ImgCorrection import ImgCorrectionManager, ImgCorrectionInterface


class DummyCorrection(ImgCorrectionInterface):
    def __init__(self, shape, number=1):
        self._data = np.ones(shape)*number
        self._shape = shape

    def get_data(self):
        return self._data

    def shape(self):
        return self._shape


class ImgCorrectionsUnitTest(unittest.TestCase):

    def setUp(self):
        self.corrections = ImgCorrectionManager()

    def tearDown(self):
        pass

    def test_add_first_matrix_and_detect_shape(self):
        cor = DummyCorrection((2048, 2048))

        self.corrections.add(cor)

        self.assertTrue(np.array_equal(cor.get_data(), self.corrections.get_data()))
        self.assertEqual(self.corrections.shape, (2048, 2048))

    def test_add_several_corrections(self):
        cor1 = DummyCorrection((2048, 2048),2)
        cor2 = DummyCorrection((2048, 2048),3)
        cor3 = DummyCorrection((2048, 2048),5)

        self.corrections.add(cor1)
        self.corrections.add(cor2)
        self.corrections.add(cor3)

        self.assertEqual(np.mean(self.corrections.get_data()), 2*3*5)

    def test_delete_corrections_without_names(self):
        self.assertEqual(self.corrections.get_data(), None)

        self.corrections.add(DummyCorrection((2048, 2048), 3))
        self.corrections.delete()
        self.assertEqual(self.corrections.get_data(), None)

        self.corrections.add(DummyCorrection((2048,2048),2))
        self.corrections.add(DummyCorrection((2048,2048),3))

        self.corrections.delete()
        self.assertEqual(np.mean(self.corrections.get_data()),2)
        self.corrections.delete()

    def test_delete_corrections_with_names(self):
        #add two corrections and check if both applied
        self.corrections.add(DummyCorrection((2048, 2048), 3), "cbn Correction")
        self.corrections.add(DummyCorrection((2048, 2048), 5), "oblique angle Correction")
        self.assertEqual(np.mean(self.corrections.get_data()), 3*5)

        #delete the first by name
        self.corrections.delete("cbn Correction")
        self.assertEqual(np.mean(self.corrections.get_data()), 5)

        #trying to delete non existent name will result in KeyError
        self.assertRaises(KeyError, self.corrections.delete, "blub")

        #just deleting something, when all corrections have a name will not change anything
        self.corrections.delete()
        self.assertEqual(np.mean(self.corrections.get_data()), 5)

    def test_set_shape(self):
        self.corrections.add(DummyCorrection((2048, 2048), 3), "cbn Correction")
        self.corrections.add(DummyCorrection((2048, 2048), 5), "oblique angle Correction")

        # setting it to a different shape should remove the existent corrections
        self.corrections.set_shape((2048, 1024))
        self.assertEqual(self.corrections.get_data(), None)

from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
from Data.ImgCorrection import CbnCorrection

class CbnCorrectionTest(unittest.TestCase):
    def setUp(self):
        # defining geometry
        image_shape = [2048, 2048] #pixel
        detector_distance = 200 #mm
        wavelength = 0.31 #angstrom
        center_x = 1024 #pixel
        center_y = 1024 #pixel
        tilt = 0 #degree
        rotation = 0 #degree
        pixel_size = 79 #um
        dummy_tth = np.linspace(0, 35, 2000)
        dummy_int = np.ones(dummy_tth.shape)
        geometry = AzimuthalIntegrator()
        geometry.setFit2D(directDist=detector_distance,
                          centerX=center_x,
                          centerY=center_y,
                          tilt=tilt,
                          tiltPlanRotation=rotation,
                          pixelX=pixel_size,
                          pixelY=pixel_size)
        geometry.wavelength = wavelength/1e10
        self.dummy_img = geometry.calcfrom1d(dummy_tth, dummy_int, shape=image_shape, correctSolidAngle=True)


        self.tth_array = geometry.twoThetaArray(image_shape)
        self.azi_array = geometry.chiArray(image_shape)

    def test_that_it_is_calculating_correctly(self):
        cbn_correction = CbnCorrection(self.tth_array, self.azi_array,
                                      diamond_thickness=2.2,
                                      seat_thickness=5.3,
                                      small_cbn_seat_radius=0.4,
                                      large_cbn_seat_radius=1.95,
                                      tilt=0,
                                      tilt_rotation=0)
        cbn_correction_data = cbn_correction.get_data()
        self.assertGreater(np.sum(cbn_correction_data),0)
        self.assertEqual(cbn_correction_data.shape, self.dummy_img.shape)

from Data.ImgCorrection import ObliqueAngleDetectorAbsorptionCorrection

class ObliqueAngleDetectorAbsorptionCorrectionTest(unittest.TestCase):
    def setUp(self):
        # defining geometry
        image_shape = [2048, 2048] #pixel
        detector_distance = 200 #mm
        wavelength = 0.31 #angstrom
        center_x = 1024 #pixel
        center_y = 1024 #pixel
        self.tilt = 0 #degree
        self.rotation = 0 #degree
        pixel_size = 79 #um
        dummy_tth = np.linspace(0, 35, 2000)
        dummy_int = np.ones(dummy_tth.shape)
        geometry = AzimuthalIntegrator()
        geometry.setFit2D(directDist=detector_distance,
                          centerX=center_x,
                          centerY=center_y,
                          tilt=self.tilt,
                          tiltPlanRotation=self.rotation,
                          pixelX=pixel_size,
                          pixelY=pixel_size)
        geometry.wavelength = wavelength/1e10
        self.dummy_img = geometry.calcfrom1d(dummy_tth, dummy_int, shape=image_shape, correctSolidAngle=True)


        self.tth_array = geometry.twoThetaArray(image_shape)
        self.azi_array = geometry.chiArray(image_shape)

    def test_that_it_is_correctly_calculating(self):
        oblique_correction = ObliqueAngleDetectorAbsorptionCorrection(
            tth_array=self.tth_array,
            azi_array=self.azi_array,
            detector_thickness=40,
            absorption_length=465.5,
            tilt=self.tilt,
            rotation=self.rotation
        )
        oblique_correction_data = oblique_correction.get_data()
        self.assertGreater(np.sum(oblique_correction_data),0)
        self.assertEqual(oblique_correction_data.shape, self.dummy_img.shape)
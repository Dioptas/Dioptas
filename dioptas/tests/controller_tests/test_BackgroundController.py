# -*- coding: utf8 -*-

import os

from ..utility import QtTest, unittest_data_path
from ...widgets.integration import IntegrationWidget
from ...controller.integration.BackgroundController import BackgroundController
from ...model.DioptasModel import DioptasModel


class BackgroundControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = BackgroundController(
            working_dir=self.working_dir,
            widget=self.widget,
            dioptas_model=self.model
        )

    def test_configuration_selected_changes_background_image_widgets(self):
        self.model.img_model.load(os.path.join(unittest_data_path, 'image_001.tif'))
        self.model.img_model.load_background(os.path.join(unittest_data_path, 'image_001.tif'))

        self.model.add_configuration()
        self.model.img_model.load(os.path.join(unittest_data_path, 'image_001.tif'))
        self.model.img_model.load_background(os.path.join(unittest_data_path, 'image_002.tif'))

        self.assertEqual(str(self.widget.bkg_image_filename_lbl.text()), 'image_002.tif')

        self.model.select_configuration(0)
        self.assertEqual(str(self.widget.bkg_image_filename_lbl.text()), 'image_001.tif')

        self.widget.bkg_image_offset_sb.setValue(100)
        self.model.select_configuration(1)
        self.assertEqual(self.widget.bkg_image_offset_sb.value(), 0)

        self.widget.bkg_image_scale_sb.setValue(2)
        self.model.select_configuration(0)
        self.assertEqual(self.widget.bkg_image_scale_sb.value(), 1)

import gc
import os
import unittest

from ..utility import QtTest, click_button, delete_if_exists

import numpy as np
from subprocess import check_output

from qtpy import QtWidgets, QtCore
from qtpy.QtTest import QTest

from mock import MagicMock

from ...model.DioptasModel import DioptasModel
from ...widgets.integration import IntegrationWidget
from ...controller.integration import IntegrationController

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, 'data')
jcpds_path = os.path.join(data_path, 'jcpds')


class BatchIntegrationFunctionalTest(QtTest):
    def setUp(self):
        self.model = DioptasModel()

        self.integration_widget = IntegrationWidget()
        self.integration_controller = IntegrationController(widget=self.integration_widget,
                                                            dioptas_model=self.model)
        self.model.calibration_model.load(os.path.join(data_path, 'lambda/L2.poni'))

        files = [os.path.join(data_path, 'lambda/testasapo1_1009_00002_m1_part00000.nxs'),
                 os.path.join(data_path, 'lambda/testasapo1_1009_00002_m1_part00001.nxs')]

        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=files)
        click_button(self.integration_widget.batch_widget.file_control_widget.load_btn)

        self.integration_controller.batch_controller.integrate()

    def tearDown(self):
        del self.integration_widget
        del self.integration_controller
        del self.model
        gc.collect()

    def test_dioptas_batch(self):

        data_files = os.path.join(data_path, 'lambda/testasapo1_1009_00002_m*nxs')
        mask_file = os.path.join(data_path, 'lambda/l2_l1_synrh9_150m_200ms_850c_oscillation_00001_m2.mask')
        out_path = os.path.join(data_path, 'tmp')
        script_parh = os.path.join(unittest_path, os.pardir, os.pardir, os.pardir, 'scripts')

        os.makedirs(out_path, exist_ok=True)
        cmd = f'{script_parh}/dioptas_batch --data_path {data_files} '
        cmd += f'--out_path {out_path} '
        cmd += f"--cal_file {os.path.join(data_path, 'lambda/L2.poni')} "
        cmd += f"--mask_file {mask_file}"

        resp = check_output(cmd, shell=True).decode('utf8')

        proc_file = os.path.join(data_path, 'tmp/testasapo1_1009_00002_v-01.nxs')
        QtWidgets.QFileDialog.getOpenFileNames = MagicMock(return_value=[proc_file])
        click_button(self.integration_widget.batch_widget.file_control_widget.load_btn)

        self.assertEqual(self.model.batch_model.data.shape[0], 50)
        self.assertEqual(self.model.batch_model.data.shape[1],
                         self.model.batch_model.binning.shape[0])

        mask = self.model.batch_model.mask_model.get_mask()
        self.assertEqual(mask.shape, (1833, 1556))
        self.assertEqual(resp, '')

        import shutil
        shutil.rmtree(os.path.join(data_path, 'tmp'))
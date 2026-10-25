# SPDX-License-Identifier: MIT
from pathlib import Path
import importlib

import numpy as np
import pytest

from .test_SingleCrystalController import load_scene
from ...controller.MainController import MainController


@pytest.fixture
def diamond_controller(qapp):
    controller = MainController(use_settings=False, run_async_processing=False,
                                experimental_single_crystal=True)
    controller.widget.show()
    yield controller
    controller.widget.close()


def test_optional_mask_applies_with_global_use_mask_off(diamond_controller, tmp_path, monkeypatch):
    c=diamond_controller
    load_scene(c,tmp_path)
    sc,w=c.single_crystal_controller,c.widget.single_crystal_widget
    module=importlib.import_module('dioptas.controller.SingleCrystalController')

    class Plan:
        def __init__(self,*args,**kwargs):self.records=[]
        def compute(self,image,existing_mask=None,**kwargs):
            mask=np.zeros(image.shape,bool);mask[20,20]=True
            self.records.append(dict(pixels=1,runtime_ms=2.0))
            return mask
        def metadata(self):return dict(algorithm='test-diamond')
    monkeypatch.setattr(module,'DiamondMaskPlan',Plan)
    w.diamond_calibration.setText(str(Path(__file__).parents[1]/'data/CeO2_Pilatus1M.poni'))
    assert not w.diamond_enabled.isChecked()
    c.model.use_mask=False
    c.widget.single_crystal_mode_btn.click()
    w.diamond_enabled.setChecked(True)
    task=sc._task()
    assert task.diamond_mask[20,20] and task.mask[20,20]
    assert not c.model.use_mask
    assert task.mask_policy['diamond']['algorithm']=='test-diamond'
    assert w.img_widget.mask_data[20,20]
    w.diamond_enabled.setChecked(False)
    task=sc._task()
    assert task.diamond_mask is None and not task.mask[20,20]


def test_missing_calibration_does_not_silently_run_unmasked(diamond_controller, tmp_path):
    c=diamond_controller
    load_scene(c,tmp_path)
    sc,w=c.single_crystal_controller,c.widget.single_crystal_widget
    c.widget.single_crystal_mode_btn.click()
    w.diamond_enabled.setChecked(True)
    sc.detect()
    assert sc.result is None
    assert 'PONI calibration' in w.status_label.text()

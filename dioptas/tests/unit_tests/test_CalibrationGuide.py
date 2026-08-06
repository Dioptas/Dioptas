# SPDX-License-Identifier: MIT

import os

from dioptas.model.CalibrationGuide import (
    CalibrationGuide,
    NextAction,
    Step,
    StepStatus,
)

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")


def load_test_image(dioptas_model):
    dioptas_model.img_model.load(os.path.join(data_path, "image_001.tif"))


def pick_peak(dioptas_model, ring=0, position=(10.0, 20.0)):
    calibration_params = dioptas_model.calibration_model.params
    calibration_params.peak_selections = calibration_params.peak_selections + (
        (ring, (position,)),
    )


def test_initial_state_suggests_loading_an_image(dioptas_model):
    guide = CalibrationGuide(dioptas_model)

    assert not guide.state.image_loaded
    assert guide.state.num_peaks == 0
    assert not guide.state.is_calibrated
    assert guide.state.next_action == NextAction.LOAD_IMAGE
    assert guide.state.step_status[Step.IMAGE] == StepStatus.ATTENTION
    assert guide.state.step_status[Step.PEAKS] == StepStatus.PENDING
    assert guide.state.step_status[Step.CALIBRATE] == StepStatus.PENDING


def test_loading_an_image_suggests_picking_peaks(dioptas_model):
    guide = CalibrationGuide(dioptas_model)
    load_test_image(dioptas_model)

    assert guide.state.image_loaded
    assert guide.state.next_action == NextAction.PICK_PEAKS
    assert guide.state.step_status[Step.IMAGE] == StepStatus.DONE
    assert guide.state.step_status[Step.PEAKS] == StepStatus.ATTENTION


def test_picking_peaks_suggests_calibrating(dioptas_model):
    guide = CalibrationGuide(dioptas_model)
    load_test_image(dioptas_model)
    pick_peak(dioptas_model, ring=0, position=(10.0, 20.0))
    pick_peak(dioptas_model, ring=0, position=(30.0, 40.0))
    pick_peak(dioptas_model, ring=1, position=(50.0, 60.0))

    assert guide.state.num_peaks == 3
    assert guide.state.num_rings == 2
    assert guide.state.next_action == NextAction.CALIBRATE
    assert guide.state.step_status[Step.PEAKS] == StepStatus.DONE
    assert guide.state.step_status[Step.CALIBRATE] == StepStatus.ATTENTION


def test_calibrating_suggests_saving(dioptas_model):
    guide = CalibrationGuide(dioptas_model)
    load_test_image(dioptas_model)
    pick_peak(dioptas_model)
    dioptas_model.calibration_model.params.is_calibrated = True

    assert guide.state.next_action == NextAction.SAVE
    assert guide.state.step_status[Step.CALIBRATE] == StepStatus.DONE
    assert guide.state.step_status[Step.VALIDATE] == StepStatus.ATTENTION
    assert not guide.state.is_saved


def test_saving_completes_the_workflow(dioptas_model):
    guide = CalibrationGuide(dioptas_model)
    load_test_image(dioptas_model)
    pick_peak(dioptas_model)
    dioptas_model.calibration_model.params.is_calibrated = True
    dioptas_model.calibration_model.params.poni_filename = "/somewhere/test.poni"

    assert guide.state.is_saved
    assert guide.state.next_action == NextAction.NONE
    assert guide.state.step_status[Step.VALIDATE] == StepStatus.DONE


def test_loaded_poni_without_peaks_needs_no_action(dioptas_model):
    # loading an existing .poni gives a calibrated, file-backed state
    guide = CalibrationGuide(dioptas_model)
    load_test_image(dioptas_model)
    dioptas_model.calibration_model.params.is_calibrated = True
    dioptas_model.calibration_model.params.poni_filename = "/somewhere/test.poni"

    assert guide.state.next_action == NextAction.NONE
    # picking peaks was never done, but the loaded calibration makes it
    # unnecessary — shown as "skipped" rather than "not started"
    assert guide.state.step_status[Step.PEAKS] == StepStatus.SKIPPED


def test_clearing_peaks_reverts_suggestion(dioptas_model):
    guide = CalibrationGuide(dioptas_model)
    load_test_image(dioptas_model)
    pick_peak(dioptas_model)
    dioptas_model.calibration_model.clear_peaks()

    assert guide.state.num_peaks == 0
    assert guide.state.next_action == NextAction.PICK_PEAKS


def test_changed_emits_only_on_actual_state_change(dioptas_model):
    guide = CalibrationGuide(dioptas_model)
    emitted = []
    guide.changed.connect(lambda state: emitted.append(state))

    load_test_image(dioptas_model)
    assert len(emitted) == 1
    assert emitted[-1].image_loaded

    # irrelevant param change must not emit
    dioptas_model.img_model.params.factor = 2.0
    assert len(emitted) == 1

    pick_peak(dioptas_model)
    assert len(emitted) == 2
    assert emitted[-1].next_action == NextAction.CALIBRATE


def test_configuration_switch_refreshes_state(dioptas_model):
    guide = CalibrationGuide(dioptas_model)
    load_test_image(dioptas_model)
    assert guide.state.image_loaded

    dioptas_model.add_configuration()
    dioptas_model.select_configuration(1)
    # the new configuration shares the loaded image state via copy, so probe
    # a difference that is configuration-local: peaks picked in config 0 only
    dioptas_model.select_configuration(0)
    pick_peak(dioptas_model)
    assert guide.state.num_peaks == 1

    dioptas_model.select_configuration(1)
    assert guide.state.num_peaks == 0

    dioptas_model.select_configuration(0)
    assert guide.state.num_peaks == 1

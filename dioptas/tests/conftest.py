import pytest
import gc

from dioptas.controller.integration import PhaseController, PatternController, BatchController, BackgroundController, \
    IntegrationController
from dioptas.model.DioptasModel import DioptasModel
from dioptas.model.CalibrationModel import CalibrationModel
from dioptas.widgets.integration import IntegrationWidget


@pytest.fixture(scope="function")
def dioptas_model():
    model = DioptasModel()
    yield model
    clear_model_memory(model)


def clear_model_memory(model):
    for config in model.configurations:
        if config.calibration_model.pattern_geometry:
            config.calibration_model.pattern_geometry.reset()
            del config.calibration_model.pattern_geometry

        if config.calibration_model.cake_geometry:
            config.calibration_model.cake_geometry.reset()
            del config.calibration_model.cake_geometry
    gc.collect()


@pytest.fixture()
def img_model(dioptas_model):
    return dioptas_model.img_model


@pytest.fixture
def calibration_model(dioptas_model):
    calibration_model = dioptas_model.calibration_model
    yield calibration_model
    calibration_model.pattern_geometry.reset()
    if calibration_model.cake_geometry is not None:
        calibration_model.cake_geometry.reset()
        del calibration_model.cake_geometry
    del calibration_model.pattern_geometry
    del calibration_model
    gc.collect()


@pytest.fixture
def phase_controller(integration_widget, dioptas_model):
    return PhaseController(integration_widget, dioptas_model)


@pytest.fixture
def pattern_controller(integration_widget, dioptas_model):
    return PatternController(integration_widget, dioptas_model)


@pytest.fixture
def integration_widget(qtbot):
    widget = IntegrationWidget()
    yield widget
    widget.close()


@pytest.fixture
def integration_controller(integration_widget, dioptas_model, qtbot):
    return IntegrationController(widget=integration_widget, dioptas_model=dioptas_model)


@pytest.fixture
def batch_model(dioptas_model):
    return dioptas_model.batch_model


@pytest.fixture
def batch_controller(integration_widget, dioptas_model):
    return BatchController(integration_widget, dioptas_model)


@pytest.fixture
def batch_widget(integration_widget):
    return integration_widget.batch_widget


@pytest.fixture
def background_controller(integration_widget, dioptas_model, qtbot):
    return BackgroundController(integration_widget, dioptas_model)

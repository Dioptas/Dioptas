# SPDX-License-Identifier: MIT

import os
import weakref

import pytest

# Run the Qt tests headless by default, so test windows don't pop up and steal
# focus while working. This matches the CI setup, which sets QT_QPA_PLATFORM to
# offscreen for all test workflows. Set DIOPTAS_TEST_GUI=1 to watch the tests
# run in real windows, or set QT_QPA_PLATFORM explicitly to override.
if not os.environ.get("DIOPTAS_TEST_GUI") and "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"


_OFFSCREEN_NOISE = (
    "This plugin does not support",
    "QOpenGLWidget is not supported on this platform",
    "QOpenGLWidget: Failed to create context",
    "Populating font family aliases took",
)


def pytest_configure(config):
    """Filter the Qt warnings the offscreen platform emits for unsupported calls.

    The offscreen plugin warns on every raise()/propagateSizeHints()/OpenGL
    context call, which floods the test output without indicating a problem.
    """
    if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        return

    import sys
    from qtpy import QtCore

    def handler(msg_type, context, message):
        if not any(message.startswith(prefix) for prefix in _OFFSCREEN_NOISE):
            print(message, file=sys.stderr)

    QtCore.qInstallMessageHandler(handler)


@pytest.fixture(scope="session")
def qapp():
    """Fixture ensuring QApplication is instanciated"""
    from qtpy import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    try:
        yield app
    finally:
        if app is not None:
            app.closeAllWindows()


@pytest.fixture
def qWidgetFactory(qapp):
    """QWidget factory as fixture

    This fixture provides a function taking a QWidget subclass as argument
    which returns an instance of this QWidget making sure it is shown first
    and destroyed once the test is done.
    """
    from qtpy import QtCore
    from qtpy.QtTest import QTest

    widgets = set()

    def createWidget(cls, *args, **kwargs):
        widget = cls(*args, **kwargs)
        # For Popup windows, remove the Popup flag to prevent automatic closing in tests
        if widget.windowFlags() & QtCore.Qt.Popup:
            widget.setWindowFlags(widget.windowFlags() & ~QtCore.Qt.Popup)
        # Don't set WA_DeleteOnClose if widget already has it
        if not widget.testAttribute(QtCore.Qt.WA_DeleteOnClose):
            widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        widget.show()
        QTest.qWaitForWindowExposed(widget)
        widgets.add(widget)
        return weakref.proxy(widget)

    try:
        yield createWidget
    finally:
        for widget in widgets:
            widget.close()
        qapp.processEvents()


@pytest.fixture
def main_controller(qapp):
    """Fixture providing a MainController instance"""
    from qtpy.QtTest import QTest
    from dioptas.controller.MainController import MainController
    from qtpy import QtCore

    controller = MainController(use_settings=False)
    controller.show_window()
    controller.widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    QTest.qWaitForWindowExposed(controller.widget)
    try:
        yield controller
    finally:
        controller.widget.close()


@pytest.fixture(scope="function")
def dioptas_model():
    from dioptas.model.DioptasModel import DioptasModel

    model = DioptasModel()
    yield model


@pytest.fixture
def phase_controller(integration_widget, dioptas_model):
    from dioptas.controller.integration import PhaseController

    return PhaseController(integration_widget, dioptas_model)


@pytest.fixture
def pattern_controller(integration_widget, dioptas_model):
    from dioptas.controller.integration import PatternController

    return PatternController(integration_widget, dioptas_model)


@pytest.fixture
def integration_widget(qtbot):
    from dioptas.widgets.integration import IntegrationWidget

    widget = IntegrationWidget()
    yield widget
    widget.close()


@pytest.fixture
def calibration_widget(qtbot):
    from dioptas.widgets.CalibrationWidget import CalibrationWidget

    widget = CalibrationWidget()
    yield widget
    widget.close()


@pytest.fixture
def integration_controller(integration_widget, dioptas_model, qtbot):
    from dioptas.controller.integration import IntegrationController

    return IntegrationController(widget=integration_widget, dioptas_model=dioptas_model)


@pytest.fixture
def batch_model(dioptas_model):
    return dioptas_model.batch_model


@pytest.fixture
def batch_controller(integration_widget, dioptas_model):
    from dioptas.controller.integration import BatchController

    return BatchController(integration_widget, dioptas_model)


@pytest.fixture
def batch_widget(integration_widget):
    return integration_widget.batch_widget


@pytest.fixture
def background_controller(integration_widget, dioptas_model, qtbot):
    from dioptas.controller.integration import BackgroundController
    return BackgroundController(integration_widget, dioptas_model)


@pytest.fixture
def image_controller(integration_widget, dioptas_model, qtbot):
    from dioptas.controller.integration import ImageController
    return ImageController(integration_widget, dioptas_model)


@pytest.fixture
def calibration_controller(calibration_widget, dioptas_model, qtbot):
    from dioptas.controller import CalibrationController
    return CalibrationController(calibration_widget, dioptas_model)


@pytest.fixture
def calibration_model(dioptas_model):
    return dioptas_model.calibration_model


@pytest.fixture
def img_model(dioptas_model):
    return dioptas_model.img_model


# --- Shared test data paths ---

data_path = os.path.join(os.path.dirname(__file__), "data")


@pytest.fixture(scope="session")
def test_data_path():
    """Path to the shared test data directory."""
    return data_path


# --- Calibrated model fixtures (function-scoped for isolation) ---


@pytest.fixture
def calibrated_model():
    """A DioptasModel with CeO2 Pilatus1M calibration and image loaded."""
    from dioptas.model.DioptasModel import DioptasModel

    model = DioptasModel()
    model.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    model.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    return model


@pytest.fixture
def calibrated_config():
    """A Configuration with CeO2 Pilatus1M calibration and image loaded."""
    from dioptas.model.Configuration import Configuration

    config = Configuration()
    config.calibration_model.load(os.path.join(data_path, "CeO2_Pilatus1M.poni"))
    config.img_model.load(os.path.join(data_path, "CeO2_Pilatus1M.tif"))
    return config

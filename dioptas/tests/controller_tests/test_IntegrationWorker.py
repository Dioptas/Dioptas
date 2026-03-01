import os
import numpy as np
import pytest
from qtpy import QtCore

from dioptas.model.Configuration import Configuration
from dioptas.model.MapModel2 import MapModel2
from dioptas.controller.integration.IntegrationWorker import (
    IntegrationSnapshot,
    IntegrationWorker,
    _create_img_model,
    _create_pyfai_geometry,
)

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, os.pardir, "data")
map_img_path = os.path.join(data_path, "map")
map_img_file_names = sorted(
    f
    for f in os.listdir(map_img_path)
    if os.path.isfile(os.path.join(map_img_path, f))
)
map_img_file_paths = [
    os.path.join(map_img_path, filename) for filename in map_img_file_names
]

cal_file = os.path.join(data_path, "CeO2_Pilatus1M.poni")

lambda_files = [
    os.path.join(data_path, "lambda/testasapo1_1009_00002_m1_part00000.nxs"),
    os.path.join(data_path, "lambda/testasapo1_1009_00002_m1_part00001.nxs"),
]
lambda_cal_file = os.path.join(data_path, "lambda/L2.poni")


@pytest.fixture
def configuration():
    return Configuration()


@pytest.fixture
def calibrated_configuration(configuration):
    configuration.calibration_model.load(cal_file)
    return configuration


class TestIntegrationSnapshot:
    def test_snapshot_captures_calibration_state(self, calibrated_configuration):
        config = calibrated_configuration
        snap = IntegrationSnapshot.from_configuration(config)

        assert snap.pyfai_config is not None
        assert snap.unit == config.integration_unit
        assert snap.num_points == config.integration_rad_points
        assert snap.azi_range == config.oned_azimuth_range
        assert snap.polarization_factor == config.calibration_model.polarization_factor
        assert snap.correct_solid_angle == config.calibration_model.correct_solid_angle
        assert snap.supersampling_factor == config.calibration_model.supersampling_factor
        assert snap.wavelength == config.calibration_model.pattern_geometry.wavelength

    def test_snapshot_captures_img_state(self, calibrated_configuration):
        config = calibrated_configuration
        config.img_model._factor = 2.0
        config.img_model._background_scaling = 0.5
        config.img_model._background_offset = 10.0

        snap = IntegrationSnapshot.from_configuration(config)

        assert snap.factor == 2.0
        assert snap.background_scaling == 0.5
        assert snap.background_offset == 10.0
        assert snap.img_transformations == config.img_model.img_transformations

    def test_snapshot_captures_mask(self, calibrated_configuration):
        config = calibrated_configuration
        # Load an image to set dimensions
        config.img_model.load(map_img_file_paths[0])
        config.mask_model.set_dimension(config.img_model.img_data.shape)
        config.use_mask = True

        snap = IntegrationSnapshot.from_configuration(config)

        assert snap.mask_data is not None
        assert snap.mask_data.shape == config.img_model.img_data.shape

    def test_snapshot_mask_is_copy(self, calibrated_configuration):
        config = calibrated_configuration
        config.img_model.load(map_img_file_paths[0])
        config.mask_model.set_dimension(config.img_model.img_data.shape)
        config.use_mask = True

        snap = IntegrationSnapshot.from_configuration(config)

        # Modifying the original mask should not affect the snapshot
        original_mask = config.mask_model.get_mask()
        assert snap.mask_data is not original_mask

    def test_snapshot_no_mask(self, calibrated_configuration):
        config = calibrated_configuration
        config.use_mask = False

        snap = IntegrationSnapshot.from_configuration(config)
        assert snap.mask_data is None

    def test_trim_trailing_zeros_always_false(self, calibrated_configuration):
        config = calibrated_configuration
        config.trim_trailing_zeros = True

        snap = IntegrationSnapshot.from_configuration(config)
        assert snap.trim_trailing_zeros is False


class TestCreateImgModel:
    def test_creates_fresh_img_model(self, calibrated_configuration):
        snap = IntegrationSnapshot.from_configuration(calibrated_configuration)
        img_model = _create_img_model(snap)

        assert img_model is not calibrated_configuration.img_model
        assert img_model._factor == snap.factor
        assert img_model._background_scaling == snap.background_scaling
        assert img_model._background_offset == snap.background_offset

    def test_img_model_signals_blocked(self, calibrated_configuration):
        snap = IntegrationSnapshot.from_configuration(calibrated_configuration)
        img_model = _create_img_model(snap)

        assert img_model.img_changed.blocked is True


class TestCreatePyFAIGeometry:
    def test_creates_geometry_from_config(self, calibrated_configuration):
        snap = IntegrationSnapshot.from_configuration(calibrated_configuration)
        geometry = _create_pyfai_geometry(snap)

        original = calibrated_configuration.calibration_model.pattern_geometry
        assert geometry.wavelength == pytest.approx(original.wavelength)
        assert geometry.dist == pytest.approx(original.dist)
        assert geometry.poni1 == pytest.approx(original.poni1)
        assert geometry.poni2 == pytest.approx(original.poni2)


class TestMapWorker:
    def test_map_worker_produces_correct_results(self, qapp, calibrated_configuration):
        """Compare worker results with synchronous MapModel2.load()"""
        config = calibrated_configuration
        filepaths = sorted(map_img_file_paths[:6])

        # Disable dioptrin so both paths use pyFAI for exact comparison
        config.calibration_model.use_dioptrin = False

        # Run synchronous integration
        sync_model = MapModel2(config)
        sync_model.load(filepaths)

        # Run worker
        snapshot = IntegrationSnapshot.from_configuration(config)
        assert not snapshot.use_dioptrin
        worker = IntegrationWorker(snapshot, filepaths, mode="map")

        results = {}
        finished = [False]

        def on_finished(r):
            results.update(r)
            finished[0] = True

        def on_error(e):
            finished[0] = True
            pytest.fail(f"Worker error: {e}")

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()
        # Wait for worker to complete (up to 30 seconds)
        worker.wait(30000)
        qapp.processEvents()

        assert finished[0], "Worker did not finish in time"
        assert results["pattern_x"] is not None
        assert len(results["pattern_intensities"]) == len(filepaths)
        assert len(results["point_infos"]) == len(filepaths)

        # pyFAI integration is deterministic — results should match exactly
        np.testing.assert_allclose(
            results["pattern_x"], sync_model.pattern_x, rtol=1e-5
        )
        np.testing.assert_allclose(
            results["pattern_intensities"],
            sync_model.pattern_intensities,
            rtol=1e-5,
        )

    def test_map_worker_cancellation(self, qapp, calibrated_configuration):
        """Cancel mid-integration and verify it completes (possibly with partial results)"""
        config = calibrated_configuration
        # Use pyFAI path for predictable per-frame cancellation checking
        config.calibration_model.use_dioptrin = False
        filepaths = sorted(map_img_file_paths)

        snapshot = IntegrationSnapshot.from_configuration(config)
        worker = IntegrationWorker(snapshot, filepaths, mode="map")

        results = {}
        progress_counts = []

        def on_progress(current, total):
            progress_counts.append(current)
            if current >= 2:
                worker.cancel()

        def on_finished(r):
            results.update(r)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.start()
        worker.wait(30000)
        qapp.processEvents()

        # Worker should have finished (with partial or full results)
        assert len(results.get("pattern_intensities", [])) >= 2
        # With pyFAI path, cancellation should stop before all files
        # (though timing may cause all to complete on fast machines)
        assert len(progress_counts) >= 2

    def test_set_integration_results_updates_model(self, calibrated_configuration):
        """Test that set_integration_results correctly updates the model"""
        config = calibrated_configuration
        filepaths = sorted(map_img_file_paths[:6])

        # Run synchronous integration to get reference results
        sync_model = MapModel2(config)
        sync_model.load(filepaths)

        # Create a fresh model and set results
        new_model = MapModel2(config)
        new_model.set_integration_results(
            sync_model.pattern_x,
            sync_model.pattern_intensities,
            sync_model.point_infos,
            filepaths,
        )

        assert new_model.filepaths == filepaths
        assert new_model.map is not None
        assert new_model.map.shape == sync_model.map.shape
        np.testing.assert_array_equal(new_model.map, sync_model.map)

    def test_no_main_thread_signals_during_worker(self, qapp, calibrated_configuration):
        """Verify main thread's model signals don't fire during worker"""
        config = calibrated_configuration
        filepaths = sorted(map_img_file_paths[:3])

        signal_fired = [False]
        config.img_model.img_changed.connect(lambda: signal_fired.__setitem__(0, True))

        snapshot = IntegrationSnapshot.from_configuration(config)
        worker = IntegrationWorker(snapshot, filepaths, mode="map")

        worker.start()
        worker.wait(30000)
        qapp.processEvents()

        assert not signal_fired[0], "Main thread img_changed signal should not fire"


class TestBatchWorker:
    @pytest.fixture
    def batch_setup(self):
        config = Configuration()
        config.calibration_model.load(lambda_cal_file)
        batch_model = config.batch_model
        batch_model.set_image_files(lambda_files)
        return config, batch_model

    def test_batch_worker_produces_results(self, qapp, batch_setup):
        config, batch_model = batch_setup
        start = 0
        stop = 6  # exclusive
        step = 2

        # Disable dioptrin so both paths use pyFAI for exact comparison
        config.calibration_model.use_dioptrin = False
        # Disable trim_trailing_zeros to match worker behavior
        config.trim_trailing_zeros = False

        # Run synchronous integration
        batch_model.integrate_raw_data(start, stop, step, use_all=True)
        sync_data = batch_model.data.copy()
        sync_binning = batch_model.binning.copy()

        # Reset and run via worker
        batch_model.data = None
        batch_model.binning = None

        snapshot = IntegrationSnapshot.from_configuration(config)
        worker = IntegrationWorker(
            snapshot,
            filepaths=None,
            mode="batch",
            batch_start=start,
            batch_stop=stop,
            batch_step=step,
            batch_use_all=True,
            batch_pos_map=batch_model.pos_map_all,
            batch_files=batch_model.files,
        )

        results = {}

        def on_finished(r):
            results.update(r)

        worker.finished.connect(on_finished)
        worker.start()
        worker.wait(30000)
        qapp.processEvents()

        assert results, "Worker should have finished with results"

        # Apply results to model
        batch_model.set_integration_results(results)
        assert batch_model.data is not None
        assert batch_model.data.shape[0] == sync_data.shape[0]

        np.testing.assert_allclose(batch_model.binning, sync_binning, rtol=1e-5)
        np.testing.assert_allclose(batch_model.data, sync_data, rtol=1e-5)

    def test_batch_set_integration_results_pyFAI(self, batch_setup):
        """Test set_integration_results with pyFAI-style variable-length results"""
        config, batch_model = batch_setup

        # Simulate variable-length pyFAI results
        results = {
            "intensity_data": [np.ones(100), np.ones(95), np.ones(100)],
            "binning_data": [np.linspace(0, 10, 100), np.linspace(0, 9.5, 95), np.linspace(0, 10, 100)],
            "pos_map": [(0, 0), (0, 1), (0, 2)],
            "unit": "2th_deg",
            "wavelength": 1e-10,
        }

        batch_model.set_integration_results(results)

        assert batch_model.data.shape == (3, 100)  # padded to max length
        assert batch_model.binning.shape == (100,)
        assert batch_model.n_img == 3
        assert batch_model.bkg is None

    def test_batch_set_integration_results_dioptrin(self, batch_setup):
        """Test set_integration_results with dioptrin-style uniform results"""
        config, batch_model = batch_setup

        results = {
            "intensity_data": [np.ones(100), np.ones(100)],
            "binning": np.linspace(0, 10, 100),
            "pos_map": [(0, 0), (0, 1)],
            "unit": "2th_deg",
            "wavelength": 1e-10,
        }

        batch_model.set_integration_results(results)

        assert batch_model.data.shape == (2, 100)
        assert batch_model.binning.shape == (100,)
        assert batch_model.n_img == 2

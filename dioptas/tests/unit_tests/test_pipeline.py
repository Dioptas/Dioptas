# SPDX-License-Identifier: MIT

import os
import numpy as np
import pytest

from dioptas.pipeline import Pipeline

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")

test_image = os.path.join(data_path, "CeO2_Pilatus1M.tif")
test_calibration = os.path.join(data_path, "CeO2_Pilatus1M.poni")
test_mask = os.path.join(data_path, "test.mask")


@pytest.fixture
def pipeline(qapp):
    return Pipeline()


@pytest.fixture
def calibrated_pipeline(pipeline):
    pipeline.load_calibration(test_calibration)
    return pipeline


class TestPipelineCreation:
    def test_create_empty_pipeline(self, pipeline):
        assert not pipeline.is_calibrated

    def test_load_calibration(self, pipeline):
        pipeline.load_calibration(test_calibration)
        assert pipeline.is_calibrated

    def test_default_integration_unit(self, pipeline):
        assert pipeline.integration_unit == "2th_deg"

    def test_default_use_mask(self, pipeline):
        assert pipeline.use_mask is False


class TestIntegration:
    def test_integrate_from_file(self, calibrated_pipeline):
        pattern = calibrated_pipeline.integrate(test_image)
        assert pattern is not None
        assert len(pattern.x) > 0
        assert len(pattern.y) > 0
        assert len(pattern.x) == len(pattern.y)

    def test_integrate_from_array(self, calibrated_pipeline):
        # Load an image as array first
        import fabio

        img_data = fabio.open(test_image).data
        pattern = calibrated_pipeline.integrate(img_data)
        assert len(pattern.x) > 0
        assert len(pattern.y) > 0

    def test_integrate_without_calibration_raises(self, pipeline):
        with pytest.raises(RuntimeError, match="No calibration loaded"):
            pipeline.integrate(test_image)

    def test_integrate_returns_pattern_with_name(self, calibrated_pipeline):
        pattern = calibrated_pipeline.integrate(test_image)
        assert "CeO2_Pilatus1M" in pattern.name

    def test_integrate_invalid_type_raises(self, calibrated_pipeline):
        with pytest.raises(TypeError):
            calibrated_pipeline.integrate(42)


class TestMask:
    def test_load_mask(self, calibrated_pipeline, tmp_path):
        calibrated_pipeline.integrate(test_image)  # load image first for dimensions
        # Create a mask file with matching dimensions
        shape = calibrated_pipeline.img_model._img_data.shape
        mask = np.zeros(shape, dtype=np.int8)
        mask[0:10, 0:10] = 1
        mask_file = str(tmp_path / "test.npy")
        np.save(mask_file, mask)
        calibrated_pipeline.load_mask(mask_file)
        assert calibrated_pipeline.use_mask is True

    def test_set_mask_from_array(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        mask = np.zeros(calibrated_pipeline.img_model._img_data.shape, dtype=bool)
        mask[0:10, 0:10] = True
        calibrated_pipeline.set_mask(mask)
        assert calibrated_pipeline.use_mask is True

    def test_toggle_use_mask(self, pipeline):
        pipeline.use_mask = True
        assert pipeline.use_mask is True
        pipeline.use_mask = False
        assert pipeline.use_mask is False


class TestIntegrationParameters:
    def test_set_integration_unit(self, pipeline):
        pipeline.integration_unit = "q_A^-1"
        assert pipeline.integration_unit == "q_A^-1"

    def test_set_num_points(self, pipeline):
        pipeline.integration_num_points = 1000
        assert pipeline.integration_num_points == 1000

    def test_set_azimuth_range(self, pipeline):
        pipeline.azimuth_range = (-10, 10)
        assert pipeline.azimuth_range == (-10, 10)

    def test_integrate_with_q_unit(self, calibrated_pipeline):
        calibrated_pipeline.integration_unit = "q_A^-1"
        pattern = calibrated_pipeline.integrate(test_image)
        assert len(pattern.x) > 0
        # q values should be in reasonable range for XRD
        assert pattern.x[0] > 0

    def test_integrate_with_num_points(self, calibrated_pipeline):
        calibrated_pipeline.integration_num_points = 500
        pattern = calibrated_pipeline.integrate(test_image)
        assert len(pattern.x) == 500


class TestBatchIntegration:
    def test_batch_from_list(self, calibrated_pipeline):
        patterns = calibrated_pipeline.integrate_batch(
            [test_image, test_image], progress=False
        )
        assert len(patterns) == 2
        assert all(len(p.x) > 0 for p in patterns)

    def test_batch_from_glob(self, calibrated_pipeline):
        glob_pattern = os.path.join(data_path, "CeO2_Pilatus1M.tif")
        patterns = calibrated_pipeline.integrate_batch(glob_pattern, progress=False)
        assert len(patterns) == 1

    def test_batch_empty_glob_raises(self, calibrated_pipeline):
        with pytest.raises(FileNotFoundError):
            calibrated_pipeline.integrate_batch(
                "/nonexistent/*.tif", progress=False
            )


class TestProjectLoading:
    def test_from_project(self, qapp, tmp_path):
        # Create a project file first
        from dioptas.model.DioptasModel import DioptasModel

        model = DioptasModel()
        model.calibration_model.load(test_calibration)
        model.img_model.load(test_image)

        project_file = str(tmp_path / "test.dio")
        model.save(project_file)

        # Load it via Pipeline
        p = Pipeline.from_project(project_file)
        assert p.is_calibrated

        # Should be able to integrate
        pattern = p.integrate(test_image)
        assert len(pattern.x) > 0

    def test_from_project_then_override_mask(self, qapp, tmp_path):
        from dioptas.model.DioptasModel import DioptasModel

        model = DioptasModel()
        model.calibration_model.load(test_calibration)
        model.img_model.load(test_image)

        project_file = str(tmp_path / "test.dio")
        model.save(project_file)

        p = Pipeline.from_project(project_file)

        # Override mask with a fresh one
        mask = np.zeros(p.img_model._img_data.shape, dtype=bool)
        mask[0:100, 0:100] = True
        p.set_mask(mask)
        assert p.use_mask is True

        pattern = p.integrate(test_image)
        assert len(pattern.x) > 0


class TestImageBackground:
    def test_load_image_background(self, calibrated_pipeline):
        # Use the same image as background for testing
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.load_image_background(test_image)
        assert calibrated_pipeline.img_model.has_background()

    def test_reset_image_background(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.load_image_background(test_image)
        calibrated_pipeline.reset_image_background()
        assert not calibrated_pipeline.img_model.has_background()

    def test_image_background_scaling(self, calibrated_pipeline):
        calibrated_pipeline.image_background_scaling = 0.5
        assert calibrated_pipeline.image_background_scaling == 0.5

    def test_image_background_offset(self, calibrated_pipeline):
        calibrated_pipeline.image_background_offset = 100
        assert calibrated_pipeline.image_background_offset == 100

    def test_integrate_with_image_background(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.load_image_background(test_image)
        calibrated_pipeline.image_background_scaling = 0.9
        pattern = calibrated_pipeline.integrate(test_image)
        assert len(pattern.x) > 0


class TestPatternBackground:
    def test_set_pattern_background_subtraction(self, calibrated_pipeline):
        # Integrate first so pattern model has data
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.set_pattern_background_subtraction()
        assert calibrated_pipeline.configuration.pattern_model.pattern.auto_bkg is not None

    def test_unset_pattern_background_subtraction(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.set_pattern_background_subtraction()
        calibrated_pipeline.unset_pattern_background_subtraction()
        assert calibrated_pipeline.configuration.pattern_model.pattern.auto_bkg is None

    def test_pattern_background_with_roi(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.set_pattern_background_subtraction(
            smoothing=100, iterations=30, poly_order=30, roi=(5, 30)
        )
        assert calibrated_pipeline.configuration.pattern_model.pattern.auto_bkg is not None


class TestCorrections:
    def test_add_cbn_correction_without_calibration_raises(self, pipeline):
        with pytest.raises(RuntimeError, match="Calibration must be loaded"):
            pipeline.add_cbn_correction()

    def test_add_oiadac_correction_without_calibration_raises(self, pipeline):
        with pytest.raises(RuntimeError, match="Calibration must be loaded"):
            pipeline.add_oiadac_correction()

    def test_clear_corrections(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)  # load image for shape
        calibrated_pipeline.add_cbn_correction()
        assert calibrated_pipeline.img_model.has_corrections()
        calibrated_pipeline.clear_corrections()
        assert not calibrated_pipeline.img_model.has_corrections()


class TestAdvancedAccess:
    def test_access_calibration_model(self, calibrated_pipeline):
        assert calibrated_pipeline.calibration_model is not None
        assert calibrated_pipeline.calibration_model.is_calibrated

    def test_access_mask_model(self, pipeline):
        assert pipeline.mask_model is not None

    def test_access_img_model(self, pipeline):
        assert pipeline.img_model is not None

    def test_access_configuration(self, pipeline):
        assert pipeline.configuration is not None

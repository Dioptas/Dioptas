# SPDX-License-Identifier: MIT

import os
import numpy as np
import pytest

from dioptas.model.util.ImgCorrection import CylinderAbsorptionCorrection

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")
test_image = os.path.join(data_path, "CeO2_Pilatus1M.tif")
test_calibration = os.path.join(data_path, "CeO2_Pilatus1M.poni")


class TestCylinderAbsorptionCorrectionPhysics:
    """Test the physics of the cylinder absorption correction."""

    def _make_tth_azi_arrays(self, shape=(50, 60)):
        tth = np.linspace(1, 30, shape[0])[:, np.newaxis] * np.ones(shape[1])
        azi = np.linspace(0, 360, shape[1])[np.newaxis, :] * np.ones((shape[0], 1))
        return tth, azi

    def test_correction_shape_matches_input(self):
        tth, azi = self._make_tth_azi_arrays((50, 60))
        corr = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.15, absorption_coefficient=3.0
        )
        corr.update()
        assert corr.shape() == (50, 60)

    def test_correction_values_between_0_and_1(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.15, absorption_coefficient=5.0
        )
        corr.update()
        data = corr.get_data()
        assert np.all(data > 0)
        assert np.all(data <= 1)

    def test_zero_radius_gives_unity(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.0, absorption_coefficient=5.0
        )
        corr.update()
        np.testing.assert_allclose(corr.get_data(), 1.0)

    def test_zero_absorption_gives_unity(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.15, absorption_coefficient=0.0
        )
        corr.update()
        np.testing.assert_allclose(corr.get_data(), 1.0)

    def test_higher_absorption_lower_transmission(self):
        tth, azi = self._make_tth_azi_arrays()
        corr_low = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.15, absorption_coefficient=1.0
        )
        corr_low.update()

        corr_high = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.15, absorption_coefficient=10.0
        )
        corr_high.update()

        # Higher absorption should give lower average transmission
        assert corr_high.get_data().mean() < corr_low.get_data().mean()

    def test_larger_radius_lower_transmission(self):
        tth, azi = self._make_tth_azi_arrays()
        corr_small = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.05, absorption_coefficient=3.0
        )
        corr_small.update()

        corr_large = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.5, absorption_coefficient=3.0
        )
        corr_large.update()

        assert corr_large.get_data().mean() < corr_small.get_data().mean()

    def test_correction_varies_with_tth(self):
        """The correction should vary with 2θ."""
        tth, azi = self._make_tth_azi_arrays()
        corr = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.15, absorption_coefficient=3.0
        )
        corr.update()
        data = corr.get_data()
        # Average over azimuth — should vary with 2θ
        avg = data.mean(axis=1)
        assert np.std(avg) > 1e-6

    def test_correction_varies_with_azimuth(self):
        """For a cylinder, the correction should vary with azimuth."""
        tth, azi = self._make_tth_azi_arrays()
        corr = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.15, absorption_coefficient=3.0
        )
        corr.update()
        data = corr.get_data()
        # At a given 2θ, values should vary with azimuth
        row = data[25]  # pick a row at ~15 degrees 2θ
        assert np.std(row) > 1e-6

    def test_get_set_params(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.2, absorption_coefficient=3.5
        )
        params = corr.get_params()
        assert params["radius"] == 0.2
        assert params["absorption_coefficient"] == 3.5

        corr2 = CylinderAbsorptionCorrection(tth_array=tth, azi_array=azi)
        corr2.set_params(params)
        corr2.update()
        corr.update()
        np.testing.assert_allclose(corr.get_data(), corr2.get_data())

    def test_numerical_integration_reference(self):
        """Verify against a brute-force numerical integration for one pixel."""
        R = 0.15
        mu = 3.0
        tth_deg = 15.0
        azi_deg = 45.0

        tth = np.array([[tth_deg]])
        azi = np.array([[azi_deg]])

        corr = CylinderAbsorptionCorrection(
            tth_array=tth, azi_array=azi,
            radius=R, absorption_coefficient=mu,
            n_cross_section=50,  # high resolution for reference
        )
        corr.update()

        # Brute-force reference with even finer grid
        n = 100
        g = np.linspace(-R, R, n)
        gx, gy = np.meshgrid(g, g)
        inside = gx**2 + gy**2 < R**2
        gx_in = gx[inside]
        gy_in = gy[inside]

        tth_rad = tth_deg * np.pi / 180
        azi_rad = azi_deg * np.pi / 180
        dx = np.cos(tth_rad)
        dy = np.cos(azi_rad) * np.sin(tth_rad)

        total = 0.0
        for i in range(len(gx_in)):
            x0, y0 = gx_in[i], gy_in[i]
            l_in = x0 + np.sqrt(R**2 - y0**2)

            a = dx**2 + dy**2
            b = x0 * dx + y0 * dy
            c = x0**2 + y0**2 - R**2
            disc = max(b**2 - a * c, 0)
            t_exit = (-b + np.sqrt(disc)) / max(a, 1e-30)

            total += np.exp(-mu * (l_in + t_exit))

        expected = total / len(gx_in)
        np.testing.assert_allclose(corr.get_data()[0, 0], expected, rtol=0.05)


class TestCylinderCorrectionInPipeline:
    """Test the cylinder correction through the Pipeline API."""

    @pytest.fixture
    def calibrated_pipeline(self, qapp):
        from dioptas.pipeline import Pipeline

        p = Pipeline()
        p.load_calibration(test_calibration)
        return p

    def test_add_cylinder_correction(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.add_cylinder_absorption_correction(
            formula="CeO2", density=7.22, radius=0.15
        )
        assert calibrated_pipeline.img_model.has_corrections()

    def test_cylinder_correction_affects_integration(self, calibrated_pipeline):
        pattern_no_corr = calibrated_pipeline.integrate(test_image)

        calibrated_pipeline.add_cylinder_absorption_correction(
            formula="CeO2", density=7.22, radius=0.15
        )
        pattern_with_corr = calibrated_pipeline.integrate(test_image)

        assert not np.allclose(pattern_no_corr.y, pattern_with_corr.y)

    def test_cylinder_correction_without_calibration_raises(self, qapp):
        from dioptas.pipeline import Pipeline

        p = Pipeline()
        with pytest.raises(RuntimeError, match="Calibration must be loaded"):
            p.add_cylinder_absorption_correction(formula="Au", radius=0.1)

    def test_clear_cylinder_correction(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.add_cylinder_absorption_correction(
            formula="CeO2", density=7.22, radius=0.15
        )
        assert calibrated_pipeline.img_model.has_corrections()
        calibrated_pipeline.clear_corrections()
        assert not calibrated_pipeline.img_model.has_corrections()

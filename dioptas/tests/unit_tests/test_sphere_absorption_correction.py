# SPDX-License-Identifier: MIT

import os
import numpy as np
import pytest

from dioptas.model.util.ImgCorrection import SphereAbsorptionCorrection

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")
test_image = os.path.join(data_path, "CeO2_Pilatus1M.tif")
test_calibration = os.path.join(data_path, "CeO2_Pilatus1M.poni")


class TestSphereAbsorptionCorrectionPhysics:

    def _make_tth_azi_arrays(self, shape=(50, 60)):
        tth = np.linspace(1, 30, shape[0])[:, np.newaxis] * np.ones(shape[1])
        azi = np.linspace(0, 360, shape[1])[np.newaxis, :] * np.ones((shape[0], 1))
        return tth, azi

    def test_correction_shape_matches_input(self):
        tth, azi = self._make_tth_azi_arrays((50, 60))
        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1, absorption_coefficient=3.0
        )
        corr.update()
        assert corr.shape() == (50, 60)

    def test_correction_values_between_0_and_1(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1, absorption_coefficient=5.0
        )
        corr.update()
        data = corr.get_data()
        assert np.all(data > 0)
        assert np.all(data <= 1)

    def test_zero_radius_gives_unity(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.0, absorption_coefficient=5.0
        )
        corr.update()
        np.testing.assert_allclose(corr.get_data(), 1.0)

    def test_zero_absorption_gives_unity(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1, absorption_coefficient=0.0
        )
        corr.update()
        np.testing.assert_allclose(corr.get_data(), 1.0)

    def test_higher_absorption_lower_transmission(self):
        tth, azi = self._make_tth_azi_arrays()
        corr_low = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1, absorption_coefficient=1.0
        )
        corr_low.update()

        corr_high = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1, absorption_coefficient=10.0
        )
        corr_high.update()

        assert corr_high.get_data().mean() < corr_low.get_data().mean()

    def test_larger_radius_lower_transmission(self):
        tth, azi = self._make_tth_azi_arrays()
        corr_small = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.02, absorption_coefficient=3.0
        )
        corr_small.update()

        corr_large = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.5, absorption_coefficient=3.0
        )
        corr_large.update()

        assert corr_large.get_data().mean() < corr_small.get_data().mean()

    def test_azimuthally_symmetric(self):
        """Sphere correction should be independent of azimuthal angle."""
        tth, azi = self._make_tth_azi_arrays()
        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1, absorption_coefficient=3.0
        )
        corr.update()
        data = corr.get_data()
        # Each row (same 2θ) should have identical values across azimuth
        for row in data:
            np.testing.assert_allclose(row, row[0], rtol=1e-5)

    def test_correction_varies_with_tth(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1, absorption_coefficient=3.0
        )
        corr.update()
        data = corr.get_data()
        avg = data.mean(axis=1)
        assert np.std(avg) > 1e-6

    def test_finite_beam_width(self):
        """Full illumination mode should give different results than pencil beam."""
        tth, azi = self._make_tth_azi_arrays()
        corr_pencil = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1,
            absorption_coefficient=3.0, beam_width=0,
        )
        corr_pencil.update()

        corr_full = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1,
            absorption_coefficient=3.0, beam_width=1.0,
        )
        corr_full.update()

        # Both should give valid corrections
        assert np.all(corr_full.get_data() > 0)
        assert np.all(corr_full.get_data() <= 1)
        # But they should differ
        assert not np.allclose(corr_pencil.get_data(), corr_full.get_data())

    def test_finite_beam_azimuthally_symmetric(self):
        """Full illumination mode should also be azimuthally symmetric."""
        tth, azi = self._make_tth_azi_arrays()
        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.1,
            absorption_coefficient=3.0, beam_width=1.0,
        )
        corr.update()
        data = corr.get_data()
        for row in data:
            np.testing.assert_allclose(row, row[0], rtol=1e-4)

    def test_get_set_params(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi, radius=0.2, absorption_coefficient=3.5
        )
        params = corr.get_params()
        assert params["radius"] == 0.2
        assert params["absorption_coefficient"] == 3.5

        corr2 = SphereAbsorptionCorrection(tth_array=tth, azi_array=azi)
        corr2.set_params(params)
        corr2.update()
        corr.update()
        np.testing.assert_allclose(corr.get_data(), corr2.get_data())

    def test_numerical_integration_reference(self):
        """Verify against scipy numerical integration along the beam path."""
        from scipy.integrate import quad

        R = 0.1
        mu = 3.0
        tth_deg = 15.0

        tth = np.array([[tth_deg]])
        azi = np.array([[0.0]])

        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi,
            radius=R, absorption_coefficient=mu, n_points=1000,
        )
        corr.update()

        # Reference: integrate along beam path through sphere center
        tth_rad = tth_deg * np.pi / 180
        cos2th = np.cos(tth_rad)
        sin2th2 = np.sin(tth_rad) ** 2

        def integrand(x):
            l_in = x + R
            l_out = -x * cos2th + np.sqrt(R**2 - x**2 * sin2th2)
            return np.exp(-mu * (l_in + l_out))

        expected, _ = quad(integrand, -R, R)
        expected /= 2 * R  # normalize by path length

        np.testing.assert_allclose(corr.get_data()[0, 0], expected, rtol=1e-4)


class TestSphereCorrectionInPipeline:

    @pytest.fixture
    def calibrated_pipeline(self, qapp):
        from dioptas.pipeline import Pipeline

        p = Pipeline()
        p.load_calibration(test_calibration)
        return p

    def test_add_sphere_correction(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.add_sphere_absorption_correction(
            formula="CeO2", density=7.22, radius=0.1
        )
        assert calibrated_pipeline.img_model.has_corrections()

    def test_sphere_correction_affects_integration(self, calibrated_pipeline):
        pattern_no_corr = calibrated_pipeline.integrate(test_image)

        calibrated_pipeline.add_sphere_absorption_correction(
            formula="CeO2", density=7.22, radius=0.1
        )
        pattern_with_corr = calibrated_pipeline.integrate(test_image)

        assert not np.allclose(pattern_no_corr.y, pattern_with_corr.y)

    def test_sphere_correction_without_calibration_raises(self, qapp):
        from dioptas.pipeline import Pipeline

        p = Pipeline()
        with pytest.raises(RuntimeError, match="Calibration must be loaded"):
            p.add_sphere_absorption_correction(formula="Au", radius=0.1)

    def test_clear_sphere_correction(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.add_sphere_absorption_correction(
            formula="CeO2", density=7.22, radius=0.1
        )
        assert calibrated_pipeline.img_model.has_corrections()
        calibrated_pipeline.clear_corrections()
        assert not calibrated_pipeline.img_model.has_corrections()

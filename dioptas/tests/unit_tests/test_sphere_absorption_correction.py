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
        """Verify against brute-force 3D integration for one 2θ value."""
        R = 0.1
        mu = 3.0
        tth_deg = 15.0

        tth = np.array([[tth_deg]])
        azi = np.array([[0.0]])

        corr = SphereAbsorptionCorrection(
            tth_array=tth, azi_array=azi,
            radius=R, absorption_coefficient=mu, n_grid=100,
        )
        corr.update()

        # Brute-force 3D grid reference
        n = 80
        g = np.linspace(-R * 0.999, R * 0.999, n)
        gx, gy, gz = np.meshgrid(g, g, g, indexing="ij")
        inside = gx**2 + gy**2 + gz**2 < R**2
        gx = gx[inside]
        gy = gy[inside]
        gz = gz[inside]

        tth_rad = tth_deg * np.pi / 180
        dx, dy, dz = np.cos(tth_rad), np.sin(tth_rad), 0.0

        total = 0.0
        for i in range(len(gx)):
            x0, y0, z0 = gx[i], gy[i], gz[i]
            l_in = x0 + np.sqrt(R**2 - y0**2 - z0**2)

            b = x0 * dx + y0 * dy + z0 * dz
            c = x0**2 + y0**2 + z0**2 - R**2
            t_exit = -b + np.sqrt(max(b**2 - c, 0))

            total += np.exp(-mu * (l_in + t_exit))

        expected = total / len(gx)
        np.testing.assert_allclose(corr.get_data()[0, 0], expected, rtol=0.05)


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

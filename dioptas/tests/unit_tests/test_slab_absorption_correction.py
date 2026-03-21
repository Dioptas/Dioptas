# SPDX-License-Identifier: MIT

import os
import numpy as np
import pytest

from dioptas.model.util.ImgCorrection import SlabAbsorptionCorrection
from dioptas.model.util.calc import wavelength_to_energy, energy_to_wavelength, calculate_mu

unittest_path = os.path.dirname(__file__)
data_path = os.path.join(unittest_path, "../data")
test_image = os.path.join(data_path, "CeO2_Pilatus1M.tif")
test_calibration = os.path.join(data_path, "CeO2_Pilatus1M.poni")


class TestSlabAbsorptionCorrectionPhysics:
    """Test the physics of the slab absorption correction."""

    def _make_tth_azi_arrays(self, shape=(100, 100)):
        """Create simple tth and azi arrays in degrees for testing."""
        tth = np.linspace(1, 30, shape[0])[:, np.newaxis] * np.ones(shape[1])
        azi = np.linspace(0, 360, shape[1])[np.newaxis, :] * np.ones((shape[0], 1))
        return tth, azi

    def test_correction_shape_matches_input(self):
        tth, azi = self._make_tth_azi_arrays((50, 60))
        corr = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi, thickness=0.1, absorption_coefficient=1.0
        )
        corr.update()
        assert corr.shape() == (50, 60)

    def test_correction_values_between_0_and_1(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi, thickness=0.1, absorption_coefficient=5.0
        )
        corr.update()
        data = corr.get_data()
        assert np.all(data > 0)
        assert np.all(data <= 1)

    def test_zero_thickness_gives_unity(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi, thickness=0.0, absorption_coefficient=5.0
        )
        corr.update()
        np.testing.assert_allclose(corr.get_data(), 1.0)

    def test_zero_absorption_gives_unity(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi, thickness=0.5, absorption_coefficient=0.0
        )
        corr.update()
        np.testing.assert_allclose(corr.get_data(), 1.0)

    def test_thickness_changes_correction(self):
        """Different thickness should give different correction values."""
        tth, azi = self._make_tth_azi_arrays()
        corr_thin = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi, thickness=0.05, absorption_coefficient=2.0
        )
        corr_thin.update()

        corr_thick = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi, thickness=0.5, absorption_coefficient=2.0
        )
        corr_thick.update()

        assert not np.allclose(corr_thick.get_data(), corr_thin.get_data())

    def test_higher_absorption_less_transmission(self):
        tth, azi = self._make_tth_azi_arrays()
        corr_low = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi, thickness=0.1, absorption_coefficient=1.0
        )
        corr_low.update()

        corr_high = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi, thickness=0.1, absorption_coefficient=10.0
        )
        corr_high.update()

        assert np.all(corr_high.get_data() < corr_low.get_data())

    def test_higher_tth_less_transmission_no_tilt(self):
        """At higher 2θ, the diffracted beam path through the slab is longer."""
        tth, azi = self._make_tth_azi_arrays()
        corr = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi, thickness=0.1, absorption_coefficient=3.0
        )
        corr.update()
        data = corr.get_data()
        # Average over azimuth: transmission should decrease with 2θ
        avg = data.mean(axis=1)
        # Check that transmission decreases (not necessarily monotonically due to
        # the combination of incident + diffracted paths)
        assert avg[0] > avg[-1]

    def test_perpendicular_slab_symmetric_in_azimuth(self):
        """A slab perpendicular to the beam (no tilt) should be azimuthally symmetric."""
        tth, azi = self._make_tth_azi_arrays()
        corr = SlabAbsorptionCorrection(
            tth_array=tth,
            azi_array=azi,
            thickness=0.1,
            absorption_coefficient=3.0,
            slab_tilt=0,
        )
        corr.update()
        data = corr.get_data()
        # All columns at same 2θ should have same value (azimuthal symmetry)
        for row in data:
            np.testing.assert_allclose(row, row[0], rtol=1e-10)

    def test_tilted_slab_breaks_azimuthal_symmetry(self):
        """A tilted slab should NOT be azimuthally symmetric."""
        tth, azi = self._make_tth_azi_arrays()
        corr = SlabAbsorptionCorrection(
            tth_array=tth,
            azi_array=azi,
            thickness=0.1,
            absorption_coefficient=3.0,
            slab_tilt=15,
        )
        corr.update()
        data = corr.get_data()
        # At a given 2θ, values should vary with azimuth
        row = data[50]  # pick a row at ~15 degrees 2θ
        assert np.std(row) > 1e-6

    def test_known_value_perpendicular_slab(self):
        """Check a specific known value for a perpendicular slab at low 2θ.

        At 2θ ≈ 0 with perpendicular slab, μ_i ≈ μ_d ≈ μ, so the
        transmission factor approaches t · exp(-μ·t) (the equal-path limit
        of the Busing & Levy integral).
        """
        tth = np.array([[0.1]])  # ~0 degrees
        azi = np.array([[0.0]])
        mu = 2.0  # 1/mm
        t = 0.1  # mm
        corr = SlabAbsorptionCorrection(
            tth_array=tth,
            azi_array=azi,
            thickness=t,
            absorption_coefficient=mu,
            slab_tilt=0,
        )
        corr.update()
        expected = t * np.exp(-mu * t)  # equal-path limit
        np.testing.assert_allclose(corr.get_data()[0, 0], expected, rtol=1e-3)

    def test_integral_vs_analytical_general_case(self):
        """Verify the general formula against numerical integration."""
        from scipy.integrate import quad

        tth = np.array([[20.0]])  # 20 degrees
        azi = np.array([[0.0]])
        mu = 3.0
        t = 0.2

        corr = SlabAbsorptionCorrection(
            tth_array=tth, azi_array=azi,
            thickness=t, absorption_coefficient=mu, slab_tilt=0,
        )
        corr.update()

        # Numerical integration for verification
        tth_rad = 20.0 * np.pi / 180.0
        cos_i = 1.0  # perpendicular slab, incident along normal
        cos_d = abs(np.cos(tth_rad))  # diffracted beam angle to normal
        mu_i = mu / cos_i
        mu_d = mu / cos_d

        def integrand(z):
            return np.exp(-mu_i * z) * np.exp(-mu_d * (t - z))

        expected, _ = quad(integrand, 0, t)
        np.testing.assert_allclose(corr.get_data()[0, 0], expected, rtol=1e-10)

    def test_get_set_params(self):
        tth, azi = self._make_tth_azi_arrays()
        corr = SlabAbsorptionCorrection(
            tth_array=tth,
            azi_array=azi,
            thickness=0.2,
            absorption_coefficient=3.5,
            slab_tilt=10,
            slab_rotation=45,
        )
        params = corr.get_params()
        assert params["thickness"] == 0.2
        assert params["absorption_coefficient"] == 3.5
        assert params["slab_tilt"] == 10
        assert params["slab_rotation"] == 45

        corr2 = SlabAbsorptionCorrection(tth_array=tth, azi_array=azi)
        corr2.set_params(params)
        corr2.update()
        corr.update()
        np.testing.assert_allclose(corr.get_data(), corr2.get_data())


class TestCalcUtilities:
    """Test the general-purpose calc utilities for energy/wavelength and mu."""

    def test_wavelength_to_energy(self):
        # 1 Angstrom ≈ 12398 eV
        energy = wavelength_to_energy(1e-10)
        assert abs(energy - 12398) < 5

    def test_wavelength_to_energy_calibration_value(self):
        # 0.3344 A ≈ 37077 eV (from test calibration)
        energy = wavelength_to_energy(0.3344e-10)
        assert abs(energy - 37077) < 10

    def test_energy_to_wavelength(self):
        # 12398 eV ≈ 1 Angstrom
        wavelength = energy_to_wavelength(12398)
        np.testing.assert_allclose(wavelength, 1e-10, rtol=1e-3)

    def test_roundtrip_wavelength_energy(self):
        wavelength = 0.3344e-10
        energy = wavelength_to_energy(wavelength)
        wavelength_back = energy_to_wavelength(energy)
        np.testing.assert_allclose(wavelength_back, wavelength, rtol=1e-12)

    def test_calculate_mu_known_material(self):
        mu = calculate_mu("CeO2", 40000, density=7.22)
        assert mu > 0
        assert 2.0 < mu < 5.0  # ~3.1 1/mm

    def test_calculate_mu_element(self):
        mu = calculate_mu("Au", 40000)
        assert mu > 0
        assert mu > 10  # gold is very absorbing

    def test_calculate_mu_higher_energy_less_absorption(self):
        mu_low = calculate_mu("Fe", 10000)
        mu_high = calculate_mu("Fe", 50000)
        assert mu_low > mu_high

    def test_calculate_mu_returns_per_mm(self):
        """calculate_mu should return values in 1/mm (not 1/cm)."""
        import xraydb
        mu_per_cm = xraydb.material_mu("Au", 40000)
        mu_per_mm = calculate_mu("Au", 40000)
        np.testing.assert_allclose(mu_per_mm, mu_per_cm / 10.0)


class TestSlabCorrectionInPipeline:
    """Test the slab correction through the Pipeline API."""

    @pytest.fixture
    def calibrated_pipeline(self, qapp):
        from dioptas.pipeline import Pipeline

        p = Pipeline()
        p.load_calibration(test_calibration)
        return p

    def test_add_slab_correction(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.add_slab_absorption_correction(
            formula="CeO2", density=7.22, thickness=0.1
        )
        assert calibrated_pipeline.img_model.has_corrections()

    def test_slab_correction_affects_integration(self, calibrated_pipeline):
        pattern_no_corr = calibrated_pipeline.integrate(test_image)

        calibrated_pipeline.add_slab_absorption_correction(
            formula="CeO2", density=7.22, thickness=0.5
        )
        pattern_with_corr = calibrated_pipeline.integrate(test_image)

        # Patterns should differ (correction divides by transmission < 1,
        # so corrected intensities should be higher)
        assert not np.allclose(pattern_no_corr.y, pattern_with_corr.y)

    def test_slab_correction_without_calibration_raises(self, qapp):
        from dioptas.pipeline import Pipeline

        p = Pipeline()
        with pytest.raises(RuntimeError, match="Calibration must be loaded"):
            p.add_slab_absorption_correction(formula="Au", thickness=0.1)

    def test_slab_correction_with_tilt(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.add_slab_absorption_correction(
            formula="Fe2O3", density=5.24, thickness=0.2, slab_tilt=10, slab_rotation=45
        )
        assert calibrated_pipeline.img_model.has_corrections()

    def test_clear_slab_correction(self, calibrated_pipeline):
        calibrated_pipeline.integrate(test_image)
        calibrated_pipeline.add_slab_absorption_correction(
            formula="CeO2", density=7.22, thickness=0.1
        )
        assert calibrated_pipeline.img_model.has_corrections()
        calibrated_pipeline.clear_corrections()
        assert not calibrated_pipeline.img_model.has_corrections()

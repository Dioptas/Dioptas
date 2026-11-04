# SPDX-License-Identifier: MIT
"""Display metadata for the installed Peritheos thermal constructors.

Units describe constructor values, without rescaling them. In particular the
multi-oscillator/DO2007 coefficients use 10^-6 K^-1, whereas Dewaele2006 uses
K^-1. Double-Debye a coefficients use inverse molar volume, not anharmonicity.
"""

# label, constructor unit (empty means dimensionless/configuration), explanation
FIELDS = {
    'Tr': ('Tᵣ', 'K', 'Reference temperature'),
    'theta0': ('θ₀', 'K', 'Characteristic temperature at the reference volume'),
    'theta': ('θ', 'K', 'Einstein characteristic temperature'),
    'gamma0': ('γ₀', '', 'Grüneisen parameter at the reference volume'),
    'gamma_inf': ('γ∞', '', 'Grüneisen parameter in the infinite-compression limit'),
    'q': ('q', '', 'Logarithmic volume derivative of the Grüneisen parameter'),
    'alpha0': ('α₀', 'K⁻¹', 'Volumetric thermal-expansion coefficient'),
    'alpha1': ('α₁', 'K⁻²', 'Temperature coefficient of thermal expansion'),
    'alpha_KT': ('αKₜ', 'GPa/K', 'Thermal-pressure coefficient'),
    'alpha_KT_ref': ('(αKₜ)ᵣ', 'GPa/K', 'Thermal-pressure coefficient at the reference state'),
    'dK_dT_V': ('(∂Kₜ/∂T)ᵥ', 'GPa/K', 'Temperature derivative of the isothermal bulk modulus at constant volume'),
    'dK_dT': ('∂K₀/∂T', 'GPa/K', 'Temperature derivative of the reference bulk modulus'),
    'dKprime_dT': ('∂K₀′/∂T', 'K⁻¹', 'Temperature derivative of the reference pressure derivative K₀′'),
    'kprime_log_coefficient': ('K₀′ log coeff.', 'K⁻¹', 'Coefficient of (T − Tᵣ) ln(T/Tᵣ) in K₀′'),
    'beta1': ('β₁', 'GPa⁻¹ K⁻¹', 'Linear-temperature coefficient in reciprocal bulk modulus'),
    'beta2': ('β₂', 'GPa⁻¹ K⁻²', 'Quadratic-temperature coefficient in reciprocal bulk modulus'),
    'beta3': ('β₃', 'GPa⁻¹ K⁻³', 'Cubic-temperature coefficient in reciprocal bulk modulus'),
    'Cvmax': ('Cᵥ,max', 'J mol⁻¹ K⁻¹', 'High-temperature molar heat-capacity limit at constant volume'),
    'delta': ('δ', '', 'Additive Grüneisen normalization constant'),
    't': ('t', '', 'Generalized Grüneisen parameter'),
    'a_0': ('a₀', '10⁻⁶ K⁻¹', 'Reference intrinsic-anharmonicity coefficient'),
    'e_0': ('e₀', '10⁻⁶ K⁻¹', 'Reference electronic coefficient'),
    'm': ('m', '', 'Volume exponent of the anharmonic or excess contribution'),
    'g': ('g', '', 'Volume exponent of the electronic contribution'),
    'beta': ('β', '', 'Volume-dependence coefficient'),
    'a': ('a', '', 'Amplitude of the Grüneisen volume dependence'),
    'b': ('b', '', 'Exponent of the Grüneisen volume dependence'),
    'Vp': ('Vₚ', 'J bar⁻¹ mol⁻¹', 'Reference molar volume for the characteristic-temperature laws'),
    'Ve': ('Vₑ', 'J bar⁻¹ mol⁻¹', 'Reference molar volume for the anharmonic term'),
    'kappa': ('κ', '', 'Volume exponent of the anharmonic coefficient'),
    'phi0': ('φ₀', 'J/mol', 'Cold reference energy per mole'),
    'anharmonic_a': ('a₀ (anh.)', 'K⁻¹', 'Reference anharmonic free-energy coefficient'),
    'anharmonic_m': ('m (anh.)', '', 'Volume exponent of the anharmonic coefficient'),
    'electronic_e': ('e₀ (el.)', 'K⁻¹', 'Reference electronic coefficient'),
    'electronic_g': ('g (el.)', '', 'Volume exponent of the electronic coefficient'),
    'defect_H': ('H (defect)', 'K', 'Defect enthalpy parameter expressed as a temperature (H/T in the exponent)'),
    'defect_S': ('S (defect)', '', 'Dimensionless defect entropy parameter'),
    'eta0': ('η₀', '', 'Reference compression, η = 1 − V/V₀'),
    'beta0': ('β₀', 'J mol⁻¹ K⁻²', 'Reference coefficient of the excess T² free-energy term'),
    'A': ('A', 'GPa/K²', 'Quadratic thermal-pressure coefficient'),
    'molar_mass_g_mol': ('M', 'g/mol', 'Formula-unit molar mass'),
    'longitudinal_intercept': ('vₗ intercept', 'km/s', 'Intercept of the longitudinal velocity–density relation'),
    'longitudinal_slope': ('∂vₗ/∂ρ', '(km/s)/(g/cm³)', 'Slope of the longitudinal velocity–density relation'),
    'shear_intercept': ('vₛ intercept', 'km/s', 'Intercept of the shear velocity–density relation'),
    'shear_slope': ('∂vₛ/∂ρ', '(km/s)/(g/cm³)', 'Slope of the shear velocity–density relation'),
    'thermal_expansion_law': ('Expansion law', '', 'Temperature dependence of thermal expansion'),
    'reference_volume_law': ('Reference volume law', '', 'Temperature dependence of the reference volume'),
    'bulk_modulus_law': ('Bulk modulus law', '', 'Temperature dependence of the reference bulk modulus'),
    'debye_temperature_law': ('Debye temperature law', '', 'Volume dependence of the Debye temperature'),
    'thermal_pressure_reference': ('Pressure reference', '', 'Reference state used for thermal pressure'),
    'zero_point_pressure': ('Zero-point pressure', '', 'Whether zero-point pressure is included'),
}

for key, suffix in [('QE1o', 'E₁,₀'), ('QE2o', 'E₂,₀'), ('QBo', 'B₀'), ('QB1o', 'B₁,₀')]:
    FIELDS[key] = (f'θ({suffix})', 'K', 'Reference oscillator characteristic temperature')
for key, symbol, suffix in [
    ('mE1', 'm', 'E₁'), ('mE2', 'm', 'E₂'), ('mb', 'm', 'B'),
    ('mb1', 'm', 'B₁'), ('d', 'd', 'B'), ('d1', 'd', 'B₁'),
]:
    FIELDS[key] = (f'{symbol}({suffix})', '',
                   'Oscillator multiplicity' if symbol == 'm' else 'Bose-mode dispersion parameter')
for suffix in ['B1', 'B2', 'E1', 'E2']:
    display = suffix.translate(str.maketrans('12', '₁₂'))
    for prefix, symbol, unit, explanation in [
        ('theta', 'θ', 'K', 'Reference oscillator characteristic temperature'),
        ('m', 'm', '', 'Oscillator multiplicity'),
        ('d', 'd', '', 'Bose-mode dispersion parameter'),
    ]:
        FIELDS[f'{prefix}_{suffix}'] = (f'{symbol}({display})', unit, explanation)
for index, unit in enumerate(['GPa', 'GPa', 'GPa/K', 'GPa', 'GPa/K²', 'GPa/K']):
    FIELDS[f'c{index}'] = (f'c{str(index).translate(str.maketrans("012345", "₀₁₂₃₄₅"))}',
                         unit, 'Second-order Taylor thermal-pressure coefficient')


def thermal_field_display(kind, name):
    """Return readable notation in the model's original coefficient convention."""
    if kind in ('DoubleDebyeHelmholtz', 'DoubleDebyeLogMomentHelmholtz'):
        for suffix, display in [('a', 'a'), ('b', 'b'), ('1', '1'), ('0', '0')]:
            if name == f'theta_{suffix}{"0" if suffix in ("a", "b") else "_0"}':
                return (f'θ({display},0)', 'K', 'Reference cutoff or phonon-moment temperature')
            if name == f'a_{suffix}':
                return (f'a({display})', 'bar mol/J', 'Inverse-volume coefficient in the characteristic-temperature law')
            if name == f'b_{suffix}':
                return (f'b({display})', '', 'Power-law coefficient in the characteristic-temperature law')
        if name == 'alpha0':
            return ('α₀ (anh.)', 'K⁻¹', 'Benedict anharmonic coefficient: Fₐₙₕ = −nRα(V)T²/2')
    label, unit, description = FIELDS.get(name, (name.replace('_', ' '), '', ''))
    if kind == 'DorogokupetsOganov2007' and name in ('anharmonic_a', 'electronic_e'):
        unit = '10⁻⁶ K⁻¹'
    if kind == 'MieGruneisenEinstein' and name == 'theta0':
        description = 'Einstein characteristic temperature at the reference volume'
    return label, unit, description

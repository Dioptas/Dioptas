# DAC thermal-pressure fraction

Settings → Phase contains **DAC thermal pressure** and **Fraction**. This is a
shared phase/session experiment setting for every detector configuration, including
new phases and individually assigned P/T values. It is never written into a
material/EoS record. The default is off with a retained fraction of 0.25.

The fraction is dimensionless, finite and in `[0, 1)`. The Qt-style control uses
a maximum of 0.9999 and 0.01 steps; the native boundary preserves any
valid imported fraction without rounding. Disabled retains the selected fraction.
With DAC enabled the input remains cold/reference **P₀** in GPa and T is the hot
temperature. With DAC off input **P** is the measured pressure. Switching the
setting changes phase positions, never the entered pressure or source EoS data.

For compatible canonical thermal models, native Peritheos solves
`P(V,T) = P₀ + fraction × ΔPthermal(V,T)`. The model owns the thermal-pressure
increment, reference temperature, model parameters, cell/molar conversion and
invertible branch. No additional thermal terms are constructed in Dioptas.
Fraction zero uses the ordinary constant-pressure thermal-volume path, exactly
as Qt does. Isothermal phases and legacy AlphaKT/JCPDS coefficient calculations
retain their Qt behavior and receive no invented DAC correction. Negative input
pressure follows Qt's existing legacy path; T=0 retains its 298 K interpretation.
Unsupported thermal models (including Maltby2024) fail for active nonzero DAC
fractions, rather than silently using ordinary hot-pressure volume predictions.

The validated fraction belongs to `Phases` in `phase_dac.rs`; all recalculations
receive its effective optional value. Global edits stage every phase before
publication. The session checkpoint provides rollback for condition, record,
reference, import and project failures. Shared phase state, configurations,
format-2 `.dio` projects, Undo/Redo and development checkpoints retain the factor.
Format-2 projects without these fields keep Qt's off/0.25 defaults. Invalid
fractions are rejected even when disabled. Formats 0/1 and EPICS are out of scope.

Project restoration also preserves omitted symmetry-implied lattice fields and
avoids copying canonical K0/K0-prime display mirrors into source legacy metadata.
This keeps native phase/project round trips exact without modifying published
records. Qt's floating RGB channels are accepted and truncated to native display
bytes in the same way as Qt's hex adapter.

## Verification

- `cargo test --locked --manifest-path backend/Cargo.toml phase_dac --lib -- --nocapture`:
  398 independent Qt PhaseModel states; 21 selected canonical records covering
  the bundled diffraction thermal families plus a legacy JCPDS phase. Factors
  0, 0.25, 0.4 and 0.75; on/off, multiple P/T conditions, cell dimensions and
  reflection spacings, source-document immutability, invalid/nonfinite values.
  Observed maximum relative difference: 5.53 × 10⁻¹³.
- `cargo test --locked --manifest-path backend/Cargo.toml --test integration -- dac_thermal_pressure::`:
  exact format-2 phase round trips; shared configuration state; linked and
  individual P/T; selected references; newly added phases; on/off retention;
  invalid and unsupported global rollback; development history transfer.
- `npm run test:dac-thermal-pressure`: real Rust stdio processing in headless
  Chromium/WebKit; Settings placement, readouts, changed volumes, factor editing,
  invalid control rollback and compact/large-text layouts.
- Explicit Python reference only: regenerate numerical fixtures with
  `../.venv/bin/python scripts/dac_thermal_pressure_reference.py` and run
  `npm run test:dac-project-reference` for actual Qt → native → Qt format-2
  interoperability with a nondefault factor and two configurations.

The reference uses Qt PhaseModel with Python Peritheos 0.17.0; production uses
native Rust Peritheos 0.18.0 at the repository's pinned revision. The numerical
fixture contains source equation parameters and a small reference peak table;
it qualifies thermal-volume behavior independently of structure intensities.
This is algorithm parity evidence, not a new validation of published EoS models.

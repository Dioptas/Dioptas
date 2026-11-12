# Phase Editor equation and parameter audit

Audited 2026-11-11 against **PeriTheos Rust 0.18.0**, commit
[`3c79b1aedf28c348a49cc22d9f24d92895546283`](https://github.com/CPrescher/peritheos/tree/3c79b1aedf28c348a49cc22d9f24d92895546283),
the dependency pinned by `backend/Cargo.toml` and `backend/Cargo.lock`.
The current online manual is supplementary documentation, not the authority for
what this pinned engine implements.

## Result and corrections

Reviewed the 11 editable isothermal families, 18 thermal metadata entries,
all 16 selectable law/reference choices, and 194 parameter/model combinations.
The implemented models' displayed equations agree with this revision after
these corrections:

- The legacy Dioptas correction inverts the **selected EoS**, with shifted K0
  and K0-prime where present. BM3 is the fallback when no EoS record exists.
  The 298 K anchor and separate zero/negative-pressure volume rules are retained.
- Dewaele's absolute-zero/included convention adds
  `P_ZP = 10^-4 (9 n R / 8 V) gamma Theta`. The equation now follows the
  stored zero-point convention. Reference-temperature Dewaele omits this term.
- Dewaele2006 and DorogokupetsOganov2007 require **beta > 0** in this engine.
  Removed the beta=0 limit from their displayed equations, and explained the
  restriction. The mathematically continuous limit is not an accepted input.
- Double-Debye help now states the actual coincident-temperature thresholds,
  limiting-weight formula, equal-gamma fallback (1/2), and zero weight derivative
  used by the engine in that branch.
- Clarified that DorogokupetsOganov2007 requires four positive multiplicities
  summing to 3n (tolerance 0.005). MultiOscillator/Sokolova permits zero weights.
- Clearing an optional numeric constructor coefficient now applies its
  advertised default explicitly. This fixes double-Debye n, Ve and energy-term
  defaults, which the Rust EOSMAT loader otherwise treats as missing parameters.
- SoundVelocityDebyeHelmholtz exists in the metadata, but has **no Rust model or
  factory implementation** in this revision. Its selection is disabled, direct
  selection is rejected with an explanation, and unverified equations are no
  longer displayed. No Python fallback was added.

## Source map

Paths below are relative to the pinned PeriTheos repository.

| Displayed family / explanation | Owning implementation |
| --- | --- |
| BM2, BM2Reference, BM3, BM4, Murnaghan | `crates/peritheos/src/isothermal.rs:13–255` |
| NaturalStrain2/3/4, ModifiedTait | `crates/peritheos/src/isothermal.rs:470–692` |
| Vinet, Holzapfel | `crates/peritheos/src/isothermal.rs:756–967` |
| K = -V dP/dV, reference K-prime and K-double-prime | `isothermal.rs` family implementations; `lib.rs:139–195` |
| MieGruneisenDebye/Einstein, Cvmax, q and temperature laws, pressure references | `crates/peritheos/src/thermal.rs:21–452` |
| DebyeQuadratic, HollandPowell, ThermalModifiedTait | `crates/peritheos/src/thermal.rs:455–753` |
| Linear, LogVolume, SecondOrderTaylor | `crates/peritheos/src/thermal.rs:755–943` |
| AlphaKT expansion, reference volume, reciprocal cubic K, linear/log K-prime | `crates/peritheos/src/thermal.rs:945–1167` |
| Tange/asymptotic-power-law Debye, b=0 limit | `crates/peritheos/src/thermal.rs:1169–1368` |
| Tange T-squared excess | `crates/peritheos/src/thermal.rs:3447–3500` |
| Dewaele: positive beta, quadratic coefficients, references, zero-point | `crates/peritheos/src/thermal.rs:1564–1824` |
| Arithmetic double-Debye, Vp/Ve, theta laws, weights, phi0, free energy and pressure | `crates/peritheos/src/thermal.rs:1843–2279` |
| Logarithmic double-Debye; volume-independent anharmonic free energy | `crates/peritheos/src/thermal.rs:2291–2678` |
| DorogokupetsOganov2007: mode multiplicities, micro-K coefficients, defects | `crates/peritheos/src/thermal.rs:2681–3076` |
| MultiOscillatorGruneisen / Sokolova2016 alias, generalized gamma, modes | `crates/peritheos/src/thermal.rs:3079–3435`; `eosmat.rs:3744–3790` |
| Cell/formula/molar conversion, explicit scale override | `crates/peritheos/src/eosmat.rs:47, 2764–2792, 3060–3080` |
| Optional/default values and constructor dispatch | `crates/peritheos/src/eosmat.rs:3338–3818`; Dioptas `backend/src/phase_workflow.rs` |
| Legacy correction and conversion of editor configuration strings | Dioptas `backend/src/phases.rs:170–213, 600–694` |

Parameter review includes pressure/temperature derivatives, atom count versus
crystallographic Z, effective electronic Z, formula-unit molar mass, oscillator
weights/dispersion, model-specific reuse of alpha/a/b/m, micro-K scaling,
phonon-law inverse-volume coefficients, defect H in kelvin and dimensionless S,
free-energy zeros, and optional-value semantics.

## Volume conventions and application boundaries

For energy-based thermal models, Rust converts public cell volumes in Å³ to
formula-unit molar J/bar/mol using `0.0602214076 / Zcell`, unless the record has an
explicit `volume.public_to_model_scale`. Energy is J/mol; pressure is GPa, hence
the factors 10^4 and 10^-4 in energy/pressure conversions. The displayed n is
atoms per the same formula unit. AlphaKT and the direct pressure polynomials
inherit their reference curve's volume basis.

**Holzapfel needs special care:** the fixed coefficient 1003.6 assumes molar
J/bar/mol. Rust does not automatically convert a standalone isothermal Holzapfel
record: without a molar thermal model or an explicit record volume scale, it
uses the supplied public volume unchanged. The help now states this requirement.
The audit verifies the Holzapfel formula at its specified molar basis; it does
not qualify an unscaled standalone Holzapfel record as physically normalized.
No existing records or scientific normalization were silently changed.

The displayed formulas describe the selected EoS. Dioptas separately applies
its legacy linear volume branch for negative pressure, and optional DAC
confinement when enabled. This audit does not change those application rules.

## Verification

`backend/tests/integration/phase_equation_audit.rs` evaluates independently transcribed
versions of the reviewed equations against the exact linked library:

- all 11 isothermal pressures at four volumes, K = -V dP/dV, reference K0,
  first derivatives, and the three adjustable second-derivative families;
- both MGD temperature laws, q=0/nonzero, all three pressure references,
  default and fitted Cvmax; Einstein energy;
- all five valid expansion/reference-volume combinations, both modulus laws,
  linear plus logarithmic K-prime shifts;
- linear/log/Taylor pressure, Holland–Powell and ThermalModifiedTait,
  Tange b=0/nonzero, T-squared excess and DebyeQuadratic;
- Dewaele reference/absolute/zero-point branches and beta=0 rejection;
- both double-Debye pressures via independent numerical derivatives of their
  displayed free energies, absolute and Tr-referenced, plus coincident weights;
- generalized multi-oscillator gamma/integral and all four oscillator terms;
- DO2007 quasiharmonic, anharmonic, electronic and defect pressure terms,
  including independent free-energy volume derivatives and beta=0 rejection;
- real editor default clearing and unsupported-model rejection;
- real legacy adapter with a Vinet reference and negative/zero/positive pressure;
- real EOSMAT cell-to-formula molar scaling and explicit scale override.

Independent Debye integrals use composite Simpson quadrature; free-energy
pressure checks use a five-point numerical derivative. Ordinary algebra checks
use tight relative tolerances; numerical quadrature/derivative thermal comparisons
use 2e-7 relative to max(1, pressure in GPa). The test also guards the audited
PeriTheos revision so a dependency update requires reviewing this qualification.
These reference expressions were compared to the authored LaTeX during the
source review; the test does not symbolically execute the LaTeX.

Validation commands:

```sh
MACOSX_DEPLOYMENT_TARGET=14.0 cargo test --locked --manifest-path backend/Cargo.toml --test integration -- phase_equation_audit::
npm run test:phase-model-help
npm run build
npm test
```

The 13 native tests pass. Headless Chromium and WebKit checks pass for all 194
parameter/model combinations and 16 choices, equation composition/MathML,
reference-law updates, the explanation toggle and numeric wheel behavior.
Production TypeScript/build and the 117 existing unit tests pass.

This establishes agreement with the pinned implementation at reviewed formulas
and sampled states. It is not a fresh literature validation, a guarantee at
all parameter/state combinations, or a statement that any fitted record is
scientifically appropriate for a particular material.

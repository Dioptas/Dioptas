# Attenuation-only XrayDB subset

`attenuation.bin` is a postcard-encoded `xraydb-data` 0.4.1 database containing
only version records, element properties, and Elam photoabsorption/scattering
splines. Named material definitions and the formula parser come from the Rust
library. The production dependency uses `default-features = false`: the full
3 MB compressed database and its zstd decoder are not embedded in the processor.
The supplied-data API loads this 329,526-byte subset once, without file access.

The isolated generation tool uses the full upstream database only during
explicit regeneration, preserving every retained floating-point bit:

```sh
cargo run --locked --manifest-path desktop/scripts/material_data/Cargo.toml -- desktop/backend/data
```

Review `attenuation.json`, the binary diff and independent material-reference
checks whenever regenerating/upgrading. Generation is not part of a normal
build and does not download or run Python. Data/license attribution is shipped
under `desktop/licenses/xraydb-data`; library code notices are generated from
Cargo metadata. Current numerical qualification includes compounds, fractional
stoichiometry, grouped formulas, named materials, an absorption edge, and
wavelength-dependent recalculation using the independent Python XrayDB oracle.

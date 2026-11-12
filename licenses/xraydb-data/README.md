# X-ray attenuation reference data

Data originate from Matt Newville and contributors' XrayDB project,
https://github.com/xraypy/XrayDB, released into the public domain under CC0-1.0.
The Elam attenuation tables reference W. T. Elam, B. D. Ravel and J. R. Sieber,
*A new atomic database for X-ray spectroscopic calculations*, Radiation Physics
and Chemistry 63 (2002), 121–128.

The application uses xraydb-rs 0.4.1
(https://github.com/Ameyanagi/xraydb-rs), whose code is MIT OR Apache-2.0,
with its full embedded-data feature disabled. The separately bundled table
subset retains element facts and Elam photoabsorption/coherent/incoherent
scattering splines for material attenuation. It omits Chantler, Waasmaier–Kirfel,
fluorescence, emission-line and other unused tables. All retained f64 data are
unchanged. It contains 118 element metadata rows and 98 rows in each Elam table.

The 329,526-byte subset has SHA-256
`a8e21d21474b777cddf89a542fc69d223f80aab5a5d6e19a0b381ca5ed3de1d1`.
Generation instructions and machine-readable provenance are in
`desktop/backend/data/README.md` and `attenuation.json` in the source tree.
No database or Python installation is needed at runtime.

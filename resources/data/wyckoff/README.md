# Wyckoff reference data

`positions.json` contains the 3,467 Wyckoff representatives for all 530 Hall
settings from Moyo 0.15.0, under its MIT license (included here). It records the
pinned upstream URLs and SHA-256 hashes. The historical generator
`desktop/scripts/generate_wyckoff_data.py` is preserved at source revision
`a39717a41458129ba9370c849a4121ecdbc6a444`; the native app uses this frozen table.

Source: https://github.com/spglib/moyo/tree/v0.15.0/moyo/src/data

Dioptas matches the declared Hall setting and PhaseSmith-expanded site orbit
against these affine representatives. No new space group is inferred from the
chemical composition. Labels are derived display annotations; source Wyckoff
metadata is preserved. Unknown settings/failed matches are explicitly unavailable.

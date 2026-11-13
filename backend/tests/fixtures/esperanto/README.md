# Independent Esperanto input

These two CC0-1.0 fixtures are copied unchanged from dioptrin-io commit
`8101935`, `tests/data/esperanto/`. That project's independent Python bit packer
generates the bytes from explicit signed32 source arrays and compares them with
the pinned FabIO AGI decoder. `provenance.json` retains the file and decoded-count
hashes, reference version, dimensions and source link.

Both files store the same rectangular 2×18 array, including signed32 extrema,
negative counts, AGI packed groups, escapes and tail pixels. Dioptas tests both
encodings under `.esperanto` and `.esper`, checking original integer samples and
the single row reversal used by the scientific/display view. Frozen gzip and
bzip2 copies of the AGI fixture additionally verify outer compression through
Dioptas; their compressed-file hashes are retained in the same manifest. These
copies use Python's standard-library gzip (mtime=0) and bzip2 encoders and inherit
the original CC0-1.0 terms. No Python is used by the tests or application.

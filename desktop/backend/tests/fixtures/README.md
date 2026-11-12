`combined-counts.h5` contains three 64×80 uint32 frames generated as
`120 + 11*row + 7*column + 83*frame`, with little-endian storage and independent
Bitshuffle/LZ4 direct chunks (filter 32008, parameters 0,4,4,2048,2; 2048-element
blocks). It is generated test input under the repository's MIT license. Rust
tests read the frozen file without Python or an external HDF5 plugin and cover
the admitted combined path across masks, units, errors, Batch/Map and projects.

`asymmetric.mask` is a generated 64×80 uint8 TIFF/Deflate Dioptas mask, with
only saved row/column (10,20) and (52,61) set to 1. Like Qt, mask loading
preserves these saved scientific coordinates rather than treating the mask
as a raw detector image. It is also MIT-licensed generated test input.

`reference-data/numerical.json` and its NPY inputs freeze independent pyFAI,
NumPy and legacy correction/LA Cosmic outputs, with the original source
revision/hashes, package versions, settings and tolerances. The active Rust
replay is `tests/frozen_references.rs`; no Python suite runs in this branch.
See `desktop/REFERENCE_DATA.md` for the scope and archived reproduction source.

`transport-frame.bslz4` is a frozen independent Bitshuffle/LZ4 encoding of a
384×448 uint16 frame, `100 + 2*column + 3*row`, in stored row order. Its header
contains the uncompressed byte count and a 4096-byte/2048-element block size.
SHA-256: `4906a75c3e01597d411f69a5a6f33ad5ac2cf2c0dad98942aa08a359944165b6`.
The native `test_fixtures` example repeats this chunk for transport tests and
creates other synthetic input arrays; it does not generate expected results.

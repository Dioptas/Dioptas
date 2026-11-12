# HDF5 external-file offset ABI

The published `hdf5-metno-sys` 0.12.5 and `hdf5-metno` 0.15.1 crates
are retained here with their original licenses and complete source archives.
`HDF5_WINDOWS_ABI.json` records their registry URLs, archive checksums, all
original file hashes and the four modified file hashes. The verifier at
`../scripts/check_hdf5_windows_abi.mjs` checks the complete inventory offline.

HDF5 2.x declares external-file offsets as `HDoff_t`, which is `int64_t` on
Windows. The original bindings used `libc::off_t`, a 32-bit Windows type.
`H5Pget_external` consequently wrote eight bytes into a four-byte Rust slot.
Both the low-level signatures and the high-level offset variable now use
the matching type. Non-Windows platforms and HDF5 1.x retain `libc::off_t`.

Header references:

- https://github.com/HDFGroup/hdf5/blob/hdf5_2.0.0/src/H5public.h
- https://github.com/HDFGroup/hdf5/blob/hdf5_2.0.0/src/H5Ppublic.h

The backend lockfile resolves both crates through these local patches.
`hdf5_external_offsets.rs` checks an offset above 4 GiB without allocating a
large payload; the master/VDS tests exercise actual external raw-file reads.
This is a local compatibility correction, not an upstream release or advisory.

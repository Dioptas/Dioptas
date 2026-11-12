//! HDF5 2.x uses 64-bit HDoff_t on Windows, where libc::off_t is only 32-bit.
#[test]
fn external_raw_offsets_above_four_gib_round_trip_without_truncation() {
    let directory = tempfile::tempdir().unwrap();
    let file = hdf5::File::create(directory.path().join("large-offset.h5")).unwrap();
    let offset = (1_usize << 33) + 7;
    let dataset = file
        .new_dataset::<u16>()
        .shape([1])
        .external("raw-detector.bin", offset, 2)
        .create("counts")
        .unwrap();
    // Only metadata is written: this test does not allocate an 8 GiB data file.
    let properties = dataset.create_plist().unwrap();
    let external = properties.get_external().unwrap();
    assert_eq!(external.len(), 1);
    assert_eq!(external[0].name, "raw-detector.bin");
    assert_eq!(external[0].offset, offset);
    assert_eq!(external[0].size, 2);
    assert!(!directory.path().join("raw-detector.bin").exists());
}

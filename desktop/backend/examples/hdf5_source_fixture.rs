//! Small real HDF5 fixture for the headless source-selector workflow.
fn main() {
    let path = std::env::args().nth(1).expect("output HDF5 path");
    let f = hdf5::File::create(path).unwrap();
    for (name, n, h, w, base) in [
        ("a", 4, 24, 32, 10),
        ("b", 2, 24, 32, 30),
        ("c", 3, 16, 20, 50),
    ] {
        let values: Vec<u16> = (0..n).flat_map(|i| vec![base + i as u16; h * w]).collect();
        f.new_dataset::<u16>()
            .shape((n, h, w))
            .create(name)
            .unwrap()
            .write_raw(&values)
            .unwrap();
    }
    f.new_dataset::<u64>()
        .shape((2, 24, 32))
        .create("bad")
        .unwrap()
        .write_raw(&vec![(1u64 << 53) + 1; 2 * 24 * 32])
        .unwrap();
}

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
    // Realistic, ambiguous dataset suffixes and a long stack for navigation UI QA.
    for (entry, frames, base) in [("entry_0000", 625, 10), ("entry_0001", 2, 30)] {
        let group = f
            .create_group(entry)
            .unwrap()
            .create_group("measurement")
            .unwrap();
        let values: Vec<u16> = (0..frames)
            .flat_map(|i| vec![base + i as u16; 24 * 32])
            .collect();
        group
            .new_dataset::<u16>()
            .shape((frames, 24, 32))
            .create("data")
            .unwrap()
            .write_raw(&values)
            .unwrap();
    }
    f.new_dataset::<u16>()
        .shape((24, 32))
        .create("plane")
        .unwrap()
        .write_raw(&vec![70; 24 * 32])
        .unwrap();
    if let Some(directory) = std::env::args().nth(2) {
        let directory = std::path::Path::new(&directory);
        let single = hdf5::File::create(directory.join("single-source.h5")).unwrap();
        single
            .new_dataset::<u16>()
            .shape((3, 24, 32))
            .create("data")
            .unwrap()
            .write_raw(&vec![25; 3 * 24 * 32])
            .unwrap();
        for (name, frames) in [("single-image.tif", 1), ("image-stack.tif", 3)] {
            let file = std::fs::File::create(directory.join(name)).unwrap();
            let mut encoder = tiff::encoder::TiffEncoder::new(file).unwrap();
            for frame in 0..frames {
                encoder
                    .new_image::<tiff::encoder::colortype::Gray16>(32, 24)
                    .unwrap()
                    .write_data(&vec![10 + frame; 24 * 32])
                    .unwrap();
            }
        }
    }
}

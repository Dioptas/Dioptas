//! Generated qualification inputs, not acquired beamline data.
use std::path::Path;
pub fn generate(directory: &Path) {
    std::fs::create_dir_all(directory.join("parts")).unwrap();
    for (name, base) in [("a.h5", 10u16), ("b.h5", 30)] {
        let f = hdf5::File::create(directory.join("parts").join(name)).unwrap();
        let values: Vec<u16> = (0..2)
            .flat_map(|frame| vec![base + frame; 24 * 32])
            .collect();
        f.new_dataset::<u16>()
            .shape((2, 24, 32))
            .create("images")
            .unwrap()
            .write_raw(&values)
            .unwrap();
        f.new_dataset::<u16>()
            .shape((2, 24, 32))
            .create("ramp")
            .unwrap()
            .write_raw(&(0..2 * 24 * 32).map(|i| i as u16).collect::<Vec<_>>())
            .unwrap();
    }
    let eiger = hdf5::File::create(directory.join("eiger-master.h5")).unwrap();
    eiger.create_group("entry/data").unwrap();
    for (number, name) in [(1, "a.h5"), (2, "b.h5")] {
        eiger
            .link_external(
                &format!("parts/{name}"),
                "/images",
                &format!("/entry/data/data_{number:06}"),
            )
            .unwrap();
    }
    eiger
        .link_soft("/entry/data/data_000002", "/alias")
        .unwrap();
    for (file, absolute) in [
        ("virtual.h5", false),
        ("relocated.h5", true),
        ("overlap.h5", false),
    ] {
        let f = hdf5::File::create(directory.join(file)).unwrap();
        let a = if absolute {
            "/missing/acquisition/a.h5"
        } else {
            "parts/a.h5"
        };
        let b = if absolute {
            "/missing/acquisition/b.h5"
        } else {
            "parts/b.h5"
        };
        let end = if file == "overlap.h5" { 0..2 } else { 2..4 };
        f.new_dataset::<u16>()
            .shape((4, 24, 32))
            .virtual_map(
                a,
                "/images",
                (2, 24, 32),
                (.., .., ..),
                (4, 24, 32),
                (0..2, .., ..),
            )
            .virtual_map(
                b,
                "/images",
                (2, 24, 32),
                (.., .., ..),
                (4, 24, 32),
                (end, .., ..),
            )
            .create("data")
            .unwrap();
    }
    let nested = hdf5::File::create(directory.join("nested.h5")).unwrap();
    nested
        .new_dataset::<u16>()
        .shape((4, 24, 32))
        .virtual_map(
            "virtual.h5",
            "/data",
            (4, 24, 32),
            (.., .., ..),
            (4, 24, 32),
            (.., .., ..),
        )
        .create("data")
        .unwrap();
    let mixed = hdf5::File::create(directory.join("mixed.h5")).unwrap();
    mixed
        .new_dataset::<u16>()
        .shape((2, 24, 32))
        .create("ordinary")
        .unwrap()
        .write_raw(&vec![7; 2 * 24 * 32])
        .unwrap();
    mixed
        .new_dataset::<u16>()
        .shape((4, 24, 32))
        .virtual_map(
            "relocated.h5",
            "/data",
            (4, 24, 32),
            (.., .., ..),
            (4, 24, 32),
            (.., .., ..),
        )
        .create("virtual")
        .unwrap();
    let ramp = hdf5::File::create(directory.join("ramp.h5")).unwrap();
    ramp.new_dataset::<u16>()
        .shape((2, 24, 32))
        .virtual_map(
            "parts/a.h5",
            "/ramp",
            (2, 24, 32),
            (.., .., ..),
            (2, 24, 32),
            (.., .., ..),
        )
        .create("data")
        .unwrap();
    let cycle = hdf5::File::create(directory.join("cycle.h5")).unwrap();
    cycle
        .new_dataset::<u16>()
        .shape((2, 24, 32))
        .virtual_map(
            ".",
            "/data",
            (2, 24, 32),
            (.., .., ..),
            (2, 24, 32),
            (.., .., ..),
        )
        .create("data")
        .unwrap();
    let raw = hdf5::File::create(directory.join("raw.h5")).unwrap();
    let values: Vec<u8> = (0..2u16)
        .flat_map(|f| std::iter::repeat_n(50 + f, 24 * 32))
        .flat_map(|v| v.to_le_bytes())
        .collect();
    let split = 109;
    std::fs::write(
        directory.join("counts-a.bin"),
        [&[9, 8, 7, 6][..], &values[..split]].concat(),
    )
    .unwrap();
    std::fs::write(
        directory.join("counts-b.bin"),
        [&[3, 2][..], &values[split..], &[1, 0][..]].concat(),
    )
    .unwrap();
    raw.new_dataset::<u16>()
        .shape((2, 24, 32))
        .external("counts-a.bin", 4, split)
        .external("counts-b.bin", 2, values.len() - split)
        .create("data")
        .unwrap();
}
pub fn compressed(source: &Path, destination: &Path) {
    use std::io::Write;
    let file = std::fs::File::create(destination).unwrap();
    let mut encoder = flate2::write::GzEncoder::new(file, flate2::Compression::fast());
    encoder.write_all(&std::fs::read(source).unwrap()).unwrap();
    encoder.finish().unwrap();
}

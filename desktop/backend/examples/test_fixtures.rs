//! Native input generator for headless transport tests, never linked into the app.
use hdf5_sys::{
    h5d::{H5Dclose, H5Dcreate2, H5Dwrite_chunk},
    h5p::{H5P_DEFAULT, H5Pset_filter},
};
use std::{env, fs, path::Path};

fn npy(path: &Path, shape: [usize; 2], values: impl Iterator<Item = f64>) {
    let mut header = format!(
        "{{'descr': '<f8', 'fortran_order': False, 'shape': ({}, {}), }}",
        shape[0], shape[1]
    );
    while (10 + header.len() + 1) % 64 != 0 {
        header.push(' ');
    }
    header.push('\n');
    let mut bytes = b"\x93NUMPY\x01\x00".to_vec();
    bytes.extend_from_slice(&(header.len() as u16).to_le_bytes());
    bytes.extend_from_slice(header.as_bytes());
    for value in values {
        bytes.extend_from_slice(&value.to_le_bytes());
    }
    fs::write(path, bytes).unwrap();
}
fn main() {
    // No threads exist yet. Avoid loading external codec plugins into this test process.
    unsafe {
        env::set_var("HDF5_PLUGIN_PRELOAD", "::");
    }
    let args: Vec<_> = env::args().skip(1).collect();
    assert!(
        args.len() >= 2,
        "Use test_fixtures project|navigation|series PATH [gzip|bitshuffle-lz4] [frames]"
    );
    let path = Path::new(&args[1]);
    if args[0] == "project" {
        npy(
            path,
            [1024, 1024],
            (0..1024 * 1024).map(|i| (100 + i % 1024 * 2 + i / 1024 * 3) as f64),
        );
        return;
    }
    let file = hdf5::File::create(path).unwrap();
    if args[0] == "navigation" {
        file.new_dataset::<u16>()
            .shape([3, 64, 64])
            .create("entry/data/data")
            .unwrap()
            .write_raw(&(0..3 * 64 * 64).map(|i| i as u16).collect::<Vec<_>>())
            .unwrap();
        return;
    }
    assert_eq!(args[0], "series");
    let compression = args.get(2).map(String::as_str).unwrap_or("bitshuffle-lz4");
    let frames: usize = args.get(3).map(|v| v.parse().unwrap()).unwrap_or(512);
    if compression == "gzip" {
        let values: Vec<u16> = (0..frames * 384 * 448)
            .map(|i| (100 + i % 448 * 2 + i / 448 % 384 * 3 + i / (384 * 448)) as u16)
            .collect();
        file.new_dataset::<u16>()
            .shape([frames, 384, 448])
            .chunk([1, 384, 448])
            .deflate(1)
            .create("frames")
            .unwrap()
            .write_raw(&values)
            .unwrap();
    } else {
        assert_eq!(compression, "bitshuffle-lz4");
        // Repeat a frozen independently encoded chunk without an HDF5 filter plugin.
        // The processor's own Bitshuffle/LZ4 decoder still reads every frame.
        let chunk = include_bytes!("../tests/fixtures/transport-frame.bslz4");
        let space = hdf5::Dataspace::try_new([frames, 384, 448]).unwrap();
        let dtype = hdf5::Datatype::from_type::<u16>().unwrap();
        let plist = hdf5::plist::DatasetCreate::build()
            .chunk([1, 384, 448])
            .finish()
            .unwrap();
        let filter = [0_u32, 4, 2, 2048, 2];
        hdf5::sync::sync(|| unsafe {
            assert!(H5Pset_filter(plist.id(), 32008, 1, filter.len(), filter.as_ptr()) >= 0);
            let dataset = H5Dcreate2(
                file.id(),
                c"frames".as_ptr(),
                dtype.id(),
                space.id(),
                H5P_DEFAULT,
                plist.id(),
                H5P_DEFAULT,
            );
            assert!(dataset >= 0);
            for frame in 0..frames {
                let offset = [frame as u64, 0, 0];
                assert!(
                    H5Dwrite_chunk(
                        dataset,
                        H5P_DEFAULT,
                        0,
                        offset.as_ptr(),
                        chunk.len(),
                        chunk.as_ptr().cast()
                    ) >= 0
                );
            }
            assert!(H5Dclose(dataset) >= 0);
        });
    }
    npy(
        &path.with_file_name(format!(
            "{}.background.npy",
            path.file_name().unwrap().to_string_lossy()
        )),
        [384, 448],
        (0..384 * 448).map(|_| 7.),
    );
    npy(
        &path.with_file_name(format!(
            "{}.flat.npy",
            path.file_name().unwrap().to_string_lossy()
        )),
        [384, 448],
        (0..384 * 448).map(|i| 0.8 + (i % 448) as f64 * 0.4 / 447.),
    );
}

use std::ffi::CString;
use std::path::Path;

#[path = "../tests/common/hdf5_master_fixtures.rs"]
mod fixtures;

/// Generate a minimal printf-template VDS fixture (`printf/files-bool.h5` backed
/// by `files-bool-0.h5` and `files-bool-1.h5`) directly via HDF5 so UI checks
/// never invoke `cargo metadata` on uncached CI runners.
fn generate_printf(directory: &Path) {
    let printf_dir = directory.join("printf");
    std::fs::create_dir_all(&printf_dir).unwrap();
    let frame: [u8; 6] = [0x00, 0x01, 0x02, 0x7f, 0x80, 0xff];
    let block: Vec<u8> = frame.iter().copied().chain(frame.iter().copied()).collect();
    for index in 0..2 {
        let source = hdf5::File::create(printf_dir.join(format!("files-bool-{index}.h5"))).unwrap();
        source
            .new_dataset::<u8>()
            .shape((2, 2, 3))
            .create("data")
            .unwrap()
            .write_raw(&block)
            .unwrap();
    }

    let master_path = CString::new(
        printf_dir
            .join("files-bool.h5")
            .to_str()
            .expect("UTF-8 fixture path"),
    )
    .unwrap();
    let dataset_name = CString::new("/data").unwrap();
    let template = CString::new("files-bool-%b.h5").unwrap();

    unsafe {
        let file_id = hdf5_sys::h5f::H5Fcreate(
            master_path.as_ptr(),
            hdf5_sys::h5f::H5F_ACC_TRUNC,
            hdf5_sys::h5p::H5P_DEFAULT,
            hdf5_sys::h5p::H5P_DEFAULT,
        );
        assert!(file_id >= 0, "H5Fcreate failed");

        let cur_dims: [hdf5_sys::h5::hsize_t; 3] = [0, 2, 3];
        let max_dims: [hdf5_sys::h5::hsize_t; 3] = [hdf5_sys::h5s::H5S_UNLIMITED, 2, 3];
        let vspace = hdf5_sys::h5s::H5Screate_simple(3, cur_dims.as_ptr(), max_dims.as_ptr());
        assert!(vspace >= 0, "H5Screate_simple (virtual) failed");

        let start: [hdf5_sys::h5::hsize_t; 3] = [0, 0, 0];
        let stride: [hdf5_sys::h5::hsize_t; 3] = [2, 1, 1];
        let count: [hdf5_sys::h5::hsize_t; 3] = [hdf5_sys::h5s::H5S_UNLIMITED, 1, 1];
        let block_dims: [hdf5_sys::h5::hsize_t; 3] = [2, 2, 3];
        assert!(
            hdf5_sys::h5s::H5Sselect_hyperslab(
                vspace,
                hdf5_sys::h5s::H5S_seloper_t::H5S_SELECT_SET,
                start.as_ptr(),
                stride.as_ptr(),
                count.as_ptr(),
                block_dims.as_ptr(),
            ) >= 0,
            "H5Sselect_hyperslab failed"
        );

        let src_dims: [hdf5_sys::h5::hsize_t; 3] = [2, 2, 3];
        let src_space = hdf5_sys::h5s::H5Screate_simple(3, src_dims.as_ptr(), std::ptr::null());
        assert!(src_space >= 0, "H5Screate_simple (source) failed");
        assert!(
            hdf5_sys::h5s::H5Sselect_all(src_space) >= 0,
            "H5Sselect_all failed"
        );

        let dcpl = hdf5_sys::h5p::H5Pcreate(*hdf5_sys::h5p::H5P_CLS_DATASET_CREATE);
        assert!(dcpl >= 0, "H5Pcreate failed");
        assert!(
            hdf5_sys::h5p::H5Pset_virtual(
                dcpl,
                vspace,
                template.as_ptr(),
                dataset_name.as_ptr(),
                src_space,
            ) >= 0,
            "H5Pset_virtual failed"
        );

        let dset = hdf5_sys::h5d::H5Dcreate2(
            file_id,
            dataset_name.as_ptr(),
            *hdf5_sys::h5t::H5T_STD_U8LE,
            vspace,
            hdf5_sys::h5p::H5P_DEFAULT,
            dcpl,
            hdf5_sys::h5p::H5P_DEFAULT,
        );
        assert!(dset >= 0, "H5Dcreate2 failed");

        assert!(hdf5_sys::h5d::H5Dclose(dset) >= 0);
        assert!(hdf5_sys::h5p::H5Pclose(dcpl) >= 0);
        assert!(hdf5_sys::h5s::H5Sclose(src_space) >= 0);
        assert!(hdf5_sys::h5s::H5Sclose(vspace) >= 0);
        assert!(hdf5_sys::h5f::H5Fclose(file_id) >= 0);
    }
}

fn main() {
    let directory = std::path::PathBuf::from(std::env::args().nth(1).expect("output directory"));
    fixtures::generate(&directory);
    fixtures::compressed(
        &directory.join("virtual.h5"),
        &directory.join("virtual.h5.gz"),
    );
    generate_printf(&directory);
}

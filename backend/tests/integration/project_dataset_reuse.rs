//! Public save/open regressions: shared storage must preserve every f64 value.
#![cfg(feature = "dioptrin")]
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{
    path::{Path, PathBuf},
    str::FromStr,
};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn fixture(path: &Path, offset: f64) -> Vec<f64> {
    let file = hdf5::File::create(path).unwrap();
    let result = file.create_group("processed/result").unwrap();
    let data: Vec<_> = (0..256)
        .map(|i| 100. + (i / 64) as f64 * 7. + (i % 64) as f64 * 0.13 + offset)
        .collect();
    for (name, values) in [
        ("data", data.clone()),
        (
            "counting_std",
            (0..256).map(|i| 1. + i as f64 * 0.017).collect(),
        ),
        (
            "azimuthal_std",
            (0..256).map(|i| 3. + i as f64 * 0.031).collect(),
        ),
    ] {
        result
            .new_dataset::<f64>()
            .shape([4, 64])
            .create(name)
            .unwrap()
            .write_raw(&values)
            .unwrap();
    }
    let x: Vec<_> = (1..=64).map(|i| i as f64).collect();
    let axis = result
        .new_dataset_builder()
        .with_data(&x)
        .create("binning")
        .unwrap();
    let unit = hdf5::types::VarLenUnicode::from_str("2th_deg").unwrap();
    axis.new_attr::<hdf5::types::VarLenUnicode>()
        .shape(())
        .create("radial_unit")
        .unwrap()
        .write_scalar(&unit)
        .unwrap();
    result
        .new_attr::<f64>()
        .shape(())
        .create("desktop_wavelength_m")
        .unwrap()
        .write_scalar(&5e-11)
        .unwrap();
    let process = file.create_group("processed/process").unwrap();
    let background: Vec<_> = (0..256).map(|i| 5. + i as f64 * 0.007).collect();
    process
        .new_dataset::<f64>()
        .shape([4, 64])
        .create("bkg")
        .unwrap()
        .write_raw(&background)
        .unwrap();
    data
}
fn bits(file: &hdf5::File, path: &str) -> Vec<u64> {
    file.dataset(path)
        .unwrap()
        .read_raw::<f64>()
        .unwrap()
        .into_iter()
        .map(f64::to_bits)
        .collect()
}
fn aliases(file: &hdf5::File, a: &str, b: &str) {
    let a = file.dataset(a).unwrap();
    let b = file.dataset(b).unwrap();
    assert_eq!(a.shape(), b.shape());
    assert!(a.dtype().unwrap().is::<f64>() && b.dtype().unwrap().is::<f64>());
    assert_eq!(
        format!("{:?}", a.loc_info().unwrap().token),
        format!("{:?}", b.loc_info().unwrap().token),
        "{} and {} must share a dataset",
        a.name(),
        b.name()
    );
}
fn shared_batch(file: &hdf5::File, index: usize) {
    let prefix = format!("configurations/{index}/native_batch");
    for (native, compat) in [
        ("result/data", "data"),
        ("result/binning", "binning"),
        ("result/counting_std", "counting_std"),
        ("result/azimuthal_std", "azimuthal_std"),
        ("process/bkg", "bkg"),
        ("result/desktop_original", "normalization_source/data"),
        (
            "result/desktop_original_counting_std",
            "normalization_source/counting_std",
        ),
        (
            "result/desktop_original_spread",
            "normalization_source/spread",
        ),
        (
            "result/desktop_original_background",
            "normalization_source/background",
        ),
    ] {
        aliases(
            file,
            &format!("{prefix}/{native}"),
            &format!("react_desktop_batch/{compat}"),
        );
    }
}
fn normalized(s: &mut Session, input: &Path, both: bool) {
    call(s, "batch_open", json!({"path":input}));
    call(
        s,
        "batch_normalize",
        json!({"enabled":true,"start":4,"stop":45,"reference":2}),
    );
    if both {
        call(s, "map_batch", json!({"path":input}));
        call(s, "map_grid", json!({"rows":2,"columns":2,"snake":true}));
        call(
            s,
            "map_normalize",
            json!({"enabled":true,"start":4,"stop":45,"reference":2}),
        );
    }
}
#[test]
fn native_and_compatibility_arrays_share_objects_with_exact_normalization_sources() {
    let dir = tempfile::tempdir().unwrap();
    let input = dir.path().join("input.h5");
    let project = dir.path().join("shared.dio");
    let expected = fixture(&input, 0.);
    let mut s = Session::new(root());
    normalized(&mut s, &input, true);
    call(&mut s, "save_project", json!({"path":project}));
    for _ in 0..3 {
        {
            let f = hdf5::File::open(&project).unwrap();
            shared_batch(&f, 0);
            aliases(
                &f,
                "configurations/0/map/pattern_intensities",
                "configurations/0/map/native_series/result/data",
            );
            aliases(
                &f,
                "configurations/0/map/pattern_x",
                "configurations/0/map/native_series/result/binning",
            );
            aliases(
                &f,
                "react_map_normalization/original",
                "configurations/0/map/native_series/result/desktop_original",
            );
            for p in [
                "configurations/0/native_batch/result/desktop_original",
                "configurations/0/map/native_series/result/desktop_original",
            ] {
                assert_eq!(
                    bits(&f, p),
                    expected.iter().map(|x| x.to_bits()).collect::<Vec<_>>()
                );
            }
        }
        call(&mut s, "open_project", json!({"path":project}));
        call(&mut s, "save_project", json!({"path":project}));
    }
}
#[test]
fn metadata_only_save_reuses_native_objects_without_merging_distinct_extensions() {
    let dir = tempfile::tempdir().unwrap();
    let input = dir.path().join("input.h5");
    let project = dir.path().join("markers.dio");
    fixture(&input, 0.);
    let mut s = Session::new(root());
    normalized(&mut s, &input, true);
    call(&mut s, "save_project", json!({"path":project}));
    {
        let f = hdf5::File::open_rw(&project).unwrap();
        for (path, marker) in [("native_batch", 17_u64), ("map/native_series", 29)] {
            f.dataset(&format!("configurations/0/{path}/result/data"))
                .unwrap()
                .new_attr::<u64>()
                .shape(())
                .create("extension_probe")
                .unwrap()
                .write_scalar(&marker)
                .unwrap();
        }
    }
    call(&mut s, "open_project", json!({"path":project}));
    call(
        &mut s,
        "configuration",
        json!({"operation":"rename","name":"Metadata changed"}),
    );
    call(&mut s, "batch_select", json!({"index":2}));
    call(&mut s, "save_project", json!({"path":project}));
    let f = hdf5::File::open(&project).unwrap();
    for (path, marker) in [("native_batch", 17_u64), ("map/native_series", 29)] {
        assert_eq!(
            f.dataset(&format!("configurations/0/{path}/result/data"))
                .unwrap()
                .attr("extension_probe")
                .unwrap()
                .read_scalar::<u64>()
                .unwrap(),
            marker
        );
    }
    shared_batch(&f, 0);
}
#[test]
fn source_changes_below_display_precision_are_saved_as_new_f64_values() {
    let dir = tempfile::tempdir().unwrap();
    let input = dir.path().join("input.h5");
    let project = dir.path().join("precision.dio");
    let before = fixture(&input, 0.);
    let mut s = Session::new(root());
    call(&mut s, "batch_open", json!({"path":input}));
    call(&mut s, "save_project", json!({"path":project}));
    call(&mut s, "open_project", json!({"path":project}));
    let after = fixture(&input, 1e-12);
    assert_ne!(before[0].to_bits(), after[0].to_bits());
    assert_eq!(
        before.iter().map(|x| *x as f32).collect::<Vec<_>>(),
        after.iter().map(|x| *x as f32).collect::<Vec<_>>()
    );
    call(&mut s, "batch_open", json!({"path":input}));
    call(&mut s, "save_project", json!({"path":project}));
    let f = hdf5::File::open(&project).unwrap();
    assert_eq!(
        bits(&f, "configurations/0/native_batch/result/data"),
        after.iter().map(|x| x.to_bits()).collect::<Vec<_>>()
    );
    drop(f);
    call(&mut s, "open_project", json!({"path":project}));
    call(
        &mut s,
        "batch_normalize",
        json!({"enabled":true,"start":4,"stop":45,"reference":2}),
    );
    call(&mut s, "save_project", json!({"path":project}));
    let f = hdf5::File::open(&project).unwrap();
    shared_batch(&f, 0);
    assert_eq!(
        bits(&f, "configurations/0/native_batch/result/desktop_original"),
        after.iter().map(|x| x.to_bits()).collect::<Vec<_>>()
    );
    drop(f);
    call(&mut s, "open_project", json!({"path":project}));
    call(&mut s, "batch_normalize", json!({"enabled":false}));
    call(&mut s, "save_project", json!({"path":project}));
    let f = hdf5::File::open(&project).unwrap();
    assert!(!f.link_exists("configurations/0/native_batch/result/desktop_original"));
    assert!(!f.link_exists("react_desktop_batch/normalization_source"));
    assert_eq!(
        bits(&f, "react_desktop_batch/data"),
        after.iter().map(|x| x.to_bits()).collect::<Vec<_>>()
    );
}
#[test]
fn legacy_react_normalization_recomputes_stale_current_data_before_reuse() {
    let dir = tempfile::tempdir().unwrap();
    let input = dir.path().join("input.h5");
    let project = dir.path().join("legacy.dio");
    fixture(&input, 0.);
    let mut s = Session::new(root());
    normalized(&mut s, &input, false);
    call(&mut s, "save_project", json!({"path":project}));
    let expected;
    {
        let f = hdf5::File::open_rw(&project).unwrap();
        expected = bits(&f, "configurations/0/native_batch/result/data");
        f.unlink("configurations/0/native_batch").unwrap();
        f.dataset("react_desktop_batch/data")
            .unwrap()
            .write_raw(&vec![999.; 256])
            .unwrap();
    }
    call(&mut s, "open_project", json!({"path":project}));
    call(&mut s, "save_project", json!({"path":project}));
    let f = hdf5::File::open(&project).unwrap();
    assert_eq!(
        bits(&f, "configurations/0/native_batch/result/data"),
        expected
    );
}

#[test]
fn converted_native_input_is_published_as_canonical_f64() {
    let dir = tempfile::tempdir().unwrap();
    let input = dir.path().join("input.h5");
    let project = dir.path().join("converted.dio");
    let raw = fixture(&input, 0.);
    let mut s = Session::new(root());
    call(&mut s, "batch_open", json!({"path":input}));
    call(&mut s, "save_project", json!({"path":project}));
    let converted: Vec<_> = raw.iter().map(|v| *v as f32).collect();
    {
        let f = hdf5::File::open_rw(&project).unwrap();
        let group = f.group("configurations/0/native_batch/result").unwrap();
        group.unlink("data").unwrap();
        group
            .new_dataset::<f32>()
            .shape([4, 64])
            .create("data")
            .unwrap()
            .write_raw(&converted)
            .unwrap();
    }
    call(&mut s, "open_project", json!({"path":project}));
    call(&mut s, "save_project", json!({"path":project}));
    let f = hdf5::File::open(&project).unwrap();
    let dataset = f
        .dataset("configurations/0/native_batch/result/data")
        .unwrap();
    assert!(dataset.dtype().unwrap().is::<f64>());
    assert_eq!(
        bits(&f, "configurations/0/native_batch/result/data"),
        converted
            .iter()
            .map(|v| (*v as f64).to_bits())
            .collect::<Vec<_>>()
    );
}

#[test]
fn external_native_arrays_are_frozen_from_loaded_values_and_saved_as_owned_storage() {
    use std::io::{Seek, SeekFrom, Write};
    for storage in ["raw", "virtual", "foreign-link"] {
        let dir = tempfile::tempdir().unwrap();
        let input = dir.path().join("input.h5");
        let project = dir.path().join("external.dio");
        let companion = dir.path().join("companion");
        let raw = fixture(&input, 0.);
        let raw_bytes: Vec<_> = raw.iter().flat_map(|v| v.to_le_bytes()).collect();
        let mut s = Session::new(root());
        call(&mut s, "batch_open", json!({"path":input}));
        call(&mut s, "save_project", json!({"path":project}));
        let offset = if storage == "raw" {
            std::fs::write(&companion, &raw_bytes).unwrap();
            0
        } else {
            let f = hdf5::File::create(&companion).unwrap();
            let d = f
                .new_dataset::<f64>()
                .shape([4, 64])
                .create("counts")
                .unwrap();
            d.write_raw(&raw).unwrap();
            d.offset().unwrap()
        };
        {
            let f = hdf5::File::open_rw(&project).unwrap();
            let group = f.group("configurations/0/native_batch/result").unwrap();
            group.unlink("data").unwrap();
            match storage {
                "raw" => {
                    group
                        .new_dataset::<f64>()
                        .shape([4, 64])
                        .external(companion.to_str().unwrap(), 0, raw_bytes.len())
                        .create("data")
                        .unwrap();
                }
                "virtual" => {
                    group
                        .new_dataset::<f64>()
                        .shape([4, 64])
                        .virtual_map(
                            companion.to_str().unwrap(),
                            "/counts",
                            (4, 64),
                            (.., ..),
                            (4, 64),
                            (.., ..),
                        )
                        .create("data")
                        .unwrap();
                }
                _ => group
                    .link_external(companion.to_str().unwrap(), "/counts", "data")
                    .unwrap(),
            }
        }
        call(&mut s, "open_project", json!({"path":project}));
        // External storage may change after the session has read its owned Vec.
        // Write the contiguous payload directly without altering HDF metadata.
        {
            let mut f = std::fs::OpenOptions::new()
                .write(true)
                .open(&companion)
                .unwrap();
            f.seek(SeekFrom::Start(offset)).unwrap();
            for value in &raw {
                f.write_all(&(value + 1000.).to_le_bytes()).unwrap();
            }
            f.sync_all().unwrap();
        }
        call(&mut s, "save_project", json!({"path":project}));
        {
            let f = hdf5::File::open(&project).unwrap();
            let data = f
                .dataset("configurations/0/native_batch/result/data")
                .unwrap();
            assert_ne!(data.layout(), hdf5::dataset::Layout::Virtual, "{storage}");
            assert!(
                data.dcpl().unwrap().get_external().unwrap().is_empty(),
                "{storage}"
            );
            assert_eq!(
                Path::new(&data.filename()).canonicalize().unwrap(),
                project.canonicalize().unwrap(),
                "{storage}"
            );
            assert_eq!(
                bits(&f, "configurations/0/native_batch/result/data"),
                raw.iter().map(|v| v.to_bits()).collect::<Vec<_>>(),
                "{storage}"
            );
        }
        std::fs::remove_file(&companion).unwrap();
        call(&mut s, "open_project", json!({"path":project}));
        call(&mut s, "save_project", json!({"path":project}));
        let f = hdf5::File::open(&project).unwrap();
        assert_eq!(
            bits(&f, "configurations/0/native_batch/result/data"),
            raw.iter().map(|v| v.to_bits()).collect::<Vec<_>>(),
            "{storage}"
        );
    }
}

#[test]
fn staging_name_collisions_preserve_existing_extension_objects() {
    let dir = tempfile::tempdir().unwrap();
    let input = dir.path().join("input.h5");
    let project = dir.path().join("extension-names.dio");
    fixture(&input, 0.);
    let mut s = Session::new(root());
    normalized(&mut s, &input, false);
    call(&mut s, "save_project", json!({"path":project}));
    {
        let file = hdf5::File::open_rw(&project).unwrap();
        let extension = file.create_group("__native_series_arrays").unwrap();
        extension
            .new_dataset::<u32>()
            .shape(())
            .create("keep")
            .unwrap()
            .write_scalar(&97)
            .unwrap();
        file.link_hard("/__native_series_arrays", "extension_alias")
            .unwrap();
        file.link_soft("/unavailable_extension", "__native_series_arrays_1")
            .unwrap();
    }
    call(&mut s, "open_project", json!({"path":project}));
    call(&mut s, "save_project", json!({"path":project}));
    let file = hdf5::File::open(&project).unwrap();
    assert_eq!(
        file.dataset("extension_alias/keep")
            .unwrap()
            .read_scalar::<u32>()
            .unwrap(),
        97
    );
    assert!(file.link_exists("__native_series_arrays_1"));
    assert!(!file.link_exists("__native_series_arrays_2"));
    shared_batch(&file, 0);
}

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
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
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

//! Exact Qt half-open rectangle/stride semantics through the shipping Session.
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
fn invoke(s: &mut Session, action: &str, payload: Value) -> Reply {
    s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    })
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = invoke(s, action, payload);
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn fixture(path: &Path, unit: &str, wavelength: bool) {
    let f = hdf5::File::create(path).unwrap();
    let g = f.create_group("processed").unwrap();
    let r = g.create_group("result").unwrap();
    let x: Vec<f64> = match unit {
        "d_A" => vec![9., 7., 5., 4., 3., 2., 1.],
        "q_A^-1" => vec![0.2, 0.5, 0.9, 1.4, 2., 2.7, 3.5],
        _ => vec![2., 5., 9., 14., 20., 27., 35.],
    };
    let axis = r
        .new_dataset_builder()
        .with_data(&x)
        .create("binning")
        .unwrap();
    axis.new_attr::<hdf5::types::VarLenUnicode>()
        .create("radial_unit")
        .unwrap()
        .write_scalar(&hdf5::types::VarLenUnicode::from_str(unit).unwrap())
        .unwrap();
    if wavelength {
        r.new_attr::<f64>()
            .create("desktop_wavelength_m")
            .unwrap()
            .write_scalar(&5e-11)
            .unwrap();
    }
    let y: Vec<_> = (0..42)
        .map(|i| (i / 7 + 1) as f64 * 10. + (i % 7) as f64 * 0.25)
        .collect();
    for (name, values) in [
        ("data", y),
        (
            "counting_std",
            (0..42).map(|i| (i + 1) as f64 * 0.01).collect(),
        ),
        (
            "azimuthal_std",
            (0..42).map(|i| (i + 1) as f64 * 0.03).collect(),
        ),
    ] {
        r.new_dataset::<f64>()
            .shape([6, 7])
            .create(name)
            .unwrap()
            .write_raw(&values)
            .unwrap();
    }
    let p = g.create_group("process").unwrap();
    let paths: Vec<_> = ["/missing/acq-A/scan.h5", "/missing/acq-B/scan.h5"]
        .iter()
        .map(|p| hdf5::types::VarLenUnicode::from_str(p).unwrap())
        .collect();
    p.new_dataset_builder()
        .with_data(&paths)
        .create("files")
        .unwrap();
    p.new_dataset_builder()
        .with_data(&[0u64, 3, 6])
        .create("file_map")
        .unwrap();
    p.new_dataset::<i64>()
        .shape([6, 2])
        .create("pos_map")
        .unwrap()
        .write_raw(&[0, 0, 0, 3, 0, 6, 1, 0, 1, 3, 1, 6])
        .unwrap();
}
fn curves(r: &Reply) -> &[Value] {
    r.result["pattern"]["curves"].as_array().unwrap()
}
fn overlays(r: &Reply) -> &[Value] {
    r.result["state"]["integration"]["overlays"]
        .as_array()
        .unwrap()
}
fn numbers(v: &Value) -> Vec<f64> {
    v.as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap())
        .collect()
}
fn close(a: &[f64], b: &[f64]) {
    assert_eq!(a.len(), b.len());
    for (a, b) in a.iter().zip(b) {
        assert!((a - b).abs() < 2e-12 * (1. + b.abs()), "{a} != {b}");
    }
}
fn selection(id: &Value, step: usize) -> Value {
    json!({"series":id,"bins":[6.9,1.1],"rows":[5.8,1.2],"step":step})
}

#[test]
fn rectangle_uses_exact_rows_bins_units_and_recorded_wavelength() {
    let d = tempfile::tempdir().unwrap();
    for source in ["2th_deg", "q_A^-1", "d_A"] {
        let file = d.path().join(format!("{source}.h5"));
        fixture(&file, source, true);
        let mut s = Session::new(root());
        let opened = call(&mut s, "batch_open", json!({"path":file}));
        let id = &opened.result["batch"]["waterfallKey"];
        assert_eq!(opened.result["batch"]["canReintegrate"], false);
        for target in ["2th_deg", "q_A^-1", "d_A"] {
            // Use the stored series' wavelength, regardless of live detector geometry.
            call(&mut s, "batch_unit", json!({"unit":target}));
            call(
                &mut s,
                "integration_overlay",
                json!({"operation":"waterfall_separation","separation":4.5}),
            );
            let before = call(&mut s, "batch_snapshot", json!({}));
            let r = call(&mut s, "batch_waterfall", selection(id, 2));
            assert_eq!(curves(&r).len(), 2);
            for (i, row) in [1usize, 3].iter().enumerate() {
                let selected = call(&mut s, "batch_select", json!({"index":row}));
                let x = numbers(&selected.result["pattern"]["x"]);
                close(&numbers(&curves(&r)[i]["x"]), &x[1..6]);
                let y: Vec<_> = (1..6)
                    .map(|col| (*row + 1) as f64 * 10. + col as f64 * 0.25 - 4.5 * (2 - i) as f64)
                    .collect();
                assert_eq!(numbers(&curves(&r)[i]["y"]), y);
                close(
                    &numbers(&curves(&r)[i]["sigma"]),
                    &(1..6)
                        .map(|col| (row * 7 + col + 1) as f64 * 0.01)
                        .collect::<Vec<_>>(),
                );
                let metadata = &overlays(&r)[i]["batchSource"];
                assert_eq!(metadata["row"], *row);
                assert_eq!(metadata["bins"], json!([1, 6]));
                assert_eq!(
                    metadata["path"],
                    if i == 0 {
                        "/missing/acq-A/scan.h5"
                    } else {
                        "/missing/acq-B/scan.h5"
                    }
                );
                assert_eq!(metadata["frame"], if i == 0 { 3 } else { 0 });
                assert_eq!(metadata["unit"], source);
            }
            let after = call(&mut s, "batch_snapshot", json!({}));
            assert_eq!(before.result["batch"]["id"], after.result["batch"]["id"]);
            assert_eq!(before.buffers[0].bytes, after.buffers[0].bytes);
            // Independent coordinate formulas, including descending d samples.
            let source_x: Vec<f64> = match source {
                "d_A" => vec![7., 5., 4., 3., 2.],
                "q_A^-1" => vec![0.5, 0.9, 1.4, 2., 2.7],
                _ => vec![5., 9., 14., 20., 27.],
            };
            let expected: Vec<_> = source_x
                .iter()
                .map(|&x| {
                    let q = match source {
                        "d_A" => 2. * std::f64::consts::PI / x,
                        "q_A^-1" => x,
                        _ => 4. * std::f64::consts::PI * (x.to_radians() / 2.).sin() / 0.5,
                    };
                    match target {
                        "q_A^-1" => q,
                        "d_A" => 2. * std::f64::consts::PI / q,
                        _ => 2. * (q * 0.5 / (4. * std::f64::consts::PI)).asin().to_degrees(),
                    }
                })
                .collect();
            close(&numbers(&curves(&r)[0]["x"]), &expected);
        }
    }
}

#[test]
fn normalized_waterfalls_replace_repeat_and_round_trip_with_overlay_edits() {
    let d = tempfile::tempdir().unwrap();
    let input = d.path().join("batch.h5");
    fixture(&input, "2th_deg", true);
    let mut s = Session::new(root());
    let opened = call(&mut s, "batch_open", json!({"path":input}));
    // Existing overlays are replaced like Qt. Extraction is independent of main-pattern fitting.
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"capture"}),
    );
    call(
        &mut s,
        "integration_background",
        json!({"enabled":true,"smoothing":0.1,"iterations":1,"order":1}),
    );
    let normalized = call(
        &mut s,
        "batch_normalize",
        json!({"enabled":true,"start":2,"stop":5}),
    );
    let id = &normalized.result["batch"]["waterfallKey"];
    let background = normalized.result["state"]["integration"]["patternBackground"].clone();
    let a = call(&mut s, "batch_waterfall", selection(id, 2));
    assert_eq!(
        a.result["state"]["integration"]["patternBackground"],
        background
    );
    assert_eq!(overlays(&a)[0]["batchSource"]["normalized"], true);
    let b = call(&mut s, "batch_waterfall", selection(id, 2));
    let factor = 10.625 / 20.625;
    close(
        &numbers(&curves(&a)[0]["y"]),
        &(1..6)
            .map(|col| (20. + col as f64 * 0.25) * factor)
            .collect::<Vec<_>>(),
    );
    close(
        &numbers(&curves(&a)[0]["sigma"]),
        &(1..6)
            .map(|col| (7 + col + 1) as f64 * 0.01 * factor)
            .collect::<Vec<_>>(),
    );
    assert_eq!(curves(&a), curves(&b));
    assert_eq!(overlays(&b).len(), 2);
    assert_ne!(overlays(&a)[0]["uid"], overlays(&b)[0]["uid"]);
    let all = call(&mut s, "batch_waterfall", selection(id, 1));
    assert_eq!(curves(&all).len(), 4);
    let undo = call(&mut s, "undo_calibration", json!({}));
    assert_eq!(overlays(&undo), overlays(&b));
    call(&mut s, "redo_calibration", json!({}));
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"update","index":0,"scale":2.5,"offset":19.,"name":"Selected normalized frame"}),
    );
    let changed = call(&mut s, "batch_unit", json!({"unit":"d_A"}));
    let expected = changed.result["pattern"]["curves"].clone();
    let metadata = changed.result["state"]["integration"]["overlays"].clone();
    let project = d.path().join("waterfall.dio");
    call(&mut s, "save_project", json!({"path":project}));
    std::fs::remove_file(input).unwrap();
    let mut restored = Session::new(root());
    let r = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(r.result["pattern"]["curves"], expected);
    assert_eq!(r.result["state"]["integration"]["overlays"], metadata);
    assert_eq!(r.result["batch"]["normalized"], true);
    // Raw matrix and reversible normalization remain owned by Batch, not overlays.
    let restored_data = call(&mut restored, "batch_normalize", json!({"enabled":false}));
    assert_eq!(
        restored_data.result["batch"]["id"],
        opened.result["batch"]["id"]
    );
    assert_eq!(restored_data.result["pattern"]["curves"], expected);
}

#[test]
fn invalid_or_stale_rectangles_leave_the_previous_overlay_owner_unchanged() {
    let d = tempfile::tempdir().unwrap();
    let input = d.path().join("batch.h5");
    fixture(&input, "q_A^-1", false);
    let mut s = Session::new(root());
    let opened = call(&mut s, "batch_open", json!({"path":input}));
    let id = &opened.result["batch"]["waterfallKey"];
    let a = call(&mut s, "batch_waterfall", selection(id, 2));
    for payload in [
        json!({"series":"stale","bins":[0,7],"rows":[0,6],"step":1}),
        json!({"series":id,"bins":[0.1,0.9],"rows":[0,6],"step":1}),
        json!({"series":id,"bins":[0,7],"rows":[1,1],"step":1}),
        json!({"series":id,"bins":[0,7],"rows":[0,6],"step":0}),
        json!({"series":id,"bins":[0,7],"rows":[0,6],"step":1.5}),
    ] {
        let r = invoke(&mut s, "batch_waterfall", payload);
        assert_eq!(r.result["ok"], false);
        let state = call(&mut s, "state", json!({}));
        assert_eq!(overlays(&state), overlays(&a));
    }
    let control = std::sync::Arc::new(dioptas_backend::control::Control::default());
    control.cancel();
    let cancelled = s.invoke_controlled(
        &Request {
            id: 2,
            action: "batch_waterfall".into(),
            payload: selection(id, 1),
            cached_buffers: vec![],
        },
        control,
    );
    assert_eq!(cancelled.result["cancelled"], true);
    assert_eq!(overlays(&call(&mut s, "state", json!({}))), overlays(&a));
    let d = call(&mut s, "batch_unit", json!({"unit":"d_A"}));
    assert_eq!(curves(&d).len(), 2);
    let bad = invoke(&mut s, "batch_unit", json!({"unit":"2th_deg"}));
    assert_eq!(bad.result["ok"], false);
    let full = call(
        &mut s,
        "batch_waterfall",
        json!({"series":id,"bins":[-9,99],"rows":[-10,99],"step":5}),
    );
    assert_eq!(curves(&full).len(), 2);
    assert_eq!(numbers(&curves(&full)[0]["y"]).len(), 7);
}

#[test]
fn identical_display_pixels_cannot_reuse_a_different_scientific_source_selection() {
    let d = tempfile::tempdir().unwrap();
    let input = d.path().join("first.h5");
    fixture(&input, "q_A^-1", false);
    let mut s = Session::new(root());
    let first = call(&mut s, "batch_open", json!({"path":input}));
    let id = &first.result["batch"]["waterfallKey"];
    let original = call(&mut s, "batch_waterfall", selection(id, 1));
    let changed = d.path().join("second.h5");
    fixture(&changed, "q_A^-1", false);
    {
        let f = hdf5::File::open_rw(&changed).unwrap();
        let paths: Vec<_> = ["/different/A/scan.h5", "/different/B/scan.h5"]
            .iter()
            .map(|p| hdf5::types::VarLenUnicode::from_str(p).unwrap())
            .collect();
        f.dataset("processed/process/files")
            .unwrap()
            .write_raw(&paths)
            .unwrap();
    }
    let second = call(&mut s, "batch_open", json!({"path":changed}));
    assert_eq!(first.result["batch"]["id"], second.result["batch"]["id"]);
    assert_ne!(id, &second.result["batch"]["waterfallKey"]);
    assert_eq!(
        invoke(&mut s, "batch_waterfall", selection(id, 1)).result["ok"],
        false
    );
    assert_eq!(
        overlays(&call(&mut s, "state", json!({}))),
        overlays(&original)
    );
    {
        let f = hdf5::File::open_rw(&input).unwrap();
        let data = f.dataset("processed/result/data").unwrap();
        let mut values = data.read_raw::<f64>().unwrap();
        values[0] += 1e-11;
        data.write_raw(&values).unwrap();
    }
    let third = call(&mut s, "batch_open", json!({"path":input}));
    assert_eq!(first.result["batch"]["id"], third.result["batch"]["id"]);
    assert_ne!(id, &third.result["batch"]["waterfallKey"]);
}

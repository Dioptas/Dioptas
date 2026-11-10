//! Native command, ownership, rollback and project tests; no Python runtime.
use dioptas_backend::{
    Session,
    control::Control,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{path::Path, str::FromStr, sync::Arc};
fn request(action: &str, payload: Value) -> Request {
    Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    }
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = s.invoke(&request(action, payload));
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn session() -> Session {
    Session::new(Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."))
}
fn fixture(path: &Path, case: usize) -> Value {
    let references: Value =
        serde_json::from_str(include_str!("fixtures/batch_background_qt.json")).unwrap();
    let case = &references["cases"][case];
    let x: Vec<f64> = serde_json::from_value(case["x"].clone()).unwrap();
    let data: Vec<f64> = serde_json::from_value(case["data"].clone()).unwrap();
    let file = hdf5::File::create(path).unwrap();
    file.new_dataset::<f64>()
        .shape([3, x.len()])
        .create("data")
        .unwrap()
        .write_raw(&data)
        .unwrap();
    let axis = file
        .new_dataset_builder()
        .with_data(&x)
        .create("binning")
        .unwrap();
    axis.new_attr::<hdf5::types::VarLenUnicode>()
        .shape(())
        .create("radial_unit")
        .unwrap()
        .write_scalar(
            &hdf5::types::VarLenUnicode::from_str(case["unit"].as_str().unwrap()).unwrap(),
        )
        .unwrap();
    let sigma: Vec<_> = data.iter().map(|y| y.sqrt()).collect();
    file.new_dataset::<f64>()
        .shape([3, x.len()])
        .create("counting_std")
        .unwrap()
        .write_raw(&sigma)
        .unwrap();
    case.clone()
}
fn batch(s: &mut Session) -> Value {
    call(s, "batch_snapshot", json!({})).result["batch"].clone()
}
fn saved(s: &mut Session, path: &Path, name: &str) -> Vec<f64> {
    call(s, "integration_save_batch", json!({"path":path}));
    hdf5::File::open(path)
        .unwrap()
        .dataset(name)
        .unwrap()
        .read_raw()
        .unwrap()
}
#[test]
fn settings_and_failures_are_atomic_and_batch_display_leaves_linked_pattern_and_map_alone() {
    let temp = tempfile::tempdir().unwrap();
    let input = temp.path().join("source.h5");
    let output = temp.path().join("saved.h5");
    let reference = fixture(&input, 0);
    let mut s = session();
    call(&mut s, "batch_open", json!({"path":input}));
    let before = batch(&mut s);
    let failed = s.invoke(&request(
        "batch_background_display",
        json!({"subtract":true}),
    ));
    assert_eq!(failed.result["ok"], false);
    assert_eq!(batch(&mut s), before);
    call(&mut s, "map_batch", json!({"path":input}));
    let map = call(&mut s, "state", json!({})).result["map"].clone();
    call(
        &mut s,
        "batch_background_extract",
        json!({"parameters":reference["parameters"]}),
    );
    let original = saved(&mut s, &output, "processed/result/data");
    let expected: Vec<f64> = serde_json::from_value(reference["data"].clone()).unwrap();
    assert_eq!(original, expected);
    let linked = call(&mut s, "batch_select", json!({"index":2})).result["pattern"].clone();
    call(&mut s, "batch_background_display", json!({"subtract":true}));
    let selected = batch(&mut s);
    assert_eq!(selected["selected"], 2);
    assert_eq!(selected["pattern"]["y"], linked["y"]);
    assert_eq!(selected["pattern"]["sigma"], linked["sigma"]);
    assert_ne!(selected["raster"]["bufferId"], before["raster"]["bufferId"]);
    assert_eq!(call(&mut s, "state", json!({})).result["map"], map);
    assert_eq!(saved(&mut s, &output, "processed/result/data"), original);
    call(
        &mut s,
        "batch_background_settings",
        json!({"parameters":{"smoothing":0.5,"iterations":21,"order":9}}),
    );
    let stale = batch(&mut s);
    assert_eq!(stale["backgroundState"]["stale"], true);
    assert_eq!(stale["raster"], selected["raster"]);
    for invalid in [
        json!({"parameters":{"smoothing":0.1,"iterations":0,"order":4}}),
        json!({"range":[99,100]}),
        json!({"range":[8,2]}),
        json!({"subtract":"true"}),
    ] {
        let result = s.invoke(&request("batch_background_settings", invalid));
        assert_eq!(result.result["ok"], false);
        assert_eq!(batch(&mut s), stale);
    }
    let control = Arc::new(Control::default());
    control.cancel();
    let cancelled = s.invoke_controlled(
        &request(
            "batch_background_extract",
            json!({"parameters":reference["parameters"]}),
        ),
        control,
    );
    assert_eq!(cancelled.result["cancelled"], true);
    assert_eq!(batch(&mut s), stale);
    call(&mut s, "batch_background_extract", json!({}));
    assert_eq!(batch(&mut s)["backgroundState"]["stale"], false);
    assert_ne!(batch(&mut s)["raster"], stale["raster"]);
}
#[test]
fn physical_normalization_limits_and_descending_background_cut_survive_configuration_project_reopen()
 {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("stored.h5");
    let project = temp.path().join("backgrounds.dio");
    let output = temp.path().join("restored.h5");
    let reference = fixture(&source, 2);
    let x: Vec<f64> = serde_json::from_value(reference["x"].clone()).unwrap();
    let mut s = session();
    call(&mut s, "batch_open", json!({"path":source}));
    call(
        &mut s,
        "batch_normalization_settings",
        json!({"minimum":x[79],"maximum":x[9],"unit":"d_A"}),
    );
    assert_eq!(batch(&mut s)["normalizationRange"], json!([9, 80]));
    call(&mut s, "batch_normalize", json!({"enabled":true}));
    assert_eq!(batch(&mut s)["normalizationRange"], json!([9, 80]));
    call(
        &mut s,
        "batch_background_extract",
        json!({"parameters":reference["parameters"]}),
    );
    call(
        &mut s,
        "batch_background_settings",
        json!({"range":[x[80],x[10]],"unit":"d_A","cut":true,"subtract":true}),
    );
    assert_eq!(batch(&mut s)["sourceBins"], json!([10, 81]));
    // Q <-> d conversion is allowed without inventing an angular wavelength.
    call(&mut s, "batch_unit", json!({"unit":"q_A^-1"}));
    call(&mut s, "batch_select", json!({"index":1}));
    let primary = batch(&mut s);
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(
        &mut s,
        "batch_background_settings",
        json!({"subtract":false,"cut":false}),
    );
    call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(batch(&mut s), primary);
    call(&mut s, "save_project", json!({"path":project}));
    std::fs::remove_file(source).unwrap();
    let mut restored = session();
    call(&mut restored, "open_project", json!({"path":project}));
    let reopened = batch(&mut restored);
    for (key, value) in primary.as_object().unwrap() {
        assert_eq!(&reopened[key], value, "reopened field {key}");
    }
    let selected = call(&mut restored, "batch_select", json!({"index":1}));
    assert_eq!(selected.result["pattern"]["y"], primary["pattern"]["y"]);
    call(&mut restored, "batch_normalize", json!({"enabled":false}));
    call(
        &mut restored,
        "batch_background_display",
        json!({"subtract":false,"cut":false}),
    );
    let original: Vec<f64> = serde_json::from_value(reference["data"].clone()).unwrap();
    assert_eq!(
        saved(&mut restored, &output, "processed/result/data"),
        original
    );
    let sigma = saved(&mut restored, &output, "processed/result/counting_std");
    assert_eq!(sigma, original.iter().map(|y| y.sqrt()).collect::<Vec<_>>());
    call(
        &mut restored,
        "configuration",
        json!({"operation":"select","index":1}),
    );
    assert_eq!(batch(&mut restored)["backgroundState"]["subtract"], false);
    assert_eq!(batch(&mut restored)["backgroundState"]["cut"], false);
}

#[test]
fn running_background_exposes_progress_and_cancels_without_replacing_any_state() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("source.h5");
    let reference = fixture(&source, 0);
    let mut s = session();
    call(&mut s, "batch_open", json!({"path":source}));
    call(
        &mut s,
        "batch_background_extract",
        json!({"parameters":reference["parameters"]}),
    );
    let before = batch(&mut s);
    let state = call(&mut s, "state", json!({})).result;
    let control = Arc::new(Control::default());
    let signal = control.clone();
    let worker = std::thread::spawn(move || {
        let start = std::time::Instant::now();
        while start.elapsed().as_secs() < 5 {
            let p = signal.progress();
            if p["label"] == "Extracting batch background" {
                assert_eq!(p["running"], true);
                assert_eq!(p["total"], 3);
                signal.cancel();
                return;
            }
            std::thread::sleep(std::time::Duration::from_millis(1));
        }
        panic!("Background extraction did not expose progress");
    });
    let start = std::time::Instant::now();
    let result = s.invoke_controlled(
        &request(
            "batch_background_extract",
            json!({"parameters":{"smoothing":0.37,"iterations":99999,"order":8}}),
        ),
        control,
    );
    worker.join().unwrap();
    assert_eq!(result.result["cancelled"], true);
    assert!(start.elapsed().as_secs_f64() < 3.0);
    assert_eq!(batch(&mut s), before);
    assert_eq!(call(&mut s, "state", json!({})).result, state);
}

#[test]
fn background_cut_keeps_existing_waterfall_coordinates_errors_and_stale_selection_guard_coherent() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("source.h5");
    let reference = fixture(&source, 0);
    let mut s = session();
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"waterfall_separation","separation":0}),
    );
    call(&mut s, "batch_open", json!({"path":source}));
    call(
        &mut s,
        "batch_background_extract",
        json!({"parameters":reference["parameters"]}),
    );
    let original_key = batch(&mut s)["waterfallKey"].clone();
    call(
        &mut s,
        "batch_background_display",
        json!({"subtract":true,"range":[2.0,8.0],"cut":true}),
    );
    let b = batch(&mut s);
    assert_ne!(b["waterfallKey"], original_key);
    let old = s.invoke(&request(
        "batch_waterfall",
        json!({"series":original_key,"bins":[1,5],"rows":[0,3],"step":2}),
    ));
    assert_eq!(old.result["ok"], false);
    let result = call(
        &mut s,
        "batch_waterfall",
        json!({"series":b["waterfallKey"],"bins":[1,5],"rows":[0,3],"step":2}),
    );
    let curves = result.result["pattern"]["curves"].as_array().unwrap();
    assert_eq!(curves.len(), 2);
    let start = b["sourceBins"][0].as_u64().unwrap() as usize + 1;
    let data: Vec<f64> = serde_json::from_value(reference["data"].clone()).unwrap();
    let background: Vec<f64> = serde_json::from_value(reference["background"].clone()).unwrap();
    let x: Vec<f64> = serde_json::from_value(reference["x"].clone()).unwrap();
    assert!(
        result.result["state"]["integration"]["waterfallSeparation"]
            .as_f64()
            .unwrap()
            > 0.0
    );
    for (index, (curve, row)) in curves.iter().zip([0, 2]).enumerate() {
        let offset = result.result["state"]["integration"]["overlays"][index]["offset"]
            .as_f64()
            .unwrap();
        let actual: Vec<f64> = serde_json::from_value(curve["y"].clone()).unwrap();
        let expected: Vec<_> = (start..start + 4)
            .map(|col| data[row * 97 + col] - background[row * 97 + col] + offset)
            .collect();
        assert_eq!(curve["x"], json!(x[start..start + 4]));
        for (a, e) in actual.iter().zip(expected) {
            assert!((a - e).abs() < 1e-8);
        }
        let errors: Vec<f64> = serde_json::from_value(curve["sigma"].clone()).unwrap();
        assert_eq!(
            errors,
            (start..start + 4)
                .map(|col| data[row * 97 + col].sqrt())
                .collect::<Vec<_>>()
        );
    }
    assert_eq!(batch(&mut s), b);
}

fn assert_batch_background_matches_pattern(s: &mut Session, output: &Path) {
    let raw = saved(s, output, "processed/result/data");
    let background = saved(s, output, "processed/process/bkg");
    let sigma = saved(s, output, "processed/result/counting_std");
    let before = batch(s);
    let x: Vec<f64> = serde_json::from_value(before["pattern"]["x"].clone()).unwrap();
    let count = before["entries"].as_array().unwrap().len();
    let n = x.len();
    for row in 0..count {
        let selected = call(s, "batch_select", json!({"index":row}));
        let curve = &selected.result["pattern"];
        let xx: Vec<f64> = serde_json::from_value(curve["x"].clone()).unwrap();
        let yy: Vec<f64> = serde_json::from_value(curve["y"].clone()).unwrap();
        let errors: Vec<f64> = serde_json::from_value(curve["sigma"].clone()).unwrap();
        for ((&a, &y), &error) in xx.iter().zip(&yy).zip(&errors) {
            let col = x.iter().position(|v| v.to_bits() == a.to_bits()).unwrap();
            let actual = raw[row * n + col] - background[row * n + col];
            assert!(
                (actual - y).abs() < 1e-9 * y.abs().max(1.0),
                "row {row}, source bin {col}: {actual} != {y}"
            );
            assert_eq!(error, sigma[row * n + col]);
        }
    }
}

#[test]
fn stored_batch_applies_pattern_background_roi_in_current_units_without_compounding() {
    let temp = tempfile::tempdir().unwrap();
    for case in [0, 1, 2] {
        let input = temp.path().join(format!("stored_{case}.h5"));
        let output = temp.path().join(format!("output_{case}.h5"));
        let reference = fixture(&input, case);
        let mut s = session();
        call(&mut s, "batch_open", json!({"path":input}));
        let unit = if case == 2 {
            "q_A^-1"
        } else {
            reference["unit"].as_str().unwrap()
        };
        call(&mut s, "batch_unit", json!({"unit":unit}));
        call(
            &mut s,
            "batch_normalize",
            json!({"enabled":true,"start":5,"stop":70,"reference":2}),
        );
        let before = batch(&mut s);
        let x: Vec<f64> = serde_json::from_value(before["pattern"]["x"].clone()).unwrap();
        let mut range = [x[12], x[75]];
        range.sort_by(f64::total_cmp);
        call(
            &mut s,
            "integration_background",
            json!({"enabled":true,"smoothing":0.18,"iterations":11,"order":7,"range":range}),
        );
        call(&mut s, "batch_background_from_pattern", json!({}));
        let applied = batch(&mut s);
        assert_eq!(applied["backgroundState"]["subtract"], true);
        assert_eq!(applied["backgroundState"]["cut"], true);
        assert_eq!(applied["backgroundState"]["patternSettings"], true);
        assert_eq!(applied["backgroundState"]["parametersUnit"], unit);
        assert!(applied["x"].as_array().unwrap().len() < 97);
        assert_eq!(applied["pattern"]["y"], before["pattern"]["y"]);
        assert_batch_background_matches_pattern(&mut s, &output);
        let prior = saved(&mut s, &output, "processed/process/bkg");
        call(&mut s, "batch_background_from_pattern", json!({}));
        assert_eq!(saved(&mut s, &output, "processed/process/bkg"), prior);
        let project = temp.path().join(format!("pattern_background_{case}.dio"));
        let snapshot = batch(&mut s);
        call(&mut s, "save_project", json!({"path":project}));
        let mut reopened = session();
        call(&mut reopened, "open_project", json!({"path":project}));
        assert_eq!(batch(&mut reopened), snapshot);
        call(&mut s, "integration_background", json!({"enabled":false}));
        call(&mut s, "batch_background_from_pattern", json!({}));
        assert_eq!(batch(&mut s)["backgroundState"]["subtract"], false);
        call(&mut s, "batch_normalize", json!({"enabled":false}));
        let original: Vec<f64> = serde_json::from_value(reference["data"].clone()).unwrap();
        assert_eq!(saved(&mut s, &output, "processed/result/data"), original);
    }
}

#[test]
fn new_raw_batch_inherits_active_pattern_background_and_enables_subtraction() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let temp = tempfile::tempdir().unwrap();
    let output = temp.path().join("raw_batch.h5");
    let mut s = session();
    call(
        &mut s,
        "open_calibration",
        json!({"path":root.join("dioptas/tests/data/LaB6_40keV_MarCCD.poni")}),
    );
    call(
        &mut s,
        "integration_settings",
        json!({"bins":97,"cake_bins":12,"poisson_errors":true,"trim_zeros":false}),
    );
    let paths: Vec<_> = ["001", "002"]
        .iter()
        .map(|i| root.join(format!("dioptas/tests/data/image_{i}.tif")))
        .collect();
    call(&mut s, "open_image", json!({"path":paths[0]}));
    call(
        &mut s,
        "integration_background",
        json!({"enabled":true,"smoothing":0.1,"iterations":7,"order":5}),
    );
    call(&mut s, "batch_load", json!({"paths":paths}));
    let b = batch(&mut s);
    assert_eq!(b["backgroundState"]["subtract"], true);
    assert_eq!(b["backgroundState"]["patternSettings"], true);
    assert_eq!(b["backgroundState"]["parameters"]["iterations"], 7);
    assert_batch_background_matches_pattern(&mut s, &output);
}

#[test]
fn loaded_overlay_and_automatic_pattern_background_use_the_same_batch_pipeline() {
    let temp = tempfile::tempdir().unwrap();
    let input = temp.path().join("stored.h5");
    let output = temp.path().join("out.h5");
    let overlay = temp.path().join("flat.xy");
    let reference = fixture(&input, 0);
    let x: Vec<f64> = serde_json::from_value(reference["x"].clone()).unwrap();
    std::fs::write(
        &overlay,
        x[10..85]
            .iter()
            .map(|v| format!("{v:.17e} 5\n"))
            .collect::<String>(),
    )
    .unwrap();
    let mut s = session();
    call(&mut s, "batch_open", json!({"path":input}));
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"load","path":overlay}),
    );
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"background","index":0}),
    );
    call(&mut s, "batch_background_from_pattern", json!({}));
    assert_batch_background_matches_pattern(&mut s, &output);
    call(
        &mut s,
        "integration_background",
        json!({"enabled":true,"smoothing":0.2,"iterations":9,"order":6,"range":[2.0,8.0]}),
    );
    call(&mut s, "batch_background_from_pattern", json!({}));
    assert_batch_background_matches_pattern(&mut s, &output);
}

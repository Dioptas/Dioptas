#![cfg(feature = "dioptrin")]
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::Path;
fn call(s: &mut Session, action: &str, mut payload: Value) -> Reply {
    payload["requested_products"] = json!({"cake":false,"rings":false});
    let r = s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn rows(path: &Path) -> Vec<Vec<f64>> {
    std::fs::read_to_string(path)
        .unwrap()
        .lines()
        .filter(|l| !l.starts_with('#'))
        .map(|l| l.split(',').map(|v| v.parse().unwrap()).collect())
        .collect()
}
#[test]
fn original_observables_survive_background_units_masks_and_project_configuration_changes() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let mut s = Session::new(root.clone());
    call(
        &mut s,
        "open_calibration",
        json!({"path":root.join("dioptas/tests/data/CeO2_Pilatus1M.poni")}),
    );
    call(
        &mut s,
        "integration_settings",
        json!({"bins":96,"cake_bins":12,"azimuthal_std":true,"poisson_errors":true}),
    );
    call(
        &mut s,
        "open_image",
        json!({"path":root.join("dioptas/tests/data/CeO2_Pilatus1M.tif")}),
    );
    let temp = tempfile::tempdir().unwrap();
    let file = temp.path().join("single.csv");
    for method in ["polygon", "subpixel", "pyfai_full"] {
        for unit in ["2th_deg", "q_A^-1", "d_A"] {
            call(&mut s, "integration_background", json!({"enabled":false}));
            let initial = call(
                &mut s,
                "integration_settings",
                json!({"unit":unit,"method":method,"supersampling":2,"trim_zeros":true}),
            );
            let raw = &initial.result["pattern"]["spottiness"];
            assert_eq!(raw["x"], initial.result["pattern"]["x"]);
            assert_eq!(raw["mean"], initial.result["pattern"]["y"]);
            assert_eq!(raw["std"], initial.result["pattern"]["azimuthalStd"]);
            assert_ne!(raw["std"], initial.result["pattern"]["sigma"]);
            let x = raw["x"].as_array().unwrap();
            let low = x
                .iter()
                .filter_map(Value::as_f64)
                .fold(f64::INFINITY, f64::min);
            let high = x
                .iter()
                .filter_map(Value::as_f64)
                .fold(f64::NEG_INFINITY, f64::max);
            let sub = call(
                &mut s,
                "integration_background",
                json!({"enabled":true,"smoothing":0.05,"iterations":2,"order":3,"range":[low+(high-low)*0.1,high-(high-low)*0.1]}),
            );
            let diag = &sub.result["pattern"]["spottiness"];
            // Background sorting may reverse the raw curve, never its pairing.
            for (i, xx) in diag["x"].as_array().unwrap().iter().enumerate() {
                let j = x.iter().position(|v| v == xx).unwrap();
                for key in ["mean", "std", "relative"] {
                    assert_eq!(diag[key][i], raw[key][j]);
                }
            }
            assert!(sub.result["pattern"]["x"].as_array().unwrap().len() < x.len());
            call(&mut s, "integration_save_spottiness", json!({"path":file}));
            let csv = rows(&file);
            assert_eq!(csv.len(), x.len());
            for (i, row) in csv.iter().enumerate() {
                for (col, key) in ["x", "mean", "std", "relative"].into_iter().enumerate() {
                    assert!(match diag[key][i].as_f64() {
                        Some(v) => row[col] == v,
                        None => row[col].is_nan(),
                    });
                }
            }
            // Reintegrating d with an enabled background must reverse std too.
            let warm = call(&mut s, "integrate", json!({}));
            assert_eq!(warm.result["pattern"]["spottiness"], *diag);
        }
    }
    call(&mut s, "integration_background", json!({"enabled":false}));
    let masked = call(
        &mut s,
        "integration_roi",
        json!({"limits":[100,500,50,400]}),
    );
    assert!(masked.result["pattern"]["spottiness"].is_object());
    let original = call(
        &mut s,
        "integration_settings",
        json!({"spottiness_relative":true}),
    );
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(
        &mut s,
        "integration_settings",
        json!({"azimuthal_std":false,"spottiness_relative":false}),
    );
    let back = call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(
        back.result["pattern"]["spottiness"],
        original.result["pattern"]["spottiness"]
    );
    assert_eq!(
        back.result["state"]["integration"]["spottinessRelative"],
        true
    );
    let project = temp.path().join("spread.dio");
    call(&mut s, "save_project", json!({"path":project}));
    call(
        &mut s,
        "integration_settings",
        json!({"spottiness_relative":false}),
    );
    let restored = call(&mut s, "open_project", json!({"path":project}));
    assert_eq!(
        restored.result["pattern"]["spottiness"],
        back.result["pattern"]["spottiness"]
    );
    assert_eq!(
        restored.result["state"]["integration"]["spottinessRelative"],
        true
    );
    call(&mut s, "combination_settings", json!({"patterns":true}));
    let before = std::fs::read(&file).unwrap();
    let rejected = s.invoke(&Request {
        id: 2,
        action: "integration_save_spottiness".into(),
        payload: json!({"path":file}),
        cached_buffers: vec![],
    });
    assert_eq!(rejected.result["ok"], false);
    assert!(
        rejected.result["error"]
            .as_str()
            .unwrap()
            .contains("combined")
    );
    assert_eq!(std::fs::read(&file).unwrap(), before);
}

#[test]
fn normalized_stored_rows_keep_mean_std_and_relative_paired() {
    let dir = tempfile::tempdir().unwrap();
    let input = dir.path().join("stored.h5");
    {
        let file = hdf5::File::create(&input).unwrap();
        file.new_dataset::<f64>()
            .shape([2, 4])
            .create("data")
            .unwrap()
            .write_raw(&[10., 20., 30., 40., 20., 40., 60., 80.])
            .unwrap();
        file.new_dataset_builder()
            .with_data(&[1., 2., 3., 4.])
            .create("binning")
            .unwrap();
        file.new_dataset::<f64>()
            .shape([2, 4])
            .create("azimuthal_std")
            .unwrap()
            .write_raw(&[1., 2., 3., 4., 2., 4., 6., 8.])
            .unwrap();
    }
    let mut s = Session::new(Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."));
    call(&mut s, "batch_open", json!({"path":input}));
    call(
        &mut s,
        "batch_normalize",
        json!({"enabled":true,"start":1,"stop":4,"reference":1}),
    );
    let selected = call(&mut s, "batch_select", json!({"index":1}));
    let diag = &selected.result["pattern"]["spottiness"];
    assert_eq!(diag["mean"], json!([10., 20., 30., 40.]));
    assert_eq!(diag["std"], json!([1., 2., 3., 4.]));
    assert_eq!(diag["relative"], json!([0.1, 0.1, 0.1, 0.1]));
    let background = dir.path().join("background.xy");
    std::fs::write(&background, "2 7\n3 8\n").unwrap();
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"load","path":background}),
    );
    let sub = call(
        &mut s,
        "integration_overlay",
        json!({"operation":"background","index":0}),
    );
    assert_eq!(sub.result["pattern"]["x"], json!([2., 3.]));
    assert_eq!(sub.result["pattern"]["y"], json!([13., 22.]));
    assert_eq!(sub.result["pattern"]["spottiness"], *diag);
    let csv = dir.path().join("row.csv");
    call(&mut s, "integration_save_spottiness", json!({"path":csv}));
    assert_eq!(
        rows(&csv).iter().map(|r| r[3]).collect::<Vec<_>>(),
        vec![0.1; 4]
    );
    call(
        &mut s,
        "integration_settings",
        json!({"azimuthal_std":true}),
    );
    let plain = dir.path().join("plain.xy");
    std::fs::write(&plain, "1 10\n2 20\n3 30\n").unwrap();
    let imported = call(&mut s, "integration_open_pattern", json!({"path":plain}));
    assert_eq!(
        imported.result["state"]["integration"]["spottinessAvailable"],
        false
    );
    assert!(imported.result["pattern"]["spottiness"].is_null());
}

#[test]
fn diagnostic_preferences_preserve_owned_cake_and_azimuthal_profile() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let mut s = Session::new(root.clone());
    call(
        &mut s,
        "open_calibration",
        json!({"path":root.join("dioptas/tests/data/CeO2_Pilatus1M.poni")}),
    );
    call(
        &mut s,
        "integration_settings",
        json!({"bins":96,"cake_bins":36,"azimuthal_std":true}),
    );
    call(
        &mut s,
        "open_image",
        json!({"path":root.join("dioptas/tests/data/CeO2_Pilatus1M.tif")}),
    );
    let profile = call(
        &mut s,
        "cake_profile",
        json!({"two_theta":10.,"bins":3,"shift":0}),
    );
    let original = profile.result["cakeProfile"].clone();
    assert!(original.is_object(), "{}", profile.result);
    let before = call(&mut s, "integration_diagnostics", json!({}));
    let curve = call(&mut s, "state", json!({})).result["pattern"]["spottiness"].clone();
    for relative in [true, false] {
        let updated = call(
            &mut s,
            "integration_settings",
            json!({"spottiness_relative":relative}),
        );
        assert_eq!(updated.result["pattern"]["spottiness"], curve);
        let profile = call(
            &mut s,
            "cake_profile",
            json!({"two_theta":10.,"bins":3,"shift":0}),
        );
        assert_eq!(profile.result["cakeProfile"], original);
    }
    let after = call(&mut s, "integration_diagnostics", json!({}));
    assert_eq!(
        before.result["integrationDiagnostics"],
        after.result["integrationDiagnostics"]
    );
}

#![cfg(feature = "dioptrin")]
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{
    fs,
    path::{Path, PathBuf},
};

fn call(session: &mut Session, command: &str, payload: Value) -> Reply {
    let result = session.invoke(&Request {
        id: 1,
        action: command.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(result.result["ok"], true, "{command}: {}", result.result);
    result
}
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap()
}
fn mask_bytes(result: &Reply) -> &[u8] {
    let id = result.result["mask"]["bufferId"].as_str().unwrap();
    result
        .buffers
        .iter()
        .find(|b| b.id == id)
        .unwrap()
        .bytes
        .as_ref()
}

#[test]
fn mask_integration_batch_map_and_multiple_configurations_share_project_state() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("counts.h5");
    fs::copy(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/combined-counts.h5"),
        &source,
    )
    .unwrap();
    let poni = temp.path().join("appended.poni");
    fs::write(&poni, "PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.1\nPoni1: 0.003\nPoni2: 0.004\nRot1: 0\nRot2: 0\nRot3: 0\nSplineFile: None\nWavelength: 4e-11\nDistance: 0.2\n").unwrap();
    let mask = temp.path().join("asymmetric.mask");
    fs::copy(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/asymmetric.mask"),
        &mask,
    )
    .unwrap();
    let mut session = Session::new(root());
    call(
        &mut session,
        "integration_settings",
        json!({"bins":48,"cake_bins":12,"trim_zeros":false}),
    );
    call(&mut session, "open_calibration", json!({"path":poni}));
    call(
        &mut session,
        "open_image",
        json!({"path":source,"dataset":"/counts"}),
    );
    let loaded = call(&mut session, "mask_file", json!({"path":mask}));
    let expected_mask = mask_bytes(&loaded).to_vec();
    assert_eq!(expected_mask[10 * 80 + 20], 1);
    assert_eq!(expected_mask[(63 - 10) * 80 + 20], 0);
    assert_eq!(
        call(&mut session, "pixel", json!({"x":20,"y":10})).result["pixel"]["value"],
        843.
    );

    // Exercise the actual fixed-plan HDF5 path, not just the generic reader.
    for unit in ["2th_deg", "q_A^-1", "d_A"] {
        for errors in [false, true] {
            for use_mask in [false, true] {
                call(
                    &mut session,
                    "integration_settings",
                    json!({"unit":unit,"poisson_errors":errors,"use_mask":use_mask}),
                );
                let before = call(&mut session,"integration_diagnostics",json!({})).result["integrationDiagnostics"].clone();
                call(&mut session, "batch_load", json!({"paths":[source]}));
                let after = call(&mut session,"integration_diagnostics",json!({})).result["integrationDiagnostics"].clone();
                assert_eq!(
                    after["patternOnlyDecodes"].as_u64().unwrap()
                        - before["patternOnlyDecodes"].as_u64().unwrap(),
                    3
                );
                assert_eq!(after["patternPlanBuilds"], before["patternPlanBuilds"]);
                let processed = temp.path().join("batch.h5");
                call(
                    &mut session,
                    "integration_save_batch",
                    json!({"path":processed}),
                );
                let file = hdf5::File::open(&processed).unwrap();
                let values = file
                    .dataset("processed/result/data")
                    .unwrap()
                    .read_raw::<f64>()
                    .unwrap();
                for frame in 0..3 {
                    let direct = call(
                        &mut session,
                        "integration_navigation",
                        json!({"frame":frame+1}),
                    );
                    let y = direct.result["pattern"]["y"].as_array().unwrap();
                    for (actual, expected) in values[frame * 48..(frame + 1) * 48].iter().zip(y) {
                        assert!((actual - expected.as_f64().unwrap()).abs() < 1e-9);
                    }
                }
            }
        }
    }
    call(
        &mut session,
        "integration_settings",
        json!({"unit":"q_A^-1","poisson_errors":false,"use_mask":true}),
    );
    call(&mut session, "map_load", json!({"paths":[source]}));
    let scan = call(&mut session, "state", json!({}));
    let minimum = scan.result["map"]["rois"][0]["min"].as_f64().unwrap();
    let maximum = scan.result["map"]["rois"][0]["max"].as_f64().unwrap();
    call(
        &mut session,
        "map_roi",
        json!({"op":"update","name":"A","minimum":minimum*0.9,"maximum":maximum*0.9,"reduction":"mean","background":true}),
    );
    call(&mut session, "map_roi", json!({"op":"add"}));
    let analysis = call(
        &mut session,
        "map_expression",
        json!({"name":"Contrast","expression":"A*2+B"}),
    );
    let second_source = temp.path().join("next-scan.h5");
    fs::copy(&source, &second_source).unwrap();
    let next = call(&mut session, "map_load", json!({"paths":[second_source]}));
    for key in ["rois", "expressions", "active", "values"] {
        assert_eq!(
            next.result["map"][key], analysis.result["map"][key],
            "map load must preserve {key}"
        );
    }
    let rebuilt = call(&mut session, "map_load", json!({"reintegrate":true}));
    for key in ["rois", "expressions", "active", "values"] {
        assert_eq!(rebuilt.result["map"][key], analysis.result["map"][key]);
    }
    // Processed batches preserve the same layers, converting their coordinates
    // when the stored series has another radial unit.
    let converted = call(
        &mut session,
        "map_batch",
        json!({"path":temp.path().join("batch.h5")}),
    );
    assert_eq!(converted.result["map"]["unit"], "d_A");
    assert_eq!(converted.result["map"]["active"], "Contrast");
    let old = &analysis.result["map"]["rois"][0];
    let new = &converted.result["map"]["rois"][0];
    assert!(
        (new["min"].as_f64().unwrap() - std::f64::consts::TAU / old["max"].as_f64().unwrap()).abs()
            < 1e-9
    );
    assert!(
        (new["max"].as_f64().unwrap() - std::f64::consts::TAU / old["min"].as_f64().unwrap()).abs()
            < 1e-9
    );
    call(&mut session, "map_load", json!({"paths":[second_source]}));
    call(
        &mut session,
        "configuration",
        json!({"operation":"rename","name":"Reference"}),
    );
    call(
        &mut session,
        "configuration",
        json!({"operation":"duplicate"}),
    );
    call(
        &mut session,
        "configuration",
        json!({"operation":"rename","name":"Sample"}),
    );
    call(
        &mut session,
        "integration_settings",
        json!({"bins":32,"use_mask":false}),
    );
    call(
        &mut session,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    let before = call(&mut session, "state", json!({}));
    let project = temp.path().join("combined.dio");
    call(&mut session, "save_project", json!({"path":project}));
    // Simulate reopening on a machine without the acquisition files. Close
    // the original session's live HDF5 reader before removing them on Windows.
    drop(session);
    fs::remove_file(&source).unwrap();
    fs::remove_file(&second_source).unwrap();
    fs::remove_file(&mask).unwrap();
    fs::remove_file(&poni).unwrap();
    let mut restored = Session::new(root());
    let reopened = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(
        reopened.result["state"]["configurationLabels"],
        json!(["Reference", "Sample"])
    );
    assert_eq!(reopened.result["state"]["unit"], "q_A^-1");
    assert_eq!(reopened.result["state"]["bins"], 48);
    assert_eq!(reopened.result["pattern"], before.result["pattern"]);
    assert_eq!(reopened.result["map"]["points"], 3);
    assert_eq!(mask_bytes(&reopened), expected_mask);
    let sample = call(
        &mut restored,
        "configuration",
        json!({"operation":"select","index":1}),
    );
    assert_eq!(sample.result["state"]["bins"], 32);
    assert_eq!(sample.result["state"]["useMask"], false);
}

#[test]
fn map_inspection_contours_survive_frame_changes_but_follow_geometry_changes() {
    let mut session = Session::new(root());
    let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/combined-counts.h5");
    let geometry = json!({"dist":0.2,"poni1":0.0032,"poni2":0.004,"rot1":0.,"rot2":0.,"rot3":0.,"pixel1":0.0001,"pixel2":0.0001,"wavelength":4e-11,"polarization_factor":0.});
    call(
        &mut session,
        "manual_geometry",
        json!({"convention":"pyfai","values":geometry}),
    );
    call(
        &mut session,
        "integration_settings",
        json!({"bins":48,"cake_bins":12}),
    );
    call(
        &mut session,
        "open_image",
        json!({"path":source,"dataset":"/counts"}),
    );
    call(&mut session, "map_load", json!({"paths":[source]}));
    let before = call(
        &mut session,
        "validation_position",
        json!({"source":"cake","x":0.5,"azimuth":15.}),
    );
    let selected = call(
        &mut session,
        "map_select",
        json!({"index":1,"reintegrate":true}),
    );
    assert_eq!(
        selected.result["linked"], before.result["linked"],
        "unchanged geometry must retain inspection without a restore request"
    );
    let integrated = call(&mut session, "integrate", json!({}));
    assert_eq!(integrated.result["linked"], before.result["linked"]);
    let after = call(
        &mut session,
        "validation_position",
        json!({"source":"cake","x":0.5,"azimuth":15.}),
    );
    assert_eq!(after.result["linked"], before.result["linked"]);
    let mut changed = geometry;
    changed["dist"] = json!(0.3);
    call(
        &mut session,
        "manual_geometry",
        json!({"convention":"pyfai","values":changed}),
    );
    let recalculated = call(
        &mut session,
        "validation_position",
        json!({"source":"cake","x":0.5,"azimuth":15.}),
    );
    assert_ne!(
        recalculated.result["linked"]["contours"],
        before.result["linked"]["contours"]
    );
}

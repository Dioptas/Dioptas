//! Regressions for accepted settings, removed references and numerical exports
//! across actual command/project boundaries, rather than mocked state.
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{
    fs,
    path::{Path, PathBuf},
};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
}
fn invoke(session: &mut Session, action: &str, payload: Value) -> Reply {
    session.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    })
}
fn call(session: &mut Session, action: &str, payload: Value) -> Reply {
    let reply = invoke(session, action, payload);
    assert_eq!(reply.result["ok"], true, "{action}: {}", reply.result);
    reply
}
fn plane(path: &Path, shape: [usize; 2]) {
    let file = hdf5::File::create(path).unwrap();
    file.new_dataset::<f64>()
        .shape(shape)
        .create("counts")
        .unwrap()
        .write_raw(&vec![100.; shape[0] * shape[1]])
        .unwrap();
}

#[test]
fn every_accepted_background_boundary_survives_project_reopen() {
    let dir = tempfile::tempdir().unwrap();
    let pattern = dir.path().join("pattern.xy");
    fs::write(
        &pattern,
        (1..=16)
            .map(|i| format!("{i} {}\n", 100 + i))
            .collect::<String>(),
    )
    .unwrap();
    let project = dir.path().join("settings.dio");
    let mut session = Session::new(root());
    call(
        &mut session,
        "integration_open_pattern",
        json!({"path":pattern}),
    );
    // Disabled drafts retain the highest supported values without performing
    // 99,999 smoothing iterations; enabled order 101 covers the original failure.
    for settings in [
        json!({"enabled":false,"smoothing":0.1,"iterations":99999,"order":1000}),
        json!({"enabled":true,"smoothing":0.1,"iterations":1,"order":101}),
        json!({"enabled":false,"smoothing":1e-9,"iterations":1,"order":0}),
    ] {
        let before = call(&mut session, "integration_background", settings);
        call(&mut session, "save_project", json!({"path":project}));
        let reopened = call(&mut session, "open_project", json!({"path":project}));
        assert_eq!(
            reopened.result["state"]["integration"]["patternBackground"],
            before.result["state"]["integration"]["patternBackground"]
        );
        let failed = invoke(
            &mut session,
            "integration_background",
            json!({"enabled":false,"order":1001}),
        );
        assert_eq!(failed.result["ok"], false);
        let after = call(&mut session, "state", json!({}));
        assert_eq!(
            after.result["state"]["integration"]["patternBackground"],
            reopened.result["state"]["integration"]["patternBackground"]
        );
    }
}

#[test]
fn removed_flat_stays_removed_after_resave_with_or_without_new_dimensions() {
    let dir = tempfile::tempdir().unwrap();
    let first = dir.path().join("first.h5");
    let second = dir.path().join("second.h5");
    plane(&first, [4, 4]);
    plane(&second, [6, 6]);
    for switch_dimensions in [false, true] {
        let project = dir.path().join(format!("flat_{switch_dimensions}.dio"));
        let mut session = Session::new(root());
        call(&mut session, "open_image", json!({"path":first}));
        call(
            &mut session,
            "integration_flat_field",
            json!({"path":first}),
        );
        call(&mut session, "save_project", json!({"path":project}));
        call(&mut session, "open_project", json!({"path":project}));
        call(
            &mut session,
            "integration_flat_field",
            json!({"reset":true}),
        );
        if switch_dimensions {
            call(
                &mut session,
                "open_image",
                json!({"path":second,"reset_image_state":true}),
            );
        }
        call(&mut session, "save_project", json!({"path":project}));
        let reopened = call(&mut session, "open_project", json!({"path":project}));
        assert_eq!(
            reopened.result["state"]["integration"]["flatField"],
            json!({"filename":null,"enabled":false})
        );
        // The serialized reference itself must be gone, not merely ignored.
        let f = hdf5::File::open(&project).unwrap();
        let raw = f
            .dataset("state")
            .unwrap()
            .read_scalar::<hdf5::types::VarLenUnicode>()
            .unwrap();
        let state: Value = serde_json::from_str(raw.as_str()).unwrap();
        assert!(state["configurations"][0]["native_desktop"]["flat_response"].is_null());
    }
}

#[test]
#[cfg(feature = "dioptrin")]
fn manual_and_automatic_d_axis_fxye_exports_keep_physical_angles_and_errors() {
    let dir = tempfile::tempdir().unwrap();
    let image = dir.path().join("source.h5");
    plane(&image, [24, 32]);
    let calibration = dir.path().join("geometry.poni");
    fs::write(&calibration,"PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.13\nPoni1: 0.0012\nPoni2: 0.0016\nRot1: 0.008\nRot2: -0.013\nRot3: 0.02\nSplineFile: None\nWavelength: 5e-11\n").unwrap();
    let mut session = Session::new(root());
    call(
        &mut session,
        "open_calibration",
        json!({"path":calibration}),
    );
    call(
        &mut session,
        "integration_settings",
        json!({"bins":16,"cake_bins":4,"unit":"d_A","trim_zeros":false,"poisson_errors":true}),
    );
    let pattern = call(&mut session, "open_image", json!({"path":image})).result["pattern"].clone();
    let manual = dir.path().join("manual.fxye");
    call(
        &mut session,
        "integration_save_pattern",
        json!({"path":manual}),
    );
    call(
        &mut session,
        "integration_output_directory",
        json!({"path":dir.path()}),
    );
    call(
        &mut session,
        "integration_settings",
        json!({"auto_save":true,"formats":[".fxye"]}),
    );
    for file in [&manual, &dir.path().join("source.fxye")] {
        let text = fs::read_to_string(file).unwrap();
        assert!(text.contains("# 2th_deg\tI\tsigma"), "{text}");
        let rows: Vec<Vec<f64>> = text
            .lines()
            .skip_while(|l| !l.starts_with("BANK "))
            .skip(1)
            .map(|l| l.split_whitespace().map(|v| v.parse().unwrap()).collect())
            .collect();
        assert_eq!(rows.len(), pattern["x"].as_array().unwrap().len());
        for (i, row) in rows.iter().enumerate() {
            let d = pattern["x"][i].as_f64().unwrap();
            let degrees = 2. * (0.5 / (2. * d)).asin().to_degrees();
            assert!((row[0] - 100. * degrees).abs() < 1e-10);
            assert_eq!(row[1], pattern["y"][i].as_f64().unwrap());
            assert_eq!(row[2], pattern["sigma"][i].as_f64().unwrap());
        }
    }
    let retained = call(&mut session, "state", json!({}));
    assert_eq!(retained.result["pattern"]["x"], pattern["x"]);
    assert_eq!(retained.result["pattern"]["unit"], "d_A");
}

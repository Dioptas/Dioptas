use dioptas_backend::{
    Session,
    control::Control,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{
    path::{Path, PathBuf},
    sync::Arc,
};
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
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
    assert_eq!(r.result["ok"], true, "{}", r.result);
    r
}
fn image(path: &Path) {
    let mut encoder =
        tiff::encoder::TiffEncoder::new(std::fs::File::create(path).unwrap()).unwrap();
    encoder
        .write_image::<tiff::encoder::colortype::Gray16>(12, 8, &(0..96).collect::<Vec<_>>())
        .unwrap();
}
#[test]
fn configurations_and_owned_project_pixels_survive_without_sources() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("raw.tif");
    image(&source);
    let mut s = Session::new(root());
    let first = call(&mut s, "open_image", json!({"path":source}));
    call(
        &mut s,
        "configuration",
        json!({"operation":"rename","name":"Reference"}),
    );
    let duplicated = call(&mut s, "configuration", json!({"operation":"duplicate"}));
    assert_ne!(
        duplicated.result["state"]["configurationContext"],
        first.result["state"]["configurationContext"]
    );
    call(
        &mut s,
        "configuration",
        json!({"operation":"rename","name":"Sample"}),
    );
    call(
        &mut s,
        "integration_settings",
        json!({"bins":75,"use_mask":false}),
    );
    call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    let r = call(&mut s, "state", json!({}));
    assert_eq!(
        r.result["state"]["configurationContext"],
        first.result["state"]["configurationContext"]
    );
    assert_eq!(r.result["state"]["bins"], 1000);
    assert_eq!(
        r.result["rawImage"]["bufferId"],
        first.result["rawImage"]["bufferId"]
    );
    let path = temp.path().join("session.dio");
    call(&mut s, "save_project", json!({"path":path}));
    std::fs::remove_file(source).unwrap();
    let mut restored = Session::new(root());
    let r = call(&mut restored, "open_project", json!({"path":path}));
    assert_eq!(
        r.result["state"]["configurationLabels"],
        json!(["Reference", "Sample"])
    );
    assert_eq!(
        r.result["rawImage"]["bufferId"],
        first.result["rawImage"]["bufferId"]
    );
    let r = call(
        &mut restored,
        "configuration",
        json!({"operation":"select","index":1}),
    );
    assert_eq!(r.result["state"]["bins"], 75);
    assert_eq!(r.result["state"]["useMask"], false);
    // With no neighboring source file, navigation quietly retains the owned pixels and controls.
    let before = call(&mut restored, "state", json!({})).result;
    assert_eq!(
        call(&mut restored, "next_image", json!({"direction":1})).result,
        json!({"ok":true,"imageUnavailable":true})
    );
    assert_eq!(call(&mut restored, "state", json!({})).result, before);
}
#[test]
fn failed_or_cancelled_projects_preserve_session_and_existing_file() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("raw.tif");
    image(&source);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":source}));
    let target = temp.path().join("project.dio");
    call(&mut s, "save_project", json!({"path":target}));
    let original = std::fs::read(&target).unwrap();
    let before = call(&mut s, "state", json!({})).result;
    for action in ["open_project", "save_project"] {
        let control = Arc::new(Control::default());
        control.cancel();
        let r = s.invoke_controlled(&request(action, json!({"path":target})), control);
        assert_eq!(r.result["cancelled"], true, "{}", r.result);
        assert_eq!(call(&mut s, "state", json!({})).result, before);
        assert_eq!(std::fs::read(&target).unwrap(), original);
    }
    let bad = temp.path().join("broken.dio");
    std::fs::write(&bad, b"not hdf5").unwrap();
    assert_eq!(
        s.invoke(&request("open_project", json!({"path":bad})))
            .result["ok"],
        false
    );
    assert_eq!(call(&mut s, "state", json!({})).result, before);
}
#[test]
fn shared_overlays_keep_unique_ids_after_project_reload_and_undo() {
    let temp = tempfile::tempdir().unwrap();
    let curve = temp.path().join("curve.xy");
    std::fs::write(&curve, "1 10\n2 20\n3 30\n").unwrap();
    let mut s = Session::new(root());
    call(&mut s, "integration_open_pattern", json!({"path":curve}));
    for _ in 0..3 {
        call(
            &mut s,
            "integration_overlay",
            json!({"operation":"capture"}),
        );
    }
    let path = temp.path().join("patterns.dio");
    call(&mut s, "save_project", json!({"path":path}));
    call(&mut s, "open_project", json!({"path":path}));
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"capture"}),
    );
    call(&mut s, "undo_calibration", json!({}));
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"capture"}),
    );
    let r = call(&mut s, "state", json!({}));
    let ids = r.result["state"]["integration"]["overlays"]
        .as_array()
        .unwrap()
        .iter()
        .map(|o| o["uid"].as_str().unwrap())
        .collect::<std::collections::BTreeSet<_>>();
    assert_eq!(ids.len(), 4);
    assert!(!ids.contains("native-overlay-4"));
}

#[test]
fn removing_a_shared_background_does_not_leave_unloadable_inactive_configurations() {
    let temp = tempfile::tempdir().unwrap();
    let curve = temp.path().join("curve.xy");
    std::fs::write(&curve, "1 10\n2 20\n3 30\n").unwrap();
    let mut s = Session::new(root());
    call(&mut s, "integration_open_pattern", json!({"path":curve}));
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"capture_background"}),
    );
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"remove","index":0}),
    );
    let path = temp.path().join("background.dio");
    call(&mut s, "save_project", json!({"path":path}));
    call(&mut s, "open_project", json!({"path":path}));
    let r = call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(
        r.result["state"]["integration"]["patternBackground"]["overlay"],
        false
    );
    assert_eq!(r.result["pattern"]["y"], json!([10., 20., 30.]));
}
#[test]
fn project_caches_retain_nonfinite_detector_samples_and_display_identity() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("pixels.h5");
    {
        let file = hdf5::File::create(&source).unwrap();
        file.new_dataset::<f64>()
            .shape([2, 3])
            .create("frames")
            .unwrap()
            .write_raw(&[1., 2., f64::NAN, f64::INFINITY, f64::NEG_INFINITY, 10.])
            .unwrap();
    }
    let mut s = Session::new(root());
    let before = call(
        &mut s,
        "open_image",
        json!({"path":source,"dataset":"frames"}),
    );
    let path = temp.path().join("pixels.dio");
    call(&mut s, "save_project", json!({"path":path}));
    std::fs::remove_file(source).unwrap();
    let after = call(&mut s, "open_project", json!({"path":path}));
    assert_eq!(
        before.result["rawImage"]["bufferId"],
        after.result["rawImage"]["bufferId"]
    );
    assert_eq!(
        before.result["rawImage"]["histogram"],
        after.result["rawImage"]["histogram"]
    );
}

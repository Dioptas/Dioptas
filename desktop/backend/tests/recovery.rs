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
fn call(session: &mut Session, action: &str, payload: Value) -> Reply {
    let reply = session.invoke(&request(action, payload));
    assert_eq!(reply.result["ok"], true, "{}", reply.result);
    reply
}
fn image(path: &Path) {
    tiff::encoder::TiffEncoder::new(std::fs::File::create(path).unwrap())
        .unwrap()
        .write_image::<tiff::encoder::colortype::Gray16>(12, 8, &(0..96).collect::<Vec<_>>())
        .unwrap();
}
#[test]
fn restart_restores_science_owned_pixels_and_user_project_identity() {
    let dir = tempfile::tempdir().unwrap();
    let source = dir.path().join("raw.tif");
    image(&source);
    let recovery = dir.path().join("native-session-v1.dio");
    let project = dir.path().join("experiment.dio");
    let mut old = Session::new(root());
    let original = call(&mut old, "open_image", json!({"path":source}));
    call(&mut old, "save_project", json!({"path":project}));
    let user_bytes = std::fs::read(&project).unwrap();
    call(&mut old, "configuration", json!({"operation":"duplicate"}));
    call(
        &mut old,
        "configuration",
        json!({"operation":"rename","name":"Last work"}),
    );
    call(
        &mut old,
        "integration_settings",
        json!({"bins":75,"use_mask":false}),
    );
    let ui = json!({"mode":"integration","logImage":true,"limits":[12,345],"cakeLog":false,"cakeLimits":[1,99]});
    call(
        &mut old,
        "recovery_checkpoint",
        json!({"path":recovery,"ui":ui}),
    );
    assert_eq!(
        call(&mut old, "state", json!({})).result["state"]["projectName"],
        "experiment.dio"
    );
    assert_eq!(std::fs::read(&project).unwrap(), user_bytes);
    drop(old);
    std::fs::remove_file(&source).unwrap();
    let checkpoint = std::fs::read(&recovery).unwrap();
    let mut new = Session::new(root());
    let restored = call(&mut new, "recovery_restore", json!({"path":recovery}));
    assert_eq!(restored.result["state"]["projectName"], "experiment.dio");
    assert_eq!(restored.result["state"]["configurationIndex"], 1);
    assert_eq!(
        restored.result["state"]["configurationLabels"][1],
        "Last work"
    );
    assert_eq!(restored.result["state"]["bins"], 75);
    assert_eq!(restored.result["state"]["useMask"], false);
    assert_eq!(
        restored.result["state"]["integration"]["autoProcess"],
        false
    );
    assert_eq!(restored.result["state"]["integration"]["autoSave"], false);
    assert_eq!(
        restored.result["rawImage"]["bufferId"],
        original.result["rawImage"]["bufferId"]
    );
    assert_eq!(restored.result["recoveryUi"], ui);
    assert_eq!(
        restored.result["missingSources"],
        json!([original.result["state"]["imagePath"]])
    );
    assert_eq!(std::fs::read(&recovery).unwrap(), checkpoint);
    let exported = dir.path().join("saved-after-restore.dio");
    call(&mut new, "save_project", json!({"path":exported}));
    assert!(
        !hdf5::File::open(exported)
            .unwrap()
            .link_exists("native_recovery")
    );
}
#[test]
fn unsaved_identity_and_failed_cancelled_writes_or_loads_preserve_last_good_snapshot() {
    let dir = tempfile::tempdir().unwrap();
    let recovery = dir.path().join("native-session-v1.dio");
    let mut session = Session::new(root());
    call(
        &mut session,
        "recovery_checkpoint",
        json!({"path":recovery}),
    );
    let before = std::fs::read(&recovery).unwrap();
    let mut restored = Session::new(root());
    assert!(call(&mut restored,"recovery_restore",json!({"path":recovery})).result["state"]["projectName"].is_null());
    let control = Arc::new(Control::default());
    control.cancel();
    let failed = session.invoke_controlled(
        &request(
            "recovery_checkpoint",
            json!({"path":recovery,"ui":{"mode":"mask"}}),
        ),
        control,
    );
    assert!(
        failed.result["ok"] != true || failed.result["cancelled"] == true,
        "{}",
        failed.result
    );
    assert_eq!(std::fs::read(&recovery).unwrap(), before);
    let failed = session.invoke(&request(
        "recovery_checkpoint",
        json!({"path":recovery,"ui":[]}),
    ));
    assert_eq!(failed.result["ok"], false);
    assert_eq!(std::fs::read(&recovery).unwrap(), before);
    let corrupt = dir.path().join("corrupt.dio");
    std::fs::write(&corrupt, b"truncated checkpoint").unwrap();
    let state = call(&mut session, "state", json!({})).result["state"].clone();
    assert_eq!(
        session
            .invoke(&request("recovery_restore", json!({"path":corrupt})))
            .result["ok"],
        false
    );
    assert_eq!(
        call(&mut session, "state", json!({})).result["state"],
        state
    );
    assert_eq!(std::fs::read(&recovery).unwrap(), before);
    // A plain user project is not a recovery checkpoint (no implicit migration).
    let plain = dir.path().join("legacy-or-user.dio");
    call(&mut session, "save_project", json!({"path":plain}));
    let state = call(&mut session, "state", json!({})).result["state"].clone();
    assert_eq!(
        session
            .invoke(&request("recovery_restore", json!({"path":plain})))
            .result["ok"],
        false
    );
    assert_eq!(
        call(&mut session, "state", json!({})).result["state"],
        state
    );
}

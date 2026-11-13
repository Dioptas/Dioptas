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
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
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
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn image(p: &Path, hit: f64) {
    let file = hdf5::File::create(p).unwrap();
    let mut values = vec![100.; 99];
    values[4 * 11 + 5] = hit;
    file.new_dataset::<f64>()
        .shape([9, 11])
        .create("frames")
        .unwrap()
        .write_raw(&values)
        .unwrap();
}
#[test]
fn cosmic_adds_one_owned_mask_edit_and_never_changes_source_or_calibration() {
    let temp = tempfile::tempdir().unwrap();
    let p = temp.path().join("detector.h5");
    image(&p, 10000.);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":p,"dataset":"frames"}));
    call(
        &mut s,
        "manual_geometry",
        json!({"convention":"pyfai","values":{"dist":0.1,"poni1":0.00045,"poni2":0.00055,"rot1":0.,"rot2":0.,"rot3":0.,"pixel1":0.0001,"pixel2":0.0001,"wavelength":5e-11,"polarization_factor":0.99},"defer_integration":true}),
    );
    call(
        &mut s,
        "save_calibration",
        json!({"path":temp.path().join("source.poni")}),
    );
    call(
        &mut s,
        "mask_edit",
        json!({"operation":"rectangle","points":[[1,1],[3,3]],"defer_integration":true}),
    );
    let before = call(&mut s, "state", json!({}));
    let result = call(
        &mut s,
        "mask_edit",
        json!({"operation":"cosmic","erase":true,"defer_integration":true}),
    );
    assert_eq!(result.result["state"]["maskedPixels"], 5);
    assert_eq!(result.result["state"]["maskDetails"]["mode"], false);
    let after = call(&mut s, "state", json!({}));
    assert_eq!(after.result["rawImage"], before.result["rawImage"]);
    assert_eq!(after.result["image"], before.result["image"]);
    assert_eq!(
        after.result["state"]["calibration"],
        before.result["state"]["calibration"]
    );
    let undone = call(&mut s, "undo_mask", json!({"defer_integration":true}));
    assert_eq!(undone.result["state"]["maskedPixels"], 4);
    assert_eq!(undone.result["state"]["maskDetails"]["mode"], true);
    let redone = call(&mut s, "redo_mask", json!({"defer_integration":true}));
    assert_eq!(redone.result["mask"], result.result["mask"]);
}
#[test]
fn cancelled_or_nonfinite_cosmic_keeps_pixels_masks_and_redo() {
    let temp = tempfile::tempdir().unwrap();
    let p = temp.path().join("detector.h5");
    image(&p, 10000.);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":p,"dataset":"frames"}));
    call(
        &mut s,
        "mask_edit",
        json!({"operation":"rectangle","points":[[1,1],[3,3]]}),
    );
    call(&mut s, "undo_mask", json!({}));
    let baseline = call(&mut s, "state", json!({})).result;
    let control = Arc::new(Control::default());
    control.cancel();
    let r = s.invoke_controlled(
        &request("mask_edit", json!({"operation":"cosmic"})),
        control,
    );
    assert_eq!(r.result["cancelled"], true);
    assert_eq!(call(&mut s, "state", json!({})).result, baseline);
    call(&mut s, "redo_mask", json!({}));
    let invalid = temp.path().join("nonfinite.h5");
    image(&invalid, f64::NAN);
    call(
        &mut s,
        "open_image",
        json!({"path":invalid,"dataset":"frames"}),
    );
    let baseline = call(&mut s, "state", json!({})).result;
    let r = s.invoke(&request("mask_edit", json!({"operation":"cosmic"})));
    assert_eq!(r.result["ok"], false);
    assert!(r.result["error"].as_str().unwrap().contains("finite"));
    assert_eq!(call(&mut s, "state", json!({})).result, baseline);
}

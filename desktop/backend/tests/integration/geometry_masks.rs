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
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn image(p: &Path) {
    tiff::encoder::TiffEncoder::new(std::fs::File::create(p).unwrap())
        .unwrap()
        .write_image::<tiff::encoder::colortype::Gray32>(
            8,
            5,
            &(0..40).map(|i| 16777217 + i).collect::<Vec<_>>(),
        )
        .unwrap();
}
fn bytes(r: &Reply, key: &str) -> Vec<u8> {
    r.buffers
        .iter()
        .find(|b| b.id == r.result[key]["bufferId"].as_str().unwrap())
        .unwrap()
        .bytes
        .to_vec()
}
#[test]
fn transforms_retain_source_precision_picks_and_mask_history_in_both_feature_modes() {
    let temp = tempfile::tempdir().unwrap();
    let p = temp.path().join("counts.tif");
    image(&p);
    let mut s = Session::new(root());
    let initial = call(&mut s, "open_image", json!({"path":p}));
    call(
        &mut s,
        "mask_edit",
        json!({"operation":"rectangle","points":[[1.,1.],[4.,3.]]}),
    );
    call(
        &mut s,
        "pick_peak",
        json!({"x":6,"y":3,"ring":1,"automatic":false,"search_size":1}),
    );
    let before = call(&mut s, "state", json!({}));
    let peaks = temp.path().join("peaks.json");
    call(&mut s, "save_peaks", json!({"path":peaks}));
    let r = call(
        &mut s,
        "image_transform",
        json!({"operation":"rotate_right"}),
    );
    assert_eq!(r.result["state"]["shape"], json!([8, 5]));
    assert_eq!(r.result["state"]["calibration"]["picks"], json!([]));
    assert_eq!(
        r.result["nativeSource"]["dtype"],
        initial.result["nativeSource"]["dtype"]
    );
    // np.rot90 of the bottom-up raw view: output [0,0] is input [0,7].
    let pixel = call(
        &mut s,
        "pixel",
        json!({"x":0,"y":0,"source":"raw_detector"}),
    );
    assert_eq!(pixel.result["pixel"]["value"], 16777256.);
    assert_eq!(
        s.invoke(&request("load_peaks", json!({"path":peaks})))
            .result["ok"],
        false
    );
    let undone = call(&mut s, "undo_calibration", json!({}));
    assert_eq!(bytes(&undone, "rawImage"), bytes(&before, "rawImage"));
    assert_eq!(bytes(&undone, "mask"), bytes(&before, "mask"));
    assert_eq!(
        undone.result["state"]["calibration"]["picks"],
        before.result["state"]["calibration"]["picks"]
    );
    let redone = call(&mut s, "redo_calibration", json!({}));
    assert_eq!(bytes(&redone, "mask"), bytes(&r, "mask"));
    let cleared = call(&mut s, "undo_mask", json!({}));
    assert_eq!(cleared.result["state"]["maskedPixels"], 0);
    let painted = call(&mut s, "redo_mask", json!({}));
    assert_eq!(bytes(&painted, "mask"), bytes(&r, "mask"));
    let reset = call(&mut s, "image_transform", json!({"operation":"reset"}));
    assert_eq!(bytes(&reset, "rawImage"), bytes(&initial, "rawImage"));
    for _ in 0..4 {
        call(
            &mut s,
            "image_transform",
            json!({"operation":"rotate_left"}),
        );
    }
    let roundtrip = call(&mut s, "state", json!({}));
    assert_eq!(bytes(&roundtrip, "rawImage"), bytes(&initial, "rawImage"));
}
#[test]
fn geometric_edits_are_atomic_and_history_covers_unmask_mode() {
    let temp = tempfile::tempdir().unwrap();
    let p = temp.path().join("counts.tif");
    image(&p);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":p}));
    let r = call(
        &mut s,
        "mask_edit",
        json!({"operation":"rectangle","points":[[1.5,1.5],[6.5,3.5]]}),
    );
    assert_eq!(r.result["state"]["maskedPixels"], 8);
    let r = call(
        &mut s,
        "mask_edit",
        json!({"operation":"rectangle","points":[[2,2],[3,3]],"erase":true}),
    );
    assert_eq!(r.result["state"]["maskedPixels"], 7);
    assert_eq!(r.result["state"]["maskDetails"]["mode"], false);
    let r = call(&mut s, "undo_mask", json!({}));
    assert_eq!(r.result["state"]["maskedPixels"], 8);
    assert_eq!(r.result["state"]["maskDetails"]["mode"], true);
    let baseline = call(&mut s, "state", json!({})).result;
    for action in ["image_transform", "mask_edit"] {
        let control = Arc::new(Control::default());
        control.cancel();
        let args = if action == "image_transform" {
            json!({"operation":"rotate_right"})
        } else {
            json!({"operation":"invert"})
        };
        let r = s.invoke_controlled(&request(action, args), control);
        assert_eq!(r.result["cancelled"], true, "{}", r.result);
        assert_eq!(call(&mut s, "state", json!({})).result, baseline);
    }
    for args in [
        json!({"operation":"polygon","points":[[1,2],[3,4]]}),
        json!({"operation":"arc","points":[[1,1],[2,2],[3,3],[4,4]]}),
        json!({"operation":"above","threshold":"invalid"}),
        json!({"operation":"rectangle","points":[[1,1],[8,4]]}),
        json!({"operation":"invert","erase":1}),
    ] {
        assert_eq!(s.invoke(&request("mask_edit", args)).result["ok"], false);
        assert_eq!(call(&mut s, "state", json!({})).result, baseline);
    }
    call(&mut s, "redo_mask", json!({}));
}
#[test]
fn transformed_configurations_and_offline_project_caches_are_independent() {
    let temp = tempfile::tempdir().unwrap();
    let p = temp.path().join("counts.tif");
    image(&p);
    let mut s = Session::new(root());
    let initial = call(&mut s, "open_image", json!({"path":p}));
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    let transformed = call(
        &mut s,
        "image_transform",
        json!({"operation":"rotate_left"}),
    );
    let target = temp.path().join("rotated.dio");
    call(&mut s, "save_project", json!({"path":target}));
    std::fs::remove_file(p).unwrap();
    let r = call(&mut s, "open_project", json!({"path":target}));
    assert_eq!(bytes(&r, "rawImage"), bytes(&transformed, "rawImage"));
    let r = call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(bytes(&r, "rawImage"), bytes(&initial, "rawImage"));
    call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":1}),
    );
    let r = call(&mut s, "image_transform", json!({"operation":"reset"}));
    assert_eq!(bytes(&r, "rawImage"), bytes(&initial, "rawImage"));
}

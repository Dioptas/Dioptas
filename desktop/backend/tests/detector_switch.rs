//! Loading order, source-coordinate resets, atomic failures and project ownership.
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
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
fn image(path: &Path, shape: [usize; 2], value: u16) {
    tiff::encoder::TiffEncoder::new(std::fs::File::create(path).unwrap())
        .unwrap()
        .write_image::<tiff::encoder::colortype::Gray16>(
            shape[1] as u32,
            shape[0] as u32,
            &vec![value; shape[0] * shape[1]],
        )
        .unwrap();
}
fn poni(path: &Path, shape: Option<[usize; 2]>) {
    let config = match shape {
        Some(shape) => json!({"pixel1":1e-4,"pixel2":1.2e-4,"max_shape":shape,"orientation":3}),
        None => json!({"pixel1":1e-4,"pixel2":1.2e-4}),
    };
    std::fs::write(path, format!("poni_version: 2.1\nDetector: Detector\nDetector_config: {config}\nDistance: 0.25\nPoni1: 0.001\nPoni2: 0.001\nRot1: 0\nRot2: 0\nRot3: 0\nWavelength: 6e-11\n")).unwrap();
}
fn settings(s: &mut Session) {
    call(
        s,
        "integration_settings",
        json!({"bins":24,"cake_bins":12,"poisson_errors":true}),
    );
}
fn orient_mask(s: &mut Session) {
    call(s, "mask_stroke", json!({"points":[[5,5]],"radius":2}));
    call(s, "image_transform", json!({"operation":"rotate_right"}));
}
#[test]
fn incompatible_calibration_can_be_loaded_first_and_roundtrips_without_old_inputs() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("old.tif");
    let b = d.path().join("new.tif");
    let pa = d.path().join("old.poni");
    let pb = d.path().join("new.poni");
    image(&a, [24, 32], 100);
    image(&b, [16, 20], 300);
    poni(&pa, Some([24, 32]));
    poni(&pb, Some([16, 20]));
    let mut s = Session::new(root());
    settings(&mut s);
    call(&mut s, "open_image", json!({"path":a}));
    call(&mut s, "open_calibration", json!({"path":pa}));
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"capture"}),
    );
    orient_mask(&mut s);
    let before = call(&mut s, "state", json!({}));
    let pending = call(&mut s, "open_calibration", json!({"path":pb}));
    assert_eq!(pending.result["cancelled"], true);
    assert_eq!(
        pending.result["calibrationChange"]["calibrationShape"],
        json!([16, 20])
    );
    assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    let loaded = call(
        &mut s,
        "open_calibration",
        json!({"path":pb,"clear_image":true}),
    );
    assert_eq!(loaded.result["clearImage"], true);
    assert_eq!(loaded.result["state"]["hasImage"], false);
    assert_eq!(loaded.result["state"]["calibrated"], true);
    assert_eq!(loaded.result["state"]["calibration"]["canUndo"], false);
    assert!(loaded.result["pattern"].is_null() && loaded.result["cake"].is_null());
    assert_eq!(
        loaded.result["state"]["integration"]["overlays"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    let p = d.path().join("waiting-for-new-image.dio");
    call(&mut s, "save_project", json!({"path":p}));
    // The new image/calibration order gives the same real integration as the reverse.
    let mut image_first = Session::new(root());
    settings(&mut image_first);
    call(&mut image_first, "open_image", json!({"path":b}));
    let expected = call(&mut image_first, "open_calibration", json!({"path":pb}));
    std::fs::remove_file(a).unwrap();
    std::fs::remove_file(pa).unwrap();
    std::fs::remove_file(pb).unwrap();
    let mut fresh = Session::new(root());
    let restored = call(&mut fresh, "open_project", json!({"path":p}));
    assert_eq!(restored.result["state"]["calibrated"], true);
    assert_eq!(restored.result["state"]["hasImage"], false);
    let actual = call(&mut fresh, "open_image", json!({"path":b}));
    assert!(actual.result.get("imageChange").is_none());
    for field in ["x", "y", "sigma"] {
        assert_eq!(
            actual.result["pattern"][field],
            expected.result["pattern"][field]
        );
    }
    assert_eq!(
        actual.result["state"]["geometry"],
        expected.result["state"]["geometry"]
    );
    assert_eq!(
        actual.result["state"]["calibration"]["transformations"],
        json!([])
    );
}
#[test]
fn uncalibrated_size_changes_clear_coordinates_without_resetting_experiment_preferences() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.tif");
    let b = d.path().join("b.tif");
    image(&a, [24, 32], 100);
    image(&b, [16, 20], 300);
    let mut s = Session::new(root());
    settings(&mut s);
    call(&mut s, "open_image", json!({"path":a}));
    call(
        &mut s,
        "integration_correction",
        json!({"kind":"cylinder","enabled":false,"parameters":{"radius":0.33}}),
    );
    orient_mask(&mut s);
    let before = call(&mut s, "state", json!({}));
    let r = call(&mut s, "open_image", json!({"path":b}));
    assert!(r.result.get("imageChange").is_none());
    assert!(r.result.get("calibrationReset").is_none());
    assert_eq!(r.result["state"]["calibrated"], false);
    assert_eq!(r.result["state"]["shape"], json!([16, 20]));
    assert_eq!(r.result["state"]["maskedPixels"], 0);
    assert_eq!(r.result["state"]["canUndoMask"], false);
    assert_eq!(
        r.result["state"]["calibration"]["transformations"],
        json!([])
    );
    assert_eq!(
        r.result["state"]["geometry"],
        before.result["state"]["geometry"]
    );
    for key in ["bins", "unit"] {
        assert_eq!(r.result["state"][key], before.result["state"][key]);
    }
    assert_eq!(
        r.result["state"]["integration"]["corrections"],
        before.result["state"]["integration"]["corrections"]
    );
    assert!(r.result["pattern"].is_null() && r.result["cake"].is_null());
}
#[test]
fn legacy_shapeless_calibration_can_explicitly_follow_a_new_image_and_preserves_source_pixels() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.tif");
    let b = d.path().join("b.tif");
    let p = d.path().join("legacy.poni");
    image(&a, [24, 32], 100);
    image(&b, [16, 20], 300);
    poni(&p, None);
    let mut s = Session::new(root());
    settings(&mut s);
    call(&mut s, "open_image", json!({"path":a}));
    orient_mask(&mut s);
    call(&mut s, "open_calibration", json!({"path":p}));
    let before = call(&mut s, "state", json!({}));
    let pending = call(&mut s, "open_image", json!({"path":b}));
    assert_eq!(pending.result["imageChange"]["canKeepCalibration"], true);
    assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    let r = call(
        &mut s,
        "open_image",
        json!({"path":b,"keep_calibration":true}),
    );
    assert_eq!(r.result["state"]["calibrated"], true);
    assert_eq!(r.result["state"]["calibrationName"], "legacy.poni");
    assert_eq!(r.result["state"]["maskedPixels"], 0);
    assert_eq!(
        r.result["state"]["calibration"]["transformations"],
        json!([])
    );
    assert_eq!(
        r.result["state"]["geometry"],
        before.result["state"]["geometry"]
    );
    assert!(r.result["pattern"].is_object());
    // The PONI was applied to the rotated view. Its reset source geometry swaps
    // unequal pixel pitches back, and a fresh session must reproduce that state.
    let saved = d.path().join("source.poni");
    call(&mut s, "save_calibration", json!({"path":saved}));
    let mut fresh = Session::new(root());
    settings(&mut fresh);
    call(&mut fresh, "open_image", json!({"path":b}));
    let expected = call(&mut fresh, "open_calibration", json!({"path":saved}));
    assert_eq!(r.result["pattern"], expected.result["pattern"]);
}
#[test]
fn rejected_keeps_and_unreadable_replacements_are_atomic() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.tif");
    let b = d.path().join("b.tif");
    let p = d.path().join("a.poni");
    image(&a, [24, 32], 100);
    image(&b, [16, 20], 300);
    poni(&p, Some([24, 32]));
    let mut s = Session::new(root());
    settings(&mut s);
    call(&mut s, "open_image", json!({"path":a}));
    call(&mut s, "open_calibration", json!({"path":p}));
    orient_mask(&mut s);
    let before = call(&mut s, "state", json!({}));
    for (action, args) in [
        ("open_image", json!({"path":b,"keep_calibration":true})),
        (
            "open_image",
            json!({"path":b,"keep_calibration":true,"reset_calibration":true}),
        ),
        (
            "open_image",
            json!({"path":d.path().join("missing.tif"),"keep_calibration":true}),
        ),
        (
            "open_calibration",
            json!({"path":d.path().join("missing.poni"),"clear_image":true}),
        ),
    ] {
        assert_eq!(invoke(&mut s, action, args).result["ok"], false);
        assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    }
}

#[test]
fn an_uncalibrated_remembered_detector_does_not_block_new_images_or_image_averages() {
    for average in [false, true] {
        let d = tempfile::tempdir().unwrap();
        let a = d.path().join("old.tif");
        let b = d.path().join("new.tif");
        let c = d.path().join("other.tif");
        image(&a, [128, 128], 100);
        image(&b, [16, 20], 200);
        image(&c, [16, 20], 400);
        let mut s = Session::new(root());
        call(&mut s, "open_image", json!({"path":a}));
        call(
            &mut s,
            "calibration_setup",
            json!({"detector":"Perkin","distance":220.,"wavelength":0.65}),
        );
        orient_mask(&mut s);
        let before = call(&mut s, "state", json!({}));
        let r = if average {
            call(
                &mut s,
                "open_image",
                json!({"paths":[b,c],"batch_mode":"average"}),
            )
        } else {
            call(&mut s, "open_image", json!({"path":b}))
        };
        assert!(r.result.get("imageChange").is_none());
        assert_eq!(r.result["state"]["shape"], json!([16, 20]));
        assert_eq!(r.result["state"]["calibrated"], false);
        assert_eq!(r.result["state"]["maskedPixels"], 0);
        assert_eq!(
            r.result["state"]["calibration"]["transformations"],
            json!([])
        );
        assert_eq!(r.result["state"]["calibration"]["detector"], "Custom");
        assert_eq!(r.result["state"]["calibration"]["distance"], 220.);
        assert_eq!(
            r.result["state"]["calibration"]["wavelength"],
            before.result["state"]["calibration"]["wavelength"]
        );
        let pixel = call(&mut s, "pixel", json!({"x":3,"y":4}));
        assert_eq!(
            pixel.result["pixel"]["value"],
            if average { json!(300.) } else { json!(200.) }
        );
    }
}

#[test]
fn supported_named_detector_binning_can_keep_the_loaded_calibration() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.tif");
    let b = d.path().join("b.tif");
    let p = d.path().join("perkin.poni");
    image(&a, [256, 256], 100);
    image(&b, [512, 512], 300);
    std::fs::write(&p,"poni_version: 2.1\nDetector: Perkin\nDetector_config: {\"pixel1\":0.0002,\"pixel2\":0.0002,\"orientation\":3}\nDistance: 0.2\nPoni1: 0.03\nPoni2: 0.04\nRot1: 0\nRot2: 0\nRot3: 0\nWavelength: 6e-11\n").unwrap();
    let mut s = Session::new(root());
    settings(&mut s);
    call(&mut s, "open_image", json!({"path":a}));
    call(&mut s, "open_calibration", json!({"path":p}));
    orient_mask(&mut s);
    assert_eq!(
        call(&mut s, "open_image", json!({"path":b})).result["imageChange"]["canKeepCalibration"],
        true
    );
    let actual = call(
        &mut s,
        "open_image",
        json!({"path":b,"keep_calibration":true}),
    );
    let mut fresh = Session::new(root());
    settings(&mut fresh);
    call(&mut fresh, "open_calibration", json!({"path":p}));
    let expected = call(&mut fresh, "open_image", json!({"path":b}));
    assert_eq!(actual.result["pattern"], expected.result["pattern"]);
    assert_eq!(actual.result["state"]["calibration"]["pixelX"], 800.);
    assert_eq!(
        actual.result["state"]["calibration"]["transformations"],
        json!([])
    );
}

use dioptas_backend::{
    Session,
    control::Control,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{fs, path::Path, sync::Arc};
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
fn mask(r: &Reply) -> Vec<u8> {
    let id = r.result["mask"]["bufferId"].as_str().unwrap();
    r.buffers
        .iter()
        .find(|b| b.id == id)
        .unwrap()
        .bytes
        .to_vec()
}
fn plugin(r: &Reply, i: usize) -> &Value {
    &r.result["state"]["maskDetails"]["plugins"][i]
}
fn fixture(path: &Path, hot: usize) {
    let mut header = "{'descr': '<f8', 'fortran_order': False, 'shape': (32, 32), }".to_string();
    while !(10 + header.len() + 1).is_multiple_of(64) {
        header.push(' ');
    }
    header.push('\n');
    let mut bytes = b"\x93NUMPY\x01\x00".to_vec();
    bytes.extend_from_slice(&(header.len() as u16).to_le_bytes());
    bytes.extend_from_slice(header.as_bytes());
    for i in 0..1024 {
        let row = 31 - i / 32;
        let col = i % 32;
        let v: f64 = if row * 32 + col == hot { 50000.0 } else { 50.0 };
        bytes.extend_from_slice(&v.to_le_bytes());
    }
    fs::write(path, bytes).unwrap();
}
fn session() -> (Session, tempfile::TempDir) {
    let temp = tempfile::tempdir().unwrap();
    fixture(&temp.path().join("a.npy"), 200);
    fixture(&temp.path().join("b.npy"), 700);
    let mut s = Session::new(temp.path().into());
    call(
        &mut s,
        "open_image",
        json!({"path":temp.path().join("a.npy")}),
    );
    (s, temp)
}
#[test]
fn threshold_settings_combination_and_imprint_are_one_undo_step() {
    let (mut s, _t) = session();
    let initial = call(&mut s, "state", json!({}));
    assert_eq!(
        initial.result["state"]["maskDetails"]["plugins"]
            .as_array()
            .unwrap()
            .len(),
        3
    );
    call(&mut s, "mask_stroke", json!({"points":[[3,3]],"radius":1}));
    let user = mask(&call(&mut s, "state", json!({})));
    let enabled = call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","enabled":true,"settings":{"above_value":1000}}),
    );
    assert_eq!(plugin(&enabled, 0)["maskedPixels"], 1);
    assert_eq!(mask(&enabled)[200], 1);
    assert_eq!(mask(&enabled)[3 * 32 + 3], 1);
    let imprinted = call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","imprint":true}),
    );
    assert_eq!(plugin(&imprinted, 0)["enabled"], false);
    assert_eq!(mask(&imprinted), mask(&enabled));
    let undone = call(&mut s, "undo_mask", json!({}));
    assert_eq!(plugin(&undone, 0)["enabled"], true);
    assert_eq!(mask(&undone), mask(&enabled));
    let redone = call(&mut s, "redo_mask", json!({}));
    assert_eq!(plugin(&redone, 0)["enabled"], false);
    assert_eq!(mask(&redone), mask(&enabled));
    call(&mut s, "undo_mask", json!({}));
    let disabled = call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","enabled":false}),
    );
    assert_eq!(mask(&disabled), user);
    assert_eq!(disabled.result["state"]["canRedoMask"], false);
}
#[test]
fn plugin_validation_and_cancellation_preserve_mask_settings_products_and_redo() {
    let (mut s, _) = session();
    call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","enabled":true,"settings":{"above_value":1000}}),
    );
    call(&mut s, "undo_mask", json!({}));
    let before = call(&mut s, "state", json!({}));
    for args in [
        json!({"name":"Threshold Mask","enabled":"yes"}),
        json!({"name":"Cosmic Ray Mask","settings":{"window_size":3.5}}),
        json!({"name":"Threshold Mask","enabled":true,"settings":{"above_value":1000,"extra":1}}),
        json!({"name":"Spot Mask","settings":{"method":"wrong"}}),
        json!({"name":"Threshold Mask","imprint":true}),
        json!({"name":"missing","enabled":true}),
    ] {
        let r = s.invoke(&request("mask_plugin", args));
        assert_eq!(r.result["ok"], false, "{}", r.result);
        let after = call(&mut s, "state", json!({}));
        assert_eq!(after.result, before.result);
        assert_eq!(mask(&after), mask(&before));
    }
    let cancelled = Arc::new(Control::default());
    cancelled.cancel();
    let r = s.invoke_controlled(
        &request(
            "mask_plugin",
            json!({"name":"Cosmic Ray Mask","enabled":true}),
        ),
        cancelled,
    );
    assert_eq!(r.result["ok"], false);
    assert!(r.result["error"].as_str().unwrap().contains("cancelled"));
    assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    let noop = call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","enabled":false}),
    );
    assert_eq!(noop.result["state"]["canRedoMask"], true);
}
#[test]
fn dynamic_plugins_recompute_on_same_shape_images_and_after_disabled_intervals() {
    let (mut s, t) = session();
    call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","enabled":true,"settings":{"above_value":1000}}),
    );
    let new = call(&mut s, "open_image", json!({"path":t.path().join("b.npy")}));
    assert_eq!(mask(&new)[200], 0);
    assert_eq!(mask(&new)[700], 1);
    call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","enabled":false}),
    );
    call(&mut s, "open_image", json!({"path":t.path().join("a.npy")}));
    let again = call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","enabled":true}),
    );
    assert_eq!(mask(&again)[200], 1);
    assert_eq!(mask(&again)[700], 0);
    call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","enabled":false}),
    );
    let cosmic = call(
        &mut s,
        "mask_plugin",
        json!({"name":"Cosmic Ray Mask","enabled":true}),
    );
    assert_eq!(mask(&cosmic).iter().filter(|&&v| v != 0).count(), 1);
    assert_eq!(mask(&cosmic)[200], 1);
    let moved = call(&mut s, "open_image", json!({"path":t.path().join("b.npy")}));
    assert_eq!(mask(&moved)[200], 0);
    assert_eq!(mask(&moved)[700], 1);
    let undo = call(&mut s, "undo_mask", json!({}));
    assert_eq!(plugin(&undo, 0)["enabled"], false);
    assert_eq!(plugin(&undo, 1)["enabled"], false);
    assert_eq!(mask(&undo)[700], 0);
    assert_eq!(mask(&undo)[200], 0);
    let redo = call(&mut s, "redo_mask", json!({}));
    assert_eq!(plugin(&redo, 1)["enabled"], true);
    assert_eq!(mask(&redo)[700], 1);
    assert_eq!(mask(&redo)[200], 0);
}
#[test]
fn spot_geometry_requirement_is_explicit_without_the_optional_engine() {
    let (mut s, _) = session();
    let r = s.invoke(&request(
        "mask_plugin",
        json!({"name":"Spot Mask","enabled":true}),
    ));
    if cfg!(feature = "dioptrin") {
        assert_eq!(r.result["ok"], true);
        assert_eq!(plugin(&r, 2)["maskedPixels"], 0);
    } else {
        assert_eq!(r.result["ok"], false);
        assert!(r.result["error"].as_str().unwrap().contains("Dioptrin"));
    }
}

#[cfg(feature = "dioptrin")]
#[test]
fn plugins_feed_integration_and_peak_picking_and_imprints_preserve_products() {
    let (mut s, _) = session();
    call(
        &mut s,
        "integration_settings",
        json!({"bins":64,"cake_bins":8,"defer_integration":true}),
    );
    call(
        &mut s,
        "manual_geometry",
        json!({"convention":"pyfai","values":{"dist":0.1,"poni1":0.0015,"poni2":0.0016,"rot1":0,"rot2":0,"rot3":0,"pixel1":0.0001,"pixel2":0.0001,"wavelength":1e-10,"polarization_factor":0}}),
    );
    let unmasked = call(&mut s, "state", json!({}));
    let filtered = call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","enabled":true,"settings":{"above_value":1000}}),
    );
    assert_ne!(unmasked.result["pattern"], filtered.result["pattern"]);
    let imprinted = call(
        &mut s,
        "mask_plugin",
        json!({"name":"Threshold Mask","imprint":true}),
    );
    // Dynamic CSC and fixed-mask block plans use different reduction orders.
    // Check scientific equivalence rather than incidental last-bit equality.
    for (a, b) in filtered.result["pattern"]["y"]
        .as_array()
        .unwrap()
        .iter()
        .zip(imprinted.result["pattern"]["y"].as_array().unwrap())
    {
        let (a, b) = (a.as_f64().unwrap(), b.as_f64().unwrap());
        assert!((a - b).abs() < 1e-10 + 1e-12 * a.abs());
    }
    assert_eq!(
        filtered.result["cake"]["bufferId"],
        imprinted.result["cake"]["bufferId"]
    );
    let undone = call(&mut s, "undo_mask", json!({}));
    assert_eq!(undone.result["pattern"], filtered.result["pattern"]);
    let bypassed = call(&mut s, "settings", json!({"use_mask":false}));
    assert_eq!(bypassed.result["pattern"], unmasked.result["pattern"]);
    assert_eq!(mask(&bypassed), mask(&filtered));
    call(&mut s, "settings", json!({"use_mask":true}));
    let rejected = s.invoke(&request("pick_peak", json!({"x":8,"y":6,"ring":1})));
    assert_eq!(rejected.result["ok"], false);
    assert!(
        rejected.result["error"]
            .as_str()
            .unwrap()
            .contains("masked")
    );
}

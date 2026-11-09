#![cfg(feature = "dioptrin")]
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn call(s: &mut Session, action: &str, mut args: Value, cake: bool) -> Reply {
    args["requested_products"] = json!({"cake":cake,"rings":false});
    let reply = s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload: args,
        cached_buffers: vec![],
    });
    assert_eq!(reply.result["ok"], true, "{action}: {}", reply.result);
    reply
}
fn fixture(temp: &Path) -> (PathBuf, PathBuf) {
    let image = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/combined-counts.h5");
    let poni = temp.join("fixture.poni");
    std::fs::write(&poni,"PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.1\nPoni1: 0.003\nPoni2: 0.004\nRot1: 0\nRot2: 0\nRot3: 0\nSplineFile: None\nWavelength: 4e-11\n").unwrap();
    (image, poni)
}
fn setup(s: &mut Session, image: &Path, poni: &Path, cake: bool) -> Reply {
    call(
        s,
        "integration_settings",
        json!({"bins":48,"cake_bins":12,"trim_zeros":false}),
        cake,
    );
    call(s, "open_calibration", json!({"path":poni}), cake);
    call(
        s,
        "open_image",
        json!({"path":image,"dataset":"/counts"}),
        cake,
    )
}
fn diagnostics(s: &mut Session) -> Value {
    call(s, "integration_diagnostics", json!({}), false).result["integrationDiagnostics"].clone()
}
fn same_cake(actual: &Value, expected: &Value) {
    // Shared parallel source statistics can round Auto limits by one ulp.
    // Pixel identities, histograms, shape and coordinate metadata stay exact.
    let (mut a, mut b) = (actual.clone(), expected.clone());
    let (al, bl) = (a["limits"].take(), b["limits"].take());
    assert_eq!(a, b);
    for (x, y) in al.as_array().unwrap().iter().zip(bl.as_array().unwrap()) {
        let (x, y) = (x.as_f64().unwrap(), y.as_f64().unwrap());
        assert!((x - y).abs() <= 4.0 * f64::EPSILON * x.abs().max(y.abs()).max(1.0));
    }
}

#[test]
fn lazy_cake_matches_eager_pixels_without_changing_the_pattern_or_history() {
    let temp = tempfile::tempdir().unwrap();
    let (image, poni) = fixture(temp.path());
    let mut lazy = Session::new(root());
    let hidden = setup(&mut lazy, &image, &poni, false);
    let mut eager = Session::new(root());
    let full = setup(&mut eager, &image, &poni, true);
    assert!(hidden.result["cake"].is_null());
    assert_eq!(diagnostics(&mut lazy)["cakeIntegrations"], 0);
    assert_eq!(hidden.result["pattern"], full.result["pattern"]);
    let before = diagnostics(&mut lazy);
    let shown = call(&mut lazy, "display_products", json!({"cake":true}), false);
    same_cake(&shown.result["cake"], &full.result["cake"]);
    assert_eq!(shown.result["pattern"], hidden.result["pattern"]);
    assert_eq!(
        shown.result["state"]["revision"],
        hidden.result["state"]["revision"]
    );
    assert_eq!(
        shown.result["state"]["calibration"]["canUndo"],
        hidden.result["state"]["calibration"]["canUndo"]
    );
    let after = diagnostics(&mut lazy);
    assert_eq!(after["cakeIntegrations"], 1);
    assert_eq!(
        after["residentIntegrations"],
        before["residentIntegrations"]
    );
    assert_eq!(after["preparedHits"], before["preparedHits"]);
    call(&mut lazy, "display_products", json!({"cake":true}), true);
    assert_eq!(diagnostics(&mut lazy)["cakeIntegrations"], 1);
    let next = call(&mut lazy, "next_image", json!({"direction":1}), false);
    assert!(next.result["cake"].is_null());
    assert_eq!(diagnostics(&mut lazy)["cakeIntegrations"], 1);
    let reference = call(&mut eager, "next_image", json!({"direction":1}), true);
    assert_eq!(next.result["pattern"], reference.result["pattern"]);
    let new_cake = call(&mut lazy, "display_products", json!({"cake":true}), true);
    same_cake(&new_cake.result["cake"], &reference.result["cake"]);
    assert_eq!(diagnostics(&mut lazy)["cakeIntegrations"], 2);
}

#[test]
fn batch_map_settings_and_explicit_export_obey_the_same_product_demand() {
    let temp = tempfile::tempdir().unwrap();
    let (image, poni) = fixture(temp.path());
    let mut s = Session::new(root());
    setup(&mut s, &image, &poni, false);
    call(&mut s, "batch_load", json!({"paths":[image]}), false);
    let selection = call(&mut s, "batch_select", json!({"index":1}), false);
    assert!(selection.result["cake"].is_null());
    assert_eq!(diagnostics(&mut s)["cakeIntegrations"], 0);
    let cake = call(&mut s, "display_products", json!({"cake":true}), true);
    assert_eq!(cake.result["pattern"], selection.result["pattern"]);
    call(&mut s, "batch_select", json!({"index":0}), false);
    assert_eq!(diagnostics(&mut s)["cakeIntegrations"], 1);
    let batch = temp.path().join("batch.h5");
    call(
        &mut s,
        "integration_save_batch",
        json!({"path":batch}),
        false,
    );
    call(&mut s, "map_batch", json!({"path":batch}), false);
    for reintegrate in [false, true] {
        let r = call(
            &mut s,
            "map_select",
            json!({"index":1,"reintegrate":reintegrate}),
            false,
        );
        assert!(r.result["cake"].is_null());
        assert_eq!(diagnostics(&mut s)["cakeIntegrations"], 1);
    }
    call(
        &mut s,
        "integration_settings",
        json!({"cake_bins":8,"solid_angle":false}),
        false,
    );
    assert_eq!(diagnostics(&mut s)["cakeIntegrations"], 1);
    let pattern = call(&mut s, "state", json!({}), false).result["pattern"].clone();
    let csv = temp.path().join("cake.csv");
    call(
        &mut s,
        "integration_save_image",
        json!({"path":csv,"source":"cake"}),
        false,
    );
    assert!(std::fs::metadata(csv).unwrap().len() > 0);
    assert_eq!(diagnostics(&mut s)["cakeIntegrations"], 2);
    assert_eq!(
        call(&mut s, "state", json!({}), false).result["pattern"],
        pattern
    );
}

#[test]
fn restored_projects_and_combined_detectors_do_not_rebuild_hidden_cakes() {
    let temp = tempfile::tempdir().unwrap();
    let (image, poni) = fixture(temp.path());
    let mut s = Session::new(root());
    setup(&mut s, &image, &poni, false);
    call(
        &mut s,
        "configuration",
        json!({"operation":"duplicate"}),
        false,
    );
    let combined = call(
        &mut s,
        "combination_settings",
        json!({"patterns":true,"cakes":true}),
        false,
    );
    assert!(combined.result["cake"].is_null());
    assert_eq!(diagnostics(&mut s)["cakeIntegrations"], 0);
    let project = temp.path().join("no-hidden-cake.dio");
    call(&mut s, "save_project", json!({"path":project}), false);
    let mut restored = Session::new(root());
    let opened = call(
        &mut restored,
        "open_project",
        json!({"path":project}),
        false,
    );
    assert!(opened.result["cake"].is_null());
    assert_eq!(diagnostics(&mut restored)["cakeIntegrations"], 0);
    let shown = call(
        &mut restored,
        "display_products",
        json!({"cake":true}),
        true,
    );
    assert!(shown.result["cake"].is_object());
    assert_eq!(shown.result["pattern"], opened.result["pattern"]);
}

#[test]
fn invalid_demand_is_rejected_and_legacy_requests_keep_complete_products() {
    let temp = tempfile::tempdir().unwrap();
    let (image, poni) = fixture(temp.path());
    let mut s = Session::new(root());
    setup(&mut s, &image, &poni, false);
    for products in [
        json!(false),
        json!({}),
        json!({"cake":"false"}),
        json!({"cake":false,"extra":true}),
        json!({"cake":false,"rings":"false"}),
    ] {
        let r = s.invoke(&Request {
            id: 1,
            action: "next_image".into(),
            payload: json!({"direction":1,"requested_products":products}),
            cached_buffers: vec![],
        });
        assert_eq!(r.result["ok"], false);
    }
    assert_eq!(
        call(&mut s, "state", json!({}), false).result["state"]["integration"]["frame"],
        0
    );
    let legacy = s.invoke(&Request {
        id: 2,
        action: "next_image".into(),
        payload: json!({"direction":1}),
        cached_buffers: vec![],
    });
    assert_eq!(legacy.result["ok"], true);
    assert!(legacy.result["cake"].is_object());
}

#[test]
fn calibration_contours_are_requested_separately_without_a_cake() {
    let temp = tempfile::tempdir().unwrap();
    let (image, poni) = fixture(temp.path());
    let text = std::fs::read_to_string(&poni)
        .unwrap()
        .replace("Distance: 0.1\n", "Distance: 0.01\n");
    std::fs::write(&poni, text).unwrap();
    let mut s = Session::new(root());
    let hidden = setup(&mut s, &image, &poni, false);
    assert!(hidden.result["rings"].as_array().unwrap().is_empty());
    let shown = call(
        &mut s,
        "display_products",
        json!({"cake":false,"rings":true}),
        false,
    );
    assert!(!shown.result["rings"].as_array().unwrap().is_empty());
    assert_eq!(shown.result["pattern"], hidden.result["pattern"]);
    assert!(shown.result["cake"].is_null());
    let next = call(&mut s, "next_image", json!({"direction":1}), false);
    assert!(next.result["rings"].as_array().unwrap().is_empty());
    let again = call(
        &mut s,
        "display_products",
        json!({"cake":false,"rings":true}),
        false,
    );
    assert_eq!(again.result["rings"], shown.result["rings"]);
    assert_eq!(diagnostics(&mut s)["cakeIntegrations"], 0);
}

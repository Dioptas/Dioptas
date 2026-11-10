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
fn assert_same_cake(before: &Reply, after: &Reply) {
    assert_eq!(before.result["cake"], after.result["cake"]);
    let id = before.result["cake"]["bufferId"].as_str().unwrap();
    let pixels = |reply: &Reply| {
        reply
            .buffers
            .iter()
            .find(|b| b.id == id)
            .unwrap()
            .bytes
            .clone()
    };
    assert!(
        std::sync::Arc::ptr_eq(&pixels(before), &pixels(after)),
        "reuse the immutable buffer, not a recalculated copy"
    );
}

#[test]
fn individual_axis_changes_and_undo_reuse_the_scientific_cake_and_exports() {
    let temp = tempfile::tempdir().unwrap();
    let (image, poni) = fixture(temp.path());
    let mut s = Session::new(root());
    let original = setup(&mut s, &image, &poni, true);
    let count = diagnostics(&mut s)["cakeIntegrations"].clone();
    let export = |s: &mut Session, name: &str| {
        let path = temp.path().join(name);
        call(
            s,
            "integration_save_image",
            json!({"source":"cake","path":path}),
            true,
        );
        std::fs::read(path).unwrap()
    };
    let data = export(&mut s, "angular.csv");
    for unit in ["q_A^-1", "d_A", "2th_deg"] {
        let changed = call(&mut s, "integration_settings", json!({"unit":unit}), true);
        assert_same_cake(&original, &changed);
        assert_eq!(changed.result["pattern"]["unit"], unit);
        assert_eq!(data, export(&mut s, "changed.csv"));
        assert_eq!(diagnostics(&mut s)["cakeIntegrations"], count);
    }
    for action in ["undo_calibration", "redo_calibration"] {
        let changed = call(&mut s, action, json!({}), true);
        assert_same_cake(&original, &changed);
        assert_eq!(diagnostics(&mut s)["cakeIntegrations"], count);
    }
    let changed = call(&mut s, "integration_settings", json!({"cake_bins":9}), true);
    assert_ne!(
        changed.result["cake"]["height"],
        original.result["cake"]["height"]
    );
    assert!(diagnostics(&mut s)["cakeIntegrations"].as_u64().unwrap() > count.as_u64().unwrap());
}

#[test]
fn combined_cakes_retain_either_source_grid_on_unit_change_and_inspection() {
    for source in ["2th_deg", "q_A^-1"] {
        let temp = tempfile::tempdir().unwrap();
        let (image, poni) = fixture(temp.path());
        let mut s = Session::new(root());
        setup(&mut s, &image, &poni, true);
        call(&mut s, "integration_settings", json!({"unit":source}), true);
        call(
            &mut s,
            "configuration",
            json!({"operation":"duplicate"}),
            true,
        );
        let original = call(
            &mut s,
            "combination_settings",
            json!({"patterns":true,"cakes":true}),
            true,
        );
        assert_eq!(original.result["cake"]["unit"], source);
        let profile = call(
            &mut s,
            "cake_profile",
            json!({"two_theta":1.,"bins":3,"shift":90}),
            true,
        )
        .result["cakeProfile"]
            .clone();
        assert_eq!(profile["radialUnit"], source);
        assert!(
            profile["y"]
                .as_array()
                .unwrap()
                .iter()
                .any(|v| v.as_f64().unwrap() > 0.)
        );
        for unit in ["q_A^-1", "2th_deg", "d_A"] {
            let changed = call(&mut s, "integration_settings", json!({"unit":unit}), true);
            assert_same_cake(&original, &changed);
            assert_eq!(changed.result["pattern"]["unit"], unit);
            let relabeled_profile = call(
                &mut s,
                "cake_profile",
                json!({"two_theta":1.,"bins":3,"shift":90}),
                true,
            );
            assert_eq!(
                relabeled_profile.result["cakeProfile"], profile,
                "The display axis must not alter fractional radial extraction."
            );
            let linked = call(
                &mut s,
                "validation_position",
                json!({"source":"cake","unit":source,"x":original.result["cake"]["radialRange"][1],"azimuth":15}),
                true,
            );
            assert_same_cake(&original, &call(&mut s, "state", json!({}), true));
            assert!(
                linked.result["linked"]["twoTheta"]
                    .as_f64()
                    .unwrap()
                    .is_finite()
            );
        }
        let project = temp.path().join("axis.dio");
        let saved = call(&mut s, "save_project", json!({"path":project}), true);
        assert!(saved.result["savedPath"].is_string());
        assert_same_cake(&original, &call(&mut s, "state", json!({}), true));
        let mut reopened = Session::new(root());
        let opened = call(&mut reopened, "open_project", json!({"path":project}), true);
        assert_eq!(opened.result["state"]["unit"], "d_A");
        assert_eq!(
            call(
                &mut reopened,
                "cake_profile",
                json!({"two_theta":1.,"bins":3,"shift":90}),
                true
            )
            .result["cakeProfile"],
            profile
        );
        assert_eq!(
            opened.result["cake"]["unit"],
            original.result["cake"]["unit"]
        );
        assert_eq!(
            opened.result["cake"]["radialRange"],
            original.result["cake"]["radialRange"]
        );
        assert_eq!(
            opened.result["cake"]["bufferId"],
            original.result["cake"]["bufferId"]
        );
        // Hidden/lazy restore and resaving must retain the saved source unit too.
        let mut lazy = Session::new(root());
        call(&mut lazy, "open_project", json!({"path":project}), false);
        call(&mut lazy, "save_project", json!({"path":project}), false);
        let lazy_cake = call(&mut lazy, "display_products", json!({"cake":true}), true);
        assert_eq!(
            lazy_cake.result["cake"]["unit"],
            original.result["cake"]["unit"]
        );
        assert_eq!(
            lazy_cake.result["cake"]["bufferId"],
            original.result["cake"]["bufferId"]
        );
        let changed = call(
            &mut reopened,
            "integration_settings",
            json!({"unit":"q_A^-1"}),
            true,
        );
        assert_same_cake(&opened, &changed);
        let moved = call(&mut s, "integration_navigation", json!({"frame":2}), true);
        assert_ne!(
            original.result["cake"]["bufferId"],
            moved.result["cake"]["bufferId"]
        );
    }
}

use dioptas_backend::{Session, protocol::Request};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
}
fn invoke(s: &mut Session, action: &str, payload: Value) -> Value {
    s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    })
    .result
}
fn call(s: &mut Session, action: &str, payload: Value) -> Value {
    let result = invoke(s, action, payload);
    assert_eq!(result["ok"], true, "{result}");
    result
}
fn phases(s: &mut Session) -> Vec<Value> {
    call(s, "state", json!({}))["state"]["integration"]["phases"]
        .as_array()
        .unwrap()
        .clone()
}

#[test]
fn phase_order_preserves_identity_history_and_saved_order() {
    let mut s = Session::new(root());
    let temp = tempfile::tempdir().unwrap();
    let curve = temp.path().join("pattern.xy");
    std::fs::write(&curve, "0 1\n10 2\n30 3\n").unwrap();
    call(&mut s, "integration_open_pattern", json!({"path":curve}));
    for name in ["mo.jcpds", "au_version3.jcpds", "pt.jcpds"] {
        call(
            &mut s,
            "integration_phase",
            json!({"operation":"load", "path":root().join("tests/data/jcpds").join(name)}),
        );
    }
    let original = phases(&mut s);
    let uid = original[1]["uid"].clone();
    // UID targeting survives a stale row index from a queued UI action.
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"move", "editor_uid":uid, "index":0, "direction":-1}),
    );
    let moved = vec![
        original[1].clone(),
        original[0].clone(),
        original[2].clone(),
    ];
    assert_eq!(phases(&mut s), moved);
    let pattern = call(&mut s, "state", json!({}));
    let mut colors = Vec::new();
    for line in pattern["pattern"]["phaseLines"].as_array().unwrap() {
        let color = line["color"].clone();
        if colors.last() != Some(&color) {
            colors.push(color);
        }
    }
    assert_eq!(
        colors,
        moved.iter().map(|p| p["color"].clone()).collect::<Vec<_>>(),
        "Plot/export reference groups follow the phase-table order"
    );

    call(
        &mut s,
        "integration_phase",
        json!({"operation":"move", "editor_uid":uid, "direction":-1}),
    );
    assert_eq!(phases(&mut s), moved, "A boundary move is a no-op");
    call(&mut s, "undo_calibration", json!({}));
    assert_eq!(
        phases(&mut s),
        original,
        "Boundary no-ops do not consume Undo"
    );
    call(&mut s, "redo_calibration", json!({}));
    assert_eq!(phases(&mut s), moved);
    let invalid = invoke(
        &mut s,
        "integration_phase",
        json!({"operation":"move", "editor_uid":uid, "direction":2}),
    );
    assert_eq!(invalid["ok"], false);
    assert_eq!(phases(&mut s), moved);
    let list = temp.path().join("ordered.txt");
    call(
        &mut s,
        "integration_phase_list",
        json!({"save":true, "path":list}),
    );
    let saved = std::fs::read_to_string(list).unwrap();
    assert!(saved.lines().next().unwrap().contains("au_version3.jcpds"));
    let project = temp.path().join("ordered.dio");
    call(&mut s, "save_project", json!({"path":project}));
    let mut restored = Session::new(root());
    call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(phases(&mut restored), moved);
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"move", "editor_uid":uid, "direction":1}),
    );
    assert_eq!(phases(&mut s), original);
}

//! Stable overlay identities survive queued list edits and retain chronological Undo.
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
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
fn prepared() -> (tempfile::TempDir, Session, Vec<String>) {
    let temp = tempfile::tempdir().unwrap();
    let paths: Vec<_> = ["A", "B", "C"]
        .into_iter()
        .map(|name| {
            let path = temp.path().join(format!("{name}.xy"));
            std::fs::write(&path, "1 10\n2 20\n3 15\n").unwrap();
            path
        })
        .collect();
    let mut session = Session::new(root());
    let reply = call(
        &mut session,
        "integration_overlay",
        json!({"operation":"load", "paths":paths}),
    );
    assert_eq!(
        reply.result["state"]["integration"]["supportsOverlayUids"],
        true
    );
    let ids = overlays(&reply)
        .iter()
        .map(|overlay| overlay["uid"].as_str().unwrap().to_owned())
        .collect();
    (temp, session, ids)
}
fn overlays(reply: &Reply) -> &Vec<Value> {
    reply.result["state"]["integration"]["overlays"]
        .as_array()
        .unwrap()
}
fn names(reply: &Reply) -> Vec<&str> {
    overlays(reply)
        .iter()
        .map(|overlay| overlay["name"].as_str().unwrap())
        .collect()
}

#[test]
fn repeated_moves_and_later_row_edits_keep_the_original_target() {
    let (_temp, mut session, ids) = prepared();
    for _ in 0..2 {
        call(
            &mut session,
            "integration_overlay",
            json!({"operation":"move", "uid":ids[0], "direction":1}),
        );
    }
    let moved = call(&mut session, "state", json!({}));
    assert_eq!(names(&moved), ["B", "C", "A"]);
    let updated = call(
        &mut session,
        "integration_overlay",
        json!({"operation":"update", "uid":ids[0], "name":"edited A", "color":"#123456", "scale":3.0, "offset":7.0, "visible":false}),
    );
    assert_eq!(names(&updated), ["B", "C", "edited A"]);
    assert_eq!(overlays(&updated)[2]["color"], "#123456");
    assert_eq!(overlays(&updated)[2]["scale"], 3.0);
    assert_eq!(overlays(&updated)[2]["offset"], 7.0);
    assert_eq!(overlays(&updated)[2]["visible"], false);
    assert_eq!(overlays(&updated)[0]["scale"], 1.0);
}

#[test]
fn missing_uid_never_redirects_removal_or_edit_to_a_reused_index() {
    let (_temp, mut session, ids) = prepared();
    call(
        &mut session,
        "integration_overlay",
        json!({"operation":"remove", "uid":ids[0]}),
    );
    let before = call(&mut session, "state", json!({}));
    for operation in ["remove", "update", "move", "background", "match_intensity"] {
        let rejected = invoke(
            &mut session,
            "integration_overlay",
            json!({"operation":operation, "uid":ids[0], "index":0, "direction":1, "scale":8.0}),
        );
        assert_eq!(rejected.result["ok"], false, "{operation}");
        assert_eq!(
            rejected.result["error"],
            "The selected overlay no longer exists."
        );
        let after = call(&mut session, "state", json!({}));
        assert_eq!(before.result["state"], after.result["state"]);
    }
    let legacy = call(
        &mut session,
        "integration_overlay",
        json!({"operation":"update", "index":0, "name":"legacy B"}),
    );
    assert_eq!(names(&legacy), ["legacy B", "C"]);
    assert_eq!(overlays(&legacy)[0]["uid"], ids[1]);
}

#[test]
fn slider_history_groups_by_uid_without_merging_different_overlays() {
    let (_temp, mut session, ids) = prepared();
    for (uid, scale) in [(&ids[0], 2.0), (&ids[0], 3.0), (&ids[1], 4.0)] {
        call(
            &mut session,
            "integration_overlay",
            json!({"operation":"update", "uid":uid, "scale":scale}),
        );
    }
    let undo_b = call(&mut session, "undo_calibration", json!({}));
    assert_eq!(overlays(&undo_b)[0]["scale"], 3.0);
    assert_eq!(overlays(&undo_b)[1]["scale"], 1.0);
    let undo_a = call(&mut session, "undo_calibration", json!({}));
    assert_eq!(overlays(&undo_a)[0]["scale"], 1.0);
    let redo_a = call(&mut session, "redo_calibration", json!({}));
    assert_eq!(overlays(&redo_a)[0]["scale"], 3.0);
    assert_eq!(overlays(&redo_a)[1]["scale"], 1.0);
}

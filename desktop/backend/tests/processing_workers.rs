use dioptas_backend::{Session, protocol::Request};
use serde_json::{Value, json};
use std::path::Path;

fn call(session: &mut Session, action: &str, payload: Value) -> Value {
    let reply = session.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(reply.result["ok"], true, "{action}: {}", reply.result);
    reply.result
}
fn background(session: &mut Session, path: &Path) -> Vec<u64> {
    call(session, "integration_save_batch", json!({"path":path}));
    hdf5::File::open(path)
        .unwrap()
        .dataset("processed/process/bkg")
        .unwrap()
        .read_raw::<f64>()
        .unwrap()
        .into_iter()
        .map(f64::to_bits)
        .collect()
}
#[test]
fn resizing_workers_retains_products_and_matches_serial_fits_and_project_preferences() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let temp = tempfile::tempdir().unwrap();
    let mut session = Session::new(root.clone());
    call(
        &mut session,
        "batch_open",
        json!({"path":root.join("desktop/backend/tests/fixtures/batch_background_input.h5")}),
    );
    call(&mut session, "processing_workers", json!({"workers":1}));
    call(
        &mut session,
        "integration_background",
        json!({"enabled":true,"smoothing":0.37,"iterations":31,"order":8,"range":[2.,8.]}),
    );
    let serial = background(&mut session, &temp.path().join("serial.h5"));
    let before = call(&mut session, "batch_snapshot", json!({}))["batch"].clone();
    let available =
        call(&mut session, "state", json!({}))["state"]["processingWorkers"]["available"]
            .as_u64()
            .unwrap();
    let count = available.min(4);
    let resized = call(&mut session, "processing_workers", json!({"workers":count}));
    assert_eq!(resized["state"]["processingWorkers"]["effective"], count);
    assert_eq!(
        call(&mut session, "batch_snapshot", json!({}))["batch"],
        before
    );
    call(&mut session, "batch_background_from_pattern", json!({}));
    assert_eq!(
        background(&mut session, &temp.path().join("parallel.h5")),
        serial
    );
    let project = temp.path().join("workers.dio");
    call(&mut session, "save_project", json!({"path":project}));
    call(&mut session, "processing_workers", json!({"workers":1}));
    call(&mut session, "open_project", json!({"path":project}));
    assert_eq!(
        call(&mut session, "state", json!({}))["state"]["processingWorkers"]["requested"],
        1
    );
    let reset = call(&mut session, "processing_workers", json!({"workers":null}));
    assert!(reset["state"]["processingWorkers"]["requested"].is_null());
    assert_eq!(
        reset["state"]["processingWorkers"]["effective"],
        reset["state"]["processingWorkers"]["automatic"]
    );
}

#[test]
fn invalid_worker_counts_retain_the_current_pool_and_development_handoff_keeps_the_choice() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let temp = tempfile::tempdir().unwrap();
    let mut session = Session::new(root.clone());
    let selected = call(&mut session,"processing_workers",json!({"workers":1}))["state"]["processingWorkers"].clone();
    for count in [json!(0), json!(-1), json!(1.5), json!("4"), json!(100000)] {
        let reply = session.invoke(&Request {
            id: 1,
            action: "processing_workers".into(),
            payload: json!({"workers":count}),
            cached_buffers: vec![],
        });
        assert_eq!(reply.result["ok"], false);
        assert_eq!(
            call(&mut session, "state", json!({}))["state"]["processingWorkers"],
            selected
        );
    }
    #[cfg(debug_assertions)]
    {
        let path = temp.path().join("handoff.dio");
        call(&mut session, "development_checkpoint", json!({"path":path}));
        let mut restored = Session::new(root);
        call(&mut restored, "development_restore", json!({"path":path}));
        assert_eq!(
            call(&mut restored, "state", json!({}))["state"]["processingWorkers"],
            selected
        );
    }
}

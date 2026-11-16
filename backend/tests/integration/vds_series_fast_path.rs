#![cfg(feature = "dioptrin")]
//! A Bliss-style master whose virtual dataset maps every frame of one Eiger
//! file one-to-one must reach the same frame-parallel Map path as the Eiger
//! file itself; any other mapping stays on the general virtual reader.
use dioptas_backend::{
    Session,
    image::Image,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};

fn call(session: &mut Session, command: &str, payload: Value) -> Reply {
    let result = session.invoke(&Request {
        id: 1,
        action: command.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(result.result["ok"], true, "{command}: {}", result.result);
    result
}
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .canonicalize()
        .unwrap()
}
fn diagnostics(session: &mut Session) -> Value {
    call(session, "integration_diagnostics", json!({})).result["integrationDiagnostics"].clone()
}
fn counter(after: &Value, before: &Value, key: &str) -> u64 {
    after[key].as_u64().unwrap() - before[key].as_u64().unwrap()
}

/// Stored Map rows, read back without reintegration.
fn map_rows(session: &mut Session, path: &Path) -> (Vec<Vec<f64>>, Value) {
    let before = diagnostics(session);
    call(session, "open_image", json!({"path":path}));
    call(session, "map_load", json!({"paths":[path]}));
    let after = diagnostics(session);
    let rows = (0..)
        .map_while(|index| {
            let selected = session.invoke(&Request {
                id: 1,
                action: "map_select".into(),
                payload: json!({"index":index,"reintegrate":false}),
                cached_buffers: vec![],
            });
            (selected.result["ok"] == true).then(|| {
                selected.result["pattern"]["y"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|v| v.as_f64().unwrap())
                    .collect()
            })
        })
        .take(3)
        .collect();
    let delta = json!({
        "pipelineRuns": counter(&after, &before, "seriesPipelineRuns"),
        "frameParallel": counter(&after, &before, "frameParallelIntegrations"),
    });
    (rows, delta)
}

#[test]
fn whole_frame_master_uses_the_source_fast_path_and_offset_masters_do_not() {
    let temp = tempfile::tempdir().unwrap();
    std::fs::create_dir(temp.path().join("scan0001")).unwrap();
    let source = temp.path().join("scan0001/eiger_0000.h5");
    std::fs::copy(
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/combined-counts.h5"),
        &source,
    )
    .unwrap();
    let master = temp.path().join("master.h5");
    let file = hdf5::File::create(&master).unwrap();
    file.create_group("1.1/instrument/eiger").unwrap();
    file.new_dataset::<u32>()
        .shape((3, 64, 80))
        .virtual_map(
            "scan0001/eiger_0000.h5",
            "/counts",
            (3, 64, 80),
            (.., .., ..),
            (3, 64, 80),
            (.., .., ..),
        )
        .create("1.1/instrument/eiger/data")
        .unwrap();
    drop(file);
    // Master frame i is source frame i + 1: correct through the general
    // reader, but not the one-to-one layout the raw source reader assumes.
    let offset = temp.path().join("offset.h5");
    let file = hdf5::File::create(&offset).unwrap();
    file.new_dataset::<u32>()
        .shape((2, 64, 80))
        .virtual_map(
            "scan0001/eiger_0000.h5",
            "/counts",
            (3, 64, 80),
            (1..3, .., ..),
            (2, 64, 80),
            (.., .., ..),
        )
        .create("data")
        .unwrap();
    drop(file);

    let image = Image::open(&master, &json!({})).unwrap();
    let combined = image.combined_source(0).unwrap().expect("admitted master");
    assert_eq!(combined.path, source.canonicalize().unwrap());
    assert_eq!(combined.dataset, "/counts");
    assert!(
        Image::open(&offset, &json!({}))
            .unwrap()
            .combined_source(0)
            .unwrap()
            .is_none()
    );

    let mut session = Session::new(root());
    let geometry = json!({"dist":0.2,"poni1":0.0032,"poni2":0.004,"rot1":0.,"rot2":0.,"rot3":0.,"pixel1":0.0001,"pixel2":0.0001,"wavelength":4e-11,"polarization_factor":0.99});
    call(
        &mut session,
        "manual_geometry",
        json!({"convention":"pyfai","values":geometry}),
    );
    call(
        &mut session,
        "integration_settings",
        json!({"bins":48,"cake_bins":12,"trim_zeros":false}),
    );
    let (direct, direct_path) = map_rows(&mut session, &source);
    let (through_master, master_path) = map_rows(&mut session, &master);
    assert_eq!(direct.len(), 3);
    assert_eq!(direct_path, json!({"pipelineRuns":1,"frameParallel":3}));
    assert_eq!(master_path, direct_path);
    assert_eq!(through_master, direct);

    let (shifted, shifted_path) = map_rows(&mut session, &offset);
    assert_eq!(shifted_path, json!({"pipelineRuns":0,"frameParallel":0}));
    assert_eq!(shifted.len(), 2);
    for (row, expected) in shifted.iter().zip(&direct[1..]) {
        for (a, b) in row.iter().zip(expected) {
            assert!((a - b).abs() <= 1e-9 * b.abs().max(1.), "{a} vs {b}");
        }
    }
}

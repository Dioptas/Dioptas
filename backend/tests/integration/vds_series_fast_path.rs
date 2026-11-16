#![cfg(feature = "dioptrin")]
//! A Bliss-style master whose virtual dataset stacks whole Eiger frames, from
//! one file or several, must reach the same frame-parallel Map path as the
//! Eiger files themselves; any other mapping stays on the general virtual reader.
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
    map_rows_of(session, &[path])
}
fn map_rows_of(session: &mut Session, paths: &[&Path]) -> (Vec<Vec<f64>>, Value) {
    let before = diagnostics(session);
    call(session, "open_image", json!({"path":paths[0]}));
    call(session, "map_load", json!({"paths":paths}));
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
        .take(16)
        .collect();
    let delta = json!({
        "pipelineRuns": counter(&after, &before, "seriesPipelineRuns"),
        "frameParallel": counter(&after, &before, "frameParallelIntegrations"),
        "processed": counter(&after, &before, "processedFrameIntegrations"),
    });
    (rows, delta)
}

#[test]
fn whole_frame_masters_with_and_without_source_offset_use_the_fast_path() {
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
    // Master frame i is source frame i + 1: a whole-frame block that starts
    // inside the source dataset, read from the source at that offset.
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
    let shifted_source = Image::open(&offset, &json!({}))
        .unwrap()
        .combined_source(1)
        .unwrap()
        .expect("admitted offset master");
    assert_eq!(
        (shifted_source.frame, shifted_source.master_frames),
        (2, 0..2)
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
    assert_eq!(
        direct_path,
        json!({"pipelineRuns":1,"frameParallel":3,"processed":0})
    );
    assert_eq!(master_path, direct_path);
    assert_eq!(through_master, direct);

    let (shifted, shifted_path) = map_rows(&mut session, &offset);
    assert_eq!(
        shifted_path,
        json!({"pipelineRuns":1,"frameParallel":2,"processed":0})
    );
    assert_eq!(shifted, direct[1..]);
}

/// A master over `blocks` of `(source file, source frames, master frames)`.
fn master_over(path: &Path, frames_total: usize, blocks: &[(&str, std::ops::Range<usize>, usize)]) {
    let file = hdf5::File::create(path).unwrap();
    file.create_group("1.1/instrument/eiger").unwrap();
    let builder = blocks.iter().fold(
        file.new_dataset::<u32>()
            .fill_value(7u32)
            .shape((frames_total, 64, 80)),
        |builder, (source, frames, start)| {
            let n = frames.len();
            builder.virtual_map(
                source,
                "/counts",
                (3, 64, 80),
                (frames.clone(), .., ..),
                (frames_total, 64, 80),
                (*start..*start + n, .., ..),
            )
        },
    );
    builder.create("1.1/instrument/eiger/data").unwrap();
}

fn batch_rows(session: &mut Session, paths: &[&Path], args: Value) -> (Vec<Vec<f64>>, Value) {
    let before = diagnostics(session);
    let mut payload = args;
    payload["paths"] = json!(paths);
    let loaded = call(session, "batch_load", payload);
    let after = diagnostics(session);
    let count = loaded.result["batch"]["entries"].as_array().unwrap().len();
    let rows = (0..count)
        .map(|index| {
            call(session, "batch_select", json!({"index":index})).result["pattern"]["y"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_f64().unwrap())
                .collect()
        })
        .collect();
    let delta = json!({
        "pipelineRuns": counter(&after, &before, "seriesPipelineRuns"),
        "frameParallel": counter(&after, &before, "frameParallelIntegrations"),
    });
    (rows, delta)
}

#[test]
fn multi_file_master_runs_one_parallel_segment_per_source_file() {
    let temp = tempfile::tempdir().unwrap();
    std::fs::create_dir(temp.path().join("scan0001")).unwrap();
    let fixture = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/combined-counts.h5");
    let first = temp.path().join("scan0001/eiger_0000.h5");
    let second = temp.path().join("scan0001/eiger_0001.h5");
    std::fs::copy(&fixture, &first).unwrap();
    std::fs::copy(&fixture, &second).unwrap();
    let master = temp.path().join("master.h5");
    master_over(
        &master,
        6,
        &[
            ("scan0001/eiger_0000.h5", 0..3, 0),
            ("scan0001/eiger_0001.h5", 0..3, 3),
        ],
    );
    // Master frames 3 and 4 are missing: the general reader fills them.
    let gap = temp.path().join("gap.h5");
    master_over(
        &gap,
        6,
        &[
            ("scan0001/eiger_0000.h5", 0..3, 0),
            ("scan0001/eiger_0001.h5", 0..1, 5),
        ],
    );
    // Master frame 2 is mapped twice: dioptrin-io refuses the master before
    // either reader could choose a copy.
    let overlap = temp.path().join("overlap.h5");
    master_over(
        &overlap,
        5,
        &[
            ("scan0001/eiger_0000.h5", 0..3, 0),
            ("scan0001/eiger_0001.h5", 0..3, 2),
        ],
    );

    let image = Image::open(&master, &json!({})).unwrap();
    let late = image.combined_source(4).unwrap().expect("admitted master");
    assert_eq!(late.path, second.canonicalize().unwrap());
    assert_eq!((late.frame, late.master_frames), (1, 3..6));
    let error = Image::open(&overlap, &json!({})).err().unwrap();
    assert!(error.contains("overlapping"), "{error}");
    let general = Image::open(&gap, &json!({})).unwrap();
    for index in 0..general.frames {
        assert!(general.combined_source(index).unwrap().is_none(), "{index}");
    }

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
    let (direct, direct_path) = map_rows_of(&mut session, &[&first, &second]);
    assert_eq!(direct.len(), 6);
    assert_ne!(direct[0], direct[1]);
    assert_eq!(
        direct_path,
        json!({"pipelineRuns":2,"frameParallel":6,"processed":0})
    );
    let (through_master, master_path) = map_rows(&mut session, &master);
    assert_eq!(master_path, direct_path);
    assert_eq!(through_master, direct);

    // Frames 2, 4 and 6 (1-based) straddle the file boundary.
    let stride = json!({"start":2,"step":2});
    let (strided, strided_path) = batch_rows(&mut session, &[&master], stride.clone());
    assert_eq!(strided_path, json!({"pipelineRuns":2,"frameParallel":3}));
    assert_eq!(
        strided,
        [direct[1].clone(), direct[3].clone(), direct[5].clone()]
    );

    let (filled, filled_path) = map_rows(&mut session, &gap);
    assert_eq!(
        filled_path,
        json!({"pipelineRuns":0,"frameParallel":0,"processed":0})
    );
    assert_eq!(filled.len(), 6);
    for (row, expected) in filled[..3]
        .iter()
        .zip(&direct)
        .chain([(&filled[5], &direct[3])])
    {
        for (a, b) in row.iter().zip(expected) {
            assert!((a - b).abs() <= 1e-9 * b.abs().max(1.), "{a} vs {b}");
        }
    }

    // pyFAI-compatible splitting goes through the processed series path.
    call(
        &mut session,
        "integration_settings",
        json!({"method":"pyfai"}),
    );
    let (direct, direct_path) = map_rows_of(&mut session, &[&first, &second]);
    assert_eq!(
        direct_path,
        json!({"pipelineRuns":2,"frameParallel":6,"processed":6})
    );
    let (through_master, master_path) = map_rows(&mut session, &master);
    assert_eq!(master_path, direct_path);
    assert_eq!(through_master, direct);
    let (strided, _) = batch_rows(&mut session, &[&master], stride);
    assert_eq!(
        strided,
        [direct[1].clone(), direct[3].clone(), direct[5].clone()]
    );
}

fn close_rows(actual: &[f64], expected: &[f64]) {
    assert_eq!(actual.len(), expected.len());
    for (a, b) in actual.iter().zip(expected) {
        assert!((a - b).abs() <= 1e-9 * b.abs().max(1.), "{a} vs {b}");
    }
}

/// Two blocks of one source file share its raw reader; the second block is
/// neither a changed source nor a reason to reopen the file.
#[test]
fn two_blocks_from_one_source_file_use_the_fast_path() {
    let temp = tempfile::tempdir().unwrap();
    std::fs::create_dir(temp.path().join("scan0001")).unwrap();
    let fixture = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/combined-counts.h5");
    let first = temp.path().join("scan0001/eiger_0000.h5");
    std::fs::copy(&fixture, &first).unwrap();
    let split = temp.path().join("split.h5");
    master_over(
        &split,
        3,
        &[
            ("scan0001/eiger_0000.h5", 0..2, 0),
            ("scan0001/eiger_0000.h5", 2..3, 2),
        ],
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
    for (method, processed) in [("polygon", 0), ("pyfai", 3)] {
        call(
            &mut session,
            "integration_settings",
            json!({"method":method}),
        );
        let (direct, _) = map_rows(&mut session, &first);
        let (through_master, path) = map_rows(&mut session, &split);
        assert_eq!(
            path,
            json!({"pipelineRuns":2,"frameParallel":3,"processed":processed}),
            "{method}"
        );
        assert_eq!(through_master, direct, "{method}");

        // Selecting the second block's frame reintegrates it alone.
        let selected = call(
            &mut session,
            "map_select",
            json!({"index":2,"reintegrate":true}),
        );
        let y: Vec<f64> = selected.result["pattern"]["y"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_f64().unwrap())
            .collect();
        close_rows(&y, &direct[2]);
    }
}

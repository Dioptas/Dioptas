// Frozen independent Python reference outputs, replayed entirely in Rust.
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{collections::HashMap, path::Path};

fn substitute(value: &mut Value, directory: &Path) {
    match value {
        Value::String(s) if s.starts_with("$FIXTURES/") => {
            *s = directory.join(&s[10..]).to_string_lossy().into_owned()
        }
        Value::Array(items) => items.iter_mut().for_each(|v| substitute(v, directory)),
        Value::Object(items) => items.values_mut().for_each(|v| substitute(v, directory)),
        _ => {}
    }
}
fn call(
    session: &mut Session,
    command: &Value,
    directory: &Path,
    buffers: &mut HashMap<String, Vec<u8>>,
) -> Reply {
    let mut payload = command["payload"].clone();
    substitute(&mut payload, directory);
    let reply = session.invoke(&Request {
        id: 1,
        action: command["action"].as_str().unwrap().into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(
        reply.result["ok"], true,
        "{}: {}",
        command["action"], reply.result
    );
    for b in &reply.buffers {
        buffers.insert(b.id.clone(), (*b.bytes).clone());
    }
    reply
}
#[test]
fn independent_numerical_outputs_match_frozen_references() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let directory = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/reference-data");
    let reference: Value =
        serde_json::from_str(include_str!("../fixtures/reference-data/numerical.json")).unwrap();
    assert_eq!(reference["schemaVersion"], 1);
    for (name, expected) in reference["provenance"]["inputs"].as_object().unwrap() {
        let bytes = std::fs::read(directory.join(name)).unwrap();
        assert_eq!(
            format!("{:x}", Sha256::digest(bytes)),
            expected.as_str().unwrap(),
            "Fixture input changed: {name}"
        );
    }
    for case in reference["cases"].as_array().unwrap() {
        let mut session = Session::new(root.clone());
        let mut buffers = HashMap::new();
        for setup in case["setup"].as_array().unwrap() {
            call(&mut session, setup, &directory, &mut buffers);
        }
        for step in case["steps"].as_array().unwrap() {
            let reply = call(&mut session, step, &directory, &mut buffers);
            for check in step["checks"].as_array().unwrap() {
                let value = reply
                    .result
                    .pointer(check["path"].as_str().unwrap())
                    .unwrap();
                let actual: Vec<f64> = if check["raster"] == true {
                    let bytes = &buffers[value["bufferId"].as_str().unwrap()];
                    match value["dtype"].as_str().unwrap() {
                        "u8" => bytes.iter().map(|&v| f64::from(v)).collect(),
                        "f32le" => bytes
                            .as_chunks::<4>()
                            .0
                            .iter()
                            .map(|b| f64::from(f32::from_le_bytes(*b)))
                            .collect(),
                        dtype => panic!("Unsupported fixture raster dtype {dtype}"),
                    }
                } else {
                    serde_json::from_value(value.clone()).unwrap()
                };
                let expected = check["expected"].as_array().unwrap();
                assert_eq!(
                    actual.len(),
                    expected.len(),
                    "{} {}",
                    case["name"],
                    check["path"]
                );
                let rtol = check["rtol"].as_f64().unwrap();
                let atol = check["atol"].as_f64().unwrap();
                for (i, (actual, expected)) in actual.iter().zip(expected).enumerate() {
                    let expected = if let Some(b) = expected.as_bool() {
                        f64::from(b)
                    } else {
                        expected.as_f64().unwrap()
                    };
                    assert!(
                        actual.is_finite()
                            && (actual - expected).abs() <= atol + rtol * expected.abs(),
                        "{} {} {} [{i}]: {actual} != {expected}",
                        case["name"],
                        step.get("label").unwrap_or(&json!("")),
                        check["path"]
                    );
                }
            }
        }
    }
}

/// pyFAI 2θ for PONI files on raw image pixels (see poni-orientation.json).
/// The Dioptas case also pins the file Dioptas writes for plain pixel sizes,
/// so a changed writer must be reviewed against pyFAI again.
#[test]
fn poni_files_match_pyfai_on_raw_image_rows() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let directory = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/reference-data");
    let reference: Value = serde_json::from_str(include_str!(
        "../fixtures/reference-data/poni-orientation.json"
    ))
    .unwrap();
    assert_eq!(reference["schemaVersion"], 1);
    for (name, expected) in reference["provenance"]["inputs"].as_object().unwrap() {
        let bytes = std::fs::read(directory.join(name)).unwrap();
        assert_eq!(
            format!("{:x}", Sha256::digest(bytes)),
            expected.as_str().unwrap(),
            "Fixture input changed: {name}"
        );
    }
    let tolerance = reference["provenance"]["tolerance"]["twoThetaDeg"]
        .as_f64()
        .unwrap();
    let [height, width] = [40usize, 60];
    assert_eq!(
        reference["provenance"]["imageShape"],
        json!([height, width])
    );
    let temp = tempfile::tempdir().unwrap();
    let image = temp.path().join("raw.npy");
    let mut header =
        format!("{{'descr': '<f8', 'fortran_order': False, 'shape': ({height}, {width}), }}");
    while (10 + header.len() + 1) % 64 != 0 {
        header.push(' ');
    }
    header.push('\n');
    let mut bytes = b"\x93NUMPY\x01\x00".to_vec();
    bytes.extend_from_slice(&(header.len() as u16).to_le_bytes());
    bytes.extend_from_slice(header.as_bytes());
    for i in 0..height * width {
        bytes.extend_from_slice(&(i as f64).to_le_bytes());
    }
    std::fs::write(&image, bytes).unwrap();
    let geometry_lines = |text: &str| {
        text.lines()
            .filter(|line| !line.trim_start().starts_with('#'))
            .map(str::to_owned)
            .collect::<Vec<_>>()
    };
    let run = |session: &mut Session, action: &str, payload: Value| {
        let reply = session.invoke(&Request {
            id: 1,
            action: action.into(),
            payload,
            cached_buffers: vec![],
        });
        assert_eq!(reply.result["ok"], true, "{action}: {}", reply.result);
        reply.result
    };
    for case in reference["cases"].as_array().unwrap() {
        let name = case["poni"].as_str().unwrap();
        let fixture = directory.join(name);
        let mut session = Session::new(root.clone());
        run(&mut session, "open_image", json!({"path":image}));
        if name == "poni-orientation-dioptas.poni" {
            // Calibrate with plain pixel sizes and save, as a user would.
            run(
                &mut session,
                "manual_geometry",
                json!({"convention":"pyfai","values":{"dist":0.1,"poni1":0.001,"poni2":0.003,"rot1":0.05,"rot2":0.1,"rot3":0.02,"pixel1":0.0001,"pixel2":0.0001,"wavelength":3e-11,"polarization_factor":0.99}}),
            );
            let saved = temp.path().join("saved.poni");
            run(&mut session, "save_calibration", json!({"path":saved}));
            assert_eq!(
                geometry_lines(&std::fs::read_to_string(&saved).unwrap()),
                geometry_lines(&std::fs::read_to_string(&fixture).unwrap()),
                "Dioptas no longer writes the file pyFAI was checked against"
            );
        } else {
            run(&mut session, "open_calibration", json!({"path":fixture}));
        }
        for point in case["twoThetaDeg"].as_array().unwrap() {
            let [row, column, expected] = [0, 1, 2].map(|i| point[i].as_f64().unwrap());
            // pyFAI file rows run top-down; Dioptas pixel rows bottom-up.
            let pixel = run(
                &mut session,
                "pixel",
                json!({"x":column,"y":height as f64 - 1.0 - row,"source":"raw_detector"}),
            );
            assert_eq!(
                pixel["pixel"]["value"],
                json!(row * width as f64 + column),
                "{name}: readout is not file pixel ({row}, {column})"
            );
            let actual = pixel["pixel"]["twoTheta"].as_f64().unwrap();
            assert!(
                (actual - expected).abs() <= tolerance,
                "{name} ({row}, {column}): Dioptas {actual}, pyFAI {expected}"
            );
        }
    }
}

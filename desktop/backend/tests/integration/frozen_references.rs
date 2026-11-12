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
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
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

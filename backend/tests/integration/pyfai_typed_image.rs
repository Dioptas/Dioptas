#![cfg(feature = "dioptrin")]
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::Path;

fn call(session: &mut Session, action: &str, mut payload: Value) -> Reply {
    payload["requested_products"] = json!({"cake":false,"rings":false});
    let reply = session.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(reply.result["ok"], true, "{action}: {}", reply.result);
    reply
}
fn same_bits(a: &Value, b: &Value) {
    for key in ["x", "y", "sigma", "azimuthalStd"] {
        match (a[key].as_array(), b[key].as_array()) {
            (Some(a), Some(b)) => {
                assert_eq!(a.len(), b.len(), "{key}");
                for (a, b) in a.iter().zip(b) {
                    if a.is_null() || b.is_null() {
                        assert_eq!(a, b, "{key}");
                        continue;
                    }
                    assert_eq!(
                        a.as_f64().unwrap().to_bits(),
                        b.as_f64().unwrap().to_bits(),
                        "{key}"
                    );
                }
            }
            (None, None) => {}
            _ => panic!("{key} presence differs"),
        }
    }
}
fn typed_calls(s: &mut Session) -> u64 {
    call(s,"integration_diagnostics",json!({})).result["integrationDiagnostics"]["typedImageIntegrations"].as_u64().unwrap()
}

#[test]
fn interactive_integer_patterns_match_float_reference_across_settings_and_navigation() {
    let temp = tempfile::tempdir().unwrap();
    let shape = [3, 43, 57];
    let count: usize = shape.iter().product();
    let raw: Vec<u32> = (0..count)
        .map(|i| {
            if i % 109 == 0 {
                u32::MAX
            } else {
                (i as u32).wrapping_mul(2654435761)
            }
        })
        .collect();
    let image = temp.path().join("samples.h5");
    let f = hdf5::File::create(&image).unwrap();
    f.new_dataset::<u32>()
        .shape(shape)
        .create("integer")
        .unwrap()
        .write_raw(&raw)
        .unwrap();
    f.new_dataset::<f64>()
        .shape(shape)
        .create("float")
        .unwrap()
        .write_raw(&raw.iter().map(|&v| f64::from(v)).collect::<Vec<_>>())
        .unwrap();
    drop(f);
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
    let mut integer = Session::new(root.clone());
    let mut reference = Session::new(root);
    for (s, dataset) in [(&mut integer, "integer"), (&mut reference, "float")] {
        call(
            s,
            "manual_geometry",
            json!({"convention":"pyfai","values":{"dist":0.12,"poni1":0.0017,"poni2":0.0021,"rot1":0.01,"rot2":-0.03,"rot3":0.02,"pixel1":0.0001,"pixel2":0.00012,"wavelength":5e-11,"polarization_factor":0.965}}),
        );
        call(
            s,
            "integration_settings",
            json!({"method":"pyfai_full","bins":67,"poisson_errors":true,"trim_zeros":false}),
        );
        call(s, "open_image", json!({"path":image,"dataset":dataset}));
    }
    let changes = [
        ("integrate", json!({})),
        ("next_image", json!({"direction":1})),
        ("integration_roi", json!({"limits":[2,38,3,51]})),
        (
            "integration_settings",
            json!({"bins":83,"unit":"q_A^-1","solid_angle":false}),
        ),
        (
            "integration_settings",
            json!({"unit":"d_A","azimuth_range":[150.,-150.],"poisson_errors":false,"trim_zeros":true}),
        ),
    ];
    for (action, payload) in changes {
        let a = call(&mut integer, action, payload.clone());
        let b = call(&mut reference, action, payload);
        same_bits(&a.result["pattern"], &b.result["pattern"]);
    }
    assert!(typed_calls(&mut integer) > 0);
    assert_eq!(typed_calls(&mut reference), 0);
    // Dynamic masks, spread and transforms must integrate current scientific
    // values rather than accidentally using the acquisition buffer.
    for (action, payload) in [
        (
            "mask_plugin",
            json!({"name":"Threshold Mask","enabled":true,"settings":{"above_enabled":true,"above_value":1000000000.}}),
        ),
        ("integration_settings", json!({"azimuthal_std":true})),
        ("image_transform", json!({"operation":"flip_horizontal"})),
        ("next_image", json!({"direction":1})),
    ] {
        let before = typed_calls(&mut integer);
        let a = call(&mut integer, action, payload.clone());
        let b = call(&mut reference, action, payload);
        same_bits(&a.result["pattern"], &b.result["pattern"]);
        assert_eq!(typed_calls(&mut integer), before);
    }
}

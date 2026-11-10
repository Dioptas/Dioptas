//! Edge trimming changes the displayed/exported curve, never the series grid.
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
fn call(session: &mut Session, action: &str, payload: Value) -> Reply {
    let r = session.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn values(reply: &Reply, name: &str) -> Vec<f64> {
    reply.result["pattern"][name]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap())
        .collect()
}
fn assert_trimmed(full: &Reply, trimmed: &Reply) -> usize {
    let y = values(full, "y");
    let start = y.iter().position(|v| *v != 0.).unwrap();
    let end = y.iter().rposition(|v| *v != 0.).unwrap() + 1;
    for key in ["x", "y", "sigma", "azimuthalStd"] {
        if full.result["pattern"][key].is_array() {
            assert_eq!(values(trimmed, key), values(full, key)[start..end], "{key}");
        }
    }
    for reply in [full, trimmed] {
        if reply.result["pattern"]["spottiness"].is_object() {
            for (diagnostic, pattern) in [("x", "x"), ("mean", "y"), ("std", "azimuthalStd")] {
                assert_eq!(
                    reply.result["pattern"]["spottiness"][diagnostic],
                    reply.result["pattern"][pattern]
                );
            }
        }
    }
    y.len() - (end - start)
}

#[test]
fn image_002_trims_default_pattern_and_export_without_changing_cake() {
    let mut s = Session::new(root());
    let initial = call(&mut s, "state", json!({}));
    assert_eq!(initial.result["state"]["integration"]["trimZeros"], true);
    call(
        &mut s,
        "open_calibration",
        json!({"path":root().join("dioptas/tests/data/LaB6_40keV_MarCCD.poni")}),
    );
    call(
        &mut s,
        "integration_settings",
        json!({"bins":1000,"cake_bins":24,"poisson_errors":true}),
    );
    call(
        &mut s,
        "open_image",
        json!({"path":root().join("dioptas/tests/data/image_002.tif")}),
    );
    for unit in ["2th_deg", "q_A^-1", "d_A"] {
        let full = call(
            &mut s,
            "integration_settings",
            json!({"unit":unit,"trim_zeros":false}),
        );
        let trimmed = call(&mut s, "integration_settings", json!({"trim_zeros":true}));
        assert!(
            assert_trimmed(&full, &trimmed) > 0,
            "image_002 should have zero edges"
        );
        assert_eq!(full.result["cake"], trimmed.result["cake"]);
        assert_eq!(trimmed.result["cake"]["width"], 1000);
    }
    let dir = tempfile::tempdir().unwrap();
    let export = dir.path().join("trimmed.xye");
    let before = call(&mut s, "state", json!({}));
    call(&mut s, "integration_save_pattern", json!({"path":export}));
    let text = std::fs::read_to_string(export).unwrap();
    let rows: Vec<Vec<f64>> = text
        .lines()
        .filter(|l| !l.starts_with('#'))
        .map(|l| l.split_whitespace().map(|v| v.parse().unwrap()).collect())
        .collect();
    for (column, key) in ["x", "y", "sigma"].into_iter().enumerate() {
        let expected = values(&before, key);
        let actual: Vec<f64> = rows.iter().map(|row| row[column]).collect();
        assert_eq!(expected.len(), actual.len());
        for (a, b) in actual.iter().zip(&expected) {
            assert!((a - b).abs() < 1e-6 * (1. + b.abs()));
        }
    }
}

#[test]
fn zero_edges_and_diagnostics_follow_warm_plans_and_series_keep_a_shared_grid() {
    let dir = tempfile::tempdir().unwrap();
    let source = dir.path().join("partial.h5");
    let [h, w] = [32, 40];
    let mut pixels = vec![0.; 3 * h * w];
    for frame in 1..3 {
        for row in 8..16 {
            for col in (8 * frame)..(8 * frame + 6) {
                pixels[frame * h * w + row * w + col] = 100.;
            }
        }
    }
    {
        let f = hdf5::File::create(&source).unwrap();
        f.new_dataset::<f64>()
            .shape([3, h, w])
            .create("counts")
            .unwrap()
            .write_raw(&pixels)
            .unwrap();
    }
    let mut s = Session::new(root());
    call(
        &mut s,
        "integration_settings",
        json!({"bins":64,"cake_bins":12,"poisson_errors":true}),
    );
    call(
        &mut s,
        "manual_geometry",
        json!({"convention":"pyfai","values":{"dist":0.1,"poni1":0.,"poni2":0.,"rot1":0.,"rot2":0.,"rot3":0.,"pixel1":0.0001,"pixel2":0.0001,"wavelength":4e-11,"polarization_factor":0.}}),
    );
    let dark = call(
        &mut s,
        "open_image",
        json!({"path":source,"dataset":"/counts"}),
    );
    assert_eq!(values(&dark, "y"), vec![0.; 64]);
    call(
        &mut s,
        "open_image",
        json!({"path":source,"dataset":"/counts","frame":1}),
    );
    for spread in [false, true] {
        call(
            &mut s,
            "integration_settings",
            json!({"azimuthal_std":spread}),
        );
        let full = call(&mut s, "integration_settings", json!({"trim_zeros":false}));
        let trimmed = call(&mut s, "integration_settings", json!({"trim_zeros":true}));
        let y = values(&full, "y");
        assert_eq!(y[0], 0.);
        assert_eq!(*y.last().unwrap(), 0.);
        assert!(assert_trimmed(&full, &trimmed) > 0);
        let warm = call(&mut s, "integrate", json!({}));
        assert_eq!(warm.result["pattern"], trimmed.result["pattern"]);
    }
    call(
        &mut s,
        "integration_settings",
        json!({"azimuthal_std":false}),
    );
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(&mut s, "combination_settings", json!({"patterns":true}));
    let full = call(&mut s, "integration_settings", json!({"trim_zeros":false}));
    let trimmed = call(&mut s, "integration_settings", json!({"trim_zeros":true}));
    assert!(assert_trimmed(&full, &trimmed) > 0);
    call(&mut s, "combination_settings", json!({"patterns":false}));
    let batch = call(&mut s, "batch_load", json!({"paths":[source]}));
    assert_eq!(batch.result["batch"]["x"].as_array().unwrap().len(), 64);
    assert_eq!(
        batch.result["batch"]["entries"].as_array().unwrap().len(),
        3
    );
    assert_eq!(batch.result["state"]["integration"]["trimZeros"], true);
    let project = dir.path().join("trim.dio");
    call(&mut s, "save_project", json!({"path":project}));
    call(&mut s, "integration_settings", json!({"trim_zeros":false}));
    let restored = call(&mut s, "open_project", json!({"path":project}));
    assert_eq!(restored.result["state"]["integration"]["trimZeros"], true);
}

//! Native equivalents of the legacy functional flows. No mocked integrator,
//! Python writer, Qt application, or installed Python runtime is involved.
#![cfg(feature = "dioptrin")]
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn invoke(s: &mut Session, action: &str, payload: Value) -> Reply {
    s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    })
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = invoke(s, action, payload);
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn npy(path: &Path, shape: [usize; 2], values: &[f64]) {
    assert_eq!(shape[0] * shape[1], values.len());
    let mut header = format!(
        "{{'descr': '<f8', 'fortran_order': False, 'shape': ({}, {}), }}",
        shape[0], shape[1]
    );
    while (10 + header.len() + 1) % 64 != 0 {
        header.push(' ');
    }
    header.push('\n');
    let mut f = fs::File::create(path).unwrap();
    f.write_all(b"\x93NUMPY\x01\x00").unwrap();
    f.write_all(&(header.len() as u16).to_le_bytes()).unwrap();
    f.write_all(header.as_bytes()).unwrap();
    for v in values {
        f.write_all(&v.to_le_bytes()).unwrap();
    }
}
fn image(path: &Path, offset: f64) {
    npy(
        path,
        [24, 32],
        &(0..768)
            .map(|i| 100. + offset + (i / 32) as f64 * 3. + (i % 32) as f64 * 2.)
            .collect::<Vec<_>>(),
    );
}
fn poni(path: &Path) {
    fs::write(path,"PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.13\nPoni1: 0.0012\nPoni2: 0.0016\nRot1: 0.008\nRot2: -0.013\nRot3: 0.02\nSplineFile: None\nWavelength: 5e-11\n").unwrap();
}
fn prepared(source: &Path, calibration: &Path, unit: &str) -> Session {
    let mut s = Session::new(root());
    call(&mut s, "open_calibration", json!({"path":calibration}));
    call(
        &mut s,
        "integration_settings",
        json!({"bins":48,"cake_bins":12,"unit":unit,"trim_zeros":false}),
    );
    call(&mut s, "open_image", json!({"path":source}));
    s
}
fn values(r: &Reply, key: &str) -> Vec<f64> {
    r.result["pattern"][key]
        .as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_f64().unwrap())
        .collect()
}
fn close(a: &[f64], b: &[f64]) {
    assert_eq!(a.len(), b.len());
    for (a, b) in a.iter().zip(b) {
        assert!((a - b).abs() < 2e-10 * (1. + b.abs()), "{a} != {b}");
    }
}
fn bytes<'a>(r: &'a Reply, key: &str) -> &'a [u8] {
    let id = r.result[key]["bufferId"].as_str().unwrap();
    r.buffers
        .iter()
        .find(|b| b.id == id)
        .unwrap()
        .bytes
        .as_slice()
}

fn processing_export_project_flow(unit: &str) {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let source = d.join("counts.npy");
    let calibration = d.join("geometry.poni");
    let background = d.join("background.npy");
    let flat = d.join("flat.npy");
    let reference = d.join("reference.npy");
    image(&source, 0.);
    poni(&calibration);
    let raw: Vec<_> = (0..768)
        .map(|i| 100. + (i / 32) as f64 * 3. + (i % 32) as f64 * 2.)
        .collect();
    let response: Vec<_> = (0..768).map(|i| 2. + (i % 32) as f64 * 0.02).collect();
    let mean = response.iter().sum::<f64>() / 768.;
    let expected: Vec<_> = raw
        .iter()
        .zip(&response)
        .map(|(v, f)| (v - 4. * 0.7 - 1.2) / (f / mean))
        .collect();
    npy(&background, [24, 32], &vec![4.; 768]);
    npy(&flat, [24, 32], &response);
    npy(&reference, [24, 32], &expected);
    let mask = d.join("mask.npy");
    let mut mask_values = vec![0.; 768];
    mask_values[5 * 32 + 9] = 1.;
    npy(&mask, [24, 32], &mask_values);
    let mut s = prepared(&source, &calibration, unit);
    call(&mut s, "mask_file", json!({"path":mask}));
    call(
        &mut s,
        "integration_image_background",
        json!({"path":background,"scale":0.7,"offset":1.2}),
    );
    call(&mut s, "integration_flat_field", json!({"path":flat}));
    call(&mut s, "integration_roi", json!({"limits":[2,22,3,29]}));
    call(
        &mut s,
        "integration_settings",
        json!({"supersampling":2,"poisson_errors":true}),
    );
    let actual = call(&mut s, "state", json!({}));
    // Independently compute corrected counts, then integrate that image through
    // the same geometry/ROI. This catches processing order and persistence bugs.
    let mut independent = prepared(&reference, &calibration, unit);
    call(&mut independent, "mask_file", json!({"path":mask}));
    call(
        &mut independent,
        "integration_roi",
        json!({"limits":[2,22,3,29]}),
    );
    let expected_pattern = call(
        &mut independent,
        "integration_settings",
        json!({"supersampling":2}),
    );
    close(&values(&actual, "y"), &values(&expected_pattern, "y"));
    for (x, y) in [(0, 0), (9, 5), (31, 23)] {
        let p = call(&mut s, "pixel", json!({"x":x,"y":y}));
        close(
            &[p.result["pixel"]["value"].as_f64().unwrap()],
            &[expected[(23 - y) * 32 + x]],
        );
    }
    for suffix in ["xy", "xye", "chi", "dat", "fxye"] {
        let output = d.join(format!("profile.{suffix}"));
        call(&mut s, "integration_save_pattern", json!({"path":output}));
        let mut reader = Session::new(root());
        let reread = call(
            &mut reader,
            "integration_open_pattern",
            json!({"path":output}),
        );
        close(&values(&reread, "x"), &values(&actual, "x"));
        close(&values(&reread, "y"), &values(&actual, "y"));
        if ["xye", "fxye"].contains(&suffix) {
            // Imported PatternModel curves deliberately do not advertise
            // propagated errors. Verify the file's third column independently.
            let errors: Vec<f64> = fs::read_to_string(&output)
                .unwrap()
                .lines()
                .filter_map(|line| {
                    let f: Vec<_> = line.split_whitespace().collect();
                    if f.len() == 3 && f[0].parse::<f64>().is_ok() {
                        f[2].parse::<f64>().ok()
                    } else {
                        None
                    }
                })
                .collect();
            close(&errors, &values(&actual, "sigma"));
        }
    }
    let project = d.join("experiment.dio");
    call(&mut s, "save_project", json!({"path":project}));
    for file in [&source, &calibration, &background, &flat, &mask] {
        fs::remove_file(file).unwrap();
    }
    let mut restored = Session::new(root());
    let reopened = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(reopened.result["pattern"], actual.result["pattern"]);
    assert_eq!(bytes(&reopened, "cake"), bytes(&actual, "cake"));
    assert_eq!(bytes(&reopened, "mask"), bytes(&actual, "mask"));
    for key in [
        "roi",
        "supersampling",
        "poissonErrors",
        "imageBackground",
        "flatField",
    ] {
        assert_eq!(
            reopened.result["state"]["integration"][key],
            actual.result["state"]["integration"][key],
            "{key}"
        );
    }
    let reintegrated = call(&mut restored, "integrate", json!({}));
    close(&values(&reintegrated, "y"), &values(&actual, "y"));
}
#[test]
fn corrected_image_to_export_and_offline_project_in_2theta() {
    processing_export_project_flow("2th_deg");
}
#[test]
fn corrected_image_to_export_and_offline_project_in_q() {
    processing_export_project_flow("q_A^-1");
}
#[test]
fn corrected_image_to_export_and_offline_project_in_d() {
    processing_export_project_flow("d_A");
}

#[test]
fn binning_sectors_supersampling_and_roi_reintegrate_without_replacing_pixels() {
    let d = tempfile::tempdir().unwrap();
    let source = d.path().join("counts.npy");
    let p = d.path().join("g.poni");
    image(&source, 0.);
    poni(&p);
    let mut s = prepared(&source, &p, "2th_deg");
    let initial = call(&mut s, "state", json!({}));
    for bins in [23, 61] {
        for ss in [1, 2] {
            for sector in [json!(null), json!([-40, 70]), json!([150, -140])] {
                let r = call(
                    &mut s,
                    "integration_settings",
                    json!({"bins":bins,"cake_bins":17,"supersampling":ss,"azimuth_range":sector,"cake_azimuth_range":sector}),
                );
                assert_eq!(values(&r, "x").len(), bins);
                assert_eq!(r.result["cake"]["width"], bins);
                assert_eq!(r.result["cake"]["height"], 17);
                assert_eq!(r.result["rawImage"], initial.result["rawImage"]);
                assert!(values(&r, "y").iter().all(|v| v.is_finite()));
            }
        }
    }
    let before = call(&mut s, "state", json!({}));
    assert_eq!(
        invoke(&mut s, "integration_roi", json!({"limits":[12,3,0,32]})).result["ok"],
        false
    );
    assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    call(&mut s, "integration_roi", json!({"limits":[2,10,3,18]}));
    call(&mut s, "integration_roi", json!({"limits":null}));
    assert_eq!(
        call(&mut s, "state", json!({})).result["pattern"],
        before.result["pattern"]
    );
}

#[test]
fn batch_stride_save_reload_missing_raw_and_fresh_reintegration() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let p = d.join("g.poni");
    poni(&p);
    let paths: Vec<_> = (1..=6)
        .map(|i| {
            let p = d.join(format!("scan_{i:03}.npy"));
            image(&p, i as f64 * 40.);
            p
        })
        .collect();
    let mut s = prepared(&paths[0], &p, "q_A^-1");
    let mut expected = vec![];
    for i in [1, 3, 5] {
        expected.push(values(
            &call(&mut s, "open_image", json!({"path":paths[i]})),
            "y",
        ));
    }
    let loaded = call(
        &mut s,
        "batch_load",
        json!({"paths":paths,"start":2,"stop":6,"step":2}),
    );
    assert_eq!(
        loaded.result["batch"]["entries"].as_array().unwrap().len(),
        3
    );
    let output = d.join("stored.h5");
    call(&mut s, "integration_save_batch", json!({"path":output}));
    let file = hdf5::File::open(&output).unwrap();
    let data = file
        .dataset("processed/result/data")
        .unwrap()
        .read_raw::<f64>()
        .unwrap();
    close(&data, &expected.concat());
    drop(file);
    // Stored display remains useful after the raw acquisition is unavailable.
    for path in &paths {
        fs::remove_file(path).unwrap();
    }
    let mut restored = Session::new(root());
    call(&mut restored, "open_calibration", json!({"path":p}));
    call(&mut restored, "batch_open", json!({"path":output}));
    for (i, y) in expected.iter().enumerate() {
        let r = call(&mut restored, "batch_select", json!({"index":i}));
        close(&values(&r, "y"), y);
        assert!(r.result["image"].is_null());
    }
    // Restore the actual source files; a changed bin count must generate new
    // profiles, rather than silently retaining the loaded 48-bin matrix.
    for (i, path) in paths.iter().enumerate() {
        image(path, (i + 1) as f64 * 40.);
    }
    call(
        &mut restored,
        "integration_settings",
        json!({"bins":31,"cake_bins":9,"unit":"q_A^-1"}),
    );
    let fresh = call(
        &mut restored,
        "batch_load",
        json!({"paths":paths,"start":2,"stop":6,"step":2}),
    );
    assert_eq!(fresh.result["batch"]["x"].as_array().unwrap().len(), 31);
    let selected = call(&mut restored, "batch_select", json!({"index":2}));
    let mut direct = prepared(&paths[5], &p, "q_A^-1");
    let direct = call(&mut direct, "integration_settings", json!({"bins":31}));
    close(&values(&selected, "y"), &values(&direct, "y"));
}

#[test]
fn batch_discovery_uses_natural_order_and_bad_input_cannot_replace_results() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let p = d.join("g.poni");
    poni(&p);
    let a = d.join("scan_2.npy");
    let b = d.join("scan_10.npy");
    image(&a, 20.);
    image(&b, 100.);
    let mut s = prepared(&a, &p, "2th_deg");
    let first = call(&mut s, "state", json!({}));
    call(&mut s, "batch_folder", json!({"path":d}));
    close(
        &values(&call(&mut s, "batch_select", json!({"index":0})), "y"),
        &values(&first, "y"),
    );
    let before = call(&mut s, "state", json!({}));
    let broken = d.join("scan_11.npy");
    fs::write(&broken, b"broken").unwrap();
    assert_eq!(
        invoke(&mut s, "batch_folder", json!({"path":d})).result["ok"],
        false
    );
    assert_eq!(call(&mut s, "state", json!({})).result, before.result);
}

#[test]
fn image_add_average_and_staged_tiff_export_preserve_sources() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let a = d.join("a.npy");
    let b = d.join("b.npy");
    let p = d.join("g.poni");
    image(&a, 0.);
    image(&b, 40.);
    poni(&p);
    let original = fs::read(&a).unwrap();
    let mut s = prepared(&a, &p, "2th_deg");
    for (mode, expected) in [("add", 378.), ("average", 189.)] {
        call(
            &mut s,
            "open_image",
            json!({"paths":[a,b],"multiple":true,"batch_mode":mode}),
        );
        let pixel = call(&mut s, "pixel", json!({"x":0,"y":0}));
        assert_eq!(pixel.result["pixel"]["value"], expected);
    }
    call(
        &mut s,
        "open_image",
        json!({"paths":[a,b],"multiple":true,"batch_mode":"save","output_directory":d}),
    );
    let output = d.join("batch_a.tiff");
    let mut decoder = tiff::decoder::Decoder::new(fs::File::open(&output).unwrap()).unwrap();
    assert_eq!(decoder.dimensions().unwrap(), (32, 24));
    match decoder.read_image().unwrap() {
        tiff::decoder::DecodingResult::I32(v) => {
            let expected: Vec<i32> = (0..768)
                .map(|i| 100 + (i / 32) * 3 + (i % 32) * 2)
                .collect();
            assert_eq!(v, expected);
        }
        other => panic!("Expected original integer TIFF: {other:?}"),
    }
    let before = fs::read(&output).unwrap();
    assert_eq!(
        invoke(
            &mut s,
            "open_image",
            json!({"paths":[a,b],"multiple":true,"batch_mode":"save","output_directory":d})
        )
        .result["ok"],
        false
    );
    assert_eq!(fs::read(&output).unwrap(), before);
    assert_eq!(fs::read(a).unwrap(), original);
}

#[test]
fn mask_file_formats_flips_and_undo_preserve_exact_detector_coordinates() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let a = d.join("a.npy");
    let p = d.join("g.poni");
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    let m = d.join("mask.npy");
    let mut data = vec![0.; 768];
    data[3 * 32 + 7] = 1.;
    data[20 * 32 + 28] = 1.;
    npy(&m, [24, 32], &data);
    let loaded = call(&mut s, "mask_file", json!({"path":m}));
    let original = bytes(&loaded, "mask").to_vec();
    for ext in ["npy", "mask", "edf"] {
        let path = d.join(format!("saved.{ext}"));
        call(&mut s, "mask_file", json!({"path":path,"save":true}));
        call(&mut s, "clear_mask", json!({}));
        let reloaded = call(&mut s, "mask_file", json!({"path":path}));
        assert_eq!(bytes(&reloaded, "mask"), original);
        let flipped = call(&mut s, "mask_file", json!({"path":path,"flipud":true}));
        for r in 0..24 {
            assert_eq!(
                &bytes(&flipped, "mask")[r * 32..(r + 1) * 32],
                &original[(23 - r) * 32..(24 - r) * 32]
            );
        }
        assert_eq!(
            bytes(&call(&mut s, "undo_mask", json!({})), "mask"),
            original
        );
    }
}

#[test]
fn unsupported_legacy_corrections_fail_atomically_instead_of_becoming_noops() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.npy");
    let p = d.path().join("g.poni");
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    let before = call(&mut s, "state", json!({}));
    for kind in ["cylinder", "sphere"] {
        let r = invoke(
            &mut s,
            "integration_correction",
            json!({"kind":kind,"enabled":true,"parameters":{}}),
        );
        assert_eq!(r.result["ok"], false);
        assert!(
            r.result["error"]
                .as_str()
                .unwrap()
                .contains("Unsupported correction")
        );
        assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    }
}

#[test]
fn map_dropped_frame_layers_selection_and_units_follow_stored_data() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let p = d.join("g.poni");
    poni(&p);
    let paths: Vec<_> = (0..5)
        .map(|i| {
            let p = d.join(format!("scan_{i:03}.npy"));
            image(&p, i as f64 * 40.);
            p
        })
        .collect();
    let mut s = prepared(&paths[0], &p, "2th_deg");
    let mut curves = vec![];
    for path in &paths {
        curves.push(values(
            &call(&mut s, "open_image", json!({"path":path})),
            "y",
        ));
    }
    let scan = call(&mut s, "map_load", json!({"paths":paths}));
    let axis = values(&call(&mut s, "state", json!({})), "x");
    call(
        &mut s,
        "map_roi",
        json!({"op":"update","name":"A","minimum":axis[5],"maximum":axis[40],"reduction":"sum","background":false}),
    );
    call(&mut s, "map_roi", json!({"op":"add"}));
    call(
        &mut s,
        "map_roi",
        json!({"op":"update","name":"B","minimum":axis[10],"maximum":axis[35],"reduction":"mean","background":false}),
    );
    let layer = call(
        &mut s,
        "map_expression",
        json!({"name":"Contrast","expression":"A-2*B"}),
    );
    let expected: Vec<_> = curves
        .iter()
        .map(|y| y[6..40].iter().sum::<f64>() - 2. * y[11..35].iter().sum::<f64>() / 24.)
        .collect();
    let flat = |r: &Reply| {
        r.result["map"]["values"]
            .as_array()
            .unwrap()
            .iter()
            .flat_map(|row| row.as_array().unwrap())
            .filter_map(Value::as_f64)
            .collect::<Vec<_>>()
    };
    close(&flat(&layer), &expected);
    call(&mut s, "map_arrange", json!({"op":"insert","slot":1}));
    let layout = call(&mut s, "map_grid", json!({"rows":2,"columns":3}));
    assert_eq!(
        layout.result["map"]["indices"],
        json!([[0, -1, 1], [2, 3, 4]])
    );
    assert!(layout.result["map"]["values"][0][1].is_null());
    call(&mut s, "integration_settings", json!({"unit":"q_A^-1"}));
    let selected = call(&mut s, "map_select", json!({"index":3,"reintegrate":true}));
    assert_eq!(selected.result["pattern"]["unit"], "2th_deg");
    close(&values(&selected, "y"), &curves[3]);
    let active = call(&mut s, "map_layer", json!({"name":"A"}));
    assert_eq!(active.result["map"]["active"], "A");
    let before = call(&mut s, "state", json!({}));
    assert_eq!(
        invoke(
            &mut s,
            "map_expression",
            json!({"name":"bad","expression":"__import__('os')"})
        )
        .result["ok"],
        false
    );
    assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    assert_eq!(scan.result["map"]["points"], 5);
}

#[test]
fn batch_normalization_is_reversible_and_saved_f64_data_reopens() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let p = d.join("g.poni");
    poni(&p);
    let paths: Vec<_> = (0..3)
        .map(|i| {
            let p = d.join(format!("scan_{i:03}.npy"));
            image(&p, i as f64 * 40.);
            p
        })
        .collect();
    let mut s = prepared(&paths[0], &p, "2th_deg");
    call(&mut s, "batch_load", json!({"paths":paths}));
    let raw = d.join("raw.h5");
    call(&mut s, "integration_save_batch", json!({"path":raw}));
    let data = hdf5::File::open(&raw)
        .unwrap()
        .dataset("processed/result/data")
        .unwrap()
        .read_raw::<f64>()
        .unwrap();
    call(
        &mut s,
        "batch_normalize",
        json!({"enabled":true,"start":3,"stop":44,"reference":2}),
    );
    let normalized = d.join("normalized.h5");
    call(&mut s, "integration_save_batch", json!({"path":normalized}));
    let norm = hdf5::File::open(&normalized)
        .unwrap()
        .dataset("processed/result/data")
        .unwrap()
        .read_raw::<f64>()
        .unwrap();
    assert_ne!(norm, data);
    // All normalized profiles must have the reference frame's window area.
    let sum = |y: &[f64]| y[2..44].iter().sum::<f64>();
    for y in norm.as_chunks::<48>().0 {
        close(&[sum(y)], &[sum(&data[48..96])]);
    }
    let mut restored = Session::new(root());
    call(&mut restored, "batch_open", json!({"path":normalized}));
    call(&mut restored, "batch_normalize", json!({"enabled":false}));
    let output = d.join("restored.h5");
    call(
        &mut restored,
        "integration_save_batch",
        json!({"path":output}),
    );
    let actual = hdf5::File::open(&output)
        .unwrap()
        .dataset("processed/result/data")
        .unwrap()
        .read_raw::<f64>()
        .unwrap();
    assert_eq!(actual, data);
}

#[test]
fn linked_detector_and_cake_positions_retain_physical_angle_across_units() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.npy");
    let p = d.path().join("g.poni");
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    let linked = call(
        &mut s,
        "validation_position",
        json!({"source":"image","x":12.25,"y":17.75}),
    );
    let angle = linked.result["linked"]["twoTheta"].as_f64().unwrap();
    assert!(angle > 0.);
    let q = call(&mut s, "integration_settings", json!({"unit":"q_A^-1"}));
    let expected = 4. * std::f64::consts::PI * (angle.to_radians() / 2.).sin() / 0.5;
    close(
        &[q.result["linked"]["radial"].as_f64().unwrap()],
        &[expected],
    );
    let d = call(&mut s, "integration_settings", json!({"unit":"d_A"}));
    close(
        &[d.result["linked"]["radial"].as_f64().unwrap()],
        &[std::f64::consts::TAU / expected],
    );
    assert_eq!(
        q.result["linked"]["contours"],
        d.result["linked"]["contours"]
    );
    let cake = call(
        &mut s,
        "validation_position",
        json!({"source":"cake","x":angle,"azimuth":15.}),
    );
    close(
        &[cake.result["linked"]["twoTheta"].as_f64().unwrap()],
        &[angle],
    );
}

#[test]
fn error_export_requires_current_errors_and_does_not_overwrite_on_failure() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let a = d.join("a.npy");
    let p = d.join("g.poni");
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    let output = d.join("profile.xye");
    fs::write(&output, b"previous output").unwrap();
    let failed = invoke(&mut s, "integration_save_pattern", json!({"path":output}));
    assert_eq!(failed.result["ok"], false);
    assert!(failed.result["error"].as_str().unwrap().contains("Poisson"));
    assert_eq!(fs::read(&output).unwrap(), b"previous output");
    call(
        &mut s,
        "integration_settings",
        json!({"poisson_errors":true}),
    );
    call(&mut s, "integration_save_pattern", json!({"path":output}));
    assert_ne!(fs::read(&output).unwrap(), b"previous output");
}

#[test]
fn incoming_file_integration_autosaves_and_mismatch_stops_without_mutation() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let a = d.join("scan_001.npy");
    let p = d.join("g.poni");
    let out = d.join("output");
    fs::create_dir(&out).unwrap();
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    call(&mut s, "integration_image_directory", json!({"path":d}));
    call(
        &mut s,
        "integration_autocreate",
        json!({"enabled":true,"directory":out}),
    );
    call(&mut s, "integration_autoprocess", json!({"enabled":true}));
    let b = d.join("scan_002.npy");
    image(&b, 40.);
    call(&mut s, "integration_autoprocess_poll", json!({}));
    call(&mut s, "integration_autoprocess_poll", json!({}));
    let state = call(&mut s, "state", json!({}));
    assert_eq!(state.result["state"]["imageName"], "scan_002.npy");
    let export = out.join("scan_002.xy");
    assert!(export.is_file());
    let mut imported = Session::new(root());
    let saved = call(
        &mut imported,
        "integration_open_pattern",
        json!({"path":export}),
    );
    close(&values(&saved, "y"), &values(&state, "y"));
    let c = d.join("scan_003.npy");
    npy(&c, [8, 10], &[1.; 80]);
    call(&mut s, "integration_autoprocess_poll", json!({}));
    call(&mut s, "integration_autoprocess_poll", json!({}));
    let stopped = call(&mut s, "state", json!({}));
    assert_eq!(stopped.result["pattern"], state.result["pattern"]);
    assert_eq!(stopped.result["image"], state.result["image"]);
    assert_eq!(stopped.result["state"]["integration"]["autoProcess"], false);
    assert!(
        stopped.result["state"]["integration"]["autoProcessError"]
            .as_str()
            .unwrap()
            .contains("dimensions changed")
    );
    assert!(!out.join("scan_003.xy").exists());
}

#[test]
fn phases_overlays_background_and_corrections_survive_a_fresh_project_owner() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let a = d.join("a.npy");
    let p = d.join("g.poni");
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "q_A^-1");
    call(
        &mut s,
        "integration_correction",
        json!({"kind":"cbn","enabled":true,"parameters":{"tilt":7,"tilt_rotation":31,"diamond_thickness":1.9}}),
    );
    call(
        &mut s,
        "integration_correction",
        json!({"kind":"oiadac","enabled":true,"parameters":{"tilt":3,"rotation":16,"detector_thickness":30.,"absorption_length":450.}}),
    );
    call(
        &mut s,
        "integration_background",
        json!({"enabled":true,"smoothing":0.2,"iterations":10,"order":4}),
    );
    let captured = call(
        &mut s,
        "integration_overlay",
        json!({"operation":"capture"}),
    );
    let original = values(&captured, "y");
    let edited = call(
        &mut s,
        "integration_overlay",
        json!({"operation":"update","index":0,"name":"Reference","scale":1.5,"offset":2.,"color":"#112233","visible":true}),
    );
    let curve: Vec<_> = edited.result["pattern"]["curves"][0]["y"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap())
        .collect();
    close(
        &curve,
        &original.iter().map(|v| v * 1.5 + 2.).collect::<Vec<_>>(),
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"load","path":root().join("dioptas/tests/data/jcpds/mo.jcpds")}),
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"update","index":0,"pressure":20.,"temperature":500.,"color":"#445566","visible":true}),
    );
    // Include non-default visibility; default-true round trips cannot catch
    // the old phase/overlay visibility persistence regressions.
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"capture"}),
    );
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"update","index":1,"visible":false,"color":"#aabbcc"}),
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"load","path":root().join("dioptas/tests/data/jcpds/au_version3.jcpds")}),
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"update","index":0,"visible":false}),
    );
    let before = call(&mut s, "state", json!({}));
    assert!(
        !before.result["pattern"]["phaseLines"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let project = d.join("references.dio");
    call(&mut s, "save_project", json!({"path":project}));
    fs::remove_file(a).unwrap();
    fs::remove_file(p).unwrap();
    let mut restored = Session::new(root());
    let after = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(after.result["pattern"], before.result["pattern"]);
    for key in ["corrections", "patternBackground", "phases", "overlays"] {
        assert_eq!(
            after.result["state"]["integration"][key], before.result["state"]["integration"][key],
            "{key}"
        );
    }
}

#[test]
fn phase_lattice_pressure_and_name_edits_reach_pattern_and_export() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let a = d.join("a.npy");
    let p = d.join("g.poni");
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"load","path":root().join("dioptas/tests/data/jcpds/mo.jcpds")}),
    );
    let before =
        call(&mut s, "integration_phase_editor", json!({"index":0})).result["phaseEditor"].clone();
    let edited = call(
        &mut s,
        "integration_phase",
        json!({"operation":"editor_parameter","index":0,"parameter":"a0","value":3.3,"editor":true}),
    );
    assert!(edited.result["phaseEditor"]["editError"].is_null());
    let edited =
        call(&mut s, "integration_phase_editor", json!({"index":0})).result["phaseEditor"].clone();
    assert_ne!(
        edited["reflections"][0]["d0"],
        before["reflections"][0]["d0"]
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"editor_name","index":0,"value":"Edited molybdenum"}),
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"update","index":0,"pressure":30.,"temperature":500.}),
    );
    let pressure =
        call(&mut s, "integration_phase_editor", json!({"index":0})).result["phaseEditor"].clone();
    assert!(
        pressure["reflections"][0]["d"].as_f64().unwrap()
            < edited["reflections"][0]["d0"].as_f64().unwrap()
    );
    let output = d.join("edited.eosmat");
    call(
        &mut s,
        "integration_phase_export",
        json!({"index":0,"path":output}),
    );
    let mut restored = prepared(&a, &p, "2th_deg");
    call(
        &mut restored,
        "integration_phase",
        json!({"operation":"load","path":output}),
    );
    let state = call(&mut restored, "state", json!({}));
    assert_eq!(
        state.result["state"]["integration"]["phases"][0]["name"],
        "Edited molybdenum"
    );
    let editor = call(
        &mut restored,
        "integration_phase_editor",
        json!({"index":0}),
    );
    assert_eq!(
        editor.result["phaseEditor"]["reflections"][0]["d0"],
        edited["reflections"][0]["d0"]
    );
}

#[test]
fn reflection_editing_add_remove_and_export_preserve_actual_peak_values() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let a = d.join("a.npy");
    let p = d.join("g.poni");
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"load","path":root().join("dioptas/tests/data/jcpds/mo.jcpds")}),
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"reflection","index":0,"action":"add"}),
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"reflection","index":0,"action":"update","row":0,"parameter":"intensity","value":432.}),
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"reflection","index":0,"action":"remove","rows":[1]}),
    );
    let rows=call(&mut s,"integration_phase_editor",json!({"index":0})).result["phaseEditor"]["reflections"].clone();
    assert_eq!(rows[0]["intensity"], 432.);
    let output = d.join("reflections.eosmat");
    call(
        &mut s,
        "integration_phase_export",
        json!({"index":0,"path":output}),
    );
    let mut restored = Session::new(root());
    call(
        &mut restored,
        "integration_phase",
        json!({"operation":"load","path":output}),
    );
    let read = call(
        &mut restored,
        "integration_phase_editor",
        json!({"index":0}),
    );
    for (a, b) in rows.as_array().unwrap().iter().zip(
        read.result["phaseEditor"]["reflections"]
            .as_array()
            .unwrap(),
    ) {
        for key in ["h", "k", "l", "d0", "intensity"] {
            assert_eq!(a[key], b[key], "{key}");
        }
    }
    assert_eq!(
        rows.as_array().unwrap().len(),
        read.result["phaseEditor"]["reflections"]
            .as_array()
            .unwrap()
            .len()
    );
}

#[test]
fn configuration_selection_and_removal_restore_independent_maps_and_clicks() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let a = d.join("a.npy");
    let b = d.join("b.npy");
    let p = d.join("g.poni");
    image(&a, 0.);
    image(&b, 40.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    call(&mut s, "map_load", json!({"paths":[a,b]}));
    call(&mut s, "integrate", json!({}));
    call(
        &mut s,
        "validation_position",
        json!({"source":"image","x":12.25,"y":17.75}),
    );
    let reference = call(&mut s, "state", json!({}));
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(
        &mut s,
        "integration_settings",
        json!({"bins":31,"cake_bins":9}),
    );
    call(&mut s, "map_load", json!({"paths":[a]}));
    call(&mut s, "integrate", json!({}));
    call(
        &mut s,
        "validation_position",
        json!({"source":"image","x":4.25,"y":6.75}),
    );
    let sample = call(&mut s, "state", json!({}));
    let first = call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(first.result["linked"], reference.result["linked"]);
    assert_eq!(first.result["map"]["points"], 2);
    assert_eq!(first.result["pattern"], reference.result["pattern"]);
    assert_eq!(first.result["cake"]["height"], 12);
    let second = call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":1}),
    );
    assert_eq!(second.result["linked"], sample.result["linked"]);
    assert_eq!(second.result["map"]["points"], 1);
    let removed = call(&mut s, "configuration", json!({"operation":"remove"}));
    assert_eq!(removed.result["state"]["configurationCount"], 1);
    assert_eq!(removed.result["map"]["points"], 2);
    assert_eq!(removed.result["pattern"], reference.result["pattern"]);
}

#[test]
fn multiple_hdf5_files_keep_dataset_frame_order_across_stride_and_map_selection() {
    let d = tempfile::tempdir().unwrap();
    let d = d.path();
    let p = d.join("g.poni");
    poni(&p);
    let mut paths = vec![];
    for (file_index, frames) in [(0, 3), (1, 2)] {
        let path = d.join(format!("detector_{file_index:03}.h5"));
        let file = hdf5::File::create(&path).unwrap();
        let group = file.create_group("detector").unwrap();
        let data: Vec<u16> = (0..frames * 768)
            .map(|i| {
                100 + (file_index * 3 + i / 768) as u16 * 40
                    + (i % 768 / 32) as u16 * 3
                    + (i % 32) as u16 * 2
            })
            .collect();
        group
            .new_dataset::<u16>()
            .shape((frames, 24, 32))
            .chunk((1, 24, 32))
            .deflate(1)
            .create("counts")
            .unwrap()
            .write_raw(&data)
            .unwrap();
        paths.push(path);
    }
    let mut s = Session::new(root());
    call(&mut s, "open_calibration", json!({"path":p}));
    call(
        &mut s,
        "integration_settings",
        json!({"bins":48,"cake_bins":12,"unit":"q_A^-1","trim_zeros":false}),
    );
    call(
        &mut s,
        "open_image",
        json!({"path":paths[0],"dataset":"/detector/counts"}),
    );
    let mut expected = vec![];
    for (file, frame) in [(0, 1), (1, 0)] {
        expected.push(values(
            &call(
                &mut s,
                "open_image",
                json!({"path":paths[file],"dataset":"/detector/counts","frame":frame}),
            ),
            "y",
        ));
    }
    let batch = call(
        &mut s,
        "batch_load",
        json!({"paths":paths,"start":2,"stop":5,"step":2}),
    );
    assert_eq!(batch.result["batch"]["total"], 5);
    assert_eq!(
        batch.result["batch"]["entries"][0]["path"],
        json!(paths[0].canonicalize().unwrap())
    );
    assert_eq!(batch.result["batch"]["entries"][0]["frame"], 2);
    assert_eq!(
        batch.result["batch"]["entries"][1]["path"],
        json!(paths[1].canonicalize().unwrap())
    );
    assert_eq!(batch.result["batch"]["entries"][1]["frame"], 1);
    let output = d.join("ordered.h5");
    call(&mut s, "integration_save_batch", json!({"path":output}));
    let saved = hdf5::File::open(&output)
        .unwrap()
        .dataset("processed/result/data")
        .unwrap()
        .read_raw::<f64>()
        .unwrap();
    close(&saved, &expected.concat());
    call(&mut s, "map_batch", json!({"path":output}));
    let selected = call(
        &mut s,
        "map_select",
        json!({"index":1,"reintegrate":true,"integration_view":true}),
    );
    assert_eq!(selected.result["state"]["imageName"], "detector_001.h5");
    close(&values(&selected, "y"), &expected[1]);
}

#[test]
fn counting_variance_survives_background_transfer_factor_masks_and_units() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.npy");
    let bg = d.path().join("bg.npy");
    let original = d.path().join("original.npy");
    let response = d.path().join("response.npy");
    let p = d.path().join("g.poni");
    npy(&a, [24, 32], &vec![100.; 768]);
    npy(&bg, [24, 32], &vec![4.; 768]);
    npy(&original, [24, 32], &vec![3.; 768]);
    npy(&response, [24, 32], &vec![2.; 768]);
    poni(&p);
    for unit in ["2th_deg", "q_A^-1", "d_A"] {
        for ss in [1, 3] {
            let mut s = prepared(&a, &p, unit);
            call(&mut s, "integration_roi", json!({"limits":[2,22,3,29]}));
            let baseline = call(
                &mut s,
                "integration_settings",
                json!({"poisson_errors":true,"supersampling":ss,"solid_angle":ss==1,"azimuth_range":if ss==3 {json!([-40,95])} else {Value::Null}}),
            );
            call(
                &mut s,
                "integration_image_background",
                json!({"path":bg,"scale":3.,"offset":1000.}),
            );
            call(
                &mut s,
                "integration_transfer",
                json!({"source":"original","path":original}),
            );
            call(
                &mut s,
                "integration_transfer",
                json!({"source":"response","path":response}),
            );
            call(&mut s, "integration_transfer", json!({"enabled":true}));
            let actual = call(&mut s, "combination_settings", json!({"factor":-2.}));
            close(
                &values(&actual, "y"),
                &values(&baseline, "y")
                    .iter()
                    .map(|v| v * 27.36)
                    .collect::<Vec<_>>(),
            );
            close(
                &values(&actual, "sigma"),
                &values(&baseline, "sigma")
                    .iter()
                    .map(|v| v * (1224f64 / 100.).sqrt())
                    .collect::<Vec<_>>(),
            );
            let fixed = call(
                &mut s,
                "integration_image_background",
                json!({"poisson":false}),
            );
            close(
                &values(&fixed, "sigma"),
                &values(&baseline, "sigma")
                    .iter()
                    .map(|v| v * 3.)
                    .collect::<Vec<_>>(),
            );
            // A live factor edit must invalidate processed data as well as variance.
            let changed = call(&mut s, "combination_settings", json!({"factor":4.}));
            close(
                &values(&changed, "sigma"),
                &values(&fixed, "sigma")
                    .iter()
                    .map(|v| v * 2.)
                    .collect::<Vec<_>>(),
            );
        }
    }
}

#[test]
fn transfer_plate_and_slab_project_owns_references_errors_and_disabled_drafts() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.npy");
    let p = d.path().join("g.poni");
    let original = d.path().join("o.npy");
    let response = d.path().join("r.npy");
    image(&a, 0.);
    poni(&p);
    npy(
        &original,
        [24, 32],
        &(0..768)
            .map(|i| 2. + (i % 32) as f64 / 100.)
            .collect::<Vec<_>>(),
    );
    npy(&response, [24, 32], &vec![3.; 768]);
    let mut s = prepared(&a, &p, "q_A^-1");
    call(
        &mut s,
        "integration_settings",
        json!({"poisson_errors":true}),
    );
    call(
        &mut s,
        "integration_transfer",
        json!({"source":"original","path":original}),
    );
    let partial_transfer =
        call(&mut s, "state", json!({})).result["state"]["integration"]["transfer"].clone();
    let partial = d.path().join("partial.dio");
    call(&mut s, "save_project", json!({"path":partial}));
    call(
        &mut s,
        "integration_transfer",
        json!({"source":"response","path":response}),
    );
    call(&mut s, "integration_transfer", json!({"enabled":true}));
    for (kind, params) in [
        (
            "plate",
            json!({"thickness":0.3,"absorption_coefficient":0.8,"plate_tilt":12.,"plate_rotation":27.}),
        ),
        (
            "slab",
            json!({"thickness":0.15,"absorption_coefficient":1.2,"slab_tilt":8.,"slab_rotation":-32.}),
        ),
    ] {
        call(
            &mut s,
            "integration_correction",
            json!({"kind":kind,"enabled":true,"parameters":params}),
        );
    }
    call(
        &mut s,
        "image_transform",
        json!({"operation":"rotate_right"}),
    );
    let before = call(&mut s, "state", json!({}));
    let output = d.path().join("profile.xye");
    call(&mut s, "integration_save_pattern", json!({"path":output}));
    let exported: Vec<_> = fs::read_to_string(output)
        .unwrap()
        .lines()
        .filter_map(|l| {
            let fields: Vec<_> = l.split_whitespace().collect();
            if fields.len() != 3 || fields[0].parse::<f64>().is_err() {
                return None;
            }
            fields[2].parse::<f64>().ok()
        })
        .collect();
    close(&exported, &values(&before, "sigma"));
    let project = d.path().join("all.dio");
    call(&mut s, "save_project", json!({"path":project}));
    let disabled = call(&mut s, "integration_transfer", json!({"enabled":false}));
    let disabled_project = d.path().join("disabled.dio");
    call(&mut s, "save_project", json!({"path":disabled_project}));
    call(&mut s, "undo_calibration", json!({}));
    let undone = call(&mut s, "state", json!({}));
    assert_eq!(undone.result["pattern"], before.result["pattern"]);
    for file in [&a, &p, &original, &response] {
        fs::remove_file(file).unwrap();
    }
    let mut restored = Session::new(root());
    let actual = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(actual.result["pattern"], before.result["pattern"]);
    assert_eq!(bytes(&actual, "image"), bytes(&before, "image"));
    assert_eq!(bytes(&actual, "cake"), bytes(&before, "cake"));
    for key in ["transfer", "corrections"] {
        assert_eq!(
            actual.result["state"]["integration"][key],
            before.result["state"]["integration"][key]
        );
    }
    let actual = call(
        &mut restored,
        "open_project",
        json!({"path":disabled_project}),
    );
    assert_eq!(actual.result["pattern"], disabled.result["pattern"]);
    let enabled = call(
        &mut restored,
        "integration_transfer",
        json!({"enabled":true}),
    );
    assert_eq!(enabled.result["pattern"], before.result["pattern"]);
    let partial = call(&mut restored, "open_project", json!({"path":partial}));
    assert_eq!(
        partial.result["state"]["integration"]["transfer"],
        partial_transfer
    );
    let bad = invoke(
        &mut restored,
        "integration_transfer",
        json!({"enabled":true}),
    );
    assert_eq!(bad.result["ok"], false);
}

#[test]
fn corrections_reject_invalid_planes_and_extreme_absorption_atomically() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.npy");
    let p = d.path().join("g.poni");
    let bad = d.path().join("bad.npy");
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    let before = call(&mut s, "state", json!({}));
    for value in [0., -1., f64::NAN, f64::INFINITY] {
        npy(&bad, [24, 32], &vec![value; 768]);
        let r = invoke(
            &mut s,
            "integration_transfer",
            json!({"source":"original","path":bad}),
        );
        assert_eq!(r.result["ok"], false);
        assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    }
    for kind in ["plate", "slab"] {
        let before = call(&mut s, "state", json!({}));
        for params in [
            json!({"thickness":-1.}),
            json!({"absorption_coefficient":-1.}),
            json!({"thickness":1000.,"absorption_coefficient":1e6}),
        ] {
            assert_eq!(
                invoke(
                    &mut s,
                    "integration_correction",
                    json!({"kind":kind,"enabled":true,"parameters":params})
                )
                .result["ok"],
                false
            );
            assert_eq!(call(&mut s, "state", json!({})).result, before.result);
        }
        let zero = call(
            &mut s,
            "integration_correction",
            json!({"kind":kind,"enabled":true,"parameters":{"thickness":0.}}),
        );
        close(&values(&zero, "y"), &values(&before, "y"));
        call(
            &mut s,
            "integration_correction",
            json!({"kind":kind,"enabled":false}),
        );
    }
}

#[test]
fn combined_corrected_detector_errors_follow_gain_and_survive_project_reopen() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.npy");
    let p = d.path().join("g.poni");
    image(&a, 0.);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    call(
        &mut s,
        "integration_settings",
        json!({"poisson_errors":true}),
    );
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    let baseline = call(
        &mut s,
        "combination_settings",
        json!({"patterns":true,"cakes":true}),
    );
    for index in 0..2 {
        call(
            &mut s,
            "configuration",
            json!({"operation":"select","index":index}),
        );
        call(&mut s, "combination_settings", json!({"factor":-3.}));
    }
    let changed = call(&mut s, "state", json!({}));
    close(
        &values(&changed, "y"),
        &values(&baseline, "y")
            .iter()
            .map(|v| -3. * v)
            .collect::<Vec<_>>(),
    );
    close(
        &values(&changed, "sigma"),
        &values(&baseline, "sigma")
            .iter()
            .map(|v| 3. * v)
            .collect::<Vec<_>>(),
    );
    let project = d.path().join("combined.dio");
    call(&mut s, "save_project", json!({"path":project}));
    fs::remove_file(a).unwrap();
    fs::remove_file(p).unwrap();
    let mut restored = Session::new(root());
    let r = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(r.result["pattern"], changed.result["pattern"]);
}

#[test]
fn averaged_images_preserve_independent_counting_variance_offline() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.npy");
    let b = d.path().join("b.npy");
    let p = d.path().join("g.poni");
    npy(&a, [24, 32], &vec![100.; 768]);
    npy(&b, [24, 32], &vec![100.; 768]);
    poni(&p);
    let mut s = prepared(&a, &p, "2th_deg");
    let baseline = call(
        &mut s,
        "integration_settings",
        json!({"poisson_errors":true}),
    );
    let averaged = call(
        &mut s,
        "open_image",
        json!({"paths":[a,b],"batch_mode":"average"}),
    );
    close(&values(&averaged, "y"), &values(&baseline, "y"));
    close(
        &values(&averaged, "sigma"),
        &values(&baseline, "sigma")
            .iter()
            .map(|v| v / 2f64.sqrt())
            .collect::<Vec<_>>(),
    );
    let project = d.path().join("average.dio");
    call(&mut s, "save_project", json!({"path":project}));
    fs::remove_file(a).unwrap();
    fs::remove_file(b).unwrap();
    fs::remove_file(p).unwrap();
    let mut restored = Session::new(root());
    let actual = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(actual.result["pattern"], averaged.result["pattern"]);
}

#[test]
fn corrected_batch_and_map_retain_counting_std_through_normalization_and_offline_storage() {
    let d = tempfile::tempdir().unwrap();
    let a = d.path().join("a.npy");
    let b = d.path().join("b.npy");
    let p = d.path().join("g.poni");
    let original = d.path().join("original.npy");
    let response = d.path().join("response.npy");
    let bg = d.path().join("background.npy");
    image(&a, 0.);
    image(&b, 80.);
    poni(&p);
    npy(&original, [24, 32], &vec![3.; 768]);
    npy(&response, [24, 32], &vec![2.; 768]);
    npy(&bg, [24, 32], &vec![4.; 768]);
    let mut s = prepared(&a, &p, "q_A^-1");
    call(
        &mut s,
        "integration_settings",
        json!({"poisson_errors":true}),
    );
    call(
        &mut s,
        "integration_image_background",
        json!({"path":bg,"scale":0.7,"offset":1.2}),
    );
    call(
        &mut s,
        "integration_transfer",
        json!({"source":"original","path":original}),
    );
    call(
        &mut s,
        "integration_transfer",
        json!({"source":"response","path":response}),
    );
    call(&mut s, "integration_transfer", json!({"enabled":true}));
    for kind in ["plate", "slab"] {
        call(
            &mut s,
            "integration_correction",
            json!({"kind":kind,"enabled":true,"parameters":{"thickness":0.3}}),
        );
    }
    let mut patterns = vec![];
    for source in [&a, &b] {
        patterns.push(call(&mut s, "open_image", json!({"path":source})));
    }
    call(&mut s, "batch_load", json!({"paths":[a,b]}));
    for (i, expected) in patterns.iter().enumerate() {
        let actual = call(&mut s, "batch_select", json!({"index":i}));
        close(&values(&actual, "y"), &values(expected, "y"));
        close(&values(&actual, "sigma"), &values(expected, "sigma"));
    }
    let batch = d.path().join("batch.h5");
    call(&mut s, "integration_save_batch", json!({"path":batch}));
    let f = hdf5::File::open(&batch).unwrap();
    let std = f
        .dataset("processed/result/counting_std")
        .unwrap()
        .read_raw::<f64>()
        .unwrap();
    close(
        &std,
        &patterns
            .iter()
            .flat_map(|p| values(p, "sigma"))
            .collect::<Vec<_>>(),
    );
    drop(f);
    call(
        &mut s,
        "batch_normalize",
        json!({"enabled":true,"start":3,"stop":44,"reference":1}),
    );
    let normalized = call(&mut s, "batch_select", json!({"index":1}));
    let factor = values(&patterns[0], "y")[2..44].iter().sum::<f64>()
        / values(&patterns[1], "y")[2..44].iter().sum::<f64>();
    close(
        &values(&normalized, "sigma"),
        &values(&patterns[1], "sigma")
            .iter()
            .map(|v| v * factor)
            .collect::<Vec<_>>(),
    );
    let normalized_batch = d.path().join("normalized.h5");
    call(
        &mut s,
        "integration_save_batch",
        json!({"path":normalized_batch}),
    );
    call(&mut s, "map_batch", json!({"path":batch}));
    let project = d.path().join("scan.dio");
    call(&mut s, "save_project", json!({"path":project}));
    for source in [&a, &b, &p, &original, &response, &bg] {
        fs::remove_file(source).unwrap();
    }
    let mut restored = Session::new(root());
    call(&mut restored, "open_project", json!({"path":project}));
    let selected = call(&mut restored, "batch_select", json!({"index":1}));
    close(&values(&selected, "sigma"), &values(&normalized, "sigma"));
    let selected = call(&mut restored, "map_select", json!({"index":1}));
    close(&values(&selected, "sigma"), &values(&patterns[1], "sigma"));
    call(
        &mut restored,
        "batch_open",
        json!({"path":normalized_batch}),
    );
    let selected = call(&mut restored, "batch_select", json!({"index":1}));
    close(&values(&selected, "sigma"), &values(&normalized, "sigma"));
    call(&mut restored, "batch_normalize", json!({"enabled":false}));
    let selected = call(&mut restored, "batch_select", json!({"index":1}));
    close(&values(&selected, "sigma"), &values(&patterns[1], "sigma"));
}

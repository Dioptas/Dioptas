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
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
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

fn raster(reply: &Reply, metadata: &Value) -> Vec<f64> {
    let id = metadata["bufferId"].as_str().unwrap();
    reply
        .buffers
        .iter()
        .find(|b| b.id == id)
        .unwrap()
        .bytes
        .as_chunks::<4>()
        .0
        .iter()
        .map(|b| f32::from_le_bytes(*b) as f64)
        .collect()
}
fn unchanged(before: &Reply, after: &Reply) {
    assert_eq!(before.result["state"], after.result["state"]);
    assert_eq!(before.result["pattern"], after.result["pattern"]);
    for key in ["image", "rawImage", "cake", "mask"] {
        assert_eq!(before.result[key], after.result[key], "{key}");
    }
}
fn preload(s: &mut Session) -> Reply {
    let start = std::time::Instant::now();
    loop {
        let reply = call(s, "integration_correction_preload", json!({}));
        if reply.result["correctionPreviewPending"] != true {
            return reply;
        }
        assert!(
            start.elapsed() < std::time::Duration::from_secs(5),
            "Background preview did not finish"
        );
        std::thread::sleep(std::time::Duration::from_millis(1));
    }
}
#[test]
fn legacy_detector_angles_are_discarded_and_recalculation_is_explained() {
    use hdf5::types::VarLenUnicode;
    use std::str::FromStr;
    let d = tempfile::tempdir().unwrap();
    let source = d.path().join("raw.npy");
    let calibration = d.path().join("geometry.poni");
    let project = d.path().join("legacy.dio");
    image(&source, 0.);
    poni(&calibration);
    let mut s = prepared(&source, &calibration, "2th_deg");
    let corrected = call(
        &mut s,
        "integration_correction",
        json!({
            "kind":"oiadac", "enabled":true,
            "parameters":{"tilt":23.,"rotation":71.,"detector_thickness":44.,"absorption_length":120.}
        }),
    );
    let correction = &corrected.result["state"]["integration"]["corrections"]["oiadac"];
    assert_eq!(correction["fields"].as_object().unwrap().len(), 2);
    assert!(correction["parameters"].get("tilt").is_none());
    call(&mut s, "save_project", json!({"path":project}));
    {
        let file = hdf5::File::open_rw(&project).unwrap();
        let dataset = file.dataset("state").unwrap();
        let mut doc: Value =
            serde_json::from_str(dataset.read_scalar::<VarLenUnicode>().unwrap().as_str()).unwrap();
        for config in doc["configurations"].as_array_mut().unwrap() {
            config["native_desktop"]
                .as_object_mut()
                .unwrap()
                .remove("detector_absorption");
            config["img"]["corrections"]["oiadac"]["tilt"] = json!(23.);
            config["img"]["corrections"]["oiadac"]["rotation"] = json!(71.);
            config["native_desktop"]["correction_drafts"]["oiadac"]["parameters"]["tilt"] =
                json!(23.);
            config["native_desktop"]["correction_drafts"]["oiadac"]["parameters"]["rotation"] =
                json!(71.);
        }
        dataset
            .write_scalar(&VarLenUnicode::from_str(&doc.to_string()).unwrap())
            .unwrap();
    }
    let mut reopened = Session::new(root());
    let restored = call(&mut reopened, "open_project", json!({"path":project}));
    assert!(
        restored.result["correctionNotice"]
            .as_str()
            .unwrap()
            .contains("calibrated geometry")
    );
    assert_eq!(restored.result["pattern"], corrected.result["pattern"]);
    call(&mut reopened, "save_project", json!({"path":project}));
    let current = call(&mut reopened, "open_project", json!({"path":project}));
    assert!(current.result.get("correctionNotice").is_none());
}
#[cfg(debug_assertions)]
#[test]
fn worker_handoff_resumes_background_preparation_for_the_frontend() {
    let d = tempfile::tempdir().unwrap();
    let source = d.path().join("raw.npy");
    let calibration = d.path().join("geometry.poni");
    let checkpoint = d.path().join("worker.dio");
    image(&source, 0.);
    poni(&calibration);
    let mut s = prepared(&source, &calibration, "2th_deg");
    call(
        &mut s,
        "integration_correction",
        json!({"kind":"oiadac","enabled":true}),
    );
    call(&mut s, "development_checkpoint", json!({"path":checkpoint}));
    let mut next = Session::new(root());
    let restored = call(&mut next, "development_restore", json!({"path":checkpoint}));
    assert!(restored.result.get("preparedCorrections").is_none());
    let refreshed = preload(&mut next);
    let plotted = call(
        &mut next,
        "integration_correction_preview",
        json!({"kind":"oiadac"}),
    );
    let id = plotted.result["correctionPreview"]["raster"]["bufferId"]
        .as_str()
        .unwrap();
    assert!(
        refreshed.result["preparedCorrections"]
            .as_array()
            .unwrap()
            .iter()
            .any(|r| r["bufferId"] == id)
    );
    assert!(refreshed.buffers.iter().any(|b| b.id == id));
}
#[test]
fn correction_previews_are_native_divisors_and_never_change_science_or_ownership() {
    let d = tempfile::tempdir().unwrap();
    let source = d.path().join("raw.npy");
    let calibration = d.path().join("geometry.poni");
    image(&source, 0.);
    poni(&calibration);
    let mut s = prepared(&source, &calibration, "q_A^-1");
    call(
        &mut s,
        "integration_image_background",
        json!({"path":source,"scale":0.1,"offset":3.}),
    );
    call(&mut s, "integration_flat_field", json!({"path":source}));
    for key in ["original", "response"] {
        call(
            &mut s,
            "integration_transfer",
            json!({"source":key,"path":source}),
        );
    }
    for kind in ["cbn", "oiadac", "plate", "slab", "cylinder", "sphere"] {
        let before_correction = call(&mut s, "state", json!({}));
        let corrected = call(
            &mut s,
            "integration_correction",
            json!({"kind":kind,"enabled":true}),
        );
        assert!(
            corrected.result.get("preparedCorrections").is_none(),
            "Apply must not wait for or transfer preview pixels"
        );
        let preloaded = preload(&mut s);
        let before = call(&mut s, "state", json!({}));
        let preview = call(
            &mut s,
            "integration_correction_preview",
            json!({"kind":kind}),
        );
        assert!(preview.result.get("state").is_none());
        assert!(preview.result.get("image").is_none());
        let map = &preview.result["correctionPreview"];
        let buffer_id = map["raster"]["bufferId"].as_str().unwrap();
        let prepared_buffer = preloaded
            .buffers
            .iter()
            .find(|b| b.id == buffer_id)
            .unwrap_or_else(|| panic!("{kind} did not preload its plot buffer during calculation"));
        let plotted_buffer = preview.buffers.iter().find(|b| b.id == buffer_id).unwrap();
        assert!(
            std::sync::Arc::ptr_eq(&prepared_buffer.bytes, &plotted_buffer.bytes),
            "{kind} rebuilt its plot buffer"
        );
        let known = preloaded
            .buffers
            .iter()
            .map(|b| b.id.clone())
            .collect::<Vec<_>>();
        let packet = preview.encode(99, &known).unwrap();
        let length = u32::from_le_bytes(packet[..4].try_into().unwrap()) as usize;
        let header: Value = serde_json::from_slice(&packet[4..4 + length]).unwrap();
        assert_eq!(
            header["buffers"],
            json!([]),
            "{kind} transferred pixels on its first Plot"
        );
        assert_eq!(map["convention"], "divisor");
        assert_eq!(
            map["units"],
            if kind == "slab" {
                "mm"
            } else {
                "dimensionless"
            }
        );
        let divisor = raster(&preview, &map["raster"]);
        assert_eq!(divisor.len(), 768);
        // Independent pipeline check: only this correction's divisor belongs
        // in the map, even when backgrounds and other corrections are active.
        let uncorrected = raster(&before_correction, &before_correction.result["image"]);
        let corrected = raster(&corrected, &corrected.result["image"]);
        for ((&a, &b), &factor) in uncorrected.iter().zip(&corrected).zip(&divisor) {
            assert!((a / b - factor).abs() < 2e-7 * factor.abs().max(1.));
        }
        unchanged(&before, &call(&mut s, "state", json!({})));
        call(
            &mut s,
            "integration_correction",
            json!({"kind":kind,"enabled":false}),
        );
        let failed = invoke(
            &mut s,
            "integration_correction_preview",
            json!({"kind":kind}),
        );
        assert_eq!(failed.result["ok"], false);
    }
    let before = call(&mut s, "state", json!({}));
    for args in [
        json!({"kind":"unknown"}),
        json!({"kind":"flat","revision":0}),
        json!({"kind":"flat","configuration":999999}),
        json!({"kind":"flat","percentile":99}),
    ] {
        assert_eq!(
            invoke(&mut s, "integration_correction_preview", args).result["ok"],
            false
        );
        unchanged(&before, &call(&mut s, "state", json!({})));
    }
}
#[test]
fn disabled_reference_maps_follow_all_image_permutations_and_partial_transfer_is_unavailable() {
    let d = tempfile::tempdir().unwrap();
    let source = d.path().join("raw.npy");
    let response = d.path().join("response.npy");
    let calibration = d.path().join("geometry.poni");
    image(&source, 0.);
    poni(&calibration);
    npy(&response, [24, 32], &vec![2.; 768]);
    let mut s = prepared(&source, &calibration, "2th_deg");
    call(
        &mut s,
        "integration_transfer",
        json!({"source":"original","path":source}),
    );
    assert_eq!(
        invoke(
            &mut s,
            "integration_correction_preview",
            json!({"kind":"transfer"})
        )
        .result["ok"],
        false
    );
    call(
        &mut s,
        "integration_transfer",
        json!({"source":"response","path":response}),
    );
    call(&mut s, "integration_transfer", json!({"enabled":false}));
    call(&mut s, "integration_flat_field", json!({"path":source}));
    call(&mut s, "integration_flat_field", json!({"enabled":false}));
    for operation in [
        "none",
        "rotate_right",
        "rotate_left",
        "flip_horizontal",
        "flip_vertical",
    ] {
        if operation != "none" {
            call(&mut s, "image_transform", json!({"operation":operation}));
        }
        let before = call(&mut s, "state", json!({}));
        let raw = raster(&before, &before.result["rawImage"]);
        let mean = raw.iter().sum::<f64>() / raw.len() as f64;
        for kind in ["flat", "transfer"] {
            let preview = call(
                &mut s,
                "integration_correction_preview",
                json!({"kind":kind,"mode":"minmax"}),
            );
            let map = &preview.result["correctionPreview"]["raster"];
            assert_eq!(map["width"], before.result["rawImage"]["width"]);
            assert_eq!(map["height"], before.result["rawImage"]["height"]);
            for (&factor, &value) in raster(&preview, map).iter().zip(&raw) {
                let expected = if kind == "flat" {
                    value / mean
                } else {
                    2. / value
                };
                assert!((factor - expected).abs() < 6e-8 * expected.abs());
            }
        }
        unchanged(&before, &call(&mut s, "state", json!({})));
    }
    call(&mut s, "integration_flat_field", json!({"reset":true}));
    assert_eq!(
        invoke(
            &mut s,
            "integration_correction_preview",
            json!({"kind":"flat"})
        )
        .result["ok"],
        false
    );
    call(
        &mut s,
        "integration_transfer",
        json!({"source":"response","reset":true}),
    );
    assert_eq!(
        invoke(
            &mut s,
            "integration_correction_preview",
            json!({"kind":"transfer"})
        )
        .result["ok"],
        false
    );
}

#[test]
fn preview_keeps_hdf5_dataset_frame_and_offline_configuration_owner() {
    let d = tempfile::tempdir().unwrap();
    let source = d.path().join("frames.h5");
    let calibration = d.path().join("geometry.poni");
    poni(&calibration);
    let f = hdf5::File::create(&source).unwrap();
    f.new_dataset::<f64>()
        .shape([2, 24, 32])
        .create("counts")
        .unwrap()
        .write_raw(&(0..1536).map(|i| 20. + i as f64).collect::<Vec<_>>())
        .unwrap();
    drop(f);
    let mut s = Session::new(root());
    call(&mut s, "open_calibration", json!({"path":calibration}));
    call(
        &mut s,
        "integration_settings",
        json!({"bins":48,"cake_bins":12}),
    );
    call(
        &mut s,
        "open_image",
        json!({"path":source,"dataset":"/counts","frame":1}),
    );
    call(
        &mut s,
        "image_transform",
        json!({"operation":"rotate_right"}),
    );
    call(
        &mut s,
        "integration_correction",
        json!({"kind":"plate","enabled":true,"material":{"mode":"formula","formula":"SiO2","density":2.23}}),
    );
    let before = call(&mut s, "state", json!({}));
    assert_eq!(before.result["state"]["selectedImageSource"], "/counts");
    assert_eq!(before.result["state"]["integration"]["frame"], 2);
    let preview = call(
        &mut s,
        "integration_correction_preview",
        json!({"kind":"plate"}),
    );
    let geometry = call(&mut s, "pixel", json!({"x":3,"y":5,"source":"geometry"}));
    assert!(geometry.result["pixel"]["value"].is_null());
    assert!(geometry.result["pixel"]["twoTheta"].is_number());
    unchanged(&before, &call(&mut s, "state", json!({})));
    let project = d.path().join("owned.dio");
    call(&mut s, "save_project", json!({"path":project}));
    // Release the live HDF5 reader before simulating an offline reopen.
    drop(s);
    std::fs::remove_file(&source).unwrap();
    std::fs::remove_file(&calibration).unwrap();
    let mut fresh = Session::new(root());
    call(&mut fresh, "open_project", json!({"path":project}));
    let offline = call(
        &mut fresh,
        "integration_correction_preview",
        json!({"kind":"plate"}),
    );
    assert_eq!(
        preview.result["correctionPreview"],
        offline.result["correctionPreview"]
    );
}

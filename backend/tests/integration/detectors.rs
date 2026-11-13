use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
use std::str::FromStr;
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_owned()
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn image(path: &Path, h: usize, w: usize) {
    let file = hdf5::File::create(path).unwrap();
    file.new_dataset::<u16>()
        .shape([h, w])
        .create("counts")
        .unwrap()
        .write_raw(&vec![123; h * w])
        .unwrap();
}
#[cfg(feature = "dioptrin")]
fn detector(path: &Path) {
    let file = hdf5::File::create(path).unwrap();
    let g = file.create_group("detector").unwrap();
    g.new_dataset_builder()
        .with_data(&[95e-6, 80e-6])
        .create("pixel_size")
        .unwrap();
    g.new_dataset_builder()
        .with_data(&[8u32, 12])
        .create("max_shape")
        .unwrap();
    let mut corners = vec![];
    for r in 0..8 {
        for c in 0..12 {
            for (dr, dc) in [(0., 0.), (1., 0.), (1., 1.), (0., 1.)] {
                corners.extend([
                    0.,
                    (r as f64 + dr) * 95e-6,
                    (c as f64 + dc) * 80e-6 + if c >= 6 { 15e-6 } else { 0. },
                ]);
            }
        }
    }
    g.new_dataset::<f64>()
        .shape([8, 12, 4, 3])
        .create("pixel_corners")
        .unwrap()
        .write_raw(&corners)
        .unwrap();
    let mut mask = vec![0u8; 96];
    mask[16] = 1;
    g.new_dataset::<u8>()
        .shape([8, 12])
        .create("mask")
        .unwrap()
        .write_raw(&mask)
        .unwrap();
}
#[cfg(feature = "dioptrin")]
fn manual() -> Value {
    json!({"dist":0.2,"poni1":0.0003,"poni2":0.0004,"pixel1":95e-6,"pixel2":80e-6,"rot1":0.,"rot2":0.,"rot3":0.,"wavelength":0.4e-10,"polarization_factor":0.})
}
#[test]
fn first_load_uses_metadata_but_respects_custom_and_reports_ambiguous_shapes() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("source.h5");
    image(&path, 1043, 981);
    {
        let file = hdf5::File::open_rw(&path).unwrap();
        let group = file.create_group("entry/instrument/detector").unwrap();
        let text = hdf5::types::VarLenUnicode::from_str("DECTRIS PILATUS3 X 1M, S/N 123").unwrap();
        group
            .new_dataset::<hdf5::types::VarLenUnicode>()
            .shape(())
            .create("description")
            .unwrap()
            .write_scalar(&text)
            .unwrap();
        for name in ["x_pixel_size", "y_pixel_size"] {
            group
                .new_dataset::<f64>()
                .shape(())
                .create(name)
                .unwrap()
                .write_scalar(&172e-6)
                .unwrap();
        }
    }
    let mut s = Session::new(root());
    call(&mut s, "example", json!({}));

    let r = call(
        &mut s,
        "open_image",
        json!({"path":path,"dataset":"/counts","defer_integration":true}),
    );
    let c = &r.result["state"]["calibration"];
    assert!(c["detector"].as_str().unwrap().contains("Pilatus"));
    assert_eq!(c["detectorAssignment"], "Matched detector metadata");
    assert_eq!(c["pixelX"], 172.);
    assert_eq!(
        call(&mut s, "pixel", json!({"x":0,"y":0})).result["pixel"]["value"],
        123.
    );
    let mut overridden = Session::new(root());
    call(
        &mut overridden,
        "calibration_setup",
        json!({"detector":"Custom"}),
    );
    let r = call(
        &mut overridden,
        "open_image",
        json!({"path":path,"dataset":"/counts","defer_integration":true}),
    );
    assert_eq!(r.result["state"]["calibration"]["detector"], "Custom");
    let ambiguous = temp.path().join("ambiguous.h5");
    image(&ambiguous, 1043, 981);
    // Optional acquisition hints must not bypass external-link admission.
    {
        let file = hdf5::File::open_rw(&ambiguous).unwrap();
        file.link_external(path.to_str().unwrap(), "/entry", "entry")
            .unwrap();
    }

    let mut s = Session::new(root());
    let r = call(
        &mut s,
        "open_image",
        json!({"path":ambiguous,"dataset":"/counts","defer_integration":true}),
    );
    let c = &r.result["state"]["calibration"];
    assert_eq!(c["detector"], "Custom");
    assert!(c["detectorCandidates"].as_array().unwrap().len() > 1);
}
#[test]
fn fit2d_conversion_and_detector_orientation_are_undoable() {
    let mut s = Session::new(root());
    let first = call(
        &mut s,
        "calibration_setup",
        json!({"detector":"Pilatus1M","orientation":2}),
    );
    let r = call(
        &mut s,
        "manual_geometry",
        json!({"convention":"fit2d","values":{"directDist":234.,"centerX":450.,"centerY":700.,"tilt":12.,"tiltPlanRotation":35.,"pixelX":172.,"pixelY":172.,"wavelength":0.4e-10,"polarization_factor":0.96}}),
    );
    let c = &r.result["state"]["calibration"];
    assert_eq!(c["detectorOrientation"], 2);
    assert!((c["fit2d"]["centerX"].as_f64().unwrap() - 450.).abs() < 1e-8);
    call(&mut s, "undo_calibration", json!({}));
    let undone = call(&mut s, "state", json!({}));
    assert_eq!(
        undone.result["state"]["geometry"],
        first.result["state"]["geometry"]
    );
    let redone = call(&mut s, "redo_calibration", json!({}));
    assert_eq!(
        redone.result["state"]["geometry"],
        r.result["state"]["geometry"]
    );
}

#[test]
fn binned_perkin_poni_does_not_double_the_recorded_pixel_pitch() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("perkin.h5");
    image(&source, 2048, 2048);
    let path = temp.path().join("perkin.poni");
    std::fs::write(&path,"poni_version: 2.1\nDetector: Perkin\nDetector_config: {\"pixel1\":0.0002,\"pixel2\":0.0002,\"orientation\":3}\nDistance: 0.2\nPoni1: 0.03\nPoni2: 0.04\nRot1: 0\nRot2: 0\nRot3: 0\nWavelength: 4e-11\n").unwrap();
    let mut s = Session::new(root());
    call(
        &mut s,
        "open_calibration",
        json!({"path":path,"defer_integration":true}),
    );
    let loaded = call(
        &mut s,
        "open_image",
        json!({"path":source,"dataset":"/counts","defer_integration":true}),
    );
    assert_eq!(loaded.result["state"]["calibration"]["pixelX"], 200.);
    #[cfg(feature = "dioptrin")]
    {
        let p = call(&mut s, "pixel", json!({"x":0,"y":0}));
        let expected = ((2047.5f64 * 0.0002 - 0.03).hypot(0.0001 - 0.04))
            .atan2(0.2)
            .to_degrees();
        assert!((p.result["pixel"]["twoTheta"].as_f64().unwrap() - expected).abs() < 1e-10);
    }
    let exported = temp.path().join("saved.poni");
    call(&mut s, "save_calibration", json!({"path":exported}));
    let reopened = call(
        &mut s,
        "open_calibration",
        json!({"path":exported,"defer_integration":true}),
    );
    assert_eq!(reopened.result["state"]["calibration"]["pixelX"], 200.);
}
#[test]
#[cfg(feature = "dioptrin")]
fn nexus_geometry_masks_transforms_projects_and_portable_poni_keep_owned_resources() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("source.h5");
    image(&source, 8, 12);
    let definition = temp.path().join("detector.nxs");
    detector(&definition);
    let mut s = Session::new(root());
    call(
        &mut s,
        "open_image",
        json!({"path":source,"dataset":"/counts"}),
    );
    call(&mut s, "detector_file", json!({"path":definition}));
    call(
        &mut s,
        "integration_settings",
        json!({"bins":25,"cake_bins":12,"trim_zeros":false}),
    );
    let before = call(
        &mut s,
        "manual_geometry",
        json!({"convention":"pyfai","values":manual()}),
    );
    assert_eq!(before.result["state"]["maskedPixels"], 1);
    let pixel = call(&mut s, "pixel", json!({"x":7,"y":4})).result["pixel"].clone();
    let poni = temp.path().join("geometry.poni");
    call(&mut s, "save_calibration", json!({"path":poni}));
    let mut loaded = Session::new(root());
    call(
        &mut loaded,
        "open_image",
        json!({"path":source,"dataset":"/counts"}),
    );
    call(&mut loaded, "open_calibration", json!({"path":poni}));
    assert_eq!(
        call(&mut loaded, "pixel", json!({"x":7,"y":4})).result["pixel"]["twoTheta"],
        pixel["twoTheta"]
    );
    call(
        &mut s,
        "image_transform",
        json!({"operation":"rotate_left"}),
    );
    // Replacing calibration while rotated must preserve the newly loaded
    // detector when transformations are later reset, including after reload.
    let mut rotated_geometry = manual();
    rotated_geometry["pixel1"] = json!(80e-6);
    rotated_geometry["pixel2"] = json!(95e-6);
    call(
        &mut s,
        "manual_geometry",
        json!({"convention":"pyfai","values":rotated_geometry}),
    );
    let rotated = temp.path().join("rotated.poni");
    call(&mut s, "save_calibration", json!({"path":rotated}));
    call(&mut s, "open_calibration", json!({"path":rotated}));
    let project = temp.path().join("owned.dio");
    call(&mut s, "save_project", json!({"path":project}));
    // Both sessions own live readers; close them before removing the sources.
    drop(s);
    drop(loaded);
    std::fs::remove_file(&source).unwrap();
    std::fs::remove_file(&definition).unwrap();
    let mut restored = Session::new(root());
    let r = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(r.result["state"]["shape"], json!([12, 8]));
    assert_eq!(r.result["state"]["maskedPixels"], 1);
    call(
        &mut restored,
        "image_transform",
        json!({"operation":"reset"}),
    );
    let r = call(&mut restored, "pixel", json!({"x":7,"y":4}));
    assert_eq!(r.result["pixel"]["twoTheta"], pixel["twoTheta"]);
}

#[test]
fn missing_spline_and_incompatible_detector_fail_atomically() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("source.h5");
    image(&source, 8, 12);
    let mut s = Session::new(root());
    let before = call(
        &mut s,
        "open_image",
        json!({"path":source,"dataset":"/counts"}),
    );
    for (action, payload) in [
        ("calibration_setup", json!({"detector":"Pilatus1M"})),
        (
            "distortion_file",
            json!({"path":temp.path().join("missing.spline")}),
        ),
    ] {
        let r = s.invoke(&Request {
            id: 3,
            action: action.into(),
            payload,
            cached_buffers: vec![],
        });
        assert_eq!(r.result["ok"], false);
        let after = call(&mut s, "state", json!({}));
        assert_eq!(
            after.result["state"]["geometry"],
            before.result["state"]["geometry"]
        );
        assert_eq!(after.result["state"]["calibration"]["detector"], "Custom");
    }
}

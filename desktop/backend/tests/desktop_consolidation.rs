use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};

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
    let reply = invoke(s, action, payload);
    assert_eq!(reply.result["ok"], true, "{action}: {}", reply.result);
    reply
}
fn image(path: &Path, shape: [usize; 2], value: u16) {
    tiff::encoder::TiffEncoder::new(std::fs::File::create(path).unwrap())
        .unwrap()
        .write_image::<tiff::encoder::colortype::Gray16>(
            shape[1] as u32,
            shape[0] as u32,
            &vec![value; shape[0] * shape[1]],
        )
        .unwrap();
}
fn geometry(s: &mut Session) {
    call(
        s,
        "manual_geometry",
        json!({"convention":"pyfai","values":{
        "dist":150.,"poni1":1.2,"poni2":1.6,"rot1":0.,"rot2":0.,"rot3":0.,
        "wavelength":0.4,"pixel1":100.,"pixel2":100.,"polarization_factor":0.99}}),
    );
    call(s, "integration_settings", json!({"bins":24,"cake_bins":12}));
}
fn y(reply: &Reply) -> Vec<f64> {
    reply.result["pattern"]["y"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap())
        .collect()
}
fn proportional(actual: &[f64], expected: &[f64], factor: f64) {
    assert_eq!(actual.len(), expected.len());
    for (a, b) in actual.iter().zip(expected) {
        assert!(
            (a - factor * b).abs() < 1e-10 * (1. + (factor * b).abs()),
            "{a} vs {}",
            factor * b
        );
    }
}

#[test]
fn image_size_prompt_is_readonly_and_reset_keeps_references() {
    let temp = tempfile::tempdir().unwrap();
    let a = temp.path().join("image_001.tif");
    let b = temp.path().join("image_002.tif");
    image(&a, [24, 32], 10);
    image(&b, [16, 20], 30);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":a}));
    geometry(&mut s);
    call(
        &mut s,
        "mask_stroke",
        json!({"points":[[10,10]],"radius":3}),
    );
    call(
        &mut s,
        "integration_overlay",
        json!({"operation":"capture"}),
    );
    call(&mut s, "integration_image_background", json!({"path":a}));
    let before = call(&mut s, "state", json!({}));
    let pending = call(&mut s, "open_image", json!({"path":b}));
    assert_eq!(
        pending.result["imageChange"]["previousShape"],
        json!([24, 32])
    );
    assert_eq!(pending.result["imageChange"]["newShape"], json!([16, 20]));
    assert_eq!(pending.result["cancelled"], true);
    assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    assert_eq!(
        call(&mut s, "next_image", json!({"direction":1})).result["imageChange"],
        pending.result["imageChange"]
    );
    let reset = call(
        &mut s,
        "open_image",
        json!({"path":b,"reset_calibration":true}),
    );
    assert_eq!(reset.result["calibrationReset"], true);
    assert_eq!(reset.result["state"]["calibrated"], false);
    assert_eq!(reset.result["state"]["shape"], json!([16, 20]));
    assert_eq!(reset.result["state"]["maskedPixels"], 0);
    assert!(reset.result["pattern"].is_null() && reset.result["cake"].is_null());
    assert_eq!(
        reset.result["state"]["integration"]["overlays"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    assert!(reset.result["state"]["integration"]["imageBackground"]["filename"].is_null());
    assert_eq!(invoke(&mut s, "integrate", json!({})).result["ok"], false);
    assert_eq!(
        invoke(
            &mut s,
            "integration_save_pattern",
            json!({"path":temp.path().join("stale.xy")})
        )
        .result["ok"],
        false
    );
    geometry(&mut s);
    assert!(call(&mut s, "state", json!({})).result["pattern"].is_object());
}

#[test]
fn same_shape_and_unreadable_image_preserve_geometry_and_rotations() {
    let temp = tempfile::tempdir().unwrap();
    let a = temp.path().join("a.tif");
    let b = temp.path().join("b.tif");
    image(&a, [24, 32], 10);
    image(&b, [24, 32], 30);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":a}));
    geometry(&mut s);
    call(
        &mut s,
        "image_transform",
        json!({"operation":"rotate_right"}),
    );
    let before = call(&mut s, "state", json!({}));
    let same = call(&mut s, "open_image", json!({"path":b}));
    assert_eq!(
        same.result["state"]["geometry"],
        before.result["state"]["geometry"]
    );
    assert_eq!(same.result["state"]["shape"], json!([32, 24]));
    let state = call(&mut s, "state", json!({}));
    let missing = invoke(
        &mut s,
        "open_image",
        json!({"path":temp.path().join("missing.tif"),"reset_calibration":true}),
    );
    assert_eq!(missing.result["ok"], false);
    assert_eq!(call(&mut s, "state", json!({})).result, state.result);
    let reset = call(&mut s, "reset_calibration", json!({}));
    assert_eq!(reset.result["state"]["shape"], json!([24, 32]));
    assert_eq!(
        reset.result["state"]["calibration"]["setupConfirmed"],
        false
    );
}

#[test]
fn native_combination_scales_raw_contributions_keeps_masks_and_roundtrips() {
    let temp = tempfile::tempdir().unwrap();
    let a = temp.path().join("first.tif");
    let b = temp.path().join("second.tif");
    image(&a, [24, 32], 10);
    image(&b, [24, 32], 30);
    let mut s = Session::new(root());
    let host = call(&mut s, "__host__", json!({}));
    assert_eq!(host.result["runtime"], "rust");
    assert_eq!(host.result["engine"], "dioptrin");
    assert_eq!(host.result["qtApplication"], false);
    call(&mut s, "open_image", json!({"path":a}));
    geometry(&mut s);
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(&mut s, "open_image", json!({"path":b}));
    let combined = call(
        &mut s,
        "combination_settings",
        json!({"patterns":true,"cakes":true}),
    );
    assert_eq!(
        combined.result["state"]["combination"]["backends"]["pattern"],
        "Dioptrin · native Rust"
    );
    assert_eq!(
        combined.result["state"]["combination"]["backends"]["cake"],
        "Dioptrin · native Rust"
    );
    let initial = y(&combined);
    assert!(initial.iter().any(|v| *v > 0.));
    assert!(combined.result["cake"].is_object());
    let scaled = call(&mut s, "combination_settings", json!({"factor":3.}));
    proportional(&y(&scaled), &initial, 2.5);
    call(&mut s, "combination_settings", json!({"factor":1.}));
    let masked = call(
        &mut s,
        "mask_stroke",
        json!({"points":[[16,12]],"radius":100}),
    );
    proportional(&y(&masked), &initial, 0.5);
    let export = temp.path().join("combined.xy");
    call(&mut s, "save_combined_pattern", json!({"path":export}));
    assert!(
        std::fs::read_to_string(export)
            .unwrap()
            .lines()
            .filter(|l| !l.starts_with('#'))
            .count()
            >= initial.len()
    );
    for (action, subtract) in [
        ("integration_save_pattern", true),
        ("export_pattern", false),
    ] {
        let output = temp.path().join(format!("{action}.xy"));
        call(
            &mut s,
            action,
            json!({"path":output,"subtract_background":subtract}),
        );
        let exported: Vec<f64> = std::fs::read_to_string(output)
            .unwrap()
            .lines()
            .filter(|line| !line.starts_with('#') && !line.is_empty())
            .map(|line| line.split_whitespace().nth(1).unwrap().parse().unwrap())
            .collect();
        proportional(&exported, &y(&masked), 1.);
    }
    let project = temp.path().join("experiment.dio");
    call(&mut s, "save_project", json!({"path":project}));
    let mut restored = Session::new(root());
    let opened = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(opened.result["state"]["combination"]["patterns"], true);
    assert_eq!(opened.result["state"]["combination"]["cakes"], true);
    proportional(&y(&opened), &y(&masked), 1.);
    let first = call(
        &mut restored,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(first.result["state"]["maskedPixels"], 0);
    proportional(&y(&first), &y(&masked), 1.);
    let second = call(
        &mut restored,
        "configuration",
        json!({"operation":"select","index":1}),
    );
    assert_eq!(second.result["state"]["maskedPixels"], 24 * 32);
}

#[test]
fn unequal_detectors_and_combined_units_keep_independent_geometry() {
    let temp = tempfile::tempdir().unwrap();
    let a = temp.path().join("first.tif");
    let b = temp.path().join("second.tif");
    image(&a, [24, 32], 10);
    image(&b, [16, 20], 30);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":a}));
    geometry(&mut s);
    let first = call(&mut s, "state", json!({})).result["state"]["geometry"].clone();
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(
        &mut s,
        "open_image",
        json!({"path":b,"reset_calibration":true}),
    );
    geometry(&mut s);
    call(&mut s, "settings", json!({"unit":"q_A^-1"}));
    let combined = call(
        &mut s,
        "combination_settings",
        json!({"patterns":true,"cakes":true}),
    );
    assert_eq!(combined.result["pattern"]["unit"], "q_A^-1");
    assert_eq!(combined.result["cake"]["unit"], "q_A^-1");
    assert!(y(&combined).iter().all(|v| v.is_finite()));
    let d = call(&mut s, "settings", json!({"unit":"d_A"}));
    // Unit buttons retain the shared cake's scientific source grid.
    assert_eq!(d.result["cake"]["unit"], "q_A^-1");
    assert_eq!(
        d.result["cake"]["bufferId"],
        combined.result["cake"]["bufferId"]
    );
    let x = d.result["pattern"]["x"].as_array().unwrap();
    assert!(x[0].as_f64().unwrap() > x.last().unwrap().as_f64().unwrap());
    let one = call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(one.result["state"]["shape"], json!([24, 32]));
    assert_eq!(one.result["state"]["geometry"], first);
}

#[test]
fn variable_size_frames_use_the_same_change_confirmation() {
    let temp = tempfile::tempdir().unwrap();
    let file = temp.path().join("variable.tif");
    let mut encoder =
        tiff::encoder::TiffEncoder::new(std::fs::File::create(&file).unwrap()).unwrap();
    encoder
        .write_image::<tiff::encoder::colortype::Gray16>(32, 24, &vec![10; 32 * 24])
        .unwrap();
    encoder
        .write_image::<tiff::encoder::colortype::Gray16>(20, 16, &vec![30; 20 * 16])
        .unwrap();
    drop(encoder);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":file}));
    geometry(&mut s);
    let before = call(&mut s, "state", json!({}));
    let pending = call(&mut s, "next_image", json!({"direction":1}));
    assert_eq!(pending.result["imageChange"]["frame"], 1);
    assert_eq!(pending.result["imageChange"]["newShape"], json!([16, 20]));
    assert_eq!(call(&mut s, "state", json!({})).result, before.result);
    let accepted = call(
        &mut s,
        "open_image",
        json!({"path":file,"frame":1,"reset_calibration":true}),
    );
    assert_eq!(accepted.result["state"]["shape"], json!([16, 20]));
    assert_eq!(accepted.result["state"]["calibrated"], false);
}

#[test]
fn individual_and_combined_cake_clicks_respect_radial_units_and_preserve_inspection_on_error() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("detector.tif");
    image(&source, [24, 32], 10);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":source}));
    call(
        &mut s,
        "manual_geometry",
        json!({"convention":"pyfai","values":{
            "dist":0.15,"poni1":0.0012,"poni2":0.0016,"rot1":0.,"rot2":0.,"rot3":0.,
            "wavelength":4e-11,"pixel1":0.0001,"pixel2":0.0001,"polarization_factor":0.99
        }}),
    );
    call(
        &mut s,
        "integration_settings",
        json!({"bins":24,"cake_bins":12}),
    );
    let theta: f64 = 0.5;
    let q = 4. * std::f64::consts::PI * (theta.to_radians() / 2.).sin() / 0.4;
    let spacing = 2. * std::f64::consts::PI / q;
    for combined in [false, true] {
        if combined {
            call(&mut s, "configuration", json!({"operation":"duplicate"}));
            call(
                &mut s,
                "combination_settings",
                json!({"cakes":true,"patterns":true}),
            );
        }
        for display_unit in ["2th_deg", "q_A^-1", "d_A"] {
            let state = call(&mut s, "settings", json!({"unit":display_unit}));
            assert_eq!(
                state.result["cake"]["unit"],
                "2th_deg" // This cake was created on the angular grid; display units do not rebin it.
            );
            for (unit, x) in [("2th_deg", theta), ("q_A^-1", q), ("d_A", spacing)] {
                let selected = call(
                    &mut s,
                    "validation_position",
                    json!({"source":"cake","unit":unit,"x":x,"azimuth":393.}),
                );
                let linked = &selected.result["linked"];
                assert!((linked["twoTheta"].as_f64().unwrap() - theta).abs() < 1e-12);
                let expected = match display_unit {
                    "q_A^-1" => q,
                    "d_A" => spacing,
                    _ => theta,
                };
                assert!((linked["radial"].as_f64().unwrap() - expected).abs() < 1e-10);
                assert_eq!(linked["azimuth"], 33.);
                assert!(
                    linked["contours"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .any(|line| !line["points"].as_array().unwrap().is_empty())
                );
            }
            // Map/frame restoration sends physical 2θ without a unit, even in Q/d mode.
            let before = call(
                &mut s,
                "validation_position",
                json!({"source":"cake","x":theta,"azimuth":33.}),
            );
            for payload in [
                json!({"unit":"unknown","x":theta}),
                json!({"unit":null,"x":theta}),
                json!({"unit":"q_A^-1","x":1000.}),
                json!({"unit":"2th_deg","x":-1.}),
            ] {
                let mut args = json!({"source":"cake"});
                args.as_object_mut()
                    .unwrap()
                    .extend(payload.as_object().unwrap().clone());
                assert_eq!(
                    invoke(&mut s, "validation_position", args).result["ok"],
                    false
                );
                assert_eq!(
                    call(&mut s, "state", json!({})).result["linked"],
                    before.result["linked"]
                );
            }
        }
    }
}

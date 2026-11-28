#[cfg(feature = "dioptrin")]
use dioptas_backend::control::Control;
use dioptas_backend::{Session, protocol::Request};
use serde_json::{Value, json};
use std::{
    fs,
    path::{Path, PathBuf},
};
#[cfg(feature = "dioptrin")]
use std::{
    sync::Arc,
    time::{Duration, Instant},
};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .into()
}
fn request(action: &str, payload: Value) -> Request {
    Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    }
}
fn call(s: &mut Session, action: &str, payload: Value) -> Value {
    let r = s.invoke(&request(action, payload)).result;
    assert_eq!(r["ok"], true, "{action}: {r}");
    r
}
fn state(s: &mut Session) -> Value {
    call(s, "state", json!({}))["state"].clone()
}
fn npy(path: &Path, shape: [usize; 2], values: &[f64]) {
    let mut h = format!(
        "{{'descr': '<f8', 'fortran_order': False, 'shape': ({}, {}), }}",
        shape[0], shape[1]
    );
    while (10 + h.len() + 1) % 64 != 0 {
        h.push(' ');
    }
    h.push('\n');
    let mut b = b"\x93NUMPY\x01\x00".to_vec();
    b.extend_from_slice(&(h.len() as u16).to_le_bytes());
    b.extend_from_slice(h.as_bytes());
    for v in values {
        b.extend_from_slice(&v.to_le_bytes());
    }
    fs::write(path, b).unwrap();
}
struct Fixture {
    temp: tempfile::TempDir,
    image: PathBuf,
    peaks: PathBuf,
    groups: Value,
}
fn fixture() -> Fixture {
    let temp = tempfile::tempdir().unwrap();
    let image = temp.path().join("rings.npy");
    let peaks = temp.path().join("peaks.json");
    let spacings = dioptrin::calibration::Calibrant::builtin("CeO2")
        .unwrap()
        .d_spacings;
    let mut data = vec![5.0_f64; 256 * 256];
    let mut groups = vec![];
    for (ring, &d) in spacings.iter().take(5).enumerate() {
        let r = 200.0 * (2.0 * (0.5 / (2.0 * d)).asin()).tan();
        let mut points = vec![];
        for i in 0..12 {
            let angle = std::f64::consts::TAU * (i as f64 + 0.13) / 12.0;
            let y = 125.2 + r * angle.sin();
            let x = 129.7 + r * angle.cos();
            points.push([y, x]);
            for row in (y as usize).saturating_sub(6)..((y as usize) + 7).min(256) {
                for col in (x as usize).saturating_sub(6)..((x as usize) + 7).min(256) {
                    data[row * 256 + col] += 1000.0
                        * (-((row as f64 - y).powi(2) + (col as f64 - x).powi(2))
                            / (2.0 * 1.2_f64.powi(2)))
                        .exp();
                }
            }
        }
        groups.push(json!({"ring":ring+1,"points":points}));
    }
    let stored: Vec<_> = (0..256)
        .rev()
        .flat_map(|r| data[r * 256..(r + 1) * 256].iter().copied())
        .collect();
    npy(&image, [256, 256], &stored);
    let groups = json!(groups);
    fs::write(&peaks,serde_json::to_vec(&json!({"format":"dioptas-calibration-peaks","version":1,"coordinates":"row-column-bottom-left","imageShape":[256,256],"imageTransformations":[],"calibrant":{"name":"CeO2","dSpacingsAngstrom":spacings},"groups":groups})).unwrap()).unwrap();
    Fixture {
        temp,
        image,
        peaks,
        groups,
    }
}
fn prepared(f: &Fixture) -> Session {
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":f.image}));
    call(
        &mut s,
        "calibration_setup",
        json!({"calibrant":"CeO2","distance":19.0,"wavelength":0.5,"pixel_x":100.0,"pixel_y":100.0}),
    );
    call(
        &mut s,
        "fit_parameters",
        json!({"parameters":{"rot1":{"value":0,"refine":false},"rot2":{"value":0,"refine":false},"rot3":{"value":0,"refine":false}}}),
    );
    call(&mut s, "load_peaks", json!({"path":f.peaks}));
    s
}

#[test]
fn setup_and_fit_drafts_validate_atomically_and_preserve_defaults() {
    let f = fixture();
    let mut s = Session::new(root());
    let empty = state(&mut s);
    assert_eq!(
        empty["calibration"]["workflow"]["automaticRefinement"],
        true
    );
    assert_eq!(empty["calibration"]["workflow"]["deltaTth"], 0.1);
    assert!(empty["calibration"]["calibrants"].as_array().unwrap().len() > 20);
    call(&mut s, "open_image", json!({"path":f.image}));
    assert_eq!(
        call(
            &mut s,
            "calibration_setup",
            json!({"pixel_x":100,"pixel_y":100})
        )["state"]["calibration"]["setupConfirmed"],
        false
    );
    let before = state(&mut s);
    assert_eq!(
        s.invoke(&request(
            "fit_parameters",
            json!({"parameters":{"dist":{"value":-1,"refine":true}}})
        ))
        .result["ok"],
        false
    );
    assert_eq!(state(&mut s)["calibration"], before["calibration"]);
    let mut parameters = before["calibration"]["parameters"].clone();
    parameters["wavelength"]["value"] = json!(0.5);
    assert_eq!(
        call(
            &mut s,
            "fit_parameters",
            json!({"parameters":parameters,"polarization":0.8})
        )["state"]["calibration"]["setupConfirmed"],
        true
    );
}

#[test]
fn single_peak_groups_reassign_delete_undo_redo_and_files_match_the_existing_schema() {
    let f = fixture();
    let mut s = prepared(&f);
    let original = state(&mut s)["calibration"]["picks"].clone();
    call(&mut s, "reassign_pick", json!({"index":0,"ring":2}));
    assert_eq!(state(&mut s)["calibration"]["picks"][0]["ring"], 2);
    assert_eq!(
        call(&mut s, "undo_calibration", json!({}))["state"]["calibration"]["picks"],
        original
    );
    call(&mut s, "redo_calibration", json!({}));
    let before = state(&mut s)["calibration"].clone();
    assert_eq!(
        s.invoke(&request("remove_picks", json!({"indices":[0,999]})))
            .result["ok"],
        false
    );
    assert_eq!(state(&mut s)["calibration"], before);
    call(&mut s, "remove_picks", json!({"indices":[0,2,2]}));
    assert_eq!(
        state(&mut s)["calibration"]["picks"]
            .as_array()
            .unwrap()
            .len(),
        3
    );
    call(&mut s, "undo_calibration", json!({}));
    let path = f.temp.path().join("native-peaks.json");
    call(&mut s, "save_peaks", json!({"path":path}));
    let saved: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
    assert_eq!(saved["coordinates"], "row-column-bottom-left");
    call(&mut s, "clear_peaks", json!({}));
    call(&mut s, "load_peaks", json!({"path":path}));
    assert_eq!(state(&mut s)["calibration"]["picks"], saved["groups"]);
    let before = state(&mut s);
    let mut invalid = saved;
    invalid["groups"][0]["points"][0][0] = json!(999);
    fs::write(&path, serde_json::to_vec(&invalid).unwrap()).unwrap();
    assert_eq!(
        s.invoke(&request("load_peaks", json!({"path":path})))
            .result["ok"],
        false
    );
    assert_eq!(state(&mut s)["calibration"], before["calibration"]);
    let point = f.groups[0]["points"][0].as_array().unwrap();
    let result = call(
        &mut s,
        "pick_peak",
        json!({"x":point[1],"y":point[0],"ring":1,"automatic":false,"search_size":6}),
    );
    assert_eq!(result["pickedCount"], 1);
    assert_eq!(result["nextRing"], 2);
    call(&mut s, "undo_calibration", json!({}));
    call(&mut s, "workflow_settings", json!({"autoIncrement":false}));
    let result = call(
        &mut s,
        "pick_peak",
        json!({"x":point[1],"y":point[0],"ring":1,"automatic":false}),
    );
    assert_eq!(result["nextRing"], 1);
    assert_eq!(result["state"]["calibration"]["canRedo"], false);
}

#[cfg(feature = "dioptrin")]
#[test]
fn missed_peak_picks_leave_calibration_and_history_unchanged() {
    let f = fixture();
    let mut data = vec![0.0; 256 * 256];
    // A nonfinite patch also gives single-peak search no eligible samples.
    for y in 120..136 {
        for x in 120..136 {
            data[y * 256 + x] = f64::NAN;
        }
    }
    npy(&f.image, [256, 256], &data);
    let mut s = prepared(&f);
    call(&mut s, "clear_peaks", json!({}));
    call(&mut s, "undo_calibration", json!({}));
    let before = state(&mut s);
    assert_eq!(before["calibration"]["canRedo"], true);
    for automatic in [true, false] {
        let result = call(
            &mut s,
            "pick_peak",
            json!({"x":128,"y":128,"ring":1,"automatic":automatic,"search_size":6}),
        );
        assert_eq!(result["noPeakFound"], true);
        assert_eq!(result["pickedCount"], 0);
        assert!(result.get("nextRing").is_none());
        assert_eq!(state(&mut s), before);
    }
    call(&mut s, "redo_calibration", json!({}));
    assert_eq!(state(&mut s)["calibration"]["picks"], json!([]));
    assert_eq!(
        s.invoke(&request("pick_peak", json!({"x":128,"y":128,"ring":0})))
            .result["ok"],
        false
    );
}

#[cfg(feature = "dioptrin")]
#[test]
fn seeded_massif_picking_recovers_subpixel_positions_on_original_samples() {
    let f = fixture();
    let mut s = prepared(&f);
    call(&mut s, "clear_peaks", json!({}));
    let p = &f.groups[0]["points"][0];
    let result = call(&mut s, "pick_peak", json!({"x":p[1],"y":p[0],"ring":1}));
    let points = result["state"]["calibration"]["picks"][0]["points"]
        .as_array()
        .unwrap();
    assert!(points.iter().any(|v| {
        (v[0].as_f64().unwrap() - p[0].as_f64().unwrap())
            .hypot(v[1].as_f64().unwrap() - p[1].as_f64().unwrap())
            < 0.2
    }));
}

#[cfg(feature = "dioptrin")]
#[test]
fn fitting_recovers_known_geometry_and_history_restores_the_entire_fit() {
    let f = fixture();
    let mut s = prepared(&f);
    let before = state(&mut s);
    let fitted = call(
        &mut s,
        "calibrate",
        json!({"automatic":false,"restart":true}),
    );
    assert!((fitted["state"]["geometry"]["dist"].as_f64().unwrap() - 0.02).abs() < 1e-8);
    assert!((fitted["state"]["geometry"]["poni1"].as_f64().unwrap() - 0.01257).abs() < 1e-8);
    assert!((fitted["state"]["geometry"]["poni2"].as_f64().unwrap() - 0.01302).abs() < 1e-8);
    assert!(
        fitted["state"]["calibration"]["rmsDegrees"]
            .as_f64()
            .unwrap()
            < 1e-6
    );
    assert!(!fitted["rings"].as_array().unwrap().is_empty());
    assert_eq!(fitted["state"]["calibration"]["fitDirty"], false);
    let undone = call(&mut s, "undo_calibration", json!({}));
    assert_eq!(undone["state"]["geometry"], before["geometry"]);
    assert_eq!(undone["state"]["calibrated"], false);
    let redone = call(&mut s, "redo_calibration", json!({}));
    assert_eq!(redone["state"]["geometry"], fitted["state"]["geometry"]);
    assert_eq!(
        redone["state"]["calibration"]["rmsDegrees"],
        fitted["state"]["calibration"]["rmsDegrees"]
    );
    let out = f.temp.path().join("fit.poni");
    call(&mut s, "save_calibration", json!({"path":out}));
    call(&mut s, "reassign_pick", json!({"index":0,"ring":2}));
    assert_eq!(
        s.invoke(&request("save_calibration", json!({"path":out})))
            .result["ok"],
        false
    );
}

#[cfg(feature = "dioptrin")]
#[test]
fn distance_tilts_and_free_wavelength_constraints_are_honored() {
    let f = fixture();
    let mut s = prepared(&f);
    call(
        &mut s,
        "fit_parameters",
        json!({"parameters":{"dist":{"value":20.0,"refine":false},"wavelength":{"value":0.49,"refine":true}}}),
    );
    let fitted = call(&mut s, "calibrate", json!({"automatic":false}));
    assert_eq!(fitted["state"]["geometry"]["dist"], 0.02);
    assert_eq!(fitted["state"]["geometry"]["rot1"], 0.0);
    assert_eq!(fitted["state"]["geometry"]["rot2"], 0.0);
    let mar_rot3 = fitted["state"]["geometry"]["rot3"].as_f64().unwrap();
    assert!(
        mar_rot3.is_finite() && mar_rot3.abs() <= std::f64::consts::FRAC_PI_2 + 1e-6,
        "unexpected rot3: {mar_rot3}"
    );
    assert!(
        (fitted["state"]["geometry"]["wavelength"].as_f64().unwrap() * 1e10 - 0.5).abs() < 1e-7
    );
    assert_eq!(fitted["state"]["calibration"]["fitWavelength"], true);
}

#[cfg(feature = "dioptrin")]
#[test]
fn fixed_rotations_keep_their_entered_interval_and_all_fixed_fits_are_valid() {
    let f = fixture();
    let mut s = prepared(&f);
    call(
        &mut s,
        "fit_parameters",
        json!({"parameters":{"rot3":{"value":4.0,"refine":false}}}),
    );
    let fitted = call(&mut s, "calibrate", json!({"automatic":false}));
    assert_eq!(fitted["state"]["geometry"]["rot3"], 4.0);
    let parameters = json!({"dist":{"value":20,"refine":false},"poni1":{"value":12.57,"refine":false},"poni2":{"value":13.02,"refine":false},
        "rot1":{"value":0,"refine":false},"rot2":{"value":0,"refine":false},"rot3":{"value":4,"refine":false},"wavelength":{"value":0.5,"refine":false}});
    let fixed = call(
        &mut s,
        "calibrate",
        json!({"parameters":parameters,"automatic":false}),
    );
    assert_eq!(fixed["state"]["calibration"]["freeParameterCount"], 0);
    assert!(
        fixed["state"]["calibration"]["rmsDegrees"]
            .as_f64()
            .unwrap()
            < 1e-6
    );
    let before = state(&mut s);
    assert_eq!(
        s.invoke(&request(
            "calibrate",
            json!({"parameters":{"wavelength":{"value":10,"refine":false}},"automatic":false})
        ))
        .result["ok"],
        false
    );
    assert_eq!(state(&mut s)["calibration"], before["calibration"]);
}

#[cfg(not(feature = "dioptrin"))]
#[test]
fn editing_is_available_without_an_engine_but_fitting_never_uses_python() {
    let f = fixture();
    let mut s = prepared(&f);
    let before = state(&mut s);
    for (action, args) in [
        ("calibrate", json!({"automatic":false})),
        ("pick_peak", json!({"x":120,"y":120,"ring":1})),
        ("calibration_engine", json!({"engine":"pyfai"})),
    ] {
        assert_eq!(s.invoke(&request(action, args)).result["ok"], false);
        assert_eq!(state(&mut s)["calibration"], before["calibration"]);
    }
}

#[cfg(feature = "dioptrin")]
#[test]
fn automatic_massif_and_blob_search_keep_controls_and_rollback_empty_searches() {
    // 1. Automatic refinement from manual picks on a real powder image uses
    //    Dioptrin's zero-config refine_image and converges cleanly.
    let mut s = Session::new(root());
    call(&mut s, "example", json!({}));
    for (x, y, ring) in [
        (637.0, 564.0, 1),
        (671.0, 511.0, 2),
        (668.0, 703.0, 3),
        (350.5, 592.8, 1),
        (554.3, 367.9, 1),
    ] {
        call(&mut s, "pick_peak", json!({"x": x, "y": y, "ring": ring}));
    }
    let fitted = call(&mut s, "calibrate", json!({"automatic": true}));
    assert!(
        fitted["state"]["calibration"]["picks"]
            .as_array()
            .unwrap()
            .len()
            >= 3,
        "{}",
        fitted["state"]["calibration"]
    );
    assert!(
        fitted["state"]["calibration"]["rmsDegrees"]
            .as_f64()
            .unwrap()
            < 0.05
    );

    // 2. When image refinement fails (e.g. blank image), previous geometry,
    //    picks, and pattern are cleanly restored.
    let f = fixture();
    let mut s_blank = prepared(&f);
    call(&mut s_blank, "calibrate", json!({"automatic": false}));
    let blank_path = f.temp.path().join("blank_same.npy");
    npy(&blank_path, [256, 256], &[0.0; 256 * 256]);
    call(&mut s_blank, "open_image", json!({"path": &blank_path}));
    call(&mut s_blank, "load_peaks", json!({"path": f.peaks}));
    let before = state(&mut s_blank);
    let product = call(&mut s_blank, "state", json!({}))["pattern"].clone();
    let result = s_blank
        .invoke(&request(
            "calibrate",
            json!({"automatic": true, "restart": true}),
        ))
        .result;
    assert_eq!(result["ok"], false);
    assert!(result["error"].as_str().unwrap().contains("restored"));
    let after = state(&mut s_blank);
    assert_eq!(after["geometry"], before["geometry"]);
    assert_eq!(after["calibration"], before["calibration"]);
    assert_eq!(call(&mut s_blank, "state", json!({}))["pattern"], product);
}

#[cfg(feature = "dioptrin")]
#[test]
fn live_progress_is_detached_and_cancellation_restores_geometry_picks_and_history() {
    let control = Arc::new(Control::default());
    let worker_control = control.clone();
    let worker = std::thread::spawn(move || {
        let mut s = Session::new(root());
        call(&mut s, "example", json!({}));
        for (x, y, ring) in [
            (637.0, 564.0, 1),
            (671.0, 511.0, 2),
            (668.0, 703.0, 3),
            (350.5, 592.8, 1),
            (554.3, 367.9, 1),
        ] {
            call(&mut s, "pick_peak", json!({"x": x, "y": y, "ring": ring}));
        }
        call(&mut s, "calibrate", json!({"automatic": false}));
        let before = state(&mut s);
        let products = call(&mut s, "state", json!({}));
        let result = s
            .invoke_controlled(
                &request("calibrate", json!({"automatic": true})),
                worker_control,
            )
            .result;
        (
            before,
            products,
            result,
            state(&mut s),
            call(&mut s, "state", json!({})),
        )
    });
    let deadline = Instant::now() + Duration::from_secs(30);
    let mut observed = None;
    while Instant::now() < deadline {
        let p = control.progress();
        if p["label"] == "Refining calibration from image" {
            observed = Some(p);
            break;
        }
        if worker.is_finished() {
            break;
        }
        std::thread::sleep(Duration::from_millis(1));
    }
    let preview = observed.expect("live refining progress");
    assert!(
        !preview["calibration"]["rings"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let frozen = serde_json::to_string(&preview).unwrap();
    control.cancel();
    let (before, products, result, after, restored) = worker.join().unwrap();
    assert_eq!(result["ok"], false);
    assert!(result["error"].as_str().unwrap().contains("cancelled"));
    assert_eq!(after["geometry"], before["geometry"]);
    assert_eq!(after["calibration"], before["calibration"]);
    assert_eq!(restored["pattern"], products["pattern"]);
    assert_eq!(restored["cake"], products["cake"]);
    assert_eq!(serde_json::to_string(&preview).unwrap(), frozen);
    assert_eq!(control.progress()["running"], false);
    assert!(control.progress().get("calibration").is_none());
}

#[test]
fn custom_calibrants_are_session_owned_and_invalid_files_do_not_replace_them() {
    let f = fixture();
    let mut s = prepared(&f);
    let file = f.temp.path().join("private.D");
    fs::write(&file, "# private reference\n3.0\n2.0\n1.0\n").unwrap();
    let opened = call(&mut s, "open_calibrant", json!({"path":file}));
    assert_eq!(
        opened["state"]["calibration"]["calibrant"],
        "private (custom)"
    );
    fs::remove_file(&file).unwrap();
    call(&mut s, "validation_calibrant", json!({"calibrant":"CeO2"}));
    assert_eq!(
        call(
            &mut s,
            "validation_calibrant",
            json!({"calibrant":"private (custom)"})
        )["state"]["calibration"]["rings"]
            .as_array()
            .unwrap()
            .len(),
        3
    );
    fs::write(&file, "NaN\n").unwrap();
    let before = state(&mut s)["calibration"].clone();
    assert_eq!(
        s.invoke(&request("open_calibrant", json!({"path":file})))
            .result["ok"],
        false
    );
    assert_eq!(state(&mut s)["calibration"], before);
}

#[test]
fn poni_calibrant_comment_round_trips_and_follows_pyfai_calib2() {
    let temp = tempfile::tempdir().unwrap();
    let geometry = "PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.1\nPoni1: 0.003\nPoni2: 0.004\nRot1: 0\nRot2: 0\nRot3: 0\nSplineFile: None\nWavelength: 4e-11\n";
    // pyFAI-calib2 writes the calibrant and image as trailing comments.
    let pyfai = temp.path().join("pyfai_CeO2.poni");
    fs::write(
        &pyfai,
        format!("# Nota: C-Order, 1 refers to the Y axis, 2 to the X axis\n{geometry}# Calibrant: Si\n# Image: si.tif\n"),
    )
    .unwrap();
    let unknown = temp.path().join("unknown_CeO2.poni");
    fs::write(&unknown, format!("# Calibrant: Unobtainium\n{geometry}")).unwrap();
    let plain = temp.path().join("plain.poni");
    fs::write(&plain, geometry).unwrap();

    let mut s = Session::new(root());
    call(&mut s, "validation_calibrant", json!({"calibrant":"CeO2"}));
    let recorded = call(&mut s, "open_calibration", json!({"path":pyfai}));
    assert_eq!(recorded["calibrantNotice"], "calibrant Si from file");
    assert_eq!(state(&mut s)["calibration"]["calibrant"], "Si");
    // Recorded names take precedence even when their spacings are unavailable.
    call(&mut s, "open_calibration", json!({"path":unknown}));
    assert_eq!(state(&mut s)["calibration"]["calibrant"], "Si");
    call(&mut s, "open_calibration", json!({"path":plain}));
    assert_eq!(state(&mut s)["calibration"]["calibrant"], "Si");

    call(
        &mut s,
        "validation_calibrant",
        json!({"calibrant":"LaB6_SRM660c"}),
    );
    let saved = temp.path().join("saved.poni");
    call(&mut s, "save_calibration", json!({"path":saved}));
    let text = fs::read_to_string(&saved).unwrap();
    assert_eq!(text.matches("# Calibrant: LaB6_SRM660c\n").count(), 1);

    call(&mut s, "validation_calibrant", json!({"calibrant":"CeO2"}));
    call(&mut s, "open_calibration", json!({"path":saved}));
    let restored = state(&mut s);
    assert_eq!(restored["calibration"]["calibrant"], "LaB6_SRM660c");
    assert_eq!(restored["geometry"]["dist"], 0.1);
    // Loading the calibration is one undo step, calibrant included.
    call(&mut s, "undo_calibration", json!({}));
    assert_eq!(state(&mut s)["calibration"]["calibrant"], "CeO2");
}

const PLAIN_PONI: &str = "PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.019\nPoni1: 0.0125\nPoni2: 0.013\nRot1: 0\nRot2: 0\nRot3: 0\nSplineFile: None\nWavelength: 5e-11\n";

#[test]
fn poni_calibrant_is_recorded_only_once_chosen_and_choosing_keeps_the_fit_clean() {
    let temp = tempfile::tempdir().unwrap();
    let plain = temp.path().join("plain.poni");
    fs::write(&plain, PLAIN_PONI).unwrap();
    let saved = temp.path().join("saved.poni");
    let mut s = Session::new(root());
    call(&mut s, "open_calibration", json!({"path":plain}));
    // The session default was never chosen, so nothing is claimed.
    call(&mut s, "save_calibration", json!({"path":saved}));
    assert!(!fs::read_to_string(&saved).unwrap().contains("Calibrant"));
    // Choosing a calibrant on the setup step leaves a loaded calibration savable.
    let chosen = call(&mut s, "calibration_setup", json!({"calibrant":"Si"}));
    assert_eq!(chosen["state"]["calibration"]["fitDirty"], false);
    call(&mut s, "save_calibration", json!({"path":saved}));
    assert!(
        fs::read_to_string(&saved)
            .unwrap()
            .contains("# Calibrant: Si\n")
    );
}

#[test]
fn poni_calibrant_switch_drops_picks_and_reports_the_change() {
    let f = fixture();
    let mut s = prepared(&f);
    let picks = state(&mut s)["calibration"]["picks"].clone();
    assert!(!picks.as_array().unwrap().is_empty());
    let si = f.temp.path().join("si_400mm_calibration.poni");
    fs::write(&si, PLAIN_PONI).unwrap();
    let loaded = call(&mut s, "open_calibration", json!({"path":si}));
    assert_eq!(loaded["calibrantNotice"], "calibrant Si from filename");
    assert_eq!(loaded["state"]["calibration"]["calibrant"], "Si");
    assert_eq!(loaded["state"]["calibration"]["picks"], json!([]));
    let undone = call(&mut s, "undo_calibration", json!({}));
    assert_eq!(undone["state"]["calibration"]["calibrant"], "CeO2");
    assert_eq!(undone["state"]["calibration"]["picks"], picks);
    // Loading the calibrant already selected keeps picks and says nothing.
    let ceo2 = f
        .temp
        .path()
        .join("ceo2_400mm_20250325-00001_calibration.poni");
    fs::write(&ceo2, PLAIN_PONI).unwrap();
    let same = call(&mut s, "open_calibration", json!({"path":ceo2}));
    assert!(same.get("calibrantNotice").is_none());
    assert_eq!(same["state"]["calibration"]["picks"], picks);
}

#[test]
fn calibration_image_open_detects_only_unambiguous_filename_references() {
    let temp = tempfile::tempdir().unwrap();
    let images = temp.path().join("Ni");
    fs::create_dir(&images).unwrap();
    let mut s = Session::new(root());
    for (filename, detect, expected) in [
        ("ceo2_400mm_20250325-00000.npy", false, "LaB6"),
        ("ceo2_400mm_20250325-00001.npy", true, "CeO2"),
        ("silicon_sample.npy", true, "CeO2"),
        ("LaB6_Si.npy", true, "CeO2"),
        ("scan-lab6_srm660c-001.npy", true, "LaB6_SRM660c"),
        ("scan-lab6-srm660c-002.npy", true, "LaB6_SRM660c"),
    ] {
        let path = images.join(filename);
        npy(&path, [16, 16], &[5.0; 256]);
        let loaded = call(
            &mut s,
            "open_image",
            json!({"path":path,"detect_calibrant":detect}),
        );
        assert_eq!(
            loaded["state"]["calibration"]["calibrant"], expected,
            "{filename}"
        );
    }
    let poni = temp.path().join("silicon.poni");
    fs::write(&poni, format!("{PLAIN_PONI}# Calibrant: Si\n")).unwrap();
    call(&mut s, "open_calibration", json!({"path":poni}));
    let loaded = call(
        &mut s,
        "open_image",
        json!({"path":images.join("ceo2_400mm_20250325-00001.npy"),"detect_calibrant":true}),
    );
    assert_eq!(loaded["state"]["calibration"]["calibrant"], "Si");
    assert!(loaded.get("calibrantNotice").is_none());
}

#[test]
fn calibration_image_open_clears_picks_records_undo_and_preserves_manual_choice_on_frame_change() {
    let f = fixture();
    let ceo2_img = f.temp.path().join("ceo2_001.npy");
    let lab6_img = f.temp.path().join("lab6_001.npy");
    fs::copy(&f.image, &ceo2_img).unwrap();
    fs::copy(&f.image, &lab6_img).unwrap();

    let mut s = Session::new(root());
    call(
        &mut s,
        "open_image",
        json!({"path": &ceo2_img, "detect_calibrant": true}),
    );
    assert_eq!(state(&mut s)["calibration"]["calibrant"], "CeO2");
    call(&mut s, "load_peaks", json!({"path": f.peaks}));
    let picks = state(&mut s)["calibration"]["picks"].clone();
    assert!(!picks.as_array().unwrap().is_empty());

    // Opening a same-shape LaB6 image switches calibrant, clears stale CeO2 picks,
    // resets nextRing to 1, and records a calibration undo step.
    let switched = call(
        &mut s,
        "open_image",
        json!({"path": &lab6_img, "detect_calibrant": true}),
    );
    assert_eq!(switched["state"]["calibration"]["calibrant"], "LaB6");
    assert_eq!(switched["state"]["calibration"]["picks"], json!([]));
    assert_eq!(switched["calibrantNotice"], "Calibrant LaB6 from filename");
    assert_eq!(switched["nextRing"], 1);

    // Undo reverts the filename-detected calibrant back to CeO2 (keeping picks empty
    // for the new image); redo restores LaB6.
    let undone = call(&mut s, "undo_calibration", json!({}));
    assert_eq!(undone["state"]["calibration"]["calibrant"], "CeO2");
    assert_eq!(undone["state"]["calibration"]["picks"], json!([]));
    let redone = call(&mut s, "redo_calibration", json!({}));
    assert_eq!(redone["state"]["calibration"]["calibrant"], "LaB6");
    assert_eq!(redone["state"]["calibration"]["picks"], json!([]));

    // Manually switching calibrant then reopening the same path (frame change)
    // must keep the manual calibrant choice.
    call(&mut s, "calibration_setup", json!({"calibrant": "Si"}));
    assert_eq!(state(&mut s)["calibration"]["calibrant"], "Si");
    let same_file = call(
        &mut s,
        "open_image",
        json!({"path": &lab6_img, "frame": 0, "detect_calibrant": true}),
    );
    assert_eq!(same_file["state"]["calibration"]["calibrant"], "Si");
    assert!(same_file.get("calibrantNotice").is_none());
}

#[test]
fn custom_calibrants_are_recorded_by_file_stem_and_unknown_names_are_reported() {
    let temp = tempfile::tempdir().unwrap();
    let spacings = temp.path().join("mysample.D");
    fs::write(&spacings, "3.1\n2.7\n1.9\n").unwrap();
    let plain = temp.path().join("plain.poni");
    fs::write(&plain, PLAIN_PONI).unwrap();
    let saved = temp.path().join("custom.poni");
    let mut s = Session::new(root());
    call(&mut s, "open_calibration", json!({"path":plain}));
    call(
        &mut s,
        "open_calibrant",
        json!({"path":spacings,"validation":true}),
    );
    call(&mut s, "save_calibration", json!({"path":saved}));
    assert!(
        fs::read_to_string(&saved)
            .unwrap()
            .contains("# Calibrant: mysample\n")
    );
    call(&mut s, "validation_calibrant", json!({"calibrant":"Si"}));
    let reloaded = call(&mut s, "open_calibration", json!({"path":saved}));
    assert_eq!(
        reloaded["state"]["calibration"]["calibrant"],
        "mysample (custom)"
    );
    // Without the spacings file the name cannot be resolved; say so.
    let mut fresh = Session::new(root());
    let missing = call(&mut fresh, "open_calibration", json!({"path":saved}));
    assert_eq!(
        missing["calibrantNotice"],
        "recorded calibrant mysample is not available; kept LaB6"
    );
    assert_eq!(missing["state"]["calibration"]["calibrant"], "LaB6");
}

#[test]
fn poni_records_the_image_orientation_and_loading_restores_it() {
    let f = fixture();
    let mut s = prepared(&f);
    let picks = state(&mut s)["calibration"]["picks"].clone();
    let plain = f.temp.path().join("plain.poni");
    fs::write(&plain, PLAIN_PONI).unwrap();
    let view = |s: &mut Session| state(s)["calibration"]["transformations"].clone();

    // Three left turns are one right turn; the file names the view, not the clicks.
    for _ in 0..3 {
        call(
            &mut s,
            "image_transform",
            json!({"operation":"rotate_left"}),
        );
    }
    // A file without the note keeps the current view.
    let loaded = call(&mut s, "open_calibration", json!({"path":plain}));
    assert!(loaded.get("orientationNotice").is_none());
    assert_eq!(view(&mut s).as_array().unwrap().len(), 3);
    let rotated = f.temp.path().join("rotated.poni");
    call(&mut s, "save_calibration", json!({"path":rotated}));
    let text = fs::read_to_string(&rotated).unwrap();
    assert_eq!(
        text.matches("# Dioptas image orientation: rotate_right\n")
            .count(),
        1
    );

    // Loading it onto the untransformed image turns the view to match.
    call(&mut s, "image_transform", json!({"operation":"reset"}));
    call(&mut s, "load_peaks", json!({"path":f.peaks}));
    assert_eq!(view(&mut s), json!([]));
    let loaded = call(&mut s, "open_calibration", json!({"path":rotated}));
    assert_eq!(
        loaded["orientationNotice"],
        "image orientation rotate_right from file"
    );
    assert_eq!(view(&mut s), json!(["rotate_matrix_p90"]));
    // Picks belonged to the previous view; undo restores view and picks together.
    assert_eq!(loaded["state"]["calibration"]["picks"], json!([]));
    let undone = call(&mut s, "undo_calibration", json!({}));
    assert_eq!(undone["state"]["calibration"]["transformations"], json!([]));
    assert_eq!(undone["state"]["calibration"]["picks"], picks);

    // Saving without transforms records "none", which resets a rotated view.
    call(&mut s, "open_calibration", json!({"path":plain}));
    let upright = f.temp.path().join("upright.poni");
    call(&mut s, "save_calibration", json!({"path":upright}));
    assert!(
        fs::read_to_string(&upright)
            .unwrap()
            .contains("# Dioptas image orientation: none\n")
    );
    call(
        &mut s,
        "image_transform",
        json!({"operation":"flip_vertical"}),
    );
    let loaded = call(&mut s, "open_calibration", json!({"path":upright}));
    assert_eq!(
        loaded["orientationNotice"],
        "image orientation none from file"
    );
    assert_eq!(view(&mut s), json!([]));

    // Unknown names are reported and leave the view alone.
    let odd = f.temp.path().join("odd.poni");
    fs::write(
        &odd,
        format!("{PLAIN_PONI}# Dioptas image orientation: sideways\n"),
    )
    .unwrap();
    call(
        &mut s,
        "image_transform",
        json!({"operation":"flip_vertical"}),
    );
    let loaded = call(&mut s, "open_calibration", json!({"path":odd}));
    assert_eq!(
        loaded["orientationNotice"],
        "recorded image orientation sideways is unknown; kept the current view"
    );
    assert_eq!(view(&mut s), json!(["flipud"]));
}

#[test]
fn poni_orientation_waits_for_the_next_image_when_none_is_open() {
    let f = fixture();
    let rotated = f.temp.path().join("rotated.poni");
    fs::write(
        &rotated,
        format!("{PLAIN_PONI}# Dioptas image orientation: rotate_left\n"),
    )
    .unwrap();
    let mut s = Session::new(root());
    call(&mut s, "open_calibration", json!({"path":rotated}));
    // Undo and redo work before any image exists.
    let undone = call(&mut s, "undo_calibration", json!({}));
    assert_eq!(undone["state"]["calibration"]["transformations"], json!([]));
    call(&mut s, "redo_calibration", json!({}));
    call(&mut s, "open_image", json!({"path":f.image}));
    assert_eq!(
        state(&mut s)["calibration"]["transformations"],
        json!(["rotate_matrix_m90"])
    );
}

#[test]
fn plain_pixel_calibrations_save_the_row_flip_as_pyfai_orientation() {
    let f = fixture();
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":f.image}));
    call(
        &mut s,
        "manual_geometry",
        json!({"convention":"pyfai","values":{"dist":0.1,"poni1":0.004,"poni2":0.013,"rot1":0.05,"rot2":0.1,"rot3":0.02,"pixel1":0.0001,"pixel2":0.0001,"wavelength":3e-11,"polarization_factor":0.99}}),
    );
    let saved = f.temp.path().join("scratch.poni");
    call(&mut s, "save_calibration", json!({"path":saved}));
    // pyFAI counts rows top-down; Dioptas views them bottom-up. Orientation 2
    // tells pyFAI so, and its 2θ on the raw file then matches Dioptas.
    let text = fs::read_to_string(&saved).unwrap();
    assert!(text.contains("poni_version: 2.1\n"), "{text}");
    assert!(
        text.contains(r#""max_shape":[256,256],"orientation":2"#),
        "{text}"
    );
    let mut fresh = Session::new(root());
    call(&mut fresh, "open_image", json!({"path":f.image}));
    call(&mut fresh, "open_calibration", json!({"path":saved}));
    // Plain pixel sizes still apply to other image sizes, as before.
    let small = f.temp.path().join("small.npy");
    npy(&small, [64, 96], &vec![1.0; 64 * 96]);
    let mut other = Session::new(root());
    call(&mut other, "open_image", json!({"path":small}));
    call(&mut other, "open_calibration", json!({"path":saved}));
    assert_eq!(state(&mut other)["calibrated"], true);
    for (x, y) in [(5, 3), (200, 40), (17, 230)] {
        let pixel = json!({"x":x,"y":y,"source":"raw_detector"});
        assert_eq!(
            call(&mut s, "pixel", pixel.clone())["pixel"]["twoTheta"],
            call(&mut fresh, "pixel", pixel)["pixel"]["twoTheta"]
        );
    }
}

#[test]
fn recorded_rotation_on_a_non_square_image_rotates_instead_of_refusing() {
    let temp = tempfile::tempdir().unwrap();
    let image = temp.path().join("wide.npy");
    let values: Vec<f64> = (0..40 * 60).map(f64::from).collect();
    npy(&image, [40, 60], &values);
    // A detector definition sized for the rotated (60 × 40) view.
    let geometry = "poni_version: 2.1\nDetector: Detector\nDetector_config: {\"pixel1\": 0.0001, \"pixel2\": 0.0001, \"max_shape\": [60, 40], \"orientation\": 3}\nDistance: 0.1\nPoni1: 0.002\nPoni2: 0.003\nRot1: 0\nRot2: 0\nRot3: 0\nWavelength: 3e-11\n";
    let noted = temp.path().join("noted.poni");
    fs::write(
        &noted,
        format!("# Dioptas image orientation: rotate_right\n{geometry}"),
    )
    .unwrap();
    let bare = temp.path().join("bare.poni");
    fs::write(&bare, geometry).unwrap();

    // Without the note the 60 × 40 detector does not fit the 40 × 60 image.
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":image}));
    let refused = call(&mut s, "open_calibration", json!({"path":bare}));
    assert_eq!(refused["cancelled"], true);
    assert_eq!(refused["calibrationChange"]["imageShape"], json!([40, 60]));
    assert_eq!(state(&mut s)["calibrated"], false);

    // With the note the view turns first, so the detector fits.
    let loaded = call(&mut s, "open_calibration", json!({"path":noted}));
    assert!(loaded.get("cancelled").is_none(), "{loaded}");
    assert_eq!(
        loaded["orientationNotice"],
        "image orientation rotate_right from file"
    );
    let after = state(&mut s);
    assert_eq!(after["calibrated"], true);
    assert_eq!(
        after["calibration"]["transformations"],
        json!(["rotate_matrix_p90"])
    );
    let corner = call(
        &mut s,
        "pixel",
        json!({"x":39,"y":59,"source":"raw_detector"}),
    );
    assert!(corner["pixel"]["twoTheta"].is_number(), "{corner}");

    // Saving and reloading in a fresh session restores the same view and 2θ.
    let saved = temp.path().join("saved.poni");
    call(&mut s, "save_calibration", json!({"path":saved}));
    let mut fresh = Session::new(root());
    call(&mut fresh, "open_image", json!({"path":image}));
    let reloaded = call(&mut fresh, "open_calibration", json!({"path":saved}));
    assert!(reloaded.get("cancelled").is_none(), "{reloaded}");
    assert_eq!(
        state(&mut fresh)["calibration"]["transformations"],
        json!(["rotate_matrix_p90"])
    );
    for (x, y) in [(0, 0), (39, 59), (12, 31)] {
        let pixel = json!({"x":x,"y":y,"source":"raw_detector"});
        assert_eq!(
            call(&mut s, "pixel", pixel.clone())["pixel"],
            call(&mut fresh, "pixel", pixel)["pixel"]
        );
    }
}

#[cfg(feature = "dioptrin")]
#[test]
fn auto_calibrate_recovers_ceo2_and_lab6_without_manual_picks_and_supports_undo() {
    // 1. CeO2_Pilatus1M via the raw example setup (zero picked peaks).
    let mut s = Session::new(root());
    call(&mut s, "example", json!({}));
    assert_eq!(state(&mut s)["calibrated"], false);
    assert!(
        state(&mut s)["calibration"]["picks"]
            .as_array()
            .unwrap()
            .is_empty()
    );

    let reply = call(&mut s, "auto_calibrate", json!({}));
    assert_eq!(reply["state"]["calibrated"], true);
    let dist_mm = reply["state"]["geometry"]["dist"].as_f64().unwrap() * 1000.0;
    assert!(
        (dist_mm - 208.65).abs() < 1.0,
        "CeO2_Pilatus1M distance mismatch: {dist_mm} mm"
    );
    assert!(
        reply["state"]["calibration"]["rmsDegrees"]
            .as_f64()
            .unwrap()
            < 0.05
    );
    assert!(!reply["rings"].as_array().unwrap().is_empty());
    assert!(
        !reply["state"]["calibration"]["picks"]
            .as_array()
            .unwrap()
            .is_empty(),
        "auto_calibrate should populate matched ring peaks"
    );
    assert!(reply["pattern"]["x"].as_array().unwrap().len() > 100);

    // Undo restores the uncalibrated state; redo restores the auto-calibrated geometry.
    call(&mut s, "undo_calibration", json!({}));
    assert_eq!(state(&mut s)["calibrated"], false);
    call(&mut s, "redo_calibration", json!({}));
    assert_eq!(state(&mut s)["calibrated"], true);

    // 2. Non-converging auto-calibration returns a graceful notice without mutating state.
    let blank_dir = tempfile::tempdir().unwrap();
    let blank_path = blank_dir.path().join("blank.npy");
    npy(&blank_path, [64, 64], &[0.0; 64 * 64]);
    let mut s_blank = Session::new(root());
    call(&mut s_blank, "open_image", json!({"path": &blank_path}));
    let before_blank = state(&mut s_blank);
    let missed = call(&mut s_blank, "auto_calibrate", json!({}));
    assert_eq!(missed["autoCalibrateFailed"], true);
    assert!(
        missed["autoCalibrateNotice"]
            .as_str()
            .unwrap()
            .contains("Check wavelength, calibrant, and pixel sizes")
    );
    assert_eq!(state(&mut s_blank), before_blank);

    // 3. LaB6_40keV_MarCCD with zero manual picks.
    let mut s2 = Session::new(root());
    call(
        &mut s2,
        "open_image",
        json!({"path": root().join("tests/data/LaB6_40keV_MarCCD.tif")}),
    );
    call(
        &mut s2,
        "calibration_setup",
        json!({"calibrant": "LaB6", "pixel_x": 79.0, "pixel_y": 79.0}),
    );
    let reply2 = call(
        &mut s2,
        "auto_calibrate",
        json!({
            "parameters": {
                "dist": {"value": 200.0, "refine": true},
                "wavelength": {"value": 0.31, "refine": false}
            }
        }),
    );
    assert_eq!(reply2["state"]["calibrated"], true);
    let dist2_mm = reply2["state"]["geometry"]["dist"].as_f64().unwrap() * 1000.0;
    assert!(
        (dist2_mm - 196.7).abs() < 1.0,
        "LaB6_40keV_MarCCD distance mismatch: {dist2_mm} mm"
    );
    assert!(
        reply2["state"]["calibration"]["rmsDegrees"]
            .as_f64()
            .unwrap()
            < 0.05
    );

    // 4. LaB6_40keV_MarCCD at the wrong default wavelength (0.3344 Å instead of 0.31 Å)
    //    flags a wavelengthHint suggesting ~0.31 Å (~40 keV).
    let mut s3 = Session::new(root());
    call(
        &mut s3,
        "open_image",
        json!({"path": root().join("tests/data/LaB6_40keV_MarCCD.tif")}),
    );
    call(
        &mut s3,
        "calibration_setup",
        json!({"calibrant": "LaB6", "pixel_x": 79.0, "pixel_y": 79.0}),
    );
    let wrong_wl = call(
        &mut s3,
        "auto_calibrate",
        json!({
            "parameters": {
                "dist": {"value": 200.0, "refine": true},
                "wavelength": {"value": 0.3344, "refine": false}
            }
        }),
    );
    assert_eq!(wrong_wl["state"]["calibrated"], true);
    let hint = &wrong_wl["wavelengthHint"];
    assert!(
        hint.is_object(),
        "expected wavelengthHint when wavelength is off by 7%: {wrong_wl}"
    );
    let suggested = hint["suggestedWavelength"].as_f64().unwrap();
    assert!(
        (suggested - 0.31).abs() < 0.015,
        "expected suggested wavelength near 0.31 Å, got {suggested}"
    );
    assert!(
        hint["suggestedRmsDegrees"].as_f64().unwrap() < hint["currentRmsDegrees"].as_f64().unwrap()
    );
}

#[cfg(feature = "dioptrin")]
#[test]
fn automatic_massif_refinement_handles_circular_zero_corner_detector_and_free_wavelength() {
    // 1. LaB6_40keV_MarCCD.tif has large zero-valued corners outside the active
    //    circle; automatic Massif search must still find rings across the image.
    let mut s = Session::new(root());
    call(
        &mut s,
        "open_image",
        json!({
            "path": root().join("tests/data/LaB6_40keV_MarCCD.tif"),
            "frame": 0,
            "reset_calibration": true
        }),
    );
    call(
        &mut s,
        "pick_peak",
        json!({"x": 1209.6, "y": 1043.2, "ring": 1, "automatic": true}),
    );
    call(
        &mut s,
        "pick_peak",
        json!({"x": 1288.0, "y": 1067.3, "ring": 2, "automatic": true}),
    );
    let fitted = call(
        &mut s,
        "calibrate",
        json!({
            "parameters": {
                "dist": {"value": 200.0, "refine": true},
                "poni1": {"value": 0.0, "refine": true},
                "poni2": {"value": 0.0, "refine": true},
                "rot1": {"value": 0.0, "refine": true},
                "rot2": {"value": 0.0, "refine": true},
                "rot3": {"value": 0.0, "refine": true},
                "wavelength": {"value": 0.31, "refine": false}
            },
            "polarization": 0.99,
            "restart": true,
            "automatic": true
        }),
    );
    assert!(
        fitted["state"]["calibration"]["picks"]
            .as_array()
            .unwrap()
            .len()
            >= 10
    );
    assert!(
        fitted["state"]["calibration"]["rmsDegrees"]
            .as_f64()
            .unwrap()
            < 0.05
    );
    let mar_rot3 = fitted["state"]["geometry"]["rot3"].as_f64().unwrap();
    assert!(
        mar_rot3.is_finite() && mar_rot3.abs() <= std::f64::consts::FRAC_PI_2 + 1e-6,
        "unexpected rot3: {mar_rot3}"
    );

    // 2. Free wavelength with rot3 checked must not hit a singular normal matrix
    //    or reset the fitted wavelength between staged automatic ring refits.
    let mut pe = Session::new(root());
    call(
        &mut pe,
        "open_image",
        json!({
            "path": root().join("tests/data/LaB6_OffCenter_PE.tif"),
            "frame": 0,
            "reset_calibration": true
        }),
    );
    call(
        &mut pe,
        "pick_peak",
        json!({"x": 1936.6, "y": 1199.3, "ring": 1, "automatic": true}),
    );
    call(
        &mut pe,
        "pick_peak",
        json!({"x": 1872.3, "y": 1156.3, "ring": 2, "automatic": true}),
    );
    let pe_fit = call(
        &mut pe,
        "calibrate",
        json!({
            "parameters": {
                "dist": {"value": 179.3840618847747, "refine": true},
                "poni1": {"value": 103.88909961110059, "refine": true},
                "poni2": {"value": 190.96659985735545, "refine": true},
                "rot1": {"value": 0.09892603519374353, "refine": true},
                "rot2": {"value": -0.0011249765124669952, "refine": true},
                "rot3": {"value": 0.6273962123849444, "refine": true},
                "wavelength": {"value": 0.28457, "refine": true}
            },
            "polarization": 0.99,
            "restart": true,
            "automatic": true
        }),
    );
    assert!(
        pe_fit["state"]["calibration"]["picks"]
            .as_array()
            .unwrap()
            .len()
            >= 5
    );
    assert!(
        pe_fit["state"]["calibration"]["rmsDegrees"]
            .as_f64()
            .unwrap()
            < 0.05
    );
    let pe_rot3 = pe_fit["state"]["geometry"]["rot3"].as_f64().unwrap();
    assert!(
        pe_rot3.is_finite() && pe_rot3.abs() <= std::f64::consts::FRAC_PI_2 + 1e-6,
        "unexpected rot3: {pe_rot3}"
    );
}

#[test]
fn builtin_calibrant_intensities_and_cif_calibrant_loading_work() {
    let mut s = Session::new(root());
    // Default LaB6 has PhaseSmith-computed reflection intensities and phase-style lineWidth/opacity.
    let lab6_rings = state(&mut s)["calibration"]["rings"]
        .as_array()
        .unwrap()
        .clone();
    assert!(!lab6_rings.is_empty());
    assert!(lab6_rings[0]["intensity"].as_f64().is_some());
    assert!(lab6_rings[0]["lineWidth"].as_f64().unwrap() >= 1.0);
    assert!(lab6_rings[0]["opacity"].as_f64().unwrap() >= 0.3);
    let lab6_lines = state(&mut s)["calibration"]["referenceLines"]
        .as_array()
        .unwrap()
        .clone();
    assert!(lab6_lines[0]["intensity"].as_f64().is_some());

    // Built-in CeO2 extends beyond the 41 spacings in CeO2.D down to 0.35 Å via PhaseSmith.
    call(&mut s, "calibration_setup", json!({"calibrant": "CeO2"}));
    let ceo2_rings = state(&mut s)["calibration"]["rings"]
        .as_array()
        .unwrap()
        .clone();
    assert!(
        ceo2_rings.len() > 100,
        "expected >100 CeO2 rings via PhaseSmith extension, got {}",
        ceo2_rings.len()
    );

    // Organic .D-only calibrant (AgBh) has no built-in crystal structure -> uniform lines.
    call(&mut s, "calibration_setup", json!({"calibrant": "AgBh"}));
    let agbh_rings = state(&mut s)["calibration"]["rings"]
        .as_array()
        .unwrap()
        .clone();
    assert!(!agbh_rings.is_empty());
    assert!(agbh_rings[0].get("intensity").is_none());
    assert!(agbh_rings[0].get("lineWidth").is_none());

    // Loading a .cif file as a custom calibrant computes d-spacings and intensities via PhaseSmith.
    let temp = tempfile::tempdir().unwrap();
    let cif_path = temp.path().join("ceo2_test.cif");
    fs::write(
        &cif_path,
        r#"data_CeO2
_cell_length_a 5.411651
_cell_length_b 5.411651
_cell_length_c 5.411651
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_space_group_name_H-M_alt 'F m -3 m'
_space_group_IT_number 225
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Ce1 Ce 0 0 0 1
O1 O 0.25 0.25 0.25 1
"#,
    )
    .unwrap();
    let loaded = call(&mut s, "open_calibrant", json!({"path": &cif_path}));
    assert_eq!(
        loaded["state"]["calibration"]["calibrant"],
        "ceo2_test (custom)"
    );
    let cif_rings = loaded["state"]["calibration"]["rings"].as_array().unwrap();
    assert!(cif_rings.len() >= 10);
    assert!(cif_rings[0]["intensity"].as_f64().unwrap() > 0.0);
    assert!(cif_rings[0]["lineWidth"].as_f64().unwrap() > 1.0);
    let cif_lines = loaded["state"]["calibration"]["referenceLines"]
        .as_array()
        .unwrap();
    assert!(cif_lines[0]["intensity"].as_f64().unwrap() > 0.0);
}

#[cfg(feature = "dioptrin")]
#[test]
fn refine_from_image_refines_perturbed_geometry_with_zero_manual_picks() {
    let mut s = Session::new(root());
    call(&mut s, "example", json!({}));
    // Apply a slightly perturbed initial geometry (off by ~2 mm in distance and ~0.5 mm in poni)
    // with zero manual picks.
    call(
        &mut s,
        "manual_geometry",
        json!({
            "convention": "pyfai",
            "values": {
                "dist": 0.2065,
                "poni1": 0.0878,
                "poni2": 0.0805,
                "rot1": -0.015,
                "rot2": 0.002,
                "rot3": 0.0,
                "pixel1": 0.000172,
                "pixel2": 0.000172,
                "wavelength": 4.06626e-11,
                "polarization_factor": 0.99
            }
        }),
    );
    assert!(
        state(&mut s)["calibration"]["picks"]
            .as_array()
            .unwrap()
            .is_empty()
    );

    let refined = call(
        &mut s,
        "calibrate",
        json!({
            "restart": false,
            "from_image": true
        }),
    );
    assert_eq!(refined["state"]["calibrated"], true);
    let dist_mm = refined["state"]["geometry"]["dist"].as_f64().unwrap() * 1000.0;
    assert!(
        (dist_mm - 208.65).abs() < 1.0,
        "refine_image distance mismatch: {dist_mm} mm"
    );
    assert!(
        refined["state"]["calibration"]["rmsDegrees"]
            .as_f64()
            .unwrap()
            < 0.05
    );
    assert!(
        !refined["state"]["calibration"]["picks"]
            .as_array()
            .unwrap()
            .is_empty(),
        "refine_image should populate matched ring peaks"
    );

    // Changing a fixed start parameter (wavelength) and refining from image must
    // honor the new fixed value instead of snapping back to the old geometry.
    let shifted_wavelength = 0.41;
    let refined_shifted = call(
        &mut s,
        "calibrate",
        json!({
            "restart": false,
            "from_image": true,
            "parameters": {
                "wavelength": {"value": shifted_wavelength, "refine": false}
            }
        }),
    );
    let fitted_wl = refined_shifted["state"]["geometry"]["wavelength"]
        .as_f64()
        .unwrap()
        * 1e10;
    assert!(
        (fitted_wl - shifted_wavelength).abs() < 1e-6,
        "expected fixed wavelength {shifted_wavelength}, got {fitted_wl}"
    );

    // rot3 remains locked during calibration/refinement, and estimate_rot3 runs
    // polarization-based rot3 estimation on demand.
    assert_eq!(refined_shifted["state"]["geometry"]["rot3"], 0.0);
    let est = call(&mut s, "estimate_rot3", json!({"polarization": 0.99}));
    assert!(
        est["rot3Notice"].as_str().is_some(),
        "expected rot3Notice in reply: {est}"
    );
    let zero_pol = s
        .invoke(&request("estimate_rot3", json!({"polarization": 0.0})))
        .result;
    assert_eq!(zero_pol["ok"], false);
}

#[cfg(feature = "dioptrin")]
#[test]
fn estimate_apply_and_save_distortion_works_across_single_and_multi_configurations() {
    let mut s = Session::new(root());
    call(&mut s, "example", json!({}));
    call(&mut s, "auto_calibrate", json!({}));

    // Add a second configuration with the same detector image & calibrate it too
    // to exercise multi-configuration joint distortion estimation.
    call(&mut s, "configuration", json!({"operation": "add"}));
    call(&mut s, "example", json!({}));
    call(&mut s, "auto_calibrate", json!({}));

    let est = call(
        &mut s,
        "estimate_distortion",
        json!({
            "configurations": [0, 1],
            "model": "smooth_spline",
            "grid_nx": 6,
            "grid_ny": 6,
            "n_passes": 2,
            "cv_folds": 3
        }),
    );
    let preview = &est["distortionPreview"];
    assert_eq!(preview["model"], "smooth_spline");
    assert_eq!(preview["canSaveSpline"], true);
    assert_eq!(preview["exposures"].as_array().unwrap().len(), 2);
    assert_eq!(preview["grid"].as_array().unwrap().len(), 17 * 17);
    assert!(preview["rmsAfterPx"].as_f64().unwrap().is_finite());

    let applied = call(&mut s, "apply_distortion", json!({}));
    assert!(
        applied["distortionNotice"]
            .as_str()
            .unwrap()
            .contains("2 configurations")
    );
    assert!(
        applied["state"]["calibration"]["distortionFile"]
            .as_str()
            .unwrap()
            .contains("Smooth B-spline")
    );

    let temp = tempfile::tempdir().unwrap();
    let spline_path = temp.path().join("estimated.spline");
    let saved = call(
        &mut s,
        "save_distortion",
        json!({"path": &spline_path, "format": "spline"}),
    );
    assert_eq!(saved["savedPath"], spline_path.to_string_lossy().as_ref());
    let text = fs::read_to_string(&spline_path).unwrap();
    assert!(text.contains("VALID REGION"), "{text}");

    // Switching back to configuration 0 also carries the saved distortion file path.
    call(
        &mut s,
        "configuration",
        json!({"operation": "select", "index": 0}),
    );
    assert!(
        state(&mut s)["calibration"]["distortionFile"]
            .as_str()
            .unwrap()
            .ends_with("estimated.spline")
    );
}

#[test]
fn detect_detector_modules_finds_pilatus_gaps_and_rejects_flat_ccd() {
    let mut s = Session::new(root());
    call(
        &mut s,
        "open_image",
        json!({"path": root().join("tests/data/CeO2_Pilatus1M.tif")}),
    );
    let detected = call(&mut s, "detect_detector_modules", json!({}));
    assert_eq!(detected["detectedModules"]["detected"], true);
    assert_eq!(detected["detectedModules"]["moduleHeight"], 195);
    assert_eq!(detected["detectedModules"]["moduleWidth"], 487);
    assert_eq!(detected["detectedModules"]["gapHeight"], 17);
    assert_eq!(detected["detectedModules"]["gapWidth"], 7);
    assert_eq!(detected["detectedModules"]["moduleRows"], 5);
    assert_eq!(detected["detectedModules"]["moduleCols"], 2);

    // Rotating the image by 90 degrees transposes the detected module dimensions.
    call(
        &mut s,
        "image_transform",
        json!({"operation": "rotate_right"}),
    );
    let rotated = call(&mut s, "detect_detector_modules", json!({}));
    assert_eq!(rotated["detectedModules"]["detected"], true);
    assert_eq!(rotated["detectedModules"]["moduleHeight"], 487);
    assert_eq!(rotated["detectedModules"]["moduleWidth"], 195);
    assert_eq!(rotated["detectedModules"]["gapHeight"], 7);
    assert_eq!(rotated["detectedModules"]["gapWidth"], 17);
    assert_eq!(rotated["detectedModules"]["moduleRows"], 2);
    assert_eq!(rotated["detectedModules"]["moduleCols"], 5);

    // A circular non-tiled MAR CCD detector must not falsely detect modules.
    let mut s_ccd = Session::new(root());
    call(
        &mut s_ccd,
        "open_image",
        json!({"path": root().join("tests/data/LaB6_40keV_MarCCD.tif")}),
    );
    let flat = call(&mut s_ccd, "detect_detector_modules", json!({}));
    assert_eq!(flat["detectedModules"]["detected"], false, "{flat}");
}

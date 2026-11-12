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
    let text = fs::read_to_string(root().join("resources/calibrants/CeO2.D")).unwrap();
    let spacings: Vec<f64> = text
        .lines()
        .filter_map(|l| l.split('#').next().unwrap().split_whitespace().next())
        .map(|v| v.parse().unwrap())
        .collect();
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
    assert_eq!(fitted["state"]["geometry"]["rot3"], 0.0);
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
    let f = fixture();
    for algorithm in ["Massif", "Blob"] {
        let mut s = prepared(&f);
        call(
            &mut s,
            "workflow_settings",
            json!({"algorithm":algorithm,"numberOfRings":4,"deltaTth":0.3,"meanFactor":1.0,"intensityLimit":10000}),
        );
        let fitted = call(&mut s, "calibrate", json!({"automatic":true}));
        assert!(
            fitted["state"]["calibration"]["picks"]
                .as_array()
                .unwrap()
                .len()
                >= 3,
            "{algorithm}: {}",
            fitted["state"]["calibration"]
        );
        assert!(
            fitted["state"]["calibration"]["rmsDegrees"]
                .as_f64()
                .unwrap()
                < 0.05,
            "{algorithm}: rms {}",
            fitted["state"]["calibration"]["rmsDegrees"]
        );
        call(
            &mut s,
            "workflow_settings",
            json!({"intensityLimit":0.00001}),
        );
        let before = state(&mut s);
        let product = call(&mut s, "state", json!({}))["pattern"].clone();
        let result = s
            .invoke(&request(
                "calibrate",
                json!({"automatic":true,"restart":true}),
            ))
            .result;
        assert_eq!(result["ok"], false);
        assert!(result["error"].as_str().unwrap().contains("restored"));
        let after = state(&mut s);
        assert_eq!(after["geometry"], before["geometry"]);
        assert_eq!(after["calibration"], before["calibration"]);
        assert_eq!(call(&mut s, "state", json!({}))["pattern"], product);
    }
}

#[cfg(feature = "dioptrin")]
#[test]
fn live_progress_is_detached_and_cancellation_restores_geometry_picks_and_history() {
    let f = fixture();
    let image = f.image.clone();
    let peaks = f.peaks.clone();
    let control = Arc::new(Control::default());
    let worker_control = control.clone();
    let worker = std::thread::spawn(move || {
        let local = Fixture {
            temp: tempfile::tempdir().unwrap(),
            image,
            peaks,
            groups: Value::Null,
        };
        let mut s = prepared(&local);
        call(&mut s, "calibrate", json!({"automatic":false}));
        call(
            &mut s,
            "workflow_settings",
            json!({"algorithm":"Blob","numberOfRings":5,"deltaTth":0.3,"meanFactor":1.0}),
        );
        let before = state(&mut s);
        let products = call(&mut s, "state", json!({}));
        let result = s
            .invoke_controlled(
                &request("calibrate", json!({"automatic":true})),
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
        if p["label"] == "Preparing peak search" {
            observed = Some(p);
            break;
        }
        if worker.is_finished() {
            break;
        }
        std::thread::sleep(Duration::from_millis(1));
    }
    let preview = observed.expect("live preparing-ring progress");
    assert!(
        preview["calibration"]["picks"]
            .as_array()
            .unwrap()
            .is_empty()
    );
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

use dioptas_backend::{
    Session,
    image::Image,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_owned()
}
fn request(action: &str, payload: Value) -> Request {
    Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    }
}
fn call(session: &mut Session, action: &str, payload: Value) -> Reply {
    let reply = session.invoke(&request(action, payload));
    assert_eq!(reply.result["ok"], true, "{}", reply.result);
    reply
}
fn npy(path: &Path, shape: &[usize], values: &[f64]) {
    let dimensions = shape
        .iter()
        .map(usize::to_string)
        .collect::<Vec<_>>()
        .join(", ");
    let mut header =
        format!("{{'descr': '<f8', 'fortran_order': False, 'shape': ({dimensions},), }}");
    while (10 + header.len() + 1) % 64 != 0 {
        header.push(' ');
    }
    header.push('\n');
    let mut bytes = b"\x93NUMPY\x01\x00".to_vec();
    bytes.extend_from_slice(&(header.len() as u16).to_le_bytes());
    bytes.extend_from_slice(header.as_bytes());
    for value in values {
        bytes.extend_from_slice(&value.to_le_bytes());
    }
    fs::write(path, bytes).unwrap();
}
fn small_image() -> (tempfile::TempDir, PathBuf) {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("counts.npy");
    npy(&path, &[3, 4], &(0..12).map(f64::from).collect::<Vec<_>>());
    (temp, path)
}
fn header(reply: &Reply, known: &[String]) -> (Value, Vec<u8>) {
    let packet = reply.encode(7, known).unwrap();
    let length = u32::from_le_bytes(packet[..4].try_into().unwrap()) as usize;
    (
        serde_json::from_slice(&packet[4..4 + length]).unwrap(),
        packet[4 + length..].to_vec(),
    )
}

#[test]
fn original_samples_stay_in_stored_order_and_scientific_rows_flip_once() {
    let (_temp, path) = small_image();
    let image = Image::open(&path, &json!({})).unwrap();
    assert_eq!(
        *image.values,
        vec![8., 9., 10., 11., 4., 5., 6., 7., 0., 1., 2., 3.]
    );
    assert_eq!(
        image.original_pixels(),
        &dioptrin_io::PixelBuffer::F64((0..12).map(f64::from).collect())
    );
    let mut session = Session::new(root());
    let opened = call(&mut session, "open_image", json!({"path":path}));
    assert_eq!(opened.result["state"]["shape"], json!([3, 4]));
    assert_eq!(
        call(&mut session, "pixel", json!({"x":0,"y":0})).result["pixel"]["value"],
        8.0
    );
    assert_eq!(
        call(&mut session, "pixel", json!({"x":3,"y":2})).result["pixel"]["value"],
        3.0
    );
}

#[test]
fn actual_tiff_fixture_has_original_full_resolution() {
    let mut session = Session::new(root());
    let reply = call(&mut session, "example", json!({}));
    assert_eq!(reply.result["state"]["shape"], json!([1043, 981]));
    assert_eq!(reply.result["state"]["calibrated"], false);
    assert_eq!(reply.result["image"]["step"], 1);
    assert_eq!(
        reply.result["image"]["histogram"]["finitePixels"],
        1043 * 981
    );
    assert_eq!(reply.result["nativeSource"]["dtype"], "I32");
}

#[test]
#[cfg(feature = "dioptrin")]
fn packaged_resources_support_example_integration_and_project_without_a_checkout() {
    let directory = tempfile::tempdir().unwrap();
    let resources = directory.path().join("resources with spaces");
    fs::create_dir_all(resources.join("examples")).unwrap();
    for name in ["CeO2_Pilatus1M.tif", "CeO2_Pilatus1M.poni"] {
        fs::copy(
            root().join("dioptas/tests/data").join(name),
            resources.join("examples").join(name),
        )
        .unwrap();
    }
    let mut session = Session::new(resources.clone());
    let example = call(&mut session, "example", json!({}));
    assert_eq!(example.result["state"]["exampleAvailable"], true);
    assert_eq!(example.result["state"]["calibrated"], false);
    assert!(
        example.result["state"]["imagePath"]
            .as_str()
            .unwrap()
            .starts_with(resources.canonicalize().unwrap().to_str().unwrap())
    );
    assert!(
        example.result["state"]["calibration"]["calibrants"]
            .as_array()
            .unwrap()
            .len()
            > 10
    );
    call(
        &mut session,
        "integration_settings",
        json!({"bins":128,"cake_bins":36}),
    );
    call(
        &mut session,
        "open_calibration",
        json!({"path":resources.join("examples/CeO2_Pilatus1M.poni")}),
    );
    let integrated = call(&mut session, "integrate", json!({}));
    assert_eq!(
        integrated.result["pattern"]["x"].as_array().unwrap().len(),
        128
    );
    fs::write(resources.join("RESOURCE_MANIFEST.json"), "{}").unwrap();
    call(
        &mut session,
        "integration_autocreate",
        json!({"enabled":true}),
    );
    let refused = session.invoke(&request("integrate", json!({})));
    assert_eq!(refused.result["ok"], false);
    assert!(
        refused.result["error"]
            .as_str()
            .unwrap()
            .contains("outside the application")
    );
    assert!(!resources.join("examples/CeO2_Pilatus1M.xy").exists());
    call(
        &mut session,
        "integration_output_directory",
        json!({"path":directory.path()}),
    );
    call(&mut session, "integrate", json!({}));
    assert!(directory.path().join("CeO2_Pilatus1M.xy").is_file());
    call(
        &mut session,
        "integration_autocreate",
        json!({"enabled":false}),
    );
    let project = directory.path().join("owned.dio");
    call(&mut session, "save_project", json!({"path":project}));
    fs::remove_dir_all(&resources).unwrap();
    let restored = call(&mut session, "open_project", json!({"path":project}));
    assert_eq!(restored.result["state"]["shape"], json!([1043, 981]));
    assert_eq!(restored.result["state"]["exampleAvailable"], false);
    assert_eq!(
        restored.result["pattern"]["y"],
        integrated.result["pattern"]["y"]
    );
}

#[test]
fn detached_phase_refresh_preserves_detector_buffers_and_revision() {
    let mut session = Session::new(root());
    call(&mut session, "example", json!({}));
    call(
        &mut session,
        "integration_phase",
        json!({
            "operation":"load", "path":root().join("dioptas/tests/data/jcpds/mo.jcpds")
        }),
    );
    call(
        &mut session,
        "integration_phase",
        json!({
            "operation":"update", "index":0, "pressure":10.
        }),
    );
    let before = call(&mut session, "state", json!({}));
    let refreshed = call(&mut session, "integration_phase_state", json!({}));
    assert_eq!(refreshed.result["phaseOnly"], true);
    assert_eq!(refreshed.result["patternOnly"], true);
    assert_eq!(refreshed.result["state"], before.result["state"]);
    assert_eq!(
        refreshed.result["state"]["integration"]["phases"][0]["pressure"],
        10.
    );
    assert!(
        !refreshed.result["batchPhaseLines"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    assert!(refreshed.buffers.is_empty());
    for key in [
        "image", "rawImage", "mask", "cake", "rings", "linked", "batch", "map",
    ] {
        assert!(
            refreshed.result.get(key).is_none(),
            "Unexpected replacement of {key}"
        );
    }
}

#[test]
fn native_hdf5_stack_retains_integer_dtype_and_tracks_selected_frame() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("scan.h5");
    {
        let file = hdf5::File::create(&path).unwrap();
        file.new_dataset::<u16>()
            .shape([2, 3, 4])
            .create("counts")
            .unwrap()
            .write_raw(&(0..24_u16).collect::<Vec<_>>())
            .unwrap();
    }
    let mut session = Session::new(root());
    let first = call(
        &mut session,
        "open_image",
        json!({"path":path,"dataset":"/counts"}),
    );
    assert_eq!(first.result["nativeSource"]["dtype"], "U16");
    assert_eq!(first.result["state"]["integration"]["frames"], 2);
    let next = call(&mut session, "next_image", json!({"direction":1}));
    assert_ne!(
        first.result["image"]["bufferId"],
        next.result["image"]["bufferId"]
    );
    assert_eq!(
        call(&mut session, "pixel", json!({"x":0,"y":0})).result["pixel"]["value"],
        20.0
    );
    let before = call(&mut session, "state", json!({}));
    let end = call(&mut session, "next_image", json!({"direction":1}));
    assert_eq!(end.result, json!({"ok":true,"imageUnavailable":true}));
    assert!(end.buffers.is_empty());
    assert_eq!(call(&mut session, "state", json!({})).result, before.result);
    let back = call(&mut session, "next_image", json!({"direction":-1}));
    assert_eq!(
        first.result["image"]["bufferId"],
        back.result["image"]["bufferId"]
    );
}

#[test]
fn image_file_boundaries_are_noops_and_later_arrivals_remain_browsable() {
    for mode in ["number", "time"] {
        let temp = tempfile::tempdir().unwrap();
        let directory = temp.path().canonicalize().unwrap();
        let first = directory.join("scan_001.npy");
        npy(&first, &[3, 4], &[1.; 12]);
        let mut session = Session::new(root());
        call(&mut session, "open_image", json!({"path":first}));
        call(&mut session, "integration_navigation", json!({"mode":mode}));
        call(
            &mut session,
            "mask_stroke",
            json!({"points":[[1,1]],"radius":1}),
        );
        let before = call(&mut session, "state", json!({}));
        for direction in [-1, 1, 1] {
            let end = call(&mut session, "next_image", json!({"direction":direction}));
            assert_eq!(
                end.result,
                json!({"ok":true,"imageUnavailable":true}),
                "{mode}"
            );
            assert!(end.buffers.is_empty());
            assert_eq!(call(&mut session, "state", json!({})).result, before.result);
        }
        let second = directory.join("scan_002.npy");
        npy(&second, &[3, 4], &[2.; 12]);
        let next = call(&mut session, "next_image", json!({"direction":1}));
        assert_eq!(next.result["state"]["imagePath"], json!(second));
        assert_ne!(
            next.result["image"]["bufferId"],
            before.result["image"]["bufferId"]
        );
        assert_eq!(
            next.result["state"]["maskedPixels"],
            before.result["state"]["maskedPixels"]
        );
        let end = call(&mut session, "next_image", json!({"direction":1,"step":2}));
        assert_eq!(end.result, json!({"ok":true,"imageUnavailable":true}));
        assert_eq!(call(&mut session, "state", json!({})).result, next.result);
        let back = call(&mut session, "next_image", json!({"direction":-1}));
        assert_eq!(back.result["state"]["imagePath"], json!(first));
        // An existing but unreadable neighbor is still a real loading error.
        let before_failure = call(&mut session, "state", json!({}));
        fs::write(&second, b"incomplete acquisition").unwrap();
        let failed = session.invoke(&request("next_image", json!({"direction":1})));
        assert_eq!(failed.result["ok"], false);
        assert_eq!(
            call(&mut session, "state", json!({})).result,
            before_failure.result
        );
    }
}

#[test]
fn uncalibrated_frame_shape_changes_reset_coordinates_even_with_the_same_number_of_pixels() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("different-shapes.tif");
    {
        let file = fs::File::create(&path).unwrap();
        let mut encoder = tiff::encoder::TiffEncoder::new(file).unwrap();
        encoder
            .write_image::<tiff::encoder::colortype::Gray16>(4, 3, &[1; 12])
            .unwrap();
        encoder
            .write_image::<tiff::encoder::colortype::Gray16>(3, 4, &[2; 12])
            .unwrap();
    }
    let mut session = Session::new(root());
    call(&mut session, "open_image", json!({"path":path}));
    call(
        &mut session,
        "mask_stroke",
        json!({"points":[[1,1]],"radius":1}),
    );
    let before = call(&mut session, "state", json!({}));
    let pending = call(&mut session, "next_image", json!({"direction":1}));
    assert_eq!(pending.result["imageChange"]["calibrated"], false);
    assert_eq!(call(&mut session, "state", json!({})).result, before.result);
    let next = call(
        &mut session,
        "open_image",
        json!({"path":path,"frame":1,"reset_image_state":true}),
    );
    assert!(next.result.get("imageChange").is_none());
    assert!(next.result.get("calibrationReset").is_none());
    assert_eq!(next.result["state"]["shape"], json!([4, 3]));
    assert_eq!(next.result["mask"]["width"], 3);
    assert_eq!(next.result["mask"]["height"], 4);
    assert_eq!(next.result["state"]["maskedPixels"], 0);
    assert_eq!(next.result["state"]["canUndoMask"], false);
}

#[test]
fn failed_open_and_changed_source_keep_the_preceding_frame() {
    let (temp, path) = small_image();
    let mut session = Session::new(root());
    let first = call(&mut session, "open_image", json!({"path":path}));
    assert_eq!(
        session
            .invoke(&request(
                "open_image",
                json!({"path":temp.path().join("absent")})
            ))
            .result["ok"],
        false
    );
    assert_eq!(
        call(&mut session, "state", json!({})).result["image"],
        first.result["image"]
    );
    let mut image = Image::open(&path, &json!({})).unwrap();
    fs::write(&path, b"changed").unwrap();
    assert!(image.read(0).is_err());
    assert_eq!(image.values[0], 8.0);
}

#[test]
fn packets_deduplicate_raw_image_and_only_omit_advertised_buffers() {
    let (_temp, path) = small_image();
    let mut session = Session::new(root());
    let reply = call(&mut session, "open_image", json!({"path":path}));
    let (first, bytes) = header(&reply, &[]);
    assert_eq!(first["id"], 7);
    assert_eq!(first["buffers"].as_array().unwrap().len(), 2);
    assert_eq!(bytes.len(), 12 * 4 + 12);
    assert!(first["result"]["image"].get("data").is_none());
    let known = first["buffers"]
        .as_array()
        .unwrap()
        .iter()
        .map(|b| b["id"].as_str().unwrap().to_owned())
        .collect::<Vec<_>>();
    let (cached, bytes) = header(&reply, &known);
    assert_eq!(cached["buffers"], json!([]));
    assert!(bytes.is_empty());
    let (forgotten, bytes) = header(&reply, &known[..1]);
    assert_eq!(forgotten["buffers"].as_array().unwrap().len(), 1);
    assert!(!bytes.is_empty());
}

#[test]
fn histogram_and_levels_use_original_precision_and_every_finite_sample() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("precision.npy");
    npy(
        &path,
        &[2, 3],
        &[16_777_216., 16_777_217., f64::NAN, -7., f64::INFINITY, 0.],
    );
    let mut session = Session::new(root());
    let reply = call(&mut session, "open_image", json!({"path":path}));
    let histogram = &reply.result["image"]["histogram"];
    assert_eq!(histogram["finitePixels"], 4);
    assert_eq!(
        histogram["counts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_u64().unwrap())
            .sum::<u64>(),
        4
    );
    let limits = call(
        &mut session,
        "image_levels",
        json!({"mode":"minmax","filter_gaps":false}),
    );
    assert_eq!(limits.result["levels"], json!([-7.0, 16_777_217.0]));
    assert_eq!(
        call(
            &mut session,
            "image_levels",
            json!({"source":"raw_detector","mode":"minmax","filter_gaps":false})
        )
        .result["levels"],
        limits.result["levels"]
    );
}

#[test]
fn mask_edits_are_original_resolution_and_undo_restores_content_identity() {
    let (_temp, path) = small_image();
    let mut session = Session::new(root());
    let initial = call(&mut session, "open_image", json!({"path":path}));
    let masked = call(
        &mut session,
        "mask_stroke",
        json!({"points":[[1,1]],"radius":1}),
    );
    assert_eq!(masked.result["state"]["maskedPixels"], 5);
    let failed = session.invoke(&request(
        "mask_stroke",
        json!({"points":[[0,0],[99,0]],"radius":1}),
    ));
    assert_eq!(failed.result["ok"], false);
    assert_eq!(
        call(&mut session, "state", json!({})).result["mask"],
        masked.result["mask"]
    );
    let undone = call(&mut session, "undo_mask", json!({}));
    assert_eq!(undone.result["mask"], initial.result["mask"]);
    assert_eq!(
        call(&mut session, "redo_mask", json!({})).result["mask"],
        masked.result["mask"]
    );
}

#[test]
fn unsupported_geometry_and_options_fail_without_publishing_partial_changes() {
    let temp = tempfile::tempdir().unwrap();
    let mut session = Session::new(root());
    let initial = call(&mut session, "state", json!({}));
    let poni = fs::read_to_string(root().join("dioptas/tests/data/CeO2_Pilatus1M.poni")).unwrap();
    for contents in [
        poni.replace("SplineFile: None", "SplineFile: correction.spline"),
        format!("{poni}\nDetector: UnavailableModel\n"),
        format!(
            "{poni}\nDetector_config: {{\"pixel1\": 0.000172, \"pixel2\": 0.000172, \"orientation\": 8}}\n"
        ),
    ] {
        let path = temp.path().join("unsupported.poni");
        fs::write(&path, contents).unwrap();
        assert_eq!(
            session
                .invoke(&request("open_calibration", json!({"path":path})))
                .result["ok"],
            false
        );
        assert_eq!(
            call(&mut session, "state", json!({})).result["state"]["geometry"],
            initial.result["state"]["geometry"]
        );
    }
    assert_eq!(
        session
            .invoke(&request(
                "integration_settings",
                json!({"bins":123,"unsupported_option":false})
            ))
            .result["ok"],
        false
    );
    assert_eq!(
        call(&mut session, "state", json!({})).result["state"]["bins"],
        1000
    );
    assert_eq!(
        session
            .invoke(&request("open_project", json!({"path":"existing.dio"})))
            .result["ok"],
        false
    );
}

#[test]
fn loaded_poni_roundtrips_without_a_python_runtime() {
    let temp = tempfile::tempdir().unwrap();
    let mut session = Session::new(root());
    let first = call(
        &mut session,
        "open_calibration",
        json!({"path":root().join("dioptas/tests/data/CeO2_Pilatus1M.poni")}),
    );
    let path = temp.path().join("calibration.poni");
    call(&mut session, "save_calibration", json!({"path":path}));
    let reopened = call(&mut session, "open_calibration", json!({"path":path}));
    assert_eq!(
        first.result["state"]["geometry"],
        reopened.result["state"]["geometry"]
    );
    assert_eq!(
        first.result["state"]["calibration"]["pyfai"],
        reopened.result["state"]["calibration"]["pyfai"]
    );
}

#[cfg(feature = "dioptrin")]
#[test]
fn corrected_constant_image_integrates_to_its_known_intensity_and_exports_xy() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("constant.npy");
    // Independent flat-detector geometry: at each center the ray has length r,
    // incidence normalization is (distance/r)^3, and unpolarized scattering has
    // factor (1+cos(2theta)^2)/2. Construct counts with corrected intensity 7.
    let mut stored = vec![];
    for stored_row in 0..16 {
        for col in 0..20 {
            let y = (15 - stored_row) as f64 + 0.5;
            let x = col as f64 + 0.5;
            let a = y * 0.001 - 0.008;
            let b = x * 0.001 - 0.010;
            let cos = 0.1 / (a * a + b * b + 0.1_f64.powi(2)).sqrt();
            stored.push(7.0 * cos.powi(3) * (1.0 + cos * cos) / 2.0);
        }
    }
    npy(&path, &[16, 20], &stored);
    let mut session = Session::new(root());
    call(
        &mut session,
        "integration_settings",
        json!({"bins":40,"cake_bins":36,"polarization":0.0}),
    );
    call(&mut session, "open_image", json!({"path":path}));
    let parameters = json!({"dist":0.1,"poni1":0.008,"poni2":0.010,"rot1":0,"rot2":0,"rot3":0,"pixel1":0.001,"pixel2":0.001,"wavelength":1e-10,"polarization_factor":0.0});
    let reply = call(
        &mut session,
        "manual_geometry",
        json!({"convention":"pyfai","values":parameters}),
    );
    let y = reply.result["pattern"]["y"].as_array().unwrap();
    let nonempty = y
        .iter()
        .map(|v| v.as_f64().unwrap())
        .filter(|v| *v != 0.0)
        .collect::<Vec<_>>();
    assert!(nonempty.len() > 20);
    for intensity in nonempty {
        assert!((intensity - 7.0).abs() < 1e-10, "{intensity}");
    }
    assert_eq!(reply.result["cake"]["height"], 36);
    assert_eq!(reply.result["cake"]["width"], 40);
    let radial = &reply.result["cake"]["radialRange"];
    let x = reply.result["pattern"]["x"].as_array().unwrap();
    assert!((radial[0].as_f64().unwrap() - x[0].as_f64().unwrap()).abs() < 1e-12);
    assert!((radial[1].as_f64().unwrap() - x[39].as_f64().unwrap()).abs() < 1e-12);
    assert_eq!(reply.result["cake"]["azimuthRange"], json!([-175.0, 175.0]));
    let pixel = call(&mut session, "pixel", json!({"x":0,"y":0}));
    let expected_angle = (0.0075_f64.hypot(0.0095) / 0.1).atan().to_degrees();
    assert!((pixel.result["pixel"]["twoTheta"].as_f64().unwrap() - expected_angle).abs() < 1e-12);
    let cake_levels = call(
        &mut session,
        "image_levels",
        json!({"source":"cake","mode":"minmax","filter_gaps":false}),
    );
    assert_eq!(cake_levels.result["display"], "cake");
    assert!((cake_levels.result["levels"][1].as_f64().unwrap() - 7.0).abs() < 1e-10);
    assert_eq!(reply.result["state"]["calibration"]["pyfai"]["dist"], 0.1);
    let out = temp.path().join("pattern.xy");
    call(
        &mut session,
        "integration_save_pattern",
        json!({"path":out}),
    );
    let text = fs::read_to_string(out).unwrap();
    assert_eq!(text.lines().filter(|l| !l.starts_with('#')).count(), 40);
    let q = call(
        &mut session,
        "integration_settings",
        json!({"unit":"q_A^-1","poisson_errors":true}),
    );
    assert_eq!(q.result["pattern"]["sigma"].as_array().unwrap().len(), 40);
    assert_eq!(q.result["cake"]["unit"], "2th_deg");
    let edited = call(
        &mut session,
        "mask_stroke",
        json!({"points":[[1,1]],"radius":1,"defer_integration":true}),
    );
    assert!(edited.result["pattern"].is_null());
    assert!(edited.result["cake"].is_null());
    assert_eq!(edited.result["state"]["integrationDirty"], true);
    let calculated = call(&mut session, "integrate", json!({}));
    assert!(calculated.result["pattern"].is_object());
    assert_eq!(calculated.result["state"]["integrationDirty"], false);
}

#[cfg(not(feature = "dioptrin"))]
#[test]
fn no_engine_build_reads_images_and_never_substitutes_a_python_integrator() {
    let (_temp, path) = small_image();
    let mut session = Session::new(root());
    call(&mut session, "open_image", json!({"path":path}));
    call(
        &mut session,
        "open_calibration",
        json!({"path":root().join("dioptas/tests/data/CeO2_Pilatus1M.poni")}),
    );
    let reply = session.invoke(&request("integrate", json!({})));
    assert_eq!(reply.result["ok"], false);
    assert!(
        reply.result["error"]
            .as_str()
            .unwrap()
            .contains("no numerical engine")
    );
}

#[test]
fn real_stdio_processor_runs_with_python_and_path_unavailable() {
    use std::process::{Command, Stdio};
    let mut child = Command::new(env!("CARGO_BIN_EXE_dioptas-processor"))
        .env("DIOPTAS_PYTHON", "/missing/python")
        .env("PATH", "/missing")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    {
        let mut input = child.stdin.take().unwrap();
        writeln!(input, "{}", json!({"id":11,"action":"__host__"})).unwrap();
        writeln!(
            input,
            "{}",
            json!({"id":12,"action":"state","payload":null})
        )
        .unwrap();
        writeln!(input, "{}", json!({"id":13,"action":"progress"})).unwrap();
    }
    let output = child.wait_with_output().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let mut bytes = output.stdout.as_slice();
    let mut messages = std::collections::BTreeMap::new();
    while !bytes.is_empty() {
        let length = u32::from_le_bytes(bytes[..4].try_into().unwrap()) as usize;
        let header: Value = serde_json::from_slice(&bytes[4..4 + length]).unwrap();
        let size = header["buffers"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v["length"].as_u64().unwrap() as usize)
            .sum::<usize>();
        messages.insert(header["id"].as_u64().unwrap(), header["result"].clone());
        bytes = &bytes[4 + length + size..];
    }
    assert_eq!(messages[&11]["runtime"], "rust");
    assert_eq!(messages[&12]["ok"], false);
    assert_eq!(messages[&13]["ok"], true);
}

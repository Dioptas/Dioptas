use super::*;
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    })
}
fn fixture() -> (tempfile::TempDir, Vec<String>) {
    let dir = tempfile::tempdir().unwrap();
    let mut paths = vec![];
    for i in 0..3 {
        let path = dir.path().join(format!("frame_{i:04}.tif"));
        let file = File::create(&path).unwrap();
        tiff::encoder::TiffEncoder::new(file)
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray16>(16, 16, &vec![30u16; 256])
            .unwrap();
        paths.push(path.to_string_lossy().into_owned());
    }
    (dir, paths)
}
#[test]
fn settings_invalidate_the_first_affected_scientific_product() {
    let a = Config {
        integration_method: "summation".into(),
        ..Default::default()
    };
    let mut b = a.clone();
    b.gain = 2.;
    assert_eq!(a.first_changed(&b), 1);
    b = a.clone();
    b.read_noise = 3.;
    assert_eq!(a.first_changed(&b), 1);
    b = a.clone();
    b.threshold = 6.;
    assert_eq!(a.first_changed(&b), 1);
    b = a.clone();
    b.polarization = 0.5;
    assert_eq!(a.first_changed(&b), 4);
    b = a.clone();
    b.group = 61;
    assert_eq!(a.first_changed(&b), 5);
    b = a.clone();
    b.adp = "anisotropic".into();
    assert_eq!(a.first_changed(&b), 6);
    b = a.clone();
    b.confirmed = !a.confirmed;
    assert_eq!(a.first_changed(&b), 7);
    let mut crystal = Crystal {
        structure: json!({"r1":0.1}),
        cif: Some("candidate".into()),
        ..Default::default()
    };
    crystal.invalidate(7);
    assert_eq!(crystal.structure["r1"], 0.1);
    assert!(crystal.cif.is_some());
}
#[test]
fn invalid_acquisition_and_metric_fail_before_processing() {
    for c in [
        Config {
            omega_step: 0.,
            ..Default::default()
        },
        Config {
            exposure: 1.,
            omega_step: 0.5,
            ..Default::default()
        },
        Config {
            axis: [0.; 3],
            ..Default::default()
        },
        Config {
            gain: 0.,
            ..Default::default()
        },
        Config {
            metric: Some([1., 1., 1., 0., 90., 90.]),
            ..Default::default()
        },
    ] {
        assert!(c.check().is_err());
    }
}
#[test]
fn numerical_source_order_and_missing_frames_are_checked() {
    let (_dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    let mut reverse = paths.clone();
    reverse.reverse();
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":reverse})).result["ok"],
        true
    );
    assert_eq!(s.scxrd.sources[0].path, PathBuf::from(&paths[0]));
    let before = s.scxrd.sources.clone();
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":[paths[0],paths[2]]})).result["ok"],
        false
    );
    assert_eq!(s.scxrd.sources.len(), before.len());
    assert_eq!(s.scxrd.config.saturation, 65535.);
}
#[test]
fn failed_edits_are_atomic_and_successful_decisions_have_private_history() {
    let (_dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    let p = s.scxrd.sources[0].path.clone();
    let original = std::fs::read(&p).unwrap();
    std::fs::write(&p, b"corrupt").unwrap();
    let failed = call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"mask","bounds":[1,1,3,3]}),
    );
    assert_eq!(failed.result["ok"], false);
    assert!(s.scxrd.mask.is_empty());
    assert_eq!(s.scxrd.revision, 0);
    std::fs::write(&p, original).unwrap();
    assert_eq!(
        call(
            &mut s,
            "scxrd_edit",
            json!({"operation":"mask","bounds":[1,1,3,3]})
        )
        .result["ok"],
        true
    );
    assert_eq!(s.scxrd.mask.len(), 1);
    assert!(s.image.is_none());
    let undone = call(&mut s, "scxrd_edit", json!({"operation":"undo"}));
    assert!(s.scxrd.mask.is_empty());
    assert_eq!(undone.result["scxrd"]["canRedo"], true);
    call(&mut s, "scxrd_edit", json!({"operation":"redo"}));
    assert_eq!(s.scxrd.mask.len(), 1);
}
#[test]
fn hkfl4_fixed_columns_survive_large_signed_intensities() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("test.hkl");
    let mut s = Session::new(PathBuf::new());
    s.scxrd.reflections = vec![
        Reflection {
            hkl: [1, -2, 3],
            omega: 0.,
            intensity: -1e12,
            sigma: 4e10,
            flags: 0,
            track: Some(0),
            crossing: None,
            correction: 1.,
            native_use: None,
        },
        Reflection {
            hkl: [-9, 8, -7],
            omega: 0.,
            intensity: 2e13,
            sigma: 1e12,
            flags: 0,
            track: Some(1),
            crossing: None,
            correction: 1.,
            native_use: None,
        },
    ];
    assert_eq!(
        call(&mut s, "scxrd_file", json!({"operation":"hkl","path":path})).result["ok"],
        true
    );
    let text = std::fs::read_to_string(path).unwrap();
    for line in text.lines() {
        assert_eq!(line.len(), 28);
        assert!(line[0..4].trim().parse::<i32>().is_ok());
        assert!(line[12..20].trim().parse::<f64>().is_ok());
        assert!(line[20..28].trim().parse::<f64>().is_ok());
    }
    assert_eq!(text.lines().next().unwrap()[4..8].trim(), "-2");
}
#[test]
fn pixel_readout_and_auto_levels_belong_to_sc_frames() {
    let (_dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    s.scxrd.preview_values = Some(Arc::new((0..256).map(|v| v as f64).collect()));
    let r = call(&mut s, "scxrd_pixel", json!({"x":4,"y":2}));
    assert_eq!(r.result["scxrdPixel"]["value"], 36.);
    assert!(s.image.is_none());
    let r = call(
        &mut s,
        "scxrd_levels",
        json!({"mode":"minmax","percentile":2.5,"filter_gaps":false}),
    );
    assert_eq!(r.result["scxrd"]["image"]["limits"], json!([0., 255.]));
    assert!(s.image.is_none());
}
#[test]
fn track_table_can_reach_later_observations() {
    let mut s = Session::new(PathBuf::new());
    s.scxrd.tracks = (0..1205)
        .map(|i| Track {
            native: false,
            observed: [i as f64, 0., 0.],
            first: 0,
            last: 2,
            bounds: [0, 0, 1, 1],
            flags: 0,
            excluded: false,
        })
        .collect();
    let r = call(
        &mut s,
        "scxrd_table",
        json!({"kind":"tracks","offset":1200}),
    );
    assert_eq!(r.result["scxrd"]["tracks"].as_array().unwrap().len(), 5);
    assert_eq!(r.result["scxrd"]["tracks"][0]["id"], 1200);
    call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"track","index":1204}),
    );
    assert!(s.scxrd.tracks[1204].excluded);
}
#[test]
fn recipe_refuses_changed_sources_without_replacing_the_session() {
    let (dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    let recipe = dir.path().join("recipe.json");
    assert_eq!(
        call(
            &mut s,
            "scxrd_file",
            json!({"operation":"save","path":recipe})
        )
        .result["ok"],
        true
    );
    let source = s.scxrd.sources[1].path.clone();
    std::fs::write(source, b"invalid modified source").unwrap();
    let before = s.scxrd.sources.len();
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"open","path":recipe}),
    );
    assert_eq!(r.result["ok"], false);
    assert_eq!(s.scxrd.sources.len(), before);
}
#[test]
fn hkfl4_refuses_zero_uncertainty_precision_loss() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("test.hkl");
    std::fs::write(&path, "keep existing export").unwrap();
    let mut s = Session::new(PathBuf::new());
    s.scxrd.reflections = vec![
        Reflection {
            hkl: [1, 0, 0],
            omega: 0.,
            intensity: 1e12,
            sigma: 1e6,
            flags: 0,
            track: Some(0),
            crossing: None,
            correction: 1.,
            native_use: None,
        },
        Reflection {
            hkl: [0, 1, 0],
            omega: 0.,
            intensity: 20.,
            sigma: 1.,
            flags: 0,
            track: Some(1),
            crossing: None,
            correction: 1.,
            native_use: None,
        },
    ];
    let r = call(&mut s, "scxrd_file", json!({"operation":"hkl","path":path}));
    assert_eq!(r.result["ok"], false);
    assert_eq!(
        std::fs::read_to_string(path).unwrap(),
        "keep existing export"
    );
}
#[test]
fn exports_cannot_replace_original_detector_inputs() {
    let (_dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    let raw = s.scxrd.sources[0].path.clone();
    let bytes = std::fs::read(&raw).unwrap();
    assert_eq!(
        call(&mut s, "scxrd_file", json!({"operation":"save","path":raw})).result["ok"],
        false
    );
    assert_eq!(std::fs::read(raw).unwrap(), bytes);
}
#[test]
fn overload_default_is_reinferred_after_changing_detector_storage() {
    let (_dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    assert_eq!(s.scxrd.config.saturation, 65535.);
    let dir = tempfile::tempdir().unwrap();
    let mut next = Vec::new();
    for i in 0..3 {
        let p = dir.path().join(format!("u32_{i:04}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&p).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray32>(16, 16, &vec![90000u32; 256])
            .unwrap();
        next.push(p);
    }
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":next})).result["ok"],
        true
    );
    assert_eq!(s.scxrd.config.saturation, f64::from(u32::MAX - 1));
    assert_eq!(s.scxrd.preview_values.as_ref().unwrap()[0], 90000.);
}
#[test]
fn recipe_verification_rebuilds_external_companion_protection() {
    let dir = tempfile::tempdir().unwrap();
    let child = dir.path().join("counts.h5");
    {
        let f = hdf5::File::create(&child).unwrap();
        f.new_dataset::<u32>()
            .shape((3, 16, 16))
            .create("images")
            .unwrap()
            .write_raw(&vec![30u32; 3 * 16 * 16])
            .unwrap();
    }
    let master = dir.path().join("master.h5");
    {
        let f = hdf5::File::create(&master).unwrap();
        f.create_group("entry/data").unwrap();
        f.link_external("counts.h5", "/images", "/entry/data/data_000001")
            .unwrap();
    }
    let mut s = Session::new(PathBuf::new());
    let loaded = call(&mut s, "scxrd_load", json!({"path":master}));
    assert_eq!(loaded.result["ok"], true, "{:?}", loaded.result);
    let recipe = dir.path().join("recipe.json");
    call(
        &mut s,
        "scxrd_file",
        json!({"operation":"save","path":recipe}),
    );
    let mut payload: Value = serde_json::from_slice(&std::fs::read(&recipe).unwrap()).unwrap();
    payload["protected_sources"] = json!([]);
    std::fs::write(&recipe, serde_json::to_vec(&payload).unwrap()).unwrap();
    assert_eq!(
        call(
            &mut s,
            "scxrd_file",
            json!({"operation":"open","path":recipe})
        )
        .result["ok"],
        true
    );
    let protected = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"save","path":child}),
    );
    assert_eq!(protected.result["ok"], false);
}
#[test]
fn cancellation_keeps_the_completed_upstream_products() {
    let mut c = Crystal::default();
    c.stages[0] = Stage {
        status: "complete".into(),
        detail: "earlier completion".into(),
        seconds: 1.,
    };
    let control = Control::default();
    control.cancel();
    assert!(c.process(1, &control, false).is_err());
    assert_eq!(c.stages[0].status, "complete");
    assert_eq!(c.stages[0].detail, "earlier completion");
}
#[test]
#[cfg(debug_assertions)]
fn development_handoff_refuses_to_silently_drop_an_unsaved_scan() {
    let (dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    let transfer = dir.path().join("development.h5");
    let r = call(&mut s, "development_checkpoint", json!({"path":transfer}));
    assert_eq!(r.result["ok"], false);
    assert!(
        r.result["error"]
            .as_str()
            .unwrap()
            .contains("single-crystal data or settings cannot yet be transferred")
    );
    assert_eq!(s.scxrd.sources.len(), 3);
    assert!(!transfer.exists());
    assert!(!dir.path().join("development.history.h5").exists());
    assert_eq!(
        call(&mut s, "scxrd_frame", json!({"frame":2,"kind":"raw"})).result["ok"],
        true
    );
    let pixel = call(&mut s, "scxrd_pixel", json!({"x":15,"y":15}));
    assert_eq!(pixel.result["scxrdPixel"]["value"], 30.);
}

#[test]
#[cfg(debug_assertions)]
fn development_handoff_also_retains_sc_settings_before_frames_are_loaded() {
    let dir = tempfile::tempdir().unwrap();
    let mut s = Session::new(PathBuf::new());
    let mut config = s.scxrd.config.clone();
    config.threshold = 8.;
    assert_eq!(
        call(&mut s, "scxrd_settings", json!({"config":config})).result["ok"],
        true
    );
    let transfer = dir.path().join("development.dio");
    let refused = call(&mut s, "development_checkpoint", json!({"path":transfer}));
    assert_eq!(refused.result["ok"], false);
    assert!(
        refused.result["error"]
            .as_str()
            .unwrap()
            .contains("single-crystal data or settings")
    );
    assert_eq!(s.scxrd.config.threshold, 8.);
    assert!(
        refused.result["error"]
            .as_str()
            .unwrap()
            .contains("load frames and save")
    );
    assert!(!transfer.exists());
}

#[test]
fn hover_misses_are_empty_readouts_and_invalid_payloads_still_fail() {
    let (_dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    let empty = call(&mut s, "scxrd_pixel", json!({"x":0,"y":0}));
    assert_eq!(empty.result, json!({"ok":true,"scxrdPixel":null}));
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    s.scxrd.preview_values = Some(Arc::new((0..256).map(|v| v as f64).collect()));
    let edge = call(&mut s, "scxrd_pixel", json!({"x":15,"y":15}));
    assert_eq!(edge.result["scxrdPixel"]["value"], 255.);
    for (x, y) in [(16, 0), (0, 16), (u64::MAX, u64::MAX)] {
        assert_eq!(
            call(&mut s, "scxrd_pixel", json!({"x":x,"y":y})).result,
            json!({"ok":true,"scxrdPixel":null})
        );
    }
    assert_eq!(
        call(&mut s, "scxrd_pixel", json!({"x":-1,"y":0})).result["ok"],
        false
    );
    assert_eq!(s.scxrd.sources.len(), 3);
    assert!(s.image.is_none());
}
#[test]
fn initial_snapshot_uses_a_valid_image_kind() {
    let mut s = Session::new(PathBuf::new());
    let r = call(&mut s, "scxrd_snapshot", json!({}));
    assert_eq!(r.result["scxrd"]["previewKind"], "raw");
    assert_eq!(adapter_identity().len(), 64);
}
#[test]
fn recipe_settings_can_transfer_to_new_measurements_without_old_source_files() {
    let (dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    let mut config = s.scxrd.config.clone();
    config.threshold = 8.;
    config.omega_start = -15.;
    call(&mut s, "scxrd_settings", json!({"config":config}));
    let recipe = dir.path().join("recipe.json");
    call(
        &mut s,
        "scxrd_file",
        json!({"operation":"save","path":recipe}),
    );
    let old = s.scxrd.sources[0].path.clone();
    let (_new_dir, new_paths) = fixture();
    call(&mut s, "scxrd_load", json!({"paths":new_paths}));
    let current = s.scxrd.sources[0].path.clone();
    std::fs::remove_file(old).unwrap();
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"preset","path":recipe}),
    );
    assert_eq!(r.result["ok"], true);
    assert_eq!(s.scxrd.sources[0].path, current);
    assert_eq!(s.scxrd.config.threshold, 8.);
    assert!(!s.scxrd.config.confirmed);
    assert!(s.scxrd.cells.is_empty());
    assert!(!s.scxrd_undo.is_empty());
}

#[test]
#[ignore = "Local measured frames and explicit recipe/output paths required"]
fn matched_mgsio3_mask_ablation() {
    let recipe = std::env::var("DIOPTAS_SCXRD_COMPARISON_RECIPE").expect("comparison recipe");
    let output =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_COMPARISON_OUTPUT").expect("new output path"));
    assert!(!output.exists(), "Preserve previous comparisons");
    let mut session = Session::new(PathBuf::new());
    assert_eq!(
        call(
            &mut session,
            "scxrd_file",
            json!({"operation":"open","path":recipe})
        )
        .result["ok"],
        true
    );
    assert_eq!(
        call(&mut session, "scxrd_run", json!({"stage":5})).result["ok"],
        true
    );
    assert!(session.scxrd.error.is_none(), "{:?}", session.scxrd.error);
    let frozen = session.scxrd.clone();
    let mut results = Vec::new();
    for (name, dac, seat) in [
        ("no-shadows", false, false),
        ("dac-only", true, false),
        ("seat-only", false, true),
        ("combined", true, true),
    ] {
        let mut case = frozen.clone();
        case.config.dac_enabled = dac;
        case.config.seat_enabled = seat;
        case.config.dac_axis = [0., 0., 1.];
        case.config.dac_half_opening = 35.;
        case.config.shadow_block = 16;
        case.config.seat_threshold = 0.85;
        case.config.seat_guard = 32;
        case.shadows = None;
        case.prepare_shadows(&session.control).unwrap();
        case.process(4, &session.control, false).unwrap();
        case.process(5, &session.control, false).unwrap();
        results.push(json!({"case":name,"config":case.config,"geometry":case.geometry,"basis":case.basis,"shadows":case.shadows.as_ref().map(|s|&s.report),"scaling":case.scaling,"reflections":case.reflections,"tracks":case.tracks.iter().map(|t|t.observed).collect::<Vec<_>>() }));
        eprintln!("{name}: {}", case.scaling);
    }
    let report = json!({"protocol":"frozen measured tracks/basis/refined geometry; only native shared masks vary; identical original counts and integration supports","baselineAdapter":adapter_identity(),"cases":results});
    std::fs::write(output, serde_json::to_vec_pretty(&report).unwrap()).unwrap();
}

#[test]
fn profile_warnings_retain_explicit_native_eligibility() {
    let mut row = Reflection {
        hkl: [1, 2, 3],
        omega: 0.,
        intensity: 100.,
        sigma: 2.,
        flags: 131072,
        track: None,
        crossing: Some(7),
        correction: 1.,
        native_use: Some(true),
    };
    assert!(row.usable());
    row.native_use = Some(false);
    assert!(!row.usable());
    row.flags = 0;
    assert!(
        !row.usable(),
        "Masked/unmeasured zero-flag rows must remain excluded"
    );
}
#[test]
fn changing_cell_shadow_controls_invalidates_every_dependent_product() {
    let c = Config::default();
    for n in [
        Config {
            dac_enabled: true,
            ..c.clone()
        },
        Config {
            seat_enabled: true,
            ..c.clone()
        },
        Config {
            dac_half_opening: 34.,
            ..c.clone()
        },
        Config {
            shadow_block: 32,
            ..c.clone()
        },
        Config {
            axis: [-1., 0., 0.],
            ..c.clone()
        },
    ] {
        assert_eq!(c.first_changed(&n), 0);
    }
    let profile = Config {
        integration_method: "profile".into(),
        ..c.clone()
    };
    assert_eq!(
        profile.first_changed(&Config {
            group: 61,
            ..profile.clone()
        }),
        2
    );
}
#[test]
fn fractional_overload_threshold_uses_the_same_integer_boundary() {
    let threshold = 65535.5f64;
    for count in [65535u32, 65536] {
        assert_eq!(
            f64::from(count) >= threshold,
            count >= super::profiles::profile_reserved_minimum(threshold)
        );
    }
}
#[test]
fn cached_dac_mask_matches_full_exposure_kernel_and_rotation() {
    use spots::frame_validity as v;
    let g = reciprocal::Geometry {
        origin: [-0.008, -0.008, 0.02],
        fast: [0., 0.001, 0.],
        slow: [0.001, 0., 0.],
        beam: [0., 0., 1.],
        axis: [1., 0., 0.],
        wavelength: 1.,
    };
    let shape = v::Shape {
        height: 16,
        width: 16,
        block: 4,
    };
    let options = v::DacOptions {
        axis_at_zero: [0., 0., 1.],
        half_opening_degrees: 35.,
    };
    let mask = v::dac_mask(g, [20., 21.], shape, options).unwrap();
    let expanded = mask.expand().unwrap();
    let cache = Shadows {
        first: 2,
        last: 2,
        block: 4,
        columns: 4,
        cells: 16,
        illumination: vec![],
        dac: mask.excluded,
        report: Value::Null,
    };
    assert_eq!(
        (0..256)
            .map(|p| cache.excluded(2, p, 16))
            .collect::<Vec<_>>(),
        expanded
    );
    assert!((0..256).all(|p| cache.excluded(1, p, 16)));
    let rotated = v::dac_mask(g, [-21., -20.], shape, options)
        .unwrap()
        .expand()
        .unwrap();
    assert_ne!(
        expanded, rotated,
        "A moving cell shadow must not become a static rectangle"
    );
}

#[test]
fn profile_source_restores_storage_order_without_double_flipping() {
    use phasesmith_workflows::single_crystal::FrameSource;
    let dir = tempfile::tempdir().unwrap();
    let values: Vec<u32> = (0..256).map(|i| i as u32 + 1).collect();
    let mut paths = Vec::new();
    for i in 0..3 {
        let path = dir.path().join(format!("image_{i:04}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&path).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray32>(16, 16, &values)
            .unwrap();
        paths.push(path);
    }
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    let original = super::profiles::OriginalSource(&s.scxrd).read(0).unwrap();
    assert_eq!(original, values);
    let oriented = s.scxrd.read(0).unwrap();
    let flipped: Vec<_> = original
        .as_chunks::<16>()
        .0
        .iter()
        .rev()
        .flatten()
        .map(|&v| f64::from(v))
        .collect();
    assert_eq!(
        oriented, flipped,
        "Native vertical_flip=true produces the same calibrated view once"
    );
    assert_ne!(oriented[0], f64::from(original[0]));
}

#[test]
fn phasesmith_protocol_load_is_versioned_and_preserves_the_full_document() {
    let p = protocol::builtin();
    let mut c = Config::default();
    let (first, last) = c.apply_protocol(p.clone()).unwrap();
    assert_eq!((first, last), (2, 143));
    assert!(!c.confirmed);
    assert_eq!(c.protocol, Some(p));
    assert_eq!(c.integration_method, "profile");
    assert!(c.dac_enabled && c.seat_enabled);
    assert_eq!(c.axis, [-1., 0., 0.]);
    let effective = c.active_protocol(3, 140).unwrap();
    assert_eq!(effective["acquisition"]["first_frame"], 3);
    assert_eq!(effective["acquisition"]["last_frame_inclusive"], 140);
    assert_eq!(effective["profiles"], protocol::builtin()["profiles"]);
}
#[test]
fn unsupported_protocol_controls_fail_atomically() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("unsupported.json");
    let mut p = protocol::builtin();
    p["integration"]["pixel_radius"] = json!(8);
    std::fs::write(&path, serde_json::to_vec(&p).unwrap()).unwrap();
    let mut s = Session::new(PathBuf::new());
    let before = serde_json::to_value(&s.scxrd.config).unwrap();
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"protocol","path":path}),
    );
    assert_eq!(r.result["ok"], false);
    assert_eq!(serde_json::to_value(&s.scxrd.config).unwrap(), before);
    let mut unknown = protocol::builtin();
    unknown["space_group_search"] = json!({"mode":"unknown"});
    assert!(
        protocol::validate(&unknown)
            .unwrap_err()
            .contains("Automatic-symmetry")
    );
}
#[test]
fn old_v1_recipes_keep_their_original_summation_semantics() {
    let mut old = serde_json::to_value(Config::default()).unwrap();
    old.as_object_mut().unwrap().remove("integration_method");
    let decoded: Config = serde_json::from_value(old).unwrap();
    assert_eq!(decoded.integration_method, "summation");
    assert_eq!(Config::default().integration_method, "profile");
}

#[test]
fn protocol_algorithm_and_null_rotation_identity_cannot_drift() {
    for field in [
        "algorithm_profile",
        "null_rotations",
        "unimplemented_control",
    ] {
        let mut p = protocol::builtin();
        p["native_coordinator"][field] = json!("different");
        assert!(protocol::validate(&p).is_err());
    }
    let hash = format!(
        "{:x}",
        Sha256::digest(include_bytes!("../data/scxrd-null-rotations-v1.json"))
    );
    assert_eq!(
        protocol::builtin()["native_coordinator"]["null_rotations"]["sha256"],
        hash
    );
    let c = Config {
        search_seconds: 120.,
        ..Default::default()
    };
    assert!(c.check().unwrap_err().contains("hard_seconds"));
}

#[test]
fn protocol_survives_javascript_number_serialization_without_relaxing_values() {
    fn normalize(v: &mut Value) {
        match v {
            Value::Object(o) => o.values_mut().for_each(normalize),
            Value::Array(a) => a.iter_mut().for_each(normalize),
            Value::Number(n) => {
                if let Some(f) = n.as_f64()
                    && f.fract() == 0.
                    && f.abs() < 1e12
                {
                    *v = json!(f as i64);
                }
            }
            _ => {}
        }
    }
    let p = protocol::builtin();
    let mut javascript = p.clone();
    normalize(&mut javascript);
    assert!(protocol::same_json(&p, &javascript));
    protocol::validate(&javascript).unwrap();
    javascript["selection"]["max_cell_angle_deviation_degrees"] = json!(1.00001);
    assert!(!protocol::same_json(&p, &javascript));
    assert!(protocol::validate(&javascript).is_err());
}

#[test]
#[ignore = "Local raw/PONI files required for original metadata boundary audit"]
fn matched_original_geometry_boundary() {
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let file = hdf5::File::open(root.join("eiger_0000.h5")).unwrap();
    let scalar = |name: &str| {
        file.dataset(&format!(
            "/entry_0000/ESRF-ID11/eiger/detector_information/pixel_size/{name}"
        ))
        .unwrap()
        .read_raw::<f64>()
        .unwrap()[0]
    };
    let g = crate::geometry::Geometry::load(&root.join("CeO2_20240620_1849_dioptas.poni")).unwrap();
    let mut c = Crystal {
        shape: [2162, 2068],
        ..Default::default()
    };
    c.config.axis = [-1., 0., 0.];
    c.set_poni(&g).unwrap();
    let (p1, p2) = (scalar("ysize"), scalar("xsize"));
    let (s1, c1) = g.rot1.sin_cos();
    let (s2, c2) = g.rot2.sin_cos();
    let (s3, c3) = g.rot3.sin_cos();
    let mul = |a: M3, b: M3| -> M3 {
        std::array::from_fn(|i| std::array::from_fn(|j| (0..3).map(|k| a[i][k] * b[k][j]).sum()))
    };
    let r = mul(
        mul(
            [[c3, -s3, 0.], [s3, c3, 0.], [0., 0., 1.]],
            [[c2, 0., -s2], [0., 1., 0.], [s2, 0., c2]],
        ),
        [[1., 0., 0.], [0., c1, s1], [0., -s1, c1]],
    );
    let mv = |a: V3| -> V3 { std::array::from_fn(|i| (0..3).map(|j| r[i][j] * a[j]).sum()) };
    let expected = [
        mv([p1 / 2. - g.poni1, p2 / 2. - g.poni2, g.dist]),
        mv([0., p2, 0.]),
        mv([p1, 0., 0.]),
    ];
    let actual = c.initial_geometry.unwrap();
    let actual = [actual.origin, actual.fast, actual.slow];
    assert_eq!(
        [g.pixel1.to_bits(), g.pixel2.to_bits()],
        [p1.to_bits(), p2.to_bits()]
    );
    assert_eq!(
        expected.map(|v| v.map(f64::to_bits)),
        actual.map(|v| v.map(f64::to_bits)),
        "Initial PONI conversion must match standalone arithmetic bit for bit"
    );
}

#[test]
fn effective_protocol_export_refuses_unrepresentable_selections_without_writing() {
    let (dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    let path = dir.path().join("effective.json");
    for excluded in [vec![0, 1, 2], vec![1]] {
        s.scxrd.excluded_frames = excluded;
        let r = call(
            &mut s,
            "scxrd_file",
            json!({"operation":"protocol_save","path":path}),
        );
        assert_eq!(r.result["ok"], false);
        assert!(!path.exists());
    }
    s.scxrd.excluded_frames.clear();
    s.scxrd.mask.push([1, 1, 3, 3]);
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"protocol_save","path":path}),
    );
    assert_eq!(r.result["ok"], false);
    assert!(!path.exists());
}

#[test]
fn protocol_scope_and_declared_policies_fail_before_processing() {
    let c = Config {
        metric: Some([8., 5., 18., 90., 100., 90.]),
        ..Config::default()
    };
    assert!(c.check().unwrap_err().contains("orthorhombic"));
    for (section, key, value) in [
        ("gates", "minimum_exported_observations", json!(1)),
        ("io", "orientation", json!("unflipped")),
        ("archive_output", "compression_level", json!(9)),
        (
            "frame_input_execution",
            "reuse_verified_digest",
            json!(false),
        ),
        ("acquisition", "workers", json!(0)),
    ] {
        let mut p = protocol::builtin();
        p[section][key] = value;
        assert!(protocol::validate(&p).is_err(), "{section}.{key}");
    }
}
#[test]
fn protocol_snapshot_inspects_applied_overrides_and_blocks_frame_toggles() {
    let (dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    let mut p = protocol::builtin();
    p["acquisition"]["first_frame"] = json!(0);
    p["acquisition"]["last_frame_inclusive"] = json!(2);
    s.scxrd.config.apply_protocol(p).unwrap();
    // Default profile mode also derives effective settings without explicit import.
    s.scxrd.config.protocol = None;
    s.scxrd.config.dac_half_opening = 36.;
    let snap = call(&mut s, "scxrd_snapshot", json!({}));
    assert_eq!(
        snap.result["scxrd"]["effectiveProtocol"]["shadow_mask"]["geometric"]["half_opening_degrees"],
        json!(36.)
    );
    let path = dir.path().join("effective.json");
    assert_eq!(
        call(
            &mut s,
            "scxrd_file",
            json!({"operation":"protocol_save","path":path})
        )
        .result["ok"],
        true
    );
    let saved: Value = serde_json::from_reader(File::open(path).unwrap()).unwrap();
    assert_eq!(saved, snap.result["scxrd"]["effectiveProtocol"]);
    assert_eq!(
        call(&mut s, "scxrd_edit", json!({"operation":"frame","index":0})).result["ok"],
        false
    );
    assert!(s.scxrd.excluded_frames.is_empty());
}

#[test]
fn entering_protocol_replaces_manual_frame_selection_with_its_declared_interval() {
    let (_dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    let mut p = protocol::builtin();
    p["acquisition"]["first_frame"] = json!(0);
    p["acquisition"]["last_frame_inclusive"] = json!(2);
    s.scxrd.config.apply_protocol(p).unwrap();
    s.scxrd.config.integration_method = "summation".into();
    s.scxrd.excluded_frames = vec![1];
    let mut c = s.scxrd.config.clone();
    c.integration_method = "profile".into();
    assert_eq!(
        call(&mut s, "scxrd_settings", json!({"config":c})).result["ok"],
        true
    );
    assert!(s.scxrd.excluded_frames.is_empty());
    assert_eq!(s.scxrd.protocol_range().unwrap(), (0, 2));
    s.scxrd.excluded_frames = vec![0];
    assert!(s.scxrd.protocol_range().unwrap_err().contains("disagree"));
}

#[test]
fn observation_view_filter_preserves_native_signed_eligibility_and_global_counts() {
    let mut s = Session::new(PathBuf::new());
    s.scxrd.reflections = [(0, Some(false)), (131072, Some(true)), (0, Some(true))]
        .into_iter()
        .map(|(flags, native_use)| Reflection {
            hkl: [1, 2, 3],
            omega: 0.,
            intensity: -3.,
            sigma: 2.,
            flags,
            native_use,
            track: None,
            crossing: Some(0),
            correction: 1.,
        })
        .collect();
    let r = call(
        &mut s,
        "scxrd_table",
        json!({"kind":"reflections","offset":0,"filter":"usable"}),
    );
    assert_eq!(r.result["ok"], true);
    assert_eq!(r.result["scxrd"]["reflectionFilteredCount"], 2);
    assert_eq!(r.result["scxrd"]["reflectionCount"], 3);
    assert_eq!(r.result["scxrd"]["reflections"][0]["flags"], 131072);
    assert_eq!(r.result["scxrd"]["reflections"][0]["intensity"], -3.);
    let r = call(
        &mut s,
        "scxrd_table",
        json!({"kind":"reflections","offset":0,"filter":"excluded"}),
    );
    assert_eq!(r.result["scxrd"]["reflectionFilteredCount"], 1);
    assert_eq!(r.result["scxrd"]["reflections"][0]["native_use"], false);
    assert_eq!(s.scxrd.reflections.len(), 3);
}

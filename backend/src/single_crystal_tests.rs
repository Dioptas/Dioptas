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
fn compressed_frame_names_number_without_the_wrapper() {
    let number = |name: &str| frame_number(&Path::new("/data").join(name));
    assert_eq!(
        number("scan_0007.esper.gz"),
        Some(("/data/scan_.esper.gz".into(), 7))
    );
    assert_eq!(
        number("scan_0007.EDF.bz2"),
        Some(("/data/scan_.EDF.bz2".into(), 7))
    );
    assert_eq!(number("scan_0007.tif"), Some(("/data/scan_.tif".into(), 7)));
    assert_ne!(
        number("scan_0007.esper.gz").unwrap().0,
        number("scan_0007.esper").unwrap().0
    );
    assert_eq!(number("scan.esper.gz"), None);
}
#[test]
fn compressed_frames_are_ordered_numerically_and_gaps_are_rejected() {
    let fixture = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/esperanto/agi-extrema-cols18.esperanto.gz");
    let dir = tempfile::tempdir().unwrap();
    let paths: Vec<String> = (1..=4)
        .map(|i| {
            let path = dir.path().join(format!("scan_{i:04}.esper.gz"));
            std::fs::copy(&fixture, &path).unwrap();
            path.to_string_lossy().into_owned()
        })
        .collect();
    let mut s = Session::new(PathBuf::new());
    let shuffled = [&paths[2], &paths[0], &paths[1]];
    let loaded = call(&mut s, "scxrd_load", json!({"paths":shuffled}));
    assert_eq!(loaded.result["ok"], true, "{}", loaded.result);
    let order: Vec<_> = s.scxrd.sources.iter().map(|f| f.path.clone()).collect();
    let expected: Vec<_> = paths[..3].iter().map(PathBuf::from).collect();
    assert_eq!(order, expected);
    let gap = call(
        &mut s,
        "scxrd_load",
        json!({"paths":[&paths[3], &paths[0], &paths[1]]}),
    );
    assert_eq!(gap.result["ok"], false);
    assert!(
        gap.result["error"]
            .as_str()
            .unwrap_or_default()
            .contains("Missing or duplicate"),
        "{}",
        gap.result
    );
    assert_eq!(s.scxrd.sources.len(), 3);
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
        masks: None,
    };
    let control = Control::default();
    control.cancel();
    assert!(c.process(1, &control, false).is_err());
    assert_eq!(c.stages[0].status, "complete");
    assert_eq!(c.stages[0].detail, "earlier completion");
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
        seat: vec![],
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
#[test]
fn selected_frames_follow_their_numbers_whatever_the_dialog_order() {
    let mut names = vec!["s_10_a.tif", "s_2_a.tif", "s_1_a.tif", "s_010_b.tif"];
    names.sort_by(|a, b| super::natural_order(a, b));
    assert_eq!(
        names,
        ["s_1_a.tif", "s_2_a.tif", "s_10_a.tif", "s_010_b.tif"]
    );
    // Names without a trailing number used to keep the dialog's order.
    let dir = tempfile::tempdir().unwrap();
    let mut paths = Vec::new();
    for i in [3, 1, 2] {
        let p = dir.path().join(format!("f_raw_{i}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&p).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray16>(8, 8, &[i as u16; 64])
            .unwrap();
        paths.push(p);
    }
    let mut s = Session::new(PathBuf::new());
    let loaded = call(&mut s, "scxrd_load", json!({"paths":paths}));
    assert_eq!(loaded.result["ok"], true, "{:?}", loaded.result);
    let order: Vec<_> = s
        .scxrd
        .sources
        .iter()
        .map(|s| s.path.file_name().unwrap().to_string_lossy().into_owned())
        .collect();
    assert_eq!(order, ["f_raw_1.tif", "f_raw_2.tif", "f_raw_3.tif"]);
    // One file of a run opens the whole run, but not a neighbouring run.
    std::fs::copy(&paths[0], dir.path().join("g_raw_1.tif")).unwrap();
    let loaded = call(&mut s, "scxrd_load", json!({"paths":[paths[0]]}));
    assert_eq!(loaded.result["ok"], true, "{:?}", loaded.result);
    assert_eq!(s.scxrd.sources.len(), 3);
    // Opening hashes nothing; the first processing read records the counts.
    assert!(s.scxrd.sources.iter().all(|s| s.digest.get().is_none()));
    s.scxrd.read(1).unwrap();
    assert!(s.scxrd.sources[1].digest.get().is_some());
}
#[test]
fn pixel_click_traces_the_sc_constant_two_theta_line() {
    let (_dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    s.scxrd.preview_values = Some(Arc::new(vec![1.; 256]));
    let plain = call(&mut s, "scxrd_pixel", json!({"x":12,"y":8}));
    assert!(plain.result["scxrdPixel"]["contour"].is_null());
    // Beam through pixel (8, 8): constant 2θ is a circle about its centre.
    s.scxrd.geometry = Some(Geometry {
        origin: [-8., -8., 100.],
        fast: [1., 0., 0.],
        slow: [0., 1., 0.],
        beam: [0., 0., 1.],
        axis: [1., 0., 0.],
        wavelength: 0.5,
    });
    let r = call(&mut s, "scxrd_pixel", json!({"x":12,"y":8,"contour":true}));
    let pixel = &r.result["scxrdPixel"];
    let paths = pixel["contour"].as_array().unwrap();
    assert!(!paths.is_empty());
    for path in paths {
        assert_eq!(path["ring"], 0);
        for p in path["points"].as_array().unwrap() {
            let (x, y) = (p[0].as_f64().unwrap() - 8.5, p[1].as_f64().unwrap() - 8.5);
            assert!(((x * x + y * y).sqrt() - 4.).abs() < 0.1, "{p}");
        }
    }
    assert!(pixel["twoTheta"].as_f64().unwrap() > 0.);
}

#[test]
fn rotation_defaults_match_the_dac_scans() {
    let c = Config::default();
    assert_eq!((c.omega_start, c.omega_step, c.exposure), (-34., 0.5, 0.5));
    assert!(c.check().is_ok());
}

/// A 20-frame 128×128 series with a centred calibration. At the default
/// start (-34°) the 35° DAC opening crosses the detector, so the mask covers
/// part of every frame and moves with each rotation setting.
fn dac_fixture() -> (tempfile::TempDir, Vec<String>, PathBuf) {
    let dir = tempfile::tempdir().unwrap();
    let mut paths = vec![];
    for i in 0..20 {
        let path = dir.path().join(format!("dac_{i:04}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&path).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray16>(128, 128, &vec![30u16; 128 * 128])
            .unwrap();
        paths.push(path.to_string_lossy().into_owned());
    }
    let poni = dir.path().join("detector.poni");
    std::fs::write(
        &poni,
        "poni_version: 2\nDetector: Detector\nDetector_config: {\"pixel1\":0.00125,\"pixel2\":0.00125}\nDistance: 0.15\nPoni1: 0.08\nPoni2: 0.08\nRot1: 0\nRot2: 0\nRot3: 0\nWavelength: 2.846e-11\n",
    )
    .unwrap();
    (dir, paths, poni)
}
/// The lean single-crystal settings: only the geometric DAC mask.
fn dac_only(s: &Session) -> Config {
    Config {
        confirmed: true,
        integration_method: "summation".into(),
        background: false,
        dac_enabled: true,
        seat_enabled: false,
        diamond_enabled: false,
        axis: [-1., 0., 0.],
        shadow_block: 4,
        ..s.scxrd.config.clone()
    }
}
fn confirm(s: &mut Session) -> Reply {
    let c = dac_only(s);
    call(s, "scxrd_settings", json!({"config":c}))
}
/// The prepared-mask raster of the shown frame in a reply, if any.
fn shown_mask(r: &Reply) -> Option<Vec<u8>> {
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let s = &r.result["scxrd"];
    if s["maskImage"].is_null() {
        return None;
    }
    let id = s["maskImage"]["bufferId"].as_str().unwrap();
    let b = r.buffers.iter().find(|b| b.id == id).unwrap();
    Some(b.bytes.to_vec())
}
fn dac_session() -> (tempfile::TempDir, Session) {
    let (dir, paths, poni) = dac_fixture();
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(
        call(&mut s, "scxrd_frame", json!({"frame":10})).result["ok"],
        true
    );
    (dir, s)
}

#[test]
fn dac_only_settings_remake_the_mask_in_the_same_reply() {
    let (_dir, mut s) = dac_session();
    // Confirming the lean settings alone (after opening a series) already
    // brings the mask.
    let r = confirm(&mut s);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    let mut previous = shown_mask(&r).expect("DAC mask on the shown frame");
    let masked = previous.iter().filter(|&&v| v == 1).count();
    assert!(masked > 0 && masked < previous.len(), "{masked}");
    let base = dac_only(&s);
    for (name, c) in [
        (
            "dac_half_opening",
            Config {
                dac_half_opening: 40.,
                ..base.clone()
            },
        ),
        (
            "omega_start",
            Config {
                omega_start: -30.,
                ..base.clone()
            },
        ),
        (
            "omega_step",
            Config {
                omega_step: 0.25,
                exposure: 0.25,
                ..base.clone()
            },
        ),
        (
            "exposure",
            Config {
                omega_step: 0.25,
                exposure: 0.1,
                ..base.clone()
            },
        ),
        (
            "axis",
            Config {
                axis: [1., 0., 0.],
                ..base.clone()
            },
        ),
    ] {
        let revision = s.scxrd.revision;
        let r = call(&mut s, "scxrd_settings", json!({"config":c}));
        let stage = r.result["scxrd"]["stages"][0].clone();
        assert_eq!(stage["status"], "complete", "{name}");
        // As settings followed by an explicit run: invalidate, then stage 0.
        assert_eq!(s.scxrd.revision, revision + 2, "{name}");
        let mask = shown_mask(&r).expect(name);
        let dac = s.scxrd.shadows.as_ref().unwrap().report["dacSha256"].clone();
        let notice = r.result["scxrd"]["notice"].clone();
        // An explicit run of stage 0 gives exactly the same products.
        call(&mut s, "scxrd_edit", json!({"operation":"rerun","index":0}));
        let revision = s.scxrd.revision;
        let rerun = call(&mut s, "scxrd_run", json!({"stage":0}));
        assert_eq!(s.scxrd.revision, revision + 1, "{name}");
        assert_eq!(
            rerun.result["scxrd"]["stages"][0]["detail"], stage["detail"],
            "{name}"
        );
        assert_eq!(rerun.result["scxrd"]["notice"], notice, "{name}");
        assert_eq!(
            s.scxrd.shadows.as_ref().unwrap().report["dacSha256"],
            dac,
            "{name}"
        );
        assert_eq!(shown_mask(&rerun).as_ref(), Some(&mask), "{name}");
        // The exposure window alone moves the mask by less than a block on
        // the shown frame; the whole scan still changes.
        if name != "exposure" {
            assert_ne!(mask, previous, "{name}");
        }
        previous = mask;
    }
    // Undo returns the previous settings with their own mask; redo the new.
    let before = shown_mask(&call(&mut s, "scxrd_snapshot", json!({}))).unwrap();
    let c = Config {
        dac_half_opening: 20.,
        ..dac_only(&s)
    };
    call(&mut s, "scxrd_settings", json!({"config":c}));
    let after = shown_mask(&call(&mut s, "scxrd_snapshot", json!({}))).unwrap();
    assert_ne!(before, after);
    let undone = call(&mut s, "scxrd_edit", json!({"operation":"undo"}));
    assert_eq!(shown_mask(&undone).unwrap(), before);
    assert_eq!(undone.result["scxrd"]["stages"][0]["status"], "complete");
    let redone = call(&mut s, "scxrd_edit", json!({"operation":"redo"}));
    assert_eq!(shown_mask(&redone).unwrap(), after);
}

/// The seat shadow is fast and shows in the settings reply; diamond spots of
/// a large scan wait for Run, with stage 0 pending and the other masks still
/// shown (small scans: see `diamond_settings_refilter_cached_candidates_like_a_fresh_run`).
#[test]
fn seat_shadow_shows_at_once_and_large_diamond_scans_wait_for_run() {
    masks::DIAMOND_REPLY_LIMIT.set(0);
    let (_dir, mut s) = dac_session();
    let c = Config {
        seat_enabled: true,
        ..dac_only(&s)
    };
    let r = call(&mut s, "scxrd_settings", json!({"config":c}));
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert!(shown_mask(&r).is_some());
    let c = Config {
        diamond_enabled: true,
        ..c
    };
    let r = call(&mut s, "scxrd_settings", json!({"config":c.clone()}));
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "pending");
    assert!(shown_mask(&r).is_some(), "DAC and seat stay shown");
    assert!(s.scxrd.shadows.is_some() && s.scxrd.diamonds.is_none());
    let r = call(&mut s, "scxrd_run", json!({"stage":0}));
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert!(s.scxrd.diamonds.is_some());
}

#[test]
fn no_calibration_means_no_remake_and_no_error() {
    let (_dir, paths, _poni) = dac_fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    let r = confirm(&mut s);
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "pending");
    assert!(r.result["scxrd"]["error"].is_null());
    assert!(shown_mask(&r).is_none());
}

#[test]
fn a_failed_remake_leaves_stage_0_pending_and_keeps_the_settings() {
    let (_dir, mut s) = dac_session();
    confirm(&mut s);
    // Every frame excluded: preparing the masks fails.
    s.scxrd.excluded_frames = (0..20).collect();
    let c = Config {
        dac_half_opening: 40.,
        ..dac_only(&s)
    };
    let r = call(&mut s, "scxrd_settings", json!({"config":c}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(s.scxrd.config.dac_half_opening, 40.);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "pending");
    assert!(s.scxrd.shadows.is_none());
    assert!(shown_mask(&r).is_none());
    // The run button then reports the failure.
    let r = call(&mut s, "scxrd_run", json!({"stage":0}));
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "attention");
}

#[test]
fn a_cancelled_remake_leaves_stage_0_pending() {
    let (_dir, mut s) = dac_session();
    let control = Control::default();
    control.cancel();
    s.scxrd.config = dac_only(&s);
    s.scxrd.invalidate(0);
    assert!(!s.scxrd.refresh_masks(&control));
    assert_eq!(s.scxrd.stages[0].status, "pending");
    assert!(s.scxrd.shadows.is_none());
    assert!(s.scxrd.refresh_masks(&Control::default()));
}

#[test]
fn loading_a_calibration_shows_the_dac_mask_at_once() {
    let (_dir, paths, poni) = dac_fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    call(&mut s, "scxrd_frame", json!({"frame":10}));
    let r = confirm(&mut s);
    assert!(shown_mask(&r).is_none());
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert!(shown_mask(&r).is_some());
    // The same through the powder calibration.
    s.settings.geometry = crate::geometry::Geometry::load(&poni).unwrap();
    s.settings.calibrated = true;
    let c = Config {
        dac_half_opening: 30.,
        ..dac_only(&s)
    };
    call(&mut s, "scxrd_settings", json!({"config":c}));
    let before = shown_mask(&call(&mut s, "scxrd_snapshot", json!({}))).unwrap();
    let r = call(&mut s, "scxrd_file", json!({"operation":"use_calibration"}));
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert_eq!(shown_mask(&r).unwrap(), before);
    // With the seat shadow on as well, both are remade at once.
    let c = Config {
        seat_enabled: true,
        ..dac_only(&s)
    };
    call(&mut s, "scxrd_settings", json!({"config":c}));
    let r = call(&mut s, "scxrd_file", json!({"operation":"use_calibration"}));
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert!(shown_mask(&r).is_some());
    // Diamond spots of a large scan wait for Run; the fast masks stay shown.
    masks::DIAMOND_REPLY_LIMIT.set(0);
    let c = Config {
        diamond_enabled: true,
        ..s.scxrd.config.clone()
    };
    call(&mut s, "scxrd_settings", json!({"config":c}));
    let r = call(&mut s, "scxrd_file", json!({"operation":"use_calibration"}));
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "pending");
    assert!(shown_mask(&r).is_some());
}

#[test]
fn reopening_a_series_with_a_calibration_needs_only_the_confirmation() {
    let (_dir, mut s) = dac_session();
    confirm(&mut s);
    let paths: Vec<_> = s.scxrd.sources.iter().map(|s| s.path.clone()).collect();
    let r = call(&mut s, "scxrd_load", json!({"paths":paths}));
    // Opening resets the confirmation, so nothing is prepared yet ...
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "pending");
    assert!(s.scxrd.initial_geometry.is_some());
    // ... and confirming the unchanged settings brings the mask.
    let r = confirm(&mut s);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert!(shown_mask(&r).is_some());
}

#[test]
fn parallel_dac_mask_equals_the_per_frame_sequential_mask() {
    use spots::frame_validity as validity;
    let (_dir, mut s) = dac_session();
    s.scxrd.config = dac_only(&s);
    s.scxrd.excluded_frames = vec![0, 19];
    s.scxrd.invalidate(0);
    s.scxrd.prepare_shadows(&Control::default()).unwrap();
    let c = &s.scxrd.config;
    let shape = validity::Shape {
        height: 128,
        width: 128,
        block: c.shadow_block,
    };
    let mut g = s.scxrd.initial_geometry.unwrap().native();
    g.axis = c.axis;
    let mut sequential = vec![];
    for frame in 1..=18 {
        let low = c.omega_start + frame as f64 * c.omega_step;
        sequential.extend(
            validity::dac_mask(
                g,
                [low, low + c.exposure],
                shape,
                validity::DacOptions {
                    axis_at_zero: c.dac_axis,
                    half_opening_degrees: c.dac_half_opening,
                },
            )
            .unwrap()
            .excluded,
        );
    }
    let shadows = s.scxrd.shadows.as_ref().unwrap();
    assert_eq!((shadows.first, shadows.last), (1, 18));
    assert!(sequential.contains(&true) && sequential.contains(&false));
    assert_eq!(shadows.dac, sequential);
}

/// The DAC mask of the measured Eiger scan, timed in parallel (as Prepare
/// masks runs it) against the per-frame sequential kernel, which it must equal.
#[test]
#[ignore = "Local Eiger scan and PONI required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_dac_mask_parallel_timing() {
    use spots::frame_validity as validity;
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let mut s = Session::new(PathBuf::new());
    let master = root.join("eiger_0000.h5");
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"path":master})).result["ok"],
        true
    );
    let poni = root.join("CeO2_20240620_1849_dioptas.poni");
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let c = Config {
        axis: [-1., 0., 0.],
        shadow_block: 16,
        ..dac_only(&s)
    };
    s.scxrd.config = c.clone();
    s.scxrd.invalidate(0);
    let start = std::time::Instant::now();
    s.scxrd.prepare_shadows(&Control::default()).unwrap();
    let parallel = start.elapsed();
    let shape = validity::Shape {
        height: s.scxrd.shape[0],
        width: s.scxrd.shape[1],
        block: c.shadow_block,
    };
    let mut g = s.scxrd.initial_geometry.unwrap().native();
    g.axis = c.axis;
    let start = std::time::Instant::now();
    let mut sequential = vec![];
    for frame in 0..s.scxrd.sources.len() {
        let low = c.omega_start + frame as f64 * c.omega_step;
        sequential.extend(
            validity::dac_mask(
                g,
                [low, low + c.exposure],
                shape,
                validity::DacOptions {
                    axis_at_zero: c.dac_axis,
                    half_opening_degrees: c.dac_half_opening,
                },
            )
            .unwrap()
            .excluded,
        );
    }
    let sequential_time = start.elapsed();
    assert_eq!(s.scxrd.shadows.as_ref().unwrap().dac, sequential);
    eprintln!(
        "{} frames: parallel {:.3} s, sequential {:.3} s",
        s.scxrd.sources.len(),
        parallel.as_secs_f64(),
        sequential_time.as_secs_f64()
    );
}

/// The DAC opening estimate on the Eiger enstatite scan: the shadow enters
/// at both ends, so start and opening are both determined.
#[test]
#[ignore = "Local Eiger scan and PONI required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_dac_estimate() {
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let mut s = Session::new(PathBuf::new());
    let master = root.join("eiger_0000.h5");
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"path":master})).result["ok"],
        true
    );
    let poni = root.join("CeO2_20240620_1849_dioptas.poni");
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let c = Config {
        axis: [-1., 0., 0.],
        ..dac_only(&s)
    };
    call(&mut s, "scxrd_settings", json!({"config":c}));
    let r = call(&mut s, "scxrd_edit", json!({"operation":"estimate_dac"}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let e = &r.result["dacEstimate"];
    eprintln!("{e:#}");
    assert_eq!(e["status"], "both");
    assert!(e["after"].as_f64().unwrap() > e["before"].as_f64().unwrap());
}

/// A 128×128 series (1° steps, 0.2° wide) whose counts are dark (10) where
/// the geometric DAC mask at `truth` = (start, half-opening) excludes a pixel
/// and lit (100) elsewhere; `None` gives a uniformly lit series. The session
/// holds the settings `start`/`opening` and the calibration.
fn synthetic_shadow(
    truth: Option<(f64, f64)>,
    frames: usize,
    start: f64,
    opening: f64,
) -> (tempfile::TempDir, Session) {
    use spots::frame_validity as validity;
    let (fixture, probe) = dac_session();
    let mut g = probe.scxrd.initial_geometry.unwrap().native();
    g.axis = [-1., 0., 0.];
    let dir = tempfile::tempdir().unwrap();
    let mut paths = vec![];
    for i in 0..frames {
        let counts: Vec<u16> = match truth {
            Some((s0, a0)) => {
                let low = s0 + i as f64;
                validity::dac_mask(
                    g,
                    [low, low + 0.2],
                    validity::Shape {
                        height: 128,
                        width: 128,
                        block: 1,
                    },
                    validity::DacOptions {
                        axis_at_zero: [0., 0., 1.],
                        half_opening_degrees: a0,
                    },
                )
                .unwrap()
                .excluded
                .iter()
                .map(|&dark| if dark { 10 } else { 100 })
                .collect()
            }
            None => vec![100; 128 * 128],
        };
        let path = dir.path().join(format!("shadow_{i:04}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&path).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray16>(128, 128, &counts)
            .unwrap();
        paths.push(path.to_string_lossy().into_owned());
    }
    let poni = dir.path().join("detector.poni");
    std::fs::copy(fixture.path().join("detector.poni"), &poni).unwrap();
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let c = Config {
        omega_start: start,
        omega_step: 1.,
        exposure: 0.2,
        dac_half_opening: opening,
        ..dac_only(&s)
    };
    let r = call(&mut s, "scxrd_settings", json!({"config":c}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    (dir, s)
}
fn estimate(s: &mut Session) -> Value {
    let revision = s.scxrd.revision;
    let config = s.scxrd.config.clone();
    let r = call(s, "scxrd_edit", json!({"operation":"estimate_dac"}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    // The estimate only reports; the settings stay as they were.
    assert_eq!(s.scxrd.revision, revision);
    assert!(s.scxrd.config == config);
    r.result["dacEstimate"].clone()
}

/// The shadow moves in from both ends of a -45…+45° scan (opening 30°):
/// start and opening are both recovered within one grid step from settings
/// 3° and 5° off. Synthetic edges come from the full-exposure, whole-pixel mask (half a
/// 0.48° pixel plus half the 0.2° exposure wider than the cone) while the fit
/// models block centres at mid-exposure, hence the tolerance.
#[test]
fn dac_estimate_recovers_start_and_opening_from_both_edges() {
    let (_dir, mut s) = synthetic_shadow(Some((-45., 30.)), 90, -42., 35.);
    let e = estimate(&mut s);
    assert_eq!(e["status"], "both", "{e}");
    let start = e["omegaStart"].as_f64().unwrap();
    let opening = e["halfOpening"].as_f64().unwrap();
    // Within one grid step: whole rotation steps (1°) and 0.5° openings.
    assert!((start + 45.).abs() < 1e-9, "{e}");
    assert!((opening - 30.).abs() <= 0.5, "{e}");
    assert!(e["after"].as_f64().unwrap() > 0.95, "{e}");
    assert!(e["after"].as_f64().unwrap() > e["before"].as_f64().unwrap());
    let range = e["startRange"].as_array().unwrap();
    assert!(range[0].as_f64().unwrap() <= start && start <= range[1].as_f64().unwrap());
}

/// Only the start of a -45…0° scan is shadowed (opening 40°, wider than the
/// detector): the start is kept and only the opening fitted, so the start
/// plus opening combination the data fixes is preserved.
#[test]
fn dac_estimate_with_one_edge_keeps_the_start_and_fits_the_opening() {
    for (start, expected) in [(-45., 40.), (-44., 39.)] {
        let (_dir, mut s) = synthetic_shadow(Some((-45., 40.)), 45, start, 35.);
        let e = estimate(&mut s);
        assert_eq!(e["status"], "opening_only", "{e}");
        assert!(e["omegaStart"].is_null(), "{e}");
        let opening = e["halfOpening"].as_f64().unwrap();
        assert!((opening - expected).abs() < 0.5, "{start}: {e}");
        let range = e["startRange"].as_array().unwrap();
        assert!(
            range[1].as_f64().unwrap() - range[0].as_f64().unwrap() > 2.,
            "{e}"
        );
    }
}

/// Returned values lie on the grids the search visits: the start on whole
/// rotation steps, the opening on 0.5°, and the reported fit is that of the
/// returned pair. Truth off both grids (start -44.7 with 1° steps, opening
/// 30.3°).
#[test]
fn dac_estimate_snaps_to_the_step_and_half_degree_grids() {
    let on = |v: f64, grid: f64| ((v / grid) - (v / grid).round()).abs() < 1e-9;
    let (_dir, mut s) = synthetic_shadow(Some((-44.7, 30.3)), 90, -42., 35.);
    let e = estimate(&mut s);
    assert_eq!(e["status"], "both", "{e}");
    let start = e["omegaStart"].as_f64().unwrap();
    let opening = e["halfOpening"].as_f64().unwrap();
    assert!(on(start, 1.) && on(opening, 0.5), "{e}");
    assert!((start + 44.7).abs() <= 1., "{e}");
    assert!((opening - 30.3).abs() <= 0.75, "{e}");
    for range in [&e["startRange"], &e["openingRange"]] {
        for v in range.as_array().unwrap() {
            assert!(on(v.as_f64().unwrap(), 0.5), "{e}");
        }
    }
    // The fit belongs to the returned values.
    let c = &s.scxrd.config;
    let fitted = Config {
        omega_start: start,
        dac_half_opening: opening,
        ..c.clone()
    };
    call(&mut s, "scxrd_settings", json!({"config":fitted}));
    let again = estimate(&mut s);
    assert!(
        (again["before"].as_f64().unwrap() - e["after"].as_f64().unwrap()).abs() < 1e-12,
        "{e} {again}"
    );
}

#[test]
fn dac_estimate_without_a_shadow_changes_nothing() {
    let (_dir, mut s) = synthetic_shadow(None, 30, -34., 35.);
    let e = estimate(&mut s);
    assert_eq!(e["status"], "no_shadow", "{e}");
    assert!(
        e["omegaStart"].is_null() && e["halfOpening"].is_null(),
        "{e}"
    );
}

#[test]
fn dac_estimate_needs_a_calibration() {
    let (_dir, paths, _poni) = dac_fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    let r = call(&mut s, "scxrd_edit", json!({"operation":"estimate_dac"}));
    assert_eq!(r.result["ok"], false, "{:?}", r.result);
    assert!(
        r.result["error"].as_str().unwrap().contains("calibration"),
        "{:?}",
        r.result
    );
}

#[test]
fn a_cancelled_dac_estimate_stops() {
    let (_dir, s) = synthetic_shadow(Some((-45., 30.)), 20, -45., 30.);
    let control = Control::default();
    control.cancel();
    assert!(s.scxrd.estimate_dac(&control).is_err());
}

/// How few frames give a stable DAC estimate on the Eiger scan.
#[test]
#[ignore = "Local Eiger scan and PONI required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_dac_estimate_frame_counts() {
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let mut s = Session::new(PathBuf::new());
    call(
        &mut s,
        "scxrd_load",
        json!({"path":root.join("eiger_0000.h5")}),
    );
    let poni = root.join("CeO2_20240620_1849_dioptas.poni");
    call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    let c = Config {
        axis: [-1., 0., 0.],
        ..dac_only(&s)
    };
    call(&mut s, "scxrd_settings", json!({"config":c}));
    let used: Vec<usize> = (0..s.scxrd.sources.len()).collect();
    let n = used.len();
    let first_last = |k: usize| {
        let mut f: Vec<usize> = (0..k).collect();
        f.extend(n - k..n);
        f
    };
    let cases: Vec<(String, Vec<usize>)> = vec![
        ("4 = frames 1-2 + last 2".into(), first_last(2)),
        ("8 = frames 1-4 + last 4".into(), first_last(4)),
        ("4 = 2 per end over 10 %".into(), dac_fit::ends(&used, 2)),
        ("8 = 4 per end over 10 %".into(), dac_fit::ends(&used, 4)),
        ("16 = 8 per end over 10 %".into(), dac_fit::ends(&used, 8)),
        ("5 = 2 per end over 10 % + middle".into(), {
            let mut f = dac_fit::ends(&used, 2);
            f.push(n / 2);
            f
        }),
        (format!("all {n}"), used.clone()),
    ];
    let control = Control::default();
    for (name, frames) in cases {
        // Second run: the file cache is warm, as after opening the series.
        let mut e = s
            .scxrd
            .estimate_dac_frames(&control, frames.clone(), false)
            .unwrap();
        e = s
            .scxrd
            .estimate_dac_frames(&control, frames, false)
            .unwrap_or(e);
        eprintln!(
            "{name:28} {:12} start {:>7} {:>16} opening {:>6} {:>14} fit {:.3}->{:.3} {:.3} s",
            e["status"].as_str().unwrap(),
            e["omegaStart"].to_string(),
            e["startRange"].to_string(),
            e["halfOpening"].to_string(),
            e["openingRange"].to_string(),
            e["before"].as_f64().unwrap(),
            e["after"].as_f64().unwrap(),
            e["seconds"].as_f64().unwrap()
        );
    }
}

/// The seat field prepared again on a single worker thread.
fn sequential_seat(s: &Session) -> Vec<u8> {
    let mut c = s.scxrd.clone();
    c.invalidate(0);
    // Nothing cached: every frame is read again.
    c.parts = Default::default();
    let pool = crate::worker_pool::pool(Some(1)).unwrap();
    crate::worker_pool::enter(pool, || c.prepare_shadows(&Control::default())).unwrap();
    c.shadows.unwrap().seat.clone()
}

/// Synthetic 256×256 scan for the measured seat shadow: lit background of
/// only 15-25 counts (rising to the left, with pixel noise), a module gap
/// (rows 120-135, saturated so unusable) and, in the first six of twelve
/// frames, a cell shadow entering from the right: umbra at 2 % of the lit
/// level and a 40 px linear penumbra whose edge is curved and moves in by
/// 15 px per frame. Returns the true lit share of every pixel per frame.
fn synthetic_seat() -> (tempfile::TempDir, Session, Vec<Vec<f64>>) {
    const N: usize = 256;
    let dir = tempfile::tempdir().unwrap();
    let (mut paths, mut truth) = (vec![], vec![]);
    let mut noise = 12345u64;
    for f in 0..12 {
        let mut share = vec![1.; N * N];
        let mut counts = vec![0u16; N * N];
        for y in 0..N {
            let edge = 230. - 15. * f as f64 + 30. * ((y as f64 - 128.) / 128.).powi(2);
            for x in 0..N {
                let i = y * N + x;
                if f < 6 {
                    let into = x as f64 - (edge - 40.);
                    share[i] = if into <= 0. {
                        1.
                    } else {
                        (1. - into / 40.).max(0.) * 0.98 + 0.02
                    };
                }
                noise = noise
                    .wrapping_mul(6364136223846793005)
                    .wrapping_add(1442695040888963407);
                let wobble = ((noise >> 33) % 9) as f64 - 4.;
                let lit = 25. - 10. * x as f64 / N as f64;
                counts[i] = if (120..136).contains(&y) {
                    u16::MAX
                } else {
                    (lit * share[i] + wobble * share[i].sqrt()).round().max(0.) as u16
                };
            }
        }
        let path = dir.path().join(format!("seat_{f:04}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&path).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray16>(N as u32, N as u32, &counts)
            .unwrap();
        paths.push(path.to_string_lossy().into_owned());
        truth.push(share);
    }
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    s.scxrd.config = Config {
        dac_enabled: false,
        seat_enabled: true,
        seat_threshold: 0.6,
        seat_guard: 8,
        shadow_block: 8,
        ..dac_only(&s)
    };
    s.scxrd.invalidate(0);
    s.scxrd.prepare_shadows(&Control::default()).unwrap();
    (dir, s, truth)
}

/// Umbra and dim penumbra are masked completely, as one region per frame
/// reaching the detector edge and continuing across the module gap; the
/// mask stops within two blocks of the fully lit area; frames without
/// shadow get no mask.
#[test]
fn seat_shadow_masks_umbra_and_penumbra_across_a_module_gap() {
    const N: usize = 256;
    let (_dir, s, truth) = synthetic_seat();
    let c = &s.scxrd;
    for (f, share) in truth.iter().enumerate() {
        let raw = c.decode(f).unwrap();
        let base = c.base_mask(&raw, f);
        let seat: Vec<bool> = c
            .mask_for(&raw, f)
            .iter()
            .zip(&base)
            .map(|(&m, &b)| m && !b)
            .collect();
        if f >= 6 {
            assert!(!seat.contains(&true), "frame {f}: no shadow, no mask");
            continue;
        }
        let mut boundary = vec![];
        for y in (0..N).filter(|y| !(120..136).contains(y)) {
            let row = &seat[y * N..(y + 1) * N];
            // One run reaching the right edge.
            let first = row.iter().position(|&m| m).unwrap_or(N);
            assert!(
                row[first..].iter().all(|&m| m),
                "frame {f} row {y}: one run"
            );
            // Fully lit from 40 px before the edge: at most 16 px into it.
            let lit_from = (0..N)
                .rev()
                .find(|&i| share[y * N + i] >= 1.)
                .map_or(0, |i| i + 1);
            for x in 0..N {
                let v = share[y * N + x];
                assert!(
                    v >= 0.3 || row[x],
                    "frame {f} ({x},{y}): share {v:.2} unmasked"
                );
                assert!(
                    !row[x] || x + 16 >= lit_from,
                    "frame {f} ({x},{y}): masked lit area"
                );
            }
            boundary.push((y, first));
        }
        // Continuous across the gap: the edge just above and below it agree.
        let at = |y: usize| boundary.iter().find(|b| b.0 == y).unwrap().1 as f64;
        assert!(
            (at(119) - at(136)).abs() <= 8.,
            "frame {f}: {} vs {}",
            at(119),
            at(136)
        );
    }
}

/// Every step of the estimate is independent of the thread count, and the
/// full-frame mask (overlay, Find spots) equals the per-pixel test (omega
/// background).
#[test]
fn seat_shadow_is_deterministic_and_equal_to_the_sequential_estimate() {
    let (_dir, s, _) = synthetic_seat();
    let first = s.scxrd.shadows.clone().unwrap();
    assert_eq!(first.report["seatMeasurement"]["route"], "every frame");
    assert_eq!(first.seat, sequential_seat(&s));
    for frame in [0, 3, 8] {
        let mut full = vec![false; 256 * 256];
        first.fill(frame, &mut full, 256);
        assert!(
            (0..full.len()).all(|i| full[i] == first.excluded(frame, i, 256)),
            "frame {frame}"
        );
    }
    let mut again = s.scxrd.clone();
    again.invalidate(0);
    again.prepare_shadows(&Control::default()).unwrap();
    assert_eq!(again.shadows.unwrap().seat, first.seat);
}

/// Long scans read a few frames. Without a calibration, or when the DAC cone
/// predicts the measured frames worse than plain interpolation (here a
/// wrong rotation axis), the frames between the measured ones are
/// interpolated; the shadow is masked either way.
#[test]
fn seat_shadow_falls_back_to_interpolation_without_a_usable_cone() {
    let (_dir, mut s) = synthetic_shadow(Some((-45., 30.)), 90, -45., 30.);
    s.scxrd.config.seat_enabled = true;
    s.scxrd.config.seat_threshold = 0.5;
    s.scxrd.config.seat_guard = 4;
    let mut uncalibrated = s.scxrd.clone();
    uncalibrated.initial_geometry = None;
    uncalibrated.config.dac_enabled = false;
    let mut wrong_axis = s.scxrd.clone();
    wrong_axis.config.axis = [0., 1., 0.];
    wrong_axis.config.dac_enabled = false;
    for (name, mut c) in [("uncalibrated", uncalibrated), ("wrong axis", wrong_axis)] {
        c.invalidate(0);
        c.prepare_shadows(&Control::default()).unwrap();
        let sh = c.shadows.unwrap();
        let m = &sh.report["seatMeasurement"];
        eprintln!("{name}: {m}");
        assert_eq!(m["route"], "interpolated", "{name}");
        assert!(m["frames"].as_array().unwrap().len() < 90, "{name}");
        assert!(
            sh.illumination[..sh.cells].iter().any(|&v| v),
            "{name}: first frame shadowed"
        );
    }
}

#[test]
fn parallel_seat_shadow_equals_the_sequential_estimate() {
    // Lit mid-scan reference frames, partial shadow towards both ends.
    let (_dir, mut s) = synthetic_shadow(Some((-45., 30.)), 90, -45., 30.);
    s.scxrd.config.seat_enabled = true;
    s.scxrd.config.seat_threshold = 0.5;
    s.scxrd.config.seat_guard = 4;
    s.scxrd.invalidate(0);
    s.scxrd.prepare_shadows(&Control::default()).unwrap();
    let shadows = s.scxrd.shadows.clone().unwrap();
    let n = shadows.illumination.iter().filter(|&&v| v).count();
    assert!(
        n > 0 && n < shadows.illumination.len(),
        "{n} of {}",
        shadows.illumination.len()
    );
    // 90 frames: a few are read, the rest follow the DAC cone model.
    assert_eq!(shadows.report["seatMeasurement"]["route"], "DAC cone model");
    assert_eq!(shadows.seat, sequential_seat(&s));
}

/// Parallel seat shadow on the Eiger scan: equal to the sequential estimate,
/// with both timings.
#[test]
#[ignore = "Local Eiger scan and PONI required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_seat_shadow_parallel_timing() {
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let mut s = Session::new(PathBuf::new());
    call(
        &mut s,
        "scxrd_load",
        json!({"path":root.join("eiger_0000.h5")}),
    );
    s.scxrd.config = Config {
        axis: [-1., 0., 0.],
        dac_enabled: false,
        seat_enabled: true,
        seat_threshold: 0.5,
        seat_guard: 16,
        shadow_block: 16,
        ..dac_only(&s)
    };
    s.scxrd.invalidate(0);
    let start = std::time::Instant::now();
    let seq = sequential_seat(&s);
    let sequential = start.elapsed();
    let start = std::time::Instant::now();
    s.scxrd.parts = Default::default();
    s.scxrd.prepare_shadows(&Control::default()).unwrap();
    let parallel = start.elapsed();
    assert_eq!(s.scxrd.shadows.as_ref().unwrap().seat, seq);
    eprintln!(
        "seat shadow, {} frames: sequential {:.2} s, parallel {:.2} s",
        s.scxrd.sources.len(),
        sequential.as_secs_f64(),
        parallel.as_secs_f64()
    );
}

/// Round trip through the real development checkpoint commands.
#[cfg(debug_assertions)]
fn development_reload(old: &mut Session, dir: &Path) -> Session {
    let transfer = dir.join("development.dio");
    let r = call(old, "development_checkpoint", json!({"path":transfer}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let mut new = Session::new(PathBuf::new());
    let r = call(&mut new, "development_restore", json!({"path":transfer}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    new
}
fn found_products(c: &mut Crystal) {
    c.stages[1] = Stage {
        status: "complete".into(),
        detail: "1 spot".into(),
        seconds: 0.5,
        masks: None,
    };
    c.stages[2] = Stage {
        status: "complete".into(),
        detail: "1 lattice".into(),
        seconds: 0.25,
        masks: None,
    };
    c.tracks = vec![Track {
        native: true,
        observed: [3., 4., 1.5],
        first: 9,
        last: 11,
        bounds: [1, 2, 5, 6],
        flags: 0,
        excluded: true,
    }];
    c.peaks = vec![Peak {
        frame: 10,
        xy: [3., 4.],
        intensity: 99.,
        flags: 0,
        bounds: [1, 2, 5, 6],
        track: 0,
    }];
    c.cells = vec![Cell {
        direct: [[5., 0., 0.], [0., 6., 0.], [0., 0., 7.]],
        parameters: [5., 6., 7., 90., 90., 90.],
        indexed: 1,
        total: 1,
        rms: 0.01,
        validation: 1,
        found: lattices::Found::Rows,
        merged: None,
        kept: true,
    }];
    c.selected = Some(0);
}
/// A second, unticked lattice, shown on the image.
fn second_lattice(c: &mut Crystal) {
    let mut cell = c.cells[0].clone();
    cell.direct = [[8., 0., 0.], [0., 9., 0.], [0., 0., 10.]];
    cell.kept = false;
    c.cells.push(cell);
    c.shown = Some(1);
}
#[test]
fn lattice_ticks_choose_the_lattice_for_later_steps_and_showing_is_not_an_edit() {
    let (_dir, mut s) = dac_session();
    found_products(&mut s.scxrd);
    second_lattice(&mut s.scxrd);
    s.scxrd.shown = None;
    let edit = |s: &mut Session, args: Value| {
        let r = call(s, "scxrd_edit", args);
        assert_eq!(r.result["ok"], true, "{:?}", r.result);
    };
    let undo = s.scxrd_undo.len();
    edit(&mut s, json!({"operation":"show","index":1}));
    assert_eq!(s.scxrd.shown, Some(1));
    assert_eq!(s.scxrd_undo.len(), undo, "showing is not an edit");
    let snapshot = call(&mut s, "scxrd_snapshot", json!({}));
    assert_eq!(snapshot.result["scxrd"]["shownLattice"], 1);
    edit(&mut s, json!({"operation":"keep","index":1,"keep":true}));
    assert_eq!(s.scxrd.selected, Some(0));
    assert_eq!(s.scxrd_undo.len(), undo + 1, "a tick is an edit");
    edit(&mut s, json!({"operation":"keep","index":0,"keep":false}));
    assert_eq!(s.scxrd.selected, Some(1), "the first kept lattice");
    assert_eq!(s.scxrd.stages[2].status, "complete");
    edit(&mut s, json!({"operation":"keep","index":1,"keep":false}));
    assert_eq!(s.scxrd.selected, None);
    assert_eq!(s.scxrd.stages[2].status, "attention");
    // `cell` keeps exactly one lattice (scripts).
    edit(&mut s, json!({"operation":"cell","index":1}));
    let kept: Vec<_> = s.scxrd.cells.iter().map(|c| c.kept).collect();
    assert_eq!((kept, s.scxrd.selected), (vec![false, true], Some(1)));
    edit(&mut s, json!({"operation":"show"}));
    assert_eq!(s.scxrd.shown, None);
}
#[test]
#[cfg(debug_assertions)]
fn development_reload_carries_the_series_calibration_settings_and_step_results() {
    let (dir, mut s) = dac_session();
    s.scxrd.excluded_frames = vec![0, 19];
    let mut config = dac_only(&s);
    config.threshold = 8.;
    config.dac_half_opening = 40.;
    assert_eq!(
        call(&mut s, "scxrd_settings", json!({"config":config})).result["ok"],
        true
    );
    assert_eq!(s.scxrd.stages[0].status, "complete");
    found_products(&mut s.scxrd);
    second_lattice(&mut s.scxrd);
    // A digest already known travels; unknown ones stay lazy (no hashing).
    s.scxrd.read(3).unwrap();
    let before = call(&mut s, "scxrd_frame", json!({"frame":10}));
    let old_mask = shown_mask(&before).unwrap();
    let old_dac = s.scxrd.shadows.as_ref().unwrap().report["dacSha256"].clone();
    let mut new = development_reload(&mut s, dir.path());
    let (a, b) = (&s.scxrd, &new.scxrd);
    assert_eq!(b.sources.len(), 20);
    assert!(
        a.sources
            .iter()
            .zip(&b.sources)
            .all(|(x, y)| x.path == y.path && x.frame == y.frame)
    );
    assert_eq!(b.sources[3].digest.get(), a.sources[3].digest.get());
    assert!(b.sources[4].digest.get().is_none());
    assert_eq!(b.shape, a.shape);
    assert!(b.config == a.config);
    assert_eq!(b.frame, 10);
    assert_eq!(b.excluded_frames, vec![0, 19]);
    // Rebuilt from the PONI; its stored axis now follows the axis setting.
    let (ga, gb) = (a.geometry.unwrap(), b.geometry.unwrap());
    assert_eq!(
        (ga.origin, ga.fast, ga.slow, ga.wavelength),
        (gb.origin, gb.fast, gb.slow, gb.wavelength)
    );
    assert_eq!(gb.axis, a.config.axis);
    assert!(b.poni.is_some() && b.calibration_source == a.calibration_source);
    // The geometric DAC mask is remade, identical, on the shown frame.
    assert_eq!(b.stages[0].status, "complete");
    assert_eq!(b.shadows.as_ref().unwrap().report["dacSha256"], old_dac);
    assert!(b.revision > a.revision);
    assert_eq!(
        (b.stages[1].status.as_str(), b.stages[2].status.as_str()),
        ("complete", "complete")
    );
    assert_eq!(b.stages[1].detail, "1 spot");
    assert_eq!(b.peaks.len(), 1);
    assert!(b.tracks[0].excluded);
    assert_eq!(b.cells[0].parameters, a.cells[0].parameters);
    assert_eq!(b.cells[0].found, lattices::Found::Rows);
    assert_eq!(b.selected, Some(0));
    let kept: Vec<_> = b.cells.iter().map(|c| c.kept).collect();
    assert_eq!((kept, b.shown), (vec![true, false], Some(1)));
    // Only the undo history (settings edits above) is reported as dropped.
    let notice = b.notice.clone().unwrap();
    assert!(notice.contains("undo history"), "{notice}");
    assert!(!notice.contains("step results"), "{notice}");
    assert!(new.scxrd_undo.is_empty());
    let snapshot = call(&mut new, "scxrd_snapshot", json!({}));
    assert_eq!(snapshot.result["scxrd"]["frame"], 10);
    assert_eq!(snapshot.result["scxrd"]["peakCount"], 1);
    assert_eq!(shown_mask(&snapshot).unwrap(), old_mask);
    let pixel = call(&mut new, "scxrd_pixel", json!({"x":64,"y":64}));
    assert_eq!(pixel.result["scxrdPixel"]["value"], 30.);
    // The restored workspace processes on: frames and settings still work.
    assert_eq!(
        call(&mut new, "scxrd_frame", json!({"frame":12})).result["ok"],
        true
    );
}
#[test]
#[cfg(debug_assertions)]
fn development_reload_carries_measured_masks_and_drops_the_omega_background() {
    let (dir, mut s) = dac_session();
    confirm(&mut s);
    // Measured masks (seat shadow, diamond spots) travel with their inputs
    // and are used as they are, not remade.
    let c = Config {
        seat_enabled: true,
        diamond_enabled: true,
        ..s.scxrd.config.clone()
    };
    call(&mut s, "scxrd_settings", json!({"config":c}));
    s.scxrd.set_diamonds(diamond::Diamonds {
        frames: vec![vec![5, 6]; 20],
        regions: 3,
    });
    assert!(s.scxrd.refresh_masks(&Control::default()));
    s.scxrd.stages[0].detail = "seat measured".into();
    let shadows = (**s.scxrd.shadows.as_ref().unwrap()).clone();
    found_products(&mut s.scxrd);
    let new = development_reload(&mut s, dir.path());
    let b = &new.scxrd;
    assert_eq!(b.stages[0].detail, "seat measured");
    assert_eq!(
        b.shadows.as_ref().unwrap().illumination,
        shadows.illumination
    );
    assert_eq!(b.diamonds.as_ref().unwrap().regions, 3);
    assert_eq!(b.peaks.len(), 1);
    // The omega background lives in the old processor's scratch file:
    // nothing derived from it is restored as complete.
    s.scxrd.background = Some(Arc::new(tempfile::NamedTempFile::new().unwrap()));
    let new = development_reload(&mut s, dir.path());
    let b = &new.scxrd;
    // The fast masks are remade from the settings; later steps are not kept.
    assert!(b.stages[1..].iter().all(|stage| stage.status == "pending"));
    assert!(b.peaks.is_empty() && b.cells.is_empty());
    assert!(b.notice.as_ref().unwrap().contains("omega background"));
    assert_eq!(b.sources.len(), 20);
    assert!(b.geometry.is_some());
}
#[test]
#[cfg(debug_assertions)]
fn unreadable_development_transfer_falls_back_to_a_reported_clean_state() {
    let (dir, mut s) = dac_session();
    confirm(&mut s);
    found_products(&mut s.scxrd);
    s.settings.bins = 777;
    s.settings.automatic_binning = false;
    let transfer = dir.path().join("development.dio");
    assert_eq!(
        call(&mut s, "development_checkpoint", json!({"path":transfer})).result["ok"],
        true
    );
    let products = transfer.with_extension("scxrd-products.msgpack");
    let essentials = transfer.with_extension("scxrd.msgpack");
    // Products unreadable (e.g. a changed struct): series kept, steps pending.
    std::fs::write(&products, b"not msgpack").unwrap();
    let mut new = Session::new(PathBuf::new());
    let r = call(&mut new, "development_restore", json!({"path":transfer}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(new.settings.bins, 777);
    assert_eq!(new.scxrd.sources.len(), 20);
    assert_eq!(new.scxrd.stages[0].status, "complete"); // geometric, remade
    assert!(new.scxrd.stages[1..].iter().all(|s| s.status == "pending"));
    assert!(new.scxrd.peaks.is_empty());
    assert!(
        new.scxrd
            .notice
            .as_ref()
            .unwrap()
            .starts_with("Backend updated. Not transferred: step results")
    );
    // Series unreadable: the powder session restores, SC is empty and says why.
    std::fs::write(&essentials, b"not msgpack").unwrap();
    let mut new = Session::new(PathBuf::new());
    let r = call(&mut new, "development_restore", json!({"path":transfer}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(new.settings.bins, 777);
    assert!(!new.scxrd.has_sources());
    let snapshot = call(&mut new, "scxrd_snapshot", json!({}));
    assert_eq!(snapshot.result["scxrd"]["frames"], 0);
    assert!(
        snapshot.result["scxrd"]["notice"]
            .as_str()
            .unwrap()
            .contains("could not be restored")
    );
    // A missing transfer file is the same clean, reported state.
    std::fs::remove_file(&essentials).unwrap();
    let mut new = Session::new(PathBuf::new());
    let r = call(&mut new, "development_restore", json!({"path":transfer}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert!(
        new.scxrd
            .notice
            .as_ref()
            .unwrap()
            .contains("could not be restored")
    );
}
#[test]
#[cfg(debug_assertions)]
fn development_reload_keeps_settings_without_frames_and_tolerates_removed_settings() {
    let dir = tempfile::tempdir().unwrap();
    let mut s = Session::new(PathBuf::new());
    let mut config = s.scxrd.config.clone();
    config.threshold = 8.;
    assert_eq!(
        call(&mut s, "scxrd_settings", json!({"config":config})).result["ok"],
        true
    );
    let new = development_reload(&mut s, dir.path());
    assert_eq!(new.scxrd.config.threshold, 8.);
    assert!(!new.scxrd.has_sources());
    // A setting the new code no longer knows is dropped by name, the rest kept.
    let mut saved = serde_json::to_value(&config).unwrap();
    saved["retired_knob"] = json!(3);
    let mut dropped = vec![];
    let restored = Config::from_development(saved, &mut dropped);
    assert_eq!(restored.threshold, 8.);
    assert_eq!(dropped, vec!["removed settings (retired_knob)".to_owned()]);
    // Settings the new checks reject fall back to the defaults.
    let mut dropped = vec![];
    let restored = Config::from_development(json!({"threshold":-1.}), &mut dropped);
    assert!(restored == Config::default());
    assert!(dropped[0].starts_with("processing settings"));
}

/// Quit (recovery checkpoint) and start again (recovery restore).
fn restart(old: &mut Session, checkpoint: &Path) -> (Session, Reply) {
    let r = call(
        old,
        "recovery_checkpoint",
        json!({"path":checkpoint,"ui":{}}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let mut new = Session::new(PathBuf::new());
    let r = call(&mut new, "recovery_restore", json!({"path":checkpoint}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    (new, r)
}
#[test]
fn restart_recovery_restores_the_single_crystal_session() {
    let (dir, mut s) = dac_session();
    s.scxrd.excluded_frames = vec![0, 19];
    let mut config = dac_only(&s);
    config.threshold = 8.;
    let status = call(&mut s, "recovery_status", json!({})).result["revision"].clone();
    assert_eq!(
        call(&mut s, "scxrd_settings", json!({"config":config})).result["ok"],
        true
    );
    // SC edits count as changes for the periodic recovery save.
    assert_ne!(
        call(&mut s, "recovery_status", json!({})).result["revision"],
        status
    );
    found_products(&mut s.scxrd);
    second_lattice(&mut s.scxrd);
    let before = call(&mut s, "scxrd_frame", json!({"frame":10}));
    let checkpoint = dir.path().join("recovery.dio");
    let (mut new, reply) = restart(&mut s, &checkpoint);
    assert!(
        reply.result["recoveryNotice"].is_null(),
        "{:?}",
        reply.result
    );
    let (a, b) = (&s.scxrd, &new.scxrd);
    assert_eq!(b.sources.len(), 20);
    assert!(
        a.sources
            .iter()
            .zip(&b.sources)
            .all(|(x, y)| x.path == y.path && x.frame == y.frame)
    );
    assert!(b.config == a.config);
    assert_eq!((b.frame, b.shape), (10, a.shape));
    assert_eq!(b.excluded_frames, vec![0, 19]);
    assert_eq!(b.calibration_source, a.calibration_source);
    assert_eq!(b.geometry.unwrap().origin, a.geometry.unwrap().origin);
    // Same build: step results come back, the DAC mask is remade.
    assert!(b.stages[..3].iter().all(|s| s.status == "complete"));
    assert_eq!(
        b.shadows.as_ref().unwrap().report["dacSha256"],
        a.shadows.as_ref().unwrap().report["dacSha256"]
    );
    assert_eq!((b.peaks.len(), b.tracks.len(), b.selected), (1, 1, Some(0)));
    let kept: Vec<_> = b.cells.iter().map(|c| c.kept).collect();
    assert_eq!((kept, b.shown), (vec![true, false], Some(1)));
    assert!(b.notice.is_none(), "{:?}", b.notice);
    let after = call(&mut new, "scxrd_snapshot", json!({}));
    assert_eq!(shown_mask(&after), shown_mask(&before));
    // A user project never carries the SC session.
    let project = dir.path().join("user.dio");
    assert_eq!(
        call(&mut new, "save_project", json!({"path":project})).result["ok"],
        true
    );
    let file = hdf5::File::open(&project).unwrap();
    assert!(!file.link_exists("single_crystal_recovery"));
    assert!(!file.link_exists("single_crystal_recovery_products"));
    // Without SC state the recovery file carries none either.
    let mut plain = Session::new(PathBuf::new());
    let empty = dir.path().join("plain.dio");
    let (restored, _) = restart(&mut plain, &empty);
    assert!(
        !hdf5::File::open(&empty)
            .unwrap()
            .link_exists("single_crystal_recovery")
    );
    assert!(!restored.scxrd.needs_development_preservation());
}
#[test]
fn restart_recovery_without_the_frames_keeps_settings_and_says_so() {
    let (dir, mut s) = dac_session();
    let mut config = dac_only(&s);
    config.threshold = 8.;
    call(&mut s, "scxrd_settings", json!({"config":config}));
    found_products(&mut s.scxrd);
    let checkpoint = dir.path().join("recovery.dio");
    let r = call(
        &mut s,
        "recovery_checkpoint",
        json!({"path":checkpoint,"ui":{}}),
    );
    assert_eq!(r.result["ok"], true);
    for source in &s.scxrd.sources {
        let _ = std::fs::remove_file(&source.path);
    }
    let mut new = Session::new(PathBuf::new());
    let r = call(&mut new, "recovery_restore", json!({"path":checkpoint}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let notice = r.result["recoveryNotice"].as_str().unwrap();
    assert!(notice.contains("no longer available"), "{notice}");
    let c = &new.scxrd;
    assert!(!c.has_sources() && c.peaks.is_empty());
    assert_eq!(c.config.threshold, 8.);
    assert!(!c.config.confirmed);
    assert!(c.poni.is_some() && c.calibration_source.is_some());
    let snapshot = call(&mut new, "scxrd_snapshot", json!({}));
    assert_eq!(snapshot.result["scxrd"]["frames"], 0);
    assert!(
        snapshot.result["scxrd"]["notice"]
            .as_str()
            .unwrap()
            .contains("Reopen them")
    );
}
/// A session saved before the cell mask switch was split from the whole
/// step (`masks_enabled`, stage report without per-mask numbers) reloads with
/// the switch kept and the numbers made, without a "removed settings" note.
#[test]
fn reload_from_before_the_cell_mask_switch_keeps_it() {
    let (_dir, mut s) = dac_session();
    confirm(&mut s);
    let saved = s.scxrd.transfer("recovery", false).unwrap();
    let mut essentials: Value = rmp_serde::from_slice(&saved.essentials).unwrap();
    let config = essentials["config"].as_object_mut().unwrap();
    config.remove("cell_masks_enabled");
    config.insert("masks_enabled".into(), json!(false));
    let mut products: Value = rmp_serde::from_slice(&saved.products).unwrap();
    products["stages"][0]
        .as_object_mut()
        .unwrap()
        .remove("masks");
    for kind in [Transfer::Development, Transfer::Recovery] {
        let (c, summary) = Crystal::restore(
            Ok(rmp_serde::to_vec_named(&essentials).unwrap()),
            Ok(rmp_serde::to_vec_named(&products).unwrap()),
            "recovery",
            kind,
            &Control::default(),
        );
        assert!(!c.config.cell_masks_enabled);
        assert!(c.shadows.is_none(), "cell masks stay off");
        assert!(
            summary
                .as_deref()
                .is_none_or(|s| !s.contains("removed settings")),
            "{summary:?}"
        );
        assert_eq!(c.stages[0].status, "complete");
        assert!(c.stages[0].masks.is_some());
    }
}
#[test]
fn restart_recovery_from_another_version_or_build_falls_back_cleanly() {
    let (_dir, mut s) = dac_session();
    confirm(&mut s);
    found_products(&mut s.scxrd);
    let saved = s.scxrd.transfer("recovery", false).unwrap();
    let edit = |bytes: &[u8], key: &str, value: Value| {
        let mut v: Value = rmp_serde::from_slice(bytes).unwrap();
        v[key] = value;
        rmp_serde::to_vec_named(&v).unwrap()
    };
    let control = Control::default();
    // Another format version: nothing of the SC session, a clear message.
    let (c, summary) = Crystal::restore(
        Ok(edit(&saved.essentials, "version", json!(99))),
        Ok(saved.products.clone()),
        "recovery",
        Transfer::Recovery,
        &control,
    );
    assert!(!c.has_sources());
    assert!(summary.unwrap().contains("another Dioptas version"));
    // Step results made by another build: series kept, steps pending (the
    // geometric DAC mask is remade).
    let (c, summary) = Crystal::restore(
        Ok(saved.essentials.clone()),
        Ok(edit(&saved.products, "identity", json!("older build"))),
        "recovery",
        Transfer::Recovery,
        &control,
    );
    assert_eq!(c.sources.len(), 20);
    assert_eq!(c.stages[0].status, "complete");
    assert!(c.stages[1..].iter().all(|s| s.status == "pending") && c.peaks.is_empty());
    assert!(summary.unwrap().contains("another Dioptas build"));
    // The development reload ignores the build identity (code changes).
    let (c, summary) = Crystal::restore(
        Ok(saved.essentials.clone()),
        Ok(edit(&saved.products, "identity", json!("older build"))),
        "recovery",
        Transfer::Development,
        &control,
    );
    assert_eq!(c.peaks.len(), 1);
    assert!(summary.is_none(), "{summary:?}");
    // Unreadable bytes never fail the restore.
    let (c, summary) = Crystal::restore(
        Ok(b"garbage".to_vec()),
        Err("missing".into()),
        "recovery",
        Transfer::Recovery,
        &control,
    );
    assert!(!c.has_sources() && summary.is_some());
}

/// The seat shadow on the Eiger scan covers the dark cell shadow: at the
/// start and end of the scan every usable pixel of a dark 16 px block
/// (mean below 5 counts; lit background is 17-35) is masked, apart from the
/// beam stop at the detector centre, and the frame in the middle of the scan
/// (fully lit) gets no seat mask.
#[test]
#[ignore = "Local Eiger scan and PONI required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_seat_shadow_covers_the_dark_region() {
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let mut s = Session::new(PathBuf::new());
    call(
        &mut s,
        "scxrd_load",
        json!({"path":root.join("eiger_0000.h5")}),
    );
    s.scxrd.config = Config {
        axis: [-1., 0., 0.],
        dac_enabled: false,
        seat_enabled: true,
        seat_threshold: 0.6,
        seat_guard: 16,
        shadow_block: 16,
        ..dac_only(&s)
    };
    let poni = root.join("CeO2_20240620_1849_dioptas.poni");
    call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    s.scxrd.config.omega_start = -37.5;
    s.scxrd.config.dac_half_opening = 41.;
    for round in 0..3 {
        s.scxrd.invalidate(0);
        s.scxrd.parts = Default::default();
        let clock = std::time::Instant::now();
        s.scxrd.prepare_shadows(&Control::default()).unwrap();
        let t = clock.elapsed().as_secs_f64();
        let m = &s.scxrd.shadows.as_ref().unwrap().report["seatMeasurement"];
        eprintln!(
            "seat shadow (round {round}) {t:.3} s: {} {} frames, read {:.3} s, estimate {:.3} s, held out {}",
            m["route"],
            m["frames"].as_array().unwrap().len(),
            m["seconds"]["read"],
            m["seconds"]["estimate"],
            m["heldOutErrors"]
        );
    }
    let c = &s.scxrd;
    let [h, w] = c.shape;
    for frame in [0, 10, 72, 133, 143] {
        let raw = c.decode(frame).unwrap();
        let base = c.base_mask(&raw, frame);
        let mask = c.mask_for(&raw, frame);
        let (mut dark, mut open, mut masked) = (0, 0, 0);
        for by in 0..h / 16 {
            for bx in 0..w / 16 {
                let pixels: Vec<usize> = (0..256)
                    .map(|k| (by * 16 + k / 16) * w + bx * 16 + k % 16)
                    .filter(|&i| !base[i])
                    .collect();
                if pixels.is_empty() {
                    continue;
                }
                masked += pixels.iter().filter(|&&i| mask[i]).count();
                let mean = pixels.iter().map(|&i| raw[i]).sum::<f64>() / pixels.len() as f64;
                let centre = by.abs_diff(h / 32) <= 4 && bx.abs_diff(w / 32) <= 4;
                if mean < 5. && !centre {
                    dark += 1;
                    open += usize::from(pixels.iter().any(|&i| !mask[i]));
                }
            }
        }
        eprintln!("frame {frame}: {dark} dark blocks, {open} not fully masked, {masked} px masked");
        assert_eq!(open, 0, "frame {frame}");
        if frame == 72 {
            assert_eq!(masked, 0);
        } else {
            assert!(dark > 1000, "frame {frame}");
        }
    }
}

/// Frame reading rates on the Eiger scan, all frames in parallel on the
/// worker pool: dioptrin-io's raw chunk reader alone, the general
/// `Image::open` path, and the single-crystal paths. Block medians straight
/// from the raw chunk equal those of the decoded frame.
#[test]
#[ignore = "Local Eiger scan required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_frame_reading_rates() {
    use dioptrin_io::hdf5::{
        Limits,
        raw::{FrameBuffer, RawReader},
    };
    use rayon::prelude::*;
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let master = root.join("eiger_0000.h5");
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"path":master}));
    let c = &s.scxrd;
    let n = c.sources.len();
    let all: Vec<usize> = (0..n).collect();
    let rate = |label: &str, run: &dyn Fn()| {
        run(); // warm file cache and readers
        let clock = std::time::Instant::now();
        run();
        let t = clock.elapsed().as_secs_f64();
        eprintln!("{label:<44} {:>7.3} s  {:>6.0} frames/s", t, n as f64 / t);
    };
    let reader = RawReader::open_snapshot(
        &master,
        "/entry_0000/ESRF-ID11/eiger/data",
        Limits::default(),
    )
    .unwrap();
    rate("dioptrin-io RawReader (u32, no copy)", &|| {
        crate::worker_pool::install(|| {
            all.par_iter().for_each_init(FrameBuffer::default, |b, &f| {
                reader.read_frame_into(f, b).unwrap()
            })
        });
    });
    rate("Image::open per frame (before)", &|| {
        crate::worker_pool::install(|| {
            all.par_iter().for_each(|&f| {
                crate::image::Image::open(&master, &json!({"frame":f})).unwrap();
            })
        });
    });
    rate("Crystal::decode (raw + f64 rows-up)", &|| {
        crate::worker_pool::install(|| {
            all.par_iter().for_each(|&f| {
                c.decode(f).unwrap();
            })
        });
    });
    rate("Crystal::read (decode + SHA-256 digest)", &|| {
        crate::worker_pool::install(|| {
            all.par_iter().for_each(|&f| {
                c.read(f).unwrap();
            })
        });
    });
    rate("Crystal::frame_medians (16 px blocks)", &|| {
        crate::worker_pool::install(|| {
            all.par_iter().for_each(|&f| {
                c.frame_medians(f, 16).unwrap();
            })
        });
    });
    eprintln!("workers: {}", crate::worker_pool::threads());
    for f in [0, 50, 143] {
        let raw = c.decode(f).unwrap();
        let expected = dac_fit::block_medians(&raw, &c.base_mask(&raw, f), c.shape, 16);
        let found = c.frame_medians(f, 16).unwrap();
        assert!(
            expected
                .iter()
                .zip(&found)
                .all(|(a, b)| a == b || (a.is_nan() && b.is_nan())),
            "frame {f}"
        );
    }
}

/// Seat masks from a few measured frames against the mask measured on every
/// frame, on the frames that were not measured (Eiger scan, defaults 0.6 /
/// 16 px / 16 px blocks). Edge error: differing pixels per reference edge
/// pixel (mean) and the largest per-row difference (max).
#[test]
#[ignore = "Local Eiger scan required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_seat_sampling_accuracy() {
    use rayon::prelude::*;
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let mut s = Session::new(PathBuf::new());
    call(
        &mut s,
        "scxrd_load",
        json!({"path":root.join("eiger_0000.h5")}),
    );
    let poni = root.join("CeO2_20240620_1849_dioptas.poni");
    call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    s.scxrd.config.axis = [-1., 0., 0.];
    s.scxrd.config.omega_start = -37.5;
    s.scxrd.config.dac_half_opening = 41.;
    let c = &s.scxrd;
    let g = c.initial_geometry.unwrap();
    let rotation = dac_fit::Rotation::new(&c.config, &g).unwrap();
    let [h, w] = c.shape;
    let (block, t, guard) = (16, 0.6, 1.);
    let dims = [h.div_ceil(block), w.div_ceil(block)];
    let n = c.sources.len();
    let medians: Vec<Vec<f64>> = crate::worker_pool::install(|| {
        (0..n)
            .into_par_iter()
            .map(|f| c.frame_medians(f, block).unwrap())
            .collect()
    });
    let shadows = |seat: Vec<u8>| Shadows {
        first: 0,
        last: n - 1,
        block,
        columns: dims[1],
        cells: dims[0] * dims[1],
        illumination: vec![],
        dac: vec![],
        seat,
        report: Value::Null,
    };
    let masks = |sh: &Shadows| -> Vec<Vec<bool>> {
        crate::worker_pool::install(|| {
            (0..n)
                .into_par_iter()
                .map(|f| {
                    let mut m = vec![false; h * w];
                    sh.fill(f, &mut m, w);
                    m
                })
                .collect()
        })
    };
    let all: Vec<(usize, Vec<f64>)> = medians.iter().cloned().enumerate().collect();
    let reference = masks(&shadows(
        shadows::SeatRatios::new(&all, dims, true)
            .unwrap()
            .levels(n, t, guard, true),
    ));
    let rays = std::sync::Arc::new(dac_fit::block_rays(&g, c.shape, block).unwrap());
    let (start, opening) = (c.config.omega_start, c.config.dac_half_opening);
    let coordinates: std::sync::Arc<Vec<Vec<[f32; 2]>>> = std::sync::Arc::new(
        (0..n)
            .map(|f| {
                rotation
                    .cone_coordinates(&rays, start, opening, f)
                    .iter()
                    .map(|&[p, a]| [p as f32, a as f32])
                    .collect()
            })
            .collect(),
    );
    let compare = |label: &str, picked: &[usize], cone: bool| {
        let measured: Vec<(usize, Vec<f64>)> =
            picked.iter().map(|&f| (f, medians[f].clone())).collect();
        let mut r = shadows::SeatRatios::new(&measured, dims, true).unwrap();
        if cone {
            r = r.with_cone(coordinates.clone());
        }
        let found = masks(&shadows(r.levels(n, t, guard, true)));
        let (mut xor, mut edge, mut worst_row, mut worst_share) = (0usize, 0usize, 0usize, 0f64);
        let (mut missed, mut masked_ref, mut far) = (0usize, 0usize, vec![]);
        for f in (0..n).filter(|f| !picked.contains(f)) {
            let (r, m) = (&reference[f], &found[f]);
            missed += r.iter().zip(m).filter(|&(&a, &b)| a && !b).count();
            masked_ref += r.iter().filter(|&&a| a).count();
            // Distance (px, 4 px grid, chessboard) of differing cells to the reference edge.
            let (gh, gw) = (h / 4, w / 4);
            let cell = |v: &Vec<bool>, y: usize, x: usize| v[(4 * y + 2) * w + 4 * x + 2];
            let mut dist = vec![usize::MAX; gh * gw];
            let mut queue = std::collections::VecDeque::new();
            for y in 0..gh {
                for x in 0..gw {
                    let here = cell(r, y, x);
                    let edge_cell = (x + 1 < gw && cell(r, y, x + 1) != here)
                        || (y + 1 < gh && cell(r, y + 1, x) != here);
                    if edge_cell {
                        dist[y * gw + x] = 0;
                        queue.push_back(y * gw + x);
                    }
                }
            }
            while let Some(i) = queue.pop_front() {
                let (y, x) = ((i / gw) as isize, (i % gw) as isize);
                for (dy, dx) in [
                    (-1, -1),
                    (-1, 0),
                    (-1, 1),
                    (0, -1),
                    (0, 1),
                    (1, -1),
                    (1, 0),
                    (1, 1),
                ] {
                    let (yy, xx) = (y + dy, x + dx);
                    if yy >= 0 && xx >= 0 && (yy as usize) < gh && (xx as usize) < gw {
                        let j = yy as usize * gw + xx as usize;
                        if dist[j] == usize::MAX {
                            dist[j] = dist[i] + 1;
                            queue.push_back(j);
                        }
                    }
                }
            }
            let mut stray = 0;
            for y in 0..gh {
                for x in 0..gw {
                    if cell(r, y, x) != cell(m, y, x) {
                        if dist[y * gw + x] == usize::MAX {
                            stray += 1;
                        } else {
                            far.push(4 * dist[y * gw + x]);
                        }
                    }
                }
            }
            if stray > 0 {
                let share =
                    |v: &Vec<bool>| 100. * v.iter().filter(|&&b| b).count() as f64 / v.len() as f64;
                eprintln!(
                    "    {label}: frame {f} has no reference edge (reference {:.1} % masked, found {:.1} %)",
                    share(r),
                    share(m)
                );
            }
            for y in 0..h {
                let row = (0..w).filter(|&x| r[y * w + x] != m[y * w + x]).count();
                xor += row;
                worst_row = worst_row.max(row);
                edge += (1..w).filter(|&x| r[y * w + x] != r[y * w + x - 1]).count();
            }
            let share = |v: &Vec<bool>| v.iter().filter(|&&b| b).count() as f64 / (h * w) as f64;
            worst_share = worst_share.max((share(r) - share(m)).abs());
        }
        if let Ok(dir) = std::env::var("SEAT_RENDER_DIR")
            && std::env::var("SEAT_RENDER").is_ok_and(|v| v == label)
        {
            // Frames with the most differing pixels: grey counts, red both,
            // blue shadow missed, yellow lit masked.
            let mut worst: Vec<(usize, usize)> = (0..n)
                .filter(|f| !picked.contains(f))
                .map(|f| {
                    (
                        reference[f]
                            .iter()
                            .zip(&found[f])
                            .filter(|(a, b)| a != b)
                            .count(),
                        f,
                    )
                })
                .collect();
            worst.sort_unstable_by(|a, b| b.cmp(a));
            for &(_, f) in worst.iter().take(4) {
                let raw = c.decode(f).unwrap();
                let mut rgb = vec![0u8; (h / 2) * (w / 2) * 3];
                for y in 0..h / 2 {
                    for x in 0..w / 2 {
                        let i = (2 * y) * w + 2 * x;
                        let g = ((raw[i].min(40.) / 40.) * 200.) as u8;
                        let px = match (reference[f][i], found[f][i]) {
                            (true, true) => [g / 2 + 110, g / 3, g / 3],
                            (true, false) => [0, 80, 255],
                            (false, true) => [255, 220, 0],
                            _ => [g, g, g],
                        };
                        rgb[(y * (w / 2) + x) * 3..][..3].copy_from_slice(&px);
                    }
                }
                let path = PathBuf::from(&dir).join(format!(
                    "{}_frame{f:03}.png",
                    label.replace([' ', ','], "_")
                ));
                let mut e =
                    png::Encoder::new(File::create(path).unwrap(), (w / 2) as u32, (h / 2) as u32);
                e.set_color(png::ColorType::Rgb);
                e.write_header().unwrap().write_image_data(&rgb).unwrap();
            }
        }
        far.sort_unstable();
        let pct = |q: f64| {
            far.get(((far.len() as f64 - 1.) * q) as usize)
                .copied()
                .unwrap_or(0)
        };
        let _ = worst_row;
        eprintln!(
            "{label:<24} {:>3} fr  edge err mean {:>5.1} px, p95 {:>3} px, max {:>3} px | missed {:.2} % of shadow | worst share diff {:.2} %",
            picked.len(),
            xor as f64 / edge.max(1) as f64,
            pct(0.95),
            pct(1.),
            100. * missed as f64 / masked_ref.max(1) as f64,
            100. * worst_share
        );
    };
    let predicted: Vec<f64> = (0..n)
        .map(|f| {
            let co = rotation.cone_coordinates(&rays, start, opening, f);
            co.iter().filter(|c| c[0] > 0.).count() as f64 / co.len() as f64
        })
        .collect();
    for count in [16, 24, 32, 40] {
        let stride = (n - 1).div_ceil(count - 1);
        let mut uniform: Vec<usize> = (0..n).step_by(stride).collect();
        if *uniform.last().unwrap() != n - 1 {
            uniform.push(n - 1);
        }
        compare(&format!("interp, uniform {count}"), &uniform, false);
        compare(&format!("cone, uniform {count}"), &uniform, true);
        let motion = shadows::seat_sample_by_motion(&predicted, count);
        compare(&format!("interp, by motion {count}"), &motion, false);
        compare(&format!("cone, by motion {count}"), &motion, true);
    }
}

/// Identity of each prepared mask part (0: none).
fn part_ids(c: &Crystal) -> [usize; 3] {
    let id = |a: Option<*const u8>| a.map_or(0, |p| p as usize);
    [
        id(c.parts
            .dac
            .as_ref()
            .map(|p| Arc::as_ptr(&p.data) as *const u8)),
        id(c.parts
            .seat
            .as_ref()
            .map(|p| Arc::as_ptr(&p.data) as *const u8)),
        id(c.parts
            .diamonds
            .as_ref()
            .map(|p| Arc::as_ptr(&p.data) as *const u8)),
    ]
}
fn settings(s: &mut Session, c: &Config) -> Reply {
    let r = call(s, "scxrd_settings", json!({"config":c}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    r
}

/// The DAC opening, seat shadow and diamond spots are independent: switching
/// one off or on, or changing its settings, leaves the others' parts as they
/// were and shown in the same reply; a part switched back on with unchanged
/// inputs returns without recomputation; the seat shadow follows its
/// threshold in the settings reply; undo brings the previous parts back.
#[test]
fn prepared_masks_are_independent() {
    // As for a large scan: diamond spots are found on Run only.
    masks::DIAMOND_REPLY_LIMIT.set(0);
    let (_dir, mut s) = synthetic_shadow(Some((-45., 30.)), 90, -45., 30.);
    let all = Config {
        seat_enabled: true,
        seat_threshold: 0.5,
        seat_guard: 4,
        diamond_enabled: true,
        ..s.scxrd.config.clone()
    };
    // Diamond spots wait for Run; DAC and seat show at once.
    let r = settings(&mut s, &all);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "pending");
    assert!(shown_mask(&r).is_some());
    let r = call(&mut s, "scxrd_run", json!({"stage":0}));
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    let ids = part_ids(&s.scxrd);
    assert!(ids.iter().all(|&i| i != 0), "{ids:?}");
    // A frame where the DAC mask and the seat shadow differ.
    let sh = s.scxrd.shadows.clone().unwrap();
    let frame = (0..90)
        .find(|&f| {
            let cells = f * sh.cells..(f + 1) * sh.cells;
            let (d, i) = (&sh.dac[cells.clone()], &sh.illumination[cells]);
            d.iter().any(|&v| v) && d.iter().any(|&v| !v) && d != i
        })
        .expect("a frame with a partial, differing shadow");
    let full = shown_mask(&call(&mut s, "scxrd_frame", json!({"frame":frame}))).unwrap();
    let active = |s: &Session| {
        let c = &s.scxrd;
        let sh = c.shadows.as_ref();
        (
            sh.is_some_and(|x| !x.dac.is_empty()),
            sh.is_some_and(|x| !x.seat.is_empty()),
            c.diamonds.is_some(),
        )
    };
    // DAC off: seat and diamond spots stay, still shown, stage complete.
    let r = settings(
        &mut s,
        &Config {
            dac_enabled: false,
            ..all.clone()
        },
    );
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert_eq!(active(&s), (false, true, true));
    assert_eq!(part_ids(&s.scxrd), ids, "parts kept");
    let without_dac = shown_mask(&r).unwrap();
    assert_ne!(without_dac, full);
    // DAC back on: the same part returns, the same mask.
    let r = settings(&mut s, &all);
    assert_eq!(part_ids(&s.scxrd), ids);
    assert_eq!(shown_mask(&r).unwrap(), full);
    // Seat off: DAC and diamond spots stay.
    let r = settings(
        &mut s,
        &Config {
            seat_enabled: false,
            ..all.clone()
        },
    );
    assert_eq!(active(&s), (true, false, true));
    assert_eq!(part_ids(&s.scxrd), ids);
    assert!(shown_mask(&r).is_some());
    // Diamond spots off: DAC and seat stay.
    settings(
        &mut s,
        &Config {
            diamond_enabled: false,
            ..all.clone()
        },
    );
    assert_eq!(active(&s), (true, true, false));
    assert_eq!(part_ids(&s.scxrd), ids);
    // Back to all three: nothing recomputed, stage complete.
    let r = settings(&mut s, &all);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert_eq!(part_ids(&s.scxrd), ids);
    // Seat threshold: only the seat shadow is remade, in this reply.
    let r = settings(
        &mut s,
        &Config {
            seat_threshold: 0.9,
            ..all.clone()
        },
    );
    let after = part_ids(&s.scxrd);
    assert_eq!((after[0], after[2]), (ids[0], ids[2]));
    assert_ne!(after[1], ids[1]);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert_ne!(
        shown_mask(&r).unwrap(),
        full,
        "the shown frame follows at once"
    );
    // Undo brings the previous seat shadow back.
    let r = call(&mut s, "scxrd_edit", json!({"operation":"undo"}));
    assert_eq!(part_ids(&s.scxrd), ids);
    assert_eq!(shown_mask(&r).unwrap(), full);
    // Diamond settings: the candidates found on Run are only re-filtered, at
    // once; DAC and seat shadow stay as they were.
    let candidates = s
        .scxrd
        .parts
        .diamond_candidates
        .as_ref()
        .unwrap()
        .data
        .clone();
    let r = settings(
        &mut s,
        &Config {
            diamond_tolerance: 5.,
            ..all.clone()
        },
    );
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    let after = part_ids(&s.scxrd);
    assert_eq!((after[0], after[1]), (ids[0], ids[1]));
    assert_eq!(active(&s), (true, true, true));
    assert!(Arc::ptr_eq(
        &s.scxrd.parts.diamond_candidates.as_ref().unwrap().data,
        &candidates
    ));
    assert!(shown_mask(&r).is_some());
    let ids = part_ids(&s.scxrd);
    // Half-opening: the DAC mask is remade; the diamond spots stay.
    let all = Config {
        diamond_tolerance: 5.,
        ..all
    };
    settings(
        &mut s,
        &Config {
            dac_half_opening: 25.,
            ..all.clone()
        },
    );
    let after = part_ids(&s.scxrd);
    assert_ne!(after[0], ids[0]);
    assert_eq!(after[2], ids[2]);
    assert_eq!(s.scxrd.stages[0].status, "complete");
}

/// Later steps are invalidated when the mask in use changes, and kept when
/// a change leaves it as it was.
#[test]
fn a_changed_mask_invalidates_later_steps() {
    masks::DIAMOND_REPLY_LIMIT.set(0);
    let (_dir, mut s) = synthetic_shadow(Some((-45., 30.)), 90, -45., 30.);
    let c = Config {
        seat_enabled: true,
        seat_threshold: 0.5,
        seat_guard: 4,
        ..s.scxrd.config.clone()
    };
    settings(&mut s, &c);
    found_products(&mut s.scxrd);
    // Diamond spots switched on but not run: the mask in use is unchanged.
    settings(
        &mut s,
        &Config {
            diamond_enabled: true,
            ..c.clone()
        },
    );
    assert_eq!(s.scxrd.stages[1].status, "complete");
    assert_eq!(s.scxrd.stages[0].status, "pending");
    settings(&mut s, &c);
    assert_eq!(s.scxrd.stages[1].status, "complete");
    // The seat shadow switched off: later steps must be redone.
    settings(
        &mut s,
        &Config {
            seat_enabled: false,
            ..c
        },
    );
    assert_eq!(s.scxrd.stages[1].status, "pending");
    assert!(s.scxrd.peaks.is_empty());
}

/// A 128×128 four-frame series with broad bright spots at different places
/// per frame, and the fixture calibration; diamond spots on, nothing else.
fn diamond_session() -> (tempfile::TempDir, Session) {
    let (fixture, _probe) = dac_session();
    let dir = tempfile::tempdir().unwrap();
    let mut paths = vec![];
    for f in 0..4 {
        let mut counts = vec![30u16; 128 * 128];
        for (k, &(cx, cy, r)) in [
            (20., 30., 3.),
            (90., 60., 4.),
            (60., 110., 2.),
            (110., 15., 5.),
        ]
        .iter()
        .enumerate()
        {
            let (cx, cy) = (cx + 7. * f as f64, cy - 3. * f as f64 + k as f64);
            for y in 0..128 {
                for x in 0..128 {
                    let r2 = (x as f64 - cx).powi(2) + (y as f64 - cy).powi(2);
                    let v = f64::from(counts[y * 128 + x]) + 60000. * (-r2 / (2. * r * r)).exp();
                    counts[y * 128 + x] = v.min(65000.) as u16;
                }
            }
        }
        let path = dir.path().join(format!("spots_{f:04}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&path).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray16>(128, 128, &counts)
            .unwrap();
        paths.push(path.to_string_lossy().into_owned());
    }
    let poni = dir.path().join("detector.poni");
    std::fs::copy(fixture.path().join("detector.poni"), &poni).unwrap();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    (dir, s)
}

/// Diamond spots are found inside the settings reply for a small scan;
/// changing Min. size, d tolerance or Margin re-filters the cached candidates
/// (no new scan) and gives exactly a fresh detection, shown in the same reply.
#[test]
fn diamond_settings_refilter_cached_candidates_like_a_fresh_run() {
    let (_dir, mut s) = diamond_session();
    let base = Config {
        dac_enabled: false,
        diamond_enabled: true,
        diamond_tolerance: 20.,
        diamond_min_size: 1,
        ..dac_only(&s)
    };
    let r = settings(&mut s, &base);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    let candidates = s
        .scxrd
        .parts
        .diamond_candidates
        .as_ref()
        .unwrap()
        .data
        .clone();
    let mut accepted = 0;
    for (min_size, tolerance) in [(1, 20.), (10, 20.), (40, 20.), (1, 1.), (10, 5.)] {
        let c = Config {
            diamond_min_size: min_size,
            diamond_tolerance: tolerance,
            ..base.clone()
        };
        let r = settings(&mut s, &c);
        assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
        // Re-filtered, not found again.
        assert!(Arc::ptr_eq(
            &s.scxrd.parts.diamond_candidates.as_ref().unwrap().data,
            &candidates
        ));
        let mut fresh = s.scxrd.clone();
        fresh.parts = Default::default();
        fresh.invalidate(0);
        fresh.prepare_diamonds(&Control::default()).unwrap();
        let (a, b) = (
            s.scxrd.diamonds.as_ref().unwrap(),
            fresh.diamonds.as_ref().unwrap(),
        );
        assert_eq!(
            (&a.frames, a.regions),
            (&b.frames, b.regions),
            "{min_size} {tolerance}"
        );
        accepted += a.regions;
        let shown = shown_mask(&r);
        assert_eq!(shown.is_some(), !a.frames[s.scxrd.frame].is_empty());
    }
    assert!(accepted > 0);
    // The detection level also only re-filters: a lower level finds more.
    let mut found = vec![];
    for level in [10., 6., 20.] {
        let c = Config {
            diamond_level: level,
            ..base.clone()
        };
        let r = settings(&mut s, &c);
        assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
        assert!(Arc::ptr_eq(
            &s.scxrd.parts.diamond_candidates.as_ref().unwrap().data,
            &candidates
        ));
        let mut fresh = s.scxrd.clone();
        fresh.parts = Default::default();
        fresh.invalidate(0);
        fresh.prepare_diamonds(&Control::default()).unwrap();
        assert_eq!(
            s.scxrd.diamonds.as_ref().unwrap().frames,
            fresh.diamonds.as_ref().unwrap().frames,
            "level {level}"
        );
        found.push(
            s.scxrd
                .diamonds
                .as_ref()
                .unwrap()
                .frames
                .iter()
                .map(Vec::len)
                .sum::<usize>(),
        );
    }
    assert!(found[1] >= found[0] && found[0] >= found[2], "{found:?}");
    // The margin also only re-filters, and each larger margin masks more.
    let mut areas = vec![];
    for margin in [0, 10, 30] {
        let c = Config {
            diamond_margin: margin,
            ..base.clone()
        };
        let r = settings(&mut s, &c);
        assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
        assert!(Arc::ptr_eq(
            &s.scxrd.parts.diamond_candidates.as_ref().unwrap().data,
            &candidates
        ));
        areas.push(
            s.scxrd
                .diamonds
                .as_ref()
                .unwrap()
                .frames
                .iter()
                .map(Vec::len)
                .sum::<usize>(),
        );
    }
    assert!(areas.windows(2).all(|a| a[0] < a[1]), "{areas:?}");
}

/// Diamond spots on the Eiger scan: the faint broad reflections of frame 63
/// (+0.4…+1.2 % from diamond spacings, seen on several frames) are masked,
/// its compact sample reflections are not; the intense diamond reflections
/// of frames 50 and 82 are masked. Positions in stored (raw) rows.
#[test]
#[ignore = "Local Eiger scan and PONI required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_diamond_spots_mask_broad_reflections_and_keep_sample_spots() {
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let mut s = Session::new(PathBuf::new());
    call(
        &mut s,
        "scxrd_load",
        json!({"path":root.join("eiger_0000.h5")}),
    );
    let poni = root.join("CeO2_20240620_1849_dioptas.poni");
    call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    s.scxrd.config.diamond_enabled = true;
    let c = &s.scxrd;
    let clock = std::time::Instant::now();
    let scans = c.all_diamond_scans(&Control::default()).unwrap();
    let candidates = c.diamond_regions(&scans).unwrap();
    let scan = clock.elapsed().as_secs_f64();
    let (lines, tolerance) = c.diamond_lines().unwrap();
    let selection = diamond::Selection {
        lines: &lines,
        tolerance,
        min_size: c.config.diamond_min_size,
        margin: c.config.diamond_margin,
        shape: c.shape,
    };
    let masks: Vec<(Vec<u32>, usize)> = candidates
        .iter()
        .map(|k| diamond::accept(k, &selection))
        .collect();
    let [h, w] = c.shape;
    let masked = |f: usize, x: usize, raw_y: usize| {
        masks[f]
            .0
            .binary_search(&(((h - 1 - raw_y) * w + x) as u32))
            .is_ok()
    };
    for (x, y) in [
        (1530, 1674),
        (1626, 654),
        (230, 482),
        (118, 1562),
        (1162, 1994),
        (446, 1946),
    ] {
        assert!(masked(63, x, y), "broad diamond reflection at {x},{y}");
    }
    for (x, y) in [
        (862, 1322),
        (286, 1158),
        (278, 1234),
        (302, 1526),
        (1414, 1878),
        (1714, 1158),
    ] {
        assert!(!masked(63, x, y), "compact sample reflection at {x},{y}");
    }
    for (f, x, y) in [(50, 766, 750), (82, 478, 1570), (143, 1530, 1678)] {
        assert!(
            masked(f, x, y),
            "intense diamond reflection frame {f} at {x},{y}"
        );
    }
    let total: usize = masks.iter().map(|m| m.1).sum();
    let share =
        masks.iter().map(|m| m.0.len()).sum::<usize>() as f64 / (masks.len() * h * w) as f64;
    eprintln!(
        "candidates of {} frames {scan:.3} s; {total} diamond spots, {:.2} % of pixels; frame 63: {} spots",
        c.sources.len(),
        100. * share,
        masks[63].1
    );
}

/// The diamond anvil cell masks can be switched off together (data not taken
/// in a cell): no cell mask is shown or applied, stage 0 counts as complete
/// (nothing else is on here), only unusable pixels stay masked. Switched on
/// again, the per-mask choices and the cached masks come back without
/// recomputation.
#[test]
fn cell_masks_can_be_switched_off_and_back_on() {
    masks::DIAMOND_REPLY_LIMIT.set(usize::MAX);
    let (_dir, mut s) = synthetic_shadow(Some((-45., 30.)), 90, -45., 30.);
    let on = Config {
        seat_enabled: true,
        seat_threshold: 0.5,
        seat_guard: 4,
        diamond_enabled: true,
        ..s.scxrd.config.clone()
    };
    let r = settings(&mut s, &on);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    let frame = (0..90)
        .find(|&f| {
            let raw = s.scxrd.decode(f).unwrap();
            let base = s.scxrd.base_mask(&raw, f);
            s.scxrd.mask_for(&raw, f) != base
        })
        .expect("a masked frame");
    let masked = shown_mask(&call(&mut s, "scxrd_frame", json!({"frame":frame}))).unwrap();
    let ids = part_ids(&s.scxrd);
    found_products(&mut s.scxrd);
    // Each mask in use has its number in the reply.
    let counts = r.result["scxrd"]["stages"][0]["masks"].clone();
    let total = counts["total"].as_f64().unwrap();
    let (dac, seat) = (
        counts["dac"].as_f64().unwrap(),
        counts["seat"].as_f64().unwrap(),
    );
    assert!(
        dac > 0. && seat > 0. && total >= dac.max(seat) - 1e-9,
        "{counts}"
    );
    assert_eq!(
        counts["diamonds"].as_u64().unwrap(),
        s.scxrd.diamonds.as_ref().unwrap().regions as u64
    );
    assert!(counts.get("persistent").is_none() && counts.get("shared").is_none());
    // A report without the numbers (carried over a development reload from
    // an older build) is renewed when the restore refreshes the masks.
    s.scxrd.stages[0].masks = None;
    s.scxrd.refresh_masks(&Control::default());
    assert_eq!(s.scxrd.stages[0].masks.as_ref(), Some(&counts));
    let off = Config {
        cell_masks_enabled: false,
        ..on.clone()
    };
    let r = settings(&mut s, &off);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert_eq!(r.result["scxrd"]["stages"][0]["detail"], "No masks");
    assert_eq!(
        r.result["scxrd"]["stages"][0]["masks"],
        json!({"total": 0.})
    );
    assert!(
        shown_mask(&r).is_none(),
        "no prepared mask on the shown frame"
    );
    assert!(s.scxrd.shadows.is_none() && s.scxrd.diamonds.is_none());
    // Find spots sees only the unusable pixels; later steps were redone.
    let raw = s.scxrd.decode(frame).unwrap();
    assert_eq!(
        s.scxrd.mask_for(&raw, frame),
        s.scxrd.base_mask(&raw, frame)
    );
    assert_eq!(s.scxrd.stages[1].status, "pending");
    // The per-mask choices are kept, and so are the cached masks.
    assert!(
        s.scxrd.config.dac_enabled && s.scxrd.config.seat_enabled && s.scxrd.config.diamond_enabled
    );
    assert_eq!(part_ids(&s.scxrd), ids);
    let r = settings(&mut s, &on);
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert_eq!(part_ids(&s.scxrd), ids, "nothing recomputed");
    assert_eq!(
        shown_mask(&call(&mut s, "scxrd_frame", json!({"frame":frame}))).unwrap(),
        masked
    );
}

/// Settings files from before the newer mask fields still load: the missing
/// fields take their defaults.
#[test]
fn older_settings_load_with_the_new_mask_defaults() {
    let mut old = serde_json::to_value(Config::default()).unwrap();
    for key in [
        "diamond_level",
        "diamond_margin",
        "diamond_min_size",
        "cell_masks_enabled",
    ] {
        old.as_object_mut().unwrap().remove(key);
    }
    // The former whole-step switch reads as the cell mask switch.
    let mut renamed = old.clone();
    renamed["masks_enabled"] = json!(false);
    let c: Config = serde_json::from_value(renamed).unwrap();
    assert!(!c.cell_masks_enabled);
    let c: Config = serde_json::from_value(old).unwrap();
    assert_eq!(c.diamond_level, 10.);
    assert_eq!(c.diamond_margin, 10);
    assert_eq!(c.diamond_min_size, 120);
    assert!(c.cell_masks_enabled);
    assert!(c.check().is_ok());
    assert!(
        Config {
            diamond_level: 2.5,
            ..c.clone()
        }
        .check()
        .is_err()
    );
    assert!(
        Config {
            diamond_level: 51.,
            ..c
        }
        .check()
        .is_err()
    );
}

/// A series with the fixture calibration, confirmed with no measured masks,
/// and its frame 3 opened as the shared detector image (Mask mode).
fn shared_mask_session() -> (tempfile::TempDir, Session, Vec<String>) {
    let (dir, paths, poni) = dac_fixture();
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let c = Config {
        dac_enabled: false,
        ..dac_only(&s)
    };
    settings(&mut s, &c);
    let r = call(&mut s, "open_image", json!({"path":paths[3]}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    (dir, s, paths)
}
/// Mask mode rectangle over rows y0..y1 and columns x0..x1 (array order).
fn draw(s: &mut Session, [x0, y0, x1, y1]: [f64; 4], erase: bool) {
    let r = call(
        s,
        "mask_edit",
        json!({"operation":"rectangle","points":[[x0,y0],[x1,y1]],"erase":erase}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
}
fn rectangle(shape: [usize; 2], [x0, y0, x1, y1]: [usize; 4]) -> Vec<u8> {
    (0..shape[0] * shape[1])
        .map(|i| {
            let (y, x) = (i / shape[1], i % shape[1]);
            u8::from((y0..y1).contains(&y) && (x0..x1).contains(&x))
        })
        .collect()
}

/// The Mask mode mask is a fourth independent mask: drawn in Mask mode it
/// reaches every frame at the next single-crystal command (no rerun), counts
/// in the masked fraction, an unchanged mask keeps the later steps, a changed
/// one or switching it off invalidates them like any other mask part.
#[test]
fn mask_mode_mask_is_an_extra_mask_on_every_frame() {
    let (_dir, mut s, _) = shared_mask_session();
    let r = call(&mut s, "scxrd_snapshot", json!({}));
    assert_eq!(r.result["scxrd"]["sharedMask"], "none");
    assert_eq!(shown_mask(&r), None);
    assert_eq!(s.scxrd.stages[0].detail, "No masks");
    draw(&mut s, [10., 20., 40., 30.], false);
    let wanted = rectangle([128, 128], [10, 20, 40, 30]);
    for frame in [0, 7, 19] {
        let r = call(&mut s, "scxrd_frame", json!({"frame":frame}));
        assert_eq!(r.result["scxrd"]["sharedMask"], "ready");
        assert_eq!(shown_mask(&r).unwrap(), wanted, "frame {frame}");
    }
    assert_eq!(s.scxrd.stages[0].status, "complete");
    // 300 of 16384 pixels on every frame.
    assert!(s.scxrd.stages[0].detail.starts_with("1.8\u{a0}% masked"));
    // Spot finding sees the same mask.
    let data = s.scxrd.decode(5).unwrap();
    let used = s.scxrd.mask_for(&data, 5);
    assert_eq!(used.iter().filter(|&&m| m).count(), 300);

    // Drawn again: identical contents, later steps are kept.
    found_products(&mut s.scxrd);
    draw(&mut s, [10., 20., 40., 30.], false);
    call(&mut s, "scxrd_snapshot", json!({}));
    assert_eq!(s.scxrd.stages[1].status, "complete");
    // Changed: they must be redone, and the new mask is shown at once.
    draw(&mut s, [50., 50., 60., 60.], false);
    let r = call(&mut s, "scxrd_snapshot", json!({}));
    assert_eq!(s.scxrd.stages[1].status, "pending");
    assert_eq!(s.scxrd.stages[0].status, "complete");
    let shown = shown_mask(&r).unwrap();
    assert_eq!(shown.iter().filter(|&&v| v == 1).count(), 400);

    // Switched off: no mask, later steps invalidated; on again: back.
    found_products(&mut s.scxrd);
    let off = Config {
        shared_mask_enabled: false,
        ..s.scxrd.config.clone()
    };
    let r = settings(&mut s, &off);
    assert_eq!(shown_mask(&r), None);
    assert_eq!(s.scxrd.stages[1].status, "pending");
    let on = Config {
        shared_mask_enabled: true,
        ..off.clone()
    };
    assert_eq!(
        shown_mask(&settings(&mut s, &on))
            .unwrap()
            .iter()
            .filter(|&&v| v == 1)
            .count(),
        400
    );
    // A detector mask: the cell mask switch leaves it on, with its number.
    let r = settings(
        &mut s,
        &Config {
            cell_masks_enabled: false,
            ..on.clone()
        },
    );
    assert_eq!(
        shown_mask(&r).unwrap().iter().filter(|&&v| v == 1).count(),
        400
    );
    assert_eq!(r.result["scxrd"]["stages"][0]["status"], "complete");
    assert_eq!(r.result["scxrd"]["stages"][0]["masks"]["shared"], 400);
    settings(&mut s, &on);

    // Cleared in Mask mode: gone at the next command.
    assert_eq!(call(&mut s, "clear_mask", json!({})).result["ok"], true);
    let r = call(&mut s, "scxrd_frame", json!({"frame":2}));
    assert_eq!(r.result["scxrd"]["sharedMask"], "none");
    assert_eq!(shown_mask(&r), None);
}

/// A mask of another detector shape is ignored without an error; a mask
/// drawn on a rotated or flipped view lands on the same source pixels.
#[test]
fn mask_mode_mask_needs_the_series_shape_and_source_orientation() {
    let (_dir, mut s, _) = shared_mask_session();
    // Rows 0..8, columns 100..128 of the source; flipped vertically the
    // view shows them in rows 120..128.
    assert_eq!(
        call(
            &mut s,
            "image_transform",
            json!({"operation":"flip_vertical"})
        )
        .result["ok"],
        true
    );
    draw(&mut s, [100., 120., 127.9, 127.9], false);
    let r = call(&mut s, "scxrd_snapshot", json!({}));
    assert_eq!(
        shown_mask(&r).unwrap(),
        rectangle([128, 128], [100, 0, 128, 8])
    );
    // Another detector shape: not used, no error.
    let (_small_dir, small) = fixture();
    let r = call(
        &mut s,
        "open_image",
        json!({"path":small[0],"reset_image_state":true}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    draw(&mut s, [0., 0., 8., 8.], false);
    let r = call(&mut s, "scxrd_frame", json!({"frame":4}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(r.result["scxrd"]["sharedMask"], "shape");
    assert_eq!(shown_mask(&r), None);
    assert!(s.scxrd.shared.is_none());
}

/// The Mask mode part and the later steps it fed survive the development
/// reload and the restart recovery; the setting too.
#[test]
#[cfg(debug_assertions)]
fn mask_mode_mask_survives_reload_and_restart() {
    let (dir, mut s, _) = shared_mask_session();
    draw(&mut s, [10., 20., 40., 30.], false);
    let wanted = rectangle([128, 128], [10, 20, 40, 30]);
    call(&mut s, "scxrd_snapshot", json!({}));
    found_products(&mut s.scxrd);
    let mut new = development_reload(&mut s, dir.path());
    assert!(new.scxrd.parts.shared.is_some());
    let r = call(&mut new, "scxrd_snapshot", json!({}));
    assert_eq!(shown_mask(&r).unwrap(), wanted);
    assert_eq!(
        new.scxrd.stages[1].status, "complete",
        "{:?}",
        new.scxrd.notice
    );
    let (mut restarted, _) = restart(&mut new, &dir.path().join("recovery.dio"));
    let r = call(&mut restarted, "scxrd_snapshot", json!({}));
    assert_eq!(shown_mask(&r).unwrap(), wanted);
    assert_eq!(restarted.scxrd.stages[1].status, "complete");
    assert!(restarted.scxrd.config.shared_mask_enabled);
}

/// "Show frame in other modes": the reply names the shown frame's file and
/// file frame; opening them through the shared image loader gives the same
/// counts and keeps the shared calibration.
#[test]
fn the_shown_frame_opens_as_the_shared_image() {
    let (_dir, mut s, _) = shared_mask_session();
    let geometry = serde_json::to_value(&s.settings.geometry).unwrap();
    let r = call(&mut s, "scxrd_frame", json!({"frame":12}));
    let source = r.result["scxrd"]["source"].clone();
    assert_eq!(source["frame"], 0);
    assert!(source["path"].as_str().unwrap().ends_with("dac_0012.tif"));
    let r = call(
        &mut s,
        "open_image",
        json!({"path":source["path"],"frame":source["frame"]}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let image = s.image.as_ref().unwrap();
    assert_eq!(image.shape, s.scxrd.shape);
    assert_eq!(*image.values, s.scxrd.decode(12).unwrap());
    assert_eq!(
        serde_json::to_value(&s.settings.geometry).unwrap(),
        geometry
    );
    // The single-crystal frame and its state are untouched.
    assert_eq!(s.scxrd.frame, 12);
}

/// 144 frames (as the Eiger scan) of 96×96 counts (decoded rows): background 20-80 rising with x,
/// dark (2 counts) left of x = 8 like a beam-stop shadow edge, a module gap
/// in rows 30..34 (saturated), a hot run on the first row below the gap
/// (row 34, x 20..31) on 130 frames (90 %), a hot single pixel (row 70, x 50) on
/// every frame, a 3×3 reflection (row 60, x 70) on frames 5-7 and a broad
/// blob (radius 6, row 15, x 75) on frames 20-34, like a diamond reflection.
fn persistent_session() -> (tempfile::TempDir, Session) {
    let dir = tempfile::tempdir().unwrap();
    let (h, w) = (96usize, 96usize);
    let mut seed = 12345u64;
    let mut normal = move || {
        let mut u = || {
            seed = seed
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            ((seed >> 11) as f64 + 0.5) / (1u64 << 53) as f64
        };
        let (a, b) = (u(), u());
        (-2. * a.ln()).sqrt() * (std::f64::consts::TAU * b).cos()
    };
    let mut paths = vec![];
    for f in 0..144 {
        let mut decoded = vec![0u16; h * w];
        for y in 0..h {
            for x in 0..w {
                let mut b = if x < 8 {
                    2.
                } else {
                    20. + 60. * x as f64 / w as f64
                };
                if (34 == y) && (20..31).contains(&x) && f % 10 != 3 {
                    b += 300.;
                }
                if (y, x) == (70, 50) {
                    b += 200.;
                }
                if (5..8).contains(&f) && y.abs_diff(60) <= 1 && x.abs_diff(70) <= 1 {
                    b += 400.;
                }
                if (20..35).contains(&f) && (y as f64 - 15.).hypot(x as f64 - 75.) <= 6. {
                    b += 250.;
                }
                let v = (b + normal() * b.sqrt()).round().max(0.);
                decoded[y * w + x] = if (30..34).contains(&y) {
                    65535
                } else {
                    v as u16
                };
            }
        }
        // TIFF rows run top-down; decoded rows run bottom-up.
        let stored: Vec<u16> = (0..h)
            .flat_map(|r| decoded[(h - 1 - r) * w..(h - r) * w].to_vec())
            .collect();
        let path = dir.path().join(format!("flaw_{f:04}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&path).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray16>(w as u32, h as u32, &stored)
            .unwrap();
        paths.push(path.to_string_lossy().into_owned());
    }
    let mut s = Session::new(PathBuf::new());
    assert_eq!(
        call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
        true
    );
    (dir, s)
}
fn persistent_config(s: &Session) -> Config {
    Config {
        confirmed: true,
        integration_method: "summation".into(),
        background: false,
        dac_enabled: false,
        seat_enabled: false,
        diamond_enabled: false,
        persistent_enabled: true,
        saturation: 65000.,
        ..s.scxrd.config.clone()
    }
}
fn persistent_pixels(s: &Session) -> std::collections::BTreeSet<(usize, usize)> {
    let w = s.scxrd.shape[1];
    let mut mask = vec![false; s.scxrd.shape[0] * w];
    if let Some(p) = &s.scxrd.persistent {
        p.fill(&mut mask);
    }
    (0..mask.len())
        .filter(|&i| mask[i])
        .map(|i| (i / w, i % w))
        .collect()
}

/// The hot run next to the gap is masked and grown by one pixel, the hot
/// single pixel alone; reflections on 3 and 15 frames, the background
/// gradient and the shadow edge are not. The fraction only re-filters.
#[test]
fn persistent_pixels_mask_detector_flaws_only() {
    let (_dir, mut s) = persistent_session();
    assert!(!Config::default().persistent_enabled);
    let c = persistent_config(&s);
    let r = settings(&mut s, &c);
    let mut wanted: std::collections::BTreeSet<(usize, usize)> = (33..=35)
        .flat_map(|y| (19..=31).map(move |x| (y, x)))
        .collect();
    wanted.insert((70, 50));
    assert_eq!(persistent_pixels(&s), wanted);
    assert_eq!(s.scxrd.stages[0].status, "complete");
    assert!(
        s.scxrd.stages[0].detail.contains("40 hot px"),
        "{}",
        s.scxrd.stages[0].detail
    );
    assert_eq!(r.result["scxrd"]["stages"][0]["masks"]["persistent"], 40);
    // A detector mask: kept with the cell masks switched off.
    let r = settings(
        &mut s,
        &Config {
            cell_masks_enabled: false,
            ..c.clone()
        },
    );
    assert_eq!(r.result["scxrd"]["stages"][0]["masks"]["persistent"], 40);
    assert_eq!(shown_mask(&r).unwrap()[34 * 96 + 25], 1);
    let r = settings(&mut s, &c);
    // Shown at once and used by Find spots.
    assert_eq!(shown_mask(&r).unwrap()[34 * 96 + 25], 1);
    let data = s.scxrd.decode(9).unwrap();
    assert!(s.scxrd.mask_for(&data, 9)[70 * 96 + 50]);
    // 90 % of the frames: at 95 % the run goes, the single pixel stays;
    // the frames are not read again.
    let scan = Arc::as_ptr(&s.scxrd.parts.persistent_scan.as_ref().unwrap().data);
    settings(
        &mut s,
        &Config {
            persistent_fraction: 95.,
            ..c.clone()
        },
    );
    assert_eq!(
        persistent_pixels(&s),
        std::collections::BTreeSet::from([(70, 50)])
    );
    assert_eq!(
        Arc::as_ptr(&s.scxrd.parts.persistent_scan.as_ref().unwrap().data),
        scan
    );
    // The lowest share, 20 %: the 15-frame blob (10 %) is still not masked.
    settings(
        &mut s,
        &Config {
            persistent_fraction: 20.,
            ..c.clone()
        },
    );
    assert_eq!(persistent_pixels(&s), wanted);
}

/// Like the other parts: switching it changes nothing else, a changed mask
/// invalidates later steps, and it survives the reload and the restart.
#[test]
#[cfg(debug_assertions)]
fn persistent_pixels_are_an_independent_part_that_survives_reloads() {
    let (dir, mut s) = persistent_session();
    let c = persistent_config(&s);
    let r = call(
        &mut s,
        "scxrd_settings",
        json!({"config":Config { persistent_fraction: 10., ..c.clone() }}),
    );
    assert_eq!(r.result["ok"], false);
    settings(&mut s, &c);
    found_products(&mut s.scxrd);
    let wanted = persistent_pixels(&s);
    let mut new = development_reload(&mut s, dir.path());
    assert_eq!(persistent_pixels(&new), wanted);
    assert_eq!(new.scxrd.stages[1].status, "complete");
    let (mut restarted, _) = restart(&mut new, &dir.path().join("recovery.dio"));
    assert_eq!(persistent_pixels(&restarted), wanted);
    assert_eq!(restarted.scxrd.stages[1].status, "complete");
    assert!(restarted.scxrd.config.persistent_enabled);
    settings(
        &mut restarted,
        &Config {
            persistent_enabled: false,
            ..c
        },
    );
    assert!(persistent_pixels(&restarted).is_empty());
    assert_eq!(restarted.scxrd.stages[1].status, "pending");
}

/// Eiger enstatite scan: the hot run on the first row below the horizontal
/// gap in the upper right quadrant (display rows 550-551, x 1530-1546) is
/// masked; reports pixels, time and Find spots with and without the mask.
/// `DIOPTAS_SCXRD_RENDER_DIR` also writes before/after crops of the area.
#[test]
#[ignore = "Local Eiger scan and PONI required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_persistent_pixels() {
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let mut s = Session::new(PathBuf::new());
    let r = call(
        &mut s,
        "scxrd_load",
        json!({"path":root.join("eiger_0000.h5")}),
    );
    assert_eq!(r.result["ok"], true);
    let poni = root.join("CeO2_20240620_1849_dioptas.poni");
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let c = Config {
        axis: [-1., 0., 0.],
        omega_start: -37.5,
        dac_half_opening: 41.,
        seat_enabled: true,
        seat_threshold: 0.6,
        seat_guard: 20,
        link_radius: 3.,
        ..dac_only(&s)
    };
    settings(&mut s, &c);
    let [h, w] = s.scxrd.shape;
    let flaw =
        |x: usize, y: usize| (1525..=1550).contains(&x) && (h - 1 - 553..=h - 1 - 548).contains(&y);
    let spots = |s: &mut Session| {
        let r = call(s, "scxrd_run", json!({"stage":1}));
        assert_eq!(r.result["ok"], true, "{:?}", r.result);
        let on_flaw = s
            .scxrd
            .tracks
            .iter()
            .filter(|t| {
                flaw(
                    t.observed[0].round() as usize,
                    t.observed[1].round() as usize,
                )
            })
            .count();
        (
            s.scxrd.peaks.len(),
            s.scxrd.tracks.len(),
            on_flaw,
            s.scxrd.stages[1].detail.clone(),
        )
    };
    let before = spots(&mut s);
    let before_tracks = s.scxrd.tracks.clone();
    let shown = |s: &Session, f: usize| {
        let data = s.scxrd.decode(f).unwrap();
        (data.clone(), s.scxrd.mask_for(&data, f))
    };
    let before_mask = shown(&s, 72);
    let clock = std::time::Instant::now();
    let on = Config {
        persistent_enabled: true,
        ..c.clone()
    };
    settings(&mut s, &on);
    let seconds = clock.elapsed().as_secs_f64();
    let part = s.scxrd.persistent.clone().expect("persistent pixels");
    let mut mask = vec![false; h * w];
    part.fill(&mut mask);
    for x in 1530..=1546 {
        assert!(mask[(h - 1 - 551) * w + x], "x {x} display row 551");
    }
    let scan = s.scxrd.parts.persistent_scan.as_ref().unwrap().data.clone();
    let after_mask = shown(&s, 72);
    {
        // Clusters of the mask (grown runs) with their display coordinates.
        let mut seen = vec![false; h * w];
        let (mut singles, mut clusters) = (0, vec![]);
        for start in 0..h * w {
            if !mask[start] || seen[start] {
                continue;
            }
            seen[start] = true;
            let mut stack = vec![start];
            let mut px = vec![];
            while let Some(i) = stack.pop() {
                px.push(i);
                let (y, x) = (i / w, i % w);
                for yy in y.saturating_sub(1)..(y + 2).min(h) {
                    for xx in x.saturating_sub(1)..(x + 2).min(w) {
                        let j = yy * w + xx;
                        if mask[j] && !seen[j] {
                            seen[j] = true;
                            stack.push(j);
                        }
                    }
                }
            }
            if px.len() == 1 {
                singles += 1;
            } else {
                let xs = px.iter().map(|i| i % w);
                let rows = px.iter().map(|i| h - 1 - i / w);
                clusters.push(format!(
                    "{} px x {}-{} rows {}-{}",
                    px.len(),
                    xs.clone().min().unwrap(),
                    xs.max().unwrap(),
                    rows.clone().min().unwrap(),
                    rows.max().unwrap()
                ));
            }
        }
        eprintln!(
            "mask: {singles} single pixels; clusters: {}",
            clusters.join("; ")
        );
    }
    let after = spots(&mut s);
    {
        // Tracks found without the mask whose centre lies on or next to a
        // masked pixel, by how many frames they span.
        let near = |t: &Track| {
            let (x, y) = (
                t.observed[0].round() as isize,
                t.observed[1].round() as isize,
            );
            (-2..=2).any(|dy| {
                (-2..=2).any(|dx| {
                    let (xx, yy) = (x + dx, y + dy);
                    xx >= 0
                        && yy >= 0
                        && (xx as usize) < w
                        && (yy as usize) < h
                        && mask[yy as usize * w + xx as usize]
                })
            })
        };
        let mut spans = std::collections::BTreeMap::new();
        let mut hit = 0;
        for t in before_tracks.iter().filter(|t| near(t)) {
            hit += 1;
            let span = t.last - t.first + 1;
            let bin = match span {
                1 => "1",
                2..=3 => "2-3",
                4..=10 => "4-10",
                11..=40 => "11-40",
                _ => ">40",
            };
            *spans.entry(bin).or_insert(0) += 1;
        }
        eprintln!("tracks before at masked pixels: {hit}, frames spanned {spans:?}");
        let mut singles = 0;
        let mut others = 0;
        for t in before_tracks
            .iter()
            .filter(|t| near(t) && t.last == t.first)
        {
            let _ = t;
            singles += 1;
        }
        for t in before_tracks
            .iter()
            .filter(|t| near(t) && t.last > t.first + 2)
        {
            let _ = t;
            others += 1;
        }
        eprintln!("single-frame {singles}, more than 3 frames {others}");
    }
    // Fraction change: re-filter only.
    let clock = std::time::Instant::now();
    settings(
        &mut s,
        &Config {
            persistent_fraction: 80.,
            ..on.clone()
        },
    );
    let refilter = clock.elapsed().as_secs_f64();
    let at80 = s.scxrd.persistent.as_ref().unwrap().pixels;
    let clock = std::time::Instant::now();
    let rescan = s.scxrd.persistent_scan(&Control::default()).unwrap();
    let scan_seconds = clock.elapsed().as_secs_f64();
    let clock = std::time::Instant::now();
    persistent::select(&rescan, s.scxrd.shape, 50.);
    let select_seconds = clock.elapsed().as_secs_f64();
    let clock = std::time::Instant::now();
    settings(
        &mut s,
        &Config {
            seat_threshold: 0.7,
            ..on.clone()
        },
    );
    let other = clock.elapsed().as_secs_f64();
    eprintln!(
        "scan alone {scan_seconds:.3} s, select {select_seconds:.3} s, a seat threshold change {other:.3} s"
    );
    eprintln!(
        "persistent: {} px masked ({} counted pixels, {} frames), settings reply with the scan {seconds:.3} s, re-filter {refilter:.3} s, at 80 %: {at80} px",
        part.pixels,
        scan.counts.len(),
        scan.frames
    );
    eprintln!(
        "Find spots without: peaks {} tracks {} on the flaw {} ({})",
        before.0, before.1, before.2, before.3
    );
    eprintln!(
        "Find spots with:    peaks {} tracks {} on the flaw {} ({})",
        after.0, after.1, after.2, after.3
    );
    assert_eq!(after.2, 0);
    if let Ok(out) = std::env::var("DIOPTAS_SCXRD_RENDER_DIR") {
        // Display orientation, x 1490-1590, display rows 520-580, scale 6;
        // left before, right after; red = prepared mask, blue = unusable.
        let (x0, r0, cw, ch, sc) = (1490, 520, 100, 60, 6);
        let tw = 2 * cw * sc + 8;
        let mut img = vec![30u8; tw * ch * sc * 3];
        for (k, (data, m)) in [&before_mask, &after_mask].into_iter().enumerate() {
            let base = s.scxrd.base_mask(data, 72);
            for r in 0..ch {
                for x in 0..cw {
                    let i = (h - 1 - (r0 + r)) * w + x0 + x;
                    let g = ((data[i] / 60.).min(1.) * 255.) as u8;
                    let px = if base[i] {
                        [0, 0, 90]
                    } else if m[i] {
                        [g.max(110), g / 3, g / 3]
                    } else {
                        [g, g, g]
                    };
                    for dy in 0..sc {
                        for dx in 0..sc {
                            let o = ((r * sc + dy) * tw + k * (cw * sc + 8) + x * sc + dx) * 3;
                            img[o..o + 3].copy_from_slice(&px);
                        }
                    }
                }
            }
        }
        let path = PathBuf::from(out).join("before_after_frame072.png");
        let mut e = png::Encoder::new(File::create(path).unwrap(), tw as u32, (ch * sc) as u32);
        e.set_color(png::ColorType::Rgb);
        e.write_header().unwrap().write_image_data(&img).unwrap();
    }
}

/// Settings saved before persistent pixels existed load with them off.
#[test]
fn older_settings_load_without_persistent_pixels() {
    let mut old = serde_json::to_value(Config::default()).unwrap();
    let o = old.as_object_mut().unwrap();
    o.remove("persistent_enabled");
    o.remove("persistent_fraction");
    let c: Config = serde_json::from_value(old).unwrap();
    assert!(!c.persistent_enabled);
    assert_eq!(c.persistent_fraction, 50.);
    assert!(c.check().is_ok());
}

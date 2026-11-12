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
    let a = Config::default();
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
            track: 0,
            correction: 1.,
        },
        Reflection {
            hkl: [-9, 8, -7],
            omega: 0.,
            intensity: 2e13,
            sigma: 1e12,
            flags: 0,
            track: 1,
            correction: 1.,
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
            track: 0,
            correction: 1.,
        },
        Reflection {
            hkl: [0, 1, 0],
            omega: 0.,
            intensity: 20.,
            sigma: 1.,
            flags: 0,
            track: 1,
            correction: 1.,
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
fn development_handoff_refuses_to_silently_drop_an_unsaved_scan() {
    let (dir, paths) = fixture();
    let mut s = Session::new(PathBuf::new());
    call(&mut s, "scxrd_load", json!({"paths":paths}));
    let transfer = dir.path().join("development.h5");
    let r = call(&mut s, "development_save", json!({"path":transfer}));
    assert_eq!(r.result["ok"], false);
    assert_eq!(s.scxrd.sources.len(), 3);
    assert!(!transfer.exists());
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

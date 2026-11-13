use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
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
    assert_eq!(r.result["ok"], true, "{}: {}", action, r.result);
    r
}
fn image(p: &Path, shape: [usize; 2], value: u16) {
    std::fs::create_dir_all(p.parent().unwrap()).unwrap();
    tiff::encoder::TiffEncoder::new(std::fs::File::create(p).unwrap())
        .unwrap()
        .write_image::<tiff::encoder::colortype::Gray16>(
            shape[1] as u32,
            shape[0] as u32,
            &vec![value; shape[0] * shape[1]],
        )
        .unwrap();
}
fn setup(a: &Path, b: &Path) -> Session {
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":a}));
    call(
        &mut s,
        "manual_geometry",
        json!({"convention":"pyfai","values":{"dist":150.,"poni1":1.2,"poni2":1.6,"rot1":0.,"rot2":0.,"rot3":0.,"wavelength":0.4,"pixel1":100.,"pixel2":100.,"polarization_factor":0.99}}),
    );
    call(
        &mut s,
        "integration_settings",
        json!({"bins":24,"cake_bins":12}),
    );
    call(
        &mut s,
        "mask_stroke",
        json!({"points":[[10,10]],"radius":2}),
    );
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(&mut s, "open_image", json!({"path":b}));
    s
}
fn select(s: &mut Session, index: usize) -> Reply {
    call(
        s,
        "configuration",
        json!({"operation":"select","index":index}),
    )
}
#[test]
fn grouped_files_keep_selection_geometry_masks_factors_and_combined_results() {
    let t = tempfile::tempdir().unwrap();
    let a = t.path().join("a_001.tif");
    let b = t.path().join("b_001.tif");
    image(&a, [24, 32], 10);
    image(&b, [24, 32], 20);
    image(&t.path().join("a_002.tif"), [24, 32], 30);
    image(&t.path().join("b_002.tif"), [24, 32], 40);
    let mut s = setup(&a, &b);
    call(
        &mut s,
        "combination_settings",
        json!({"patterns":true,"cakes":true,"factor":2}),
    );
    let before = call(&mut s, "state", json!({}));
    let r = call(
        &mut s,
        "configuration_navigation",
        json!({"target":"file","direction":1}),
    );
    assert_eq!(
        r.result["configurationNavigation"]["advanced"],
        json!([0, 1])
    );
    assert_eq!(
        r.result["state"]["configurationContext"],
        before.result["state"]["configurationContext"]
    );
    assert_eq!(r.result["state"]["imageName"], "b_002.tif");
    assert_eq!(
        r.result["state"]["geometry"],
        before.result["state"]["geometry"]
    );
    assert_eq!(
        r.result["state"]["maskedPixels"],
        before.result["state"]["maskedPixels"]
    );
    assert_eq!(r.result["state"]["combination"]["factor"], 2.);
    assert_ne!(r.result["pattern"]["y"], before.result["pattern"]["y"]);
    let first = select(&mut s, 0);
    assert_eq!(first.result["state"]["imageName"], "a_002.tif");
    assert_eq!(first.result["state"]["combination"]["factor"], 1.);
    assert_eq!(
        first.result["state"]["maskedPixels"],
        before.result["state"]["maskedPixels"]
    );
    select(&mut s, 1);
    image(&t.path().join("a_003.tif"), [24, 32], 50);
    let r = call(
        &mut s,
        "configuration_navigation",
        json!({"target":"file","direction":1}),
    );
    assert_eq!(r.result["configurationNavigation"]["advanced"], json!([0]));
    assert_eq!(r.result["configurationNavigation"]["skipped"], json!([1]));
    assert_eq!(r.result["state"]["imageName"], "b_002.tif");
    let project = t.path().join("browsed.dio");
    call(&mut s, "save_project", json!({"path":project}));
    let mut restored = Session::new(root());
    call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(
        select(&mut restored, 0).result["state"]["imageName"],
        "a_003.tif"
    );
}
#[test]
fn grouped_filename_position_counts_from_right() {
    let t = tempfile::tempdir().unwrap();
    let a = t.path().join("a_scan_001_det_07.tif");
    let b = t.path().join("b_scan_001_det_07.tif");
    for p in [&a, &b] {
        image(p, [24, 32], 10);
    }
    for p in [
        "a_scan_002_det_07.tif",
        "b_scan_002_det_07.tif",
        "a_scan_001_det_08.tif",
        "b_scan_001_det_08.tif",
    ] {
        image(&t.path().join(p), [24, 32], 20);
    }
    let mut s = setup(&a, &b);
    let r = call(
        &mut s,
        "configuration_navigation",
        json!({"target":"file","direction":1,"number_position":2}),
    );
    assert_eq!(r.result["state"]["imageName"], "b_scan_002_det_07.tif");
    let r = call(
        &mut s,
        "configuration_navigation",
        json!({"target":"file","direction":-1,"number_position":2}),
    );
    assert_eq!(r.result["state"]["imageName"], "b_scan_001_det_07.tif");
}
#[test]
fn grouped_folders_and_mec_keep_each_detector_directory() {
    for mec in [false, true] {
        let t = tempfile::tempdir().unwrap();
        let first = if mec {
            "run_001_evt_002.0.tif"
        } else {
            "image_001.tif"
        };
        let second = if mec { "run_002_evt_002.0.tif" } else { first };
        let a = t.path().join("detA/run001").join(first);
        let b = t.path().join("detB/run001").join(first);
        for p in [&a, &b] {
            image(p, [24, 32], 10);
        }
        for detector in ["detA", "detB"] {
            image(
                &t.path().join(detector).join("run002").join(second),
                [24, 32],
                30,
            );
        }
        let mut s = setup(&a, &b);
        let r = call(
            &mut s,
            "configuration_navigation",
            json!({"target":"folder","direction":1,"mec":mec}),
        );
        assert_eq!(
            r.result["configurationNavigation"]["advanced"],
            json!([0, 1])
        );
        assert!(
            r.result["state"]["imagePath"]
                .as_str()
                .unwrap()
                .replace('\\', "/")
                .contains("detB/run002")
        );
        assert_eq!(r.result["state"]["imageName"], second);
        assert!(
            select(&mut s, 0).result["state"]["imagePath"]
                .as_str()
                .unwrap()
                .replace('\\', "/")
                .contains("detA/run002")
        );
        let r = call(
            &mut s,
            "configuration_navigation",
            json!({"target":"folder","direction":-1,"mec":mec}),
        );
        assert_eq!(r.result["state"]["imageName"], first);
        assert!(
            r.result["state"]["imagePath"]
                .as_str()
                .unwrap()
                .replace('\\', "/")
                .contains("detA/run001")
        );
    }
}
#[test]
fn grouped_navigation_rolls_back_all_detectors_on_bad_data_or_shape_change() {
    for shape_change in [false, true] {
        let t = tempfile::tempdir().unwrap();
        let a = t.path().join("a_001.tif");
        let b = t.path().join("b_001.tif");
        image(&a, [24, 32], 10);
        image(&b, [24, 32], 20);
        image(&t.path().join("a_002.tif"), [24, 32], 30);
        let target = t.path().join("b_002.tif");
        if shape_change {
            image(&target, [16, 20], 40);
        } else {
            std::fs::write(&target, b"corrupt image").unwrap();
        }
        let mut s = setup(&a, &b);
        let before = call(&mut s, "state", json!({}));
        let r = invoke(
            &mut s,
            "configuration_navigation",
            json!({"target":"file","direction":1}),
        );
        assert_eq!(r.result["ok"], false);
        if shape_change {
            assert!(
                r.result["error"]
                    .as_str()
                    .unwrap()
                    .contains("no configurations were advanced")
            );
        }
        let after = call(&mut s, "state", json!({}));
        assert_eq!(after.result["state"], before.result["state"]);
        assert_eq!(after.result["pattern"], before.result["pattern"]);
        assert_eq!(select(&mut s, 0).result["state"]["imageName"], "a_001.tif");
    }
}

#[test]
fn configurable_steps_and_active_scope_leave_other_detectors_in_place() {
    let t = tempfile::tempdir().unwrap();
    let a = t.path().join("a_001_det_07.tif");
    let b = t.path().join("b_001_det_07.tif");
    image(&a, [24, 32], 10);
    image(&b, [24, 32], 20);
    image(&t.path().join("a_004_det_07.tif"), [24, 32], 30);
    image(&t.path().join("b_004_det_07.tif"), [24, 32], 40);
    let mut s = setup(&a, &b);
    let r = call(
        &mut s,
        "configuration_navigation",
        json!({"target":"file","direction":1,"scope":"active","number_position":2,"step":3}),
    );
    assert_eq!(r.result["configurationNavigation"]["advanced"], json!([1]));
    assert_eq!(r.result["state"]["imageName"], "b_004_det_07.tif");
    assert_eq!(
        select(&mut s, 0).result["state"]["imageName"],
        "a_001_det_07.tif"
    );
    select(&mut s, 1);
    let r = call(
        &mut s,
        "configuration_navigation",
        json!({"target":"file","direction":-1,"scope":"active","number_position":2,"step":3}),
    );
    assert_eq!(r.result["state"]["imageName"], "b_001_det_07.tif");
}

#[test]
fn generic_folder_rules_select_number_and_independent_filename_step() {
    let t = tempfile::tempdir().unwrap();
    let first = "image_010_det_07.tif";
    let second = "image_015_det_07.tif";
    let a = t.path().join("detA/run001/shot009").join(first);
    let b = t.path().join("detB/run001/shot009").join(first);
    image(&a, [24, 32], 10);
    image(&b, [24, 32], 20);
    for detector in ["detA", "detB"] {
        image(
            &t.path().join(detector).join("run003/shot009").join(second),
            [24, 32],
            30,
        );
        // These exist but must not be selected when number 2 was requested.
        image(
            &t.path().join(detector).join("run001/shot011").join(second),
            [24, 32],
            90,
        );
    }
    let mut s = setup(&a, &b);
    for direction in [1, -1] {
        let r = call(
            &mut s,
            "configuration_navigation",
            json!({"target":"folder","scope":"all","direction":direction,"folder_number_position":2,"step":2,"folder_filename_position":2,"folder_filename_step":5}),
        );
        assert_eq!(
            r.result["configurationNavigation"]["advanced"],
            json!([0, 1])
        );
        assert_eq!(
            r.result["state"]["imageName"],
            if direction == 1 { second } else { first }
        );
        let expected = if direction == 1 {
            "detB/run003/shot009"
        } else {
            "detB/run001/shot009"
        };
        assert!(
            r.result["state"]["imagePath"]
                .as_str()
                .unwrap()
                .replace('\\', "/")
                .contains(expected)
        );
    }
}

#[test]
fn invalid_generic_rules_preserve_the_session() {
    let t = tempfile::tempdir().unwrap();
    let a = t.path().join("a_001.tif");
    let b = t.path().join("b_001.tif");
    image(&a, [24, 32], 10);
    image(&b, [24, 32], 20);
    let mut s = setup(&a, &b);
    let before = call(&mut s, "state", json!({}));
    for bad in [
        json!({"step":0}),
        json!({"scope":"everything"}),
        json!({"folder_number_position":-1}),
        json!({"folder_filename_position":1.5}),
        json!({"folder_filename_step":1000001}),
    ] {
        let mut args = json!({"target":"file","direction":1});
        args.as_object_mut()
            .unwrap()
            .extend(bad.as_object().unwrap().clone());
        assert_eq!(
            invoke(&mut s, "configuration_navigation", args).result["ok"],
            false
        );
        assert_eq!(
            call(&mut s, "state", json!({})).result["state"],
            before.result["state"]
        );
    }
}

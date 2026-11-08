use dioptas_backend::{
    Session,
    control::Control,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{
    path::{Path, PathBuf},
    sync::Arc,
};
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn request(action: &str, payload: Value) -> Request {
    Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    }
}
fn invoke(s: &mut Session, action: &str, payload: Value) -> Reply {
    s.invoke(&request(action, payload))
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = invoke(s, action, payload);
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn fixture(path: &Path) {
    let f = hdf5::File::create(path).unwrap();
    for (name, n, h, w, base) in [
        ("a", 4, 24, 32, 10),
        ("b", 2, 24, 32, 30),
        ("c", 3, 16, 20, 50),
    ] {
        let values: Vec<u16> = (0..n).flat_map(|i| vec![base + i as u16; h * w]).collect();
        f.new_dataset::<u16>()
            .shape((n, h, w))
            .create(name)
            .unwrap()
            .write_raw(&values)
            .unwrap();
    }
    f.new_dataset::<u16>()
        .shape((24, 32))
        .create("plane")
        .unwrap()
        .write_raw(&vec![70; 24 * 32])
        .unwrap();
    f.new_dataset::<u16>()
        .shape((2, 2, 3, 4))
        .create("components")
        .unwrap();
    f.new_dataset::<u16>()
        .shape((2,))
        .create("metadata")
        .unwrap();
    f.new_dataset::<u64>()
        .shape((2, 24, 32))
        .create("bad")
        .unwrap()
        .write_raw(&vec![(1u64 << 53) + 1; 2 * 24 * 32])
        .unwrap();
    f.new_dataset::<u64>()
        .shape((2, 16, 20))
        .create("bad_size")
        .unwrap()
        .write_raw(&vec![(1u64 << 53) + 1; 2 * 16 * 20])
        .unwrap();
}
fn geometry(s: &mut Session) {
    call(
        s,
        "manual_geometry",
        json!({"convention":"pyfai","values":{"dist":150.,"poni1":1.2,"poni2":1.6,"rot1":0.,"rot2":0.,"rot3":0.,"wavelength":0.4,"pixel1":100.,"pixel2":100.,"polarization_factor":0.99}}),
    );
    call(
        s,
        "integration_settings",
        json!({"bins":24,"cake_bins":12,"trim_zeros":false}),
    );
}
fn pixel(s: &mut Session) -> f64 {
    call(s, "pixel", json!({"x":0,"y":0})).result["pixel"]["value"]
        .as_f64()
        .unwrap()
}
#[test]
fn generic_discovery_source_frame_navigation_and_scientific_products() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("image_001.h5");
    fixture(&path);
    let mut s = Session::new(root());
    let opened = call(&mut s, "open_image", json!({"path":path}));
    assert_eq!(opened.result["state"]["selectedImageSource"], "/a");
    let sources = opened.result["state"]["imageSources"].as_array().unwrap();
    assert!(
        sources
            .iter()
            .any(|v| v["dataset"] == "/plane" && v["frames"] == 1)
    );
    assert!(
        !sources
            .iter()
            .any(|v| v["dataset"] == "/components" || v["dataset"] == "/metadata")
    );
    assert_eq!(opened.result["state"]["imageSourceError"], Value::Null);
    geometry(&mut s);
    let before = call(&mut s, "integration_navigation", json!({"frame":4}));
    assert_eq!(pixel(&mut s), 13.);
    let switched = call(&mut s, "select_image_source", json!({"dataset":"/b"}));
    assert_eq!(switched.result["state"]["selectedImageSource"], "/b");
    assert_eq!(switched.result["state"]["integration"]["frames"], 2);
    assert_eq!(switched.result["state"]["integration"]["frame"], 2);
    assert_eq!(
        switched.result["state"]["geometry"],
        before.result["state"]["geometry"]
    );
    assert_eq!(pixel(&mut s), 31.);
    let a = before.result["pattern"]["y"].as_array().unwrap();
    let b = switched.result["pattern"]["y"].as_array().unwrap();
    assert!(!a.is_empty());
    assert_eq!(a.len(), b.len());
    for (a, b) in a.iter().zip(b) {
        let expected = a.as_f64().unwrap() * 31. / 13.;
        assert!((b.as_f64().unwrap() - expected).abs() < 1e-9 * (1. + expected.abs()));
    }
    assert_ne!(
        switched.result["cake"]["bufferId"],
        before.result["cake"]["bufferId"]
    );
    call(&mut s, "next_image", json!({"direction":-1}));
    assert_eq!(pixel(&mut s), 30.);
    let single = call(&mut s, "select_image_source", json!({"dataset":"/plane"}));
    assert_eq!(single.result["state"]["integration"]["frames"], 1);
    assert_eq!(pixel(&mut s), 70.);
}
#[test]
fn size_confirmation_failures_and_cancellation_restore_entire_session() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("image.h5");
    fixture(&path);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":path}));
    geometry(&mut s);
    call(
        &mut s,
        "mask_stroke",
        json!({"points":[[10,10]],"radius":2}),
    );
    let before = call(&mut s, "state", json!({})).result;
    for dataset in ["/missing", "/bad"] {
        assert_eq!(
            invoke(&mut s, "select_image_source", json!({"dataset":dataset})).result["ok"],
            false
        );
        assert_eq!(call(&mut s, "state", json!({})).result, before);
    }
    let pending = call(&mut s, "select_image_source", json!({"dataset":"/c"}));
    assert_eq!(pending.result["cancelled"], true);
    assert_eq!(pending.result["imageChange"]["options"]["dataset"], "/c");
    assert_eq!(call(&mut s, "state", json!({})).result, before);
    let control = Arc::new(Control::default());
    control.cancel();
    let cancelled = s.invoke_controlled(
        &request("select_image_source", json!({"dataset":"/b"})),
        control,
    );
    assert_eq!(cancelled.result["ok"], false);
    assert_eq!(call(&mut s, "state", json!({})).result, before);
    assert_eq!(
        invoke(
            &mut s,
            "open_image",
            json!({"path":path,"dataset":"/bad_size","reset_calibration":true})
        )
        .result["ok"],
        false
    );
    assert_eq!(call(&mut s, "state", json!({})).result, before);
    let accepted = call(
        &mut s,
        "open_image",
        json!({"path":path,"dataset":"/c","reset_calibration":true}),
    );
    assert_eq!(accepted.result["calibrationReset"], true);
    assert_eq!(accepted.result["state"]["calibrated"], false);
    assert_eq!(accepted.result["state"]["maskedPixels"], 0);
    assert!(accepted.result["pattern"].is_null() && accepted.result["cake"].is_null());
    assert_eq!(pixel(&mut s), 50.);
}
#[test]
fn selected_source_is_retained_across_files_and_missing_source_never_substitutes() {
    let temp = tempfile::tempdir().unwrap();
    let a = temp.path().join("image_001.h5");
    let b = temp.path().join("image_002.h5");
    let c = temp.path().join("image_003.h5");
    fixture(&a);
    fixture(&b);
    {
        let f = hdf5::File::create(&c).unwrap();
        f.new_dataset::<u16>()
            .shape((24, 32))
            .create("different")
            .unwrap();
    }
    let mut s = Session::new(root());
    call(
        &mut s,
        "open_image",
        json!({"path":a,"dataset":"/b","frame":1}),
    );
    let next = call(&mut s, "next_image", json!({"direction":1}));
    assert_eq!(
        next.result["state"]["imagePath"],
        json!(b.canonicalize().unwrap())
    );
    assert_eq!(next.result["state"]["selectedImageSource"], "/b");
    call(&mut s, "next_image", json!({"direction":1}));
    let before = call(&mut s, "state", json!({})).result;
    assert_eq!(
        invoke(&mut s, "next_image", json!({"direction":1})).result["ok"],
        false
    );
    assert_eq!(call(&mut s, "state", json!({})).result, before);
}
#[test]
fn independent_configurations_and_owned_project_sources_round_trip() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("image.h5");
    fixture(&path);
    let project = temp.path().join("sources.dio");
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":path,"frame":2}));
    geometry(&mut s);
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(&mut s, "select_image_source", json!({"dataset":"/b"}));
    let expected = call(&mut s, "state", json!({})).result;
    call(&mut s, "save_project", json!({"path":project}));
    let moved = temp.path().join("moved.h5");
    std::fs::rename(&path, &moved).unwrap();
    let mut restored = Session::new(root());
    let loaded = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(loaded.result["state"]["selectedImageSource"], "/b");
    assert_eq!(
        loaded.result["state"]["imageSources"],
        expected["state"]["imageSources"]
    );
    assert_eq!(pixel(&mut restored), 31.);
    let before = call(&mut restored, "state", json!({})).result;
    assert_eq!(
        invoke(
            &mut restored,
            "select_image_source",
            json!({"dataset":"/a"})
        )
        .result["ok"],
        false
    );
    assert_eq!(call(&mut restored, "state", json!({})).result, before);
    let first = call(
        &mut restored,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(first.result["state"]["selectedImageSource"], "/a");
    assert_eq!(pixel(&mut restored), 12.);
    std::fs::rename(moved, &path).unwrap();
    call(&mut restored, "next_image", json!({"direction":1}));
    assert_eq!(pixel(&mut restored), 13.);
    let second = call(
        &mut restored,
        "configuration",
        json!({"operation":"select","index":1}),
    );
    assert_eq!(second.result["state"]["selectedImageSource"], "/b");
    assert_eq!(pixel(&mut restored), 31.);
}
#[test]
fn automatic_eiger_series_and_explicit_link_policy_are_preserved() {
    let temp = tempfile::tempdir().unwrap();
    let data = temp.path().join("data.h5");
    {
        let f = hdf5::File::create(&data).unwrap();
        f.new_dataset::<u16>()
            .shape((2, 24, 32))
            .create("images")
            .unwrap()
            .write_raw(&vec![12; 2 * 24 * 32])
            .unwrap();
        f.create_group("nested").unwrap();
        f.new_dataset::<u16>()
            .shape((3, 24, 32))
            .create("nested/other")
            .unwrap()
            .write_raw(&vec![25; 3 * 24 * 32])
            .unwrap();
    }
    let master = temp.path().join("master.h5");
    {
        let f = hdf5::File::create(&master).unwrap();
        f.create_group("entry/data").unwrap();
        f.link_external("data.h5", "/images", "/entry/data/data_000001")
            .unwrap();
        f.link_external("data.h5", "/images", "/entry/data/data_000002")
            .unwrap();
        f.link_external("data.h5", "/nested", "/other_group")
            .unwrap();
        f.link_soft("/other_group", "/soft_group").unwrap();
    }
    let mut s = Session::new(root());
    assert_eq!(
        invoke(&mut s, "open_image", json!({"path":master})).result["ok"],
        false
    );
    let auto = call(
        &mut s,
        "open_image",
        json!({"path":master,"follow_external_links":true}),
    );
    assert_eq!(auto.result["state"]["automaticImageSource"], true);
    assert!(auto.result["state"]["selectedImageSource"].is_null());
    assert_eq!(auto.result["state"]["integration"]["frames"], 4);
    assert_eq!(auto.result["state"]["imageSourceError"], Value::Null);
    assert!(
        auto.result["state"]["imageSources"]
            .as_array()
            .unwrap()
            .iter()
            .any(|s| s["dataset"] == "/soft_group/other")
    );
    let explicit = call(
        &mut s,
        "select_image_source",
        json!({"dataset":"/other_group/other"}),
    );
    assert_eq!(explicit.result["state"]["integration"]["frames"], 3);
    assert_eq!(pixel(&mut s), 25.);
    let project = temp.path().join("external.dio");
    call(&mut s, "save_project", json!({"path":project}));
    let mut restored = Session::new(root());
    let loaded = call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(
        loaded.result["state"]["selectedImageSource"],
        "/other_group/other"
    );
    // The restored reader policy is still explicit, and permits source switching.
    call(&mut restored, "select_image_source", json!({"dataset":""}));
    assert_eq!(pixel(&mut restored), 12.);
    let auto = call(&mut s, "select_image_source", json!({"dataset":""}));
    assert_eq!(auto.result["state"]["integration"]["frames"], 4);
    assert_eq!(pixel(&mut s), 12.);
    // Explicit missing/broken links must fail, even if automatic data still exists.
    assert_eq!(
        invoke(
            &mut s,
            "open_image",
            json!({"path":master,"dataset":"/missing","follow_external_links":true})
        )
        .result["ok"],
        false
    );
    assert_eq!(
        call(&mut s, "state", json!({})).result["state"]["selectedImageSource"],
        Value::Null
    );
}

#[test]
fn link_opt_in_does_not_change_non_hdf5_loading() {
    let mut s = Session::new(root());
    let loaded = call(
        &mut s,
        "open_image",
        json!({"path":root().join("dioptas/tests/data/CeO2_Pilatus1M.tif"),"follow_external_links":true}),
    );
    assert_eq!(loaded.result["state"]["shape"], json!([1043, 981]));
    assert_eq!(loaded.result["state"]["imageSources"], json!([]));
}

use dioptas_backend::{
    Session,
    control::Control,
    image::Image,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{
    path::{Path, PathBuf},
    sync::Arc,
};
#[path = "common/hdf5_master_fixtures.rs"]
mod fixtures;
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
fn pixel(s: &mut Session) -> f64 {
    call(s, "pixel", json!({"x":0,"y":0})).result["pixel"]["value"]
        .as_f64()
        .unwrap()
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
fn choices(path: &Path) -> Value {
    json!([
     {"owner":path.join("relocated.h5"),"stored_filename":"/missing/acquisition/a.h5","actual_file":path.join("parts/a.h5")},
     {"owner":path.join("relocated.h5"),"stored_filename":"/missing/acquisition/b.h5","actual_file":path.join("parts/b.h5")}
    ])
}
#[test]
fn standard_open_follows_multiple_exact_relative_companions_and_vds_frames() {
    let temp = tempfile::tempdir().unwrap();
    fixtures::generate(temp.path());
    let mut s = Session::new(root());
    for name in ["eiger-master.h5", "virtual.h5", "nested.h5"] {
        let opened = call(&mut s, "open_image", json!({"path":temp.path().join(name)}));
        assert_eq!(opened.result["state"]["integration"]["frames"], 4);
        assert_eq!(opened.result["nativeSource"]["dtype"], "U16");
        assert_eq!(opened.result["state"]["imageSourceError"], Value::Null);
        for (frame, expected) in [(1, 10.), (2, 11.), (3, 30.), (4, 31.)] {
            call(&mut s, "integration_navigation", json!({"frame":frame}));
            assert_eq!(pixel(&mut s), expected);
        }
    }
    call(
        &mut s,
        "open_image",
        json!({"path":temp.path().join("eiger-master.h5")}),
    );
    geometry(&mut s);
    call(&mut s, "integration_navigation", json!({"frame":4}));
    let selected = call(
        &mut s,
        "select_image_source",
        json!({"dataset":"/entry/data/data_000001"}),
    );
    assert_eq!(selected.result["state"]["integration"]["frame"], 2);
    assert_eq!(pixel(&mut s), 11.);
    call(&mut s, "select_image_source", json!({"dataset":""}));
    assert_eq!(pixel(&mut s), 11.);
    // Nonuniform original words verify the single stored-to-scientific row flip.
    let ramp = Image::open(&temp.path().join("ramp.h5"), &json!({"frame":1})).unwrap();
    assert_eq!(ramp.shape, [24, 32]);
    assert!(
        matches!(ramp.original_pixels(),dioptrin_io::PixelBuffer::U16(v) if *v == (768..1536).collect::<Vec<u16>>())
    );
    assert_eq!(ramp.values[0], (768 + 23 * 32) as f64);
    assert!(ramp.combined_source(0).unwrap().is_none());
}
#[test]
fn source_requirements_are_read_only_and_choices_round_trip_offline() {
    let temp = tempfile::tempdir().unwrap();
    fixtures::generate(temp.path());
    let mut s = Session::new(root());
    call(
        &mut s,
        "open_image",
        json!({"path":temp.path().join("mixed.h5"),"frame":1}),
    );
    geometry(&mut s);
    let before = call(&mut s, "state", json!({})).result;
    let request = call(&mut s, "select_image_source", json!({"dataset":"/virtual"}));
    assert_eq!(request.result["cancelled"], true);
    assert_eq!(
        request.result["hdf5SourceRequest"]["requirements"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    assert_eq!(call(&mut s, "state", json!({})).result, before);
    let mut options = request.result["hdf5SourceRequest"]["options"].clone();
    options["hdf5_bindings"] = choices(temp.path());
    let opened = call(&mut s, "open_image", options);
    assert_eq!(opened.result["state"]["integration"]["frame"], 2);
    assert_eq!(pixel(&mut s), 11.);
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    call(
        &mut s,
        "select_image_source",
        json!({"dataset":"/ordinary"}),
    );
    assert_eq!(pixel(&mut s), 7.);
    let project = temp.path().join("sources.dio");
    call(&mut s, "save_project", json!({"path":project}));
    drop(s); // Close acquisition readers before moving the companion directory.
    std::fs::rename(temp.path().join("parts"), temp.path().join("offline-parts")).unwrap();
    let mut restored = Session::new(root());
    call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(pixel(&mut restored), 7.);
    call(
        &mut restored,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(pixel(&mut restored), 11.);
    let cached = call(&mut restored, "state", json!({})).result;
    let failed = invoke(&mut restored, "integration_navigation", json!({"frame":3}));
    assert_eq!(failed.result["ok"], false);
    assert_eq!(call(&mut restored, "state", json!({})).result, cached);
    std::fs::rename(temp.path().join("offline-parts"), temp.path().join("parts")).unwrap();
    call(&mut restored, "integration_navigation", json!({"frame":3}));
    assert_eq!(pixel(&mut restored), 30.);
    #[cfg(debug_assertions)]
    {
        let checkpoint = temp.path().join("development.dio");
        call(
            &mut restored,
            "development_checkpoint",
            json!({"path":checkpoint}),
        );
        let mut worker = Session::new(root());
        call(
            &mut worker,
            "development_restore",
            json!({"path":checkpoint}),
        );
        call(&mut worker, "integration_navigation", json!({"frame":4}));
        assert_eq!(pixel(&mut worker), 31.);
        assert_eq!(
            call(&mut worker, "state", json!({})).result["state"]["configurationCount"],
            2
        );
    }
    // Format-2 owned cache remains independent; the external acquisition file was never rewritten.
    let image = Image::open(
        &temp.path().join("parts/a.h5"),
        &json!({"dataset":"/images"}),
    )
    .unwrap();
    assert_eq!(image.values[0], 10.);
}
#[test]
fn raw_windows_missing_changed_unsupported_and_cancelled_loads_roll_back() {
    let temp = tempfile::tempdir().unwrap();
    fixtures::generate(temp.path());
    let mut s = Session::new(root());
    call(
        &mut s,
        "open_image",
        json!({"path":temp.path().join("raw.h5")}),
    );
    assert_eq!(pixel(&mut s), 50.);
    call(&mut s, "integration_navigation", json!({"frame":2}));
    assert_eq!(pixel(&mut s), 51.);
    let stable = call(&mut s, "state", json!({})).result;
    for file in ["overlap.h5", "cycle.h5"] {
        let r = invoke(&mut s, "open_image", json!({"path":temp.path().join(file)}));
        assert_eq!(r.result["ok"], false, "{}", r.result);
        assert_eq!(call(&mut s, "state", json!({})).result, stable);
    }
    let control = Arc::new(Control::default());
    control.cancel();
    let cancelled = s.invoke_controlled(
        &request("open_image", json!({"path":temp.path().join("virtual.h5")})),
        control,
    );
    assert_eq!(cancelled.result["ok"], false);
    assert_eq!(call(&mut s, "state", json!({})).result, stable);
    std::fs::write(temp.path().join("counts-b.bin"), [0; 8]).unwrap();
    assert_eq!(
        invoke(&mut s, "integration_navigation", json!({"frame":1})).result["ok"],
        false
    );
    assert_eq!(call(&mut s, "state", json!({})).result, stable);
    // Explicit reopen diagnoses the invalid raw window rather than filling it.
    let invalid = invoke(
        &mut s,
        "open_image",
        json!({"path":temp.path().join("raw.h5")}),
    );
    assert_eq!(invalid.result["ok"], false);
    assert!(
        invalid.result["error"]
            .as_str()
            .unwrap()
            .contains("complete frozen source window")
    );
}
#[test]
#[cfg(feature = "dioptrin")]
fn series_owns_source_choices_after_switching_and_project_reopen() {
    let temp = tempfile::tempdir().unwrap();
    fixtures::generate(temp.path());
    let mut s = Session::new(root());
    let master = temp.path().join("eiger-master.h5");
    call(&mut s, "open_image", json!({"path":master}));
    geometry(&mut s);
    let first = call(&mut s, "integrate", json!({}));
    call(&mut s, "batch_load", json!({"paths":[master]}));
    call(&mut s, "map_load", json!({"paths":[master]}));
    call(
        &mut s,
        "select_image_source",
        json!({"dataset":"/entry/data/data_000001"}),
    );
    let b = call(&mut s, "batch_select", json!({"index":3}));
    assert_eq!(pixel(&mut s), 31.);
    assert!(b.result["state"]["selectedImageSource"].is_null());
    let expected = first.result["pattern"]["y"].as_array().unwrap();
    let actual = b.result["pattern"]["y"].as_array().unwrap();
    for (a, b) in actual.iter().zip(expected) {
        let expected = b.as_f64().unwrap() * 3.1;
        assert!((a.as_f64().unwrap() - expected).abs() < 1e-8 * (1. + expected.abs()));
    }
    call(
        &mut s,
        "select_image_source",
        json!({"dataset":"/entry/data/data_000001"}),
    );
    let m = call(
        &mut s,
        "map_select",
        json!({"index":2,"integration_view":true}),
    );
    assert_eq!(pixel(&mut s), 30.);
    assert!(m.result["state"]["selectedImageSource"].is_null());
    let project = temp.path().join("series.dio");
    call(&mut s, "save_project", json!({"path":project}));
    let mut restored = Session::new(root());
    call(&mut restored, "open_project", json!({"path":project}));
    call(
        &mut restored,
        "select_image_source",
        json!({"dataset":"/entry/data/data_000001"}),
    );
    call(&mut restored, "batch_select", json!({"index":3}));
    assert_eq!(pixel(&mut restored), 31.);
    call(
        &mut restored,
        "select_image_source",
        json!({"dataset":"/entry/data/data_000001"}),
    );
    call(&mut restored, "map_load", json!({"reintegrate":true}));
    call(
        &mut restored,
        "map_select",
        json!({"index":3,"integration_view":true}),
    );
    assert_eq!(pixel(&mut restored), 31.);
    // The same generic VDS/raw paths are valid bulk inputs; no fused-path admission is required.
    for file in ["nested.h5", "raw.h5"] {
        call(
            &mut restored,
            "open_image",
            json!({"path":temp.path().join(file)}),
        );
        call(
            &mut restored,
            "batch_load",
            json!({"paths":[temp.path().join(file)]}),
        );
        call(
            &mut restored,
            "map_load",
            json!({"paths":[temp.path().join(file)]}),
        );
    }
}
#[test]
fn compressed_master_keeps_only_external_acquisition_identities_on_reopen() {
    let temp = tempfile::tempdir().unwrap();
    fixtures::generate(temp.path());
    let master = temp.path().join("relocated.h5.gz");
    fixtures::compressed(&temp.path().join("relocated.h5"), &master);
    let mut s = Session::new(root());
    let pending = call(&mut s, "open_image", json!({"path":master}));
    let source_request = &pending.result["hdf5SourceRequest"];
    assert_eq!(
        source_request["path"],
        json!(master.canonicalize().unwrap())
    );
    let mut options = source_request["options"].clone();
    let mut bindings = choices(temp.path());
    for binding in bindings.as_array_mut().unwrap() {
        binding["owner"] = json!(master);
    }
    options["hdf5_bindings"] = bindings;
    call(&mut s, "open_image", options);
    assert_eq!(pixel(&mut s), 10.);
    let project = temp.path().join("compressed.dio");
    call(&mut s, "save_project", json!({"path":project}));
    let mut restored = Session::new(root());
    call(&mut restored, "open_project", json!({"path":project}));
    assert_eq!(pixel(&mut restored), 10.);
    call(&mut restored, "integration_navigation", json!({"frame":4}));
    assert_eq!(pixel(&mut restored), 31.);
}

#[test]
#[cfg(feature = "dioptrin")]
fn compressed_master_batch_uses_external_identity_not_private_decode_paths() {
    let temp = tempfile::tempdir().unwrap();
    fixtures::generate(temp.path());
    let master = temp.path().join("virtual.h5.gz");
    fixtures::compressed(&temp.path().join("virtual.h5"), &master);
    let mut s = Session::new(root());
    call(&mut s, "open_image", json!({"path":master}));
    geometry(&mut s);
    call(&mut s, "batch_load", json!({"paths":[master]}));
    call(&mut s, "batch_select", json!({"index":3}));
    assert_eq!(pixel(&mut s), 31.);
}

#[test]
fn binding_dialog_cannot_resume_a_changed_master() {
    let temp = tempfile::tempdir().unwrap();
    fixtures::generate(temp.path());
    let mut s = Session::new(root());
    let master = temp.path().join("relocated.h5");
    call(
        &mut s,
        "open_image",
        json!({"path":temp.path().join("raw.h5")}),
    );
    let before = call(&mut s, "state", json!({})).result;
    let pending = call(&mut s, "open_image", json!({"path":master}));
    let mut options = pending.result["hdf5SourceRequest"]["options"].clone();
    options["hdf5_bindings"] = choices(temp.path());
    std::fs::rename(&master, temp.path().join("old-master.h5")).unwrap();
    std::fs::copy(temp.path().join("virtual.h5"), &master).unwrap();
    let changed = invoke(&mut s, "open_image", options);
    assert_eq!(changed.result["ok"], false);
    assert!(
        changed.result["error"]
            .as_str()
            .unwrap()
            .contains("source changed")
    );
    assert_eq!(call(&mut s, "state", json!({})).result, before);
}

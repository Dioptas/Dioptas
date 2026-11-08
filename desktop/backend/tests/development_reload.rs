#![cfg(debug_assertions)]
use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn request(s: &mut Session, action: &str, payload: Value) -> Reply {
    s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    })
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = request(s, action, payload);
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn image(path: &Path, value: u16) {
    tiff::encoder::TiffEncoder::new(std::fs::File::create(path).unwrap())
        .unwrap()
        .write_image::<tiff::encoder::colortype::Gray16>(32, 24, &vec![value; 768])
        .unwrap();
}
fn select(s: &mut Session, i: usize) -> Reply {
    call(s, "configuration", json!({"operation":"select","index":i}))
}
#[test]
fn development_handoff_owns_all_images_and_retains_settings_identities_and_project_path() {
    let tmp = tempfile::tempdir().unwrap();
    let a = tmp.path().join("first.tif");
    let b = tmp.path().join("second.tif");
    image(&a, 10);
    image(&b, 40);
    let mut old = Session::new(root());
    call(&mut old, "open_image", json!({"path":a}));
    call(
        &mut old,
        "manual_geometry",
        json!({"convention":"pyfai","values":{"dist":0.15,"poni1":0.0012,"poni2":0.0016,"pixel1":0.0001,"pixel2":0.0001,"wavelength":4e-11,"rot1":0.,"rot2":0.,"rot3":0.,"polarization_factor":0.99}}),
    );
    call(
        &mut old,
        "integration_settings",
        json!({"bins":32,"cake_bins":12}),
    );
    call(
        &mut old,
        "mask_stroke",
        json!({"points":[[10.,10.]],"radius":2}),
    );
    call(&mut old, "configuration", json!({"operation":"duplicate"}));
    call(&mut old, "open_image", json!({"path":b}));
    call(
        &mut old,
        "integration_settings",
        json!({"unit":"q_A^-1","bins":48,"supersampling":2}),
    );
    call(
        &mut old,
        "combination_settings",
        json!({"patterns":true,"cakes":true,"factor":2}),
    );
    call(
        &mut old,
        "validation_position",
        json!({"source":"cake","unit":"2th_deg","x":0.4,"azimuth":35.}),
    );
    let project = tmp.path().join("authored.dio");
    call(&mut old, "save_project", json!({"path":project}));
    let authored = std::fs::read(&project).unwrap();
    select(&mut old, 0);
    let first = call(&mut old, "state", json!({}));
    select(&mut old, 1);
    let second = call(&mut old, "state", json!({}));
    let checkpoint = tmp.path().join("private.dio");
    call(
        &mut old,
        "development_checkpoint",
        json!({"path":checkpoint}),
    );
    assert_eq!(
        call(&mut old, "state", json!({})).result,
        second.result,
        "Checkpoint must not mutate the live session"
    );
    assert_eq!(std::fs::read(&project).unwrap(), authored);
    // Restoration must use owned detector/correction data, not source-file reopening.
    std::fs::remove_file(a).unwrap();
    std::fs::remove_file(b).unwrap();
    let mut next = Session::new(root());
    call(&mut next, "development_restore", json!({"path":checkpoint}));
    for (i, before) in [(0, first), (1, second)] {
        let after = select(&mut next, i);
        for key in [
            "configurationContext",
            "configurationLabels",
            "configurationIndex",
            "imagePath",
            "imageName",
            "shape",
            "geometry",
            "unit",
            "bins",
            "useMask",
            "maskedPixels",
            "projectName",
            "projectPath",
            "combination",
        ] {
            assert_eq!(
                after.result["state"][key], before.result["state"][key],
                "Configuration {i}: {key}"
            );
        }
        assert_eq!(after.result["linked"], before.result["linked"]);
        assert_eq!(after.result["pattern"]["y"], before.result["pattern"]["y"]);
    }
    let user_save = tmp.path().join("new-save.dio");
    call(&mut next, "save_project", json!({"path":user_save}));
    assert!(
        !hdf5::File::open(user_save)
            .unwrap()
            .link_exists("development_session")
    );
    let previous = call(&mut next, "state", json!({}));
    let bad = tmp.path().join("broken.dio");
    std::fs::write(&bad, b"broken").unwrap();
    assert_eq!(
        request(&mut next, "development_restore", json!({"path":bad})).result["ok"],
        false
    );
    assert_eq!(call(&mut next, "state", json!({})).result, previous.result);
}
#[test]
fn empty_untitled_sessions_survive_a_development_handoff() {
    let tmp = tempfile::tempdir().unwrap();
    let p = tmp.path().join("session.dio");
    let mut s = Session::new(root());
    call(
        &mut s,
        "integration_settings",
        json!({"bins":777,"unit":"d_A"}),
    );
    let before = call(&mut s, "state", json!({}));
    call(&mut s, "development_checkpoint", json!({"path":p}));
    let mut n = Session::new(root());
    let after = call(&mut n, "development_restore", json!({"path":p}));
    for key in [
        "hasImage",
        "unit",
        "bins",
        "projectName",
        "projectPath",
        "configurationContext",
    ] {
        assert_eq!(
            after.result["state"][key], before.result["state"][key],
            "{key}"
        );
    }
}

#[test]
fn upgrading_an_older_host_can_adopt_a_private_project_without_using_it_as_the_save_target() {
    let t = tempfile::tempdir().unwrap();
    let p = t.path().join("recovery.dio");
    let mut old = Session::new(root());
    call(
        &mut old,
        "integration_settings",
        json!({"bins":777,"unit":"q_A^-1"}),
    );
    call(&mut old, "save_project", json!({"path":p}));
    let mut new = Session::new(root());
    let recovered = call(
        &mut new,
        "development_restore",
        json!({"path":p,"project_only":true}),
    );
    assert_eq!(recovered.result["state"]["bins"], 777);
    assert_eq!(recovered.result["state"]["unit"], "q_A^-1");
    assert!(recovered.result["state"]["projectName"].is_null());
}

use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .canonicalize()
        .unwrap()
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r
}
fn bytes(r: &Reply, key: &str) -> Vec<u8> {
    let id = r.result[key]["bufferId"].as_str().unwrap();
    r.buffers
        .iter()
        .find(|b| b.id == id)
        .unwrap()
        .bytes
        .to_vec()
}
#[test]
fn eiger_gap_margins_follow_source_flags_and_survive_projects_and_series() {
    let temp = tempfile::tempdir().unwrap();
    let [h, w] = [256, 514];
    let mut session = Session::new(root());
    call(
        &mut session,
        "integration_settings",
        json!({"bins":48,"cake_bins":12,"trim_zeros":false,"poisson_errors":true}),
    );
    call(
        &mut session,
        "manual_geometry",
        json!({"convention":"pyfai","values":{"dist":0.2,"poni1":0.0096,"poni2":0.019275,"rot1":0.,"rot2":0.,"rot3":0.,"pixel1":0.00015,"pixel2":0.00015,"wavelength":4e-11,"polarization_factor":0.}}),
    );
    // Manual geometry retains the explicit detector when its pixel pitches agree.
    call(
        &mut session,
        "calibration_setup",
        json!({"detector":"Eiger2 CdTe 500k"}),
    );
    let mut sources = vec![];
    for (index, flag) in [i32::MAX, 0, -1].into_iter().enumerate() {
        let path = temp.path().join(format!("scan{index}.h5"));
        let mut raw = vec![120i32; h * w];
        for r in 0..h {
            for c in 254..260 {
                raw[r * w + c] = flag;
            }
        }
        raw[40 * w + 40] = 0;
        raw[40 * w + 50] = flag;
        raw[42 * w + 50] = 6_000_000;
        {
            let f = hdf5::File::create(&path).unwrap();
            f.new_dataset::<i32>()
                .shape([1, h, w])
                .create("counts")
                .unwrap()
                .write_raw(&raw)
                .unwrap();
        }
        let opened = call(
            &mut session,
            "open_image",
            json!({"path":path,"dataset":"/counts"}),
        );
        let mask = bytes(&opened, "mask");
        for r in 0..h {
            for c in 254..260 {
                assert_eq!(mask[r * w + c], 1, "flag {flag}");
            }
        }
        assert_eq!(
            mask[(h - 1 - 40) * w + 40],
            0,
            "valid zero inside a module must survive"
        );
        let point = [(h - 1 - 40), 50];
        assert_eq!(mask[point[0] * w + point[1]], u8::from(flag != 0));
        assert_eq!(
            mask[(h - 1 - 42) * w + 50],
            0,
            "high measured counts are preserved"
        );
        if flag != 0 {
            // Explicitly masking the known invalid pixel must not change its
            // exclusion, normalization, pattern or cake.
            let explicit = call(
                &mut session,
                "mask_edit",
                json!({"operation":"rectangle","points":[[point[1],point[0]],[point[1]+1,point[0]+1]]}),
            );
            assert_eq!(opened.result["pattern"], explicit.result["pattern"]);
            assert_eq!(bytes(&opened, "cake"), bytes(&explicit, "cake"));
            let disabled = call(
                &mut session,
                "integration_settings",
                json!({"use_mask":false}),
            );
            assert_eq!(
                opened.result["pattern"], disabled.result["pattern"],
                "intrinsic detector invalids do not depend on the optional user mask"
            );
            call(
                &mut session,
                "integration_settings",
                json!({"use_mask":true}),
            );
            call(&mut session, "clear_mask", json!({}));
        }
        sources.push(path);
    }
    call(&mut session, "map_load", json!({"paths":sources}));
    let reference = call(&mut session, "state", json!({}));
    let selected = call(
        &mut session,
        "map_select",
        json!({"index":0,"reintegrate":true}),
    );
    assert!(selected.result["cake"].is_null());
    let project = temp.path().join("gaps.dio");
    call(&mut session, "save_project", json!({"path":project}));
    drop(session); // Windows locks acquisition files while their readers are open.
    for source in sources {
        std::fs::remove_file(source).unwrap();
    }
    let mut reopened = Session::new(root());
    let restored = call(&mut reopened, "open_project", json!({"path":project}));
    assert_eq!(bytes(&selected, "mask"), bytes(&restored, "mask"));
    assert_eq!(restored.result["pattern"], selected.result["pattern"]);
    assert_eq!(
        restored.result["map"]["values"],
        reference.result["map"]["values"]
    );
}

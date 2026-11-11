use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    let r = s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(r.result["ok"], true, "{}", r.result);
    r
}
fn editor(s: &mut Session, index: usize) -> Value {
    call(s, "integration_phase_editor", json!({"index":index})).result["phaseEditor"].clone()
}
fn edit(s: &mut Session, before: &Value, changes: Value) -> Value {
    call(s,"integration_phase",json!({"operation":"editor_transaction","edit_operation":"editor_metadata","editor":true,"editor_uid":before["uid"],"record_index":before["reference"],"expected_record_token":before["recordToken"],"changes":changes})).result["phaseEditor"].clone()
}
fn prepared(s: &mut Session, file: &Path) {
    call(
        s,
        "integration_phase",
        json!({"operation":"load","path":root().join("dioptas/tests/data/jcpds/mo.jcpds")}),
    );
    call(
        s,
        "integration_phase",
        json!({"operation":"editor_record","index":0,"action":"add"}),
    );
    call(
        s,
        "integration_phase",
        json!({"operation":"editor_thermal_type","index":0,"value":"AlphaKT"}),
    );
    call(
        s,
        "integration_phase_export",
        json!({"index":0,"path":file}),
    );
    let mut doc: Value = serde_json::from_slice(&std::fs::read(file).unwrap()).unwrap();
    let r = &mut doc["eos_records"][0];
    r["reference"] = json!({"authors":["Original Author"],"year":2001,"source":"Original Journal","unknown_reference":{"verbatim":"retain"}});
    r["parameter_errors"] = json!({"K0":null,"unknown_error":0.375});
    r["fixed_parameters"] = json!(["unknown_fixed"]);
    r["thermal"]["parameter_errors"] = json!({"unknown_thermal_error":0.25});
    r["thermal"]["fixed_parameters"] = json!(["unknown_thermal_fixed"]);
    r["validity"] = json!({"unknown_domain":"retain"});
    r["unknown_metadata"] =
        json!({"values":[null,"verbatim",-2.5],"exact_integer":9007199254740993_u64});
    std::fs::write(file, serde_json::to_vec(&doc).unwrap()).unwrap();
    call(
        s,
        "integration_phase",
        json!({"operation":"reload","index":0}),
    );
}
#[test]
fn metadata_roundtrips_without_changing_science_and_preserves_independent_records() {
    let temp = tempfile::tempdir().unwrap();
    let file = temp.path().join("material.eosmat");
    let mut s = Session::new(root());
    call(
        &mut s,
        "open_image",
        json!({"path":root().join("dioptas/tests/data/CeO2_Pilatus1M.tif")}),
    );
    call(
        &mut s,
        "open_calibration",
        json!({"path":root().join("dioptas/tests/data/CeO2_Pilatus1M.poni")}),
    );
    call(
        &mut s,
        "integration_settings",
        json!({"bins":64,"cake_bins":12}),
    );
    prepared(&mut s, &file);
    let original = editor(&mut s, 0);
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"editor_record","index":0,"action":"duplicate"}),
    );
    let before = editor(&mut s, 0);
    let state_before = call(&mut s, "state", json!({}));
    let changes = json!({"reference":{"authors":["Smith, A.","Long Author, B."],"authors_truncated":true,"year":2026,"source":"Journal of Mineral Physics","volume":"42","locator":"e12345–e12359","doi":"10.0000/example","details":"Original reported convention retained"},"notes":"Sample and fit notes\nSecond line","ranges":{"experimental_pressure_range_gpa":[-1.,125.],"experimental_temperature_range_k":[298.,2000.],"pressure_gpa":[-2.,150.],"temperature_k":[200.,2200.]},"parameters":[{"scope":"eos","key":"K0","error":-1.25,"fixed":true},{"scope":"thermal","key":"alpha0","error":0.0000001,"fixed":true}]});
    let after = edit(&mut s, &before, changes);
    assert!(after["editError"].is_null(), "{after}");
    let r = &after["recordData"];
    assert_eq!(r["eos"], before["recordData"]["eos"]);
    assert_eq!(
        r["thermal"]["parameters"],
        before["recordData"]["thermal"]["parameters"]
    );
    for key in [
        "identifier",
        "default",
        "default_for",
        "unknown_metadata",
        "temperature_ref",
    ] {
        assert_eq!(r[key], before["recordData"][key], "{key}");
    }
    assert_eq!(
        r["reference"]["unknown_reference"],
        before["recordData"]["reference"]["unknown_reference"]
    );
    assert_eq!(
        r["parameter_errors"]["unknown_error"],
        before["recordData"]["parameter_errors"]["unknown_error"]
    );
    assert_eq!(r["fixed_parameters"], json!(["unknown_fixed", "K0"]));
    assert_eq!(
        r["thermal"]["fixed_parameters"],
        json!(["unknown_thermal_fixed", "alpha0"])
    );
    assert_eq!(after["lattice"], before["lattice"]);
    assert_eq!(after["reflections"], before["reflections"]);
    let state_after = call(&mut s, "state", json!({}));
    for key in ["rawImage", "image", "cake", "pattern"] {
        assert_eq!(state_after.result[key], state_before.result[key], "{key}");
    }
    call(
        &mut s,
        "integration_phase_export",
        json!({"index":0,"save_current":true}),
    );
    let saved: Value = serde_json::from_slice(&std::fs::read(&file).unwrap()).unwrap();
    assert_eq!(&saved["eos_records"][1], r);
    assert_eq!(saved["eos_records"][0], original["recordData"]);
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"reload","index":0}),
    );
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"update","index":0,"reference":1}),
    );
    assert_eq!(editor(&mut s, 0)["recordData"], *r);
    let project = temp.path().join("native-format-2.dio");
    call(&mut s, "save_project", json!({"path":project}));
    std::fs::remove_file(&file).unwrap();
    let mut restored = Session::new(root());
    call(&mut restored, "open_project", json!({"path":project}));
    let reopened = editor(&mut restored, 0);
    assert_eq!(reopened["recordData"], *r);
    assert_eq!(reopened["reference"], 1);
    assert_eq!(reopened["defaultReference"], original["defaultReference"]);
    let cleared = edit(
        &mut restored,
        &reopened,
        json!({"notes":"","reference":{"authors":[],"authors_truncated":false,"year":null,"source":"","volume":"","locator":"","doi":"","details":""},"temperature_ref":null,"ranges":{"experimental_pressure_range_gpa":null,"experimental_temperature_range_k":null,"pressure_gpa":null,"temperature_k":null},"parameters":[{"scope":"eos","key":"K0","error":null,"fixed":false},{"scope":"thermal","key":"alpha0","error":null,"fixed":false}]}),
    );
    assert!(cleared["editError"].is_null(), "{}", cleared["editError"]);
    let c = &cleared["recordData"];
    for key in [
        "notes",
        "temperature_ref",
        "experimental_pressure_range_gpa",
        "experimental_temperature_range_k",
    ] {
        assert!(c.get(key).is_none(), "{key}");
    }
    assert_eq!(
        c["reference"],
        json!({"unknown_reference":{"verbatim":"retain"}})
    );
    assert_eq!(c["validity"], json!({"unknown_domain":"retain"}));
    assert_eq!(c["parameter_errors"]["K0"], Value::Null);
    assert_eq!(c["fixed_parameters"], json!(["unknown_fixed"]));
    assert_eq!(c["thermal"]["parameters"], r["thermal"]["parameters"]);
    let cleared_file = temp.path().join("cleared.eosmat");
    call(
        &mut restored,
        "integration_phase_export",
        json!({"index":0,"path":cleared_file}),
    );
    call(
        &mut restored,
        "integration_phase",
        json!({"operation":"reload","index":0}),
    );
    call(
        &mut restored,
        "integration_phase",
        json!({"operation":"update","index":0,"reference":1}),
    );
    assert_eq!(editor(&mut restored, 0)["recordData"], *c);
    for reference in [
        json!({"authors":["Only Author"]}),
        json!({"authors":[],"year":2026}),
        json!({"authors":["Author"],"year":0}),
        json!({"details":"Free text citation","year":null,"authors":[]}),
    ] {
        let current = editor(&mut restored, 0);
        let edited = edit(&mut restored, &current, json!({"reference":reference}));
        assert!(edited["editError"].is_null(), "{}", edited["editError"]);
        call(
            &mut restored,
            "integration_phase_export",
            json!({"index":0,"path":cleared_file}),
        );
        call(
            &mut restored,
            "integration_phase",
            json!({"operation":"reload","index":0}),
        );
        call(
            &mut restored,
            "integration_phase",
            json!({"operation":"update","index":0,"reference":1}),
        );
        assert_eq!(editor(&mut restored, 0)["recordData"], edited["recordData"]);
    }
}
#[test]
fn validation_stale_selection_and_source_protection_are_atomic() {
    let temp = tempfile::tempdir().unwrap();
    let mut s = Session::new(root());
    prepared(&mut s, &temp.path().join("m.eosmat"));
    let before = editor(&mut s, 0);
    for changes in [
        json!({"notes":"must roll back","reference":{"year":2026.5}}),
        json!({"notes":"must roll back","temperature_ref":-1}),
        json!({"notes":"must roll back","ranges":{"pressure_gpa":[3,2]}}),
        json!({"reference":{"authors":"not a list"}}),
        json!({"ranges":{"temperature_k":[-1,2000]}}),
        json!({"parameters":[{"scope":"eos","key":"K0","error":"invalid"}]}),
        json!({"parameters":[{"scope":"eos","key":"invented_coefficient","fixed":true}]}),
        json!({"eos":{"parameters":{"K0":1}}}),
    ] {
        let rejected = edit(&mut s, &before, changes);
        assert!(rejected["editError"].is_string(), "{rejected}");
        assert_eq!(editor(&mut s, 0)["recordData"], before["recordData"]);
    }
    let after = edit(&mut s, &before, json!({"notes":"Applied"}));
    assert!(after["editError"].is_null());
    assert!(edit(&mut s, &before, json!({"notes":"stale overwrite"}))["editError"].is_string());
    assert_eq!(editor(&mut s, 0)["recordData"], after["recordData"]);
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"editor_record","index":0,"action":"duplicate"}),
    );
    assert!(edit(&mut s, &after, json!({"notes":"wrong record"}))["editError"].is_string());
    // Bundled records are protected even when a caller forges editable UI state.
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"load_database","material_id":"gold","reference":4}),
    );
    let source = editor(&mut s, 1);
    assert_eq!(source["editable"], false);
    assert!(edit(&mut s, &source, json!({"notes":"forbidden"}))["editError"].is_string());
    assert_eq!(editor(&mut s, 1)["recordData"], source["recordData"]);
    call(
        &mut s,
        "integration_phase",
        json!({"operation":"editor_copy","index":1}),
    );
    let copy = editor(&mut s, 2);
    let edited = edit(&mut s, &copy, json!({"notes":"User-owned copy"}));
    assert!(edited["editError"].is_null());
    assert_eq!(editor(&mut s, 1)["recordData"], source["recordData"]);
    assert_ne!(
        edited["recordData"]["scientific_validation"]["status"],
        "primary_source_validated"
    );
}

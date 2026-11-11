use dioptas_backend::{
    Session,
    protocol::{Reply, Request},
};
use serde_json::{Value, json};
use std::{
    path::{Path, PathBuf},
    str::FromStr,
};
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
fn call(s: &mut Session, action: &str, payload: Value) -> Value {
    let r = request(s, action, payload);
    assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
    r.result
}
fn phase(s: &mut Session, payload: Value) -> Value {
    call(s, "integration_phase", payload)
}
fn state(s: &mut Session) -> Value {
    call(s, "state", json!({}))
}
fn editor(s: &mut Session, i: usize) -> Value {
    call(s, "integration_phase_editor", json!({"index":i}))["phaseEditor"].clone()
}
fn gold(s: &mut Session, reference: usize) {
    phase(
        s,
        json!({"operation":"load_database","material_id":"gold","reference":reference}),
    );
}
fn project_doc(path: &Path) -> Value {
    let f = hdf5::File::open(path).unwrap();
    let text = f
        .dataset("state")
        .unwrap()
        .read_scalar::<hdf5::types::VarLenUnicode>()
        .unwrap();
    serde_json::from_str(text.as_str()).unwrap()
}
fn assert_same(a: &Value, b: &Value, path: &str) {
    if a == b {
        return;
    }
    match (a, b) {
        (Value::Object(a), Value::Object(b)) => {
            for key in a.keys().chain(b.keys()) {
                assert_same(
                    a.get(key).unwrap_or(&Value::Null),
                    b.get(key).unwrap_or(&Value::Null),
                    &format!("{path}.{key}"),
                );
            }
        }
        (Value::Array(a), Value::Array(b)) => {
            assert_eq!(a.len(), b.len(), "{path}");
            for (i, (a, b)) in a.iter().zip(b).enumerate() {
                assert_same(a, b, &format!("{path}[{i}]"));
            }
        }
        _ => assert_eq!(a, b, "{path}"),
    }
}
#[test]
fn factor_is_shared_and_retained_across_conditions_references_projects_and_history() {
    let temp = tempfile::tempdir().unwrap();
    let mut s = Session::new(root());
    gold(&mut s, 4);
    phase(
        &mut s,
        json!({"operation":"update","index":0,"pressure":40.,"temperature":2000.}),
    );
    let source = editor(&mut s, 0);
    let initial = state(&mut s);
    assert_eq!(
        initial["state"]["integration"]["phaseDacThermalPressureFactor"],
        0.25
    );
    phase(
        &mut s,
        json!({"operation":"dac_thermal_pressure","enabled":true,"factor":0.4}),
    );
    let confined = editor(&mut s, 0);
    assert!(confined["lattice"]["v"].as_f64().unwrap() < source["lattice"]["v"].as_f64().unwrap());
    assert_eq!(source["recordData"], confined["recordData"]);
    assert_eq!(source["modified"], confined["modified"]);
    call(&mut s, "undo_calibration", json!({}));
    assert_eq!(editor(&mut s, 0)["lattice"], source["lattice"]);
    call(&mut s, "redo_calibration", json!({}));
    assert_eq!(editor(&mut s, 0)["lattice"], confined["lattice"]);
    call(&mut s, "configuration", json!({"operation":"duplicate"}));
    phase(
        &mut s,
        json!({"operation":"dac_thermal_pressure","factor":0.75}),
    );
    call(
        &mut s,
        "configuration",
        json!({"operation":"select","index":0}),
    );
    assert_eq!(
        state(&mut s)["state"]["integration"]["phaseDacThermalPressureFactor"],
        0.75
    );
    phase(
        &mut s,
        json!({"operation":"dac_thermal_pressure","enabled":false}),
    );
    assert_eq!(editor(&mut s, 0)["lattice"], source["lattice"]);
    phase(
        &mut s,
        json!({"operation":"dac_thermal_pressure","enabled":true}),
    );
    gold(&mut s, 4);
    assert_eq!(editor(&mut s, 0)["lattice"], editor(&mut s, 1)["lattice"]);
    phase(
        &mut s,
        json!({"operation":"update","index":0,"pressure":35.,"temperature":1500.}),
    );
    assert_eq!(editor(&mut s, 0)["lattice"], editor(&mut s, 1)["lattice"]);
    phase(
        &mut s,
        json!({"operation":"same_conditions","enabled":false}),
    );
    phase(
        &mut s,
        json!({"operation":"update","index":1,"reference":3,"pressure":20.,"temperature":1000.}),
    );
    let before = state(&mut s);
    let e0 = editor(&mut s, 0);
    let e1 = editor(&mut s, 1);
    let path = temp.path().join("saved.dio");
    call(&mut s, "save_project", json!({"path":path}));
    let doc = project_doc(&path);
    assert_eq!(doc["phase"]["dac_thermal_pressure_factor"], 0.75);
    assert_eq!(doc["phase"]["dac_thermal_pressure_enabled"], true);
    for row in doc["phases"].as_array().unwrap() {
        assert!(row["crystal"]["material_document"]["dac_thermal_pressure_factor"].is_null());
    }
    let mut restored = Session::new(root());
    call(&mut restored, "open_project", json!({"path":path}));
    assert_eq!(editor(&mut restored, 0), e0);
    assert_eq!(editor(&mut restored, 1), e1);
    assert_eq!(
        state(&mut restored)["state"]["integration"],
        before["state"]["integration"]
    );
    let second = temp.path().join("again.dio");
    call(&mut restored, "save_project", json!({"path":second}));
    assert_eq!(project_doc(&second)["phase"], doc["phase"]);
    assert_same(&project_doc(&second)["phases"], &doc["phases"], "phases");
    // Off retains a nondefault selected fraction through a project round trip.
    phase(
        &mut restored,
        json!({"operation":"dac_thermal_pressure","enabled":false}),
    );
    call(&mut restored, "save_project", json!({"path":second}));
    call(&mut s, "open_project", json!({"path":second}));
    assert_eq!(
        state(&mut s)["state"]["integration"]["phaseDacThermalPressureFactor"],
        0.75
    );
    assert_eq!(
        state(&mut s)["state"]["integration"]["phaseColdPressure"],
        false
    );
}
#[test]
fn invalid_and_unsupported_changes_roll_back_every_phase_and_history() {
    let mut s = Session::new(root());
    gold(&mut s, 4);
    phase(
        &mut s,
        json!({"operation":"update","index":0,"pressure":20.,"temperature":1000.}),
    );
    // Maltby is an explicit thermal equation with no compatible DAC increment.
    phase(
        &mut s,
        json!({"operation":"load_database","material_id":"argon_fcc","reference":13}),
    );
    let before = state(&mut s);
    let a = editor(&mut s, 0);
    let b = editor(&mut s, 1);
    for factor in [
        json!(-0.1),
        json!(1.),
        json!(2.),
        json!(null),
        json!("NaN"),
        json!("Infinity"),
    ] {
        let r = request(
            &mut s,
            "integration_phase",
            json!({"operation":"dac_thermal_pressure","enabled":true,"factor":factor}),
        );
        assert_eq!(r.result["ok"], false, "{}", r.result);
        assert_eq!(state(&mut s), before);
    }
    let r = request(
        &mut s,
        "integration_phase",
        json!({"operation":"dac_thermal_pressure","enabled":true,"factor":0.4}),
    );
    assert_eq!(r.result["ok"], false, "{}", r.result);
    assert!(
        r.result["error"]
            .as_str()
            .unwrap()
            .contains("not supported")
    );
    assert_eq!(state(&mut s), before);
    assert_eq!(editor(&mut s, 0), a);
    assert_eq!(editor(&mut s, 1), b);
    phase(&mut s, json!({"operation":"remove","index":1}));
    phase(
        &mut s,
        json!({"operation":"dac_thermal_pressure","enabled":true,"factor":0.4}),
    );
    let active = state(&mut s);
    let rejected = request(
        &mut s,
        "integration_phase",
        json!({"operation":"load_database","material_id":"argon_fcc","reference":13}),
    );
    assert_eq!(rejected.result["ok"], false);
    assert_eq!(
        state(&mut s),
        active,
        "An unsupported addition must not change phase identity/order/history"
    );
    phase(
        &mut s,
        json!({"operation":"load_database","material_id":"argon_fcc","reference":1}),
    );
    let active = state(&mut s);
    let rejected = request(
        &mut s,
        "integration_phase",
        json!({"operation":"update","index":1,"reference":13}),
    );
    assert_eq!(rejected.result["ok"], false);
    assert_eq!(
        state(&mut s),
        active,
        "An incompatible selected record must roll back"
    );
}
#[test]
fn qt_format_two_factor_defaults_and_invalid_import_are_atomic() {
    let temp = tempfile::tempdir().unwrap();
    let mut s = Session::new(root());
    gold(&mut s, 4);
    let path = temp.path().join("qt-like.dio");
    call(&mut s, "save_project", json!({"path":path}));
    let original = project_doc(&path);
    for factor in [Some(json!(0.4)), None, Some(json!(1.)), Some(json!("nan"))] {
        let mut doc = original.clone();
        doc["phase"]["dac_thermal_pressure_enabled"] = json!(true);
        if let Some(f) = &factor {
            doc["phase"]["dac_thermal_pressure_factor"] = f.clone();
        } else {
            doc["phase"]
                .as_object_mut()
                .unwrap()
                .remove("dac_thermal_pressure_factor");
        }
        {
            let f = hdf5::File::open_rw(&path).unwrap();
            let text = hdf5::types::VarLenUnicode::from_str(&doc.to_string()).unwrap();
            f.dataset("state").unwrap().write_scalar(&text).unwrap();
        }
        let before = state(&mut s);
        let r = request(&mut s, "open_project", json!({"path":path}));
        if factor
            .as_ref()
            .is_some_and(|f| *f == json!(1.) || f.is_string())
        {
            assert_eq!(r.result["ok"], false);
            assert_eq!(state(&mut s), before);
        } else {
            assert_eq!(r.result["ok"], true, "{}", r.result);
            assert_eq!(
                state(&mut s)["state"]["integration"]["phaseDacThermalPressureFactor"],
                factor.unwrap_or(json!(0.25))
            );
        }
    }
}
#[test]
#[cfg(debug_assertions)]
fn development_checkpoint_retains_factor_and_undo_redo() {
    let temp = tempfile::tempdir().unwrap();
    let mut s = Session::new(root());
    gold(&mut s, 4);
    phase(
        &mut s,
        json!({"operation":"update","index":0,"pressure":40.,"temperature":2000.}),
    );
    phase(
        &mut s,
        json!({"operation":"dac_thermal_pressure","enabled":true,"factor":0.4}),
    );
    phase(
        &mut s,
        json!({"operation":"dac_thermal_pressure","factor":0.75}),
    );
    call(&mut s, "undo_calibration", json!({}));
    let expected = editor(&mut s, 0);
    let path = temp.path().join("checkpoint.dio");
    call(&mut s, "development_checkpoint", json!({"path":path}));
    let mut restored = Session::new(root());
    call(&mut restored, "development_restore", json!({"path":path}));
    assert_eq!(editor(&mut restored, 0), expected);
    call(&mut restored, "redo_calibration", json!({}));
    assert_eq!(
        state(&mut restored)["state"]["integration"]["phaseDacThermalPressureFactor"],
        0.75
    );
    call(&mut restored, "undo_calibration", json!({}));
    assert_eq!(editor(&mut restored, 0), expected);
}

use dioptas_backend::{Session, protocol::Request};
use serde_json::{Value, json};
use std::path::Path;

fn call(session: &mut Session, action: &str, payload: Value) -> Value {
    let reply = session.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(reply.result["ok"], true, "{}", reply.result);
    reply.result
}
fn editor(session: &mut Session) -> Value {
    call(session, "integration_phase_editor", json!({"index":0}))["phaseEditor"].clone()
}
#[test]
fn clearing_or_deleting_all_records_can_start_a_valid_new_eos() {
    for action in ["clear", "delete"] {
        let mut session = Session::new(Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."));
        call(
            &mut session,
            "integration_phase",
            json!({"operation":"load","path":Path::new(env!("CARGO_MANIFEST_DIR")).join("../../desktop/tests/data/jcpds/mo.jcpds")}),
        );
        call(
            &mut session,
            "integration_phase",
            json!({"operation":"editor_record","index":0,"action":"add"}),
        );
        let before = editor(&mut session);
        let mut remaining = before["references"].as_array().unwrap().len();
        while remaining > 0 {
            call(
                &mut session,
                "integration_phase",
                json!({"operation":"editor_record","index":0,"action":action}),
            );
            remaining = editor(&mut session)["references"].as_array().unwrap().len();
        }
        call(
            &mut session,
            "integration_phase",
            json!({"operation":"editor_record","index":0,"action":"add"}),
        );
        let created = editor(&mut session);
        assert_eq!(created["recordData"]["eos"]["parameters"]["K0"], 100.0);
        assert_eq!(created["lattice"]["v0"], before["lattice"]["v0"]);
        call(
            &mut session,
            "integration_phase",
            json!({"operation":"update","index":0,"pressure":10.0}),
        );
        call(
            &mut session,
            "integration_phase",
            json!({"operation":"editor_thermal_type","index":0,"value":"MieGruneisenDebye"}),
        );
        assert_eq!(editor(&mut session)["thermalType"], "MieGruneisenDebye");
    }
}
#[test]
fn adding_to_an_existing_eos_preserves_its_measured_modulus() {
    let mut session = Session::new(Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."));
    call(
        &mut session,
        "integration_phase",
        json!({"operation":"load","path":Path::new(env!("CARGO_MANIFEST_DIR")).join("../../desktop/tests/data/jcpds/mo.jcpds")}),
    );
    call(
        &mut session,
        "integration_phase",
        json!({"operation":"editor_record","index":0,"action":"add"}),
    );
    let before = editor(&mut session);
    call(
        &mut session,
        "integration_phase",
        json!({"operation":"editor_record","index":0,"action":"add"}),
    );
    assert_eq!(
        editor(&mut session)["recordData"]["eos"]["parameters"]["K0"],
        before["recordData"]["eos"]["parameters"]["K0"]
    );
}

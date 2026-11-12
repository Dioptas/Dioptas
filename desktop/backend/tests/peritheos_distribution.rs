//! Shipped EOS documents must remain valid without experimental observations.
use serde_json::Value;

#[test]
fn eos_only_catalog_retains_valid_refit_provenance_without_data() {
    let catalog: Vec<Value> =
        serde_json::from_str(include_str!("../resources/peritheos/materials.json")).unwrap();
    assert_eq!(catalog.len(), 234);
    let mut records = 0;
    let mut provenance = 0;
    for material in catalog {
        peritheos::eosmat::validate_eosmat_document(&material)
            .unwrap_or_else(|error| panic!("{}: {error}", material["identifier"]));
        records += material["eos_records"].as_array().unwrap().len();
        for dataset in material["datasets"].as_array().into_iter().flatten() {
            provenance += 1;
            assert_eq!(dataset["rows"], serde_json::json!([]));
            assert!(dataset.get("resource").is_none());
            assert!(dataset.get("source_tokens").is_none());
        }
    }
    assert_eq!(records, 685);
    assert_eq!(provenance, 456);
}

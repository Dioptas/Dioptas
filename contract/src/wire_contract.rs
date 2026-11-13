//! Structural types on the existing Tauri/stdin JSON metadata boundary.
//! These checks borrow metadata, never copy payload trees or inspect rasters.
use serde::Deserialize;
use serde_json::Value;

#[path = "native_payload_contracts.generated.rs"]
pub mod payloads;
pub use payloads::{DecisionKind, ResponseDisposition};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PayloadCoverage {
    /// Present field types are checked; handlers still own required fields,
    /// numeric ranges, defaults and operation-specific scientific invariants.
    TypedFields,
    /// Explicit compatibility boundary: dispatch/validation stays in its handler.
    Legacy,
}

const PRODUCTS_ERROR: &str =
    "Requested products must contain a cake boolean and optional rings boolean.";

pub fn validate_payload(action: &str, payload: &Value) -> Result<PayloadCoverage, String> {
    if !payload.is_object() {
        return Err("Command arguments must be an object.".into());
    }
    if let Some(products) = payload.get("requested_products") {
        // Keep the established error and strict keys, including null rejection.
        if !products.is_object()
            || !products["cake"].is_boolean()
            || products.as_object().unwrap().iter().any(|(key, value)| {
                !["cake", "rings"].contains(&key.as_str()) || !value.is_boolean()
            })
        {
            return Err(PRODUCTS_ERROR.into());
        }
        payloads::RequestedProducts::deserialize(products)
            .map_err(|_| PRODUCTS_ERROR.to_string())?;
    }
    payloads::validate_fields(action, payload)
        .map_err(|error| format!("Invalid {action} arguments: {error}"))
}

/// Additive metadata view. Scientific fields stay in their original response
/// object and binary buffers. Deferred decisions precede cancellation/failure,
/// matching the existing UI even when a deferred reply has cancelled=true.
#[derive(Debug, PartialEq)]
#[allow(dead_code)] // Shared API: host and processor consume different metadata.
pub struct ResponseMetadata<'a> {
    pub disposition: ResponseDisposition,
    pub decision: Option<DecisionKind>,
    pub ok: bool,
    pub cancelled: bool,
    pub fatal: bool,
    pub error: Option<&'a str>,
}

pub fn response_metadata(result: &Value) -> Result<ResponseMetadata<'_>, String> {
    let object = result
        .as_object()
        .ok_or("Response metadata must be an object.")?;
    let ok = object
        .get("ok")
        .and_then(Value::as_bool)
        .ok_or("Response metadata needs a boolean ok field.")?;
    let flag = |name| match object.get(name) {
        None | Some(Value::Null) => Ok(false),
        Some(value) => value
            .as_bool()
            .ok_or_else(|| format!("Response {name} must be a boolean.")),
    };
    let cancelled = flag("cancelled")?;
    let fatal = flag("fatal")?;
    let error = match object.get("error") {
        None | Some(Value::Null) => None,
        Some(value) => Some(value.as_str().ok_or("Response error must be a string.")?),
    };
    let decision = [
        ("hdf5SourceRequest", DecisionKind::Hdf5Source),
        ("imageChange", DecisionKind::ImageChange),
        ("calibrationChange", DecisionKind::CalibrationChange),
    ]
    .into_iter()
    .find_map(|(key, kind)| {
        object
            .get(key)
            .filter(|value| value.is_object())
            .map(|_| kind)
    });
    let disposition = if decision.is_some() {
        ResponseDisposition::Deferred
    } else if !ok {
        ResponseDisposition::Failed
    } else if cancelled {
        ResponseDisposition::Cancelled
    } else {
        ResponseDisposition::Applied
    };
    Ok(ResponseMetadata {
        disposition,
        decision,
        ok,
        cancelled,
        fatal,
        error,
    })
}

// Constructors prevent contradictory status flags at the common metadata-only
// response sites while preserving the existing JSON field names and wire bytes.
#[allow(dead_code)] // Used by processor errors; compiled into the host as well.
pub fn failure_metadata(error: impl ToString) -> Value {
    #[derive(serde::Serialize)]
    struct Failure {
        ok: bool,
        error: String,
    }
    serde_json::to_value(Failure {
        ok: false,
        error: error.to_string(),
    })
    .expect("String failure metadata is serializable")
}

#[allow(dead_code)] // Used by native host choosers, also compiled into processor.
pub fn cancelled_metadata() -> Value {
    #[derive(serde::Serialize)]
    struct Cancelled {
        ok: bool,
        cancelled: bool,
    }
    serde_json::to_value(Cancelled {
        ok: true,
        cancelled: true,
    })
    .expect("Boolean cancellation metadata is serializable")
}

#[allow(dead_code)] // Used by processor control replies; also compiled into host.
pub fn success_metadata() -> Value {
    #[derive(serde::Serialize)]
    struct Success {
        ok: bool,
    }
    serde_json::to_value(Success { ok: true }).expect("Boolean success metadata is serializable")
}

#[allow(dead_code)] // Processor decisions; shared host compiles the same contract.
pub fn deferred_metadata(kind: DecisionKind, decision: Value) -> Value {
    let mut result = cancelled_metadata();
    let key = match kind {
        DecisionKind::Hdf5Source => "hdf5SourceRequest",
        DecisionKind::ImageChange => "imageChange",
        DecisionKind::CalibrationChange => "calibrationChange",
    };
    // Move the existing decision object into its typed envelope; no tree clone.
    result.as_object_mut().unwrap().insert(key.into(), decision);
    result
}

/// Optional transport cache negotiation; never part of scientific payloads.
pub fn validate_cached_products(value: &serde_json::Value) -> Result<(), String> {
    let Some(products) = value.as_object() else {
        return Err("Invalid cached product table.".into());
    };
    if products.len() > 2
        || products.iter().any(|(field, id)| {
            !matches!(field.as_str(), "batch" | "map")
                || id.as_str().is_none_or(|id| {
                    id.is_empty()
                        || id.len() > 128
                        || !id
                            .bytes()
                            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b':' | b'-' | b'_'))
                })
        })
    {
        return Err("Invalid cached product table.".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn typed_fields_reject_wrong_types_without_narrowing_native_numbers_or_defaults() {
        for payload in [json!({"x":1,"y":2}), json!({"x":-1.25,"y":2.5}), json!({})] {
            assert_eq!(
                validate_payload("pixel", &payload).unwrap(),
                PayloadCoverage::TypedFields
            );
        }
        for payload in [json!({"x":"1","y":2}), json!({"x":true}), json!({"x":[]})] {
            assert!(validate_payload("pixel", &payload).is_err());
        }
        assert!(
            validate_payload("integration_flat_field", &json!({"path":null,"reset":true})).is_ok()
        );
        assert!(
            validate_payload(
                "integration_transfer",
                &json!({"source":"response","enabled":false})
            )
            .is_ok()
        );
        assert!(validate_payload("integration_transfer", &json!({"enabled":"false"})).is_err());
        // Missing fields, scalar ranges, irrelevant operation fields and tolerant
        // legacy source metadata remain the native handler's responsibility.
        assert!(
            validate_payload(
                "configuration",
                &json!({"operation":"rename","name":"A","index":"unused"})
            )
            .is_ok()
        );
        assert!(validate_payload("configuration", &json!({"operation":null,"index":0})).is_ok());
        assert!(validate_payload("pixel", &json!({"x":1,"y":2,"source":true})).is_ok());
        assert_eq!(
            validate_payload("unknown_legacy_command", &json!({"anything":[]})).unwrap(),
            PayloadCoverage::Legacy
        );
    }

    #[test]
    fn common_product_metadata_retains_its_existing_validation_contract() {
        for products in [
            json!({}),
            json!(null),
            json!({"cake":true,"extra":true}),
            json!({"cake":1}),
            json!({"cake":true,"rings":null}),
        ] {
            assert_eq!(
                validate_payload("state", &json!({"requested_products":products})).unwrap_err(),
                PRODUCTS_ERROR
            );
        }
        assert!(
            validate_payload(
                "state",
                &json!({"requested_products":{"cake":false,"rings":true}})
            )
            .is_ok()
        );
    }

    #[test]
    fn borrowed_path_dtos_and_response_errors_retain_original_storage() {
        let payload = json!({"path":"/owned/source.tif","enabled":true});
        let fields = payloads::TransferPayloadFields::deserialize(&payload).unwrap();
        assert_eq!(
            fields.path.unwrap().as_ptr(),
            payload["path"].as_str().unwrap().as_ptr()
        );
        let result = failure_metadata("Exact native failure");
        let metadata = response_metadata(&result).unwrap();
        assert_eq!(
            metadata.error.unwrap().as_ptr(),
            result["error"].as_str().unwrap().as_ptr()
        );
        assert_eq!(metadata.disposition, ResponseDisposition::Failed);
    }

    #[test]
    fn dispositions_preserve_existing_defer_cancel_error_precedence_and_wire_flags() {
        assert_eq!(
            failure_metadata("failure"),
            json!({"ok":false,"error":"failure"})
        );
        assert_eq!(cancelled_metadata(), json!({"ok":true,"cancelled":true}));
        assert_eq!(
            response_metadata(&success_metadata()).unwrap().disposition,
            ResponseDisposition::Applied
        );
        assert_eq!(
            response_metadata(&cancelled_metadata())
                .unwrap()
                .disposition,
            ResponseDisposition::Cancelled
        );
        for key in ["hdf5SourceRequest", "imageChange", "calibrationChange"] {
            let mut reply = json!({"ok":true,"cancelled":true});
            reply[key] = json!({"decision":"required"});
            assert_eq!(
                response_metadata(&reply).unwrap().disposition,
                ResponseDisposition::Deferred
            );
        }
        let both = json!({"ok":false,"hdf5SourceRequest":{},"imageChange":{}});
        assert_eq!(
            response_metadata(&both).unwrap().decision,
            Some(DecisionKind::Hdf5Source)
        );
        assert_eq!(
            response_metadata(&json!({"ok":false,"cancelled":true}))
                .unwrap()
                .disposition,
            ResponseDisposition::Failed
        );
        for invalid in [
            json!({}),
            json!({"ok":1}),
            json!({"ok":false,"error":42}),
            json!({"ok":true,"cancelled":"yes"}),
        ] {
            assert!(response_metadata(&invalid).is_err());
        }
    }

    #[test]
    fn typed_decision_envelopes_move_the_existing_object_without_cloning_it() {
        for (kind, key) in [
            (DecisionKind::Hdf5Source, "hdf5SourceRequest"),
            (DecisionKind::ImageChange, "imageChange"),
            (DecisionKind::CalibrationChange, "calibrationChange"),
        ] {
            let decision = json!({"path":"source.h5","options":{"dataset":"/counts"}});
            let source = decision["path"].as_str().unwrap().as_ptr();
            let result = deferred_metadata(kind, decision);
            assert_eq!(result[key]["path"].as_str().unwrap().as_ptr(), source);
            assert_eq!(result["ok"], true);
            assert_eq!(result["cancelled"], true);
            assert_eq!(response_metadata(&result).unwrap().decision, Some(kind));
        }
    }
}

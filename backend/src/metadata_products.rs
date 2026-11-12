//! Optional, per-client content-addressed Batch/Map metadata reuse.
//! Scientific command arguments and legacy full responses remain unchanged.
use serde::{Serialize, Serializer, ser::SerializeMap};
use serde_json::Value;
use std::{collections::BTreeMap, io::Write};

pub(crate) type CachedProducts = BTreeMap<String, String>;

#[derive(Serialize)]
pub(crate) struct Product {
    id: String,
    bytes: usize,
}

struct Fingerprint {
    hash: blake3::Hasher,
    bytes: usize,
}
impl Write for Fingerprint {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        self.hash.update(bytes);
        self.bytes += bytes.len();
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

pub(crate) struct Products<'a> {
    pub result: &'a Value,
    pub table: BTreeMap<&'static str, Product>,
    known: &'a CachedProducts,
}
impl<'a> Products<'a> {
    pub fn new(result: &'a Value, known: &'a CachedProducts) -> Result<Self, String> {
        let mut table = BTreeMap::new();
        for field in ["batch", "map"] {
            if let Some(value) = result.get(field) {
                // Hash the exact JSON without allocating another large tree or
                // encoded copy. A token includes every field, including nulls,
                // labels, phase guides, units and selection metadata.
                let mut sink = Fingerprint {
                    hash: blake3::Hasher::new(),
                    bytes: 0,
                };
                serde_json::to_writer(&mut sink, value).map_err(|e| e.to_string())?;
                table.insert(
                    field,
                    Product {
                        id: sink.hash.finalize().to_hex().to_string(),
                        bytes: sink.bytes,
                    },
                );
            }
        }
        Ok(Self {
            result,
            table,
            known,
        })
    }
}
impl Serialize for Products<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let Some(object) = self.result.as_object() else {
            return self.result.serialize(serializer);
        };
        let mut map = serializer.serialize_map(None)?;
        for (key, value) in object {
            if self
                .table
                .get(key.as_str())
                .is_some_and(|p| self.known.get(key) == Some(&p.id))
            {
                continue;
            }
            map.serialize_entry(key, value)?;
        }
        map.end()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::{Reply, decode_request};
    use serde_json::json;

    #[test]
    fn stdio_negotiation_is_optional_and_isolated_per_request() {
        let null_id = blake3::hash(b"null").to_hex().to_string();
        let requests = [
            json!({"id":1,"action":"state","cachedProducts":{}}),
            json!({"id":2,"action":"state","cachedProducts":{"batch":null_id,"map":null_id}}),
            json!({"id":3,"action":"state"}),
        ];
        let input = requests
            .iter()
            .map(|r| r.to_string() + "\n")
            .collect::<String>();
        let mut output = vec![];
        crate::transport::serve(
            &mut std::io::Cursor::new(input),
            &mut output,
            std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".."),
            false,
        )
        .unwrap();
        let mut offset = 0;
        let mut headers = vec![];
        while offset < output.len() {
            let length =
                u32::from_le_bytes(output[offset..offset + 4].try_into().unwrap()) as usize;
            let header: Value =
                serde_json::from_slice(&output[offset + 4..offset + 4 + length]).unwrap();
            assert!(header["buffers"].as_array().unwrap().is_empty());
            headers.push(header);
            offset += 4 + length;
        }
        assert_eq!(headers.len(), 3);
        assert!(
            headers[0]["result"]
                .get("batch")
                .is_some_and(Value::is_null)
        );
        assert!(headers[1]["result"].get("batch").is_none());
        assert!(headers[1]["result"].get("map").is_none());
        assert_eq!(headers[1]["products"], headers[0]["products"]);
        assert!(
            headers[2]["result"]
                .get("batch")
                .is_some_and(Value::is_null)
        );
        assert!(headers[2].get("products").is_none());
    }

    fn header(reply: &Reply, cached: Option<&CachedProducts>) -> Value {
        let parts = reply.packet_parts_with_products(7, &[], cached).unwrap();
        serde_json::from_slice(&parts.header[4..]).unwrap()
    }

    #[test]
    fn per_client_tokens_omit_only_exact_products_and_preserve_legacy_replies() {
        let reply = Reply::metadata(json!({"ok":true,"state":{"revision":8},
            "batch":{"unit":"d_A","values":vec![1.25;10_000],"selected":3},"map":null}));
        let legacy = header(&reply, None);
        assert_eq!(legacy["result"], reply.result);
        assert!(legacy.get("products").is_none());
        let full = header(&reply, Some(&CachedProducts::new()));
        let known: CachedProducts = ["batch", "map"]
            .into_iter()
            .map(|field| {
                (
                    field.to_string(),
                    full["products"][field]["id"].as_str().unwrap().to_string(),
                )
            })
            .collect();
        let warm = header(&reply, Some(&known));
        assert_eq!(warm["result"], json!({"ok":true,"state":{"revision":8}}));
        assert!(serde_json::to_vec(&warm).unwrap().len() < 500);
        assert_eq!(warm["products"], full["products"]);
        assert_eq!(
            reply.result["batch"]["values"].as_array().unwrap().len(),
            10_000
        );
        // A different client has not seen those products and still gets all data.
        assert_eq!(
            header(&reply, Some(&CachedProducts::new()))["result"],
            reply.result
        );
        for (key, value) in [
            ("unit", json!("q_A^-1")),
            ("selected", json!(4)),
            ("values", json!([null, -0.0, 2.0])),
        ] {
            let mut changed = reply.result.clone();
            changed["batch"][key] = value;
            let changed = header(&Reply::metadata(changed), Some(&known));
            assert!(changed["result"].get("batch").is_some());
            assert_ne!(
                changed["products"]["batch"]["id"],
                full["products"]["batch"]["id"]
            );
        }
        let cleared = header(
            &Reply::metadata(json!({"ok":true,"batch":null})),
            Some(&known),
        );
        assert!(cleared["result"].get("batch").is_some_and(Value::is_null));
    }

    #[test]
    fn transport_cache_capability_does_not_change_public_scientific_requests() {
        let request = json!({"id":2,"action":"settings","payload":{"unit":"d_A"},
            "cachedBuffers":[],"cachedProducts":{"map":"b3:123"}});
        let (decoded, products) = decode_request(&serde_json::to_vec(&request).unwrap()).unwrap();
        assert_eq!(decoded.payload, request["payload"]);
        assert_eq!(products.unwrap()["map"], "b3:123");
        let (_, products) = decode_request(br#"{"id":1,"action":"state"}"#).unwrap();
        assert!(products.is_none());
        for invalid in [
            json!(null),
            json!([]),
            json!({"map":1}),
            json!({"other":"id"}),
            json!({"map":""}),
            json!({"map":"x".repeat(129)}),
            json!({"map":"bad\nvalue"}),
        ] {
            let mut value = request.clone();
            value["cachedProducts"] = invalid;
            assert!(decode_request(&serde_json::to_vec(&value).unwrap()).is_err());
        }
        let mut unknown = request;
        unknown["unknown"] = json!(true);
        assert!(decode_request(&serde_json::to_vec(&unknown).unwrap()).is_err());
    }
}

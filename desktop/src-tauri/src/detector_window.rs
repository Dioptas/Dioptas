//! Presentation-only detector companion. No processor, decoding or integration
//! lives here: immutable pixels are published once by the main webview.
use serde_json::{json, Value};
use std::{
    collections::{HashMap, HashSet},
    sync::{Arc, Mutex},
};
use tauri::{
    ipc::{InvokeBody, Request, Response},
    State,
};

const MAX_HEADER: usize = 8 * 1024 * 1024;
const MAX_PIXELS: usize = 256 * 1024 * 1024;

#[derive(Default)]
pub struct DetectorSnapshot(Mutex<Snapshot>);
#[derive(Default)]
struct Snapshot {
    result: Option<Value>,
    buffers: HashMap<String, Arc<Vec<u8>>>,
}

fn references(value: &Value, output: &mut HashMap<String, usize>) -> Result<(), String> {
    match value {
        Value::Array(values) => {
            for item in values {
                references(item, output)?;
            }
        }
        Value::Object(values) => {
            if let Some(id) = values.get("bufferId").and_then(Value::as_str) {
                if id.len() > 256 {
                    return Err("Invalid detector buffer identity.".into());
                }
                let dimension = |key| {
                    values
                        .get(key)
                        .and_then(Value::as_u64)
                        .filter(|n| *n > 0 && *n <= 100_000)
                        .ok_or("Invalid detector dimensions.")
                };
                let bytes = match values.get("dtype").and_then(Value::as_str) {
                    Some("u8") => 1,
                    Some("f32le") => 4,
                    _ => return Err("Invalid detector data type.".into()),
                };
                let size = dimension("width")?
                    .checked_mul(dimension("height")?)
                    .and_then(|n| n.checked_mul(bytes))
                    .filter(|n| *n <= MAX_PIXELS as u64)
                    .ok_or("Detector buffer exceeds the display bound.")?
                    as usize;
                if output
                    .insert(id.to_owned(), size)
                    .is_some_and(|previous| previous != size)
                {
                    return Err("Conflicting detector buffer sizes.".into());
                }
            } else {
                for item in values.values() {
                    references(item, output)?;
                }
            }
        }
        _ => (),
    }
    Ok(())
}
impl Snapshot {
    fn publish(&mut self, bytes: &[u8]) -> Result<Vec<String>, String> {
        if bytes.len() > MAX_HEADER + MAX_PIXELS + 4 {
            return Err("Detector snapshot exceeds the display bound.".into());
        }
        let length = u32::from_le_bytes(
            bytes
                .get(..4)
                .ok_or("Missing detector header.")?
                .try_into()
                .unwrap(),
        ) as usize;
        if length > MAX_HEADER {
            return Err("Detector header exceeds the display bound.".into());
        }
        let header: Value = serde_json::from_slice(
            bytes
                .get(4..4 + length)
                .ok_or("Truncated detector header.")?,
        )
        .map_err(|e| e.to_string())?;
        let result = header
            .get("result")
            .filter(|v| v.is_object())
            .ok_or("Missing detector presentation.")?;
        let mut required = HashMap::new();
        references(result, &mut required)?;
        if required.len() > 4 || required.values().sum::<usize>() > MAX_PIXELS {
            return Err("Detector pixels exceed the display bound.".into());
        }
        let mut buffers = HashMap::new();
        let mut offset = 4 + length;
        for item in header["buffers"]
            .as_array()
            .ok_or("Missing detector buffers.")?
        {
            let id = item["id"]
                .as_str()
                .ok_or("Invalid detector buffer identity.")?;
            let size = item["length"]
                .as_u64()
                .filter(|n| *n <= MAX_PIXELS as u64)
                .ok_or("Invalid detector buffer size.")? as usize;
            if required.get(id) != Some(&size) || buffers.contains_key(id) {
                return Err("Unexpected detector buffer.".into());
            }
            let data = bytes
                .get(offset..offset + size)
                .ok_or("Truncated detector pixels.")?;
            buffers.insert(id.to_owned(), Arc::new(data.to_vec()));
            offset += size;
        }
        if offset != bytes.len() {
            return Err("Unexpected detector pixel bytes.".into());
        }
        for (id, size) in &required {
            if buffers.contains_key(id) {
                continue;
            }
            let retained = self
                .buffers
                .get(id)
                .filter(|b| b.len() == *size)
                .ok_or("Missing detector pixels; republish the current view.")?;
            buffers.insert(id.clone(), retained.clone());
        }
        // Atomic replacement: invalid updates leave the last view intact. Only
        // the current image/mask is retained; browsing never grows this store.
        self.result = Some(result.clone());
        self.buffers = buffers;
        Ok(self.buffers.keys().cloned().collect())
    }
    fn packet(&self, known: &[String]) -> Vec<u8> {
        let cached: HashSet<&String> = known.iter().collect();
        let incoming: Vec<_> = self
            .buffers
            .iter()
            .filter(|(id, _)| !cached.contains(id))
            .collect();
        let result = self
            .result
            .clone()
            .unwrap_or_else(|| json!({"ok": true, "presentation": null}));
        let header = json!({"result": result, "buffers": incoming.iter().map(|(id, data)| json!({"id": id, "length": data.len()})).collect::<Vec<_>>()}).to_string();
        let mut bytes = (header.len() as u32).to_le_bytes().to_vec();
        bytes.extend_from_slice(header.as_bytes());
        for (_, data) in incoming {
            bytes.extend_from_slice(data);
        }
        bytes
    }
}

#[tauri::command]
pub fn publish_detector_snapshot(
    window: tauri::WebviewWindow,
    state: State<'_, DetectorSnapshot>,
    request: Request<'_>,
) -> Result<Vec<String>, String> {
    if window.label() != "main" {
        return Err("Only the main window may publish detector pixels.".into());
    }
    let InvokeBody::Raw(bytes) = request.body() else {
        return Err("Detector pixels require binary transport.".into());
    };
    state.0.lock().map_err(|e| e.to_string())?.publish(bytes)
}
#[tauri::command]
pub fn detector_snapshot(
    window: tauri::WebviewWindow,
    state: State<'_, DetectorSnapshot>,
    cached_buffers: Option<Vec<String>>,
) -> Result<Response, String> {
    if window.label() != "detector-window" {
        return Err("Only the detector window may read this snapshot.".into());
    }
    Ok(Response::new(
        state
            .0
            .lock()
            .map_err(|e| e.to_string())?
            .packet(&cached_buffers.unwrap_or_default()),
    ))
}
#[tauri::command]
pub fn open_detector_window(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
) -> Result<(), String> {
    crate::map_window::open_window::<2>(app, window)
}
#[tauri::command]
pub fn close_detector_window(
    app: tauri::AppHandle,
    window: tauri::WebviewWindow,
) -> Result<(), String> {
    crate::map_window::close_window::<2>(app, window)
}
pub fn clear(app: &tauri::AppHandle) {
    use tauri::Manager;
    *app.state::<DetectorSnapshot>().0.lock().unwrap() = Snapshot::default();
}

#[cfg(test)]
mod tests {
    use super::*;
    fn frame(id: &str, pixels: Option<Vec<u8>>) -> Vec<u8> {
        let raster = json!({"bufferId": id, "width": 2, "height": 1, "dtype": "f32le"});
        let header = json!({"result": {"ok": true, "presentation": {"identity": id, "raster": {"raster": raster.clone()}, "intensity": {"raster": raster}}}, "buffers": pixels.as_ref().map(|p| vec![json!({"id": id, "length": p.len()})]).unwrap_or_default()}).to_string();
        let mut bytes = (header.len() as u32).to_le_bytes().to_vec();
        bytes.extend_from_slice(header.as_bytes());
        if let Some(p) = pixels {
            bytes.extend(p);
        }
        bytes
    }
    #[test]
    fn snapshots_share_immutable_buffers_and_only_retain_current_source() {
        let mut store = Snapshot::default();
        store.publish(&frame("source-a", Some(vec![1; 8]))).unwrap();
        let first = store.buffers["source-a"].clone();
        store.publish(&frame("source-a", None)).unwrap();
        assert!(Arc::ptr_eq(&first, &store.buffers["source-a"]));
        let packet = store.packet(&["source-a".into()]);
        let n = u32::from_le_bytes(packet[..4].try_into().unwrap()) as usize;
        assert_eq!(packet.len(), n + 4);
        store.publish(&frame("source-b", Some(vec![2; 8]))).unwrap();
        assert_eq!(store.buffers.len(), 1);
        assert!(!store.buffers.contains_key("source-a"));
        assert_eq!(*first, vec![1; 8]); // in-flight readers can retain the prior source
    }
    #[test]
    fn invalid_or_missing_pixels_cannot_replace_a_valid_snapshot() {
        let mut store = Snapshot::default();
        store.publish(&frame("good", Some(vec![1; 8]))).unwrap();
        for packet in [
            frame("missing", None),
            frame("bad-size", Some(vec![1; 4])),
            vec![255; 4],
            frame("truncated", Some(vec![1; 7])),
        ] {
            assert!(store.publish(&packet).is_err());
            assert!(store.buffers.contains_key("good"));
        }
        let mut oversized =
            json!({"bufferId": "huge", "width": 100_000, "height": 100_000, "dtype": "f32le"});
        assert!(references(&oversized, &mut HashMap::new()).is_err());
        oversized["width"] = json!(0);
        assert!(references(&oversized, &mut HashMap::new()).is_err());
    }
}

//! A native Save choice can ask the display to render before file publication.
//! Numerical saves/cancellation do not allocate or transfer figure buffers.
use serde_json::{json, Value};
pub(super) fn capture_request(action: &str, payload: &Value) -> Option<Value> {
    if action != "integration_save_pattern" || payload["figure_export"] != true {
        return None;
    }
    let path = payload["path"].as_str()?;
    let extension = std::path::Path::new(path)
        .extension()?
        .to_str()?
        .to_ascii_lowercase();
    let key = match extension.as_str() {
        "png" => "png_data",
        "svg" => "svg_data",
        _ => return None,
    };
    if payload[key].as_str().is_some() {
        return None;
    }
    Some(json!({"ok":true, "figureExportPath":path}))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn only_an_explicit_display_capability_and_figure_path_request_rendering() {
        for extension in ["png", "SVG"] {
            let path = format!("/tmp/with spaces.{extension}");
            let args = json!({"path":path,"figure_export":true});
            assert_eq!(
                capture_request("integration_save_pattern", &args).unwrap()["figureExportPath"],
                path
            );
            assert!(capture_request("integration_save_background", &args).is_none());
        }
        for args in [
            json!({}),
            json!({"figure_export":true}),
            json!({"path":"/tmp/a.svg"}),
            json!({"path":"/tmp/a.svg","figure_export":true,"svg_data":"<svg/>"}),
            json!({"path":"/tmp/a.png","figure_export":true,"png_data":"data"}),
            json!({"path":"/tmp/a.xy","figure_export":true}),
        ] {
            assert!(capture_request("integration_save_pattern", &args).is_none());
        }
    }
}

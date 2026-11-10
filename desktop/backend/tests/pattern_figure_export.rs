//! Figure publication uses display-owned bytes; numerical pattern export retains
//! its existing scientific path and cannot silently become an image export.
use dioptas_backend::{Session, protocol::Request};
use serde_json::{Value, json};
use std::{
    fs,
    path::{Path, PathBuf},
};
fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_owned()
}
fn invoke(session: &mut Session, payload: Value) -> Value {
    session
        .invoke(&Request {
            id: 1,
            action: "integration_save_pattern".into(),
            payload,
            cached_buffers: vec![],
        })
        .result
}
fn png_bytes() -> Vec<u8> {
    let mut output = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut output, 2, 1);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        encoder
            .write_header()
            .unwrap()
            .write_image_data(&[255, 149, 0, 255, 16, 21, 24, 255])
            .unwrap();
    }
    output
}
#[test]
fn display_figures_publish_atomically_and_reject_bad_payloads_without_replacing_files() {
    use base64::Engine;
    let temp = tempfile::tempdir().unwrap();
    let mut session = Session::new(root());
    let bytes = png_bytes();
    let png_data = base64::engine::general_purpose::STANDARD.encode(&bytes);
    let svg = r##"<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400" viewBox="0 0 800 400"><path d="M0 0L800 400" stroke="#ff9500"/></svg>"##;
    let svg_path = temp.path().join("with spaces.SVG");
    let png_path = temp.path().join("with spaces.PNG");
    for path in [&png_path, &svg_path] {
        let result = invoke(
            &mut session,
            json!({"path":path,"png_data":png_data,"svg_data":svg,"subtract_background":true}),
        );
        assert_eq!(result["ok"], true, "{result}");
        assert_eq!(result["savedPath"], json!(path));
    }
    assert_eq!(fs::read(&png_path).unwrap(), bytes);
    assert_eq!(fs::read_to_string(&svg_path).unwrap(), svg);
    for (path, payload) in [
        (&png_path, json!({"png_data":"invalid"})),
        (&svg_path, json!({"svg_data":"<svg>"})),
        (&svg_path, json!({"svg_data":"<html/>"})),
        (&svg_path, json!({})),
    ] {
        let before = fs::read(path).unwrap();
        let mut args = payload;
        args["path"] = json!(path);
        let result = invoke(&mut session, args);
        assert_eq!(result["ok"], false, "{result}");
        assert_eq!(fs::read(path).unwrap(), before);
    }
    let result = invoke(
        &mut session,
        json!({"path":temp.path().join("absent/figure.svg"),"svg_data":svg}),
    );
    assert_eq!(result["ok"], false, "{result}");
    assert!(!temp.path().join("absent").exists());
    // Extra figure payload does not bypass the numerical path's prerequisites.
    let result = invoke(
        &mut session,
        json!({"path":temp.path().join("pattern.xy"),"png_data":png_data,"svg_data":svg}),
    );
    assert_eq!(result["ok"], false, "{result}");
    assert!(!temp.path().join("pattern.xy").exists());
}

#[test]
fn figure_resolution_metadata_preserves_pixels_and_invalid_dpi_cannot_replace_files() {
    use base64::Engine;
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("paper.png");
    let bytes = png_bytes();
    let data = base64::engine::general_purpose::STANDARD.encode(&bytes);
    let mut session = Session::new(root());
    for dpi in [150, 300, 600] {
        let reply = invoke(
            &mut session,
            json!({"path":path,"png_data":data,"png_dpi":dpi}),
        );
        assert_eq!(reply["ok"], true, "{reply}");
        let saved = fs::read(&path).unwrap();
        let mut reader = png::Decoder::new(std::io::Cursor::new(saved.clone()))
            .read_info()
            .unwrap();
        let dimensions = reader.info().pixel_dims.unwrap();
        assert_eq!(dimensions.xppu, (dpi as f64 / 0.0254).round() as u32);
        assert_eq!(dimensions.yppu, dimensions.xppu);
        assert_eq!(dimensions.unit, png::Unit::Meter);
        let mut pixels = vec![0; reader.output_buffer_size().unwrap()];
        reader.next_frame(&mut pixels).unwrap();
        assert_eq!(pixels, vec![255, 149, 0, 255, 16, 21, 24, 255]);
        let reply = invoke(
            &mut session,
            json!({"path":path,"png_data":data,"png_dpi":-300}),
        );
        assert_eq!(reply["ok"], false);
        assert_eq!(fs::read(&path).unwrap(), saved);
    }
}

#[test]
fn figure_format_rejects_mismatched_suffix_before_writing_and_defaults_missing_suffix() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("numeric.xy");
    std::fs::write(&path, "keep numerical data").unwrap();
    let mut session = Session::new(root());
    let svg = r#"<svg xmlns="http://www.w3.org/2000/svg"/>"#;
    let failed = invoke(
        &mut session,
        json!({"path":path,"format":"svg","svg_data":svg}),
    );
    assert_eq!(failed["ok"], false);
    assert_eq!(
        std::fs::read_to_string(&path).unwrap(),
        "keep numerical data"
    );
    let output = temp.path().join("paper");
    let saved = invoke(
        &mut session,
        json!({"path":output,"format":"svg","svg_data":svg}),
    );
    assert_eq!(saved["ok"], true, "{saved}");
    assert_eq!(
        std::fs::read_to_string(output.with_extension("svg")).unwrap(),
        svg
    );
}

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

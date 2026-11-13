//! Explicit qualification tool: original stored scalar words, no integration.
use dioptas_backend::image::Image;
use serde_json::json;
use sha2::{Digest, Sha256};
fn main() {
    let path = std::path::PathBuf::from(std::env::args().nth(1).expect("image path"));
    let mut image = Image::open(&path, &json!({})).unwrap();
    let frames = image.frames;
    let mut samples = vec![];
    for frame in [0, frames / 2, frames - 1] {
        image.read(frame).unwrap();
        let mut digest = Sha256::new();
        match image.original_pixels() {
            dioptrin_io::PixelBuffer::U16(v) => {
                for x in v {
                    digest.update(x.to_le_bytes());
                }
            }
            dioptrin_io::PixelBuffer::U32(v) => {
                for x in v {
                    digest.update(x.to_le_bytes());
                }
            }
            other => panic!("Unqualified probe type: {:?}", other.pixel_type()),
        }
        samples.push(json!({"frame":frame,"sha256":format!("{:x}",digest.finalize())}));
    }
    println!(
        "{}",
        json!({"path":path,"frames":frames,"dtype":image.source_dtype,"shape":image.shape,"samples":samples})
    );
}

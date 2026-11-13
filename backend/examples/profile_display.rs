//! Read-only stage timing for a supplied real detector frame.
use std::{path::Path, time::Instant};
fn main() {
    let file = std::env::args().nth(1).expect("detector path");
    let start = Instant::now();
    let image =
        dioptas_backend::image::Image::open(Path::new(&file), &serde_json::json!({})).unwrap();
    let read = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let _ = dioptas_backend::display::levels(&image.values, image.shape, "percentile", 2.5, true);
    let levels = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let bytes: Vec<_> = image
        .values
        .iter()
        .flat_map(|v| (*v as f32).to_le_bytes())
        .collect();
    let conversion = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let _ = dioptas_backend::protocol::Buffer::new(bytes);
    let hash = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let _ = dioptas_backend::display::Raster::image(&image.values, image.shape);
    let raster = start.elapsed().as_secs_f64();
    println!(
        "{}",
        serde_json::json!({"shape":image.shape,"read_seconds":read,"levels_seconds":levels,"conversion_seconds":conversion,"hash_seconds":hash,"raster_seconds":raster})
    );
}

//! Scaled real detector TIFFs for the headless Batch companion workflow.
use std::{fs::File, io::BufWriter, path::Path};

fn main() {
    let mut args = std::env::args().skip(1);
    let source = args.next().expect("source detector TIFF");
    let directory = args.next().expect("output directory");
    let image = dioptas_backend::image::Image::open(Path::new(&source), &serde_json::json!({}))
        .expect("read detector fixture");
    let [height, width] = image.shape;
    for frame in 1..=6 {
        // Image exposes bottom-left display rows; TIFF stores top-left rows.
        let values: Vec<f32> = image
            .values
            .chunks_exact(width)
            .rev()
            .flatten()
            .map(|value| *value as f32 * frame as f32)
            .collect();
        let file = File::create(Path::new(&directory).join(format!("series_{frame}.tif")))
            .expect("create fixture TIFF");
        tiff::encoder::TiffEncoder::new(BufWriter::new(file))
            .expect("create TIFF encoder")
            .new_image::<tiff::encoder::colortype::Gray32Float>(width as u32, height as u32)
            .expect("create TIFF image")
            .write_data(&values)
            .expect("write scaled detector pixels");
    }
}

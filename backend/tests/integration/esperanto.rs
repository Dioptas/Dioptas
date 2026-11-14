use dioptas_backend::image::Image;
use dioptrin_io::PixelBuffer;
use serde_json::json;

#[test]
fn esperanto_encodings_load_through_dioptas_with_exact_counts_and_orientation() {
    let fixtures =
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/esperanto");
    let pattern = [
        i32::MIN,
        i32::MAX,
        0,
        -32768,
        32767,
        -128,
        127,
        126,
        -1,
        0,
        1,
        -2,
        2,
        -3,
        3,
        65535,
        32768,
    ];
    let expected: Vec<i32> = (0..36).map(|i| pattern[i % pattern.len()]).collect();
    let oriented: Vec<f64> = expected
        .as_chunks::<18>()
        .0
        .iter()
        .rev()
        .flatten()
        .map(|&v| f64::from(v))
        .collect();
    let temp = tempfile::tempdir().unwrap();
    for (encoding, wrapper) in [("long32", ""), ("agi", ""), ("agi", ".gz"), ("agi", ".bz2")] {
        for extension in ["esperanto", "esper"] {
            let path = temp.path().join(format!("{encoding}.{extension}{wrapper}"));
            std::fs::copy(
                fixtures.join(format!("{encoding}-extrema-cols18.esperanto{wrapper}")),
                &path,
            )
            .unwrap();
            let image = Image::open(&path, &json!({})).unwrap();
            assert_eq!(image.frames, 1);
            assert_eq!(image.shape, [2, 18]);
            assert_eq!(image.source_dtype, "I32");
            assert_eq!(image.original_pixels(), &PixelBuffer::I32(expected.clone()));
            assert_eq!(image.values.as_ref(), &oriented);
        }
    }
}

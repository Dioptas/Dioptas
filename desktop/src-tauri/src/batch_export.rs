//! Save-format routing stays in the native dialog host, including detached Batch.
use serde_json::Value;
type Choice = (&'static str, &'static [&'static str], &'static str, bool);
pub(super) fn file_choice(payload: &Value) -> Choice {
    match payload["format"].as_str() {
        Some("h5" | "hdf5" | "nxs") => (
            "Processed batch HDF5 / NXS",
            &["h5", "hdf5", "nxs"],
            "integrated.h5",
            true,
        ),
        Some("csv") => ("Single-file batch CSV", &["csv"], "integrated.csv", true),
        Some("xy") => ("Per-frame XY", &["xy"], "batch.xy", true),
        Some("chi") => ("Per-frame CHI", &["chi"], "batch.chi", true),
        Some("dat") => ("Per-frame DAT", &["dat"], "batch.dat", true),
        Some("fxye") => ("Per-frame GSAS FXYE", &["fxye"], "batch.fxye", true),
        Some("png") => ("Batch view image", &["png"], "batch.png", true),
        _ => (
            "Integrated batch",
            &[
                "h5", "hdf5", "nxs", "csv", "xy", "chi", "dat", "fxye", "png",
            ],
            "integrated.h5",
            true,
        ),
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    #[test]
    fn native_batch_filters_and_suggested_names() {
        for format in ["csv", "xy", "chi", "dat", "fxye", "png"] {
            let (label, extensions, name, save) = file_choice(&json!({"format":format}));
            assert!(!label.is_empty());
            assert_eq!(extensions, &[format]);
            assert!(name.ends_with(&format!(".{format}")));
            assert!(save);
        }
        assert_eq!(
            file_choice(&json!({"format":"nxs"})).1,
            &["h5", "hdf5", "nxs"]
        );
    }
}

//! Filename admission shared by native image dialogs and folder scanning.
//! Extensions make files visible; the reader still validates their contents.

/// Image formats enabled by the processor, plus supported outer compression.
/// Native dialogs filter on the final suffix, so gzip/bzip2 need `gz`/`bz2`
/// rather than compound entries such as `edf.gz`. Folder scanning additionally
/// requires a recognized image suffix before the compression suffix.
pub const DETECTOR_IMAGE_EXTENSIONS: &[&str] = &[
    "tif",
    "tiff",
    "edf",
    "cbf",
    "h5",
    "hdf5",
    "nxs",
    "npy",
    "img",
    "mccd",
    "mar345",
    "mar1200",
    "mar1600",
    "mar1800",
    "mar2000",
    "mar2300",
    "mar2400",
    "mar3000",
    "mar3450",
    "kcd",
    "mpa",
    "sfrm",
    "osc",
    "gfrm",
    "cor",
    "spe",
    "dat",
    "esperanto",
    "esper",
    "mrc",
    "map",
    "fei",
    "dm3",
    "f2d",
    "pnm",
    "pgm",
    "pbm",
    "xsd",
    "xml",
    "gz",
    "bz2",
];

/// Admit ordinary visible image filenames, optionally wrapped once in gzip or
/// bzip2. This is a filename filter, not a promise that decoding will succeed.
pub fn detector_image_filename(name: &str) -> bool {
    if name.starts_with('.') {
        return false;
    }
    let name = name.to_ascii_lowercase();
    let image = name
        .strip_suffix(".gz")
        .or_else(|| name.strip_suffix(".bz2"))
        .unwrap_or(&name);
    image.rsplit_once('.').is_some_and(|(stem, extension)| {
        !stem.is_empty()
            && !matches!(extension, "gz" | "bz2")
            && DETECTOR_IMAGE_EXTENSIONS.contains(&extension)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn visible_image_aliases_and_outer_compression_are_case_insensitive() {
        for extension in [
            "npy",
            "img",
            "mccd",
            "mar345",
            "mar1200",
            "mar1600",
            "mar1800",
            "mar2000",
            "mar2300",
            "mar2400",
            "mar3000",
            "mar3450",
            "kcd",
            "mpa",
            "sfrm",
            "osc",
            "gfrm",
            "cor",
            "spe",
            "dat",
            "esperanto",
            "esper",
            "mrc",
            "map",
            "fei",
            "dm3",
            "f2d",
            "pnm",
            "pgm",
            "pbm",
            "xsd",
            "xml",
            "tif",
            "tiff",
            "edf",
            "cbf",
            "h5",
            "hdf5",
            "nxs",
        ] {
            assert!(DETECTOR_IMAGE_EXTENSIONS.contains(&extension));
            for wrapper in ["", ".gz", ".bz2"] {
                let name = format!("frame_001.{extension}{wrapper}");
                assert!(detector_image_filename(&name), "{name}");
                assert!(
                    detector_image_filename(&name.to_ascii_uppercase()),
                    "{name}"
                );
                assert!(!detector_image_filename(&format!(".{name}")), "{name}");
            }
        }
    }

    #[test]
    fn archives_disabled_codecs_and_unrecognized_or_nested_wrappers_are_not_scanned() {
        for name in [
            "frame.npz",
            "frame.jpg",
            "frame.jpeg",
            "frame.jp2",
            "frame.j2k",
            "frame.bin",
            "notes.txt.gz",
            "notes.txt.bz2",
            "frame.gz",
            "frame.bz2",
            "frame.edf.gz.bz2",
            "frame.edf.gz.gz",
            "frame.esper.txt",
            "frame",
            "edf",
            ".edf",
            ".edf.gz",
        ] {
            assert!(!detector_image_filename(name), "{name}");
        }
    }
}

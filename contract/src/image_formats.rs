//! Filename admission shared by native image dialogs and folder scanning.
//! Extensions make files visible; the reader still validates their contents.

/// Image extensions of the formats enabled by the processor. Every entry is
/// selectable in detector-image dialogs; entries in
/// [`DIALOG_ONLY_IMAGE_EXTENSIONS`] are excluded from folder scanning.
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
];

/// Generic suffixes that beamline sidecars (XML metadata) or unrelated data
/// (CCP4 density maps) also use. They stay selectable in dialogs, but folder
/// scans and the acquisition watcher skip them so such files are not taken
/// for frames.
pub const DIALOG_ONLY_IMAGE_EXTENSIONS: &[&str] = &["xml", "map"];

/// Outer compression wrappers, applied once around a detector image. Native
/// dialogs filter on the final suffix only, so these get their own filter.
pub const COMPRESSED_IMAGE_EXTENSIONS: &[&str] = &["gz", "bz2"];

/// Split a filename into its stem and image suffix, treating one outer
/// `.gz`/`.bz2` as part of the suffix: `scan_0001.edf.gz` gives
/// `("scan_0001", "edf.gz")`, `scan_0001.tif` gives `("scan_0001", "tif")`.
/// Case is preserved. Returns `None` without a stem or a suffix.
pub fn split_image_name(name: &str) -> Option<(&str, &str)> {
    let lower = name.to_ascii_lowercase();
    let inner = COMPRESSED_IMAGE_EXTENSIONS
        .iter()
        .find(|wrapper| lower.ends_with(&format!(".{wrapper}")))
        .map_or(name.len(), |wrapper| name.len() - wrapper.len() - 1);
    let dot = name[..inner]
        .rfind('.')
        .or((inner < name.len()).then_some(inner))?;
    let (stem, suffix) = (&name[..dot], &name[dot + 1..]);
    (!stem.is_empty() && !suffix.is_empty()).then_some((stem, suffix))
}

/// Lowercase image extension of a visible name, ignoring one outer
/// compression wrapper; `None` for hidden or unlisted names.
fn image_extension(name: &str) -> Option<String> {
    if name.starts_with('.') {
        return None;
    }
    let (_, suffix) = split_image_name(name)?;
    let extension = suffix.split('.').next()?.to_ascii_lowercase();
    DETECTOR_IMAGE_EXTENSIONS
        .contains(&extension.as_str())
        .then_some(extension)
}

/// Admit visible names with any dialog-selectable image extension, optionally
/// wrapped once in gzip or bzip2. This is a filename filter, not a promise
/// that decoding will succeed.
pub fn detector_image_filename(name: &str) -> bool {
    image_extension(name).is_some()
}

/// Admit names that folder scanning and acquisition watching treat as frames:
/// [`detector_image_filename`] without the generic dialog-only suffixes.
pub fn scanned_image_filename(name: &str) -> bool {
    image_extension(name)
        .is_some_and(|extension| !DIALOG_ONLY_IMAGE_EXTENSIONS.contains(&extension.as_str()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn listed_extensions_and_outer_compression_are_case_insensitive() {
        for extension in DETECTOR_IMAGE_EXTENSIONS {
            let scanned = !DIALOG_ONLY_IMAGE_EXTENSIONS.contains(extension);
            for wrapper in ["", ".gz", ".bz2"] {
                let name = format!("frame_001.{extension}{wrapper}");
                for name in [name.clone(), name.to_ascii_uppercase()] {
                    assert!(detector_image_filename(&name), "{name}");
                    assert_eq!(scanned_image_filename(&name), scanned, "{name}");
                    assert!(!detector_image_filename(&format!(".{name}")), "{name}");
                }
            }
        }
    }

    #[test]
    fn dialog_only_and_compression_lists_are_disjoint_subsets() {
        for extension in DIALOG_ONLY_IMAGE_EXTENSIONS {
            assert!(DETECTOR_IMAGE_EXTENSIONS.contains(extension), "{extension}");
        }
        for wrapper in COMPRESSED_IMAGE_EXTENSIONS {
            assert!(!DETECTOR_IMAGE_EXTENSIONS.contains(wrapper), "{wrapper}");
        }
    }

    #[test]
    fn generic_suffixes_are_selectable_but_not_scanned() {
        for name in ["beamline.xml", "density.map", "scan_0001.xml.gz"] {
            assert!(detector_image_filename(name), "{name}");
            assert!(!scanned_image_filename(name), "{name}");
        }
        assert!(scanned_image_filename("frame_001.xsd"));
        assert!(scanned_image_filename("frame_001.fei"));
    }

    #[test]
    fn archives_disabled_codecs_and_unrecognized_or_nested_wrappers_are_not_admitted() {
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
            assert!(!scanned_image_filename(name), "{name}");
        }
    }

    #[test]
    fn split_keeps_one_compression_wrapper_in_the_suffix() {
        for (name, expected) in [
            ("scan_0001.edf.gz", Some(("scan_0001", "edf.gz"))),
            ("scan_0001.ESPER.BZ2", Some(("scan_0001", "ESPER.BZ2"))),
            ("scan_0001.tif", Some(("scan_0001", "tif"))),
            ("a.b.cbf", Some(("a.b", "cbf"))),
            ("frame.gz", Some(("frame", "gz"))),
            ("frame.edf.gz.gz", Some(("frame.edf", "gz.gz"))),
            ("frame", None),
            (".edf", None),
            ("frame.", None),
            (".gz", None),
        ] {
            assert_eq!(split_image_name(name), expected, "{name}");
        }
    }
}

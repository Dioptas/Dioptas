//! NeXus transport for Dioptrin's physical detector model.
use super::*;
use dioptrin::detector::{Detector, PixelMap};
use std::sync::Arc;
fn error(e: impl std::fmt::Display) -> String {
    format!("Detector definition: {e}")
}
fn find(group: &hdf5::Group, depth: usize, out: &mut Vec<hdf5::Group>) -> Result<(), String> {
    if depth > 8 {
        return Err("Detector definition exceeds eight group levels.".into());
    }
    if group.link_exists("pixel_size")
        && (group.link_exists("max_shape") || group.link_exists("pixel_corners"))
    {
        out.push(group.clone());
        return Ok(());
    }
    let names = group.member_names().map_err(error)?;
    if names.len() > 1024 {
        return Err("Too many detector groups.".into());
    }
    for child in group.groups().map_err(error)? {
        find(&child, depth + 1, out)?;
    }
    Ok(())
}
impl Geometry {
    /// Save portable PONI geometry plus owned spline/NeXus companion resources.
    pub fn save_to(&self, path: &Path) -> Result<(), String> {
        let Some(d) = &self.detector else {
            return crate::session::atomic_write(path, self.save_text().as_bytes());
        };
        let dir = path.parent().unwrap_or(Path::new("."));
        let stem = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("calibration");
        let mut resources = Vec::new();
        let mut config = json!({"pixel1":self.pixel1,"pixel2":self.pixel2,"max_shape":d.max_shape,"orientation":match d.orientation {0|3=>2,2=>3,1=>4,4=>1,_=>return Err("Unsupported detector orientation.".into())}});
        let named = dioptrin::detector::named(&d.name)
            .ok()
            .is_some_and(|original| {
                original.map == d.map
                    && original.pixel1 == d.pixel1
                    && original.pixel2 == d.pixel2
                    && original.max_shape == d.max_shape
                    && original.mask == d.mask
            });
        let name = if d.name == "Detector" && matches!(d.map, PixelMap::Uniform) {
            "Detector"
        } else if named {
            d.name.as_str()
        } else {
            "NexusDetector"
        };
        if name == "NexusDetector" {
            let temp = tempfile::Builder::new()
                .prefix(&format!("{stem}-detector-"))
                .suffix(".nxs")
                .tempfile_in(dir)
                .map_err(error)?;
            write_nexus(d, temp.path())?;
            config = json!({"filename":temp.path().canonicalize().map_err(error)?.to_string_lossy(),"orientation":config["orientation"]});
            resources.push(temp);
        }
        if let Some(s) = &d.spline {
            use std::io::Write;
            let mut temp = tempfile::Builder::new()
                .prefix(&format!("{stem}-distortion-"))
                .suffix(".spline")
                .tempfile_in(dir)
                .map_err(error)?;
            temp.write_all(s.content.as_bytes()).map_err(error)?;
            temp.as_file().sync_all().map_err(error)?;
            config["splineFile"] =
                json!(temp.path().canonicalize().map_err(error)?.to_string_lossy());
            resources.push(temp);
        }
        let text = format!(
            "# Dioptas native geometry; file rows use pyFAI convention\nponi_version: 2.1\nDetector: {name}\nDetector_config: {config}\nDistance: {}\nPoni1: {}\nPoni2: {}\nRot1: {}\nRot2: {}\nRot3: {}\nWavelength: {}\n",
            self.dist, self.poni1, self.poni2, self.rot1, self.rot2, self.rot3, self.wavelength
        );
        // Resources exist before publishing their references. Failed saves remove
        // only new temporary resources; existing project/calibration files survive.
        crate::session::atomic_write(path, text.as_bytes())?;
        for resource in resources {
            resource.keep().map_err(error)?;
        }
        Ok(())
    }
    pub fn load_detector_file(&mut self, path: &Path) -> Result<(), String> {
        self.frame_pixels = None;
        let file = hdf5::File::open(path).map_err(error)?;
        let mut groups = vec![];
        find(&file, 0, &mut groups)?;
        if groups.len() != 1 {
            return Err("Choose a NeXus file containing exactly one detector definition.".into());
        }
        let g = &groups[0];
        // Reject corrections that would otherwise be silently dropped.
        for key in ["flatfield", "darkcurrent"] {
            if g.link_exists(key) {
                return Err(format!(
                    "This NeXus definition embeds {key}; load it through the image correction controls before using a detector-only definition."
                ));
            }
        }
        if g.link_exists("dioptas_detector_model") {
            let data = g.dataset("dioptas_detector_model").map_err(error)?;
            if data.size() != 1 {
                return Err("Invalid embedded detector model.".into());
            }
            let text = data
                .read_scalar::<hdf5::types::VarLenUnicode>()
                .map_err(error)?;
            if text.len() > 16 * 1024 * 1024 {
                return Err("Embedded detector model exceeds 16 MiB.".into());
            }
            let d: Detector = serde_json::from_str(text.as_str()).map_err(error)?;
            d.validate()?;
            self.pixel1 = d.pixel1;
            self.pixel2 = d.pixel2;
            self.detector = Some(Arc::new(d));
            self.detector_file = Some(path.to_string_lossy().into());
            self.distortion_file = None;
            return Ok(());
        }

        let pixels = g
            .dataset("pixel_size")
            .map_err(error)?
            .read_raw::<f64>()
            .map_err(error)?;
        if pixels.len() != 2 {
            return Err("Detector pixel_size needs two SI values.".into());
        }
        let mut d = Detector::custom(pixels[0], pixels[1]);
        d.name = "NexusDetector".into();
        d.aliases = vec![g.name()];
        for name in ["max_shape", "shape"] {
            if g.link_exists(name) {
                let shape = g
                    .dataset(name)
                    .map_err(error)?
                    .read_raw::<usize>()
                    .map_err(error)?;
                if shape.len() != 2 {
                    return Err("Detector shape needs two dimensions.".into());
                }
                d.max_shape = Some([shape[0], shape[1]]);
            }
        }
        if g.link_exists("orientation") {
            d.orientation = g
                .dataset("orientation")
                .map_err(error)?
                .read_scalar::<u8>()
                .map_err(error)?;
        }
        if g.link_exists("pixel_corners") {
            let dataset = g
                .dataset(if g.link_exists("dioptas_pixel_corners_f64") {
                    "dioptas_pixel_corners_f64"
                } else {
                    "pixel_corners"
                })
                .map_err(error)?;
            let shape = dataset.shape();
            if shape.len() != 4 || shape[2..] != [4, 3] || dataset.size() > 64 * 1024 * 1024 {
                return Err("NeXus detector requires quadrilateral [rows,columns,4,3] corners within the 64-million-coordinate bound.".into());
            }
            let raw = dataset.read_raw::<f64>().map_err(error)?;
            let values = raw
                .as_chunks::<12>()
                .0
                .iter()
                .map(|p| std::array::from_fn(|i| [p[i * 3], p[i * 3 + 1], p[i * 3 + 2]]))
                .collect();
            d.max_shape = Some([shape[0], shape[1]]);
            d.map = PixelMap::Corners {
                shape: [shape[0], shape[1]],
                values: Arc::new(values),
            };
        }
        if g.link_exists("mask") {
            let dataset = g.dataset("mask").map_err(error)?;
            if d.max_shape.as_ref().is_none_or(|s| dataset.shape() != s) {
                return Err("NeXus detector mask shape differs from its coordinates.".into());
            }
            let values = dataset.read_raw::<f64>().map_err(error)?;
            let mut start = None;
            for (i, v) in values.iter().chain(std::iter::once(&0.)).enumerate() {
                if *v != 0. {
                    start.get_or_insert(i);
                } else if let Some(a) = start.take() {
                    d.mask.push([a, i]);
                }
            }
        }
        d.validate()?;
        self.pixel1 = d.pixel1;
        self.pixel2 = d.pixel2;
        self.detector = Some(Arc::new(d));
        self.detector_file = Some(path.to_string_lossy().into());
        self.distortion_file = None;
        Ok(())
    }
}
fn write_nexus(d: &Detector, path: &Path) -> Result<(), String> {
    use std::str::FromStr;
    let shape = d
        .max_shape
        .ok_or("NeXus export requires a detector shape.")?;
    if shape[0]
        .checked_mul(shape[1])
        .and_then(|n| n.checked_mul(12))
        .is_none_or(|n| n > 64 * 1024 * 1024)
    {
        return Err("Detector corner export exceeds 64 million coordinates.".into());
    }
    let file = hdf5::File::create(path).map_err(error)?;
    let entry = file.create_group("entry").map_err(error)?;
    let instrument = entry.create_group("pyFAI").map_err(error)?;
    let group = instrument.create_group("detector").map_err(error)?;
    for (location, class) in [
        (&entry, "NXentry"),
        (&instrument, "NXsubentry"),
        (&group, "NXdetector"),
    ] {
        let value = hdf5::types::VarLenUnicode::from_str(class).map_err(error)?;
        location
            .new_attr::<hdf5::types::VarLenUnicode>()
            .shape(())
            .create("NX_class")
            .map_err(error)?
            .write_scalar(&value)
            .map_err(error)?;
    }
    let stamp = time::OffsetDateTime::now_utc()
        .format(&time::format_description::well_known::Rfc3339)
        .map_err(error)?;
    let stamp = hdf5::types::VarLenUnicode::from_str(&stamp).map_err(error)?;
    entry
        .new_dataset::<hdf5::types::VarLenUnicode>()
        .shape(())
        .create("start_time")
        .map_err(error)?
        .write_scalar(&stamp)
        .map_err(error)?;
    let scalar = |name: &str, value: i32| -> Result<(), String> {
        group
            .new_dataset::<i32>()
            .shape(())
            .create(name)
            .map_err(error)?
            .write_scalar(&value)
            .map_err(error)
    };
    scalar("CORNERS", 4)?;
    scalar("IS_FLAT", i32::from(d.is_flat()))?;
    scalar("IS_CONTIGUOUS", 0)?;
    scalar("orientation", 3)?;
    group
        .new_dataset_builder()
        .with_data(&[d.pixel1, d.pixel2])
        .create("pixel_size")
        .map_err(error)?;
    for name in ["max_shape", "shape"] {
        group
            .new_dataset_builder()
            .with_data(&shape)
            .create(name)
            .map_err(error)?;
    }
    let mut canonical = d.clone();
    if d.has_spline() {
        let mut model = d.clone();
        model.orientation = 3;
        let text = serde_json::to_string(&model).map_err(error)?;
        let text = hdf5::types::VarLenUnicode::from_str(&text).map_err(error)?;
        group
            .new_dataset::<hdf5::types::VarLenUnicode>()
            .shape(())
            .create("dioptas_detector_model")
            .map_err(error)?
            .write_scalar(&text)
            .map_err(error)?;
    }

    canonical.orientation = 3;
    canonical.spline = None;
    let mut corners = Vec::with_capacity(shape[0] * shape[1] * 12);
    for r in 0..shape[0] {
        for c in 0..shape[1] {
            corners.extend(canonical.corners(shape, r, c).into_iter().flatten());
        }
    }
    let standard: Vec<f32> = corners.iter().map(|v| *v as f32).collect();
    group
        .new_dataset::<f32>()
        .shape([shape[0], shape[1], 4, 3])
        .create("pixel_corners")
        .map_err(error)?
        .write_raw(&standard)
        .map_err(error)?;
    group
        .new_dataset::<f64>()
        .shape([shape[0], shape[1], 4, 3])
        .create("dioptas_pixel_corners_f64")
        .map_err(error)?
        .write_raw(&corners)
        .map_err(error)?;
    let mask = canonical.builtin_mask(shape)?;
    group
        .new_dataset::<u8>()
        .shape(shape)
        .create("mask")
        .map_err(error)?
        .write_raw(&mask)
        .map_err(error)?;
    file.flush().map_err(error)
}

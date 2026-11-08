use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{collections::BTreeMap, path::Path};
#[path = "detector_io.rs"]
mod detector_io;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Geometry {
    /// Declared PONI pitches are resolved against the first image and factory binning.
    #[serde(default)]
    pub(crate) frame_pixels: Option<[Option<f64>; 2]>,
    #[serde(default)]
    pub auto_assign: bool,
    #[serde(default)]
    pub assignment: Option<String>,
    #[serde(default)]
    pub candidates: Vec<String>,
    #[serde(default)]
    pub detector: Option<std::sync::Arc<dioptrin::detector::Detector>>,
    #[serde(default)]
    pub detector_file: Option<String>,
    #[serde(default)]
    pub distortion_file: Option<String>,
    pub dist: f64,
    pub poni1: f64,
    pub poni2: f64,
    pub rot1: f64,
    pub rot2: f64,
    pub rot3: f64,
    pub pixel1: f64,
    pub pixel2: f64,
    pub wavelength: f64,
}
impl Default for Geometry {
    fn default() -> Self {
        Self {
            frame_pixels: None,
            auto_assign: true,
            assignment: None,
            candidates: vec![],
            detector: None,
            detector_file: None,
            distortion_file: None,
            dist: 0.2,
            poni1: 0.0,
            poni2: 0.0,
            rot1: 0.0,
            rot2: 0.0,
            rot3: 0.0,
            pixel1: 79e-6,
            pixel2: 79e-6,
            wavelength: 0.3344e-10,
        }
    }
}
impl Geometry {
    pub fn set_pixels(
        &mut self,
        pixels: [f64; 2],
        shape: Option<[usize; 2]>,
    ) -> Result<(), String> {
        if pixels.iter().any(|v| !v.is_finite() || *v <= 0.) {
            return Err("Pixel sizes must be positive and finite.".into());
        }
        if let Some(d) = &mut self.detector {
            let target = shape.or(d.max_shape).unwrap_or([1, 1]);
            let bin = d.binning(target)?;
            let default = [
                d.config["pixel1"].as_f64().unwrap_or(d.pixel1),
                d.config["pixel2"].as_f64().unwrap_or(d.pixel2),
            ];
            let expected = if shape.is_some() {
                d.effective_pixels(target)
            } else {
                std::array::from_fn(|i| self.frame_pixels.and_then(|p| p[i]).unwrap_or(default[i]))
            };
            let changed = pixels
                .iter()
                .zip(expected)
                .any(|(a, b)| ((a - b) / b).abs() > 1e-12);
            if changed
                && (d.name != "Detector"
                    || !matches!(d.map, dioptrin::detector::PixelMap::Uniform)
                    || d.spline.is_some()
                    || !d.binning_pitches.is_empty())
            {
                return Err("Pixel sizes are defined by this detector definition, map, spline or manufacturer binning table. Reset to Custom before entering different pixel sizes.".into());
            }
            if changed {
                self.frame_pixels = None;
                let d = std::sync::Arc::make_mut(d);
                d.pixel1 = pixels[0] / bin[0] as f64;
                d.pixel2 = pixels[1] / bin[1] as f64;
            }
        }
        [self.pixel1, self.pixel2] = pixels;
        Ok(())
    }
    #[cfg(any(feature = "dioptrin", test))]
    pub fn native_geometry(
        &self,
        shape: [usize; 2],
    ) -> Result<dioptrin::geometry::Geometry, String> {
        let g = dioptrin::geometry::Geometry::new(shape[0], shape[1], self.native_poni());
        if let Some(d) = &self.detector {
            g.with_detector(d.clone())
        } else {
            Ok(g)
        }
    }
    pub fn validate_shape(&self, shape: [usize; 2]) -> Result<(), String> {
        if let Some(d) = &self.detector {
            if let Some(expected) = d.max_shape
                && (shape.contains(&0)
                    || expected[0] % shape[0] != 0
                    || expected[1] % shape[1] != 0)
            {
                return Err(format!(
                    "{} calibration expects a {} × {} detector image or supported binning; the current image is {} × {}. Open the matching detector image first.",
                    d.name, expected[1], expected[0], shape[1], shape[0]
                ));
            }
            d.binning(shape)?;
            if d.name == "Detector"
                && matches!(d.map, dioptrin::detector::PixelMap::Uniform)
                && !d.has_spline()
                && d.max_shape.is_some_and(|max| max != shape)
            {
                return Err("Custom PONI detector dimensions differ from the image; binning/cropping cannot be inferred safely. Use explicit Custom geometry for this image.".into());
            }
        }
        Ok(())
    }
    pub fn sync_shape(&mut self, shape: [usize; 2]) -> Result<(), String> {
        self.validate_shape(shape)?;
        if let Some(d) = &self.detector {
            let expected = d.effective_pixels(shape);
            if let Some(declared) = self.frame_pixels {
                let raw = [d.pixel1, d.pixel2];
                let ctor = [
                    d.config["pixel1"].as_f64().unwrap_or(raw[0]),
                    d.config["pixel2"].as_f64().unwrap_or(raw[1]),
                ];
                let close = |a: f64, b: f64| ((a - b) / b).abs() < 1e-10;
                for i in 0..2 {
                    if let Some(p) = declared[i]
                        && !close(p, expected[i])
                        && !(d.name != "Detector" && (close(p, raw[i]) || close(p, ctor[i])))
                    {
                        return Err("PONI pixel pitches conflict with this detector/image binning; use a physical NeXus definition or explicit Custom geometry.".into());
                    }
                }
            }
            [self.pixel1, self.pixel2] = expected;
        }
        self.frame_pixels = None;
        Ok(())
    }
    pub fn select_detector(&mut self, name: &str) -> Result<(), String> {
        self.auto_assign = false;
        self.frame_pixels = None;
        self.assignment = None;
        self.candidates.clear();
        if name == "Custom" {
            self.detector = None;
            self.detector_file = None;
            self.distortion_file = None;
            return Ok(());
        }
        let d = dioptrin::detector::named(name)?;
        d.validate()?;
        self.pixel1 = d.config["pixel1"].as_f64().unwrap_or(d.pixel1);
        self.pixel2 = d.config["pixel2"].as_f64().unwrap_or(d.pixel2);
        self.detector = Some(std::sync::Arc::new(d));
        self.detector_file = None;
        self.distortion_file = None;
        Ok(())
    }
    pub fn load_spline(&mut self, path: &Path) -> Result<(), String> {
        use std::io::Read;
        let mut content = String::new();
        std::fs::File::open(path)
            .map_err(|e| e.to_string())?
            .take(16 * 1024 * 1024 + 1)
            .read_to_string(&mut content)
            .map_err(|e| e.to_string())?;
        let spline = dioptrin::detector::spline::Spline::parse(&content)?;
        let mut d = self
            .detector
            .as_deref()
            .cloned()
            .unwrap_or_else(|| dioptrin::detector::Detector::custom(self.pixel1, self.pixel2));
        if !matches!(d.map, dioptrin::detector::PixelMap::Uniform) {
            return Err("A spline cannot replace an existing nonuniform pixel-corner map. Reset that detector definition first.".into());
        }
        d.pixel1 = spline.pixels[1] * 1e-6;
        d.pixel2 = spline.pixels[0] * 1e-6;
        if let Some(shape) = d.max_shape
            && (spline.region != [0., 0., shape[1] as f64, shape[0] as f64])
        {
            return Err("Spline valid region does not match the selected detector. Reset to Custom before loading this spline.".into());
        }
        if d.max_shape.is_none() && spline.region[0] == 0. && spline.region[1] == 0. {
            d.max_shape = Some([spline.region[3] as usize, spline.region[2] as usize]);
        }
        self.pixel1 = d.pixel1;
        self.pixel2 = d.pixel2;
        d.spline = Some(std::sync::Arc::new(spline));
        self.detector = Some(std::sync::Arc::new(d));
        self.distortion_file = Some(path.to_string_lossy().into());
        Ok(())
    }
    pub fn reset_spline(&mut self) {
        self.frame_pixels = None;
        if let Some(d) = self.detector.as_mut() {
            let d = std::sync::Arc::make_mut(d);
            d.clear_spline();
            if d.name == "Detector"
                && d.mask.is_empty()
                && !d.circular_mask
                && matches!(d.map, dioptrin::detector::PixelMap::Uniform)
            {
                d.max_shape = None;
                d.pixel1 = self.pixel1;
                d.pixel2 = self.pixel2;
            }
        }
        self.distortion_file = None;
    }
    pub fn fit2d_values(&self, polarization: f64) -> Value {
        let f = dioptrin::fit2d::Fit2d::from_poni(&self.native_poni());
        json!({"directDist":f.direct_dist,"centerX":f.center_x,"centerY":f.center_y,"tilt":f.tilt,"tiltPlanRotation":f.tilt_plane_rotation,"pixelX":f.pixel_x,"pixelY":f.pixel_y,"wavelength":self.wavelength,"polarization_factor":polarization})
    }
    pub fn manual_fit2d(values: &Value) -> Result<(Self, f64), String> {
        let keys = [
            "directDist",
            "centerX",
            "centerY",
            "tilt",
            "tiltPlanRotation",
            "pixelX",
            "pixelY",
            "wavelength",
            "polarization_factor",
        ];
        let o = values
            .as_object()
            .ok_or("Complete every geometry field before applying.")?;
        if o.len() != keys.len() || keys.iter().any(|k| !o.contains_key(*k)) {
            return Err("Complete every geometry field before applying.".into());
        }
        let n = |k: &str| {
            o[k].as_f64()
                .filter(|v| v.is_finite())
                .ok_or_else(|| format!("Invalid Fit2D {k}."))
        };
        let p = dioptrin::fit2d::Fit2d {
            direct_dist: n("directDist")?,
            center_x: n("centerX")?,
            center_y: n("centerY")?,
            tilt: n("tilt")?,
            tilt_plane_rotation: n("tiltPlanRotation")?,
            pixel_x: n("pixelX")?,
            pixel_y: n("pixelY")?,
        }
        .to_poni(n("wavelength")?)?;
        Self::manual(
            &json!({"dist":p.distance,"poni1":p.poni1,"poni2":p.poni2,"rot1":p.rot1,"rot2":p.rot2,"rot3":p.rot3,"pixel1":p.pixel1,"pixel2":p.pixel2,"wavelength":p.wavelength,"polarization_factor":n("polarization_factor")?}),
        )
    }
    /// Same Fit2D beam-center based automatic bin count as Configuration.
    pub fn automatic_bins(&self, shape: [usize; 2]) -> usize {
        let center_x = (self.poni2 - self.dist * self.rot1.tan()) / self.pixel2;
        let center_y = (self.poni1
            + self.dist * self.rot2.sin() / (self.rot1.cos() * self.rot2.cos()))
            / self.pixel1;
        // Preserve the existing model's shape/center convention exactly.
        let [width, height] = shape.map(|v| v as f64);
        let a = if center_x > 0.0 && center_x < width {
            (width - center_x).abs().max(center_x)
        } else {
            width
        };
        let b = if center_y > 0.0 && center_y < height {
            (height - center_y).abs().max(center_y)
        } else {
            height
        };
        ((a.hypot(b) * 2.0) as usize).clamp(1, 100000)
    }
    pub fn native_poni(&self) -> dioptrin::poni::Poni {
        dioptrin::poni::Poni {
            pixel1: self.pixel1,
            pixel2: self.pixel2,
            distance: self.dist,
            poni1: self.poni1,
            poni2: self.poni2,
            rot1: self.rot1,
            rot2: self.rot2,
            rot3: self.rot3,
            wavelength: self.wavelength,
            spline_file: String::new(),
        }
    }
    pub fn validate(&self) -> Result<(), String> {
        if self
            .frame_pixels
            .is_some_and(|p| p.into_iter().flatten().any(|v| !v.is_finite() || v <= 0.))
        {
            return Err("Invalid declared PONI pixel pitches.".into());
        }
        if let Some(d) = &self.detector {
            d.validate()?;
        }
        for (name, value) in [
            ("distance", self.dist),
            ("pixel1", self.pixel1),
            ("pixel2", self.pixel2),
            ("wavelength", self.wavelength),
        ] {
            if !value.is_finite() || value <= 0.0 {
                return Err(format!("{name} must be positive and finite."));
            }
        }
        for value in [self.poni1, self.poni2, self.rot1, self.rot2, self.rot3] {
            if !value.is_finite() {
                return Err("Geometry values must be finite.".into());
            }
        }
        Ok(())
    }
    /// Read explicit PONI geometry and retain supported physical detector data.
    /// Unsupported settings fail before the session publishes a change.
    pub fn load(path: &Path) -> Result<Self, String> {
        use std::io::Read;
        let mut file = String::new();
        std::fs::File::open(path)
            .map_err(|e| e.to_string())?
            .take(1024 * 1024 + 1)
            .read_to_string(&mut file)
            .map_err(|e| e.to_string())?;
        if file.len() > 1024 * 1024 {
            return Err("PONI file exceeds 1 MiB.".into());
        }
        let mut fields = BTreeMap::new();
        for line in file
            .lines()
            .map(str::trim)
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
        {
            let (key, value) = line.split_once(':').ok_or("Invalid PONI field.")?;
            // pyFAI Geometry.save appends calibration records to an existing file.
            // Its reader keeps the last occurrence of each case-insensitive field.
            fields.insert(key.trim().to_lowercase(), value.trim().to_owned());
        }
        let known = [
            "poni_version",
            "detector",
            "detector_config",
            "pixelsize1",
            "pixelsize2",
            "distance",
            "poni1",
            "poni2",
            "rot1",
            "rot2",
            "rot3",
            "splinefile",
            "wavelength",
        ];
        if let Some(key) = fields.keys().find(|key| !known.contains(&key.as_str())) {
            return Err(format!(
                "PONI field {key} is not supported by the native backend yet."
            ));
        }
        let mut detector = match fields.get("detector").map(String::as_str) {
            None | Some("Detector") | Some("detector") => None,
            Some("NexusDetector") => {
                let config: Value = serde_json::from_str(
                    fields
                        .get("detector_config")
                        .ok_or("Missing Nexus detector config.")?,
                )
                .map_err(|e| e.to_string())?;
                let file = config["filename"]
                    .as_str()
                    .ok_or("Missing Nexus detector filename.")?;
                let file = Path::new(file);
                let resolved = if file.is_absolute() && file.exists() {
                    file.to_owned()
                } else {
                    path.parent()
                        .unwrap_or(Path::new("."))
                        .join(if file.is_absolute() {
                            Path::new(file.file_name().ok_or("Invalid detector filename.")?)
                        } else {
                            file
                        })
                };
                let mut g = Self::default();
                g.load_detector_file(&resolved)?;
                fields.insert(
                    "__native_detector_file".into(),
                    resolved.to_string_lossy().into_owned(),
                );
                g.detector.map(|d| d.as_ref().clone())
            }
            Some(name) => Some(dioptrin::detector::named(name)?),
        };
        let mut orientation = 3;
        let mut has_orientation = false;
        let mut max_shape = None;
        let mut spline = fields.get("splinefile").cloned();
        if fields
            .get("poni_version")
            .is_some_and(|v| !["1", "1.0", "2", "2.0", "2.1"].contains(&v.as_str()))
        {
            return Err("Unsupported PONI version.".into());
        }
        if let Some(config) = fields.get("detector_config") {
            let config: Value = serde_json::from_str(config).map_err(|e| e.to_string())?;
            let config = config
                .as_object()
                .ok_or("PONI detector config must be an object.")?;
            for (key, value) in config {
                match key.as_str() {
                    "pixel1" => {
                        fields.insert("pixelsize1".into(), value.to_string());
                    }
                    "pixel2" => {
                        fields.insert("pixelsize2".into(), value.to_string());
                    }
                    "orientation" => {
                        has_orientation = true;
                        orientation = value
                            .as_u64()
                            .filter(|v| *v <= 4)
                            .ok_or("Unsupported detector orientation.")?
                            as u8;
                    }
                    "max_shape" => {
                        max_shape = serde_json::from_value::<Option<[usize; 2]>>(value.clone())
                            .map_err(|e| e.to_string())?;
                    }
                    "filename" if fields.get("detector").is_some_and(|d| d == "NexusDetector") => {}
                    "splineFile" | "splinefile" => {
                        spline = value.as_str().map(str::to_owned);
                    }

                    "sensor" if value.is_null() => {}
                    _ if detector
                        .as_ref()
                        .is_some_and(|d| d.config.get(key) == Some(value)) => {}
                    _ => {
                        return Err(format!(
                            "Detector config {key} is not supported by the native backend yet."
                        ));
                    }
                }
            }
        }
        let declared = [
            fields.contains_key("pixelsize1"),
            fields.contains_key("pixelsize2"),
        ];
        if let Some(d) = &detector {
            fields
                .entry("pixelsize1".into())
                .or_insert(d.config["pixel1"].as_f64().unwrap_or(d.pixel1).to_string());
            fields
                .entry("pixelsize2".into())
                .or_insert(d.config["pixel2"].as_f64().unwrap_or(d.pixel2).to_string());
        }
        let read = |key: &str| -> Result<f64, String> {
            fields
                .get(key)
                .ok_or_else(|| format!("Missing PONI {key}."))?
                .parse()
                .map_err(|_| format!("Invalid PONI {key}."))
        };
        let mut geometry = Self {
            frame_pixels: None,
            auto_assign: false,
            assignment: None,
            candidates: vec![],
            detector: None,
            detector_file: None,
            distortion_file: None,
            dist: read("distance")?,
            poni1: read("poni1")?,
            poni2: read("poni2")?,
            rot1: read("rot1")?,
            rot2: read("rot2")?,
            rot3: read("rot3")?,
            pixel1: read("pixelsize1")?,
            pixel2: read("pixelsize2")?,
            wavelength: read("wavelength")?,
        };
        if declared.iter().any(|v| *v) {
            geometry.frame_pixels = Some([
                declared[0].then_some(geometry.pixel1),
                declared[1].then_some(geometry.pixel2),
            ]);
        }
        if fields.contains_key("detector_config")
            || orientation != 3
            || detector.is_some()
            || max_shape.is_some()
        {
            let mut d = detector.take().unwrap_or_else(|| {
                dioptrin::detector::Detector::custom(geometry.pixel1, geometry.pixel2)
            });
            if d.name == "Detector"
                && matches!(d.map, dioptrin::detector::PixelMap::Uniform)
                && !d.has_spline()
            {
                d.pixel1 = geometry.pixel1;
                d.pixel2 = geometry.pixel2;
            }
            // PONI v2 uses top-down file rows; the Dioptas scientific image is bottom-up.
            d.orientation = if has_orientation
                && fields
                    .get("poni_version")
                    .and_then(|v| v.parse::<f64>().ok())
                    .is_some_and(|v| v >= 2.)
            {
                match orientation {
                    0 | 3 => 2,
                    2 => 3,
                    1 => 4,
                    4 => 1,
                    _ => unreachable!(),
                }
            } else {
                orientation
            };
            if let Some(shape) = max_shape {
                if d.name == "Detector" && matches!(d.map, dioptrin::detector::PixelMap::Uniform) {
                    d.max_shape = Some(shape)
                } else if d.max_shape != Some(shape) {
                    return Err(
                        "PONI maximum shape differs from its named detector definition.".into(),
                    );
                }
            }
            d.validate()?;
            geometry.detector = Some(std::sync::Arc::new(d));
        }
        if let Some(file) = spline.filter(|s| !s.is_empty() && !s.eq_ignore_ascii_case("none")) {
            let spline_path = Path::new(&file);
            let resolved = if spline_path.is_absolute() && spline_path.exists() {
                spline_path.to_owned()
            } else {
                path.parent()
                    .unwrap_or(Path::new("."))
                    .join(if spline_path.is_absolute() {
                        Path::new(spline_path.file_name().ok_or("Invalid spline filename.")?)
                    } else {
                        spline_path
                    })
            };
            geometry.load_spline(&resolved)?;
        }
        if let Some(p) = geometry.frame_pixels {
            if let Some(v) = p[0] {
                geometry.pixel1 = v;
            }
            if let Some(v) = p[1] {
                geometry.pixel2 = v;
            }
        }
        geometry.detector_file = fields.get("__native_detector_file").cloned();
        geometry.validate()?;
        Ok(geometry)
    }
    pub fn manual(values: &Value) -> Result<(Self, f64), String> {
        let fields = values
            .as_object()
            .ok_or("Complete every geometry field before applying.")?;
        let keys = [
            "dist",
            "poni1",
            "poni2",
            "rot1",
            "rot2",
            "rot3",
            "pixel1",
            "pixel2",
            "wavelength",
            "polarization_factor",
        ];
        if fields.len() != keys.len() || keys.iter().any(|key| !fields.contains_key(*key)) {
            return Err("Complete every geometry field before applying.".into());
        }
        let n = |key| {
            fields[key]
                .as_f64()
                .filter(|n| n.is_finite())
                .ok_or_else(|| format!("Invalid geometry {key}."))
        };
        // The existing command carries SI values; the React form owns display
        // conversion to mm, µm and Å. Rotations remain radians.
        let geometry = Self {
            frame_pixels: None,
            auto_assign: false,
            assignment: None,
            candidates: vec![],
            detector: None,
            detector_file: None,
            distortion_file: None,
            dist: n("dist")?,
            poni1: n("poni1")?,
            poni2: n("poni2")?,
            rot1: n("rot1")?,
            rot2: n("rot2")?,
            rot3: n("rot3")?,
            pixel1: n("pixel1")?,
            pixel2: n("pixel2")?,
            wavelength: n("wavelength")?,
        };
        geometry.validate()?;
        let polarization = n("polarization_factor")?;
        if !(-1.0..=1.0).contains(&polarization) {
            return Err("Polarization must be between -1 and 1.".into());
        }
        Ok((geometry, polarization))
    }
    pub fn manual_values(&self, polarization: f64) -> Value {
        json!({"dist": self.dist, "poni1": self.poni1, "poni2": self.poni2,
            "pixel1": self.pixel1, "pixel2": self.pixel2, "wavelength": self.wavelength,
            "rot1": self.rot1, "rot2": self.rot2, "rot3": self.rot3, "polarization_factor": polarization})
    }
    pub fn save_text(&self) -> String {
        format!(
            "# Dioptas native backend; flat uniform pixels; SI geometry\nPixelSize1: {}\nPixelSize2: {}\nDistance: {}\nPoni1: {}\nPoni2: {}\nRot1: {}\nRot2: {}\nRot3: {}\nSplineFile: None\nWavelength: {}\n",
            self.pixel1,
            self.pixel2,
            self.dist,
            self.poni1,
            self.poni2,
            self.rot1,
            self.rot2,
            self.rot3,
            self.wavelength
        )
    }
}

impl PartialEq for Geometry {
    fn eq(&self, other: &Self) -> bool {
        let detectors = match (&self.detector, &other.detector) {
            (None, None) => true,
            (Some(a), Some(b)) => std::sync::Arc::ptr_eq(a, b) || a.as_ref() == b.as_ref(),
            _ => false,
        };
        detectors
            && (
                self.dist,
                self.poni1,
                self.poni2,
                self.rot1,
                self.rot2,
                self.rot3,
                self.pixel1,
                self.pixel2,
                self.wavelength,
            ) == (
                other.dist,
                other.poni1,
                other.poni2,
                other.rot1,
                other.rot2,
                other.rot3,
                other.pixel1,
                other.pixel2,
                other.wavelength,
            )
            && self.detector_file == other.detector_file
            && self.distortion_file == other.distortion_file
            && self.frame_pixels == other.frame_pixels
            && self.auto_assign == other.auto_assign
            && self.assignment == other.assignment
            && self.candidates == other.candidates
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn appended_poni_records_use_the_last_field_like_pyfai() {
        let fixture = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../dioptas/tests/data/LaB6_40keV_MarCCD.poni");
        let text = std::fs::read_to_string(&fixture).unwrap();
        assert_eq!(text.matches("Distance:").count(), 2);
        let geometry = Geometry::load(&fixture).unwrap();
        assert_eq!(geometry.dist, 0.196711580484);
        assert_eq!(geometry.poni1, 0.0813975852141);
        assert_eq!(geometry.poni2, 0.0820662115429);
        assert_eq!(geometry.rot1, 0.00615439716514);
        assert_eq!(geometry.rot2, -0.00156720465515);
        assert_eq!(geometry.rot3, 1.68707221612e-6);
        assert_eq!(geometry.wavelength, 3.1e-11);
        assert_eq!([geometry.pixel1, geometry.pixel2], [79e-6, 79e-6]);
        let temporary = tempfile::tempdir().unwrap();
        let path = temporary.path().join("repeated.poni");
        std::fs::write(&path, format!("{text}\nDISTANCE: 0.21\n")).unwrap();
        assert_eq!(Geometry::load(&path).unwrap().dist, 0.21);
        std::fs::write(&path, format!("{text}\nDistance: invalid\n")).unwrap();
        assert!(Geometry::load(&path).is_err());
    }

    #[test]
    fn eiger_poni_accepts_its_detector_shape_and_explains_pilatus_mismatch() {
        let temporary = tempfile::tempdir().unwrap();
        let path = temporary.path().join("eiger_0000.poni");
        std::fs::write(
            &path,
            concat!(
                "poni_version: 2.1\nDetector: Eiger2CdTe_9M\n",
                "Detector_config: {\"orientation\":2}\n",
                "Distance: 0.1839103128035422\nPoni1: 0.11374917888680143\n",
                "Poni2: 0.11053144274970403\nRot1: 0.012275635675880966\n",
                "Rot2: 0.012776464559415958\nRot3: -3.4968839362494736e-09\n",
                "Wavelength: 3.7380000000000004e-11\n"
            ),
        )
        .unwrap();
        let mut geometry = Geometry::load(&path).unwrap();
        let error = geometry.sync_shape([1043, 981]).unwrap_err();
        assert!(error.contains("Eiger2 CdTe 9M"));
        assert!(error.contains("3108 × 3262"));
        assert!(error.contains("981 × 1043"));
        assert!(error.contains("Open the matching detector image first"));
        geometry.sync_shape([3262, 3108]).unwrap();
        assert_eq!([geometry.pixel1, geometry.pixel2], [75e-6, 75e-6]);
        assert_eq!(geometry.detector.as_ref().unwrap().orientation, 3);
        assert_eq!(geometry.dist, 0.1839103128035422);
    }
    #[test]
    fn legacy_v2_orientation_and_transformed_spline_exports_keep_their_geometry() {
        use dioptrin::detector::{Detector, DetectorTransform, spline::Spline};
        use std::sync::Arc;
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path().join("legacy.poni");
        let g = Geometry::default();
        let text = format!(
            "poni_version: 2\n{}Detector_config: {{\"pixel1\":0.000079,\"pixel2\":0.000079}}\n",
            g.save_text()
        );
        std::fs::write(&path, text).unwrap();
        let loaded = Geometry::load(&path).unwrap();
        assert_eq!(loaded.detector.as_ref().unwrap().orientation, 3);
        let mut d = Detector::custom(50e-6, 50e-6);
        d.max_shape = Some([3, 5]);
        let fixture = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../dioptas/tests/data/distortion/f4mnew.spline");
        d.spline = Some(Arc::new(
            Spline::parse(&std::fs::read_to_string(fixture).unwrap()).unwrap(),
        ));
        let d = d
            .transformed(DetectorTransform::Left)
            .unwrap()
            .transformed(DetectorTransform::Horizontal)
            .unwrap();
        let original = Geometry {
            detector: Some(Arc::new(d)),
            pixel1: 50e-6,
            pixel2: 50e-6,
            ..Default::default()
        };
        let path = temp.path().join("transformed.poni");
        original.save_to(&path).unwrap();
        let mut restored = Geometry::load(&path).unwrap();
        let before = original.native_geometry([5, 3]).unwrap().calc_tth_all();
        let after = restored.native_geometry([5, 3]).unwrap().calc_tth_all();
        assert_eq!(before, after);
        assert!(restored.detector.as_ref().unwrap().has_spline());
        restored.reset_spline();
        assert!(!restored.detector.as_ref().unwrap().has_spline());
    }
}

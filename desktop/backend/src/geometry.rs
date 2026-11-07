use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{collections::BTreeMap, path::Path};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Geometry {
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
    #[cfg(feature = "dioptrin")]
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
    /// The first native slice admits explicit flat uniform geometry only. Never
    /// silently discard a detector definition, orientation or spline correction.
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
            if fields
                .insert(key.trim().to_lowercase(), value.trim().to_owned())
                .is_some()
            {
                return Err("Duplicate PONI field.".into());
            }
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
        if fields
            .get("detector")
            .is_some_and(|v| !v.eq_ignore_ascii_case("detector"))
        {
            return Err("Named detector definitions are not supported by the native backend yet; their geometry must not be discarded.".into());
        }
        if fields
            .get("splinefile")
            .is_some_and(|v| !v.eq_ignore_ascii_case("none") && !v.is_empty())
        {
            return Err("Distortion splines are not supported by the native backend yet.".into());
        }
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
                    "orientation" if value.as_i64() == Some(3) => {}
                    "max_shape" => {}
                    _ => {
                        return Err(format!(
                            "Detector config {key} is not supported by the native backend yet."
                        ));
                    }
                }
            }
        }
        let read = |key: &str| -> Result<f64, String> {
            fields
                .get(key)
                .ok_or_else(|| format!("Missing PONI {key}."))?
                .parse()
                .map_err(|_| format!("Invalid PONI {key}."))
        };
        let geometry = Self {
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

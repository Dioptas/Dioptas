//! Native image background, flat field and absorption pipeline.
use crate::{geometry::Geometry, image::Image};
use serde_json::{Value, json};
use std::{path::Path, sync::Arc};
#[derive(Clone)]
struct Plane {
    path: String,
    shape: [usize; 2],
    values: Arc<Vec<f64>>,
}
impl Plane {
    fn open(path: &Path, shape: [usize; 2]) -> Result<Self, String> {
        let image = Image::open(path, &json!({}))?;
        if image.shape != shape {
            return Err("Correction/background image must have the same detector shape.".into());
        }
        Ok(Self {
            path: image.path.to_string_lossy().into_owned(),
            shape,
            values: image.values,
        })
    }
}
#[derive(Clone)]
struct Cached {
    generation: u64,
    geometry: Option<Geometry>,
    values: Arc<Vec<f64>>,
}
#[derive(Clone)]
pub(crate) struct Processing {
    background: Option<Plane>,
    pub scale: f64,
    pub offset: f64,
    flat: Option<Plane>,
    flat_enabled: bool,
    corrections: Value,
    cache: Option<Cached>,
}
impl PartialEq for Processing {
    fn eq(&self, other: &Self) -> bool {
        let same = |a: &Option<Plane>, b: &Option<Plane>| match (a, b) {
            (None, None) => true,
            (Some(a), Some(b)) => {
                a.path == b.path && a.shape == b.shape && Arc::ptr_eq(&a.values, &b.values)
            }
            _ => false,
        };
        self.scale == other.scale
            && self.offset == other.offset
            && self.flat_enabled == other.flat_enabled
            && self.corrections == other.corrections
            && same(&self.background, &other.background)
            && same(&self.flat, &other.flat)
    }
}
impl Default for Processing {
    fn default() -> Self {
        Self {
            background: None,
            scale: 1.0,
            offset: 0.0,
            flat: None,
            flat_enabled: false,
            corrections: serde_json::from_str(include_str!("correction_defaults.json")).unwrap(),
            cache: None,
        }
    }
}
impl Processing {
    pub fn estimated_bytes(&self) -> usize {
        self.cache.as_ref().map_or(0, |c| c.values.len() * 8)
            + self.background.as_ref().map_or(0, |p| p.values.len() * 8)
            + self.flat.as_ref().map_or(0, |p| p.values.len() * 8)
    }
    pub fn active(&self) -> bool {
        self.background.is_some()
            || self.flat_enabled
            || self
                .corrections
                .as_object()
                .unwrap()
                .values()
                .any(|v| v["enabled"] == true)
    }
    pub fn details(&self) -> Value {
        json!({"imageBackground":{"filename":self.background.as_ref().map(|p|&p.path),"scale":self.scale,"offset":self.offset},"flatField":{"filename":self.flat.as_ref().map(|p|&p.path),"enabled":self.flat_enabled},"corrections":self.corrections})
    }
    pub fn background(&mut self, args: &Value, shape: [usize; 2]) -> Result<(), String> {
        if args.get("reset").is_some_and(|v| v == true) {
            self.background = None;
        } else if let Some(path) = args.get("path").and_then(Value::as_str) {
            self.background = Some(Plane::open(Path::new(path), shape)?);
        }
        for (key, slot) in [("scale", &mut self.scale), ("offset", &mut self.offset)] {
            if let Some(v) = args.get(key) {
                *slot = v
                    .as_f64()
                    .filter(|v| v.is_finite() && v.abs() <= 1e12)
                    .ok_or("Background scale/offset must be finite and within ±1e12.")?;
            }
        }
        if args.get("reset").is_some_and(|v| !v.is_boolean()) {
            return Err("Reset must be a boolean.".into());
        }
        self.cache = None;
        Ok(())
    }
    pub fn flat_field(&mut self, args: &Value, shape: [usize; 2]) -> Result<(), String> {
        let enabled = args
            .get("enabled")
            .map(|v| v.as_bool().ok_or("Flat field enabled must be a boolean."))
            .transpose()?
            .unwrap_or(true);
        let reset = args
            .get("reset")
            .map(|v| v.as_bool().ok_or("Reset must be a boolean."))
            .transpose()?
            .unwrap_or(false);
        if reset {
            self.flat = None;
            self.flat_enabled = false;
        } else if !enabled {
            self.flat_enabled = false;
        } else {
            if let Some(path) = args.get("path").and_then(Value::as_str) {
                let mut plane = Plane::open(Path::new(path), shape)?;
                let mean = plane.values.iter().sum::<f64>() / plane.values.len() as f64;
                let response: Vec<_> = plane
                    .values
                    .iter()
                    .map(|&v| {
                        let x = if mean != 0.0 { v / mean } else { v };
                        if x == 0.0 { 1.0 } else { x }
                    })
                    .collect();
                if response.iter().any(|v| !v.is_finite() || *v <= 0.0) {
                    return Err("Flat field must contain finite, positive response factors.".into());
                }
                plane.values = Arc::new(response);
                self.flat = Some(plane);
            }
            if self.flat.is_none() {
                return Err("Choose a flat-field image.".into());
            }
            self.flat_enabled = true;
        }
        self.cache = None;
        Ok(())
    }
    pub fn correction(&mut self, args: &Value, calibrated: bool) -> Result<(), String> {
        let kind = args["kind"]
            .as_str()
            .filter(|v| ["cbn", "oiadac"].contains(v))
            .ok_or("Unsupported correction.")?;
        let enabled = args["enabled"]
            .as_bool()
            .ok_or("Correction enabled must be a boolean.")?;
        if enabled && !calibrated {
            return Err("Load an image and calibration first.".into());
        }
        let entry = &mut self.corrections[kind];
        if let Some(values) = args.get("parameters") {
            for (key, value) in values
                .as_object()
                .ok_or("Correction parameters must be an object.")?
            {
                let field = &entry["fields"][key];
                if field.is_null() {
                    return Err("Unknown correction parameter.".into());
                }
                let v = value
                    .as_f64()
                    .filter(|v| {
                        v.is_finite()
                            && *v >= field["min"].as_f64().unwrap()
                            && *v <= field["max"].as_f64().unwrap()
                    })
                    .ok_or_else(|| format!("Invalid correction parameter {key}."))?;
                entry["parameters"][key] = json!(v);
            }
        }
        if kind == "cbn"
            && entry["parameters"]["small_cbn_seat_radius"].as_f64()
                > entry["parameters"]["large_cbn_seat_radius"].as_f64()
        {
            return Err("Small seat radius must not exceed large seat radius.".into());
        }
        #[cfg(not(feature = "dioptrin"))]
        if enabled {
            return Err(
                "Absorption corrections require the optional Dioptrin geometry engine.".into(),
            );
        }
        entry["enabled"] = json!(enabled);
        self.cache = None;
        Ok(())
    }
    pub fn values(
        &mut self,
        image: &Image,
        generation: u64,
        geometry: &Geometry,
    ) -> Result<Arc<Vec<f64>>, String> {
        if self
            .background
            .as_ref()
            .is_some_and(|p| p.shape != image.shape)
        {
            self.background = None;
            self.cache = None;
        }
        if self.flat.as_ref().is_some_and(|p| p.shape != image.shape) {
            self.flat = None;
            self.flat_enabled = false;
            self.cache = None;
        }
        if !self.active() {
            return Ok(image.values.clone());
        }
        let geometry_active = self
            .corrections
            .as_object()
            .unwrap()
            .values()
            .any(|v| v["enabled"] == true);
        let g = geometry_active.then(|| geometry.clone());
        if let Some(c) = &self.cache
            && c.generation == generation
            && c.geometry == g
        {
            return Ok(c.values.clone());
        }
        let mut values = image.values.as_ref().clone();
        if let Some(background) = &self.background {
            for (v, b) in values.iter_mut().zip(background.values.iter()) {
                *v -= self.scale * b + self.offset;
            }
        }
        if self.flat_enabled {
            let response = &self.flat.as_ref().unwrap().values;
            for (v, f) in values.iter_mut().zip(response.iter()) {
                *v /= f;
            }
        }
        #[cfg(feature = "dioptrin")]
        if geometry_active {
            let native = dioptrin::geometry::Geometry::new(
                image.shape[0],
                image.shape[1],
                geometry.native_poni(),
            );
            let tth = native.calc_tth_all();
            let azi = native.calc_azimuth_all();
            for (kind, entry) in self.corrections.as_object().unwrap() {
                if entry["enabled"] != true {
                    continue;
                }
                for (i, v) in values.iter_mut().enumerate() {
                    let factor = absorption(kind, &entry["parameters"], tth[i], azi[i]);
                    if !factor.is_finite() || factor <= 0.0 {
                        return Err(
                            "Correction is not finite and positive across this detector.".into(),
                        );
                    }
                    *v /= factor;
                }
            }
        }
        let values = Arc::new(values);
        self.cache = Some(Cached {
            generation,
            geometry: g,
            values: values.clone(),
        });
        Ok(values)
    }
}
#[cfg(feature = "dioptrin")]
fn absorption(kind: &str, p: &Value, tth: f64, azi: f64) -> f64 {
    let n = |key: &str| p[key].as_f64().unwrap();
    if kind == "oiadac" {
        let tilt = n("tilt").to_radians();
        let rotation = n("rotation").to_radians();
        let d = n("detector_thickness");
        let mu = 1.0 / n("absorption_length");
        let angle = (tth * tth + tilt * tilt
            - 2.0 * tilt * tth * (std::f64::consts::PI - azi + rotation).cos())
        .sqrt();
        (1.0 - (-mu * d / angle.cos()).exp()) / (1.0 - (-mu * d).exp())
    } else {
        let diam = n("diamond_thickness");
        let ds = n("seat_thickness");
        let mut r1 = n("small_cbn_seat_radius");
        let mut r2 = n("large_cbn_seat_radius");
        let tilt = -n("tilt").to_radians();
        let rotation = n("tilt_rotation").to_radians() + std::f64::consts::FRAC_PI_2;
        let offset = n("center_offset");
        let angle = n("center_offset_angle").to_radians();
        if offset != 0.0 {
            let beta =
                azi - (offset * (std::f64::consts::PI - (azi + angle)).sin() / r1).asin() + angle;
            r1 = (r1 * r1 + offset * offset - 2.0 * r1 * offset * beta.cos()).sqrt();
            r2 = (r2 * r2 + offset * offset - 2.0 * r2 * offset * beta.cos()).sqrt();
        }
        let dot = tilt.cos() * tth.cos() + rotation.sin() * tilt.sin() * azi.cos() * tth.sin()
            - rotation.cos() * tilt.sin() * azi.sin() * tth.sin();
        let tt = dot.clamp(-1.0, 1.0).acos();
        let ts1 = (r1 / diam).atan();
        let ts2 = (r2 / (diam + ds)).atan();
        let seat = if tt >= ts2 {
            ds / tt.cos()
        } else if tt > ts1 && tt < ts2 {
            let alpha = std::f64::consts::FRAC_PI_2 - ((r2 - r1) / ds).atan();
            let gamma = std::f64::consts::PI - (alpha + tt + std::f64::consts::FRAC_PI_2);
            (diam * tt.tan() - r1) * alpha.sin() / gamma.sin()
        } else {
            0.0
        };
        (-diam / tt.cos() / n("diamond_abs_length")).exp() * (-seat / n("cbn_abs_length")).exp()
    }
}

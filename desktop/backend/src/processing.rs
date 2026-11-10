//! Native image background, flat field and absorption pipeline.
use crate::{geometry::Geometry, image::Image};
use serde_json::{Value, json};
use std::{path::Path, sync::Arc};
#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct Plane {
    path: String,
    shape: [usize; 2],
    #[serde(with = "crate::history_transfer::arc")]
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
    factor: f64,
    geometry: Option<Geometry>,
    values: Arc<Vec<f64>>,
    variance: Arc<Vec<f64>>,
}
#[derive(Clone, serde::Serialize, serde::Deserialize)]
pub(crate) struct Processing {
    background: Option<Plane>,
    pub scale: f64,
    pub offset: f64,
    pub factor: f64,
    flat: Option<Plane>,
    flat_enabled: bool,
    transfer_original: Option<Plane>,
    transfer_response: Option<Plane>,
    transfer_enabled: bool,
    pub background_poisson: bool,
    corrections: Value,
    #[serde(skip)]
    cache: Option<Cached>,
    #[cfg(feature = "dioptrin")]
    #[serde(skip)]
    sample_maps: crate::sample_absorption::Maps,
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
            && self.factor == other.factor
            && self.flat_enabled == other.flat_enabled
            && self.transfer_enabled == other.transfer_enabled
            && self.background_poisson == other.background_poisson
            && same(&self.transfer_original, &other.transfer_original)
            && same(&self.transfer_response, &other.transfer_response)
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
            factor: 1.0,
            flat: None,
            flat_enabled: false,
            transfer_original: None,
            transfer_response: None,
            transfer_enabled: false,
            background_poisson: true,
            corrections: serde_json::from_str(include_str!("correction_defaults.json")).unwrap(),
            cache: None,
            #[cfg(feature = "dioptrin")]
            sample_maps: crate::sample_absorption::Maps::default(),
        }
    }
}
impl Processing {
    /// Freeze deterministic maps once while preserving every divide/multiply
    /// in the established pixel arithmetic. Regrouping gains can change a mask
    /// comparison for a pixel exactly on its threshold.
    #[cfg(feature = "dioptrin")]
    pub(crate) fn series_snapshot(
        &self,
        image: &Image,
        geometry: &Geometry,
        control: &crate::control::Control,
    ) -> Result<SeriesProcessing, String> {
        let mut processing = self.clone();
        processing.resolve_materials(geometry)?;
        let orient = |p: &Plane| {
            crate::transform::apply(&p.values, p.shape, &image.transformations, control)
        };
        let background = processing
            .background
            .as_ref()
            .filter(|p| p.shape == image.source_shape)
            .map(orient)
            .transpose()?;
        let mut operations = vec![];
        if processing.flat_enabled
            && let Some(flat) = processing
                .flat
                .as_ref()
                .filter(|p| p.shape == image.source_shape)
        {
            operations.push(SeriesOperation::Divide(orient(flat)?));
        }
        if processing.transfer_enabled
            && let (Some(original), Some(response)) =
                (&processing.transfer_original, &processing.transfer_response)
            && original.shape == image.source_shape
            && response.shape == image.source_shape
        {
            let gains = Arc::new(
                original
                    .values
                    .iter()
                    .zip(response.values.iter())
                    .map(|(o, r)| o / r)
                    .collect(),
            );
            operations.push(SeriesOperation::Multiply(crate::transform::apply(
                &gains,
                original.shape,
                &image.transformations,
                control,
            )?));
        }
        let mut angles = None;
        for (kind, entry) in processing.corrections.as_object().unwrap() {
            if entry["enabled"] != true {
                continue;
            }
            let mut parameters = entry["parameters"].clone();
            if kind == "cylinder" && entry["container"]["enabled"] != true {
                parameters["container_absorption_coefficient"] = json!(0.);
            }
            let factors = if (kind == "cylinder" || kind == "sphere")
                && let Some(values) =
                    processing
                        .sample_maps
                        .lookup(kind, &parameters, geometry, image.shape)
            {
                values
            } else {
                if angles.is_none() {
                    let native = geometry.native_geometry(image.shape)?;
                    angles = Some((native.calc_tth_all(), native.calc_azimuth_all()));
                }
                let (tth, azi) = angles.as_ref().unwrap();
                let values = if kind == "cylinder" || kind == "sphere" {
                    crate::sample_absorption::build(kind, &parameters, tth, azi, control)?
                } else {
                    let mut values = Vec::with_capacity(tth.len());
                    for (i, (&t, &a)) in tth.iter().zip(azi).enumerate() {
                        if i % 65536 == 0 {
                            control.check()?;
                        }
                        let factor = absorption(kind, &parameters, t, a);
                        if !factor.is_finite() || factor <= 0. {
                            return Err(
                                "Correction is not finite and positive across this detector."
                                    .into(),
                            );
                        }
                        values.push(factor);
                    }
                    values
                };
                Arc::new(values)
            };
            operations.push(SeriesOperation::Divide(factors));
        }
        Ok(SeriesProcessing {
            operations,
            background,
            scale: self.scale,
            offset: self.offset,
            factor: self.factor,
            background_poisson: self.background_poisson,
        })
    }
    pub fn estimated_bytes(&self) -> usize {
        #[cfg(feature = "dioptrin")]
        let map_bytes = self.sample_maps.bytes();
        #[cfg(not(feature = "dioptrin"))]
        let map_bytes = 0;
        map_bytes
            + self
                .cache
                .as_ref()
                .map_or(0, |c| (c.values.len() + c.variance.len()) * 8)
            + self.background.as_ref().map_or(0, |p| p.values.len() * 8)
            + self.flat.as_ref().map_or(0, |p| p.values.len() * 8)
            + self
                .transfer_original
                .as_ref()
                .map_or(0, |p| p.values.len() * 8)
            + self
                .transfer_response
                .as_ref()
                .map_or(0, |p| p.values.len() * 8)
    }
    #[cfg(feature = "dioptrin")]
    pub fn diagnostics(&self) -> Value {
        self.sample_maps.diagnostics()
    }
    pub fn active(&self) -> bool {
        self.factor != 1.0
            || self.background.is_some()
            || self.flat_enabled
            || self.transfer_enabled
            || self
                .corrections
                .as_object()
                .unwrap()
                .values()
                .any(|v| v["enabled"] == true)
    }
    pub fn project_background(&self) -> Option<(&str, [usize; 2], &[f64])> {
        self.background
            .as_ref()
            .map(|p| (p.path.as_str(), p.shape, p.values.as_slice()))
    }
    pub fn project_flat(&self) -> Option<(&str, [usize; 2], &[f64], bool)> {
        self.flat.as_ref().map(|p| {
            (
                p.path.as_str(),
                p.shape,
                p.values.as_slice(),
                self.flat_enabled,
            )
        })
    }
    pub fn variance(&self) -> Option<Arc<Vec<f64>>> {
        self.cache.as_ref().map(|c| c.variance.clone())
    }
    pub fn project_transfer(&self, source: &str) -> Option<(&str, [usize; 2], &[f64])> {
        let plane = if source == "original" {
            &self.transfer_original
        } else {
            &self.transfer_response
        };
        plane
            .as_ref()
            .map(|p| (p.path.as_str(), p.shape, p.values.as_slice()))
    }
    pub fn restore_transfer(
        &mut self,
        source: &str,
        path: String,
        shape: [usize; 2],
        values: Vec<f64>,
    ) -> Result<(), String> {
        if values.len() != shape[0] * shape[1] || values.iter().any(|v| !v.is_finite() || *v <= 0.0)
        {
            return Err("Transfer references must contain finite, positive counts.".into());
        }
        let plane = Some(Plane {
            path,
            shape,
            values: Arc::new(values),
        });
        match source {
            "original" => self.transfer_original = plane,
            "response" => self.transfer_response = plane,
            _ => return Err("Unknown transfer reference.".into()),
        }
        self.cache = None;
        Ok(())
    }
    pub fn transfer(&mut self, args: &Value, shape: [usize; 2]) -> Result<(), String> {
        if let Some(source) = args.get("source") {
            let source = source
                .as_str()
                .filter(|v| ["original", "response"].contains(v))
                .ok_or("Choose original or response transfer reference.")?;
            if let Some(reset) = args.get("reset") {
                if !reset.is_boolean() {
                    return Err("Reset must be a boolean.".into());
                }
                if reset == true {
                    if source == "original" {
                        self.transfer_original = None;
                    } else {
                        self.transfer_response = None;
                    }
                    self.transfer_enabled = false;
                }
            }
            if let Some(path) = args.get("path") {
                let plane = Plane::open(
                    Path::new(path.as_str().ok_or("Transfer path must be a string.")?),
                    shape,
                )?;
                self.restore_transfer(source, plane.path, shape, plane.values.as_ref().clone())?;
            }
        } else if args.get("path").is_some() || args.get("reset").is_some() {
            return Err("Choose original or response transfer reference.".into());
        }
        if let Some(enabled) = args.get("enabled") {
            let enabled = enabled
                .as_bool()
                .ok_or("Transfer enabled must be a boolean.")?;
            if enabled && (self.transfer_original.is_none() || self.transfer_response.is_none()) {
                return Err("Choose both transfer reference images first.".into());
            }
            self.transfer_enabled = enabled;
        }
        self.cache = None;
        Ok(())
    }
    pub fn restore_background(&mut self, path: String, shape: [usize; 2], values: Vec<f64>) {
        self.background = Some(Plane {
            path,
            shape,
            values: Arc::new(values),
        });
        self.cache = None;
    }
    pub fn restore_flat(
        &mut self,
        path: String,
        shape: [usize; 2],
        values: Vec<f64>,
        enabled: bool,
    ) -> Result<(), String> {
        if values.len() != shape[0] * shape[1] || values.iter().any(|v| !v.is_finite() || *v <= 0.0)
        {
            return Err("Invalid project flat-field response.".into());
        }
        self.flat = Some(Plane {
            path,
            shape,
            values: Arc::new(values),
        });
        self.flat_enabled = enabled;
        self.cache = None;
        Ok(())
    }
    pub fn details(&self) -> Value {
        json!({"imageBackground":{"filename":self.background.as_ref().map(|p|&p.path),"scale":self.scale,"offset":self.offset,"poisson":self.background_poisson},"flatField":{"filename":self.flat.as_ref().map(|p|&p.path),"enabled":self.flat_enabled},"transfer":{"original":self.transfer_original.as_ref().map(|p|&p.path),"response":self.transfer_response.as_ref().map(|p|&p.path),"enabled":self.transfer_enabled},"corrections":self.corrections})
    }
    pub fn background(&mut self, args: &Value, shape: [usize; 2]) -> Result<(), String> {
        if args.get("reset").is_some_and(|v| v == true) {
            self.background = None;
        } else if let Some(path) = args.get("path").and_then(Value::as_str) {
            self.background = Some(Plane::open(Path::new(path), shape)?);
        }
        if let Some(v) = args.get("poisson") {
            self.background_poisson = v
                .as_bool()
                .ok_or("Background counting noise must be a boolean.")?;
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
            .filter(|v| ["cbn", "oiadac", "plate", "slab", "cylinder", "sphere"].contains(v))
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
        if let Some(patch) = args.get("material") {
            if !["plate", "slab", "cylinder", "sphere"].contains(&kind) {
                return Err(
                    "Material lookup is available for plate, slab, cylinder and sphere absorption."
                        .into(),
                );
            }
            let patch = patch
                .as_object()
                .ok_or("Material settings must be an object.")?;
            for (key, value) in patch {
                if !["mode", "formula", "density"].contains(&key.as_str()) {
                    return Err("Unknown material setting.".into());
                }
                entry["material"][key] = value.clone();
            }
            validate_material(&entry["material"])?;
        }
        if let Some(patch) = args.get("container") {
            if kind != "cylinder" {
                return Err("A container wall is available for cylinder absorption.".into());
            }
            for (key, value) in patch
                .as_object()
                .ok_or("Container settings must be an object.")?
            {
                match key.as_str() {
                    "enabled" => {
                        if !value.is_boolean() {
                            return Err("Container enabled must be a boolean.".into());
                        }
                        entry["container"][key] = value.clone();
                    }
                    "material" => {
                        for (key, value) in value
                            .as_object()
                            .ok_or("Container material settings must be an object.")?
                        {
                            if !["mode", "formula", "density"].contains(&key.as_str()) {
                                return Err("Unknown container material setting.".into());
                            }
                            entry["container"]["material"][key] = value.clone();
                        }
                        validate_material(&entry["container"]["material"])?;
                    }
                    _ => return Err("Unknown container setting.".into()),
                }
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
    fn resolve_materials(&mut self, geometry: &Geometry) -> Result<(), String> {
        for kind in ["plate", "slab", "cylinder", "sphere"] {
            let entry = &mut self.corrections[kind];
            if entry["enabled"] == true && entry["material"]["mode"] == "formula" {
                let mu = material_mu(&entry["material"], geometry.wavelength)?;
                entry["parameters"]["absorption_coefficient"] = json!(mu);
            }
        }
        let cylinder = &mut self.corrections["cylinder"];
        if cylinder["enabled"] == true
            && cylinder["container"]["enabled"] == true
            && cylinder["parameters"]["wall_thickness"]
                .as_f64()
                .is_some_and(|v| v > 0.)
            && cylinder["container"]["material"]["mode"] == "formula"
        {
            cylinder["parameters"]["container_absorption_coefficient"] = json!(material_mu(
                &cylinder["container"]["material"],
                geometry.wavelength
            )?);
        }
        Ok(())
    }
    pub fn values(
        &mut self,
        image: &Image,
        generation: u64,
        geometry: &Geometry,
        control: &crate::control::Control,
    ) -> Result<Arc<Vec<f64>>, String> {
        if self
            .background
            .as_ref()
            .is_some_and(|p| p.shape != image.source_shape)
        {
            self.background = None;
            self.cache = None;
        }
        if self
            .flat
            .as_ref()
            .is_some_and(|p| p.shape != image.source_shape)
        {
            self.flat = None;
            self.flat_enabled = false;
            self.cache = None;
        }
        if self
            .transfer_original
            .as_ref()
            .is_some_and(|p| p.shape != image.source_shape)
            || self
                .transfer_response
                .as_ref()
                .is_some_and(|p| p.shape != image.source_shape)
        {
            self.transfer_original = None;
            self.transfer_response = None;
            self.transfer_enabled = false;
            self.cache = None;
        }
        if !self.active() {
            self.cache = None;
            return Ok(image.values.clone());
        }
        control.check()?;
        self.resolve_materials(geometry)?;
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
            && c.factor == self.factor
        {
            return Ok(c.values.clone());
        }
        let mut values = image.values.as_ref().clone();
        let mut variance: Vec<f64> = image
            .input_variance()
            .map(|v| v.as_ref().clone())
            .unwrap_or_else(|| values.iter().map(|v| v.max(0.0)).collect());
        if let Some(background) = &self.background {
            let background = crate::transform::apply(
                &background.values,
                background.shape,
                &image.transformations,
                control,
            )?;
            for ((v, var), b) in values.iter_mut().zip(&mut variance).zip(background.iter()) {
                *v -= self.scale * b + self.offset;
                if self.background_poisson {
                    *var += self.scale * self.scale * b.max(0.0);
                }
            }
        }
        if self.flat_enabled {
            let flat = self.flat.as_ref().unwrap();
            let response =
                crate::transform::apply(&flat.values, flat.shape, &image.transformations, control)?;
            for ((v, var), f) in values.iter_mut().zip(&mut variance).zip(response.iter()) {
                *v /= f;
                *var /= f * f;
            }
        }
        if self.transfer_enabled {
            let original = self.transfer_original.as_ref().unwrap();
            let response = self.transfer_response.as_ref().unwrap();
            let gains: Vec<_> = original
                .values
                .iter()
                .zip(response.values.iter())
                .map(|(o, r)| o / r)
                .collect();
            let gains = crate::transform::apply(
                &Arc::new(gains),
                original.shape,
                &image.transformations,
                control,
            )?;
            for ((v, var), gain) in values.iter_mut().zip(&mut variance).zip(gains.iter()) {
                *v *= gain;
                *var *= gain * gain;
            }
        }
        #[cfg(feature = "dioptrin")]
        if geometry_active {
            let mut angles = None;
            for (kind, entry) in self.corrections.as_object().unwrap() {
                if entry["enabled"] != true {
                    continue;
                }
                if kind == "cylinder" || kind == "sphere" {
                    let mut parameters = entry["parameters"].clone();
                    if kind == "cylinder" && entry["container"]["enabled"] != true {
                        parameters["container_absorption_coefficient"] = json!(0.);
                    }
                    let factors = if let Some(v) =
                        self.sample_maps
                            .lookup(kind, &parameters, geometry, image.shape)
                    {
                        v
                    } else {
                        if angles.is_none() {
                            let native = geometry.native_geometry(image.shape)?;
                            angles = Some((native.calc_tth_all(), native.calc_azimuth_all()));
                        }
                        let (tth, azi) = angles.as_ref().unwrap();
                        let factors =
                            crate::sample_absorption::build(kind, &parameters, tth, azi, control)?;
                        self.sample_maps.store(
                            kind,
                            parameters,
                            geometry.clone(),
                            image.shape,
                            factors,
                        )
                    };
                    for ((v, var), factor) in
                        values.iter_mut().zip(&mut variance).zip(factors.iter())
                    {
                        *v /= factor;
                        *var /= factor * factor;
                    }
                    continue;
                }
                if angles.is_none() {
                    let native = geometry.native_geometry(image.shape)?;
                    angles = Some((native.calc_tth_all(), native.calc_azimuth_all()));
                }
                let (tth, azi) = angles.as_ref().unwrap();
                for (i, v) in values.iter_mut().enumerate() {
                    let factor = absorption(kind, &entry["parameters"], tth[i], azi[i]);
                    if !factor.is_finite() || factor <= 0.0 {
                        return Err(
                            "Correction is not finite and positive across this detector.".into(),
                        );
                    }
                    *v /= factor;
                    variance[i] /= factor * factor;
                }
            }
        }
        if self.factor != 1.0 {
            for (value, var) in values.iter_mut().zip(&mut variance) {
                *value *= self.factor;
                *var *= self.factor * self.factor;
            }
        }
        if values.iter().any(|v| !v.is_finite()) || variance.iter().any(|v| !v.is_finite()) {
            return Err("Processing produced nonfinite intensities or variances; check correction parameters.".into());
        }
        let values = Arc::new(values);
        self.cache = Some(Cached {
            generation,
            factor: self.factor,
            geometry: g,
            values: values.clone(),
            variance: Arc::new(variance),
        });
        Ok(values)
    }
}

/// I = (S - b B - o) g; V = (max(S,0) + b² max(B,0)) g².
/// Only original counting noise is stochastic; correction maps are fixed.
#[cfg(feature = "dioptrin")]
pub(crate) struct SeriesProcessing {
    operations: Vec<SeriesOperation>,
    background: Option<Arc<Vec<f64>>>,
    scale: f64,
    offset: f64,
    background_poisson: bool,
    factor: f64,
}
#[cfg(feature = "dioptrin")]
enum SeriesOperation {
    Divide(Arc<Vec<f64>>),
    Multiply(Arc<Vec<f64>>),
}
#[cfg(feature = "dioptrin")]
impl SeriesProcessing {
    pub fn apply(
        &self,
        values: &mut [f64],
        variance: Option<&mut Vec<f64>>,
        control: &crate::control::Control,
    ) -> Result<(), String> {
        let mut variance = variance;
        if let Some(v) = variance.as_mut() {
            v.resize(values.len(), 0.);
        }
        for (i, value) in values.iter_mut().enumerate() {
            if i % 65536 == 0 {
                control.check()?;
            }
            let mut var = value.max(0.);
            if let Some(background) = &self.background {
                *value -= self.scale * background[i] + self.offset;
                if self.background_poisson {
                    var += self.scale * self.scale * background[i].max(0.);
                }
            }
            for operation in &self.operations {
                match operation {
                    SeriesOperation::Divide(factors) => {
                        *value /= factors[i];
                        var /= factors[i] * factors[i];
                    }
                    SeriesOperation::Multiply(factors) => {
                        *value *= factors[i];
                        var *= factors[i] * factors[i];
                    }
                }
            }
            if self.factor != 1. {
                *value *= self.factor;
                var *= self.factor * self.factor;
            }
            if !value.is_finite() || !var.is_finite() {
                return Err("Processing produced nonfinite intensities or variances; check correction parameters.".into());
            }
            if let Some(v) = variance.as_mut() {
                v[i] = var;
            }
        }
        Ok(())
    }
}

#[cfg(all(test, feature = "dioptrin"))]
mod series_tests {
    use super::*;

    #[test]
    fn prepared_operations_preserve_pixel_bits_and_variances_for_all_corrections() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("raw.h5");
        let shape = [24, 32];
        let n = shape[0] * shape[1];
        let file = hdf5::File::create(&path).unwrap();
        file.new_dataset::<u32>()
            .shape(shape)
            .create("counts")
            .unwrap()
            .write_raw(&(0..n).map(|i| (i % 97) as u32).collect::<Vec<_>>())
            .unwrap();
        drop(file);
        let image = Image::open(&path, &json!({"dataset":"/counts"})).unwrap();
        let (geometry, _) = Geometry::manual(&json!({"dist":0.15,"poni1":0.0012,"poni2":0.0016,
            "rot1":0.01,"rot2":-0.02,"rot3":0.,"pixel1":0.0001,"pixel2":0.0001,"wavelength":0.5e-10,"polarization_factor":0.965})).unwrap();
        let control = crate::control::Control::default();
        for kind in [
            "none", "cbn", "oiadac", "plate", "slab", "cylinder", "sphere",
        ] {
            let mut processing = Processing::default();
            processing.restore_background(
                "background".into(),
                shape,
                (0..n).map(|i| 80. + (i % 19) as f64).collect(),
            );
            processing.scale = 1.3;
            processing.offset = -2.4;
            processing
                .restore_flat(
                    "flat".into(),
                    shape,
                    (0..n).map(|i| 0.8 + (i % 13) as f64 / 30.).collect(),
                    true,
                )
                .unwrap();
            processing
                .restore_transfer("original", "original".into(), shape, vec![1.7; n])
                .unwrap();
            processing
                .restore_transfer("response", "response".into(), shape, vec![0.9; n])
                .unwrap();
            processing.transfer_enabled = true;
            if kind != "none" {
                processing
                    .correction(&json!({"kind":kind,"enabled":true}), true)
                    .unwrap();
            }
            for noise in [false, true] {
                for factor in [-0.7, 0., 1.3] {
                    processing.background_poisson = noise;
                    processing.factor = factor;
                    processing.cache = None;
                    let prepared = processing
                        .series_snapshot(&image, &geometry, &control)
                        .unwrap();
                    let expected = processing.values(&image, 1, &geometry, &control).unwrap();
                    let expected_var = processing.variance().unwrap();
                    let mut actual = image.values.as_ref().clone();
                    let mut variance = vec![];
                    prepared
                        .apply(&mut actual, Some(&mut variance), &control)
                        .unwrap();
                    for (actual, reference) in actual
                        .iter()
                        .zip(expected.iter())
                        .chain(variance.iter().zip(expected_var.iter()))
                    {
                        assert_eq!(
                            actual.to_bits(),
                            reference.to_bits(),
                            "{kind}: {actual} != {reference}"
                        );
                    }
                }
            }
        }
    }
}
fn validate_material(material: &Value) -> Result<(), String> {
    if !material["mode"]
        .as_str()
        .is_some_and(|v| ["manual", "formula"].contains(&v))
    {
        return Err("Choose manual attenuation or formula and density.".into());
    }
    if !material["formula"]
        .as_str()
        .is_some_and(|v| !v.trim().is_empty() && v.len() <= 256)
    {
        return Err("Enter a material formula or name (up to 256 characters).".into());
    }
    if !material["density"]
        .as_f64()
        .is_some_and(|v| v.is_finite() && (0.0..=100_000.).contains(&v))
    {
        return Err("Density must be finite and between 0 and 100000 g/cm³; zero uses the material database.".into());
    }
    Ok(())
}
fn material_mu(material: &Value, wavelength: f64) -> Result<f64, String> {
    validate_material(material)?;
    let energy = (6.626_070_15e-34 * 299_792_458. / 1.602_176_634e-19) / wavelength;
    let (low, high) = xraydb::XrayDb::elam_energy_range();
    if !energy.is_finite() || !(low..=high).contains(&energy) {
        return Err(format!(
            "Material attenuation requires photon energy from {low} to {high} eV; check the calibration wavelength."
        ));
    }
    let db = xraydb::XrayDb::load_uncompressed(include_bytes!("../data/attenuation.bin"))
        .map_err(|e| format!("Could not load embedded X-ray reference data: {e}"))?;
    let density = material["density"].as_f64().unwrap();
    let mu = db
        .material_mu_named_at(
            material["formula"].as_str().unwrap().trim(),
            energy,
            xraydb::CrossSectionKind::Total,
            (density > 0.).then_some(density),
        )
        .map_err(|e| format!("Material attenuation: {e}"))?
        / 10.;
    if !mu.is_finite() || !(0.0..=1e6).contains(&mu) {
        return Err("Calculated material attenuation is outside the supported range.".into());
    }
    Ok(mu)
}
#[cfg(feature = "dioptrin")]
fn absorption(kind: &str, p: &Value, tth: f64, azi: f64) -> f64 {
    let n = |key: &str| p[key].as_f64().unwrap();
    if kind == "plate" || kind == "slab" {
        let thickness = n("thickness");
        let mu = n("absorption_coefficient");
        if thickness == 0.0 || mu == 0.0 {
            return 1.0;
        }
        let tilt = n(&format!("{kind}_tilt")).to_radians();
        let rotation = n(&format!("{kind}_rotation")).to_radians();
        let cosine = (tilt.cos() * tth.cos() + tilt.sin() * tth.sin() * (azi - rotation).cos())
            .abs()
            .max(1e-10);
        let outgoing = mu / cosine;
        if kind == "plate" {
            return (-outgoing * thickness).exp();
        }
        let incident = mu / tilt.cos().abs().max(1e-10);
        let difference = (outgoing - incident).abs() * thickness;
        let ratio = if difference == 0.0 {
            1.0
        } else {
            -(-difference).exp_m1() / difference
        };
        thickness * (-incident.min(outgoing) * thickness).exp() * ratio
    } else if kind == "oiadac" {
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

#[cfg(all(test, feature = "dioptrin"))]
mod tests {
    use super::*;
    #[test]
    fn slab_equal_path_limit_is_stable_and_zero_absorption_matches_reference() {
        let mut p =
            json!({"thickness":0.2,"absorption_coefficient":3.,"slab_tilt":0.,"slab_rotation":0.});
        let expected = 0.2 * (-0.6f64).exp();
        for angle in [0., 1e-10, 1e-8] {
            assert!((absorption("slab", &p, angle, 0.5) - expected).abs() < 1e-15);
        }
        p["absorption_coefficient"] = json!(0.);
        assert_eq!(absorption("slab", &p, 0.5, 0.3), 1.);
        p["absorption_coefficient"] = json!(3.);
        p["thickness"] = json!(0.);
        assert_eq!(absorption("slab", &p, 0.5, 0.3), 1.);
    }
}

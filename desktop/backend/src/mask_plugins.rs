//! Native counterparts of all three bundled Python mask plugins.
//! Spot statistics follow the shipped C accelerator (upper median, one pass).
use crate::{control::Control, geometry::Geometry, protocol::Buffer};
use serde_json::{Value, json};
use std::sync::Arc;

#[derive(Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub(crate) struct State {
    pub enabled: bool,
    pub settings: Value,
}
#[derive(Clone, PartialEq)]
struct Key {
    generation: u64,
    settings: Value,
    geometry: Option<Geometry>,
    user: String,
}
#[derive(Clone)]
struct Cached {
    key: Key,
    mask: Arc<Vec<u8>>,
}
#[derive(Clone)]
struct BinPlan {
    geometry: Geometry,
    shape: [usize; 2],
    count: usize,
    indices: Arc<Vec<usize>>,
}
#[derive(Clone)]
pub(crate) struct Plugins {
    pub states: Vec<State>,
    cache: Vec<Option<Cached>>,
    // The bin plan is geometry dependent, not image dependent.
    bins: Option<BinPlan>,
}
fn catalog() -> Vec<Value> {
    serde_json::from_str(include_str!("mask_plugins.json")).expect("embedded plugin schema")
}
impl Default for Plugins {
    fn default() -> Self {
        Self {
            states: catalog()
                .iter()
                .map(|p| State {
                    enabled: false,
                    settings: p["settings"].clone(),
                })
                .collect(),
            cache: vec![None; 3],
            bins: None,
        }
    }
}
impl Plugins {
    pub fn edit(
        &mut self,
        name: &str,
        enabled: Option<&Value>,
        settings: Option<&Value>,
    ) -> Result<usize, String> {
        let catalog = catalog();
        let index = catalog
            .iter()
            .position(|p| p["name"] == name)
            .ok_or("This optional mask plugin is not installed in the Rust backend.")?;
        if let Some(value) = enabled {
            self.states[index].enabled =
                value.as_bool().ok_or("Plugin enabled must be a boolean.")?;
        }
        if let Some(settings) = settings {
            for (key, value) in settings
                .as_object()
                .ok_or("Plugin settings must be an object.")?
            {
                let spec = &catalog[index]["schema"][key];
                if spec.is_null() {
                    return Err(format!("Unknown plugin setting: {key}."));
                }
                let valid = match spec["type"].as_str().unwrap() {
                    "bool" => value.is_boolean(),
                    "choice" => spec["choices"].as_array().unwrap().contains(value),
                    kind => value.as_f64().is_some_and(|v| {
                        v.is_finite()
                            && v >= spec["min"].as_f64().unwrap()
                            && v <= spec["max"].as_f64().unwrap()
                            && (kind != "int" || v.fract() == 0.0)
                    }),
                };
                if !valid {
                    return Err(format!("Invalid value for {key}."));
                }
                self.states[index].settings[key] = value.clone();
            }
        }
        #[cfg(not(feature = "dioptrin"))]
        if index == 2 && self.states[index].enabled {
            return Err("Spot Mask requires the optional Dioptrin geometry engine; build with --features dioptrin.".into());
        }
        Ok(index)
    }
    pub fn details(&self) -> Value {
        Value::Array(
            catalog()
                .into_iter()
                .enumerate()
                .map(|(i, mut p)| {
                    p["enabled"] = json!(self.states[i].enabled);
                    p["settings"] = self.states[i].settings.clone();
                    p["maskedPixels"] = json!(
                        self.cache[i].as_ref().map_or(0, |c| c
                            .mask
                            .iter()
                            .filter(|&&v| v != 0)
                            .count())
                    );
                    p
                })
                .collect(),
        )
    }
    pub fn mask(&self, i: usize) -> Option<&[u8]> {
        self.cache[i].as_ref().map(|c| c.mask.as_slice())
    }
    pub fn refresh(
        &mut self,
        data: &[f64],
        shape: [usize; 2],
        generation: u64,
        geometry: Option<&Geometry>,
        user: &[u8],
        control: &Control,
    ) -> Result<Vec<u8>, String> {
        let mut combined = user.to_vec();
        let user_id = if self.states[2].enabled {
            Buffer::new(user.to_vec()).id
        } else {
            String::new()
        };
        for i in 0..self.states.len() {
            control.check()?;
            let state = &self.states[i];
            if !state.enabled {
                if self.cache[i]
                    .as_ref()
                    .is_some_and(|c| c.key.generation != generation)
                {
                    self.cache[i] = None;
                }
                continue;
            }
            let key = Key {
                generation,
                settings: state.settings.clone(),
                geometry: if i == 2 { geometry.cloned() } else { None },
                user: if i == 2 {
                    user_id.clone()
                } else {
                    String::new()
                },
            };
            if self.cache[i].as_ref().is_none_or(|c| c.key != key) {
                control.publish(json!({"running":true,"current":i,"total":3,"label":format!("Computing {}",catalog()[i]["name"].as_str().unwrap())}));
                let p = &state.settings;
                let mask = match i {
                    0 => data
                        .iter()
                        .map(|&v| {
                            u8::from(
                                (p["above_enabled"].as_bool().unwrap()
                                    && v > number(p, "above_value"))
                                    || (p["below_enabled"].as_bool().unwrap()
                                        && v < number(p, "below_value")),
                            )
                        })
                        .collect(),
                    1 => cosmic(data, shape, p, control)?,
                    _ => {
                        if let Some(g) = geometry {
                            let count = number(p, "num_bins") as usize;
                            if self.bins.as_ref().is_none_or(|plan| {
                                plan.geometry != *g || plan.shape != shape || plan.count != count
                            }) {
                                self.bins = Some(BinPlan {
                                    geometry: g.clone(),
                                    shape,
                                    count,
                                    indices: Arc::new(bin_indices(g, shape, count)?),
                                });
                            }
                            spot(
                                data,
                                shape,
                                user,
                                &self.bins.as_ref().unwrap().indices,
                                p,
                                control,
                            )?
                        } else {
                            vec![0; data.len()]
                        }
                    }
                };
                control.check()?;
                self.cache[i] = Some(Cached {
                    key,
                    mask: Arc::new(mask),
                });
            }
            for (out, &v) in combined.iter_mut().zip(self.mask(i).unwrap()) {
                *out |= v;
            }
        }
        Ok(combined)
    }
}
fn number(p: &Value, name: &str) -> f64 {
    p[name].as_f64().unwrap()
}

// scipy.ndimage's default half-sample symmetric boundary (including even windows).
fn reflect(i: isize, n: usize) -> usize {
    let r = i.rem_euclid(2 * n as isize) as usize;
    if r < n { r } else { 2 * n - r - 1 }
}
fn uniform_axis(
    data: &[f64],
    shape: [usize; 2],
    window: usize,
    axis: usize,
    control: &Control,
) -> Result<Vec<f64>, String> {
    let [h, w] = shape;
    let (lines, length, stride) = if axis == 0 { (w, h, w) } else { (h, w, 1) };
    let left = window as isize / 2;
    let mut out = vec![0.0; data.len()];
    for line in 0..lines {
        if line % 128 == 0 {
            control.check()?;
        }
        let base = if axis == 0 { line } else { line * w };
        let at = |j| data[base + reflect(j, length) * stride];
        let mut sum = (-left..window as isize - left).map(at).sum::<f64>();
        for j in 0..length {
            out[base + j * stride] = sum / window as f64;
            sum += at(j as isize + window as isize - left) - at(j as isize - left);
        }
    }
    Ok(out)
}
fn uniform(
    data: &[f64],
    shape: [usize; 2],
    window: usize,
    c: &Control,
) -> Result<Vec<f64>, String> {
    uniform_axis(
        &uniform_axis(data, shape, window, 0, c)?,
        shape,
        window,
        1,
        c,
    )
}
fn cosmic(data: &[f64], shape: [usize; 2], p: &Value, c: &Control) -> Result<Vec<u8>, String> {
    let mut image = data.to_vec();
    let mut mask = vec![0; data.len()];
    let window = number(p, "window_size") as usize;
    for iteration in 0..number(p, "iterations") as usize {
        c.check()?;
        c.publish(json!({"running":true,"current":iteration,"total":number(p,"iterations"),"label":"Computing Cosmic Ray Mask"}));
        let positive: Vec<_> = image
            .iter()
            .map(|&v| if v > 0.0 { v } else { 0.0 })
            .collect();
        let counts = uniform(
            &image
                .iter()
                .map(|&v| if v > 0.0 { 1.0 } else { 0.0 })
                .collect::<Vec<_>>(),
            shape,
            window,
            c,
        )?;
        let sums = uniform(&positive, shape, window, c)?;
        let squares = uniform(
            &positive.iter().map(|v| v * v).collect::<Vec<_>>(),
            shape,
            window,
            c,
        )?;
        for i in 0..image.len() {
            let mean = if counts[i] > 0.0 {
                sums[i] / counts[i]
            } else {
                0.0
            };
            let std = if counts[i] > 0.0 {
                (squares[i] / counts[i] - mean * mean).max(0.0).sqrt()
            } else {
                0.0
            };
            let v = image[i];
            let z = if v > 0.0 && std > 0.0 {
                (v - mean) / (std + 1e-10)
            } else {
                0.0
            };
            if v > number(p, "min_intensity")
                && v > 0.0
                && (z > number(p, "sigma") || v > 2.0 * mean)
            {
                mask[i] = 1;
                image[i] = f64::NAN;
            }
        }
    }
    Ok(mask)
}
#[cfg(feature = "dioptrin")]
fn bin_indices(g: &Geometry, shape: [usize; 2], bins: usize) -> Result<Vec<usize>, String> {
    let tth = g.native_geometry(shape)?.calc_tth_all();
    let min = tth.iter().copied().fold(f64::INFINITY, f64::min);
    let max = tth.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let width = (max - min) / bins as f64;
    Ok(tth
        .iter()
        .map(|v| {
            if width > 0.0 {
                (((v - min) / width) as usize).min(bins - 1)
            } else {
                0
            }
        })
        .collect())
}
#[cfg(not(feature = "dioptrin"))]
fn bin_indices(_: &Geometry, _: [usize; 2], _: usize) -> Result<Vec<usize>, String> {
    Err("Spot Mask requires the optional Dioptrin geometry engine.".into())
}
fn upper_median(values: &mut [f64]) -> f64 {
    let mid = values.len() / 2;
    *values.select_nth_unstable_by(mid, f64::total_cmp).1
}
fn spot(
    data: &[f64],
    shape: [usize; 2],
    user: &[u8],
    indices: &[usize],
    p: &Value,
    c: &Control,
) -> Result<Vec<u8>, String> {
    let mut bins = vec![Vec::new(); number(p, "num_bins") as usize];
    for (i, &b) in indices.iter().enumerate() {
        if user[i] == 0 {
            bins[b].push(i);
        }
    }
    let mut mask = vec![0; data.len()];
    for (b, ids) in bins.iter().enumerate() {
        if b % 64 == 0 {
            c.check()?;
        }
        if ids.len() < 3 {
            continue;
        }
        let vals: Vec<_> = ids.iter().map(|&i| data[i]).collect();
        let mean = vals.iter().sum::<f64>() / vals.len() as f64;
        let std = (vals.iter().map(|v| v * v).sum::<f64>() / vals.len() as f64 - mean * mean)
            .max(0.0)
            .sqrt();
        let (center, spread) = if p["method"] == "median" {
            let center = upper_median(&mut vals.clone());
            let mad =
                upper_median(&mut vals.iter().map(|v| (v - center).abs()).collect::<Vec<_>>())
                    * 1.4826;
            (center, if mad <= 0.0 { std } else { mad })
        } else {
            (mean, std)
        };
        if spread <= 0.0 {
            continue;
        }
        let threshold = center + number(p, "esdmul") * spread;
        for &i in ids {
            mask[i] = u8::from(data[i] > threshold);
        }
    }
    let sigma = number(p, "smooth_sigma");
    if sigma > 0.0 {
        smooth(&mask, shape, user, sigma, number(p, "smooth_threshold"), c)
    } else {
        Ok(mask)
    }
}
fn dilate(
    mask: &[u8],
    shape: [usize; 2],
    iterations: usize,
    c: &Control,
) -> Result<Vec<u8>, String> {
    let [h, w] = shape;
    let mut out = mask.to_vec();
    for _ in 0..iterations {
        c.check()?;
        let before = out.clone();
        for row in 0..h {
            for col in 0..w {
                let i = row * w + col;
                out[i] = before[i]
                    | if row > 0 { before[i - w] } else { 0 }
                    | if row + 1 < h { before[i + w] } else { 0 }
                    | if col > 0 { before[i - 1] } else { 0 }
                    | if col + 1 < w { before[i + 1] } else { 0 };
            }
        }
    }
    Ok(out)
}
// SciPy fallback Gaussian: reflect boundaries, truncate=4, float32 between axes.
fn smooth(
    mask: &[u8],
    shape: [usize; 2],
    gap: &[u8],
    sigma: f64,
    threshold: f64,
    c: &Control,
) -> Result<Vec<u8>, String> {
    let gap_active = gap.iter().any(|&v| v != 0);
    let mut input: Vec<f32> = mask.iter().map(|&v| v as f32).collect();
    let reach = if gap_active {
        let deep = dilate(mask, shape, (sigma * 3.0).ceil().max(1.0) as usize, c)?;
        for (i, &v) in gap.iter().enumerate() {
            if v != 0 {
                input[i] = deep[i] as f32;
            }
        }
        Some(dilate(
            mask,
            shape,
            sigma.round_ties_even().max(1.0) as usize,
            c,
        )?)
    } else {
        None
    };
    let radius = (sigma * 4.0 + 0.5).floor() as isize;
    let mut kernel: Vec<_> = (-radius..=radius)
        .map(|x| (-0.5 * (x as f64 / sigma).powi(2)).exp())
        .collect();
    let sum = kernel.iter().sum::<f64>();
    for v in &mut kernel {
        *v /= sum;
    }
    let [h, w] = shape;
    for axis in 0..2 {
        let mut output = vec![0f32; input.len()];
        for row in 0..h {
            if row % 32 == 0 {
                c.check()?;
            }
            for col in 0..w {
                output[row * w + col] = (-radius..=radius)
                    .zip(&kernel)
                    .map(|(d, &k)| {
                        let i = if axis == 0 {
                            reflect(row as isize + d, h) * w + col
                        } else {
                            row * w + reflect(col as isize + d, w)
                        };
                        input[i] as f64 * k
                    })
                    .sum::<f64>() as f32;
            }
        }
        input = output;
    }
    // NumPy casts a scalar to the float32 array's dtype for this comparison.
    Ok(input
        .iter()
        .enumerate()
        .map(|(i, &v)| {
            u8::from(
                v > threshold as f32 && reach.as_ref().is_none_or(|r| r[i] != 0 && gap[i] == 0),
            )
        })
        .collect())
}

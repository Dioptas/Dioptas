//! Native counterparts of all three bundled Python mask plugins.
//! Spot statistics follow the shipped C accelerator (upper median, one pass).
use crate::{control::Control, geometry::Geometry, protocol::Buffer};
use serde_json::{Value, json};
use std::sync::Arc;
#[cfg(test)]
#[path = "mask_plugins_reference.rs"]
mod reference;
#[path = "spatial_masks.rs"]
mod spatial;

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
    groups: Option<Arc<spatial::Groups>>,
}
#[derive(Clone)]
pub(crate) struct Plugins {
    pub states: Vec<State>,
    cache: Vec<Option<Cached>>,
    // The bin plan is geometry dependent, not image dependent.
    bins: Option<BinPlan>,
    fixed_user_id: Option<String>,
    workspace: spatial::Workspace,
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
            fixed_user_id: None,
            workspace: spatial::Workspace::default(),
        }
    }
}
impl Plugins {
    /// Retain only settings and the immutable geometry bins across workers.
    /// Per-frame plugin masks/caches are always private and initially empty.
    pub(crate) fn series_snapshot(
        &self,
        geometry: &Geometry,
        shape: [usize; 2],
        user: &[u8],
    ) -> Result<Self, String> {
        let mut snapshot = self.clone();
        snapshot.cache = vec![None; 3];
        snapshot.fixed_user_id = None;
        if snapshot.states[2].enabled {
            let count = number(&snapshot.states[2].settings, "num_bins") as usize;
            if snapshot
                .bins
                .as_ref()
                .is_none_or(|p| p.geometry != *geometry || p.shape != shape || p.count != count)
            {
                snapshot.bins = Some(BinPlan {
                    geometry: geometry.clone(),
                    shape,
                    count,
                    indices: Arc::new(bin_indices(geometry, shape, count)?),
                    groups: None,
                });
            }
        }
        if snapshot.states[2].enabled {
            let id = Buffer::new(user.to_vec()).id;
            let bins = snapshot.bins.as_mut().unwrap();
            if bins.groups.as_ref().is_none_or(|g| g.user != id) {
                bins.groups = Some(Arc::new(spatial::Groups::new(
                    &bins.indices,
                    user,
                    bins.count,
                    id.clone(),
                )?));
            }
            snapshot.fixed_user_id = Some(id);
        }
        Ok(snapshot)
    }

    /// Account for retained masks, compact row workspaces and the largest
    /// bin's median/MAD scratch; geometry/user bin membership is shared.
    pub(crate) fn series_scratch_bytes(&self, shape: [usize; 2]) -> usize {
        let pixels = shape[0].saturating_mul(shape[1]);
        let mut bytes = pixels.saturating_mul(8);
        if self.states[1].enabled {
            bytes = bytes
                .saturating_add(pixels.saturating_mul(8))
                .saturating_add(shape[1].saturating_mul(48));
        }
        if self.states[2].enabled {
            let largest = self
                .bins
                .as_ref()
                .and_then(|b| b.groups.as_ref())
                .map_or(pixels, |g| g.largest);
            bytes = bytes
                .saturating_add(pixels.saturating_mul(12))
                .saturating_add(largest.saturating_mul(16))
                .saturating_add(shape[1].saturating_mul(12) + 1024);
        }
        bytes
    }
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
        crate::worker_pool::install(|| {
            self.refresh_in_pool(data, shape, generation, geometry, user, control)
        })
    }
    #[allow(clippy::too_many_arguments)]
    fn refresh_in_pool(
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
            self.fixed_user_id
                .clone()
                .unwrap_or_else(|| Buffer::new(user.to_vec()).id)
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
                    0 => {
                        let above = p["above_enabled"].as_bool().unwrap();
                        let below = p["below_enabled"].as_bool().unwrap();
                        let high = number(p, "above_value");
                        let low = number(p, "below_value");
                        data.iter()
                            .map(|&v| u8::from((above && v > high) || (below && v < low)))
                            .collect()
                    }
                    1 => spatial::cosmic(data, shape, p, control, &mut self.workspace)?,
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
                                    groups: None,
                                });
                            }
                            let bins = self.bins.as_mut().unwrap();
                            if bins.groups.as_ref().is_none_or(|g| g.user != user_id) {
                                bins.groups = Some(Arc::new(spatial::Groups::new(
                                    &bins.indices,
                                    user,
                                    count,
                                    user_id.clone(),
                                )?));
                            }
                            spatial::spot(
                                data,
                                shape,
                                user,
                                bins.groups.as_ref().unwrap(),
                                p,
                                control,
                                &mut self.workspace,
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

// scipy.ndimage half-sample symmetric reflection.
fn reflect(i: isize, n: usize) -> usize {
    let r = i.rem_euclid(2 * n as isize) as usize;
    if r < n { r } else { 2 * n - r - 1 }
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

#[cfg(test)]
mod tests {
    use super::*;
    fn settings(i: usize) -> Value {
        catalog()[i]["settings"].clone()
    }
    fn data(shape: [usize; 2]) -> Vec<f64> {
        (0..shape[0] * shape[1])
            .map(|i| {
                if i % 37 == 0 {
                    10000.
                } else if i % 31 == 0 {
                    f64::NAN
                } else if i % 17 == 0 {
                    -7.
                } else {
                    ((i * 997) % 541) as f64 / 13.
                }
            })
            .collect()
    }
    #[test]
    fn streaming_cosmic_matches_frozen_filters_at_edges_and_across_passes() {
        let c = Control::default();
        let mut work = spatial::Workspace::default();
        for shape in [[1, 1], [2, 3], [7, 9], [32, 47], [128, 163]] {
            let values = data(shape);
            for window in [3, 4, 5, 11, 51] {
                for iterations in [1, 2, 4] {
                    let mut p = settings(1);
                    p["window_size"] = json!(window);
                    p["iterations"] = json!(iterations);
                    assert_eq!(
                        spatial::cosmic(&values, shape, &p, &c, &mut work).unwrap(),
                        reference::cosmic(&values, shape, &p, &c).unwrap(),
                        "{shape:?}, window {window}, iterations {iterations}"
                    );
                }
            }
        }
    }
    #[test]
    fn row_major_gaussian_preserves_reflection_float32_rounding_and_gap_reach() {
        let c = Control::default();
        let mut work = spatial::Workspace::default();
        for shape in [[1, 1], [2, 3], [7, 9], [32, 47]] {
            let mask: Vec<_> = (0..shape[0] * shape[1])
                .map(|i| u8::from(i % 7 == 0 || i % 23 == 0))
                .collect();
            for gap_active in [false, true] {
                let gap: Vec<_> = (0..mask.len())
                    .map(|i| u8::from(gap_active && i % 11 == 0))
                    .collect();
                for sigma in [0.1, 0.3, 1., 2.6, 10.] {
                    for threshold in [0.0001, 0.5, 0.9] {
                        assert_eq!(
                            spatial::smooth(&mask, shape, &gap, sigma, threshold, &c, &mut work)
                                .unwrap(),
                            reference::smooth(&mask, shape, &gap, sigma, threshold, &c).unwrap(),
                            "{shape:?}, sigma {sigma}, threshold {threshold}"
                        );
                    }
                }
            }
        }
    }
    #[test]
    fn shared_groups_and_reused_medians_preserve_statistical_masks() {
        let shape = [97, 113];
        let mut values = data(shape);
        let indices: Vec<_> = (0..values.len()).map(|i| (i * 13) % 64).collect();
        let c = Control::default();
        let mut work = spatial::Workspace::default();
        for masked in [false, true] {
            let user: Vec<_> = (0..values.len())
                .map(|i| u8::from(masked && i % 17 == 0))
                .collect();
            let groups = spatial::Groups::new(&indices, &user, 64, "test".into()).unwrap();
            for finite in [false, true] {
                if finite {
                    for v in &mut values {
                        if !v.is_finite() {
                            *v = 0.;
                        }
                    }
                }
                for method in ["mean", "median"] {
                    for sigma in [0., 0.3, 1.] {
                        let mut p = settings(2);
                        p["num_bins"] = json!(64);
                        p["method"] = json!(method);
                        p["smooth_sigma"] = json!(sigma);
                        assert_eq!(
                            spatial::spot(&values, shape, &user, &groups, &p, &c, &mut work)
                                .unwrap(),
                            reference::spot(&values, shape, &user, &indices, &p, &c).unwrap()
                        );
                    }
                }
            }
        }
    }

    #[cfg(feature = "dioptrin")]
    #[test]
    fn spot_membership_invalidates_on_user_geometry_and_bin_edits() {
        let mut plugins = Plugins::default();
        plugins
            .edit(
                "Spot Mask",
                Some(&json!(true)),
                Some(&json!({"num_bins":64})),
            )
            .unwrap();
        let mut geometry = Geometry::default();
        let shape = [32, 47];
        let values = data(shape);
        let mut user = vec![0; values.len()];
        let c = Control::default();
        for stage in 0..4 {
            match stage {
                1 => user
                    .iter_mut()
                    .enumerate()
                    .for_each(|(i, v)| *v = u8::from(i % 7 == 0)),
                2 => geometry.poni1 = 0.001,
                3 => {
                    plugins
                        .edit("Spot Mask", None, Some(&json!({"num_bins":128})))
                        .unwrap();
                }
                _ => {}
            }
            // Keep generation constant: cache invalidation must come from the
            // edited user mask, geometry or bin settings, not a new frame.
            let actual = plugins
                .refresh(&values, shape, 1, Some(&geometry), &user, &c)
                .unwrap();
            let p = &plugins.states[2].settings;
            let indices = bin_indices(&geometry, shape, number(p, "num_bins") as usize).unwrap();
            let mut expected = reference::spot(&values, shape, &user, &indices, p, &c).unwrap();
            for (m, &u) in expected.iter_mut().zip(&user) {
                *m |= u;
            }
            assert_eq!(actual, expected, "edit stage {stage}");
            let snapshot = plugins.series_snapshot(&geometry, shape, &user).unwrap();
            let clone = snapshot.clone();
            assert!(Arc::ptr_eq(
                snapshot.bins.as_ref().unwrap().groups.as_ref().unwrap(),
                clone.bins.as_ref().unwrap().groups.as_ref().unwrap(),
            ));
        }
    }

    #[cfg(feature = "dioptrin")]
    #[test]
    #[ignore = "requires DIOPTAS_EIGER_FILE; full-resolution mask oracle"]
    fn measured_eiger_mask_bits_match_frozen_kernels() {
        use dioptrin_io::{
            PixelBuffer,
            hdf5::{
                Limits,
                raw::{FrameBuffer, RawReader},
            },
        };
        let path = std::path::PathBuf::from(std::env::var("DIOPTAS_EIGER_FILE").unwrap());
        let geometry = Geometry::load(&path.with_extension("poni")).unwrap();
        let reader =
            RawReader::open_snapshot(&path, "entry_0000/instrument/eiger/data", Limits::default())
                .unwrap();
        let [_, h, w] = reader.shape();
        let shape = [h, w];
        let mut decoded = FrameBuffer::default();
        let c = Control::default();
        let p_spot = settings(2);
        let p_cosmic = settings(1);
        let indices = bin_indices(&geometry, shape, number(&p_spot, "num_bins") as usize).unwrap();
        let user = vec![0; h * w];
        let groups = spatial::Groups::new(
            &indices,
            &user,
            number(&p_spot, "num_bins") as usize,
            "oracle".into(),
        )
        .unwrap();
        let mut work = spatial::Workspace::default();
        for frame in [0, 1, 312, 624] {
            reader.read_frame_into(frame, &mut decoded).unwrap();
            let PixelBuffer::U32(pixels) = decoded.pixels().unwrap() else {
                panic!("Expected Eiger uint32");
            };
            let values: Vec<_> = pixels
                .chunks_exact(w)
                .rev()
                .flat_map(|r| r.iter().map(|&v| f64::from(v)))
                .collect();
            assert_eq!(
                spatial::spot(&values, shape, &user, &groups, &p_spot, &c, &mut work).unwrap(),
                reference::spot(&values, shape, &user, &indices, &p_spot, &c).unwrap(),
                "Spot frame {frame}"
            );
            assert_eq!(
                spatial::cosmic(&values, shape, &p_cosmic, &c, &mut work).unwrap(),
                reference::cosmic(&values, shape, &p_cosmic, &c).unwrap(),
                "Cosmic frame {frame}"
            );
            eprintln!("Full-resolution mask bits match: frame {frame}");
        }
    }
}

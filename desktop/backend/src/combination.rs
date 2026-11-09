//! Combine physical detector contributions through Dioptrin's shared-grid API.
use super::*;

#[derive(Clone, Default)]
pub(super) struct State {
    pub patterns: bool,
    pub cakes: bool,
    pub pattern: Option<Arc<Value>>,
    pub cake: Option<Raster>,
    pub cake_values: Option<Arc<Vec<f64>>>,
}

#[cfg(feature = "dioptrin")]
#[derive(PartialEq)]
struct DetectorKey {
    geometry: Geometry,
    shape: [usize; 2],
    mask: Vec<u8>,
    supersampling: usize,
    pyfai: bool,
}
#[cfg(feature = "dioptrin")]
#[derive(PartialEq)]
struct Key {
    detectors: Vec<DetectorKey>,
    unit: String,
    bins: usize,
    cake_bins: usize,
    polarization: f64,
    radial: [f64; 2],
    pattern_azimuth: [f64; 2],
    cake_azimuth: [f64; 2],
}
#[cfg(feature = "dioptrin")]
pub(super) struct Plans {
    key: Key,
    pattern: dioptrin::multi::MultiIntegrator,
    cake: dioptrin::multi::MultiIntegrator,
    compatible: Option<Vec<CompatibleDetector>>,
}

#[cfg(feature = "dioptrin")]
struct CompatibleDetector {
    engine: dioptrin::integration::Integrator,
    pattern: dioptrin::lut::Lut1d,
    normalization: Vec<f64>,
    absolute: f64,
    pyfai: bool,
}

#[cfg(feature = "dioptrin")]
type DetectorImage = (Arc<Vec<f64>>, [usize; 2], Arc<Vec<f64>>);

#[cfg(feature = "dioptrin")]
impl Plans {
    fn compatible_result(
        &self,
        images: &[DetectorImage],
        pattern: bool,
        errors: bool,
    ) -> Result<dioptrin::multi::Multi2dResult, String> {
        use dioptrin::{
            integration::{IntegrationGrid2d, PixelSplitMode},
            lut::{IntermediateResult2d, integrate1d_raw, integrate1d_raw_with_variance},
        };
        let count = if pattern { 1 } else { self.key.cake_bins };
        let angles = if pattern {
            self.key.pattern_azimuth
        } else {
            self.key.cake_azimuth
        };
        let grid = IntegrationGrid2d::new(
            self.key.bins,
            count,
            (self.key.radial[0], self.key.radial[1]),
            (angles[0], angles[1]),
        )?;
        let size = self.key.bins * count;
        let mut total = IntermediateResult2d {
            sum_signal: vec![0.; size],
            sum_norm: vec![0.; size],
            sum_variance: errors.then(|| vec![0.; size]),
            count: vec![0.; size],
            n_radial: self.key.bins,
            n_azimuthal: count,
        };
        for (detector, (data, shape, variance)) in
            self.compatible.as_ref().unwrap().iter().zip(images)
        {
            let raw = if pattern {
                let mask = detector.engine.mask().map(|m| m.data.as_slice());
                let r = if errors {
                    integrate1d_raw_with_variance(
                        data,
                        variance,
                        &detector.pattern,
                        mask,
                        &detector.normalization,
                    )
                } else {
                    integrate1d_raw(data, &detector.pattern, mask, &detector.normalization)
                };
                IntermediateResult2d {
                    sum_signal: r.sum_signal,
                    sum_norm: r.sum_norm,
                    sum_variance: r.sum_variance,
                    count: r.count,
                    n_radial: self.key.bins,
                    n_azimuthal: 1,
                }
            } else {
                let grid = grid.with_pixel_split_mode(if detector.pyfai {
                    PixelSplitMode::PyfaiHistogram
                } else {
                    PixelSplitMode::Fractional
                });
                if errors {
                    detector
                        .engine
                        .integrate2d_raw_on_grid_with_variances_from_slice(
                            data, variance, shape[0], shape[1], &grid,
                        )?
                } else {
                    detector.engine.integrate2d_raw_on_grid_from_slice(
                        data, shape[0], shape[1], &grid, false,
                    )?
                }
            };
            for bin in 0..size {
                total.sum_signal[bin] += raw.sum_signal[bin];
                total.sum_norm[bin] += raw.sum_norm[bin] * detector.absolute;
                total.count[bin] += raw.count[bin];
                if let (Some(total), Some(v)) = (&mut total.sum_variance, &raw.sum_variance) {
                    total[bin] += v[bin];
                }
            }
        }
        let intensity = total
            .sum_signal
            .iter()
            .zip(&total.sum_norm)
            .map(|(s, n)| if *n == 0. { 0. } else { s / n })
            .collect();
        let sigma = total.sum_variance.as_ref().map(|v| {
            v.iter()
                .zip(&total.sum_norm)
                .map(|(v, n)| if *n == 0. { 0. } else { v.max(0.).sqrt() / n })
                .collect()
        });
        Ok(dioptrin::multi::Multi2dResult {
            radial: grid.radial_centers(),
            azimuthal: grid.azimuthal_centers(),
            intensity,
            errors: sigma,
            raw: total,
        })
    }
}

impl Session {
    pub(super) fn displayed_cake(&self) -> Option<&Raster> {
        if self.combination.cakes {
            self.combination.cake.as_ref()
        } else {
            self.cake.as_ref()
        }
    }
    pub(super) fn displayed_cake_values(&self) -> Option<&Arc<Vec<f64>>> {
        if self.combination.cakes {
            self.combination.cake_values.as_ref()
        } else {
            self.cake_values.as_ref()
        }
    }
    fn combination_configurations(&self) -> Vec<checkpoint::Checkpoint> {
        self.project
            .configurations
            .iter()
            .enumerate()
            .map(|(index, c)| {
                if index == self.project.selected {
                    self.checkpoint()
                } else {
                    c.as_ref()
                        .expect("owned inactive configuration")
                        .state
                        .clone()
                }
            })
            .collect()
    }

    pub(super) fn combination_state(&self) -> Value {
        let configurations = self.combination_configurations();
        let missing: Vec<_> = configurations
            .iter()
            .enumerate()
            .filter(|(_, c)| c.image.is_none() || !c.settings.calibrated)
            .map(|(i, _)| (i + 1).to_string())
            .collect();
        let reason = if configurations.len() < 2 {
            Some("Add another detector configuration to combine results.".to_string())
        } else if !missing.is_empty() {
            Some(format!(
                "Load an image and calibration for configuration {}.",
                missing.join(", ")
            ))
        } else {
            None
        };
        json!({"patterns":self.combination.patterns,"cakes":self.combination.cakes,
            "ready":reason.is_none(),"reason":reason,"factor":self.processing.factor,
            "configurations":configurations.iter().enumerate().map(|(i,c)| json!({
                "index":i,"imageName":c.image.as_ref().and_then(|im|im.path.file_name()).map(|n|n.to_string_lossy()),
                "calibrated":c.settings.calibrated,"factor":c.processing.factor})).collect::<Vec<_>>(),
            "backends":{"pattern":"Dioptrin · native Rust","cake":"Dioptrin · native Rust"}})
    }

    pub(super) fn combination_command(
        &mut self,
        action: &str,
        args: &Value,
    ) -> Result<Option<Reply>, String> {
        match action {
            "configuration_select" => self
                .dispatch(
                    "configuration",
                    &json!({"operation":"select","index":args["index"]}),
                )
                .map(Some),
            "combination_settings" => {
                check_keys(args, &["patterns", "cakes", "factor"])?;
                if let Some(value) = args.get("factor") {
                    self.processing.factor = finite(value, "Detector factor", -1e12, 1e12)?;
                    self.processed_values = None;
                    self.calculate(false)?;
                }
                if let Some(value) = args.get("patterns") {
                    self.combination.patterns = boolean(value, "Combine patterns")?;
                }
                if let Some(value) = args.get("cakes") {
                    self.combination.cakes = boolean(value, "Combine cakes")?;
                }
                if (self.combination.patterns || self.combination.cakes)
                    && self.combination_state()["ready"] != true
                {
                    return Err(self.combination_state()["reason"]
                        .as_str()
                        .unwrap_or("Detector setup is incomplete.")
                        .into());
                }
                self.revision += 1;
                Ok(Some(self.snapshot(true)))
            }
            "save_combined_pattern" => {
                check_keys(args, &["path", "suggested_name"])?;
                let displayed = self
                    .combination
                    .pattern
                    .as_ref()
                    .filter(|_| self.combination.patterns)
                    .ok_or("Enable combined patterns before saving.")?;
                let mut curve = crate::pattern::Curve::from_json(displayed)?;
                curve.sigma = displayed["sigma"]
                    .as_array()
                    .map(|a| Arc::new(a.iter().filter_map(Value::as_f64).collect()));
                file_workflow::export_curve(
                    path(args)?,
                    &curve,
                    &self.settings.unit,
                    self.settings.geometry.wavelength,
                )?;
                Ok(Some(Reply::metadata(
                    json!({"ok":true,"savedPath":args["path"]}),
                )))
            }
            _ => Ok(None),
        }
    }

    pub(super) fn update_combination_reply(
        &mut self,
        reply: &mut Reply,
        action: &str,
        args: &Value,
    ) -> Result<(), String> {
        if !reply.result["state"].is_object() {
            return Ok(());
        }
        let active = self.combination.patterns || self.combination.cakes;
        if active && args["defer_integration"] == true {
            self.combination.pattern = None;
            self.combination.cake = None;
            self.combination.cake_values = None;
        } else if active
            && self.combination_state()["ready"] == true
            && !matches!(
                action,
                "state"
                    | "display_products"
                    | "pixel"
                    | "image_levels"
                    | "integration_phase_state"
                    | "integration_phase_guides"
                    | "map_display"
                    | "map_poll"
            )
        {
            #[cfg(feature = "dioptrin")]
            self.refresh_combination()?;
            #[cfg(not(feature = "dioptrin"))]
            return Err("Detector combination requires the native Dioptrin engine.".into());
        } else if active && self.combination_state()["ready"] != true {
            self.combination.pattern = None;
            self.combination.cake = None;
            self.combination.cake_values = None;
        }
        reply.result["state"]["combination"] = self.combination_state();
        if self.combination.patterns && reply.result.get("pattern").is_some() {
            let pattern = self.combination.pattern.as_ref().map(|combined| {
                let mut p = combined.as_ref().clone();
                if let Some(current) = self.pattern.as_ref() {
                    for key in ["curves", "phaseLines"] {
                        p[key] = current[key].clone();
                    }
                }
                p
            });
            reply.result["pattern"] = json!(pattern);
        }
        if self.combination.cakes
            && self.control.cake_requested()
            && reply.result.get("cake").is_some()
        {
            reply.result["cake"] = self
                .combination
                .cake
                .as_ref()
                .map(|r| r.metadata.clone())
                .unwrap_or(Value::Null);
            if let Some(raster) = &self.combination.cake {
                reply.buffers.push(raster.buffer.clone());
            }
        }
        Ok(())
    }

    #[cfg(feature = "dioptrin")]
    pub(super) fn refresh_combination(&mut self) -> Result<(), String> {
        use dioptrin::{
            integration::{IntegrationMethod, Integrator, RadialUnit},
            mask::Mask,
            multi::{Multi2dOptions, MultiIntegrator, MultiNormalization},
        };
        let unit = match self.settings.unit.as_str() {
            "q_A^-1" => RadialUnit::QAngstrom,
            "q_nm^-1" => RadialUnit::QNm,
            _ => RadialUnit::TthDeg,
        };
        let mut images = vec![];
        let mut detectors = vec![];
        let (mut rmin, mut rmax, mut amin, mut amax) = (
            f64::INFINITY,
            f64::NEG_INFINITY,
            f64::INFINITY,
            f64::NEG_INFINITY,
        );
        for configuration in self.combination_configurations() {
            self.control.check()?;
            let mut owner = Session::new(self.root.clone());
            owner.restore_checkpoint(configuration);
            owner.control = self.control.clone();
            if !owner.settings.solid_angle {
                return Err("Combined detector results require solid-angle correction.".into());
            }
            owner.prepare_processing()?;
            owner.refresh_masks(&self.control.clone())?;
            let image = owner
                .image
                .as_ref()
                .ok_or("Load all detector images first.")?;
            let g = owner.settings.geometry.native_geometry(image.shape)?;
            for r in unit.convert_from_tth(&g.calc_tth_all(), g.poni.wavelength) {
                rmin = rmin.min(r);
                rmax = rmax.max(r);
            }
            for a in g.calc_azimuth_all() {
                amin = amin.min(a);
                amax = amax.max(a);
            }
            let variance = owner
                .processing
                .variance()
                .or_else(|| image.input_variance())
                .unwrap_or_else(|| Arc::new(image.values.iter().map(|v| v.max(0.0)).collect()));
            images.push((owner.scientific_values(), image.shape, variance));
            detectors.push(DetectorKey {
                geometry: owner.settings.geometry.clone(),
                shape: image.shape,
                mask: owner.integration_mask(image.shape),
                supersampling: owner.settings.supersampling,
                pyfai: owner.settings.pyfai_splitting,
            });
        }
        let radial = [rmin.max(0.), rmax * (1. + f32::EPSILON as f64)];
        if !radial.iter().all(|v| v.is_finite()) || radial[0] >= radial[1] {
            return Err("Combined detector radial coverage is invalid.".into());
        }
        let union = [
            amin,
            (amax + amax.abs() * f32::EPSILON as f64).min(std::f64::consts::PI),
        ];
        let key = Key {
            detectors,
            unit: self.settings.unit.clone(),
            bins: if self.settings.automatic_binning {
                self.automatic_bins()
            } else {
                self.settings.bins
            },
            cake_bins: self.settings.cake_bins,
            polarization: self.settings.polarization,
            radial,
            pattern_azimuth: self
                .settings
                .azimuth
                .map_or(union, |r| crate::sector::angular(Some(r))),
            cake_azimuth: self
                .settings
                .cake_azimuth
                .map_or(union, |r| crate::sector::angular(Some(r))),
        };
        if self.combination_plans.as_ref().is_none_or(|p| p.key != key) {
            let make = || -> Result<MultiIntegrator, String> {
                let integrators = key
                    .detectors
                    .iter()
                    .map(
                        |DetectorKey {
                             geometry: g,
                             shape,
                             mask,
                             supersampling: ss,
                             ..
                         }| {
                            let mut integrator = Integrator::new(g.native_geometry(*shape)?)
                                .with_method(if *ss > 1 {
                                    IntegrationMethod::Supersampled { n_ss: *ss }
                                } else {
                                    IntegrationMethod::PixelSplit
                                })
                                .with_radial_unit(unit)
                                .with_radial_range(radial[0], radial[1])
                                .with_polarization_factor(key.polarization);
                            integrator.set_mask(Mask {
                                data: mask.clone(),
                                dim1: shape[0],
                                dim2: shape[1],
                            });
                            Ok(integrator)
                        },
                    )
                    .collect::<Result<Vec<_>, String>>()?;
                MultiIntegrator::try_new(integrators)
            };
            let compatible = if key.detectors.iter().any(|d| d.pyfai) {
                Some(
                    key.detectors
                        .iter()
                        .map(
                            |DetectorKey {
                                 geometry: parameters,
                                 shape,
                                 mask,
                                 supersampling: ss,
                                 pyfai,
                             }| {
                                let g = parameters.native_geometry(*shape)?;
                                let tth = g.calc_tth_all();
                                let azimuth = g.calc_azimuth_all();
                                let polarization =
                                    g.calc_polarization(key.polarization, &tth, &azimuth);
                                let normalization = g
                                    .calc_solid_angle()
                                    .into_iter()
                                    .zip(polarization)
                                    .map(|(s, p)| s * p)
                                    .collect();
                                let angles = Some([
                                    key.pattern_azimuth[0].to_degrees(),
                                    key.pattern_azimuth[1].to_degrees(),
                                ]);
                                let pattern = if *pyfai {
                                    crate::pyfai_splitting::build1d(
                                        &g,
                                        unit,
                                        key.bins,
                                        angles,
                                        Some(radial),
                                    )?
                                } else {
                                    crate::sector::collapse(crate::sector::build_on_range(
                                        &g,
                                        unit,
                                        key.bins,
                                        1,
                                        angles,
                                        *ss,
                                        Some(radial),
                                    )?)
                                };
                                let absolute = (g.poni.pixel1 / g.poni.distance)
                                    * (g.poni.pixel2 / g.poni.distance);
                                let mut engine = Integrator::new(g)
                                    .with_method(if *ss > 1 {
                                        IntegrationMethod::Supersampled { n_ss: *ss }
                                    } else {
                                        IntegrationMethod::PixelSplit
                                    })
                                    .with_radial_unit(unit)
                                    .with_polarization_factor(key.polarization);
                                engine.set_mask(Mask {
                                    data: mask.clone(),
                                    dim1: shape[0],
                                    dim2: shape[1],
                                });
                                Ok(CompatibleDetector {
                                    engine,
                                    pattern,
                                    normalization,
                                    absolute,
                                    pyfai: *pyfai,
                                })
                            },
                        )
                        .collect::<Result<Vec<_>, String>>()?,
                )
            } else {
                None
            };
            self.combination_plans = Some(Plans {
                pattern: make()?,
                cake: make()?,
                compatible,
                key,
            });
        }
        let plans = self.combination_plans.as_ref().unwrap();
        let slices: Vec<_> = images
            .iter()
            .map(|(values, shape, _)| (values.as_slice(), shape[0], shape[1]))
            .collect();
        let options = |range: [f64; 2]| Multi2dOptions {
            azimuthal_range: (range[0], range[1]),
            normalization: MultiNormalization::Absolute,
            errors: self.settings.errors,
            normalization_factors: None,
        };
        let variances: Vec<_> = images.iter().map(|(_, _, v)| v.as_slice()).collect();
        let integrate = |engine: &MultiIntegrator, pattern, azimuth_bins, range| {
            if plans.compatible.is_some() {
                return plans.compatible_result(&images, pattern, self.settings.errors);
            }
            if self.settings.errors {
                engine.integrate2d_from_slices_with_variances(
                    &slices,
                    &variances,
                    plans.key.bins,
                    azimuth_bins,
                    &options(range),
                )
            } else {
                engine.integrate2d_from_slices(
                    &slices,
                    plans.key.bins,
                    azimuth_bins,
                    &options(range),
                )
            }
        };
        if self.combination.patterns {
            let mut p = integrate(&plans.pattern, true, 1, plans.key.pattern_azimuth)?;
            let mut x: Vec<_> = p
                .radial
                .iter()
                .map(|v| {
                    if self.settings.unit == "d_A" {
                        crate::pattern::convert_coordinate(
                            *v,
                            "2th_deg",
                            "d_A",
                            self.settings.geometry.wavelength,
                        )
                    } else {
                        *v
                    }
                })
                .collect();
            if self.settings.trim_zeros {
                crate::integration::trim_zero_edges(
                    &mut x,
                    &mut p.intensity,
                    p.errors.as_mut(),
                    None,
                );
            }
            self.combination.pattern = Some(Arc::new(
                json!({"x":x,"y":p.intensity,"unit":self.settings.unit,"sigma":p.errors}),
            ));
        } else {
            self.combination.pattern = None;
        }
        if self.combination.cakes && self.control.cake_requested() {
            let p = integrate(
                &plans.cake,
                false,
                plans.key.cake_bins,
                plans.key.cake_azimuth,
            )?;
            let mut raster = Raster::image(&p.intensity, [plans.key.cake_bins, plans.key.bins]);
            raster.metadata["radialRange"] = json!([p.radial[0], p.radial[p.radial.len() - 1]]);
            raster.metadata["azimuthRange"] = json!([
                p.azimuthal[0].to_degrees(),
                p.azimuthal[p.azimuthal.len() - 1].to_degrees()
            ]);
            raster.metadata["unit"] = json!(if self.settings.unit == "d_A" {
                "2th_deg"
            } else {
                &self.settings.unit
            });
            self.combination.cake = Some(raster);
            self.combination.cake_values = Some(Arc::new(p.intensity));
        } else {
            self.combination.cake = None;
            self.combination.cake_values = None;
        }
        Ok(())
    }
}

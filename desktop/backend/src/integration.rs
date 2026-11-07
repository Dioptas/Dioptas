//! Persistent, worker-owned integration plans. No Python fallback.
use crate::{
    control::Control,
    display::Raster,
    geometry::Geometry as Parameters,
    image::{CombinedSource, Image},
};
use dioptrin::{
    integration::{
        Fixed1dPlan, InputOrder, IntegrationMethod, Integrator, MaskMode, RadialUnit, SparseLayout,
    },
    mask::Mask,
};
use dioptrin_io::{
    PixelBuffer, PixelType,
    hdf5::{
        Limits,
        raw::{ParallelBlockBuffer, PipelineOptions, PixelBlock, RawReader},
    },
};
use serde_json::{Value, json};
use std::sync::Arc;

pub struct Products {
    pub pattern: Value,
    pub cake: Raster,
    pub cake_values: Vec<f64>,
    pub sigma: Option<Vec<f64>>,
}
#[derive(Clone, PartialEq)]
pub struct Options {
    pub bins: usize,
    pub automatic_bins: bool,
    pub cake_bins: usize,
    pub unit: String,
    pub polarization: f64,
    pub errors: bool,
    pub supersampling: usize,
    pub solid_angle: bool,
    pub azimuth: Option<[f64; 2]>,
    pub cake_azimuth: Option<[f64; 2]>,
    pub trim: bool,
    pub spread: bool,
    pub dynamic_mask: bool,
    pub csc: bool,
}
#[derive(Clone, PartialEq)]
struct Key {
    shape: [usize; 2],
    geometry: Parameters,
    bins: usize,
    angular_bins: usize,
    unit: String,
    polarization: f64,
    supersampling: usize,
    mask: Vec<u8>,
    dynamic: bool,
    csc: bool,
    solid: bool,
    azimuth: Option<[f64; 2]>,
}
struct Plan {
    key: Key,
    engine: Integrator,
    fixed: Option<Arc<Fixed1dPlan>>,
    general_1d: Option<dioptrin::lut::Lut1d>,
    general_2d: Option<crate::sector::Grid>,
    normalization: Option<Vec<f64>>,
    radial: Option<[f64; 2]>,
}
struct RawSource {
    source: CombinedSource,
    reader: RawReader,
    buffer: ParallelBlockBuffer,
}
#[derive(Clone)]
pub struct Prepared {
    key: Key,
    x: Vec<f64>,
    y: Vec<f64>,
    sigma: Option<Vec<f64>>,
}
#[derive(Default)]
pub struct Engine {
    pattern: Option<Plan>,
    cake: Option<Plan>,
    raw: Option<RawSource>,
    pattern_builds: u64,
    cake_builds: u64,
    combined_decodes: u64,
    prepared_hits: u64,
    resident_calls: u64,
}
fn unit(value: &str) -> RadialUnit {
    match value {
        "q_A^-1" => RadialUnit::QAngstrom,
        "q_nm^-1" => RadialUnit::QNm,
        _ => RadialUnit::TthDeg,
    }
}
fn key(shape: [usize; 2], p: &Parameters, m: &[u8], o: &Options, cake: bool) -> Key {
    Key {
        shape,
        geometry: p.clone(),
        bins: o.bins,
        angular_bins: if cake { o.cake_bins } else { 0 },
        unit: if cake || o.unit == "d_A" {
            "2th_deg".into()
        } else {
            o.unit.clone()
        },
        polarization: o.polarization,
        supersampling: o.supersampling,
        mask: if o.dynamic_mask { vec![] } else { m.to_vec() },
        dynamic: o.dynamic_mask,
        csc: o.csc,
        solid: o.solid_angle,
        azimuth: if cake { o.cake_azimuth } else { o.azimuth },
    }
}
impl Plan {
    fn new(key: Key) -> Result<Self, String> {
        let [h, w] = key.shape;
        let mut engine = Integrator::new(key.geometry.native_geometry([h, w])?)
            .with_method(if key.supersampling > 1 {
                IntegrationMethod::Supersampled {
                    n_ss: key.supersampling,
                }
            } else {
                IntegrationMethod::PixelSplit
            })
            .with_fast_math(true)
            .with_sparse_layout(if key.csc {
                SparseLayout::Csc
            } else {
                SparseLayout::Csr
            })
            .with_mask_mode(if key.dynamic {
                MaskMode::Dynamic
            } else {
                MaskMode::Fixed
            })
            .with_radial_unit(unit(&key.unit))
            .with_polarization_factor(key.polarization);
        engine.set_mask(Mask {
            data: if key.dynamic {
                vec![0; h * w]
            } else {
                key.mask.clone()
            },
            dim1: h,
            dim2: w,
        });
        Ok(Self {
            key,
            engine,
            fixed: None,
            general_1d: None,
            general_2d: None,
            normalization: None,
            radial: None,
        })
    }
    fn fixed(&mut self) -> Result<Arc<Fixed1dPlan>, String> {
        if self.fixed.is_none() {
            self.fixed = Some(Arc::new(
                self.engine
                    .prepare_fixed1d((self.key.shape[0], self.key.shape[1]), self.key.bins)?,
            ));
        }
        Ok(self.fixed.as_ref().unwrap().clone())
    }
    fn prepare_normalization(&mut self) {
        if self.normalization.is_some() {
            return;
        }
        let g = self.engine.geometry();
        let tth = g.calc_tth_all();
        let azi = g.calc_azimuth_all();
        let pol = g.calc_polarization(self.key.polarization, &tth, &azi);
        let mut norm = if self.key.solid {
            g.calc_solid_angle()
        } else {
            vec![1.0; g.size()]
        };
        for (n, p) in norm.iter_mut().zip(pol) {
            *n *= p;
        }
        self.normalization = Some(norm);
    }
    fn general_pattern(
        &mut self,
        data: &[f64],
        mask: &[u8],
        o: &Options,
    ) -> Result<dioptrin::lut::AzimuthalIntegrationResult, String> {
        self.prepare_normalization();
        if self.general_1d.is_none() {
            let g = self.engine.geometry();
            let u = unit(&self.key.unit);
            self.general_1d = Some(if o.azimuth.is_some() {
                crate::sector::collapse(crate::sector::build(
                    g,
                    u,
                    o.bins,
                    1,
                    o.azimuth,
                    o.supersampling,
                )?)
            } else {
                let radial = u.convert_from_tth(&g.calc_tth_all(), g.poni.wavelength);
                if o.supersampling > 1 {
                    dioptrin::lut::build_lut1d_ss_csr(g, &radial, o.bins, o.supersampling, u)
                } else {
                    dioptrin::lut::build_lut1d_ps_csr(g, &radial, o.bins, u)
                }
            });
        }
        let lut = self.general_1d.as_ref().unwrap();
        let norm = self.normalization.as_ref().unwrap();
        let variance = o
            .errors
            .then(|| data.iter().map(|&v| v.max(0.0)).collect::<Vec<_>>());
        if o.spread {
            Ok(dioptrin::lut::integrate1d_with_azimuthal_std(
                data,
                lut,
                Some(mask),
                norm,
                variance.as_deref(),
            ))
        } else {
            let (x, y, e) = if let Some(v) = variance {
                let (x, y, e) =
                    dioptrin::lut::integrate1d_with_errors(data, &v, lut, Some(mask), norm);
                (x, y, Some(e))
            } else {
                let (x, y) = dioptrin::lut::integrate1d(data, lut, Some(mask), norm);
                (x, y, None)
            };
            Ok(dioptrin::lut::AzimuthalIntegrationResult {
                radial: x,
                intensity: y,
                errors: e,
                azimuthal_std: vec![],
            })
        }
    }
}
impl Engine {
    pub fn diagnostics(&self) -> Value {
        json!({"patternPlanBuilds":self.pattern_builds,"cakePlanBuilds":self.cake_builds,"combinedDecodes":self.combined_decodes,"preparedHits":self.prepared_hits,"residentIntegrations":self.resident_calls})
    }
    fn pattern_plan(&mut self, k: Key) -> Result<&mut Plan, String> {
        if self.pattern.as_ref().is_none_or(|p| p.key != k) {
            self.pattern = Some(Plan::new(k)?);
            self.pattern_builds += 1;
        }
        Ok(self.pattern.as_mut().unwrap())
    }
    /// Admission is metadata-only. Unsupported layouts decode through ordinary
    /// native input once; admitted-source failures never become silent fallbacks.
    pub fn load_combined(
        &mut self,
        image: &mut Image,
        index: usize,
        p: &Parameters,
        mask: &[u8],
        options: &Options,
        c: &Control,
    ) -> Result<Option<Prepared>, String> {
        if std::env::var("DIOPTAS_COMBINED_HDF5").as_deref() == Ok("0") {
            return Ok(None);
        }
        let mut o = options.clone();
        if o.dynamic_mask || !o.csc || !o.solid_angle || o.azimuth.is_some() || o.spread {
            return Ok(None);
        }
        let Some(mut source) = image.combined_source(index)? else {
            return Ok(None);
        };
        if source.shape.contains(&0)
            || source.shape[0]
                .checked_mul(source.shape[1])
                .is_none_or(|n| n > 64 * 1024 * 1024)
        {
            return Err(
                "Detector plane exceeds the native session's 64-million-pixel bound.".into(),
            );
        }
        if o.automatic_bins {
            o.bins = p.automatic_bins(source.shape);
        }
        if !mask.is_empty() && mask.len() != source.shape[0] * source.shape[1] {
            return Ok(None);
        }
        c.check()?;
        source.frame = 0;
        if self.raw.as_ref().is_none_or(|r| r.source != source) {
            let reader =
                match RawReader::open_snapshot(&source.path, &source.dataset, Limits::default()) {
                    Ok(reader) => reader,
                    Err(_) => {
                        image.check_sources()?;
                        return Ok(None);
                    }
                };
            self.raw = Some(RawSource {
                source: source.clone(),
                reader,
                buffer: ParallelBlockBuffer::default(),
            });
        }
        let m = if mask.is_empty() {
            vec![0; source.shape[0] * source.shape[1]]
        } else {
            mask.to_vec()
        };
        let k = key(source.shape, p, &m, &o, false);
        let plan = self.pattern_plan(k.clone())?.fixed()?;
        let raw = self.raw.as_mut().unwrap();
        let kind = raw.reader.pixel_type();
        let frame = image
            .combined_source(index)?
            .ok_or("Combined source metadata disappeared.")?
            .frame;
        let workers = std::env::var("DIOPTAS_INTEGRATION_THREADS")
            .ok()
            .and_then(|v| v.parse::<usize>().ok())
            .unwrap_or(8)
            .clamp(1, 256);
        let states = raw
            .reader
            .fold_frame_blocks(
                frame,
                &mut raw.buffer,
                PipelineOptions {
                    workers,
                    memory_bytes: 256 * 1024 * 1024,
                },
                |_, range| {
                    c.check().map_err(dioptrin_io::hdf5::Error::from)?;
                    let mut worker = plan.worker(o.errors, InputOrder::FlipVertical);
                    worker
                        .begin_range(range.clone())
                        .map_err(dioptrin_io::hdf5::Error::from)?;
                    let pixels = match kind {
                        PixelType::U16 => PixelBuffer::U16(Vec::with_capacity(range.len())),
                        PixelType::U32 => PixelBuffer::U32(Vec::with_capacity(range.len())),
                        _ => unreachable!(),
                    };
                    Ok((worker, pixels))
                },
                |(worker, pixels), offset, block| {
                    c.check().map_err(dioptrin_io::hdf5::Error::from)?;
                    match (pixels, block) {
                        (PixelBuffer::U16(out), PixelBlock::U16(v)) => {
                            out.extend_from_slice(v);
                            worker.push_u16_block(offset, v)
                        }
                        (PixelBuffer::U32(out), PixelBlock::U32(v)) => {
                            out.extend_from_slice(v);
                            worker.push_u32_block(offset, v)
                        }
                        _ => unreachable!(),
                    }
                    .map_err(Into::into)
                },
            )
            .map_err(|e| e.to_string())?;
        let mut pixels = match kind {
            PixelType::U16 => {
                PixelBuffer::U16(Vec::with_capacity(source.shape[0] * source.shape[1]))
            }
            PixelType::U32 => {
                PixelBuffer::U32(Vec::with_capacity(source.shape[0] * source.shape[1]))
            }
            _ => unreachable!(),
        };
        let mut partials = Vec::with_capacity(states.len());
        for (worker, part) in states {
            match (&mut pixels, part) {
                (PixelBuffer::U16(out), PixelBuffer::U16(v)) => out.extend(v),
                (PixelBuffer::U32(out), PixelBuffer::U32(v)) => out.extend(v),
                _ => unreachable!(),
            };
            partials.push(worker);
        }
        let result = plan.finish_ranges(&mut partials)?;
        image.check_sources()?;
        c.check()?;
        image.publish_combined(index, source.shape, pixels)?;
        self.combined_decodes += 1;
        Ok(Some(Prepared {
            key: k,
            x: result.radial,
            y: result.intensity,
            sigma: result.errors,
        }))
    }
    pub fn integrate_pattern(
        &mut self,
        data: &[f64],
        shape: [usize; 2],
        p: &Parameters,
        mask: &[u8],
        o: &Options,
        prepared: Option<Prepared>,
    ) -> Result<(Value, Option<Vec<f64>>), String> {
        let k = key(shape, p, mask, o, false);
        let prepared =
            prepared.filter(|r| r.key == k && (!o.errors || r.sigma.is_some()) && !o.spread);
        let (mut x, mut y, mut sigma, mut spread) = if let Some(r) = prepared {
            self.prepared_hits += 1;
            (r.x, r.y, r.sigma, None)
        } else {
            self.resident_calls += 1;
            let plan = self.pattern_plan(k)?;
            if o.dynamic_mask && plan.engine.mask().is_none_or(|m| m.data != mask) {
                plan.engine.set_mask(Mask {
                    data: mask.to_vec(),
                    dim1: shape[0],
                    dim2: shape[1],
                });
            }
            if !o.solid_angle || o.azimuth.is_some() {
                let r = plan.general_pattern(data, mask, o)?;
                (
                    r.radial,
                    r.intensity,
                    r.errors,
                    o.spread.then_some(r.azimuthal_std),
                )
            } else if o.spread {
                let r = plan.engine.integrate1d_with_azimuthal_std_from_slice(
                    data, shape[0], shape[1], o.bins, o.errors,
                );
                (r.radial, r.intensity, r.errors, Some(r.azimuthal_std))
            } else if !o.dynamic_mask && o.csc {
                let r = plan.fixed()?.integrate_frame(data, o.errors)?;
                (r.radial, r.intensity, r.errors, None)
            } else if o.errors {
                let (x, y, e) = plan
                    .engine
                    .integrate1d_with_errors_from_slice(data, shape[0], shape[1], o.bins);
                (x, y, Some(e), None)
            } else {
                let (x, y) = plan
                    .engine
                    .integrate1d_from_slice(data, shape[0], shape[1], o.bins);
                (x, y, None, None)
            }
        };
        if o.unit == "d_A" {
            for v in &mut x {
                *v = p.wavelength * 1e10 / (2.0 * (v.to_radians() / 2.0).sin());
            }
        }
        if o.trim && y.iter().any(|v| *v != 0.0) {
            let n = y.iter().rposition(|v| *v != 0.0).unwrap() + 1;
            x.truncate(n);
            y.truncate(n);
            if let Some(s) = &mut sigma {
                s.truncate(n);
            }
            if let Some(s) = &mut spread {
                s.truncate(n);
            }
        }
        Ok((
            json!({"x":x,"y":y,"unit":o.unit,"azimuthalStd":spread}),
            sigma,
        ))
    }
    pub fn integrate(
        &mut self,
        data: &[f64],
        shape: [usize; 2],
        p: &Parameters,
        mask: &[u8],
        o: &Options,
        prepared: Option<Prepared>,
    ) -> Result<Products, String> {
        let (pattern, sigma) = self.integrate_pattern(data, shape, p, mask, o, prepared)?;
        let ck = key(shape, p, mask, o, true);
        if self.cake.as_ref().is_none_or(|plan| plan.key != ck) {
            self.cake = Some(Plan::new(ck)?);
            self.cake_builds += 1;
        }
        let plan = self.cake.as_mut().unwrap();
        if o.dynamic_mask && plan.engine.mask().is_none_or(|m| m.data != mask) {
            plan.engine.set_mask(Mask {
                data: mask.to_vec(),
                dim1: shape[0],
                dim2: shape[1],
            });
        }
        let (pixels, radial_range, azimuth_range) = if !o.solid_angle || o.cake_azimuth.is_some() {
            plan.prepare_normalization();
            if plan.general_2d.is_none() {
                plan.general_2d = Some(crate::sector::build(
                    plan.engine.geometry(),
                    RadialUnit::TthDeg,
                    o.bins,
                    o.cake_bins,
                    o.cake_azimuth,
                    o.supersampling,
                )?);
            }
            let grid = plan.general_2d.as_ref().unwrap();
            (
                dioptrin::lut::integrate2d(
                    data,
                    &grid.lut,
                    Some(mask),
                    plan.normalization.as_ref().unwrap(),
                ),
                grid.radial,
                grid.azimuth,
            )
        } else {
            let pixels = plan.engine.integrate2d_with_azimuthal_range_from_slice(
                data,
                shape[0],
                shape[1],
                o.bins,
                o.cake_bins,
                -std::f64::consts::PI + std::f64::consts::PI / o.cake_bins as f64,
                std::f64::consts::TAU / o.cake_bins as f64,
            );
            if plan.radial.is_none() {
                let g = plan.engine.geometry();
                if o.supersampling > 1 {
                    let radial =
                        RadialUnit::TthDeg.convert_from_tth(&g.calc_tth_all(), p.wavelength);
                    let lut = dioptrin::lut::build_lut1d_ss_csr(
                        g,
                        &radial,
                        o.bins,
                        o.supersampling,
                        RadialUnit::TthDeg,
                    );
                    let bins = lut.bins();
                    plan.radial = Some([bins[0], *bins.last().unwrap()]);
                } else {
                    let (rows, cols) = g.corner_grid();
                    let (tth, _) = g.calc_tth_and_azimuth(&rows, &cols);
                    let radial = RadialUnit::TthDeg.convert_from_tth(&tth, p.wavelength);
                    let low = radial.iter().copied().fold(f64::INFINITY, f64::min);
                    let high = radial.iter().copied().fold(f64::NEG_INFINITY, f64::max)
                        + 10.0 * f64::EPSILON;
                    let half = (high - low) / (2.0 * o.bins as f64);
                    plan.radial = Some([low + half, high - half]);
                }
            }
            (
                pixels,
                plan.radial.unwrap(),
                [
                    -180.0 + 180.0 / o.cake_bins as f64,
                    180.0 - 180.0 / o.cake_bins as f64,
                ],
            )
        };
        let mut cake = Raster::image(&pixels, [o.cake_bins, o.bins]);
        cake.metadata["radialRange"] = json!(radial_range);
        cake.metadata["azimuthRange"] = json!(azimuth_range);
        cake.metadata["unit"] = json!("2th_deg");
        Ok(Products {
            pattern,
            cake,
            cake_values: pixels,
            sigma,
        })
    }
}

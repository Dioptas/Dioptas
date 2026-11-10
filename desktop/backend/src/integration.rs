//! Persistent, worker-owned integration plans. No Python fallback.
use crate::{
    control::Control,
    display::Raster,
    geometry::Geometry as Parameters,
    image::{CombinedSource, Image},
};
use dioptrin::{
    integration::{
        Dynamic1dPlan, Dynamic1dWorker, Fixed1dPlan, FixedCsr1dPlan, FixedGrid2dPlan, InputOrder,
        IntegrationGrid2d, IntegrationMethod, Integrator, MaskMode, RadialUnit, SparseLayout,
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
#[path = "series_pipeline.rs"]
mod series_pipeline;

/// Remove only contiguous exact-zero edges, keeping every radial array aligned.
/// Keep an entirely zero pattern (for example, image minus itself) on its grid.
pub(super) fn trim_zero_edges(
    x: &mut Vec<f64>,
    y: &mut Vec<f64>,
    sigma: Option<&mut Vec<f64>>,
    spread: Option<&mut Vec<f64>>,
) {
    let Some(start) = y.iter().position(|v| *v != 0.0) else {
        return;
    };
    let end = y.iter().rposition(|v| *v != 0.0).unwrap() + 1;
    for values in [Some(x), Some(y), sigma, spread].into_iter().flatten() {
        values.truncate(end);
        values.drain(..start);
    }
}

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
    pub pyfai: bool,
    pub solid_angle: bool,
    pub azimuth: Option<[f64; 2]>,
    pub cake_azimuth: Option<[f64; 2]>,
    pub trim: bool,
    pub spread: bool,
    pub dynamic_mask: bool,
    pub csc: bool,
    pub auto_layout: bool,
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
    pyfai: bool,
    mask: Vec<u8>,
    dynamic: bool,
    csc: bool,
    auto_layout: bool,
    solid: bool,
    azimuth: Option<[f64; 2]>,
}
struct Plan {
    key: Key,
    engine: Integrator,
    fixed: Option<Arc<Fixed1dPlan>>,
    general_1d: Option<Arc<dioptrin::lut::Lut1d>>,
    dynamic_series: Option<Arc<Dynamic1dPlan>>,
    compatibility_1d: Option<Arc<FixedCsr1dPlan>>,
    compatibility_cake: Option<CompatibilityCake>,
    general_2d: Option<crate::sector::Grid>,
    normalization: Option<Arc<Vec<f64>>>,
    radial: Option<[f64; 2]>,
}
struct CompatibilityCake {
    grid: IntegrationGrid2d,
    fixed: Option<FixedGrid2dPlan>,
    radial: [f64; 2],
    azimuth: [f64; 2],
}
struct RawSource {
    source: CombinedSource,
    reader: RawReader,
    buffer: ParallelBlockBuffer,
}
#[derive(Clone)]
pub struct Prepared {
    key: Arc<Key>,
    x: Vec<f64>,
    y: Vec<f64>,
    sigma: Option<Vec<f64>>,
}
pub struct CombinedSeriesPlan {
    key: Arc<Key>,
    fixed: Arc<Fixed1dPlan>,
    source: CombinedSource,
    options: Options,
}
pub struct ProcessedSeriesPlan {
    key: Arc<Key>,
    integration: SeriesIntegrationPlan,
    source: CombinedSource,
    options: Options,
}
enum SeriesIntegrationPlan {
    Dynamic(Arc<Dynamic1dPlan>),
    FixedCompatibility(Arc<FixedCsr1dPlan>),
}
enum SeriesFrameIntegrator<'a> {
    Dynamic(Dynamic1dWorker<'a>),
    FixedCompatibility(&'a FixedCsr1dPlan),
}

pub struct SeriesFrameContext {
    pub processing: Option<crate::processing::SeriesProcessing>,
    pub plugins: crate::mask_plugins::Plugins,
    pub user_mask: Arc<Vec<u8>>,
    pub base_mask: Arc<Vec<u8>>,
}

struct ProcessedFrameWorker<'a> {
    integrator: SeriesFrameIntegrator<'a>,
    values: Vec<f64>,
    variance: Vec<f64>,
    plugins: crate::mask_plugins::Plugins,
    pool: rayon::ThreadPool,
}
#[derive(Default)]
pub struct Engine {
    pattern: Option<Plan>,
    cake: Option<Plan>,
    raw: Option<RawSource>,
    pattern_builds: u64,
    cake_builds: u64,
    cake_integrations: u64,
    combined_decodes: u64,
    parallel_pixel_decodes: u64,
    last_pixel_decode_ms: f64,
    prepared_hits: u64,
    resident_calls: u64,
    pattern_only_decodes: u64,
    frame_parallel_integrations: u64,
    series_worker_starts: u64,
    series_pipeline_runs: u64,
    series_pending_peak: usize,
    processed_frame_integrations: u64,
    dynamic_series_builds: u64,
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
        pyfai: o.pyfai,
        mask: if o.dynamic_mask { vec![] } else { m.to_vec() },
        dynamic: o.dynamic_mask,
        csc: o.csc,
        auto_layout: o.auto_layout,
        solid: o.solid_angle,
        azimuth: if cake { o.cake_azimuth } else { o.azimuth },
    }
}
impl Plan {
    fn new(key: Key) -> Result<Self, String> {
        let [h, w] = key.shape;
        let mut engine = Integrator::new(key.geometry.native_geometry([h, w])?)
            .with_method(if key.pyfai {
                IntegrationMethod::PyfaiFull
            } else if key.supersampling > 1 {
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
            dynamic_series: None,
            compatibility_1d: None,
            compatibility_cake: None,
            general_2d: None,
            normalization: None,
            radial: None,
        })
    }
    fn fixed(&mut self) -> Result<Arc<Fixed1dPlan>, String> {
        if self.fixed.is_none() {
            let shape = (self.key.shape[0], self.key.shape[1]);
            let fixed = if self.key.csc {
                self.engine.prepare_fixed1d(shape, self.key.bins)?
            } else {
                // Keep the resident CSR plan and the fused CSC snapshot under
                // the same immutable scientific key. Entering Batch must not
                // evict/rebuild the resident plan for every frame.
                let mut stream_key = self.key.clone();
                stream_key.csc = true;
                stream_key.auto_layout = false;
                Self::new(stream_key)?
                    .engine
                    .prepare_fixed1d(shape, self.key.bins)?
            };
            self.fixed = Some(Arc::new(if self.key.auto_layout {
                fixed.with_auto_layout()
            } else {
                fixed.with_csc_layout()
            }));
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
        self.normalization = Some(Arc::new(norm));
    }
    fn prepare_general(&mut self, o: &Options) -> Result<(), String> {
        self.prepare_normalization();
        if self.general_1d.is_none() {
            let g = self.engine.geometry();
            let u = unit(&self.key.unit);
            self.general_1d = Some(Arc::new(if o.pyfai {
                crate::pyfai_splitting::build1d(g, u, o.bins, o.azimuth, None)?
            } else if o.azimuth.is_some() {
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
            }));
        }
        Ok(())
    }
    fn fixed_compatibility(
        &mut self,
        o: &Options,
        mask: &[u8],
    ) -> Result<Arc<FixedCsr1dPlan>, String> {
        self.prepare_general(o)?;
        if self.compatibility_1d.is_none() {
            self.compatibility_1d = Some(Arc::new(FixedCsr1dPlan::new(
                self.general_1d.as_ref().unwrap().as_ref().clone(),
                self.normalization.as_ref().unwrap().as_ref().clone(),
                Some(mask.to_vec()),
            )?));
        }
        Ok(self.compatibility_1d.as_ref().unwrap().clone())
    }
    fn general_pattern(
        &mut self,
        data: &[f64],
        supplied_variance: Option<&[f64]>,
        mask: &[u8],
        o: &Options,
    ) -> Result<dioptrin::lut::AzimuthalIntegrationResult, String> {
        self.prepare_general(o)?;
        if o.pyfai && !o.dynamic_mask && !o.spread && supplied_variance.is_none() {
            let result = self
                .fixed_compatibility(o, mask)?
                .integrate_frame(data, o.errors)?;
            return Ok(dioptrin::lut::AzimuthalIntegrationResult {
                radial: result.radial,
                intensity: result.intensity,
                errors: result.errors,
                azimuthal_std: vec![],
            });
        }
        let lut = self.general_1d.as_ref().unwrap();
        let norm = self.normalization.as_ref().unwrap();
        let variance = (o.errors && supplied_variance.is_none())
            .then(|| data.iter().map(|&v| v.max(0.0)).collect::<Vec<_>>());
        let variance = supplied_variance.or(variance.as_deref());
        if o.spread {
            Ok(dioptrin::lut::integrate1d_with_azimuthal_std(
                data,
                lut,
                Some(mask),
                norm,
                variance,
            ))
        } else {
            let (x, y, e) = if let Some(v) = variance {
                let (x, y, e) =
                    dioptrin::lut::integrate1d_with_errors(data, v, lut, Some(mask), norm);
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
    /// One interactive frame loader for file opens, frame arrows, Batch and Map
    /// selections. Keep admission, parallel pixels and the ordinary reader in
    /// the same order so new input optimizations reach every view.
    pub(crate) fn load_frame(
        &mut self,
        image: &mut Image,
        index: usize,
        integration: Option<(&Parameters, &[u8], &Options)>,
        control: &Control,
    ) -> Result<Option<Prepared>, String> {
        let prepared = if let Some((geometry, mask, options)) = integration {
            self.load_combined(image, index, geometry, mask, options, control)?
        } else {
            None
        };
        if prepared.is_none() && !self.load_pixels(image, index, control)? {
            image.read(index)?;
        }
        Ok(prepared)
    }

    pub fn diagnostics(&self) -> Value {
        json!({"patternPlanBuilds":self.pattern_builds,"cakePlanBuilds":self.cake_builds,"cakeIntegrations":self.cake_integrations,"combinedDecodes":self.combined_decodes,"preparedHits":self.prepared_hits,"residentIntegrations":self.resident_calls,"patternOnlyDecodes":self.pattern_only_decodes,"parallelPixelDecodes":self.parallel_pixel_decodes,"lastPixelDecodeMs":self.last_pixel_decode_ms,
            "frameParallelIntegrations":self.frame_parallel_integrations,"seriesWorkerStarts":self.series_worker_starts,"seriesPipelineRuns":self.series_pipeline_runs,"seriesPendingPeak":self.series_pending_peak,
            "processedFrameIntegrations":self.processed_frame_integrations,"dynamicSeriesPlanBuilds":self.dynamic_series_builds})
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
        let Some(plan) = self.prepare_combined_series(image, index, p, mask, options, c)? else {
            return Ok(None);
        };
        self.decode_combined(image, index, &plan, c, true).map(Some)
    }

    pub fn combined_series_pattern(
        &mut self,
        image: &mut Image,
        index: usize,
        plan: &CombinedSeriesPlan,
        c: &Control,
    ) -> Result<Value, String> {
        let prepared = self.decode_combined(image, index, plan, c, false)?;
        self.prepared_hits += 1;
        self.pattern_only_decodes += 1;
        Self::finish_pattern(
            prepared.x,
            prepared.y,
            prepared.sigma,
            None,
            &plan.key.geometry,
            &plan.options,
        )
        .map(|(pattern, _)| pattern)
    }

    pub fn prepare_processed_series(
        &mut self,
        image: &Image,
        p: &Parameters,
        mask: &[u8],
        options: &Options,
        corrected: bool,
    ) -> Result<Option<ProcessedSeriesPlan>, String> {
        let Some(mut source) = image.combined_source(0)? else {
            return Ok(None);
        };
        if source.shape.contains(&0)
            || source.shape[0]
                .checked_mul(source.shape[1])
                .is_none_or(|n| n > 64 * 1024 * 1024)
        {
            return Err("Series detector plane exceeds the native pixel bound.".into());
        }
        source.frame = 0;
        if self.raw.as_ref().is_none_or(|raw| raw.source != source) {
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
        let k = key(image.shape, p, mask, options, false);
        let plan = self.pattern_plan(k.clone())?;
        let fixed_compatibility =
            options.pyfai && !corrected && !options.dynamic_mask && !options.spread;
        let built = !fixed_compatibility && plan.dynamic_series.is_none();
        if built {
            let shape = (image.shape[0], image.shape[1]);
            let dynamic = if !options.pyfai && options.solid_angle && options.azimuth.is_none() {
                // The native dynamic type owns geometry-only CSC weights.
                // Resident layout preferences do not change frame-worker layout.
                let mut dynamic_key = k.clone();
                dynamic_key.dynamic = true;
                dynamic_key.csc = true;
                dynamic_key.auto_layout = false;
                Plan::new(dynamic_key)?
                    .engine
                    .prepare_dynamic1d(shape, options.bins)?
            } else {
                // Preserve the existing custom sector/compatibility grid, but
                // still execute it through the same native dynamic-plan type.
                plan.prepare_general(options)?;
                Dynamic1dPlan::new(
                    shape,
                    plan.general_1d.as_ref().unwrap().as_ref().clone(),
                    plan.normalization.as_ref().unwrap().clone(),
                )?
            };
            plan.dynamic_series = Some(Arc::new(dynamic));
        }
        let result = ProcessedSeriesPlan {
            key: Arc::new(k),
            integration: if fixed_compatibility {
                SeriesIntegrationPlan::FixedCompatibility(plan.fixed_compatibility(options, mask)?)
            } else {
                SeriesIntegrationPlan::Dynamic(plan.dynamic_series.as_ref().unwrap().clone())
            },
            source,
            options: options.clone(),
        };
        self.dynamic_series_builds += u64::from(built);
        Ok(Some(result))
    }

    pub fn parallel_processed_series(
        &mut self,
        image: &Image,
        frames: &[usize],
        plan: &ProcessedSeriesPlan,
        context: &SeriesFrameContext,
        control: &Control,
        mut consume: impl FnMut(usize, Value) -> Result<(), String>,
    ) -> Result<(), String> {
        let raw = self.raw.as_ref().ok_or("Missing prepared series reader.")?;
        if raw.source != plan.source || image.combined_source(0)?.as_ref() != Some(&plan.source) {
            return Err("A series source changed after plan preparation.".into());
        }
        let pixels = image.shape[0] * image.shape[1];
        let supplied_variance =
            plan.options.errors && matches!(plan.integration, SeriesIntegrationPlan::Dynamic(_));
        let extra = pixels
            .saturating_mul(if supplied_variance { 16 } else { 8 })
            .saturating_add(context.plugins.series_scratch_bytes(image.shape));
        let stats = series_pipeline::execute(
            &raw.reader,
            frames,
            control,
            extra,
            || {
                Ok(ProcessedFrameWorker {
                    integrator: match &plan.integration {
                        SeriesIntegrationPlan::Dynamic(p) => {
                            SeriesFrameIntegrator::Dynamic(p.worker(plan.options.errors))
                        }
                        SeriesIntegrationPlan::FixedCompatibility(p) => {
                            SeriesFrameIntegrator::FixedCompatibility(p)
                        }
                    },
                    values: Vec::new(),
                    variance: Vec::new(),
                    plugins: context.plugins.clone(),
                    pool: rayon::ThreadPoolBuilder::new()
                        .num_threads(1)
                        .build()
                        .map_err(|e| e.to_string())?,
                })
            },
            |worker, samples, frame, child| {
                worker.values.clear();
                let width = image.shape[1];
                match samples {
                    PixelBuffer::U16(v) => worker.values.extend(
                        v.chunks_exact(width)
                            .rev()
                            .flat_map(|r| r.iter().map(|&v| f64::from(v))),
                    ),
                    PixelBuffer::U32(v) => worker.values.extend(
                        v.chunks_exact(width)
                            .rev()
                            .flat_map(|r| r.iter().map(|&v| f64::from(v))),
                    ),
                    _ => return Err("Unexpected series sample type.".into()),
                }
                if let Some(processing) = &context.processing {
                    processing.apply(
                        &mut worker.values,
                        plan.options.errors.then_some(&mut worker.variance),
                        child,
                    )?;
                } else if supplied_variance {
                    worker.variance.clear();
                    worker
                        .variance
                        .extend(worker.values.iter().map(|v| v.max(0.)));
                }
                let mask = if plan.options.dynamic_mask {
                    let mut mask = worker.plugins.refresh(
                        &worker.values,
                        image.shape,
                        frame as u64,
                        Some(&plan.key.geometry),
                        &context.user_mask,
                        child,
                    )?;
                    for (value, base) in mask.iter_mut().zip(context.base_mask.iter()) {
                        *value |= base;
                    }
                    std::borrow::Cow::Owned(mask)
                } else {
                    std::borrow::Cow::Borrowed(context.base_mask.as_slice())
                };
                child.check()?;
                let (radial, intensity, errors, spread) =
                    worker.pool.install(|| match &mut worker.integrator {
                        SeriesFrameIntegrator::Dynamic(integrator) => {
                            let result = integrator.integrate(
                                &worker.values,
                                Some(&mask),
                                plan.options.errors.then_some(worker.variance.as_slice()),
                                plan.options.spread,
                            )?;
                            Ok::<_, String>((
                                result.radial,
                                result.intensity,
                                result.errors,
                                result.azimuthal_std,
                            ))
                        }
                        SeriesFrameIntegrator::FixedCompatibility(integrator) => {
                            let result =
                                integrator.integrate_frame(&worker.values, plan.options.errors)?;
                            Ok((result.radial, result.intensity, result.errors, None))
                        }
                    })?;
                Self::finish_pattern(
                    radial,
                    intensity,
                    errors,
                    spread,
                    &plan.key.geometry,
                    &plan.options,
                )
                .map(|r| r.0)
            },
            &mut consume,
        )?;
        image.check_sources()?;
        control.check()?;
        self.frame_parallel_integrations += stats.frames as u64;
        self.processed_frame_integrations += stats.frames as u64;
        self.series_worker_starts += stats.workers as u64;
        self.series_pipeline_runs += 1;
        self.series_pending_peak = self.series_pending_peak.max(stats.pending_peak);
        Ok(())
    }

    /// Share the frozen plan/reader; only the caller collects ordered curves.
    /// Worker threads own scratch, never the mutable session or display state.
    pub fn parallel_series_patterns(
        &mut self,
        image: &Image,
        frames: &[usize],
        plan: &CombinedSeriesPlan,
        control: &Control,
        mut consume: impl FnMut(usize, Value) -> Result<(), String>,
    ) -> Result<(), String> {
        let raw = self.raw.as_ref().ok_or("Missing prepared series reader.")?;
        if raw.source != plan.source || image.combined_source(0)?.as_ref() != Some(&plan.source) {
            return Err("A combined source changed after plan preparation.".into());
        }
        let stats = series_pipeline::run(
            &raw.reader,
            &plan.fixed,
            plan.options.errors,
            frames,
            control,
            |frame, result| {
                let (pattern, _) = Self::finish_pattern(
                    result.radial,
                    result.intensity,
                    result.errors,
                    None,
                    &plan.key.geometry,
                    &plan.options,
                )?;
                consume(frame, pattern)
            },
        )?;
        image.check_sources()?;
        control.check()?;
        self.frame_parallel_integrations += stats.frames as u64;
        self.combined_decodes += stats.frames as u64;
        self.pattern_only_decodes += stats.frames as u64;
        self.prepared_hits += stats.frames as u64;
        self.series_worker_starts += stats.workers as u64;
        self.series_pipeline_runs += 1;
        self.series_pending_peak = self.series_pending_peak.max(stats.pending_peak);
        Ok(())
    }

    /// Parallel input is independent of calibration and integration. Stored Map
    /// patterns, corrections and uncalibrated image browsing use this too.
    pub fn load_pixels(
        &mut self,
        image: &mut Image,
        index: usize,
        c: &Control,
    ) -> Result<bool, String> {
        let started = std::time::Instant::now();
        let Some(mut source) = image.combined_source(index)? else {
            return Ok(false);
        };
        let frame = source.frame;
        source.frame = 0;
        if self.raw.as_ref().is_none_or(|raw| raw.source != source) {
            let reader =
                match RawReader::open_snapshot(&source.path, &source.dataset, Limits::default()) {
                    Ok(reader) => reader,
                    Err(_) => {
                        image.check_sources()?;
                        return Ok(false);
                    }
                };
            self.raw = Some(RawSource {
                source: source.clone(),
                reader,
                buffer: ParallelBlockBuffer::default(),
            });
        }
        let raw = self.raw.as_mut().unwrap();
        let kind = raw.reader.pixel_type();
        let allocate = |n| match kind {
            PixelType::U16 => PixelBuffer::U16(Vec::with_capacity(n)),
            PixelType::U32 => PixelBuffer::U32(Vec::with_capacity(n)),
            _ => unreachable!(),
        };
        let workers = std::env::var("DIOPTAS_INTEGRATION_THREADS")
            .ok()
            .and_then(|v| v.parse::<usize>().ok())
            .unwrap_or(8)
            .clamp(1, 256);
        let parts = raw
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
                    Ok(allocate(range.len()))
                },
                |out, _, block| {
                    c.check().map_err(dioptrin_io::hdf5::Error::from)?;
                    match (out, block) {
                        (PixelBuffer::U16(out), PixelBlock::U16(v)) => out.extend_from_slice(v),
                        (PixelBuffer::U32(out), PixelBlock::U32(v)) => out.extend_from_slice(v),
                        _ => unreachable!(),
                    }
                    Ok(())
                },
            )
            .map_err(|e| e.to_string())?;
        let mut pixels = allocate(source.shape[0] * source.shape[1]);
        for part in parts {
            match (&mut pixels, part) {
                (PixelBuffer::U16(out), PixelBuffer::U16(v)) => out.extend(v),
                (PixelBuffer::U32(out), PixelBuffer::U32(v)) => out.extend(v),
                _ => unreachable!(),
            }
        }
        image.check_sources()?;
        c.check()?;
        image.publish_combined(index, source.shape, pixels)?;
        image.parallel_pixels = true;
        self.parallel_pixel_decodes += 1;
        self.last_pixel_decode_ms = started.elapsed().as_secs_f64() * 1000.;
        Ok(true)
    }

    pub fn prepare_combined_series(
        &mut self,
        image: &mut Image,
        index: usize,
        p: &Parameters,
        mask: &[u8],
        options: &Options,
        c: &Control,
    ) -> Result<Option<CombinedSeriesPlan>, String> {
        if std::env::var("DIOPTAS_COMBINED_HDF5").as_deref() == Ok("0") {
            return Ok(None);
        }
        let mut o = options.clone();
        if o.pyfai || o.dynamic_mask || !o.solid_angle || o.azimuth.is_some() || o.spread {
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
        Ok(Some(CombinedSeriesPlan {
            key: Arc::new(k),
            fixed: plan,
            source,
            options: o,
        }))
    }

    fn decode_combined(
        &mut self,
        image: &mut Image,
        index: usize,
        context: &CombinedSeriesPlan,
        c: &Control,
        retain_pixels: bool,
    ) -> Result<Prepared, String> {
        let mut source = image
            .combined_source(index)?
            .ok_or("Admitted combined source disappeared.")?;
        let frame = source.frame;
        source.frame = 0;
        if source != context.source || self.raw.as_ref().is_none_or(|r| r.source != source) {
            return Err("A combined source changed after plan preparation.".into());
        }
        let o = &context.options;
        let plan = &context.fixed;
        let raw = self.raw.as_mut().unwrap();
        let kind = raw.reader.pixel_type();
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
                    let pixels = retain_pixels.then(|| match kind {
                        PixelType::U16 => PixelBuffer::U16(Vec::with_capacity(range.len())),
                        PixelType::U32 => PixelBuffer::U32(Vec::with_capacity(range.len())),
                        _ => unreachable!(),
                    });
                    Ok((worker, pixels))
                },
                |(worker, pixels), offset, block| {
                    c.check().map_err(dioptrin_io::hdf5::Error::from)?;
                    match (pixels, block) {
                        (Some(PixelBuffer::U16(out)), PixelBlock::U16(v)) => {
                            out.extend_from_slice(v);
                            worker.push_u16_block(offset, v)
                        }
                        (Some(PixelBuffer::U32(out)), PixelBlock::U32(v)) => {
                            out.extend_from_slice(v);
                            worker.push_u32_block(offset, v)
                        }
                        (None, PixelBlock::U16(v)) => worker.push_u16_block(offset, v),
                        (None, PixelBlock::U32(v)) => worker.push_u32_block(offset, v),
                        _ => unreachable!(),
                    }
                    .map_err(Into::into)
                },
            )
            .map_err(|e| e.to_string())?;
        let mut pixels = retain_pixels.then(|| match kind {
            PixelType::U16 => {
                PixelBuffer::U16(Vec::with_capacity(source.shape[0] * source.shape[1]))
            }
            PixelType::U32 => {
                PixelBuffer::U32(Vec::with_capacity(source.shape[0] * source.shape[1]))
            }
            _ => unreachable!(),
        });
        let mut partials = Vec::with_capacity(states.len());
        for (worker, part) in states {
            match (&mut pixels, part) {
                (Some(PixelBuffer::U16(out)), Some(PixelBuffer::U16(v))) => out.extend(v),
                (Some(PixelBuffer::U32(out)), Some(PixelBuffer::U32(v))) => out.extend(v),
                (None, None) => {}
                _ => unreachable!(),
            };
            partials.push(worker);
        }
        let result = plan.finish_ranges(&mut partials)?;
        image.check_sources()?;
        c.check()?;
        if let Some(pixels) = pixels {
            image.publish_combined(index, source.shape, pixels)?;
        }
        self.combined_decodes += 1;
        Ok(Prepared {
            key: context.key.clone(),
            x: result.radial,
            y: result.intensity,
            sigma: result.errors,
        })
    }
    #[allow(clippy::too_many_arguments)]
    pub fn integrate_pattern_with_variance(
        &mut self,
        data: &[f64],
        variance: Option<&[f64]>,
        shape: [usize; 2],
        p: &Parameters,
        mask: &[u8],
        o: &Options,
        prepared: Option<Prepared>,
    ) -> Result<(Value, Option<Vec<f64>>), String> {
        let k = key(shape, p, mask, o, false);
        let prepared = prepared
            .filter(|_| variance.is_none())
            .filter(|r| *r.key == k && (!o.errors || r.sigma.is_some()) && !o.spread);
        let (x, y, sigma, spread) = if let Some(r) = prepared {
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
            if o.pyfai || !o.solid_angle || o.azimuth.is_some() || (o.errors && variance.is_some())
            {
                let r = plan.general_pattern(data, variance, mask, o)?;
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
        Self::finish_pattern(x, y, sigma, spread, p, o)
    }

    fn finish_pattern(
        mut x: Vec<f64>,
        mut y: Vec<f64>,
        mut sigma: Option<Vec<f64>>,
        mut spread: Option<Vec<f64>>,
        p: &Parameters,
        o: &Options,
    ) -> Result<(Value, Option<Vec<f64>>), String> {
        if o.unit == "d_A" {
            for v in &mut x {
                *v = p.wavelength * 1e10 / (2.0 * (v.to_radians() / 2.0).sin());
            }
        }
        if o.trim {
            trim_zero_edges(&mut x, &mut y, sigma.as_mut(), spread.as_mut());
        }
        Ok((
            json!({"x":x,"y":y,"unit":o.unit,"azimuthalStd":spread,"sigma":sigma}),
            sigma,
        ))
    }
    #[allow(clippy::too_many_arguments)]
    pub fn integrate_with_variance(
        &mut self,
        data: &[f64],
        variance: Option<&[f64]>,
        shape: [usize; 2],
        p: &Parameters,
        mask: &[u8],
        o: &Options,
        prepared: Option<Prepared>,
    ) -> Result<Products, String> {
        let (pattern, sigma) =
            self.integrate_pattern_with_variance(data, variance, shape, p, mask, o, prepared)?;
        let (cake, cake_values) = self.integrate_cake(data, shape, p, mask, o)?;
        Ok(Products {
            pattern,
            cake,
            cake_values,
            sigma,
        })
    }
    /// Both full integration and lazy display/export use this same cake kernel.
    pub fn integrate_cake(
        &mut self,
        data: &[f64],
        shape: [usize; 2],
        p: &Parameters,
        mask: &[u8],
        o: &Options,
    ) -> Result<(Raster, Vec<f64>), String> {
        self.cake_integrations += 1;
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
        let (pixels, radial_range, azimuth_range) = if o.pyfai {
            if plan.compatibility_cake.is_none() {
                let grid = crate::pyfai_splitting::grid2d(
                    plan.engine.geometry(),
                    RadialUnit::TthDeg,
                    o.bins,
                    o.cake_bins,
                    o.cake_azimuth,
                    None,
                )?;
                let radial = grid.radial_centers();
                let angles = grid.azimuthal_centers();
                let fixed = if !o.dynamic_mask && o.solid_angle {
                    Some(
                        plan.engine
                            .prepare_fixed2d_on_grid((shape[0], shape[1]), &grid)?,
                    )
                } else {
                    None
                };
                plan.compatibility_cake = Some(CompatibilityCake {
                    grid,
                    fixed,
                    radial: [radial[0], *radial.last().unwrap()],
                    azimuth: [angles[0].to_degrees(), angles.last().unwrap().to_degrees()],
                });
            }
            if !o.solid_angle {
                plan.prepare_normalization();
            }
            let compatibility = plan.compatibility_cake.as_ref().unwrap();
            let pixels = if let Some(fixed) = &compatibility.fixed {
                fixed.integrate_frame(data, false)?.0
            } else {
                let mut raw = plan.engine.integrate2d_raw_on_grid_from_slice(
                    data,
                    shape[0],
                    shape[1],
                    &compatibility.grid,
                    false,
                )?;
                if !o.solid_angle {
                    raw.sum_norm = plan
                        .engine
                        .integrate2d_raw_on_grid_from_slice(
                            plan.normalization.as_ref().unwrap(),
                            shape[0],
                            shape[1],
                            &compatibility.grid,
                            false,
                        )?
                        .sum_signal;
                }
                raw.sum_signal
                    .iter()
                    .zip(raw.sum_norm)
                    .map(|(s, n)| if n == 0.0 { 0.0 } else { s / n })
                    .collect()
            };
            (pixels, compatibility.radial, compatibility.azimuth)
        } else if !o.solid_angle || o.cake_azimuth.is_some() {
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
        Ok((cake, pixels))
    }
}

#[cfg(test)]
mod zero_trimming_tests {
    use super::trim_zero_edges;

    #[test]
    fn edges_keep_internal_zeros_negative_counts_and_aligned_diagnostics() {
        let mut x = vec![9., 8., 7., 6., 5., 4., 3., 2.];
        let mut y = vec![0., -0., -2., 0., 2., 1e-100, 0., 0.];
        let mut sigma = vec![10., 11., 12., 13., 14., 15., 16., 17.];
        let mut spread = vec![20., 21., 22., 23., 24., 25., 26., 27.];
        trim_zero_edges(&mut x, &mut y, Some(&mut sigma), Some(&mut spread));
        assert_eq!(x, [7., 6., 5., 4.]);
        assert_eq!(y, [-2., 0., 2., 1e-100]);
        assert_eq!(sigma, [12., 13., 14., 15.]);
        assert_eq!(spread, [22., 23., 24., 25.]);
    }

    #[test]
    fn empty_all_zero_and_single_point_patterns_keep_valid_grids() {
        for values in [vec![], vec![0., 0., 0.], vec![3.], vec![0., 3., 0.]] {
            let mut x: Vec<_> = (0..values.len()).map(|i| i as f64).collect();
            let mut y = values.clone();
            let mut sigma = vec![1.; y.len()];
            trim_zero_edges(&mut x, &mut y, Some(&mut sigma), None);
            if values == [0., 3., 0.] {
                assert_eq!(x, [1.]);
                assert_eq!(y, [3.]);
                assert_eq!(sigma, [1.]);
            } else {
                assert_eq!(y, values);
                assert_eq!(x.len(), values.len());
                assert_eq!(sigma.len(), values.len());
            }
        }
    }
}

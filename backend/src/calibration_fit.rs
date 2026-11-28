use super::*;
use crate::control::Control;
use dioptrin::{
    calibration::{
        AutoCalibrateError, AutoCalibrateImageOptions, AutoCalibrateProgress, Calibrant,
        CalibrationOptions, CalibrationPoints, DistortionImageObservation, DistortionImageOptions,
        DistortionModel, DistortionOptions, Loss, MassifOptions, ParamMask,
        PolarizationRot3Options, PolarizationRot3Source, PreparedMassif, RefineImageOptions,
        RingCenterOptions, auto_calibrate_image_with_progress, calibrate_rot3_polarization,
        estimate_distortion_image_multi, extract_ring_peaks, refine_image,
    },
    geometry::Geometry as NativeGeometry,
};
use std::cell::RefCell;
use std::collections::BTreeMap;

fn points_to_groups(points: &CalibrationPoints) -> Vec<Group> {
    let mut by_ring: BTreeMap<usize, Vec<[f64; 2]>> = BTreeMap::new();
    let mut total = 0usize;
    for ((&d1, &d2), ring) in points.d1.iter().zip(&points.d2).zip(&points.ring) {
        if total >= MAX_POINTS {
            break;
        }
        if let Some(r) = *ring
            && d1.is_finite()
            && d2.is_finite()
        {
            by_ring.entry(r + 1).or_default().push([d1, d2]);
            total += 1;
        }
    }
    by_ring
        .into_iter()
        .map(|(ring, points)| Group { ring, points })
        .collect()
}

/// Fast post-calibration diagnostic: when wavelength was held fixed, check
/// whether freeing wavelength on the extracted ring peaks dramatically lowers
/// the residual (signaling a wrong starting wavelength).
fn diagnose_wavelength_mismatch(
    shape: [usize; 2],
    poni: &dioptrin::poni::Poni,
    detector: Option<Arc<dioptrin::detector::Detector>>,
    pts: &CalibrationPoints,
    reference: &Calibrant,
    refine_mask: ParamMask,
) -> Option<Value> {
    if pts.len() < 20 {
        return None;
    }
    let n_rings = pts
        .ring
        .iter()
        .flatten()
        .copied()
        .collect::<std::collections::BTreeSet<_>>()
        .len();
    if n_rings < 4 {
        return None;
    }
    let geom = {
        let base = NativeGeometry::new(shape[0], shape[1], poni.clone());
        match detector {
            Some(d) => base.with_detector(d).ok()?,
            None => base,
        }
    };
    let mut fixed_opts = CalibrationOptions {
        mask: refine_mask,
        loss: Loss::Huber { c: 1.5e-3 },
        ..Default::default()
    };
    fixed_opts.mask.rot3 = false;
    fixed_opts.mask.wavelength = false;
    let mut free_opts = fixed_opts.clone();
    free_opts.mask.wavelength = true;

    let (fixed_res, free_res) = crate::worker_pool::install(|| {
        let fixed = dioptrin::calibration::refine(&geom, pts, reference, &fixed_opts);
        let mut free = dioptrin::calibration::refine(&geom, pts, reference, &free_opts);
        // If fixed RMS is high and keeping fixed ring assignments didn't drop it
        // much (e.g. wrong wavelength shifted outer ring indices), retry with
        // auto ring reassignment.
        if let Ok(ref fx) = fixed {
            let need_reassign = match &free {
                Ok(fr) => fr.rms_rad >= fx.rms_rad * 0.70,
                Err(_) => true,
            };
            if need_reassign && fx.rms_rad > 0.015_f64.to_radians() {
                let mut reassign_opts = free_opts.clone();
                reassign_opts.auto_assign_rings = true;
                reassign_opts.assign_tolerance_rad = 0.025;
                if let Ok(re) = dioptrin::calibration::refine(&geom, pts, reference, &reassign_opts)
                {
                    let better = match &free {
                        Ok(fr) => re.rms_rad < fr.rms_rad,
                        Err(_) => true,
                    };
                    if better {
                        free = Ok(re);
                    }
                }
            }
        }
        (fixed, free)
    });

    if let (Ok(fixed_cal), Ok(free_cal)) = (fixed_res, free_res)
        && fixed_cal.rms_rad.is_finite()
        && free_cal.rms_rad.is_finite()
        && free_cal.poni.distance.is_finite()
        && free_cal.poni.distance > 0.01
        && free_cal.poni.wavelength.is_finite()
        && (0.05e-10..=5.0e-10).contains(&free_cal.poni.wavelength)
    {
        let rel_wl_shift = (free_cal.poni.wavelength - poni.wavelength).abs() / poni.wavelength;
        if fixed_cal.rms_rad > 0.006_f64.to_radians()
            && free_cal.rms_rad < fixed_cal.rms_rad * 0.70
            && rel_wl_shift > 0.02
        {
            let current_a = poni.wavelength * 1e10;
            let suggested_a = free_cal.poni.wavelength * 1e10;
            return Some(json!({
                "currentWavelength": current_a,
                "suggestedWavelength": suggested_a,
                "suggestedEnergy": 12.39841984332 / suggested_a,
                "currentRmsDegrees": fixed_cal.rms_rad.to_degrees(),
                "suggestedRmsDegrees": free_cal.rms_rad.to_degrees(),
            }));
        }
    }
    None
}

fn geometry(shape: [usize; 2], parameters: &Geometry) -> Result<NativeGeometry, String> {
    parameters.native_geometry(shape)
}

fn fit_once(
    candidate: &mut Snapshot,
    shape: [usize; 2],
    restart: bool,
    control: &Control,
) -> Result<(), String> {
    crate::worker_pool::install(|| fit_once_in_pool(candidate, shape, restart, control))
}
fn fit_once_in_pool(
    candidate: &mut Snapshot,
    shape: [usize; 2],
    restart: bool,
    control: &Control,
) -> Result<(), String> {
    let mut trace = crate::frame_trace::FrameTrace::new("calibration-fit", 0);
    control.check()?;
    let count = candidate
        .data
        .picks
        .iter()
        .map(|g| g.points.len())
        .sum::<usize>();
    if count < candidate.data.free_count().max(1) {
        return Err(format!(
            "Select at least {} peaks for the current free parameters. Spread selections across several rings when possible.",
            candidate.data.free_count().max(1)
        ));
    }
    let mut start = candidate.geometry.clone();
    if !candidate.calibrated || restart {
        let points: Vec<_> = candidate
            .data
            .picks
            .iter()
            .flat_map(|g| g.points.iter().map(|p| (p[0], p[1])))
            .collect();
        if candidate.data.free[1] || candidate.data.free[2] {
            let center = dioptrin::calibration::estimate_ring_center(
                &points,
                &RingCenterOptions {
                    max_radius_px: 2.0 * (shape[0] as f64).hypot(shape[1] as f64),
                    ..Default::default()
                },
            )
            .ok_or("Could not estimate the ring center. Pick more positions around the rings.")?;
            let p = geometry(shape, &start)?.detector_position(center.d1 + 0.5, center.d2 + 0.5);
            start.poni1 = p[1];
            start.poni2 = p[2];
        }
        start.dist = candidate.data.start[0];
        start.rot1 = 0.0;
        start.rot2 = 0.0;
        start.rot3 = 0.0;
        start.wavelength = candidate.data.start[6];
    }
    let mut values = [
        start.dist,
        start.poni1,
        start.poni2,
        start.rot1,
        start.rot2,
        start.rot3,
        start.wavelength,
    ];
    for (i, v) in values.iter_mut().enumerate() {
        if !candidate.data.free[i] {
            *v = candidate.data.start[i];
        }
    }
    start.dist = values[0];
    start.poni1 = values[1];
    start.poni2 = values[2];
    start.rot1 = values[3];
    start.rot2 = values[4];
    start.rot3 = values[5];
    start.wavelength = values[6];
    start.validate()?;
    let mut points = CalibrationPoints::new();
    for group in &candidate.data.picks {
        for &[row, col] in &group.points {
            points.push(row, col, Some(group.ring - 1));
        }
    }
    let free = candidate.data.free;
    let options = CalibrationOptions {
        mask: ParamMask {
            distance: free[0],
            poni1: free[1],
            poni2: free[2],
            rot1: free[3],
            rot2: free[4],
            // 2θ residuals are invariant under rot3 (rotation around the beam
            // axis), so leaving rot3 free adds a zero Jacobian column that can
            // make the normal equations singular or drift to arbitrary angles.
            rot3: false,
            wavelength: free[6],
        },
        max_iter: 300,
        ..Default::default()
    };
    let reference = Calibrant::from_d_spacings(
        &candidate.data.reference.name,
        candidate.data.reference.spacings.clone(),
    );
    trace.mark("prepare");
    let fitted =
        dioptrin::calibration::refine(&geometry(shape, &start)?, &points, &reference, &options)
            .map_err(|e| {
                format!("Calibration fit failed: {e}. Previous geometry and picked peaks restored.")
            })?;
    control.check()?;
    if fitted.inliers.len() != count || fitted.inliers.iter().any(|inlier| !*inlier) {
        return Err("A selected ring is unavailable at the fitted wavelength; previous geometry and picked peaks restored.".into());
    }
    let mut p = fitted.poni;
    // The engine wraps even fixed rotations into a principal interval after
    // an accepted step. Preserve the exact user-entered fixed values; adding
    // whole turns does not change the physical rotation or its residual.
    for (i, value) in [
        &mut p.distance,
        &mut p.poni1,
        &mut p.poni2,
        &mut p.rot1,
        &mut p.rot2,
        &mut p.rot3,
        &mut p.wavelength,
    ]
    .into_iter()
    .enumerate()
    {
        if !candidate.data.free[i] {
            *value = candidate.data.start[i];
        }
    }
    candidate.geometry = Geometry {
        dist: p.distance,
        poni1: p.poni1,
        poni2: p.poni2,
        rot1: p.rot1,
        rot2: p.rot2,
        rot3: p.rot3,
        pixel1: p.pixel1,
        pixel2: p.pixel2,
        wavelength: p.wavelength,
        ..candidate.geometry.clone()
    };
    candidate.geometry.validate()?;
    if !fitted.rms_rad.is_finite() {
        return Err("Calibration produced a nonfinite residual; previous geometry and picked peaks restored.".into());
    }
    trace.mark("solve-and-apply");
    candidate.calibrated = true;
    candidate.name = Some("current".into());
    candidate.data.rms = Some(fitted.rms_rad.to_degrees());
    candidate.data.source = "fitted".into();
    candidate.data.reference_chosen = true;
    candidate.data.reference_wavelength = candidate.geometry.wavelength;
    candidate.data.saved = false;
    Ok(())
}

fn rings(candidate: &Snapshot, shape: [usize; 2], cache: &RefCell<Option<RingCache>>) -> Value {
    if !candidate.calibrated {
        return json!([]);
    }
    let targets = candidate
        .data
        .reference
        .angles(candidate.data.reference_wavelength);
    if let Some(entry) = cache.borrow().as_ref()
        && entry.geometry == candidate.geometry
        && entry.shape == shape
        && entry.targets == targets
        && entry.intensities == candidate.data.reference.intensities
    {
        return entry.value.clone();
    }
    let Ok(native) = geometry(shape, &candidate.geometry) else {
        return json!([]);
    };
    let field = Arc::new(native.calc_tth_all());
    let mut value = crate::peak_search::contours(&field, shape, &targets);
    if let Some(items) = value.as_array_mut() {
        for item in items {
            if let Some(ring) = item["ring"].as_u64().map(|r| r as usize)
                && let Some(intensity) = candidate.data.reference.intensity(ring)
            {
                let strength = intensity.clamp(0.0, 1.0).sqrt();
                item["lineWidth"] = json!(1.2 + 2.8 * strength);
                item["opacity"] = json!(0.35 + 0.45 * strength);
            }
        }
    }
    *cache.borrow_mut() = Some(RingCache {
        geometry: candidate.geometry.clone(),
        shape,
        targets,
        intensities: candidate.data.reference.intensities.clone(),
        value: value.clone(),
    });
    value
}
fn publish(
    control: &Control,
    candidate: &Snapshot,
    shape: [usize; 2],
    cache: &RefCell<Option<RingCache>>,
    progress: (usize, usize, &str, Option<usize>),
) {
    let (current, total, label, ring) = progress;
    let mut trace = crate::frame_trace::FrameTrace::new("calibration-preview", current as u64);
    // Progress is an owned immutable JSON snapshot. The reader never observes
    // candidate geometry, native objects, or vectors which the worker mutates.
    control.publish(json!({"running":true,"current":current,"total":total,"label":label,
        "calibration":{"activeRing":ring,"picks":candidate.data.picks,"rings":rings(candidate,shape,cache),"rmsDegrees":candidate.data.rms}}));
    trace.mark("contours-and-snapshot");
}

/// A single bounded, disposable preprocessing cache. Immutable owners keep
/// pointer identity valid across image/configuration changes and copy-on-write
/// edits; mask changes while mask use is disabled do not affect the search.
pub(crate) struct MassifCache {
    values: std::sync::Arc<Vec<f64>>,
    mask: Option<std::sync::Arc<Vec<u8>>>,
    shape: [usize; 2],
    prepared: PreparedMassif,
}

impl MassifCache {
    fn matches(
        &self,
        values: &std::sync::Arc<Vec<f64>>,
        mask: Option<&std::sync::Arc<Vec<u8>>>,
        shape: [usize; 2],
    ) -> bool {
        self.shape == shape
            && std::sync::Arc::ptr_eq(&self.values, values)
            && match (&self.mask, mask) {
                (None, None) => true,
                (Some(a), Some(b)) => std::sync::Arc::ptr_eq(a, b),
                _ => false,
            }
    }
}

impl Session {
    pub(super) fn seeded_peaks(&self, seed: [f64; 2]) -> Result<Vec<[f64; 2]>, String> {
        let image = self.image.as_ref().ok_or("Open a calibrant image first.")?;
        let values = self.scientific_values();
        let mask = self.settings.use_mask.then_some(&self.effective_mask);
        let row = seed[0].round_ties_even() as usize;
        let col = seed[1].round_ties_even() as usize;
        if mask.is_some_and(|m| m[row * image.shape[1] + col] != 0) {
            return Err("The selected pixel is masked.".into());
        }
        self.control.check()?;
        let mut cache = self.massif_cache.borrow_mut();
        if cache
            .as_ref()
            .is_none_or(|c| !c.matches(&values, mask, image.shape))
        {
            let clean = values
                .iter()
                .enumerate()
                .map(|(i, &v)| {
                    if v.is_finite() && mask.is_none_or(|m| m[i] == 0) {
                        v
                    } else {
                        0.0
                    }
                })
                .collect();
            let shape = image.shape;
            let prepared = crate::worker_pool::install(|| {
                // Collect peaks across the entire connected massif (not just the
                // first 200 rows in row-major order), then subsample evenly below.
                PreparedMassif::new(
                    clean,
                    shape[0],
                    shape[1],
                    MassifOptions {
                        max_peaks: 4000,
                        dedup_dist: 2.0,
                        ..MassifOptions::default()
                    },
                )
            });
            self.control.check()?;
            *cache = Some(MassifCache {
                values,
                mask: mask.cloned(),
                shape: image.shape,
                prepared,
            });
        }
        let prepared = &cache.as_ref().unwrap().prepared;
        let mut points = prepared.find_peaks((row, col));
        if points.is_empty() {
            let clean = prepared.image();
            let mut best = (row, col);
            for y in row.saturating_sub(5)..(row + 6).min(image.shape[0]) {
                for x in col.saturating_sub(5)..(col + 6).min(image.shape[1]) {
                    if clean[y * image.shape[1] + x] > clean[best.0 * image.shape[1] + best.1] {
                        best = (y, x);
                    }
                }
            }
            points = prepared.find_peaks(best);
        }
        self.control.check()?;
        let mut valid: Vec<[f64; 2]> = points
            .into_iter()
            .filter(|&(y, x)| {
                y.is_finite()
                    && x.is_finite()
                    && y >= 0.0
                    && x >= 0.0
                    && y <= image.shape[0] as f64 - 1.0
                    && x <= image.shape[1] as f64 - 1.0
                    && (!self.settings.use_mask
                        || self.mask[y.round() as usize * image.shape[1] + x.round() as usize] == 0)
            })
            .map(|(y, x)| [y, x])
            .collect();
        const MAX_SEEDED_PEAKS: usize = 200;
        if valid.len() > MAX_SEEDED_PEAKS {
            let n = valid.len() as f64;
            let cy = valid.iter().map(|p| p[0]).sum::<f64>() / n;
            let cx = valid.iter().map(|p| p[1]).sum::<f64>() / n;
            valid.sort_by(|a, b| {
                let aa = (a[0] - cy).atan2(a[1] - cx);
                let ba = (b[0] - cy).atan2(b[1] - cx);
                aa.total_cmp(&ba)
            });
            let len = valid.len();
            valid = (0..MAX_SEEDED_PEAKS)
                .map(|k| valid[k * len / MAX_SEEDED_PEAKS])
                .collect();
        }
        Ok(valid)
    }
    pub(crate) fn calibration_rings(&self) -> Value {
        self.image
            .as_ref()
            .map(|i| rings(&self.calibration_snapshot(), i.shape, &self.ring_cache))
            .unwrap_or_else(|| json!([]))
    }
    pub(super) fn fit_transaction(&mut self, args: &Value, defer: bool) -> Result<(), String> {
        check_keys(
            args,
            &[
                "automatic",
                "parameters",
                "polarization",
                "restart",
                "from_image",
                "fit_rot3",
                "defer_integration",
            ],
        )?;
        let image = self.image.as_ref().ok_or("Open a calibrant image first.")?;
        let shape = image.shape;
        let mut candidate = self.calibration_snapshot();
        if let Some(parameters) = args.get("parameters") {
            candidate.data.fit_parameters(
                parameters,
                &mut candidate.polarization,
                args.get("polarization"),
            )?;
        }
        let from_image = args
            .get("from_image")
            .map(|v| boolean(v, "Refine from image"))
            .transpose()?
            .unwrap_or(false);
        let fit_rot3 = args
            .get("fit_rot3")
            .map(|v| boolean(v, "Fit rot3 from polarization"))
            .transpose()?
            .unwrap_or(false);
        let restart = args
            .get("restart")
            .map(|v| boolean(v, "Restart calibration"))
            .transpose()?
            .unwrap_or(false);
        let zero_config_refine = !restart && candidate.calibrated && from_image;
        if !zero_config_refine && !candidate.data.confirmed {
            return Err(
                "Check detector pixel sizes and the fit start values before fitting.".into(),
            );
        }
        if !zero_config_refine {
            validate_groups(
                &candidate.data.picks,
                shape,
                candidate.data.reference.spacings.len(),
            )?;
        }
        let automatic = args
            .get("automatic")
            .map(|v| boolean(v, "Automatic refinement"))
            .transpose()?
            .unwrap_or(self.workflow.automatic_refinement);
        let control = self.control.clone();
        let ring_cache = RefCell::new(None);
        let publish = |candidate: &Snapshot, current, total, label: &str, ring| {
            publish(
                &control,
                candidate,
                shape,
                &ring_cache,
                (current, total, label, ring),
            )
        };
        let outcome = (|| {
            control.check()?;
            let refine_from_current_image = |candidate: &mut Snapshot,
                                             apply_fixed_starts: bool|
             -> Result<(), String> {
                let mut plugins = self.plugins.clone();
                let mut processing = self.processing.clone();
                let data = processing.values(
                    image,
                    self.image_generation,
                    &candidate.geometry,
                    &self.control,
                )?;
                let mask_bool: Option<Vec<bool>> = if self.settings.use_mask {
                    let current_mask = plugins.refresh(
                        &data,
                        shape,
                        self.scientific_generation.saturating_add(1),
                        Some(&candidate.geometry),
                        &self.mask,
                        &control,
                    )?;
                    Some(current_mask.into_iter().map(|v| v != 0).collect())
                } else {
                    None
                };
                let reference = match &candidate.data.reference.intensities {
                    Some(intensities) => Calibrant::from_d_spacings_and_intensities(
                        &candidate.data.reference.name,
                        candidate.data.reference.spacings.clone(),
                        intensities.iter().map(|&v| Some(v * 100.0)).collect(),
                    ),
                    None => Calibrant::from_d_spacings(
                        &candidate.data.reference.name,
                        candidate.data.reference.spacings.clone(),
                    ),
                };
                let free = candidate.data.free;
                let refine_mask = ParamMask {
                    distance: free[0],
                    poni1: free[1],
                    poni2: free[2],
                    rot1: free[3],
                    rot2: free[4],
                    rot3: false,
                    wavelength: free[6],
                };
                let mut start_poni = geometry(shape, &candidate.geometry)?.poni.clone();
                if apply_fixed_starts {
                    if !free[0] {
                        start_poni.distance = candidate.data.start[0];
                    }
                    if !free[1] {
                        start_poni.poni1 = candidate.data.start[1];
                    }
                    if !free[2] {
                        start_poni.poni2 = candidate.data.start[2];
                    }
                    if !free[3] {
                        start_poni.rot1 = candidate.data.start[3];
                    }
                    if !free[4] {
                        start_poni.rot2 = candidate.data.start[4];
                    }
                    if !free[5] {
                        start_poni.rot3 = candidate.data.start[5];
                    }
                    if !free[6] {
                        start_poni.wavelength = candidate.data.start[6];
                    }
                }
                let ring_cap = (!apply_fixed_starts).then(|| self.workflow.number_of_rings.max(1));
                let max_rings_val = ring_cap.unwrap_or(16);
                let opts = RefineImageOptions {
                    refine_mask,
                    max_rings: ring_cap,
                    max_ring_index: ring_cap.unwrap_or(100).max(100),
                    polarization_factor: (fit_rot3 && candidate.polarization.abs() >= 0.05)
                        .then_some(candidate.polarization),
                    detector: candidate.geometry.detector.clone(),
                    ..Default::default()
                };
                let refined = crate::worker_pool::install(|| {
                    let first = refine_image(
                        &data,
                        shape[0],
                        shape[1],
                        mask_bool.as_deref(),
                        &start_poni,
                        &reference,
                        &opts,
                    );
                    if first.is_ok() {
                        return first;
                    }
                    let mut stage_poni = start_poni.clone();
                    let mut wide_opts = opts.clone();
                    wide_opts.refine_mask.wavelength = false;
                    wide_opts.search_half_width_px = Some(36);
                    wide_opts.n_passes = 5;
                    wide_opts.max_rings = Some(max_rings_val.clamp(3, 6));
                    if let Ok(mid) = refine_image(
                        &data,
                        shape[0],
                        shape[1],
                        mask_bool.as_deref(),
                        &stage_poni,
                        &reference,
                        &wide_opts,
                    ) {
                        stage_poni = mid.calibration.poni.clone();
                        let second = refine_image(
                            &data,
                            shape[0],
                            shape[1],
                            mask_bool.as_deref(),
                            &stage_poni,
                            &reference,
                            &opts,
                        );
                        if second.is_ok() {
                            return second;
                        }
                        if !opts.refine_mask.wavelength {
                            return Ok(mid);
                        }
                    }
                    let mut extract_opts = opts.clone();
                    extract_opts.search_half_width_px = Some(36);
                    extract_opts.max_rings = Some(max_rings_val.clamp(4, 8));
                    let pts = extract_ring_peaks(
                        &data,
                        shape[0],
                        shape[1],
                        mask_bool.as_deref(),
                        &stage_poni,
                        &reference,
                        &extract_opts,
                    )?;
                    let geom = NativeGeometry::new(shape[0], shape[1], stage_poni.clone());
                    let mut cal_opts = CalibrationOptions {
                        mask: opts.refine_mask,
                        ..Default::default()
                    };
                    cal_opts.mask.rot3 = false;
                    cal_opts.mask.wavelength = false;
                    let pulled = dioptrin::calibration::refine(&geom, &pts, &reference, &cal_opts)
                        .map_err(|_| AutoCalibrateError::NoConfidentIdentity)?;
                    match refine_image(
                        &data,
                        shape[0],
                        shape[1],
                        mask_bool.as_deref(),
                        &pulled.poni,
                        &reference,
                        &opts,
                    ) {
                        Ok(res) => Ok(res),
                        Err(_) => {
                            let pts_final = extract_ring_peaks(
                                &data,
                                shape[0],
                                shape[1],
                                mask_bool.as_deref(),
                                &pulled.poni,
                                &reference,
                                &opts,
                            )?;
                            let g_final =
                                NativeGeometry::new(shape[0], shape[1], pulled.poni.clone());
                            let mut final_opts = CalibrationOptions {
                                mask: opts.refine_mask,
                                ..Default::default()
                            };
                            final_opts.mask.rot3 = false;
                            let mut cal = dioptrin::calibration::refine(
                                &g_final,
                                &pts_final,
                                &reference,
                                &final_opts,
                            )
                            .map_err(|_| AutoCalibrateError::NoConfidentIdentity)?;
                            if !cal.rms_rad.is_finite() || cal.rms_rad > 3.5e-3 {
                                return Err(AutoCalibrateError::NoConfidentIdentity);
                            }
                            let rot3_calibration = opts.polarization_factor.and_then(|pol| {
                                calibrate_rot3_polarization(
                                    &data,
                                    shape[0],
                                    shape[1],
                                    mask_bool.as_deref(),
                                    &cal.poni,
                                    &reference,
                                    pol,
                                    &PolarizationRot3Options::default(),
                                )
                                .ok()
                            });
                            if let Some(ref rot3_res) = rot3_calibration
                                && rot3_res.reliable
                                && rot3_res.rot3_rad.is_finite()
                            {
                                cal.poni.rot3 = rot3_res.rot3_rad;
                            }
                            Ok(dioptrin::calibration::RefineImageResult {
                                n_rings: pts_final
                                    .ring
                                    .iter()
                                    .flatten()
                                    .copied()
                                    .collect::<std::collections::BTreeSet<_>>()
                                    .len(),
                                calibration: cal,
                                points: pts_final,
                                rot3_calibration,
                                start_rms_rad: None,
                            })
                        }
                    }
                })
                .map_err(|e| {
                    format!(
                        "Image refinement failed: {e}; previous geometry and picked peaks restored."
                    )
                })?;
                control.check()?;
                let p = refined.calibration.poni;
                candidate.geometry = Geometry {
                    dist: p.distance,
                    poni1: p.poni1,
                    poni2: p.poni2,
                    rot1: p.rot1,
                    rot2: p.rot2,
                    rot3: p.rot3,
                    pixel1: p.pixel1,
                    pixel2: p.pixel2,
                    wavelength: p.wavelength,
                    ..candidate.geometry.clone()
                };
                candidate.geometry.validate()?;
                if !refined.calibration.rms_rad.is_finite() {
                    return Err(
                        "Refinement produced a nonfinite residual; previous geometry restored."
                            .into(),
                    );
                }
                candidate.calibrated = true;
                candidate.name = Some("current".into());
                candidate.data.confirmed = true;
                candidate.data.rms = Some(refined.calibration.rms_rad.to_degrees());
                candidate.data.source = "fitted".into();
                candidate.data.reference_chosen = true;
                candidate.data.reference_wavelength = candidate.geometry.wavelength;
                candidate.data.saved = false;
                candidate.data.dirty = false;
                candidate.data.picks = points_to_groups(&refined.points);
                candidate.data.start = [
                    candidate.geometry.dist,
                    candidate.geometry.poni1,
                    candidate.geometry.poni2,
                    candidate.geometry.rot1,
                    candidate.geometry.rot2,
                    candidate.geometry.rot3,
                    candidate.geometry.wavelength,
                ];
                Ok(())
            };
            if zero_config_refine {
                publish(&candidate, 0, 1, "Refining calibration from image", None);
                refine_from_current_image(&mut candidate, true)?;
                publish(&candidate, 1, 1, "Integrating calibrated image", None);
                return Ok(());
            }
            let total = if automatic { 2 } else { 1 };
            publish(&candidate, 0, total, "Fitting calibration", None);
            // With fewer than 4 picked rings, distance and wavelength are strongly
            // correlated; hold wavelength fixed during the initial manual fit and
            // let refine_image fit wavelength across all detected rings.
            let defer_wavelength = automatic
                && candidate.data.free[6]
                && candidate
                    .data
                    .picks
                    .iter()
                    .map(|g| g.ring)
                    .collect::<std::collections::BTreeSet<_>>()
                    .len()
                    < 4;
            if defer_wavelength {
                candidate.data.free[6] = false;
            }
            let initial_fit = fit_once(&mut candidate, shape, restart, &control);
            if defer_wavelength {
                candidate.data.free[6] = true;
            }
            initial_fit?;
            publish(&candidate, 1, total, "Initial fit complete", None);
            if automatic {
                publish(
                    &candidate,
                    1,
                    total,
                    "Refining calibration from image",
                    None,
                );
                control.check()?;
                refine_from_current_image(&mut candidate, false)?;
            }
            control.check()?;
            candidate.data.dirty = false;
            publish(
                &candidate,
                total,
                total,
                "Integrating calibrated image",
                None,
            );
            Ok(())
        })();
        if let Err(error) = outcome {
            control.finish();
            return Err(error);
        }
        // Retain the preceding products by ownership, without cloning detector
        // pixels. Cancellation after integration restores both model and display.
        let previous = (
            self.pattern.take(),
            self.cake.take(),
            self.cake_values.take(),
            self.elapsed_ms,
            self.sigma.take(),
            self.plugins.clone(),
            self.effective_mask.clone(),
            self.mask_raster.clone(),
        );
        self.restore_calibration(candidate)?;
        let result = self.calculate(defer).and_then(|_| control.check());
        if result.is_ok() {
            *self.ring_cache.borrow_mut() = ring_cache.into_inner();
        }
        if result.is_err() {
            (
                self.pattern,
                self.cake,
                self.cake_values,
                self.elapsed_ms,
                self.sigma,
                self.plugins,
                self.effective_mask,
                self.mask_raster,
            ) = previous;
        }
        control.finish();
        result
    }
    pub(super) fn auto_calibrate_transaction(
        &mut self,
        args: &Value,
        defer: bool,
    ) -> Result<Value, String> {
        check_keys(
            args,
            &[
                "parameters",
                "polarization",
                "use_start_distance",
                "fit_rot3",
                "defer_integration",
            ],
        )?;
        let image = self.image.as_ref().ok_or("Open a calibrant image first.")?;
        let shape = image.shape;
        let mut candidate = self.calibration_snapshot();
        if let Some(parameters) = args.get("parameters") {
            candidate.data.fit_parameters(
                parameters,
                &mut candidate.polarization,
                args.get("polarization"),
            )?;
        }
        let use_start_distance = args
            .get("use_start_distance")
            .map(|v| boolean(v, "Use starting distance"))
            .transpose()?
            .unwrap_or(true);
        let fit_rot3 = args
            .get("fit_rot3")
            .map(|v| boolean(v, "Fit rot3 from polarization"))
            .transpose()?
            .unwrap_or(false);

        let pixel1 = candidate.geometry.pixel1;
        let pixel2 = candidate.geometry.pixel2;
        let wavelength = candidate.data.start[6];
        if !pixel1.is_finite() || pixel1 <= 0.0 || !pixel2.is_finite() || pixel2 <= 0.0 {
            return Err("Enter valid detector pixel sizes before auto-calibrating.".into());
        }
        if !wavelength.is_finite() || wavelength <= 0.0 {
            return Err("Enter a valid wavelength before auto-calibrating.".into());
        }

        let free = candidate.data.free;
        let refine_mask = ParamMask {
            distance: free[0],
            poni1: free[1],
            poni2: free[2],
            rot1: free[3],
            rot2: free[4],
            rot3: free[5],
            wavelength: free[6],
        };
        let starting_distance = (use_start_distance
            && candidate.data.start[0].is_finite()
            && candidate.data.start[0] > 0.0)
            .then_some(candidate.data.start[0]);

        let reference = match &candidate.data.reference.intensities {
            Some(intensities) => Calibrant::from_d_spacings_and_intensities(
                &candidate.data.reference.name,
                candidate.data.reference.spacings.clone(),
                intensities.iter().map(|&v| Some(v * 100.0)).collect(),
            ),
            None => Calibrant::from_d_spacings(
                &candidate.data.reference.name,
                candidate.data.reference.spacings.clone(),
            ),
        };
        let data = self.scientific_values();
        let mask_bool: Option<Vec<bool>> = self
            .settings
            .use_mask
            .then(|| self.effective_mask.iter().map(|&v| v != 0).collect());

        let control = self.control.clone();
        let ring_cache = RefCell::new(None);
        let publish_snap = |candidate: &Snapshot, current, total, label: &str, ring| {
            publish(
                &control,
                candidate,
                shape,
                &ring_cache,
                (current, total, label, ring),
            )
        };

        let mut wavelength_hint: Option<Value> = None;
        let outcome: Result<Option<String>, String> = (|| {
            control.check()?;
            publish_snap(
                &candidate,
                0,
                100,
                "Auto-calibrating detector geometry",
                None,
            );
            let detector = candidate.geometry.detector.clone();
            let opts = AutoCalibrateImageOptions {
                starting_distance,
                refine_mask,
                polarization_factor: (fit_rot3 && candidate.polarization.abs() >= 0.05)
                    .then_some(candidate.polarization),
                detector: detector.clone(),
                ..Default::default()
            };
            let preview_base = candidate.clone();
            let fitted = crate::worker_pool::install(|| {
                let preview_cache = RefCell::new(None);
                let mut stream_progress = |p: AutoCalibrateProgress| -> bool {
                    if control.check().is_err() {
                        return false;
                    }
                    let mut preview = preview_base.clone();
                    if let Some(peaks) = p.peaks {
                        let points: Vec<[f64; 2]> =
                            peaks.into_iter().map(|(y, x)| [y, x]).collect();
                        if !points.is_empty() {
                            preview.data.picks = vec![Group { ring: 1, points }];
                        }
                    }
                    if let Some(poni) = p.candidate_poni {
                        let cand_geom = Geometry {
                            dist: poni.distance,
                            poni1: poni.poni1,
                            poni2: poni.poni2,
                            rot1: poni.rot1,
                            rot2: poni.rot2,
                            rot3: poni.rot3,
                            pixel1: poni.pixel1,
                            pixel2: poni.pixel2,
                            wavelength: poni.wavelength,
                            ..preview.geometry.clone()
                        };
                        if cand_geom.validate().is_ok() {
                            preview.geometry = cand_geom;
                            preview.calibrated = true;
                            preview.data.reference_wavelength = preview.geometry.wavelength;
                        }
                    }
                    if let Some(rms) = p.candidate_rms_rad.filter(|r| r.is_finite()) {
                        preview.data.rms = Some(rms.to_degrees());
                    }
                    let step = (p.progress.clamp(0.0, 1.0) * 100.0).round() as usize;
                    publish(
                        &control,
                        &preview,
                        shape,
                        &preview_cache,
                        (step, 100, &p.message, None),
                    );
                    true
                };
                let first = auto_calibrate_image_with_progress(
                    &data,
                    shape[0],
                    shape[1],
                    mask_bool.as_deref(),
                    &reference,
                    wavelength,
                    pixel1,
                    pixel2,
                    &opts,
                    &mut stream_progress,
                );
                // If a starting distance hint missed (e.g. default 200 mm left on a
                // 500 mm setup) and distance is free, retry blind before failing.
                if control.check().is_ok()
                    && matches!(first, Err(AutoCalibrateError::NoConfidentIdentity))
                    && opts.starting_distance.is_some()
                    && opts.refine_mask.distance
                {
                    let blind_opts = AutoCalibrateImageOptions {
                        starting_distance: None,
                        ..opts.clone()
                    };
                    auto_calibrate_image_with_progress(
                        &data,
                        shape[0],
                        shape[1],
                        mask_bool.as_deref(),
                        &reference,
                        wavelength,
                        pixel1,
                        pixel2,
                        &blind_opts,
                        &mut stream_progress,
                    )
                } else {
                    first
                }
            });
            control.check()?;

            let (result, _diag) = match fitted {
                Ok(v) => v,
                Err(AutoCalibrateError::Cancelled) => {
                    return Err("Operation cancelled.".into());
                }
                Err(_) => {
                    return Ok(Some(format!(
                        "Auto-calibration could not match the rings ({} at {:.4} Å). Check wavelength, calibrant, and pixel sizes, or pick peaks manually.",
                        candidate.data.reference.name,
                        wavelength * 1e10,
                    )));
                }
            };
            let p = result.poni;
            candidate.geometry = Geometry {
                dist: p.distance,
                poni1: p.poni1,
                poni2: p.poni2,
                rot1: p.rot1,
                rot2: p.rot2,
                rot3: p.rot3,
                pixel1: p.pixel1,
                pixel2: p.pixel2,
                wavelength: p.wavelength,
                ..candidate.geometry.clone()
            };
            if candidate.geometry.validate().is_err() || !result.rms_rad.is_finite() {
                return Ok(Some(format!(
                    "Auto-calibration did not converge ({} at {:.4} Å). Check wavelength, calibrant, and pixel sizes, or pick peaks manually.",
                    candidate.data.reference.name,
                    wavelength * 1e10,
                )));
            }
            candidate.calibrated = true;
            candidate.name = Some("current".into());
            candidate.data.confirmed = true;
            candidate.data.rms = Some(result.rms_rad.to_degrees());
            candidate.data.source = "fitted".into();
            candidate.data.reference_chosen = true;
            candidate.data.reference_wavelength = candidate.geometry.wavelength;
            candidate.data.saved = false;
            candidate.data.dirty = false;
            candidate.data.start = [
                candidate.geometry.dist,
                candidate.geometry.poni1,
                candidate.geometry.poni2,
                candidate.geometry.rot1,
                candidate.geometry.rot2,
                candidate.geometry.rot3,
                candidate.geometry.wavelength,
            ];

            // Extract visible ring peaks using Dioptrin's zero-config extractor so the
            // user can inspect the matched points on the detector and refine if desired.
            publish_snap(
                &candidate,
                95,
                100,
                "Extracting calibrated ring peaks",
                None,
            );
            let extracted = crate::worker_pool::install(|| {
                extract_ring_peaks(
                    &data,
                    shape[0],
                    shape[1],
                    mask_bool.as_deref(),
                    &p,
                    &reference,
                    &RefineImageOptions {
                        detector: detector.clone(),
                        ..Default::default()
                    },
                )
            });
            if let Ok(pts) = extracted {
                if !free[6] {
                    wavelength_hint = diagnose_wavelength_mismatch(
                        shape,
                        &p,
                        detector.clone(),
                        &pts,
                        &reference,
                        refine_mask,
                    );
                }
                candidate.data.picks = points_to_groups(&pts);
            } else {
                candidate.data.picks.clear();
            }
            if wavelength_hint.is_none()
                && !free[6]
                && let Some(rms_deg) = candidate.data.rms
                && rms_deg > 0.02
            {
                wavelength_hint = Some(json!({
                    "currentWavelength": p.wavelength * 1e10,
                    "currentRmsDegrees": rms_deg,
                }));
            }
            publish_snap(&candidate, 100, 100, "Integrating calibrated image", None);
            Ok(None)
        })();
        match outcome {
            Err(error) => {
                control.finish();
                return Err(error);
            }
            Ok(Some(notice)) => {
                control.finish();
                return Ok(json!({
                    "autoCalibrateFailed": true,
                    "autoCalibrateNotice": notice,
                }));
            }
            Ok(None) => {}
        }
        let previous = (
            self.pattern.take(),
            self.cake.take(),
            self.cake_values.take(),
            self.elapsed_ms,
            self.sigma.take(),
            self.plugins.clone(),
            self.effective_mask.clone(),
            self.mask_raster.clone(),
        );
        self.restore_calibration(candidate)?;
        let result = self.calculate(defer).and_then(|_| control.check());
        if result.is_ok() {
            *self.ring_cache.borrow_mut() = ring_cache.into_inner();
        }
        if result.is_err() {
            (
                self.pattern,
                self.cake,
                self.cake_values,
                self.elapsed_ms,
                self.sigma,
                self.plugins,
                self.effective_mask,
                self.mask_raster,
            ) = previous;
        }
        control.finish();
        result.map(|()| match wavelength_hint {
            Some(hint) => json!({ "wavelengthHint": hint }),
            None => json!({}),
        })
    }

    pub(super) fn estimate_rot3_transaction(
        &mut self,
        args: &Value,
        defer: bool,
    ) -> Result<Value, String> {
        check_keys(args, &["polarization"])?;
        let image = self.image.as_ref().ok_or("Open a detector image first.")?;
        if !self.settings.calibrated {
            return Err("Calibrate or load a detector geometry before estimating rot3.".into());
        }
        let shape = image.shape;
        let polarization = match args.get("polarization") {
            Some(v) => finite(v, "Polarization", -1.0, 1.0)?,
            None => self.settings.polarization,
        };
        if polarization.abs() < 0.05 {
            return Err(
                "Set a non-zero polarization factor (|P| ≥ 0.05) before estimating rot3.".into(),
            );
        }
        let data = self.scientific_values();
        let mask_bool: Option<Vec<bool>> = self
            .settings
            .use_mask
            .then(|| self.effective_mask.iter().map(|&v| v != 0).collect());
        let reference = match &self.calibration.reference.intensities {
            Some(intensities) => Calibrant::from_d_spacings_and_intensities(
                &self.calibration.reference.name,
                self.calibration.reference.spacings.clone(),
                intensities.iter().map(|&v| Some(v * 100.0)).collect(),
            ),
            None => Calibrant::from_d_spacings(
                &self.calibration.reference.name,
                self.calibration.reference.spacings.clone(),
            ),
        };
        let poni = geometry(shape, &self.settings.geometry)?.poni.clone();
        let detector = self.settings.geometry.detector.clone();
        let res = crate::worker_pool::install(|| {
            calibrate_rot3_polarization(
                &data,
                shape[0],
                shape[1],
                mask_bool.as_deref(),
                &poni,
                &reference,
                polarization,
                &PolarizationRot3Options {
                    detector,
                    ..Default::default()
                },
            )
        })
        .map_err(|e| format!("Could not estimate rot3: {e}"))?;
        if !res.reliable || !res.rot3_rad.is_finite() {
            return Ok(json!({
                "rot3Notice": "Could not reliably determine rot3 from intensity variation; previous geometry kept."
            }));
        }
        let mut candidate = self.calibration_snapshot();
        candidate.polarization = polarization;
        candidate.geometry.rot3 = res.rot3_rad;
        candidate.data.start[5] = res.rot3_rad;
        candidate.data.saved = false;
        candidate.data.dirty = false;
        self.restore_calibration(candidate)?;
        self.calculate(defer)?;
        let source_label = match res.source_used {
            PolarizationRot3Source::Rings => "rings",
            PolarizationRot3Source::Diffuse => "diffuse background",
            PolarizationRot3Source::Auto => "auto",
        };
        Ok(json!({
            "rot3Notice": format!(
                "Estimated rot3 = {:.2}° ± {:.2}° ({source_label})",
                res.rot3_rad.to_degrees(),
                res.uncertainty_rad.to_degrees(),
            )
        }))
    }

    pub(super) fn estimate_distortion_transaction(
        &mut self,
        args: &Value,
    ) -> Result<Value, String> {
        check_keys(
            args,
            &[
                "configurations",
                "model",
                "grid_nx",
                "grid_ny",
                "smoothness",
                "max_order",
                "max_degree",
                "module_height",
                "module_width",
                "gap_height",
                "gap_width",
                "fit_z",
                "regularization",
                "n_passes",
                "cv_folds",
            ],
        )?;
        let requested_indices: Vec<usize> = match args.get("configurations") {
            Some(Value::Array(arr)) if !arr.is_empty() => {
                let mut seen = std::collections::BTreeSet::new();
                let mut out = Vec::with_capacity(arr.len());
                for item in arr {
                    let idx = item
                        .as_u64()
                        .ok_or("Configuration indices must be non-negative integers.")?
                        as usize;
                    if idx >= self.project.configurations.len() {
                        return Err(format!("Configuration {} does not exist.", idx + 1));
                    }
                    if seen.insert(idx) {
                        out.push(idx);
                    }
                }
                out
            }
            _ => vec![self.project.selected],
        };

        let model_kind = args
            .get("model")
            .and_then(Value::as_str)
            .unwrap_or("smooth_spline");
        let (model, model_label) = match model_kind {
            "smooth_spline" => {
                let grid_nx = args
                    .get("grid_nx")
                    .and_then(Value::as_u64)
                    .map(|v| (v as usize).clamp(4, 24))
                    .unwrap_or(8);
                let grid_ny = args
                    .get("grid_ny")
                    .and_then(Value::as_u64)
                    .map(|v| (v as usize).clamp(4, 24))
                    .unwrap_or(8);
                let smoothness = match args.get("smoothness") {
                    Some(v) => finite(v, "Smoothness", 1e-6, 1e6)?,
                    None => 1.0,
                };
                (
                    DistortionModel::SmoothSpline {
                        grid_nx,
                        grid_ny,
                        smoothness,
                    },
                    format!("Smooth B-spline ({grid_nx}×{grid_ny})"),
                )
            }
            "radial_optical" => {
                let max_order = args
                    .get("max_order")
                    .and_then(Value::as_u64)
                    .map(|v| (v as usize).clamp(3, 7))
                    .unwrap_or(5);
                (
                    DistortionModel::RadialOptical { max_order },
                    format!("Radial optical (order {max_order})"),
                )
            }
            "bow_z" => {
                let max_degree = args
                    .get("max_degree")
                    .and_then(Value::as_u64)
                    .map(|v| (v as usize).clamp(2, 5))
                    .unwrap_or(3);
                let smoothness = match args.get("smoothness") {
                    Some(v) => finite(v, "Smoothness", 1e-8, 1e4)?,
                    None => 1e-3,
                };
                (
                    DistortionModel::BowZ {
                        max_degree,
                        smoothness,
                    },
                    format!("Detector bow Δz (deg {max_degree})"),
                )
            }
            "per_module" => {
                let module_height = args
                    .get("module_height")
                    .and_then(Value::as_u64)
                    .map(|v| (v as usize).max(16))
                    .unwrap_or(195);
                let module_width = args
                    .get("module_width")
                    .and_then(Value::as_u64)
                    .map(|v| (v as usize).max(16))
                    .unwrap_or(487);
                let gap_height = args
                    .get("gap_height")
                    .and_then(Value::as_u64)
                    .map(|v| v as usize)
                    .unwrap_or(17);
                let gap_width = args
                    .get("gap_width")
                    .and_then(Value::as_u64)
                    .map(|v| v as usize)
                    .unwrap_or(7);
                let fit_z = args
                    .get("fit_z")
                    .map(|v| boolean(v, "Fit per-module Z"))
                    .transpose()?
                    .unwrap_or(false);
                let regularization = match args.get("regularization") {
                    Some(v) => finite(v, "Regularization", 1e-8, 1e4)?,
                    None => 1e-2,
                };
                (
                    DistortionModel::PerModule {
                        module_height,
                        module_width,
                        gap_height,
                        gap_width,
                        fit_z,
                        regularization,
                    },
                    format!("Per-module ({module_height}×{module_width})"),
                )
            }
            other => return Err(format!("Unknown distortion model: {other}")),
        };
        let n_passes = args
            .get("n_passes")
            .and_then(Value::as_u64)
            .map(|v| (v as usize).clamp(1, 6))
            .unwrap_or(3);
        let cv_folds = args
            .get("cv_folds")
            .and_then(Value::as_u64)
            .map(|v| (v as usize).clamp(0, 10))
            .unwrap_or(5);

        struct OwnedObs {
            config_index: usize,
            label: String,
            data: Arc<Vec<f64>>,
            mask: Option<Vec<bool>>,
            shape: [usize; 2],
            poni: dioptrin::poni::Poni,
            calibrant: Calibrant,
            dist_before_mm: f64,
        }

        let labels = self.project.labels();
        let mut owned = Vec::with_capacity(requested_indices.len());
        let mut common_shape: Option<[usize; 2]> = None;
        let mut common_pixels: Option<(f64, f64)> = None;

        for idx in requested_indices {
            let (image_opt, data, mask_opt, settings, cal_ref) = if idx == self.project.selected {
                let data = self.scientific_values();
                let mask_opt = self
                    .settings
                    .use_mask
                    .then(|| self.effective_mask.iter().map(|&v| v != 0).collect());
                (
                    self.image.as_ref(),
                    data,
                    mask_opt,
                    &self.settings,
                    &self.calibration.reference,
                )
            } else {
                let cfg = self.project.configurations[idx]
                    .as_ref()
                    .ok_or_else(|| format!("Configuration {} is unavailable.", idx + 1))?;
                let st = &cfg.state;
                let data = st
                    .processed_values
                    .clone()
                    .or_else(|| st.image.as_ref().map(|img| img.values.clone()))
                    .unwrap_or_else(|| Arc::new(Vec::new()));
                let mask_opt = st
                    .settings
                    .use_mask
                    .then(|| st.effective_mask.iter().map(|&v| v != 0).collect());
                (
                    st.image.as_ref(),
                    data,
                    mask_opt,
                    &st.settings,
                    &st.calibration.reference,
                )
            };

            let img =
                image_opt.ok_or_else(|| format!("{} has no detector image open.", labels[idx]))?;
            if !settings.calibrated {
                return Err(format!(
                    "{} must be calibrated before estimating distortion.",
                    labels[idx]
                ));
            }
            if let Some(expected) = common_shape {
                if img.shape != expected {
                    return Err(format!(
                        "{} has shape {}×{}, which does not match {}×{}.",
                        labels[idx], img.shape[0], img.shape[1], expected[0], expected[1]
                    ));
                }
            } else {
                common_shape = Some(img.shape);
                common_pixels = Some((settings.geometry.pixel1, settings.geometry.pixel2));
            }
            let poni = geometry(img.shape, &settings.geometry)?.poni.clone();
            let calibrant = match &cal_ref.intensities {
                Some(intensities) => Calibrant::from_d_spacings_and_intensities(
                    &cal_ref.name,
                    cal_ref.spacings.clone(),
                    intensities.iter().map(|&v| Some(v * 100.0)).collect(),
                ),
                None => Calibrant::from_d_spacings(&cal_ref.name, cal_ref.spacings.clone()),
            };
            owned.push(OwnedObs {
                config_index: idx,
                label: labels[idx].clone(),
                data,
                mask: mask_opt,
                shape: img.shape,
                poni,
                calibrant,
                dist_before_mm: settings.geometry.dist * 1000.0,
            });
        }

        let shape = common_shape.ok_or("Select at least one calibrated configuration.")?;
        let (pixel1, pixel2) = common_pixels.unwrap();
        let mut refine_mask = ParamMask::fix_wavelength();
        refine_mask.rot3 = false;
        let opts = DistortionImageOptions {
            distortion: DistortionOptions {
                model,
                refine_poni: true,
                refine_mask,
                cv_folds,
                ..Default::default()
            },
            n_passes,
            ..Default::default()
        };

        let result = crate::worker_pool::install(|| {
            let obs: Vec<DistortionImageObservation<'_>> = owned
                .iter()
                .map(|o| DistortionImageObservation {
                    image: &o.data,
                    dim1: o.shape[0],
                    dim2: o.shape[1],
                    mask: o.mask.as_deref(),
                    poni: &o.poni,
                    calibrant: &o.calibrant,
                })
                .collect();
            estimate_distortion_image_multi(&obs, &opts)
        })
        .map_err(|e| format!("Distortion estimation failed: {e:?}"))?;

        let dist_res = &result.distortion;
        let detector = Arc::new(
            dist_res
                .field
                .to_detector(
                    shape[0],
                    shape[1],
                    pixel1,
                    pixel2,
                    self.settings.geometry.detector.as_deref(),
                )
                .map_err(|e| format!("Could not build distortion detector: {e}"))?,
        );
        let spline_text = dist_res
            .field
            .to_spline(shape[0], shape[1], pixel1, pixel2)
            .ok()
            .map(|s| s.to_fit2d_string());

        // Sample a 17×17 preview vector grid across the detector for the UI map.
        const GRID: usize = 17;
        let mut grid_points = Vec::with_capacity(GRID * GRID);
        let mut max_dz_um = 0.0_f64;
        for r in 0..GRID {
            let d1 = (r as f64 + 0.5) * (shape[0] as f64) / (GRID as f64);
            for c in 0..GRID {
                let d2 = (c as f64 + 0.5) * (shape[1] as f64) / (GRID as f64);
                let (dd1, dd2) = dist_res.field.displacement_px(d1, d2);
                let dz_um = dist_res.field.dz_m(d1, d2) * 1e6;
                if dz_um.is_finite() {
                    max_dz_um = max_dz_um.max(dz_um.abs());
                }
                grid_points.push(json!([
                    d2 / (shape[1] as f64),
                    1.0 - d1 / (shape[0] as f64),
                    if dd2.is_finite() { dd2 } else { 0.0 },
                    if dd1.is_finite() { -dd1 } else { 0.0 },
                    if dz_um.is_finite() { dz_um } else { 0.0 },
                ]));
            }
        }

        let exposures: Vec<Value> = owned
            .iter()
            .enumerate()
            .map(|(i, o)| {
                let after_mm = dist_res
                    .ponis
                    .get(i)
                    .map(|p| p.distance * 1000.0)
                    .unwrap_or(o.dist_before_mm);
                json!({
                    "index": o.config_index,
                    "label": o.label,
                    "nRings": result.n_rings.get(i).copied().unwrap_or(0),
                    "nPoints": result.points.get(i).map(|p| p.len()).unwrap_or(0),
                    "distBeforeMm": o.dist_before_mm,
                    "distAfterMm": after_mm,
                })
            })
            .collect();

        let rms_after_deg = dist_res.rms_after_rad.to_degrees();
        let configs = owned
            .iter()
            .enumerate()
            .map(|(i, o)| {
                let p = dist_res
                    .ponis
                    .get(i)
                    .cloned()
                    .unwrap_or_else(|| o.poni.clone());
                (o.config_index, p, rms_after_deg)
            })
            .collect();

        let can_save_spline = spline_text.is_some();
        self.pending_distortion = Some(PendingDistortion {
            detector,
            spline_text,
            model_label: model_label.clone(),
            configs,
        });

        Ok(json!({
            "distortionPreview": {
                "model": model_kind,
                "modelLabel": model_label,
                "shape": shape,
                "initialRmsPx": result.initial_rms_px,
                "rmsBeforePx": dist_res.rms_before_px,
                "rmsAfterPx": dist_res.rms_after_px,
                "cvRmsPx": dist_res.cv_rms_px,
                "significant": dist_res.significant,
                "rmsBeforeDegrees": dist_res.rms_before_rad.to_degrees(),
                "rmsAfterDegrees": rms_after_deg,
                "maxDisplacementPx": dist_res.max_displacement_px,
                "maxDzUm": max_dz_um,
                "nPointsUsed": dist_res.n_points_used,
                "nPassesCompleted": result.n_passes_completed,
                "canSaveSpline": can_save_spline,
                "exposures": exposures,
                "grid": grid_points,
            }
        }))
    }

    pub(super) fn apply_distortion_transaction(
        &mut self,
        args: &Value,
        defer: bool,
    ) -> Result<Value, String> {
        check_keys(args, &[])?;
        let pending = self
            .pending_distortion
            .clone()
            .ok_or("Estimate a distortion field before applying it.")?;
        let label = format!("Estimated ({})", pending.model_label);
        let mut applied = 0usize;
        let mut active_updated = false;

        for (cfg_idx, poni, rms_deg) in &pending.configs {
            if *cfg_idx == self.project.selected {
                let mut candidate = self.calibration_snapshot();
                candidate.geometry.dist = poni.distance;
                candidate.geometry.poni1 = poni.poni1;
                candidate.geometry.poni2 = poni.poni2;
                candidate.geometry.rot1 = poni.rot1;
                candidate.geometry.rot2 = poni.rot2;
                candidate.geometry.rot3 = poni.rot3;
                candidate.geometry.wavelength = poni.wavelength;
                candidate.geometry.detector = Some(pending.detector.clone());
                candidate.geometry.distortion_file = Some(label.clone());
                candidate.geometry.validate()?;
                candidate.data.rms = Some(*rms_deg);
                candidate.data.saved = false;
                candidate.data.dirty = false;
                candidate.data.start = [
                    candidate.geometry.dist,
                    candidate.geometry.poni1,
                    candidate.geometry.poni2,
                    candidate.geometry.rot1,
                    candidate.geometry.rot2,
                    candidate.geometry.rot3,
                    candidate.geometry.wavelength,
                ];
                self.restore_calibration(candidate)?;
                active_updated = true;
                applied += 1;
            } else if let Some(Some(cfg)) = self.project.configurations.get_mut(*cfg_idx) {
                let st = &mut std::rc::Rc::make_mut(cfg).state;
                st.settings.geometry.dist = poni.distance;
                st.settings.geometry.poni1 = poni.poni1;
                st.settings.geometry.poni2 = poni.poni2;
                st.settings.geometry.rot1 = poni.rot1;
                st.settings.geometry.rot2 = poni.rot2;
                st.settings.geometry.rot3 = poni.rot3;
                st.settings.geometry.wavelength = poni.wavelength;
                st.settings.geometry.detector = Some(pending.detector.clone());
                st.settings.geometry.distortion_file = Some(label.clone());
                st.calibration.rms = Some(*rms_deg);
                st.calibration.saved = false;
                st.calibration.start = [
                    poni.distance,
                    poni.poni1,
                    poni.poni2,
                    poni.rot1,
                    poni.rot2,
                    poni.rot3,
                    poni.wavelength,
                ];
                st.pattern = None;
                st.cake = None;
                st.cake_values = None;
                st.prepared = None;
                *st.ring_cache.borrow_mut() = None;
                applied += 1;
            }
        }
        if active_updated {
            self.calculate(defer)?;
        }
        Ok(json!({
            "distortionNotice": format!(
                "Applied {} distortion to {} configuration{}",
                pending.model_label,
                applied,
                if applied == 1 { "" } else { "s" }
            )
        }))
    }

    pub(super) fn save_distortion_transaction(&mut self, args: &Value) -> Result<Value, String> {
        check_keys(args, &["path", "format"])?;
        let path = args
            .get("path")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
            .ok_or("Distortion file path is required.")?;
        let format = args
            .get("format")
            .and_then(Value::as_str)
            .unwrap_or("spline");
        let save_h5 = format == "h5"
            || path.to_lowercase().ends_with(".h5")
            || path.to_lowercase().ends_with(".hdf5");

        if save_h5 {
            let detector = self
                .pending_distortion
                .as_ref()
                .map(|p| p.detector.clone())
                .or_else(|| self.settings.geometry.detector.clone())
                .ok_or("Estimate or apply a distortion field before saving.")?;
            crate::geometry::detector_io::write_nexus(&detector, Path::new(path))?;
            if self
                .settings
                .geometry
                .detector
                .as_ref()
                .is_some_and(|d| Arc::ptr_eq(d, &detector))
            {
                self.settings.geometry.detector_file = Some(path.to_string());
                self.settings.geometry.distortion_file = None;
            }
            for cfg in self.project.configurations.iter_mut().flatten() {
                if cfg
                    .state
                    .settings
                    .geometry
                    .detector
                    .as_ref()
                    .is_some_and(|d| Arc::ptr_eq(d, &detector))
                {
                    let st = &mut std::rc::Rc::make_mut(cfg).state;
                    st.settings.geometry.detector_file = Some(path.to_string());
                    st.settings.geometry.distortion_file = None;
                }
            }
        } else {
            let spline_text = self
                .pending_distortion
                .as_ref()
                .and_then(|p| p.spline_text.clone())
                .ok_or(
                    "This distortion model uses a 3D pixel map and cannot be saved as a 2D .spline file. Save as NeXus .h5 instead.",
                )?;
            std::fs::write(path, spline_text)
                .map_err(|e| format!("Could not write spline: {e}"))?;
            if let Some(pending) = &self.pending_distortion {
                let det = &pending.detector;
                if self
                    .settings
                    .geometry
                    .detector
                    .as_ref()
                    .is_some_and(|d| Arc::ptr_eq(d, det))
                {
                    self.settings.geometry.distortion_file = Some(path.to_string());
                }
                for cfg in self.project.configurations.iter_mut().flatten() {
                    if cfg
                        .state
                        .settings
                        .geometry
                        .detector
                        .as_ref()
                        .is_some_and(|d| Arc::ptr_eq(d, det))
                    {
                        std::rc::Rc::make_mut(cfg)
                            .state
                            .settings
                            .geometry
                            .distortion_file = Some(path.to_string());
                    }
                }
            }
        }
        Ok(json!({ "savedPath": path }))
    }
}

#[cfg(test)]
mod massif_cache_tests {
    use super::*;
    use std::sync::Arc;

    fn call(session: &mut Session, action: &str, payload: Value) -> Value {
        let reply = session
            .invoke(&crate::protocol::Request {
                id: 1,
                action: action.into(),
                payload,
                cached_buffers: vec![],
            })
            .result;
        assert_eq!(reply["ok"], true, "{action}: {reply}");
        reply
    }
    fn session() -> Session {
        let mut session = Session::new(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".."));
        call(&mut session, "example", json!({}));
        session
    }
    fn cache_id(session: &Session) -> usize {
        session
            .massif_cache
            .borrow()
            .as_ref()
            .unwrap()
            .prepared
            .image()
            .as_ptr() as usize
    }
    fn matches_fresh(session: &Session, seed: [f64; 2]) {
        let cached = session.seeded_peaks(seed).unwrap();
        *session.massif_cache.borrow_mut() = None;
        assert_eq!(cached, session.seeded_peaks(seed).unwrap());
    }

    #[test]
    fn massif_cache_reuses_pixels_across_seeds_and_calibration_edits() {
        let mut s = session();
        assert!(!s.seeded_peaks([564., 637.]).unwrap().is_empty());
        let id = cache_id(&s);
        for seed in [[511., 671.], [703., 668.], [0., 0.]] {
            s.seeded_peaks(seed).unwrap();
            assert_eq!(cache_id(&s), id);
        }
        call(&mut s, "workflow_settings", json!({"autoIncrement":false}));
        call(&mut s, "pick_peak", json!({"x":637,"y":564,"ring":1}));
        call(&mut s, "undo_calibration", json!({}));
        call(&mut s, "redo_calibration", json!({}));
        assert_eq!(cache_id(&s), id);
    }

    #[test]
    fn massif_cache_invalidates_on_image_orientation_corrections_and_masks() {
        let mut s = session();
        s.seeded_peaks([564., 637.]).unwrap();
        let source = s.image.as_ref().unwrap().path.clone();
        for (action, payload) in [
            (
                "mask_edit",
                json!({"operation":"rectangle","points":[[1.,1.],[4.,3.]]}),
            ),
            ("undo_mask", json!({})),
            ("redo_mask", json!({})),
            ("settings", json!({"use_mask":false})),
            ("settings", json!({"use_mask":true})),
            (
                "integration_image_background",
                json!({"path":source,"scale":0.01}),
            ),
            ("integration_image_background", json!({"reset":true})),
            ("image_transform", json!({"operation":"flip_horizontal"})),
            ("image_transform", json!({"operation":"rotate_right"})),
            ("example", json!({})),
        ] {
            let before = cache_id(&s);
            call(&mut s, action, payload);
            s.seeded_peaks([564., 637.]).unwrap();
            assert_ne!(cache_id(&s), before, "{action} must rebuild preprocessing");
            matches_fresh(&s, [564., 637.]);
        }
        call(&mut s, "settings", json!({"use_mask":false}));
        s.seeded_peaks([564., 637.]).unwrap();
        let before = cache_id(&s);
        // Editing through the Mask workflow also enables mask use. Here vary
        // an inactive effective mask directly to check the cache key itself.
        Arc::make_mut(&mut s.effective_mask)[5 * 981 + 5] = 1;
        s.seeded_peaks([564., 637.]).unwrap();
        assert_eq!(
            cache_id(&s),
            before,
            "Disabled masks do not affect preprocessing"
        );
    }

    #[test]
    fn massif_cache_keeps_copy_on_write_inputs_immutable_and_rejects_masked_seeds() {
        let mut s = session();
        let original = s.seeded_peaks([564., 637.]).unwrap();
        let before = cache_id(&s);
        // Holding the source owners in the cache forces a fresh identity even
        // when a caller changes an existing Arc through copy-on-write.
        s.processed_values = Some(s.scientific_values());
        let values = s.processed_values.as_mut().unwrap();
        Arc::make_mut(values)[564 * 981 + 637] += 1000.;
        s.seeded_peaks([564., 637.]).unwrap();
        assert_ne!(cache_id(&s), before);
        matches_fresh(&s, [564., 637.]);
        let before = cache_id(&s);
        Arc::make_mut(&mut s.effective_mask)[564 * 981 + 637] = 1;
        assert_eq!(
            s.seeded_peaks([564., 637.]).unwrap_err(),
            "The selected pixel is masked."
        );
        // A rejected click does not publish preprocessing for that masked seed.
        assert_eq!(cache_id(&s), before);
        s.seeded_peaks([511., 671.]).unwrap();
        assert_ne!(cache_id(&s), before);
        matches_fresh(&s, [511., 671.]);
        assert!(!original.is_empty());
    }

    #[test]
    fn massif_cache_rebuilds_for_a_different_frame_of_the_same_file() {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path().join("frames.tif");
        let mut encoder =
            tiff::encoder::TiffEncoder::new(std::fs::File::create(&path).unwrap()).unwrap();
        for center in [20.3, 40.2] {
            let values: Vec<_> = (0..64 * 64)
                .map(|i| {
                    1.0 + 100.0
                        * (-((i / 64) as f64 - 32.0).powi(2) / 8.0
                            - ((i % 64) as f64 - center).powi(2) / 8.0)
                            .exp()
                })
                .collect();
            encoder
                .write_image::<tiff::encoder::colortype::Gray64Float>(64, 64, &values)
                .unwrap();
        }
        drop(encoder);
        let mut s = Session::new(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".."));
        call(&mut s, "open_image", json!({"path":path,"frame":0}));
        assert_eq!(s.image.as_ref().unwrap().frames, 2);
        let first = s.seeded_peaks([31., 20.]).unwrap();
        let before = cache_id(&s);
        call(&mut s, "open_image", json!({"path":path,"frame":1}));
        let second = s.seeded_peaks([31., 40.]).unwrap();
        assert_ne!(cache_id(&s), before);
        assert!((first[0][1] - 20.3).abs() < 0.1);
        assert!((second[0][1] - 40.2).abs() < 0.1);
        matches_fresh(&s, [31., 40.]);
    }
}

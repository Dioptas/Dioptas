use super::*;
use crate::control::Control;
use dioptrin::{
    calibration::{
        Calibrant, CalibrationOptions, CalibrationPoints, MassifOptions, ParamMask, PreparedMassif,
        RingCenterOptions,
    },
    geometry::Geometry as NativeGeometry,
};
use std::cell::RefCell;

fn geometry(shape: [usize; 2], parameters: &Geometry) -> Result<NativeGeometry, String> {
    parameters.native_geometry(shape)
}

fn fit_once(
    candidate: &mut Snapshot,
    shape: [usize; 2],
    restart: bool,
    control: &Control,
) -> Result<(), String> {
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
    }
    start.wavelength = candidate.data.start[6];
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
            rot3: free[5],
            wavelength: free[6],
        },
        max_iter: 300,
        ..Default::default()
    };
    let reference = Calibrant::from_d_spacings(
        &candidate.data.reference.name,
        candidate.data.reference.spacings.clone(),
    );
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
    candidate.calibrated = true;
    candidate.name = Some("current".into());
    candidate.data.rms = Some(fitted.rms_rad.to_degrees());
    candidate.data.source = "fitted".into();
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
    {
        return entry.value.clone();
    }
    let Ok(native) = geometry(shape, &candidate.geometry) else {
        return json!([]);
    };
    let field = native.calc_tth_all();
    let value = crate::peak_search::contours(&field, shape, &targets);
    *cache.borrow_mut() = Some(RingCache {
        geometry: candidate.geometry.clone(),
        shape,
        targets,
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
    // Progress is an owned immutable JSON snapshot. The reader never observes
    // candidate geometry, native objects, or vectors which the worker mutates.
    control.publish(json!({"running":true,"current":current,"total":total,"label":label,
        "calibration":{"activeRing":ring,"picks":candidate.data.picks,"rings":rings(candidate,shape,cache),"rmsDegrees":candidate.data.rms}}));
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
            let prepared = PreparedMassif::new(
                clean,
                image.shape[0],
                image.shape[1],
                MassifOptions::default(),
            );
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
        Ok(points
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
            .collect())
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
        if !candidate.data.confirmed {
            return Err(
                "Check detector pixel sizes and the fit start values before fitting.".into(),
            );
        }
        validate_groups(
            &candidate.data.picks,
            shape,
            candidate.data.reference.spacings.len(),
        )?;
        let automatic = args
            .get("automatic")
            .map(|v| boolean(v, "Automatic refinement"))
            .transpose()?
            .unwrap_or(self.workflow.automatic_refinement);
        let restart = args
            .get("restart")
            .map(|v| boolean(v, "Restart calibration"))
            .transpose()?
            .unwrap_or(false);
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
            publish(&candidate, 0, 1, "Fitting calibration", None);
            fit_once(&mut candidate, shape, restart, &control)?;
            publish(&candidate, 1, 1, "Initial fit complete", None);
            if automatic {
                candidate.data.picks.clear();
                let total = self.workflow.number_of_rings.min(
                    candidate
                        .data
                        .reference
                        .angles(candidate.geometry.wavelength)
                        .len(),
                );
                publish(&candidate, 0, total, "Preparing peak search", Some(1));
                let mut plugins = self.plugins.clone();
                let mut processing = self.processing.clone();
                let mut data = self.scientific_values();
                let mut data_generation = self.scientific_generation;
                let mut mask = Vec::new();
                let mut candidates = Vec::new();
                for ring in 1..=total {
                    control.check()?;
                    let current = processing.values(
                        image,
                        self.image_generation,
                        &candidate.geometry,
                        &self.control,
                    )?;
                    let changed = !Arc::ptr_eq(&current, &data);
                    if changed {
                        data_generation += 1;
                        data = current;
                    }
                    // Spot Mask follows the detached candidate geometry. Its
                    // cache and newly excluded peaks must never leak into the
                    // durable model if this complete fit is cancelled.
                    let current_mask = if self.settings.use_mask {
                        plugins.refresh(
                            &data,
                            shape,
                            data_generation,
                            Some(&candidate.geometry),
                            &self.mask,
                            &control,
                        )?
                    } else {
                        vec![0; image.values.len()]
                    };
                    if ring == 1 || current_mask != mask || changed {
                        mask = current_mask;
                        let clean: Vec<_> = data
                            .iter()
                            .enumerate()
                            .map(|(i, &v)| {
                                if v.is_finite() && mask[i] == 0 {
                                    v
                                } else {
                                    0.0
                                }
                            })
                            .collect();
                        candidates = crate::peak_search::candidates(
                            &clean,
                            shape,
                            &self.workflow.algorithm,
                            &control,
                        )?;
                    }
                    publish(&candidate, ring, total, "Finding peaks on ring", Some(ring));
                    let field = geometry(shape, &candidate.geometry)?.calc_tth_all();
                    let target = candidate
                        .data
                        .reference
                        .angles(candidate.geometry.wavelength)
                        .into_iter()
                        .find(|(r, _)| *r == ring)
                        .ok_or("Ring unavailable at fitted wavelength.")?
                        .1;
                    let points = crate::peak_search::on_ring(
                        &data,
                        &field,
                        &mask,
                        shape,
                        &candidates,
                        crate::peak_search::Band {
                            target,
                            delta: self.workflow.delta_tth,
                            factor: self.workflow.mean_factor,
                            ceiling: self.workflow.intensity_limit,
                        },
                        &control,
                    )?;
                    if !points.is_empty() {
                        candidate.data.picks.push(Group { ring, points });
                    }
                    if candidate
                        .data
                        .picks
                        .iter()
                        .map(|g| g.points.len())
                        .sum::<usize>()
                        > MAX_POINTS
                    {
                        return Err("Automatic search exceeds 100000 peaks; previous geometry and picked peaks restored.".into());
                    }
                    publish(&candidate, ring, total, "Refining ring", Some(ring));
                    if ring >= 2
                        && candidate
                            .data
                            .picks
                            .iter()
                            .map(|g| g.points.len())
                            .sum::<usize>()
                            >= candidate.data.free_count().max(1)
                    {
                        fit_once(&mut candidate, shape, false, &control)?;
                    }
                    publish(&candidate, ring, total, "Refining ring", Some(ring));
                }
                if candidate.data.picks.is_empty() {
                    return Err("Automatic ring search found no peaks; previous geometry and picked peaks restored.".into());
                }
                fit_once(&mut candidate, shape, false, &control)?;
            }
            control.check()?;
            candidate.data.dirty = false;
            publish(&candidate, 1, 1, "Integrating calibrated image", None);
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
        let mut session = Session::new(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."));
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
        let mut s = Session::new(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../.."));
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

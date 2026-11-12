//! Adapter to the same native coordinator as standalone PhaseSmith. No duplicate
//! profile, empirical-scaling or shadow estimator is maintained in Dioptas.
use super::*;
use phasesmith_workflows::single_crystal as sc;
pub(super) fn profile_reserved_minimum(value: f64) -> u32 {
    value.ceil() as u32
}
const CHECKPOINT: &str = "Dioptas native reduction checkpoint (before structure search)";
pub(super) struct OriginalSource<'a>(pub(super) &'a Crystal);
impl sc::FrameSource for OriginalSource<'_> {
    fn shape(&self) -> [usize; 3] {
        [self.0.sources.len(), self.0.shape[0], self.0.shape[1]]
    }
    fn read(&mut self, index: usize) -> sc::Result<Vec<u32>> {
        let values = self.0.read(index).map_err(sc::Error)?;
        // Dioptas already flipped the decoded view. Restore original storage order;
        // the coordinator then applies its declared flip exactly once.
        values
            .chunks_exact(self.0.shape[1])
            .rev()
            .flatten()
            .map(|&v| {
                if !v.is_finite() || v < 0. || v > u32::MAX as f64 || v.fract() != 0. {
                    Err(sc::Error(
                        "Profile recipe requires original uint32-compatible detector counts."
                            .into(),
                    ))
                } else {
                    Ok(v as u32)
                }
            })
            .collect()
    }
}
#[derive(Default)]
struct Capture<'a> {
    control: Option<&'a Control>,
    audit: Option<audit::Audit>,
    audit_directory: Option<Arc<tempfile::TempDir>>,
    first: usize,
    last: usize,
    stop_after: &'static str,
    checkpoint_complete: bool,
    centres: Vec<V3>,
    measured_hkl: Vec<[i32; 3]>,
    tracks: Vec<Track>,
    peaks: Vec<Peak>,
    rows: Vec<Reflection>,
    cell: Option<Cell>,
    basis: Option<M3>,
    geometry: Option<Geometry>,
    geometry_report: Value,
    shadows: Option<Arc<Shadows>>,
    report: Value,
}
impl sc::Observer for Capture<'_> {
    fn stage(&mut self, name: &str, seconds: f64) -> sc::Result<()> {
        if let Some(c) = self.control {
            c.check().map_err(sc::Error)?;
            c.publish(json!({"running":true,"label":format!("PhaseSmith profile recipe · completed {name} ({seconds:.1}s)")}));
        }
        if name == self.stop_after {
            self.checkpoint_complete = true;
            return Err(sc::Error(CHECKPOINT.into()));
        }
        Ok(())
    }
    fn masks(&mut self, p: &spots::frame_input::Plan, scales: &[f64]) -> sc::Result<()> {
        let block = p.blocks[0].block;
        let columns = p.shape[1].div_ceil(block);
        let rows = p.shape[0].div_ceil(block);
        let illumination = p.blocks[0].excluded.clone();
        let dac = p.blocks[1].excluded.clone();
        let report = json!({"first":self.first,"last":self.last,"block":block,"coarseShape":[rows,columns],"illuminationSha256":shadows::fingerprint(&illumination),"dacSha256":shadows::fingerprint(&dac),"illuminationExcluded":illumination.iter().filter(|&&v|v).count(),"dacExcluded":dac.iter().filter(|&&v|v).count(),"detectionScales":scales,"sourceHashes":p.expected_hashes,"geometry":"standalone initial calibration; full exposure and detector-block footprint"});
        if let Some(a) = &mut self.audit {
            a.b(
                "illumination_excluded",
                &[p.frames, rows, columns],
                &illumination,
            );
            a.b("dac_excluded", &[p.frames, rows, columns], &dac);
            a.f("detection_scales", &[scales.len()], scales.iter().copied());
        }
        self.shadows = Some(Arc::new(Shadows {
            first: self.first,
            last: self.last,
            block,
            columns,
            cells: rows * columns,
            illumination,
            dac,
            report,
        }));
        Ok(())
    }
    fn positions(&mut self, p: &sc::Positions) -> sc::Result<()> {
        if let Some(a) = &mut self.audit {
            a.f(
                "positions_values",
                &[p.values.len(), 5],
                p.values.iter().flatten().copied(),
            );
            a.i(
                "positions_boxes",
                &[p.boxes.len(), 4],
                p.boxes
                    .iter()
                    .flat_map(|b| [b.x0 as i64, b.y0 as i64, b.x1 as i64, b.y1 as i64]),
            );
            a.i(
                "positions_frame_ranges",
                &[p.ranges.len(), 2],
                p.ranges.iter().flatten().map(|&v| v as i64),
            );
            a.u("positions_flags", &p.flags);
            a.u("positions_original_flags", &p.original_flags);
            a.f(
                "positions_observations",
                &[p.observations.len(), 5],
                p.observations.iter().flatten().copied(),
            );
            a.f(
                "omega_bounds",
                &[p.angles.len(), 2],
                p.angles.iter().flatten().copied(),
            );
        }
        self.tracks = p
            .values
            .iter()
            .enumerate()
            .map(|(id, v)| {
                let b = p.boxes[id];
                Track {
                    observed: [v[0], v[1], v[2]],
                    first: p.ranges[id][0] + self.first,
                    last: p.ranges[id][1].saturating_sub(1) + self.first,
                    bounds: [b.x0, b.y0, b.x1, b.y1],
                    flags: p.flags[id],
                    excluded: false,
                    native: true,
                }
            })
            .collect();
        self.peaks = p
            .observations
            .iter()
            .map(|v| {
                let id = v[0] as usize;
                Peak {
                    frame: v[1] as usize + self.first,
                    xy: [v[2], v[3]],
                    intensity: 0.,
                    flags: p.flags[id],
                    bounds: self.tracks[id].bounds,
                    track: id,
                }
            })
            .collect();
        Ok(())
    }
    fn indexed(&mut self, i: &sc::Indexed) -> sc::Result<()> {
        if let Some(a) = &mut self.audit {
            a.i(
                "indexed_track_ids",
                &[i.track_ids.len()],
                i.track_ids.iter().map(|&v| v as i64),
            );
            a.i(
                "indexed_hkl",
                &[i.hkl.len(), 3],
                i.hkl.iter().flatten().copied(),
            );
            a.f(
                "indexed_observed",
                &[i.observed.len(), 3],
                i.observed.iter().flatten().copied(),
            );
            a.f(
                "indexed_predicted",
                &[i.fit.predictions.len(), 3],
                i.fit.predictions.iter().flat_map(|p| p.values),
            );
            a.b("indexed_training", &[i.training.len()], &i.training);
            a.b("indexed_eligible", &[i.eligible.len()], &i.eligible);
            a.f(
                "reciprocal_basis",
                &[3, 3],
                i.fit.state.basis.iter().flatten().copied(),
            );
            let g = i.fit.state.geometry;
            a.f(
                "geometry_vectors",
                &[5, 3],
                [g.origin, g.fast, g.slow, g.beam, g.axis]
                    .iter()
                    .flatten()
                    .copied(),
            );
        }
        let direct = fft::inverse_transpose(i.fit.state.basis).map_err(sc::Error)?;
        let q = i.fit.state.geometry.convert(&i.observed)?;
        let distances =
            fft::Engine::new(1)
                .map_err(sc::Error)?
                .score(&q, direct, i.fit.state.basis);
        let withheld: Vec<_> = distances
            .iter()
            .enumerate()
            .filter(|(k, _)| i.fit.eligible[*k] && !i.training[*k])
            .map(|(_, (_, d))| *d)
            .collect();
        if withheld.is_empty() {
            return Err(sc::Error(
                "No independent reciprocal-position validation points.".into(),
            ));
        }
        self.cell = Some(Cell {
            direct,
            parameters: super::processing::parameters(direct),
            indexed: i.fit.eligible.iter().filter(|&&v| v).count(),
            total: self.tracks.len(),
            rms: (withheld.iter().map(|d| d * d).sum::<f64>() / withheld.len() as f64).sqrt(),
            validation: withheld.len(),
        });
        self.basis = Some(i.fit.state.basis);
        self.geometry = Some(i.fit.state.geometry.into());
        self.geometry_report = json!({"refined":true,"converged":i.fit.converged,"atBounds":i.fit.at_bounds,"condition":i.fit.scaled_condition,"maximumCorrelation":i.fit.maximum_parameter_correlation,"rms":i.fit.rms,"counts":i.fit.counts,"evaluations":i.fit.evaluations,"parameters":i.fit.parameters,"accepted":i.fit.acceptable(),"source":"PhaseSmith standalone orthorhombic-v1; independent family holdout"});
        Ok(())
    }
    fn profiles(&mut self, m: &sc::Measurements) -> sc::Result<()> {
        if let Some(a) = &mut self.audit {
            let d = &m.data;
            let n = m.hkl.len();
            a.i(
                "table_hkl",
                &[n, 3],
                m.hkl.iter().flatten().map(|&v| i64::from(v)),
            );
            a.f(
                "table_predicted",
                &[n, 3],
                d.centres.iter().flatten().copied(),
            );
            a.f(
                "table_values",
                &[n, 6],
                m.aperture.iter().flatten().copied(),
            );
            a.u("table_flags", &m.flags);
            a.i(
                "table_observation_ids",
                &[d.ids.len()],
                d.ids.iter().map(|&v| v as i64),
            );
            a.i(
                "table_frame_indices",
                &[d.frames.len()],
                d.frames.iter().map(|&v| v as i64),
            );
            a.i(
                "table_boxes",
                &[d.boxes.len(), 4],
                d.boxes
                    .iter()
                    .flat_map(|b| [b.x0 as i64, b.y0 as i64, b.x1 as i64, b.y1 as i64]),
            );
            a.f(
                "table_frame_values",
                &[d.frame_values.len(), 11],
                d.frame_values.iter().flatten().copied(),
            );
            a.u("table_frame_flags", &d.flags);
            a.u("native_group_flags", &d.native_flags);
            a.f(
                "table_background_models",
                &[d.background.len(), 12],
                d.background.iter().flatten().copied(),
            );
            a.f(
                "table_angular_half_widths",
                &[n],
                d.scales.iter().map(|s| (0.9 / s[2].abs() + 0.5).min(4.5)),
            );
            a.f(
                "obs_samples",
                &[d.samples.len(), 3],
                d.samples.iter().flatten().copied(),
            );
            a.b("obs_valid", &[d.valid.len()], &d.valid);
            a.i(
                "obs_offsets",
                &[d.offsets.len()],
                d.offsets.iter().map(|&v| v as i64),
            );
            a.f(
                "obs_covariance",
                &[d.covariance.len(), 9],
                d.covariance.iter().flatten().copied(),
            );
            a.f("obs_centres", &[n, 3], d.centres.iter().flatten().copied());
            a.f("obs_scales", &[n, 3], d.scales.iter().flatten().copied());
            a.f(
                "obs_planar_transforms",
                &[n, 2, 2],
                d.planar.iter().flatten().copied(),
            );
            a.f(
                "bank_profiles",
                &[m.bank.counts.len(), m.grid.size()],
                m.bank.profiles.iter().copied(),
            );
            a.i(
                "bank_counts",
                &[m.bank.counts.len()],
                m.bank.counts.iter().map(|&v| v as i64),
            );
            a.f(
                "bank_shifts",
                &[m.bank.shifts.len(), 3],
                m.bank.shifts.iter().flatten().copied(),
            );
            let used = m.bank.used.iter().filter(|&&v| v).count();
            a.i(
                "bank_reference_ids",
                &[used],
                m.bank
                    .used
                    .iter()
                    .enumerate()
                    .filter_map(|(i, &v)| v.then_some(i as i64)),
            );
            a.f(
                "bank_reference_centres",
                &[used, 3],
                m.bank
                    .reference_centres
                    .iter()
                    .zip(&m.bank.used)
                    .filter(|(_, u)| **u)
                    .flat_map(|(p, _)| p.iter().copied()),
            );
        }
        self.measured_hkl = m.hkl.clone();
        self.centres = m.data.centres.clone();
        Ok(())
    }
    fn reduced(&mut self, r: &sc::Reduced) -> sc::Result<()> {
        if r.hkl != self.measured_hkl || r.hkl.len() != self.centres.len() {
            return Err(sc::Error("Native reduction changed crossing order or identity after measurement; refusing positional row mapping.".into()));
        }
        if let Some(mut a) = self.audit.take() {
            let n = r.hkl.len();
            a.i(
                "hkl",
                &[n, 3],
                r.hkl.iter().flatten().map(|&v| i64::from(v)),
            );
            a.f("intensity", &[n], r.values.iter().map(|v| v[0]));
            a.f("sigma", &[n], r.values.iter().map(|v| v[1]));
            a.f(
                "statistical_sigma",
                &[n],
                r.statistical_sigma.iter().copied(),
            );
            a.f("physical", &[n], r.physical.iter().copied());
            a.f("empirical", &[n], r.empirical.iter().copied());
            a.u("flags", &r.flags);
            a.b("use", &[n], &r.use_mask);
            a.b("visible", &[n], &r.visible);
            a.f(
                "raw_profiles",
                &[n, 10],
                r.profiles.iter().flatten().copied(),
            );
            a.f(
                "parameters",
                &[n, 5],
                r.parameters.iter().flatten().copied(),
            );
            a.i("choices", &[n], r.choices.iter().map(|&v| i64::from(v)));
            self.audit_directory = Some(a.finish().map_err(sc::Error)?);
        }
        self.rows = r
            .hkl
            .iter()
            .enumerate()
            .map(|(id, h)| Reflection {
                hkl: h.map(i64::from),
                omega: self.centres[id][2],
                intensity: r.values[id][0],
                sigma: r.values[id][1],
                flags: r.flags[id],
                native_use: Some(r.use_mask[id]),
                track: None,
                crossing: Some(id),
                correction: r.physical[id] * r.empirical[id],
            })
            .collect();
        self.report = json!({"recipe":"PhaseSmith orthorhombic-v1","engine":ENGINE,"integration":"predicted crossings, guarded-plane background, independently learned 3D profiles","scaling":"native robust per-frame/detector/ray family scaling; equivalent-error floor","converged":r.scaling.converged,"errorFloor":r.error_floor,"rows":r.hkl.len(),"used":r.use_mask.iter().filter(|&&v|v).count(),"warningPolicy":"Retain native profile MISMATCH (131072); every other flag and centre-visibility failure excludes. No significance cut.","controls":{"pixelRadius":7,"omegaHalfWidth":4.5,"polarization":0.98,"gain":1.,"readNoise":0.,"backgroundMargin":6,"backgroundGap":3,"profileGrid":[31,31,23],"profileSteps":[0.0125,0.0125,0.05],"teacherSNR":20.,"minimumTeachers":8,"shapeFitIterations":80,"linkRadius":5}});
        self.checkpoint_complete = true;
        Err(sc::Error(CHECKPOINT.into()))
    }
}
impl Crystal {
    pub(super) fn protocol_range(&self) -> Result<(usize, usize), String> {
        if !self.mask.is_empty() || self.tracks.iter().any(|t| t.excluded) {
            return Err("This versioned profile recipe does not accept manual rectangles/track exclusions. Clear them or select summation; they will never be silently ignored.".into());
        }
        let first = (0..self.sources.len())
            .find(|i| !self.excluded_frames.contains(i))
            .ok_or("All frames excluded.")?;
        let last = (0..self.sources.len())
            .rfind(|i| !self.excluded_frames.contains(i))
            .unwrap();
        if (first..=last).any(|i| self.excluded_frames.contains(&i)) {
            return Err("Profile recipe requires a contiguous selected exposure range; interior excluded frames are unsupported.".into());
        }
        if self.config.integration_method == "profile"
            && let Some(p) = &self.config.protocol
        {
            let declared = (
                protocol::integer(p, "acquisition", "first_frame")?,
                protocol::integer(p, "acquisition", "last_frame_inclusive")?,
            );
            if declared != (first, last) {
                return Err("Selected frames disagree with the declared protocol interval. Apply the intended first/last frame in Frames before running or exporting.".into());
            }
        }
        Ok((first, last))
    }
    pub(super) fn profile_run(
        &mut self,
        control: &Control,
        target: usize,
    ) -> Result<String, String> {
        let c = &self.config;
        let metric = c
            .metric
            .ok_or("Profile recipe needs an explicit orthorhombic metric in Geometry.")?;
        let elements: Vec<_> = c
            .elements
            .split(|x: char| x == ',' || x.is_whitespace())
            .filter(|x| !x.is_empty())
            .map(str::to_owned)
            .collect();
        if elements.is_empty() {
            return Err("Enter declared element symbols in Structure before using the profile recipe; no atom counts or model are needed.".into());
        }
        if !c.dac_enabled || !c.seat_enabled {
            return Err("Profile recipe requires explicitly configured DAC and seat/illumination masks in Background.".into());
        }
        let (first, last) = self.protocol_range()?;
        if c.background
            || c.scan_scaling
            || c.gain != 1.
            || c.read_noise != 0.
            || c.aperture_radius != 7
            || c.omega_radius != 4.5
            || c.polarization != 0.98
            || !c.refine_geometry
            || c.threshold != 5.
            || c.min_pixels != 3
            || c.link_radius != 5.
        {
            return Err("Profile recipe uses frozen controls: original counts, gain 1, read noise 0, threshold 5, minimum area 3, link radius 5, spatial half-width 7 px, rocking half-width 4.5°, polarization 0.98, geometry refinement, native family scaling; disable omega baseline and the separate log-linear scale. Choose summation for other controls.".into());
        }
        let mut geometry = self
            .initial_geometry
            .ok_or("Load a detector calibration.")?
            .native();
        geometry.axis = c.axis;
        let p = c.active_protocol(first, last)?;
        let pi = |section: &str, name: &str| protocol::integer(&p, section, name);
        let pn = |section: &str, name: &str| protocol::number(&p, section, name);
        let cancellation = solution::Cancellation::default();
        let options = sc::Options {
            discovery: None,
            acquisition: sc::Acquisition {
                first, last, omega_zero: c.omega_start, omega_step: c.omega_step,
                exposure: c.exposure, vertical_flip: true,
                reserved_minimum: profile_reserved_minimum(c.saturation),
            },
            geometry,
            priors: sc::Priors {
                cell: phasesmith_crystallography::UnitCell {
                    a_angstrom: metric[0], b_angstrom: metric[1], c_angstrom: metric[2],
                    alpha_deg: metric[3], beta_deg: metric[4], gamma_deg: metric[5],
                },
                group: Some(phasesmith_io::space_group_by_number(i32::from(c.group)).map_err(err)?.space_group),
                elements,
                provenance: "User-declared cell, symmetry, element symbols and cell-shadow assumptions; no atomic model or reference intensities".into(),
            },
            null_rotations: serde_json::from_str(include_str!("../data/scxrd-null-rotations-v1.json")).map_err(err)?,
            shadows: sc::ShadowOptions {
                illumination_block: c.shadow_block,
                illumination: spots::frame_validity::SeatOptions {
                    threshold: c.seat_threshold, guard_pixels: c.seat_guard,
                    ..Default::default()
                },
                aperture_block: c.shadow_block,
                aperture: spots::frame_validity::DacOptions {
                    axis_at_zero: c.dac_axis, half_opening_degrees: c.dac_half_opening,
                },
            },
            mask_workers: pi("acquisition","workers")?, preparation_workers: pi("frame_input_execution","native_preparation_workers")?, preparation_batch: pi("frame_input_execution","batch_frames")?,
            max_in_flight_frame_bytes: pi("frame_preparation_execution","max_in_flight_bytes")?,
            cancellation: cancellation.clone(), detection_workers: p["detection_workers"].as_u64().ok_or("Protocol detection_workers missing")? as usize,
            profile_workers: pi("reduction","shape_fit_workers")?, learning_workers: pi("profile_execution","workers")?, frame_workers: pi("frame_preparation_execution","workers")?,
            geometry_cache_bytes: pi("profile_execution","geometry_cache_bytes")?, frame_payload_bytes: pi("frame_input_execution","payload_bytes")?,
            max_samples: 20_000_000, search_seconds: pn("search","native_seconds")?,
            dense_memory_bytes: pi("search","dense_memory_budget_bytes")?, search_trials: pi("search","trials")?, search_cycles: pi("search","cycles")?, seed: pi("search","seed")? as u64,
        };
        let mut capture = Capture {
            control: Some(control),
            audit: if c.keep_stage_audit {
                Some(audit::Audit::new()?)
            } else {
                None
            },
            first,
            last,
            stop_after: match target {
                0 => "shadow_masks",
                1 => "detection_linking",
                2 | 3 => "indexing_geometry",
                _ => "profile_fitting_scaling",
            },
            ..Default::default()
        };
        control.publish(json!({"running":true,"label":"PhaseSmith profile recipe · preparing original-count masks"}));
        let done = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let result = std::thread::scope(|scope| {
            let flag = done.clone();
            let token = cancellation.clone();
            scope.spawn(move || {
                while !flag.load(std::sync::atomic::Ordering::Acquire) {
                    if control.check().is_err() {
                        let _ = token.cancel();
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(20));
                }
            });
            let _completion = super::processing::SearchCompletion(done.clone());
            let result = sc::run(&mut OriginalSource(self), &options, &mut capture);
            done.store(true, std::sync::atomic::Ordering::Release);
            result
        });
        control.check()?;
        match result {
            Err(e) if e.0 == CHECKPOINT && capture.checkpoint_complete => {
                if target < 4 && !capture.rows.is_empty() {
                    return Err("Native checkpoint name changed; refusing to mark a full reduction as an early checkpoint.".into());
                }
            }
            Err(e) => return Err(e.to_string()),
            Ok(_) => {
                return Err(
                    "Profile coordinator unexpectedly crossed the reduction checkpoint.".into(),
                );
            }
        }
        if target < 4
            && let Some(a) = capture.audit.take()
        {
            capture.audit_directory = Some(a.finish()?);
        }
        let completed = match target {
            0 => 0,
            1 => 1,
            2 | 3 => 3,
            _ => 5,
        };
        // Commit checkpoint products only after assessment and cancellation checks.
        let mut next = self.clone();
        next.shadows = capture.shadows;
        next.background = None;
        if completed >= 1 {
            next.peaks = capture.peaks;
            next.tracks = capture.tracks;
            next.track_offset = 0;
        }
        if completed >= 3 {
            next.cells = vec![
                capture
                    .cell
                    .ok_or("Native fit did not supply validated cell evidence.")?,
            ];
            next.selected = Some(0);
            next.basis = capture.basis;
            next.geometry = capture.geometry;
            next.geometry_report = capture.geometry_report;
        }
        let used = capture.rows.iter().filter(|r| r.usable()).count();
        if completed >= 4 {
            next.reflections = capture.rows;
            next.unscaled_reflections = next.reflections.clone();
            next.reflection_offset = 0;
        }
        next.profile_options = Some(Arc::new(options));
        next.profile_audit = capture.audit_directory;
        next.profile_report = if completed >= 4 {
            capture.report
        } else {
            json!({"recipe":"PhaseSmith orthorhombic-v1","checkpoint":completed})
        };
        next.profile_report["auditAvailable"] = json!(next.profile_audit.is_some());
        let protocol_bytes = serde_json::to_vec(&p).map_err(err)?;
        next.profile_report["effectiveProtocol"] = p;
        next.profile_report["maxSamples"] = json!(20_000_000);
        next.profile_report["validationScope"] = json!({"runtime":"Pinned coordinator enforces frame hashes, >=40 profile teachers, >=1000 usable observations, withheld xy<=1px and omega<=0.3deg. Geometry convergence and bounds are enforced upstream; conditioning/correlation remain reported diagnostics.","referenceGrading":"Reference atom counts and coordinate-error gates are not evaluated in Dioptas; no reference structure enters this worker."});
        let identity = json!({"protocol":next.profile_report["effectiveProtocol"],"initialGeometry":next.initial_geometry,"metric":next.config.metric,"group":next.config.group,"elements":next.config.elements,"sourceHashes":next.shadows.as_ref().map(|s|&s.report["sourceHashes"]),"maxSamples":20_000_000});
        next.profile_report["runIdentitySha256"] = json!(format!(
            "{:x}",
            Sha256::digest(serde_json::to_vec(&identity).map_err(err)?)
        ));

        next.profile_report["protocolSha256"] =
            json!(format!("{:x}", Sha256::digest(protocol_bytes)));
        for (i, detail) in [
            "Standalone shared cell-seat/DAC masks; omega baseline disabled",
            "Standalone original-count peak detection/linking",
            "Supplied metric indexed with native position gates",
            "Native pose/orientation refinement with family holdout",
            "Native predicted-crossing integration and learned profiles",
            "Native per-frame/detector/ray family scaling and equivalent-error model",
        ]
        .into_iter()
        .enumerate()
        .take(completed + 1)
        {
            next.stages[i] = Stage {
                status: "complete".into(),
                detail: detail.into(),
                seconds: 0.,
            };
        }
        if completed >= 4 {
            let detail = next.scale(control)?;
            next.stages[5].detail = detail;
        }
        control.check()?;
        *self = next;
        Ok(if completed >= 4 {
            format!(
                "{used} signed observations retained by the same native profile/visibility/scaling policy as standalone PhaseSmith. MISMATCH warnings preserved; no absorption correction."
            )
        } else {
            format!(
                "PhaseSmith protocol checkpoint complete: {}. All prerequisites used the same native coordinator.",
                self.stages[completed].detail
            )
        })
    }
}

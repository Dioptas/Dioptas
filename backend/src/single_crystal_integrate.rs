//! Integrate: every reflection of every kept lattice measured on the frames it
//! crosses, whether or not Find spots detected it.
//!
//! The science is PhaseSmith's public `measurement` module: prediction of
//! every centring-allowed reflection to the resolution limit that crosses the
//! Ewald sphere inside the scan and lands on the detector, shoebox summation
//! with a local background plane (and optionally profile fitting), the
//! quality flags, the Lorentz-polarisation correction, the rocking-width and
//! spot-size estimate and the merging statistics in the holohedry of the
//! lattice. Dioptas supplies the inputs (refined pose, refined conventional
//! cells, frames with their masks, the scan) and keeps the product: the
//! unmerged reflection list per lattice with its statistics, the match
//! against Find spots, the panel, the overlay and the HKL export.
//!
//! Reflections whose centre pixel is masked on its centre frame (DAC body,
//! seat, gaps, diamond spots) or whose centre frame is excluded are counted
//! as "under masks" and left out of the list.
use super::*;
use phasesmith_single_crystal::lattice_symmetry::Bravais;
use phasesmith_single_crystal::measurement as ps;

/// Flag names in bit order, as the snapshot and the export name them.
pub(super) const FLAG_NAMES: [(u32, &str); 11] = ps::FLAG_NAMES;
/// Profile flag names in bit order.
pub(super) const PROFILE_FLAG_NAMES: [(u32, &str); 11] = ps::PROFILE_FLAG_NAMES;
/// Names of the profile flags set.
fn profile_reasons(flags: u32) -> String {
    PROFILE_FLAG_NAMES
        .iter()
        .filter(|(bit, _)| flags & bit != 0)
        .map(|(_, name)| *name)
        .collect::<Vec<_>>()
        .join(", ")
}
/// Rows per table page.
pub(super) const PAGE: usize = 100;
/// Profile fitting when the user has not chosen (see `integrate.md` for the
/// enstatite comparison behind it).
pub(super) const PROFILES_DEFAULT: bool = true;

pub(super) const D_MIN_RANGE: (f64, f64) = (0.2, 50.);
pub(super) const BOX_RANGE: (usize, usize) = (3, 41);
pub(super) const ROCKING_RANGE: (f64, f64) = (0.01, 20.);

/// Integration settings in effect.
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Settings {
    /// Resolution limit, Å.
    pub d_min: f64,
    /// Side of the square peak box, pixels (odd).
    pub box_size: usize,
    /// Full width in ω of the rocking window for |ζ| = 1, degrees.
    pub rocking: f64,
    /// Profile intensity where the fit is usable, summation elsewhere.
    #[serde(default)]
    pub profiles: bool,
    /// The derived rocking width is the step floor (the spots fit within
    /// one frame), not a measured spread.
    #[serde(default)]
    pub rocking_floor: bool,
}

/// Rocking width and spot size PhaseSmith estimated from the frames
/// (`estimate_shape`); kept until the lattices or the pose change.
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Shape {
    pub rocking: f64,
    pub rocking_sigma: f64,
    pub box_size: Option<usize>,
    pub spot_sigma: Option<[f64; 2]>,
    pub reflections: usize,
    #[serde(default)]
    pub at_step_floor: bool,
}
impl Shape {
    fn from(e: &ps::ShapeEstimate) -> Self {
        Self {
            rocking: e.rocking_width,
            rocking_sigma: e.rocking_sigma,
            box_size: e.box_size,
            spot_sigma: e.spot_sigma,
            reflections: e.reflections,
            at_step_floor: e.at_step_floor,
        }
    }
}

/// A profile-fitted intensity, Lorentz-polarisation corrected.
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Fit {
    pub intensity: f64,
    pub sigma: f64,
    /// PhaseSmith profile flags (0 usable).
    pub flags: u32,
}

/// One measured reflection.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Row {
    pub hkl: [i64; 3],
    /// Predicted x, y (pixels) and ω (degrees).
    pub xyz: V3,
    pub d: f64,
    /// The intensity in use (profile where `profiled`, else summation),
    /// Lorentz-polarisation corrected; NaN when not measured.
    pub intensity: f64,
    pub sigma: f64,
    /// Summation flags.
    pub flags: u32,
    /// First and last frame of the rocking window.
    pub frames: [usize; 2],
    /// Lorentz-polarisation factor applied (NaN when singular).
    pub correction: f64,
    /// Summation intensity and σ, corrected.
    #[serde(default)]
    pub summed: [f64; 2],
    /// Profile-fitted intensity, when profiles were fitted.
    #[serde(default)]
    pub profile: Option<Fit>,
    /// The intensity in use is the profile one.
    #[serde(default)]
    pub profiled: bool,
}
impl Row {
    pub(super) fn measured(&self) -> bool {
        self.intensity.is_finite() && self.sigma.is_finite()
    }
    pub(super) fn usable(&self) -> bool {
        (self.profiled || self.flags == 0) && self.measured() && self.sigma > 0.
    }
}

/// R_int within a group of shells or intensity bins.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Bin {
    /// Bin limits: d (Å, high to low) for shells, mean I/σ for bins.
    pub limits: [f64; 2],
    pub r_int: Option<f64>,
    /// Reflections in groups of two or more.
    pub reflections: usize,
}

/// Statistics of one lattice's reflections.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub(super) struct Stats {
    /// Crossings inside the scan, on the detector and not under masks.
    pub predicted: usize,
    /// Crossings whose centre is masked or on an excluded frame.
    pub hidden: usize,
    /// With an intensity.
    pub measured: usize,
    /// Measured and usable.
    pub usable: usize,
    /// Usable with I/σ > 3.
    pub strong: usize,
    /// Usable rows whose intensity is the profile-fitted one.
    #[serde(default)]
    pub profiled: usize,
    /// Profile fitting: none, "fitted" or why it failed.
    #[serde(default)]
    pub profile: Option<String>,
    /// Largest and smallest d of the usable reflections, Å.
    pub d_range: [f64; 2],
    /// Laue class used for equivalents.
    pub laue: String,
    pub r_int: Option<f64>,
    /// Usable reflections per unique reflection measured.
    pub redundancy: f64,
    /// Unique reflections with a usable measurement / unique reflections
    /// allowed by the centring to the resolution limit.
    pub completeness: f64,
    pub unique: usize,
    pub possible: usize,
    /// Count per flag, in [`FLAG_NAMES`] order.
    pub flags: Vec<usize>,
    /// Why fitted profiles were not used: count per profile flag (in
    /// [`PROFILE_FLAG_NAMES`] order) over usable rows with a profile value
    /// that use the summed one.
    #[serde(default)]
    pub profile_flags: Vec<usize>,
    /// Usable reflections a detected spot lies on (Find spots).
    pub detected: usize,
    /// Of those, the ones with I/σ > 3.
    #[serde(default)]
    pub detected_strong: usize,
    /// Median distance of predicted position and detected centroid of the
    /// strong reflections (I/σ > 10) a spot lies on, pixels.
    pub offset: Option<f64>,
    pub shells: Vec<Bin>,
    pub bins: Vec<Bin>,
}

fn bin(b: &ps::MergingBin) -> Bin {
    Bin {
        limits: b.limits,
        r_int: b.r_int,
        reflections: b.multiples,
    }
}

/// Counts and merging statistics (PhaseSmith, holohedry of the lattice) of
/// one lattice's rows.
fn statistics(rows: &[Row], lattice: &ps::Lattice, d_min: f64) -> Result<Stats, String> {
    let usable: Vec<&Row> = rows.iter().filter(|r| r.usable()).collect();
    let d = usable.iter().map(|r| r.d);
    let mut stats = Stats {
        predicted: rows.len(),
        measured: rows.iter().filter(|r| r.measured()).count(),
        usable: usable.len(),
        strong: usable.iter().filter(|r| r.intensity > 3. * r.sigma).count(),
        profiled: usable.iter().filter(|r| r.profiled).count(),
        d_range: if usable.is_empty() {
            [0.; 2]
        } else {
            [
                d.clone().fold(0., f64::max),
                d.fold(f64::INFINITY, f64::min),
            ]
        },
        laue: lattice.bravais().system().laue_symbol().into(),
        flags: FLAG_NAMES
            .iter()
            .map(|(bit, _)| rows.iter().filter(|r| r.flags & bit != 0).count())
            .collect(),
        profile_flags: PROFILE_FLAG_NAMES
            .iter()
            .map(|(bit, _)| {
                rows.iter()
                    .filter(|r| {
                        r.usable() && !r.profiled && r.profile.is_some_and(|p| p.flags & bit != 0)
                    })
                    .count()
            })
            .collect(),
        ..Stats::default()
    };
    if usable.is_empty() {
        return Ok(stats);
    }
    let observations: Vec<ps::Observation> = usable
        .iter()
        .map(|r| ps::Observation::new(r.hkl, r.intensity, r.sigma, r.d))
        .collect();
    let mut options = ps::MergingOptions::default();
    options.d_min = Some(d_min);
    options.lattice = Some(*lattice);
    let m = ps::merging_statistics(&observations, &lattice.bravais().holohedry(), &options)
        .map_err(err)?;
    stats.r_int = m.overall.r_int;
    stats.redundancy = m.overall.redundancy;
    stats.completeness = m.overall.completeness.unwrap_or(0.);
    stats.unique = m.overall.unique;
    stats.possible = m.overall.possible.unwrap_or(0);
    stats.shells = m.shells.iter().map(bin).collect();
    stats.bins = m.signal.iter().map(bin).collect();
    Ok(stats)
}

/// Integrate product of one lattice.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Lattice {
    /// Row in Find lattices.
    pub lattice: usize,
    pub bravais: String,
    pub cell: [f64; 6],
    pub cell_su: [f64; 6],
    /// Measured crossings (those under masks left out), in ω order.
    pub rows: Vec<Row>,
    pub stats: Stats,
}

/// Integrate product.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Integration {
    pub settings: Settings,
    pub lattices: Vec<Lattice>,
}

/// Reflection table position (view only).
#[derive(Clone, Debug, Default)]
pub(super) struct Table {
    pub lattice: usize,
    pub offset: usize,
    /// "all", "usable" or "flagged".
    pub filter: String,
}

/// Short flag letters for the table.
pub(super) fn flag_letters(flags: u32) -> String {
    [
        (ps::EDGE, 'E'),
        (ps::MASKED, 'M'),
        (ps::SATURATED, 'S'),
        (ps::OVERLAP, 'O'),
        (ps::BACKGROUND | ps::MODEL, 'B'),
        (ps::BOUNDARY, 'W'),
        (ps::AXIAL, 'A'),
        (ps::PARTIAL, 'P'),
        (ps::NO_DATA, 'N'),
    ]
    .iter()
    .filter(|(bit, _)| flags & bit != 0)
    .map(|(_, c)| *c)
    .collect()
}

fn median(mut v: Vec<f64>) -> Option<f64> {
    if v.is_empty() {
        return None;
    }
    v.sort_by(f64::total_cmp);
    Some(v[v.len() / 2])
}
fn odd(n: usize) -> usize {
    if n.is_multiple_of(2) { n + 1 } else { n }
}
fn round_up(v: f64) -> f64 {
    (v * 100.).ceil() / 100.
}
/// Progress and cancel for PhaseSmith.
fn monitor(control: &Control) -> impl Fn(ps::Stage, usize, usize) -> bool + Sync + '_ {
    move |stage, done, total| {
        let label = match stage {
            ps::Stage::LearningProfiles => "Learning profiles",
            ps::Stage::FittingProfiles => "Fitting profiles",
            _ => "Integrating",
        };
        control.publish(json!({"running":true,"current":done,"total":total,"label":label}));
        control.check().is_ok()
    }
}
/// A PhaseSmith error as the step reports it: Dioptas' own cancel message,
/// the frame that could not be read, or PhaseSmith's message.
fn failure(control: &Control, e: phasesmith_single_crystal::spots::SpotError) -> String {
    match ps::error_kind(&e) {
        ps::ErrorKind::Cancelled => control
            .check()
            .err()
            .unwrap_or_else(|| "Integrate was cancelled.".into()),
        ps::ErrorKind::FrameRead => format!("Integrate could not read a frame ({}).", e.0),
        _ => format!("Integrate failed: {}", e.0),
    }
}
fn scan_of(c: &Config, frames: usize, excluded: &[usize]) -> Result<ps::Scan, String> {
    ps::Scan::new(c.omega_start, c.omega_step, c.exposure, frames)
        .and_then(|s| s.with_excluded(excluded.to_vec()))
        .map_err(err)
}

impl Crystal {
    /// Settings derived from the data: the resolution at the farthest
    /// detector corner and PhaseSmith's estimate of rocking width and box
    /// from the frames once Integrate has run, before that the rocking width
    /// from the Find spots tracks and PhaseSmith's default box.
    pub(super) fn integration_defaults(&self) -> Option<Settings> {
        let g = self.pose_geometry()?.native();
        if self.shape.contains(&0) {
            return None;
        }
        let d_min =
            round_up(ps::detector_resolution(&g, self.shape)).clamp(D_MIN_RANGE.0, D_MIN_RANGE.1);
        let (rocking, rocking_floor) = match self.integration_shape {
            Some(s) => (s.rocking, s.at_step_floor),
            None => self
                .track_rocking(&g)
                .map_or((self.config.omega_step, true), |e| {
                    (e.rocking_width, e.at_step_floor)
                }),
        };
        let box_size = self
            .integration_shape
            .and_then(|s| s.box_size)
            .unwrap_or(ps::MeasureOptions::default().box_size);
        Some(Settings {
            d_min,
            box_size: odd(box_size).clamp(BOX_RANGE.0, BOX_RANGE.1),
            rocking: round_up(rocking).clamp(ROCKING_RANGE.0, ROCKING_RANGE.1),
            profiles: PROFILES_DEFAULT,
            rocking_floor,
        })
    }
    /// Rocking width from the spread in ω of the Find spots tracks
    /// (PhaseSmith `estimate_rocking_from_tracks`).
    fn track_rocking(&self, g: &reciprocal::Geometry) -> Option<ps::ShapeEstimate> {
        let usable = |t: &Track| !t.excluded && t.flags == 0;
        let mut groups: BTreeMap<usize, Vec<[f64; 4]>> = BTreeMap::new();
        for p in &self.peaks {
            if self.tracks.get(p.track).is_some_and(usable) {
                let omega = self.config.omega_start
                    + p.frame as f64 * self.config.omega_step
                    + self.config.exposure / 2.;
                groups.entry(p.track).or_default().push([
                    p.xy[0],
                    p.xy[1],
                    omega,
                    p.intensity.max(1e-9),
                ]);
            }
        }
        let tracks: Vec<Vec<[f64; 4]>> = groups.into_values().collect();
        let scan = scan_of(&self.config, self.sources.len().max(1), &[]).ok()?;
        ps::estimate_rocking_from_tracks(&tracks, g, &scan).ok()
    }
    /// The settings in effect: the user's where set, else the defaults.
    pub(super) fn integration_settings(&self) -> Option<Settings> {
        let d = self.integration_defaults()?;
        Some(Settings {
            d_min: self.config.integration_d_min.unwrap_or(d.d_min),
            box_size: self.config.integration_box.unwrap_or(d.box_size),
            rocking: self.config.rocking_width.unwrap_or(d.rocking),
            profiles: self.config.profile_fitting.unwrap_or(d.profiles),
            rocking_floor: d.rocking_floor && self.config.rocking_width.is_none(),
        })
    }
    /// One frame for measurement: saturated pixels stay unmasked (flagged by
    /// the measurement), gaps and every mask of the frame are left out.
    fn measurement_frame(&self, frame: usize) -> Result<ps::Frame, String> {
        let mut values = self.read(frame)?;
        let saturation = self.config.saturation;
        // u32::MAX marks gaps and dead pixels, never a count. Saturated
        // pixels are set aside while the masks are made (no second frame).
        let saturated: Vec<(usize, f64)> = values
            .iter()
            .enumerate()
            .filter(|(_, v)| **v >= saturation && **v < f64::from(u32::MAX))
            .map(|(i, v)| (i, *v))
            .collect();
        for &(i, _) in &saturated {
            values[i] = 0.;
        }
        let mask = self.mask_for(&values, frame);
        for (i, v) in saturated {
            values[i] = v;
        }
        Ok(ps::Frame::new(values, mask))
    }
    /// The frames as PhaseSmith reads them.
    fn frame_reader(
        &self,
    ) -> impl Fn(usize) -> Result<ps::Frame, phasesmith_single_crystal::spots::SpotError> + Sync + '_
    {
        |f| {
            self.measurement_frame(f)
                .map_err(phasesmith_single_crystal::spots::SpotError)
        }
    }
    /// PhaseSmith measurement options from the config and the settings; the
    /// measurement runs in the caller's (Dioptas') worker pool.
    fn measure_options(&self, settings: &Settings) -> ps::MeasureOptions {
        let mut options = ps::MeasureOptions::default();
        options.noise.gain = self.config.gain;
        options.noise.read_noise = self.config.read_noise;
        options.noise.saturation = Some(self.config.saturation);
        options.polarization = ps::Polarization::new(self.config.polarization, [0., 1., 0.]);
        options.workers = 0;
        options.box_size = settings.box_size;
        options.profile = settings.profiles.then(ps::ProfileOptions::default);
        options
    }
    /// Predict and measure every reflection of the lattices with these
    /// settings, in Dioptas' worker pool.
    fn measure_with(
        &self,
        g: &reciprocal::Geometry,
        scan: &ps::Scan,
        lattices: &[ps::Lattice],
        settings: &Settings,
        control: &Control,
    ) -> Result<ps::Measurement, String> {
        control.publish(json!({"running":true,"label":"Predicting reflections"}));
        let predict = ps::PredictOptions::new(settings.d_min, settings.rocking);
        let reflections = ps::predict(lattices, g, scan, self.shape, &predict, None)
            .map_err(|e| format!("{}; raise the resolution limit.", err(e)))?;
        control.check()?;
        let options = self.measure_options(settings);
        let reader = self.frame_reader();
        crate::worker_pool::install(|| {
            ps::measure(
                &reader,
                g,
                scan,
                self.shape,
                &reflections,
                &options,
                &monitor(control),
            )
        })
        .map_err(|e| failure(control, e))
    }
    /// Stage 5: predict and measure every reflection of every refined lattice
    /// with PhaseSmith.
    pub(super) fn integrate(&mut self, control: &Control) -> Result<String, String> {
        self.integration = None;
        let g = self
            .pose_geometry()
            .ok_or("Load a PONI calibration in Frames first.")?
            .native();
        let mut kept = Vec::new();
        let mut lattices = Vec::new();
        for refined in &self.refined {
            let Some(r) = &refined.result else { continue };
            let bravais = Bravais::from_symbol(&r.bravais)
                .ok_or_else(|| format!("Unknown lattice type {}.", r.bravais))?;
            lattices.push(ps::Lattice::new(r.conventional, bravais).map_err(err)?);
            kept.push((refined.lattice, r.clone()));
        }
        if lattices.is_empty() {
            return Err("No refined lattice. Run Refine lattice first.".into());
        }
        let scan = scan_of(&self.config, self.sources.len(), &self.excluded_frames)?;
        // Rocking width and box from the frames, once, unless both are set.
        let estimate = self.integration_shape.is_none()
            && (self.config.integration_box.is_none() || self.config.rocking_width.is_none());
        let mut settings = self
            .integration_settings()
            .ok_or("Load a PONI calibration in Frames first.")?;
        let mut measured = self.measure_with(&g, &scan, &lattices, &settings, control)?;
        if estimate {
            // With profiles, the measurement's own partials (margin frames
            // included) give the estimate without a second pass, unless the
            // window or box may have cut the spots (a suggestion as large as
            // what was used); then PhaseSmith's wide-window estimate.
            let from_partials = settings
                .profiles
                .then(|| ps::estimate_shape_from_partials(&measured, &scan).ok())
                .flatten()
                .filter(|e| {
                    round_up(e.rocking_width) <= settings.rocking
                        && e.box_size.is_none_or(|b| b <= settings.box_size)
                });
            let shape = match from_partials {
                Some(e) => Some(e),
                None => {
                    control.publish(json!({"running":true,"label":"Estimating spot shape"}));
                    let mut options = self.measure_options(&settings);
                    options.profile = None;
                    let reader = self.frame_reader();
                    let estimated = crate::worker_pool::install(|| {
                        ps::estimate_shape(
                            &reader,
                            &g,
                            &scan,
                            self.shape,
                            &lattices,
                            settings.d_min,
                            &options,
                            &monitor(control),
                        )
                    });
                    match estimated {
                        Ok(e) => Some(e),
                        Err(e) if ps::error_kind(&e) == ps::ErrorKind::Other => None,
                        Err(e) => return Err(failure(control, e)),
                    }
                }
            };
            // Too few reflections to estimate: the track estimate stays.
            if let Some(e) = shape {
                self.integration_shape = Some(Shape::from(&e));
                let updated = self
                    .integration_settings()
                    .ok_or("Load a PONI calibration in Frames first.")?;
                if (updated.box_size, updated.rocking) != (settings.box_size, settings.rocking) {
                    measured = self.measure_with(&g, &scan, &lattices, &updated, control)?;
                }
                settings = updated;
            }
        }
        let profile = match &measured.profile {
            ps::ProfileStatus::Fitted(m) => Some(format!("fitted ({} teachers)", m.teachers)),
            ps::ProfileStatus::Failed(why) => Some(format!("failed: {why}")),
            _ => None,
        };
        let mut rows: Vec<Vec<Row>> = vec![Vec::new(); lattices.len()];
        let mut hidden = vec![0; lattices.len()];
        for m in &measured.reflections {
            let r = &m.reflection;
            if m.flags & ps::HIDDEN != 0 {
                hidden[r.lattice] += 1;
                continue;
            }
            let summed = m.corrected_summation();
            let profile = m.corrected_profile().zip(m.profile).map(|(i, p)| Fit {
                intensity: i.value,
                sigma: i.sigma,
                flags: p.flags,
            });
            let profiled = settings.profiles && m.profile_usable() && profile.is_some();
            let chosen = if profiled {
                profile.map(|p| [p.intensity, p.sigma])
            } else {
                None
            }
            .unwrap_or([summed.value, summed.sigma]);
            rows[r.lattice].push(Row {
                hkl: r.hkl,
                xyz: r.xyz,
                d: r.d,
                intensity: chosen[0],
                sigma: chosen[1],
                flags: m.flags,
                frames: r.frames,
                correction: m.corrections.map_or(f64::NAN, |c| c.factor),
                summed: [summed.value, summed.sigma],
                profile,
                profiled,
            });
        }
        let detected = self.detected_spots();
        let mut out = Vec::new();
        for (((index, r), rows), (lattice, hidden)) in
            kept.into_iter().zip(rows).zip(lattices.iter().zip(hidden))
        {
            let mut stats = statistics(&rows, lattice, settings.d_min)?;
            stats.hidden = hidden;
            stats.profile.clone_from(&profile);
            (stats.detected, stats.detected_strong, stats.offset) =
                matched(&rows, &detected, &scan);
            out.push(Lattice {
                lattice: index,
                bravais: r.bravais,
                cell: r.cell,
                cell_su: r.cell_su,
                rows,
                stats,
            });
        }
        let integration = Integration {
            settings,
            lattices: out,
        };
        let detail = integration.detail();
        self.integration = Some(integration);
        self.adopt_integration();
        Ok(detail)
    }
    /// Observed spots (x, y, ω) of the unflagged and the masked-aperture
    /// tracks, for matching predictions with detections.
    fn detected_spots(&self) -> Vec<V3> {
        self.tracks
            .iter()
            .filter(|t| !t.excluded && t.flags & !spots::MASKED == 0)
            .map(|t| t.observed)
            .collect()
    }
    /// The older later steps (scaling, structure search) read the first kept
    /// lattice's reflections in their earlier record.
    pub(super) fn adopt_integration(&mut self) {
        let rows = self.integration.as_ref().and_then(|i| {
            i.lattices
                .iter()
                .find(|l| Some(l.lattice) == self.selected)
                .or(i.lattices.first())
        });
        let reflections: Vec<Reflection> = rows
            .map(|l| {
                l.rows
                    .iter()
                    .enumerate()
                    .filter(|(_, r)| r.measured())
                    .map(|(i, r)| Reflection {
                        hkl: r.hkl,
                        omega: r.xyz[2],
                        intensity: r.intensity,
                        sigma: r.sigma,
                        flags: if r.usable() { 0 } else { r.flags.max(1) },
                        track: None,
                        crossing: Some(i),
                        correction: r.correction,
                        native_use: None,
                    })
                    .collect()
            })
            .unwrap_or_default();
        self.unscaled_reflections = reflections.clone();
        self.reflections = reflections;
        self.reflection_offset = 0;
    }
    /// Predicted positions on the shown frame (each crossing on the frame of
    /// its predicted ω): x, y, lattice row and usable.
    pub(super) fn integrated_markers(&self) -> Vec<Value> {
        let Some(i) = &self.integration else {
            return vec![];
        };
        let Ok(scan) = scan_of(&self.config, self.sources.len().max(1), &[]) else {
            return vec![];
        };
        i.lattices
            .iter()
            .flat_map(|l| {
                l.rows
                    .iter()
                    .filter(|r| scan.frame_of(r.xyz[2]) == self.frame)
                    .map(|r| json!({"x":r.xyz[0],"y":r.xyz[1],"lattice":l.lattice,"usable":r.usable()}))
            })
            .take(20000)
            .collect()
    }
    /// Summary for the snapshot (no reflection lists).
    pub(super) fn integration_summary(&self) -> Value {
        let defaults = self.integration_defaults();
        let lattices: Vec<Value> = self
            .integration
            .iter()
            .flat_map(|i| &i.lattices)
            .map(|l| json!({"lattice":l.lattice,"bravais":l.bravais,"cell":l.cell,"stats":l.stats}))
            .collect();
        json!({
            "defaults": defaults,
            "settings": self.integration.as_ref().map(|i| i.settings),
            "lattices": lattices,
            "flagNames": FLAG_NAMES.iter().map(|f| f.1).collect::<Vec<_>>(),
            "profileFlagNames": PROFILE_FLAG_NAMES.iter().map(|f| f.1).collect::<Vec<_>>(),
        })
    }
    fn table_rows(&self) -> Vec<&Row> {
        let Some(l) = self.integration.as_ref().and_then(|i| {
            i.lattices
                .iter()
                .find(|l| l.lattice == self.integrated_table.lattice)
                .or(i.lattices.first())
        }) else {
            return vec![];
        };
        l.rows
            .iter()
            .filter(|r| match self.integrated_table.filter.as_str() {
                "usable" => r.usable(),
                "flagged" => !r.usable(),
                _ => true,
            })
            .collect()
    }
    /// One page of the reflection table: the intensity in use and both the
    /// summation and the profile value.
    pub(super) fn integrated_page(&self) -> Value {
        let rows = self.table_rows();
        let t = &self.integrated_table;
        let page: Vec<Value> = rows
            .iter()
            .skip(t.offset)
            .take(PAGE)
            .map(|r| {
                json!({
                    "hkl": r.hkl, "i": r.intensity, "sigma": r.sigma, "d": r.d, "omega": r.xyz[2],
                    "flags": r.flags, "letters": flag_letters(r.flags), "usable": r.usable(),
                    "summed": r.summed, "profile": r.profile.map(|p| [p.intensity, p.sigma]),
                    "profileFlags": r.profile.map(|p| p.flags), "profiled": r.profiled,
                    "profileWhy": r.profile.map(|p| profile_reasons(p.flags)),
                })
            })
            .collect();
        json!({"lattice":t.lattice,"offset":t.offset,"filter":if t.filter.is_empty(){"all"}else{&t.filter},"count":rows.len(),"rows":page})
    }
    /// Move the reflection table (lattice, filter, page).
    pub(super) fn set_integrated_table(&mut self, args: &Value) -> Result<(), String> {
        let i = self.integration.as_ref().ok_or("Run Integrate first.")?;
        let lattice = match args.get("lattice") {
            Some(v) => v.as_u64().ok_or("Choose a lattice.")? as usize,
            None => self.integrated_table.lattice,
        };
        if !i.lattices.iter().any(|l| l.lattice == lattice) {
            return Err("Lattice is not integrated.".into());
        }
        let filter = match args.get("filter") {
            Some(v) => v
                .as_str()
                .ok_or("Reflection filter must be text.")?
                .to_owned(),
            None => self.integrated_table.filter.clone(),
        };
        if !["", "all", "usable", "flagged"].contains(&filter.as_str()) {
            return Err("Unknown reflection filter.".into());
        }
        let offset = args["offset"].as_u64().unwrap_or(0) as usize;
        self.integrated_table = Table {
            lattice,
            offset: 0,
            filter,
        };
        let count = self.table_rows().len();
        if offset >= count && offset != 0 {
            return Err("Reflection page is out of range.".into());
        }
        self.integrated_table.offset = offset;
        Ok(())
    }
}

/// Usable rows a detected spot lies on (within 3 px and the rocking window
/// plus one frame), those with I/σ > 3, and the median offset of the strong
/// ones (I/σ > 10).
fn matched(rows: &[Row], spots: &[V3], scan: &ps::Scan) -> (usize, usize, Option<f64>) {
    let cell = 8.;
    let mut grid: BTreeMap<(i64, i64), Vec<usize>> = BTreeMap::new();
    for (i, s) in spots.iter().enumerate() {
        grid.entry(((s[0] / cell).floor() as i64, (s[1] / cell).floor() as i64))
            .or_default()
            .push(i);
    }
    let (mut count, mut strong, mut offsets) = (0, 0, Vec::new());
    for r in rows.iter().filter(|r| r.usable()) {
        let (gx, gy) = (
            (r.xyz[0] / cell).floor() as i64,
            (r.xyz[1] / cell).floor() as i64,
        );
        let lo = scan.bounds(r.frames[0])[0] - scan.step;
        let hi = scan.bounds(r.frames[1])[1] + scan.step;
        let mut best = f64::INFINITY;
        for dx in -1..=1 {
            for dy in -1..=1 {
                for &i in grid.get(&(gx + dx, gy + dy)).into_iter().flatten() {
                    let s = spots[i];
                    let d = (s[0] - r.xyz[0]).hypot(s[1] - r.xyz[1]);
                    if d <= 3. && s[2] >= lo && s[2] <= hi {
                        best = best.min(d);
                    }
                }
            }
        }
        if best.is_finite() {
            count += 1;
            strong += usize::from(r.intensity > 3. * r.sigma);
            if r.intensity > 10. * r.sigma {
                offsets.push(best);
            }
        }
    }
    (count, strong, median(offsets))
}

impl Integration {
    /// The step line: the first lattice, or a count over all.
    pub(super) fn detail(&self) -> String {
        let Some(first) = self.lattices.first() else {
            return "No lattice integrated.".into();
        };
        let s = &first.stats;
        let r = s
            .r_int
            .map_or(String::new(), |r| format!(" · R_int {:.1} %", 100. * r));
        match self.lattices.len() {
            1 => format!("{} usable{r}", s.usable),
            n => format!(
                "{n} lattices · {} usable",
                self.lattices.iter().map(|l| l.stats.usable).sum::<usize>()
            ),
        }
    }
    /// Unmerged usable reflections of one lattice (the intensity in use) as
    /// SHELX HKLF 4, scaled so the largest value fits the F8.2 fields;
    /// returns the scale.
    pub(super) fn hklf4(&self, lattice: usize, w: &mut impl Write) -> Result<f64, String> {
        let l = self
            .lattices
            .iter()
            .find(|l| l.lattice == lattice)
            .ok_or("Lattice is not integrated.")?;
        let rows: Vec<&Row> = l.rows.iter().filter(|r| r.usable()).collect();
        write_hklf4(rows.iter().map(|r| (r.hkl, r.intensity, r.sigma)), w)
    }
    /// A small Bruker-style `.p4p` header with the conventional cell.
    pub(super) fn p4p(
        &self,
        lattice: usize,
        wavelength: f64,
        w: &mut impl Write,
    ) -> Result<(), String> {
        let l = self
            .lattices
            .iter()
            .find(|l| l.lattice == lattice)
            .ok_or("Lattice is not integrated.")?;
        let [a, b, c, al, be, ga] = l.cell;
        let s = l.cell_su;
        let volume = a
            * b
            * c
            * (1.
                - al.to_radians().cos().powi(2)
                - be.to_radians().cos().powi(2)
                - ga.to_radians().cos().powi(2)
                + 2. * al.to_radians().cos() * be.to_radians().cos() * ga.to_radians().cos())
            .max(0.)
            .sqrt();
        let text = format!(
            "FILEID Dioptas {ENGINE}\nTITLE  Lattice {} {} (conventional setting)\nCELL   {a:.5} {b:.5} {c:.5} {al:.4} {be:.4} {ga:.4} {volume:.3}\nCELLSD {:.5} {:.5} {:.5} {:.4} {:.4} {:.4} 0\nBRAVAIS {}\nSOURCE SYN {wavelength:.5}\n",
            l.lattice + 1,
            l.bravais,
            s[0],
            s[1],
            s[2],
            s[3],
            s[4],
            s[5],
            l.bravais,
        );
        w.write_all(text.as_bytes()).map_err(err)
    }
}

/// HKLF 4 lines (3I4, 2F8.2) and the terminating zero line; values are scaled
/// to fit the fields. Returns the scale.
pub(super) fn write_hklf4(
    rows: impl Iterator<Item = ([i64; 3], f64, f64)> + Clone,
    w: &mut impl Write,
) -> Result<f64, String> {
    if rows.clone().next().is_none() {
        return Err("No usable reflections to export.".into());
    }
    if rows.clone().any(|r| r.0.iter().any(|h| h.abs() > 999)) {
        return Err("Miller indices exceed the HKLF4 field width; export the complete observation table instead.".into());
    }
    let max = rows.clone().map(|r| r.1.abs().max(r.2)).fold(1., f64::max);
    let scale = (9999. / max).min(1.);
    if rows.clone().any(|r| {
        format!("{:.2}", r.2 * scale)
            .parse::<f64>()
            .map_or(true, |v| v <= 0.)
    }) {
        return Err("HKLF4 cannot preserve positive uncertainties at this dynamic range. Export the full-precision observation table instead.".into());
    }
    for (h, i, s) in rows {
        writeln!(
            w,
            "{:4}{:4}{:4}{:8.2}{:8.2}",
            h[0],
            h[1],
            h[2],
            i * scale,
            s * scale
        )
        .map_err(err)?;
    }
    writeln!(w, "{:4}{:4}{:4}{:8.2}{:8.2}", 0, 0, 0, 0., 0.).map_err(err)?;
    Ok(scale)
}

#[cfg(test)]
#[path = "single_crystal_integrate_tests.rs"]
mod tests;

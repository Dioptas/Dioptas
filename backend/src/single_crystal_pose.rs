//! Refine geometry: the detector pose and the crystal orientation fitted to
//! the measured spot positions with the refined cell held fixed, with
//! PhaseSmith's `spots::geometry_refinement::fit`.
//!
//! Refine lattice fits in reciprocal space through the calibration, so a
//! calibration error ends up in the cell. This step indexes the spots of one
//! lattice in its refined setting and lets PhaseSmith move the detector (three
//! shifts and three rotations) and turn the crystal (three angles) to match
//! the observed pixel positions and rotation angles; every fifth spot is
//! withheld to check the fit. The refined pose then converts all spots, and
//! Refine lattice runs again on it with the user's symmetry choices. Pose and
//! cell are alternated while the withheld RMS still improves by [`GAIN`] or
//! the cell still moves (at most [`CYCLES`]). On the enstatite scan the first
//! cycle halves the RMS; further ones gain nothing for oP (the cell then only
//! creeps by about 0.1 σ per cycle along the weakly determined scale) and
//! about 10 % once for a free triclinic cell.
//!
//! The detector is one object for all lattices, but PhaseSmith's fit takes one
//! lattice: the pose is fitted on the refined lattice with the most spots and
//! the other lattices are refined again on that pose.
//!
//! If the fit fails PhaseSmith's gates (convergence, bounds, conditioning and
//! a withheld improvement), the calibration is kept and the following steps
//! continue with it.
use super::*;
use phasesmith_single_crystal::lattice_symmetry::{self as symmetry, Bravais};
use refine::Refinement;
use spots::geometry_refinement as fitting;

/// Most pose-then-cell cycles.
pub(super) const CYCLES: usize = 4;
/// The cell has settled when no free parameter moves by more than this
/// fraction of its standard uncertainty.
const SETTLED: f64 = 0.1;
/// Smallest relative withheld RMS gain of a cycle worth another one.
const GAIN: f64 = 0.01;

/// Refine geometry product.
#[derive(Clone, Serialize, Deserialize)]
pub(super) struct PoseFit {
    /// Lattice row (Find lattices) the pose was fitted on.
    pub lattice: usize,
    /// The fit passed PhaseSmith's gates and its pose is in use.
    pub passed: bool,
    /// Why the calibration was kept.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    /// Pose-then-cell cycles accepted.
    pub cycles: usize,
    /// Position RMS in pixels, [training, withheld] × [before, after].
    pub rms: [[f64; 2]; 2],
    /// Spots in the fit, [training, withheld].
    pub counts: [usize; 2],
    /// Detector centre shift in mm along the calibrated fast and slow
    /// directions and the detector normal (positive: away from the sample).
    pub shift: V3,
    /// Pixel size along fast and slow, mm.
    pub pixel: [f64; 2],
    /// Detector rotation, degrees.
    pub tilt: f64,
    /// Largest turn of a crystal axis of the fitted lattice, degrees.
    pub turn: f64,
    pub converged: bool,
    pub at_bounds: bool,
    pub condition: f64,
    /// The refined pose (None when the calibration is kept).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub geometry: Option<Geometry>,
    /// Refine lattice product on the calibration, restored when this step
    /// is cleared.
    pub before: Vec<refine::Refined>,
    pub before_detail: String,
}

fn sub(a: V3, b: V3) -> V3 {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}
fn unit(v: V3) -> V3 {
    let l = fft::dot(v, v).sqrt();
    v.map(|x| x / l)
}
fn cross(a: V3, b: V3) -> V3 {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}
fn angle(a: V3, b: V3) -> f64 {
    (fft::dot(unit(a), unit(b)))
        .clamp(-1., 1.)
        .acos()
        .to_degrees()
}
/// Orthonormal detector frame: fast, slow (made orthogonal), normal away
/// from the sample.
fn frame(g: &reciprocal::Geometry) -> M3 {
    let f = unit(g.fast);
    let s = unit(sub(g.slow, f.map(|x| x * fft::dot(f, g.slow))));
    let mut n = cross(f, s);
    if fft::dot(n, g.origin) < 0. {
        n = n.map(|x| -x);
    }
    [f, s, n]
}
fn centre(g: &reciprocal::Geometry, shape: [usize; 2]) -> V3 {
    std::array::from_fn(|j| {
        g.origin[j]
            + (shape[1] - 1) as f64 / 2. * g.fast[j]
            + (shape[0] - 1) as f64 / 2. * g.slow[j]
    })
}
/// Detector centre shift (mm, in the frame of `a`) and rotation (degrees).
pub(super) fn pose_change(
    a: &reciprocal::Geometry,
    b: &reciprocal::Geometry,
    shape: [usize; 2],
) -> (V3, f64) {
    let (fa, fb) = (frame(a), frame(b));
    let d = sub(centre(b, shape), centre(a, shape));
    let shift = fa.map(|e| 1e3 * fft::dot(e, d));
    // trace of the rotation taking frame a onto frame b
    let trace: f64 = (0..3).map(|i| fft::dot(fa[i], fb[i])).sum();
    (
        shift,
        ((trace - 1.) / 2.).clamp(-1., 1.).acos().to_degrees(),
    )
}
/// Whether the cell moved by less than [`SETTLED`] standard uncertainties.
fn settled(a: &Refinement, b: &Refinement) -> bool {
    (0..6).all(|i| {
        let su = a.cell_su[i].max(b.cell_su[i]);
        su <= 0. || (a.cell[i] - b.cell[i]).abs() <= SETTLED * su
    })
}

impl Crystal {
    fn refinement_of(&self, lattice: usize) -> Option<&Refinement> {
        self.refined
            .iter()
            .find(|r| r.lattice == lattice)
            .and_then(|r| r.result.as_ref())
    }
    /// Observed (x, y, omega) and conventional hkl of the unflagged spots
    /// the lattice owns, indexed in its refined setting.
    fn indexed_tracks(&self, lattice: usize) -> Result<(Vec<V3>, Vec<[i64; 3]>), String> {
        let r = self
            .refinement_of(lattice)
            .ok_or("The lattice has no refined cell.")?;
        let bravais = Bravais::from_symbol(&r.bravais)
            .ok_or_else(|| format!("Unknown lattice type {}.", r.bravais))?;
        let (ids, q) = self.cloud(false)?;
        let owners = self.owners(&q);
        let (ids, q): (Vec<usize>, Vec<V3>) = ids
            .into_iter()
            .zip(q)
            .zip(owners)
            .filter(|(_, o)| *o == lattice + 1)
            .map(|(p, _)| p)
            .unzip();
        let hkl =
            symmetry::index(&q, r.conventional, bravais, self.config.tolerance).map_err(|e| e.0)?;
        Ok(ids
            .into_iter()
            .zip(hkl)
            .filter_map(|(id, h)| Some((self.tracks[id].observed, h?)))
            .unzip())
    }
    /// One PhaseSmith pose fit of `lattice` starting from `geometry`.
    fn pose_fit(
        &self,
        lattice: usize,
        geometry: reciprocal::Geometry,
        control: &Control,
        cycle: usize,
    ) -> Result<fitting::Fit, String> {
        let (observed, hkl) = self.indexed_tracks(lattice)?;
        let r = self.refinement_of(lattice).ok_or("No refined cell.")?;
        let training: Vec<bool> = (0..hkl.len()).map(|i| i % 5 != 0).collect();
        let eligible = vec![true; hkl.len()];
        fitting::fit(
            &fitting::Input {
                observed: &observed,
                hkl: &hkl,
                training: &training,
                eligible: &eligible,
                basis: fft::inverse_transpose(r.conventional)?,
                geometry,
                image_shape: self.shape,
                reference_cell: None,
                refine_lengths: false,
            },
            fitting::Options::default(),
            |current, total| {
                control.check().map_err(spots::SpotError)?;
                control.publish(json!({"running":true,"current":current,"total":total,"label":format!("Refining detector pose · cycle {}", cycle + 1)}));
                Ok(())
            },
        )
        .map_err(|e| e.0)
    }
    /// Stage 4: detector pose and crystal orientation with the refined cell
    /// fixed, alternated with Refine lattice on the new pose.
    pub(super) fn refine_pose(&mut self, control: &Control) -> Result<String, String> {
        self.drop_pose();
        if !self.config.refine_geometry {
            return Ok("Calibration kept (refinement off).".into());
        }
        let lattice = self
            .refined
            .iter()
            .filter_map(|r| Some((r.lattice, r.result.as_ref()?.used)))
            .max_by_key(|(_, used)| *used)
            .map(|(l, _)| l)
            .ok_or("No refined lattice. Run Refine lattice first.")?;
        let start = self
            .geometry
            .ok_or("Load a PONI calibration in Frames first.")?
            .native();
        let before = self.refined.clone();
        let before_detail = self.stages[3].detail.clone();
        let first = self.refinement_of(lattice).cloned().expect("refined");
        let mut geometry = start;
        let mut fits: Vec<fitting::Fit> = Vec::new();
        let mut reason = None;
        for cycle in 0..CYCLES {
            let previous = self.refinement_of(lattice).cloned();
            let fit = match self.pose_fit(lattice, geometry, control, cycle) {
                Ok(f) if f.acceptable() => f,
                Ok(_) => {
                    reason = Some("The fit did not pass its gates.".to_owned());
                    break;
                }
                Err(e) => {
                    control.check()?;
                    reason = Some(e);
                    break;
                }
            };
            let gain = fits.last().map_or(1., |p: &fitting::Fit| {
                1. - fit.rms[1][1][0] / p.rms[1][1][0]
            });
            geometry = fit.state.geometry;
            fits.push(fit);
            self.geometry = Some(geometry.into());
            self.rerun_refinements()?;
            let moved = match (previous, self.refinement_of(lattice)) {
                (Some(a), Some(b)) => !settled(&a, b),
                _ => false,
            };
            if !moved || gain < GAIN {
                break;
            }
        }
        let (Some(head), Some(tail)) = (fits.first(), fits.last()) else {
            self.geometry = Some(start.into());
            self.refined = before.clone();
            let reason = reason.unwrap_or_else(|| "No fit.".into());
            self.pose = Some(PoseFit {
                lattice,
                passed: false,
                reason: Some(reason.clone()),
                cycles: 0,
                rms: [[0.; 2]; 2],
                counts: [0; 2],
                shift: [0.; 3],
                pixel: [
                    1e3 * fft::dot(start.fast, start.fast).sqrt(),
                    1e3 * fft::dot(start.slow, start.slow).sqrt(),
                ],
                tilt: 0.,
                turn: 0.,
                converged: false,
                at_bounds: false,
                condition: f64::NAN,
                geometry: None,
                before,
                before_detail,
            });
            self.adopt_refinement();
            return Ok(format!("Calibration kept: {}", lowercase_first(&reason)));
        };
        let (shift, tilt) = pose_change(&start, &geometry, self.shape);
        let last = self.refinement_of(lattice).cloned().expect("refined");
        let turn = (0..3)
            .map(|i| angle(first.conventional[i], last.conventional[i]))
            .fold(0., f64::max);
        let pose = PoseFit {
            lattice,
            passed: true,
            reason,
            cycles: fits.len(),
            rms: [
                [head.rms[0][0][0], tail.rms[0][1][0]],
                [head.rms[1][0][0], tail.rms[1][1][0]],
            ],
            counts: tail.counts,
            shift,
            pixel: [
                1e3 * fft::dot(start.fast, start.fast).sqrt(),
                1e3 * fft::dot(start.slow, start.slow).sqrt(),
            ],
            tilt,
            turn,
            converged: tail.converged,
            at_bounds: tail.at_bounds,
            condition: tail.scaled_condition,
            geometry: Some(geometry.into()),
            before,
            before_detail,
        };
        let detail = format!(
            "Withheld {:.2} → {:.2} px, {} spots",
            pose.rms[1][0],
            pose.rms[1][1],
            pose.counts[0] + pose.counts[1]
        );
        self.pose = Some(pose);
        self.adopt_refinement();
        if let Ok(d) = self.refine_detail() {
            self.stages[3].detail = d;
        }
        Ok(detail)
    }
    /// Clear the Refine geometry product: the calibration and the Refine
    /// lattice product on it come back.
    pub(super) fn drop_pose(&mut self) {
        if let Some(p) = self.pose.take() {
            if p.geometry.is_some() {
                self.refined = p.before;
                self.stages[3].detail = p.before_detail;
            }
            self.adopt_refinement();
        }
    }
    /// The detector geometry in use: the refined pose once it exists, else
    /// the calibration with the spindle axis of the settings.
    pub(super) fn pose_geometry(&self) -> Option<Geometry> {
        self.pose
            .as_ref()
            .and_then(|p| p.geometry)
            .or(self.initial_geometry)
            .map(|mut g| {
                g.axis = self.config.axis;
                g
            })
    }
}

fn lowercase_first(s: &str) -> String {
    let mut c = s.chars();
    c.next()
        .map(|f| f.to_lowercase().chain(c).collect())
        .unwrap_or_default()
}

#[cfg(test)]
#[path = "single_crystal_pose_tests.rs"]
mod tests;

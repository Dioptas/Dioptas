//! Refine lattice: the lattice symmetry and the constrained cell of every
//! kept lattice, with PhaseSmith's `phasesmith_single_crystal::lattice_symmetry`.
//!
//! For each lattice ticked in Find lattices, PhaseSmith's Bravais search lists
//! every lattice type whose metric fits the reduced primitive cell within the
//! tolerances, highest symmetry first (triclinic always last). Dioptas
//! preselects the first; the user may choose another row. The chosen setting
//! indexes the spots the lattice owns in Find lattices (the same reciprocal
//! cloud and ownership rule) and PhaseSmith refines the orientation and the
//! free cell parameters of that lattice system. Dioptas indexes again with the
//! refined cell until the indexed set no longer changes (at most
//! [`REINDEX`] fits).
//!
//! The product per lattice, the refined conventional basis and its Bravais
//! type, is what prediction and integration of all reflections will use. It is
//! cleared with everything from Find lattices on. Refine geometry refines it
//! again on the corrected detector pose (see `pose`).
use super::*;
use phasesmith_single_crystal::lattice_symmetry::{
    self as symmetry, Bravais, CellRefinement, Convergence, RefineOptions, SearchOptions,
};

/// Fewest indexed spots for a refinement with meaningful uncertainties.
pub(super) const MIN_SPOTS: usize = 10;
/// Most index-and-refine passes per lattice.
const REINDEX: usize = 4;
/// Upper limit of both symmetry tolerances (PhaseSmith accepts up to 10 %
/// and 10°).
pub(super) const TOLERANCE_MAX: f64 = 10.;
/// PhaseSmith's defaults (`SearchOptions::default`): 1 % and 1°.
pub(super) fn default_length_tolerance() -> f64 {
    100. * SearchOptions::default().length_tolerance
}
pub(super) fn default_angle_tolerance() -> f64 {
    SearchOptions::default().angle_tolerance
}

/// One lattice type the lattice fits, in PhaseSmith's standard setting.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Candidate {
    /// Bravais symbol, aP … cF.
    pub bravais: String,
    /// `conventional = transform · reduced` (rows).
    pub transform: [[i64; 3]; 3],
    /// Measured conventional cell (Å, °).
    pub cell: [f64; 6],
    /// The cell with the type's constraints imposed.
    pub constrained: [f64; 6],
    /// Constrained cell oriented onto the measured one (direct rows, Å).
    pub idealized: M3,
    /// Largest relative mismatch of lengths that must be equal (fraction).
    pub length_deviation: f64,
    /// Largest deviation of a constrained angle or obliquity (degrees).
    pub angle_deviation: f64,
}

/// The constrained refinement of the chosen candidate.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Refinement {
    pub bravais: String,
    /// Refined conventional direct row basis, Å (lab frame of the spots).
    pub conventional: M3,
    pub cell: [f64; 6],
    pub cell_su: [f64; 6],
    pub volume: f64,
    pub volume_su: f64,
    /// RMS of |q_obs − q_calc|, Å⁻¹.
    pub rms: f64,
    /// Spots indexed and fitted.
    pub used: usize,
    /// Spots the lattice owns (the indexing input).
    pub owned: usize,
    pub converged: bool,
}

/// Refine lattice product of one kept lattice.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub(super) struct Refined {
    /// Row in Find lattices (`Crystal::cells`).
    pub lattice: usize,
    /// Lattice types within tolerance, highest symmetry first.
    pub candidates: Vec<Candidate>,
    /// The candidate refined (preselected: 0).
    pub chosen: usize,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result: Option<Refinement>,
    /// Why the chosen candidate could not be refined.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

fn search_options(config: &Config) -> SearchOptions {
    let mut o = SearchOptions::default();
    o.length_tolerance = config.symmetry_length_tolerance / 100.;
    o.angle_tolerance = config.symmetry_angle_tolerance;
    o
}

/// Lattice types the reduced primitive basis fits, highest symmetry first.
pub(super) fn candidates(direct: M3, config: &Config) -> Result<Vec<Candidate>, String> {
    let found = symmetry::search(direct, &search_options(config)).map_err(|e| e.0)?;
    Ok(found
        .into_iter()
        .map(|m| Candidate {
            bravais: m.bravais.symbol().into(),
            transform: m.transform,
            cell: m.cell,
            constrained: m.constrained_cell,
            idealized: m.idealized,
            length_deviation: m.length_deviation,
            angle_deviation: m.angle_deviation,
        })
        .collect())
}

fn summary(fit: &CellRefinement, owned: usize) -> Refinement {
    Refinement {
        bravais: fit.bravais.symbol().into(),
        conventional: fit.conventional,
        cell: fit.cell,
        cell_su: fit.cell_su,
        volume: fit.volume,
        volume_su: fit.volume_su,
        rms: fit.rms,
        used: fit.used,
        owned,
        converged: matches!(fit.status, Convergence::Converged),
    }
}

/// Index the owned spots `q` in the candidate's setting and refine under its
/// constraints; index again with each refined cell until the set is stable.
pub(super) fn refine(
    q: &[V3],
    candidate: &Candidate,
    tolerance: f64,
) -> Result<Refinement, String> {
    let bravais = Bravais::from_symbol(&candidate.bravais)
        .ok_or_else(|| format!("Unknown lattice type {}.", candidate.bravais))?;
    if q.len() < MIN_SPOTS {
        return Err(format!(
            "{} spots belong to this lattice; at least {MIN_SPOTS} are needed.",
            q.len()
        ));
    }
    let mut fit: Option<CellRefinement> = None;
    let mut previous: Option<Vec<Option<[i64; 3]>>> = None;
    for _ in 0..REINDEX {
        let start = fit.as_ref().map_or(candidate.idealized, |f| f.conventional);
        let hkl = symmetry::index(q, start, bravais, tolerance).map_err(|e| e.0)?;
        if previous.as_ref() == Some(&hkl) {
            break;
        }
        let (observed, indices): (Vec<V3>, Vec<[i64; 3]>) = q
            .iter()
            .zip(&hkl)
            .filter_map(|(&p, h)| h.map(|h| (p, h)))
            .unzip();
        if observed.len() < MIN_SPOTS {
            return Err(format!(
                "{} spots index as {}; at least {MIN_SPOTS} are needed.",
                observed.len(),
                candidate.bravais
            ));
        }
        fit = Some(
            symmetry::refine_cell(
                &observed,
                &indices,
                start,
                bravais,
                &RefineOptions::default(),
            )
            .map_err(|e| format!("Refinement as {} failed: {}", candidate.bravais, e.0))?,
        );
        previous = Some(hkl);
    }
    Ok(summary(&fit.expect("at least one pass"), q.len()))
}

impl Refined {
    /// The chosen candidate refined on the lattice's spots.
    fn run(&mut self, q: &[V3], tolerance: f64) {
        match self
            .candidates
            .get(self.chosen)
            .ok_or_else(|| "No lattice type fits.".to_owned())
            .and_then(|c| refine(q, c, tolerance))
        {
            Ok(r) => {
                self.result = Some(r);
                self.error = None;
            }
            Err(e) => {
                self.result = None;
                self.error = Some(e);
            }
        }
    }
}

/// Short form of a cell for the step line, e.g. `oP 5.18 · 8.82 · 18.23 Å`.
fn cell_line(r: &Refinement) -> String {
    format!(
        "{} {:.2} · {:.2} · {:.2} Å",
        r.bravais, r.cell[0], r.cell[1], r.cell[2]
    )
}

impl Crystal {
    /// Spots of every lattice: the reciprocal positions of the Find lattices
    /// cloud grouped by owner (index = row in `cells`).
    fn owned_spots(&self) -> Result<Vec<Vec<V3>>, String> {
        let (_, q) = self.cloud(true)?;
        let owners = self.owners(&q);
        let mut spots: Vec<Vec<V3>> = vec![Vec::new(); self.cells.len()];
        for (p, owner) in q.into_iter().zip(owners) {
            if owner > 0 {
                spots[owner - 1].push(p);
            }
        }
        Ok(spots)
    }
    /// Stage 3: symmetry and constrained cell of every kept lattice.
    pub(super) fn refine_lattices(&mut self) -> Result<String, String> {
        self.refined.clear();
        if !self.cells.iter().any(|c| c.kept) {
            return Err("No lattice kept. Tick a lattice in Find lattices.".into());
        }
        let spots = self.owned_spots()?;
        for (i, cell) in self.cells.iter().enumerate().filter(|(_, c)| c.kept) {
            let mut r = Refined {
                lattice: i,
                candidates: vec![],
                chosen: 0,
                result: None,
                error: None,
            };
            match candidates(cell.direct, &self.config) {
                Ok(c) => {
                    r.candidates = c;
                    r.run(&spots[i], self.config.tolerance);
                }
                Err(e) => r.error = Some(e),
            }
            self.refined.push(r);
        }
        self.adopt_refinement();
        self.refine_detail()
    }
    /// Refine every lattice again in its chosen setting, on the geometry in
    /// use (after Refine geometry moved the detector).
    pub(super) fn rerun_refinements(&mut self) -> Result<(), String> {
        let spots = self.owned_spots()?;
        let tolerance = self.config.tolerance;
        for r in &mut self.refined {
            if !r.candidates.is_empty() {
                r.run(&spots[r.lattice], tolerance);
            }
        }
        self.adopt_refinement();
        Ok(())
    }
    /// The step line, or why no lattice could be refined.
    pub(super) fn refine_detail(&self) -> Result<String, String> {
        let done: Vec<&Refinement> = self
            .refined
            .iter()
            .filter_map(|r| r.result.as_ref())
            .collect();
        if done.is_empty() {
            let reason = self
                .refined
                .iter()
                .find_map(|r| r.error.clone())
                .unwrap_or_else(|| "No lattice kept.".into());
            return Err(reason);
        }
        let first = cell_line(done[0]);
        Ok(match self.refined.len() {
            1 => format!("{first}, {} spots", done[0].used),
            n => format!("{first}; {} of {n} lattices refined", done.len()),
        })
    }
    /// The first kept lattice's refined cell is the basis the older later
    /// stages (and the predicted markers) use, with the refined detector pose
    /// once Refine geometry has one, else the calibration.
    pub(super) fn adopt_refinement(&mut self) {
        let first = self
            .refined
            .iter()
            .find(|r| Some(r.lattice) == self.selected)
            .and_then(|r| r.result.as_ref());
        self.basis = first.and_then(|r| fft::inverse_transpose(r.conventional).ok());
        self.geometry = self.pose_geometry();
        self.geometry_report = Value::Null;
    }
    /// Refine one lattice in another of its candidate settings, on the
    /// calibration; Refine geometry and the following steps start again.
    pub(super) fn choose_symmetry(&mut self, lattice: usize, choice: usize) -> Result<(), String> {
        if self.stages[3].status == "pending" {
            return Err("Run Refine lattice first.".into());
        }
        let at = self
            .refined
            .iter()
            .position(|r| r.lattice == lattice)
            .ok_or("Lattice is not refined.")?;
        if choice >= self.refined[at].candidates.len() {
            return Err("Lattice type no longer listed.".into());
        }
        if self.refined[at].chosen == choice && self.refined[at].result.is_some() {
            return Ok(());
        }
        // Back to the calibration and the other lattices' cells on it.
        self.invalidate(4);
        let at = self
            .refined
            .iter()
            .position(|r| r.lattice == lattice)
            .ok_or("Lattice is not refined.")?;
        let spots = self.owned_spots()?;
        let tolerance = self.config.tolerance;
        let r = &mut self.refined[at];
        r.chosen = choice;
        r.run(&spots[lattice], tolerance);
        self.adopt_refinement();
        let (status, detail) = match self.refine_detail() {
            Ok(detail) => ("complete", detail),
            Err(e) => ("attention", e),
        };
        self.stages[3].status = status.into();
        self.stages[3].detail = detail;
        Ok(())
    }
}

#[cfg(test)]
#[path = "single_crystal_refine_tests.rs"]
pub(super) mod tests;

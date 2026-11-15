//! Refine geometry on synthetic spots measured on a detector that is tilted
//! and shifted against the calibration, so the step runs the real cloud,
//! indexing, PhaseSmith pose fit and the following Refine lattice pass.
use super::super::refine::tests::{
    ENSTATITE, Lcg, call, crystal, detector, lattice, rotation, run, sheared, tracks_on,
};
use super::*;

const SHAPE: [usize; 2] = [4000, 4000];

/// The calibration turned by `tilt` (degrees, about the fast direction)
/// around the detector centre and moved by `shift` (mm, lab frame).
fn moved(tilt: f64, shift: V3) -> Geometry {
    let g = detector();
    let r = rotation(tilt.to_radians(), 0., 0.);
    let turn = |v: V3| r.map(|row| fft::dot(row, v));
    let c = centre(&g.native(), SHAPE);
    let rel = sub(g.origin, c);
    let o = turn(rel);
    Geometry {
        origin: std::array::from_fn(|j| c[j] + o[j] + 1e-3 * shift[j]),
        fast: turn(g.fast),
        slow: turn(g.slow),
        ..g
    }
}
/// A crystal after Refine lattice whose spots were measured on `truth`
/// while the calibration is the unmoved detector.
fn measured(truth: Geometry, sets: &[(f64, usize)]) -> (Crystal, Vec<M3>) {
    let mut lattices = vec![];
    let mut cells = vec![];
    for (i, &(turn, limit)) in sets.iter().enumerate() {
        let d = lattice(ENSTATITE, rotation(0.3 + turn, -0.5, 0.8 - turn));
        let t = tracks_on(truth, d, 0.9, limit, &mut Lcg(7 + i as u64));
        lattices.push((sheared(d), t));
        cells.push(d);
    }
    let mut c = crystal(lattices);
    c.shape = SHAPE;
    run(&mut c).unwrap();
    (c, cells)
}
/// Stage 4 as the run command runs it.
fn run_pose(c: &mut Crystal) -> Result<String, String> {
    let result = c.process(4, &Control::default(), false);
    c.stages[4].status = if result.is_ok() {
        "complete"
    } else {
        "attention"
    }
    .into();
    result
}
/// Largest length error of the refined cell, Å.
fn error(c: &Crystal, lattice: usize) -> f64 {
    let r = c.refinement_of(lattice).unwrap();
    r.cell[..3]
        .iter()
        .zip([5.18, 8.81, 18.23])
        .map(|(a, b)| (a - b).abs())
        .fold(0., f64::max)
}

#[test]
fn a_tilted_detector_is_corrected_and_the_cell_refined_again() {
    let (mut c, _) = measured(moved(0.3, [0., 0.08, 0.]), &[(0., 5000)]);
    let before = c.refined.clone();
    let error_before = error(&c, 0);
    let detail = run_pose(&mut c).unwrap();
    let p = c.pose.as_ref().unwrap();
    assert!(p.passed, "{:?}", p.reason);
    assert!(p.cycles >= 1 && p.cycles <= CYCLES);
    assert!(
        p.rms[1][1] < 0.5 * p.rms[1][0] && p.rms[1][1] < 0.3,
        "withheld {:?}",
        p.rms[1]
    );
    assert!(p.counts[1] >= 10 && p.counts[0] > 4 * p.counts[1] - 10);
    assert!((p.tilt - 0.3).abs() < 0.05, "tilt {}", p.tilt);
    assert!(p.shift.iter().map(|v| v * v).sum::<f64>().sqrt() < 0.5);
    assert!(detail.starts_with("Withheld "), "{detail}");
    // The detector in use is the refined pose; the cell was refined on it.
    let g = c.geometry.unwrap();
    assert_eq!(g.origin, p.geometry.unwrap().origin);
    assert_eq!(p.before, before);
    assert_ne!(c.refined, before);
    let error_after = error(&c, 0);
    assert!(
        error_after < 0.5 * error_before,
        "{error_before} -> {error_after}"
    );
    assert!(c.stages[3].detail.starts_with("oP "));
    let basis = c.basis.unwrap();
    let conventional = c.refinement_of(0).unwrap().conventional;
    assert_eq!(basis, fft::inverse_transpose(conventional).unwrap());
}

#[test]
fn turned_off_it_keeps_the_calibration() {
    let (mut c, _) = measured(moved(0.3, [0.; 3]), &[(0., 5000)]);
    c.config.refine_geometry = false;
    let before = c.refined.clone();
    let detail = run_pose(&mut c).unwrap();
    assert_eq!(detail, "Calibration kept (refinement off).");
    assert!(c.pose.is_none());
    assert_eq!(c.geometry.unwrap().origin, detector().origin);
    assert_eq!(c.refined, before);
}

#[test]
fn a_failed_fit_keeps_the_calibration_and_the_later_steps_continue() {
    // Too few spots for PhaseSmith's 30 training and 10 withheld.
    let (mut c, _) = measured(moved(0.3, [0.; 3]), &[(0., 40)]);
    assert!(c.refinement_of(0).is_some(), "{:?}", c.refined[0].error);
    let before = c.refined.clone();
    let detail = run_pose(&mut c).unwrap();
    assert_eq!(c.stages[4].status, "complete");
    assert!(detail.starts_with("Calibration kept: "), "{detail}");
    let p = c.pose.as_ref().unwrap();
    assert!(!p.passed && p.geometry.is_none());
    assert!(p.reason.as_deref().unwrap().contains("withheld"));
    assert_eq!(c.geometry.unwrap().origin, detector().origin);
    assert_eq!(c.refined, before);
}

#[test]
fn the_pose_is_fitted_on_the_largest_lattice_and_every_lattice_refined_on_it() {
    let (mut c, _) = measured(moved(0.3, [0.; 3]), &[(0., 1500), (0.6, 5000)]);
    assert_eq!(c.refined.len(), 2);
    let before = c.refined.clone();
    run_pose(&mut c).unwrap();
    let p = c.pose.as_ref().unwrap();
    assert!(p.passed, "{:?}", p.reason);
    let used = |l: usize| {
        before
            .iter()
            .find(|r| r.lattice == l)
            .unwrap()
            .result
            .as_ref()
            .unwrap()
            .used
    };
    let largest = if used(0) > used(1) { 0 } else { 1 };
    assert_eq!(p.lattice, largest);
    for (a, b) in before.iter().zip(&c.refined) {
        assert_ne!(a.result, b.result, "lattice {} refined again", a.lattice);
    }
    for l in 0..2 {
        assert!(
            error(&c, l) < 0.01,
            "lattice {l}: {:?}",
            c.refinement_of(l).unwrap().cell
        );
    }
}

#[test]
fn choosing_a_symmetry_or_clearing_the_step_brings_back_the_calibration() {
    let (c, _) = measured(moved(0.3, [0.; 3]), &[(0., 5000)]);
    let mut s = Session::new(PathBuf::new());
    s.scxrd = c;
    s.scxrd.stages[3].status = "complete".into();
    let before = s.scxrd.refined.clone();
    let detail = s.scxrd.stages[3].detail.clone();
    let r = call(&mut s, "scxrd_run", json!({"stage":4}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(s.scxrd.stages[4].status, "complete");
    assert_eq!(r.result["scxrd"]["poseFit"]["passed"], true);
    assert!(r.result["scxrd"]["poseFit"]["before"][0]["result"]["cell"].is_array());
    // Clearing Refine geometry: the calibration and its cells come back.
    call(&mut s, "scxrd_edit", json!({"operation":"rerun","index":4}));
    assert_eq!(s.scxrd.stages[4].status, "pending");
    assert_eq!(s.scxrd.stages[3].status, "complete");
    assert!(s.scxrd.pose.is_none());
    assert_eq!(s.scxrd.refined, before);
    assert_eq!(s.scxrd.stages[3].detail, detail);
    assert_eq!(s.scxrd.geometry.unwrap().origin, detector().origin);
    // Choosing another symmetry clears it too and refines on the calibration.
    call(&mut s, "scxrd_run", json!({"stage":4}));
    assert!(s.scxrd.pose.is_some());
    let r = call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"symmetry","index":0,"choice":2}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(s.scxrd.stages[4].status, "pending");
    assert!(s.scxrd.pose.is_none());
    assert_eq!(s.scxrd.geometry.unwrap().origin, detector().origin);
    let ap = s.scxrd.refinement_of(0).unwrap();
    assert_eq!(ap.bravais, "aP");
    // The undo snapshot holds the refined geometry.
    let undo = s.scxrd_undo.last().unwrap();
    assert!(undo.pose.as_ref().is_some_and(|p| p.passed));
    assert_eq!(r.result["scxrd"]["undoLabel"], "choose lattice symmetry");
}

#[test]
fn settings_and_earlier_steps_clear_refine_geometry() {
    let (mut c, _) = measured(moved(0.3, [0.; 3]), &[(0., 5000)]);
    let before = c.refined.clone();
    run_pose(&mut c).unwrap();
    let mut changed = c.config.clone();
    changed.refine_geometry = false;
    assert_eq!(c.config.first_changed(&changed), 4);
    c.invalidate(4);
    assert!(c.pose.is_none() && c.stages[4].status == "pending");
    assert_eq!(c.refined, before);
    assert_eq!(c.stages[3].status, "complete");
    run_pose(&mut c).unwrap();
    c.invalidate(3);
    assert!(c.pose.is_none() && c.refined.is_empty());
    assert_eq!(c.geometry.unwrap().origin, detector().origin);
}

#[test]
fn the_pose_change_is_reported_in_the_detector_frame() {
    let g = detector();
    let t = moved(0.25, [0.1, -0.2, 0.]);
    let (shift, tilt) = pose_change(&g.native(), &t.native(), SHAPE);
    assert!((tilt - 0.25).abs() < 1e-9, "{tilt}");
    // fast = +x, slow = +y; normal +z points away from the sample.
    assert!((shift[0] - 0.1).abs() < 1e-9 && (shift[1] + 0.2).abs() < 1e-9);
    assert!(shift[2].abs() < 1e-9, "{shift:?}");
    let further = moved(0., [0., 0., 0.05]);
    let (shift, _) = pose_change(&g.native(), &further.native(), SHAPE);
    assert!((shift[2] - 0.05).abs() < 1e-9, "{shift:?}");
}

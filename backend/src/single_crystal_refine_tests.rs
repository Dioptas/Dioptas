//! Refine lattice on synthetic spots: tracks predicted on a flat detector
//! from known lattices, so the step runs the real cloud, ownership, search,
//! indexing and constrained refinement.
use super::*;

pub(crate) fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    })
}
/// Deterministic uniform numbers in [0, 1).
pub(crate) struct Lcg(pub(crate) u64);
impl Lcg {
    pub(crate) fn next(&mut self) -> f64 {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (self.0 >> 11) as f64 / (1u64 << 53) as f64
    }
}
pub(crate) fn rotation(x: f64, y: f64, z: f64) -> M3 {
    let (sx, cx, sy, cy, sz, cz) = (x.sin(), x.cos(), y.sin(), y.cos(), z.sin(), z.cos());
    [
        [cy * cz, sx * sy * cz - cx * sz, cx * sy * cz + sx * sz],
        [cy * sz, sx * sy * sz + cx * cz, cx * sy * sz - sx * cz],
        [-sy, sx * cy, cx * cy],
    ]
}
/// Direct rows of a cell (Å, degrees), rotated.
pub(crate) fn lattice(p: [f64; 6], r: M3) -> M3 {
    let basis = symmetry::cell_basis(p).unwrap();
    basis.map(|row| r.map(|q| fft::dot(q, row)))
}
/// A primitive but not conventional basis of the same lattice (a, b, a + c),
/// as Find lattices might report it.
pub(crate) fn sheared(d: M3) -> M3 {
    [d[0], d[1], std::array::from_fn(|j| d[0][j] + d[2][j])]
}
pub(crate) const ENSTATITE: [f64; 6] = [18.23, 8.81, 5.18, 90., 90., 90.];
pub(crate) const AXIS: V3 = [1., 0., 0.];
/// A flat detector 200 mm downstream (metres, like a loaded calibration).
pub(crate) fn detector() -> Geometry {
    Geometry {
        origin: [-0.15, -0.15, 0.2],
        fast: [75e-6, 0., 0.],
        slow: [0., 75e-6, 0.],
        beam: [0., 0., 1.],
        axis: AXIS,
        wavelength: 0.2846,
    }
}
/// Observed tracks (x, y px, omega °) of the nodes of `direct` within `qmax`
/// that cross the sphere within ±40°, at most `limit`, with small scatter.
fn tracks(direct: M3, qmax: f64, limit: usize, rng: &mut Lcg) -> Vec<Track> {
    tracks_on(detector(), direct, qmax, limit, rng)
}
/// The same, measured on detector `g`.
pub(crate) fn tracks_on(
    g: Geometry,
    direct: M3,
    qmax: f64,
    limit: usize,
    rng: &mut Lcg,
) -> Vec<Track> {
    let b = fft::inverse_transpose(direct).unwrap();
    let span = direct.map(|r| (qmax * fft::dot(r, r).sqrt()).ceil() as i64);
    let mut hkl = vec![];
    for h in -span[0]..=span[0] {
        for k in -span[1]..=span[1] {
            for l in -span[2]..=span[2] {
                let q: V3 = std::array::from_fn(|j| {
                    h as f64 * b[0][j] + k as f64 * b[1][j] + l as f64 * b[2][j]
                });
                let n = fft::dot(q, q).sqrt();
                if n > 0.05 && n < qmax {
                    hkl.push([h, k, l]);
                }
            }
        }
    }
    let mut out = vec![];
    for other in [false, true] {
        let hints = vec![0.; hkl.len()];
        let p = spots::prediction::predict(g.native(), b, &hkl, &hints, other).unwrap();
        for p in p {
            let [x, y, omega] = p.values;
            if p.flags == 0
                && omega.abs() < 40.
                && (0. ..4000.).contains(&x)
                && (0. ..4000.).contains(&y)
            {
                out.push(Track {
                    native: false,
                    observed: [
                        x + (rng.next() - 0.5) * 0.4,
                        y + (rng.next() - 0.5) * 0.4,
                        omega + (rng.next() - 0.5) * 0.04,
                    ],
                    first: 0,
                    last: 0,
                    bounds: [0, 0, 1, 1],
                    flags: 0,
                    excluded: false,
                });
            }
        }
    }
    out.truncate(limit);
    out
}
pub(crate) fn found(direct: M3) -> Cell {
    Cell {
        direct,
        parameters: processing::parameters(direct),
        indexed: 0,
        total: 0,
        rms: 0.,
        validation: 0,
        found: lattices::Found::Both,
        kept: true,
        merged: None,
    }
}
/// A crystal after Find lattices with these (cell given, spots) lattices.
pub(crate) fn crystal(lattices: Vec<(M3, Vec<Track>)>) -> Crystal {
    let mut c = Crystal {
        config: Config {
            integration_method: "summation".into(),
            axis: AXIS,
            confirmed: true,
            ..Config::default()
        },
        geometry: Some(detector()),
        initial_geometry: Some(detector()),
        // The run command needs a series; these steps never read it.
        sources: vec![Source {
            path: PathBuf::from("unread.tif"),
            frame: 0,
            digest: Default::default(),
        }],
        ..Default::default()
    };
    for (direct, t) in lattices {
        c.cells.push(found(direct));
        c.tracks.extend(t);
    }
    c.selected = Some(0);
    for s in &mut c.stages[..3] {
        s.status = "complete".into();
    }
    c
}
fn enstatite() -> (Crystal, M3) {
    let truth = lattice(ENSTATITE, rotation(0.3, -0.5, 0.8));
    let t = tracks(truth, 0.9, 5000, &mut Lcg(7));
    (crystal(vec![(sheared(truth), t)]), truth)
}
fn symbols(r: &Refined) -> Vec<&str> {
    r.candidates.iter().map(|c| c.bravais.as_str()).collect()
}
/// Stage 3 as the run command runs it (status set from the result).
pub(crate) fn run(c: &mut Crystal) -> Result<String, String> {
    let result = c.process(3, &Control::default(), false);
    c.stages[3].status = if result.is_ok() {
        "complete"
    } else {
        "attention"
    }
    .into();
    result
}

#[test]
fn an_orthorhombic_lattice_preselects_primitive_orthorhombic_and_refines_it() {
    let (mut c, truth) = enstatite();
    let detail = run(&mut c).unwrap();
    assert_eq!(c.refined.len(), 1);
    let r = &c.refined[0];
    assert_eq!(symbols(r), ["oP", "mP", "aP"], "highest symmetry first");
    assert_eq!(r.chosen, 0);
    let fit = r.result.as_ref().unwrap();
    assert_eq!(fit.bravais, "oP");
    // PhaseSmith's lattice setting: a <= b <= c.
    for (got, want) in fit.cell.iter().zip([5.18, 8.81, 18.23, 90., 90., 90.]) {
        assert!((got - want).abs() < 0.005, "{:?}", fit.cell);
    }
    assert!(fit.cell_su[..3].iter().all(|&s| s > 0. && s < 0.005));
    assert_eq!(
        fit.cell_su[3..],
        [0.; 3],
        "fixed angles carry no uncertainty"
    );
    assert!((fit.volume - 5.18 * 8.81 * 18.23).abs() < 1.);
    assert!(fit.volume_su > 0.);
    assert!(
        fit.used > 300 && fit.used <= fit.owned,
        "{} of {}",
        fit.used,
        fit.owned
    );
    assert!(fit.converged && fit.rms < 0.002, "{}", fit.rms);
    assert!(detail.starts_with("oP 5.18 · 8.81 · 18.23 Å"), "{detail}");
    // The refined basis spans the same lattice as the truth.
    let volume = processing::det(fit.conventional).abs();
    assert!((volume / processing::det(truth).abs() - 1.).abs() < 1e-3);
    // Older later stages take the first kept lattice's refined cell.
    let basis = c.basis.unwrap();
    assert!((processing::det(fft::inverse_transpose(basis).unwrap()).abs() - volume).abs() < 1e-6);
}

#[test]
fn choosing_another_lattice_type_refines_again_as_an_undoable_edit() {
    let (c, _) = enstatite();
    let mut s = Session::new(PathBuf::new());
    s.scxrd = c;
    let r = call(&mut s, "scxrd_run", json!({"stage":3}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(s.scxrd.stages[3].status, "complete");
    let listed = &r.result["scxrd"]["refinedLattices"][0];
    assert_eq!(listed["candidates"][0]["bravais"], "oP");
    assert_eq!(listed["result"]["bravais"], "oP");
    // Triclinic: all six parameters free.
    let r = call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"symmetry","index":0,"choice":2}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let fit = s.scxrd.refined[0].result.clone().unwrap();
    assert_eq!((s.scxrd.refined[0].chosen, fit.bravais.as_str()), (2, "aP"));
    assert!(fit.cell_su.iter().all(|&s| s > 0.), "{:?}", fit.cell_su);
    assert!(
        fit.cell[3..].iter().all(|a| (a - 90.).abs() < 0.05),
        "{:?}",
        fit.cell
    );
    assert_eq!(s.scxrd.stages[3].status, "complete");
    assert!(s.scxrd.stages[3].detail.starts_with("aP "));
    assert_eq!(r.result["scxrd"]["undoLabel"], "choose lattice symmetry");
    // Monoclinic: b unique, beta free.
    call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"symmetry","index":0,"choice":1}),
    );
    let fit = s.scxrd.refined[0].result.clone().unwrap();
    assert_eq!(fit.bravais, "mP");
    assert!(fit.cell_su[4] > 0. && fit.cell_su[3] == 0. && fit.cell_su[5] == 0.);
    // The step before is kept for undo (undo itself redraws the frame,
    // which this fixture does not have).
    let before = &s.scxrd_undo.last().unwrap().refined[0];
    assert_eq!(before.result.as_ref().unwrap().bravais, "aP");
    // Out of range, or not a refined lattice.
    let r = call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"symmetry","index":0,"choice":3}),
    );
    assert_eq!(r.result["ok"], false);
    let r = call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"symmetry","index":1,"choice":0}),
    );
    assert_eq!(r.result["ok"], false);
}

#[test]
fn the_tolerances_decide_the_preselected_type() {
    // beta 90.6°: orthorhombic within 1°, monoclinic within 0.3°.
    let direct = lattice([7.5, 9.2, 12.4, 90., 90.6, 90.], rotation(0.1, 0.2, 0.3));
    let mut config = Config::default();
    assert_eq!(candidates(direct, &config).unwrap()[0].bravais, "oP");
    config.symmetry_angle_tolerance = 0.3;
    assert_eq!(candidates(direct, &config).unwrap()[0].bravais, "mP");
    // Tolerances are settings of this step: they restart it.
    let wider = Config {
        symmetry_length_tolerance: 3.,
        ..Config::default()
    };
    assert_eq!(Config::default().first_changed(&wider), 3);
    assert!(
        Config {
            symmetry_angle_tolerance: 0.,
            ..Config::default()
        }
        .check()
        .is_err()
    );
    assert!(
        Config {
            symmetry_length_tolerance: 10.5,
            ..Config::default()
        }
        .check()
        .is_err()
    );
    // Older settings load with PhaseSmith's defaults, 1 % and 1°.
    let mut older = serde_json::to_value(Config::default()).unwrap();
    older
        .as_object_mut()
        .unwrap()
        .remove("symmetry_length_tolerance");
    older
        .as_object_mut()
        .unwrap()
        .remove("symmetry_angle_tolerance");
    let older: Config = serde_json::from_value(older).unwrap();
    assert_eq!(
        (
            older.symmetry_length_tolerance,
            older.symmetry_angle_tolerance
        ),
        (1., 1.)
    );
}

#[test]
fn find_lattices_and_earlier_changes_clear_the_refinement() {
    let (c, _) = enstatite();
    let mut s = Session::new(PathBuf::new());
    s.scxrd = c;
    assert_eq!(
        call(&mut s, "scxrd_run", json!({"stage":3})).result["ok"],
        true
    );
    assert!(s.scxrd.basis.is_some());
    // A tick in Find lattices.
    let r = call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"keep","index":0,"keep":false}),
    );
    assert_eq!(r.result["ok"], true);
    assert!(s.scxrd.refined.is_empty() && s.scxrd.basis.is_none());
    assert_eq!(s.scxrd.stages[3].status, "pending");
    assert_eq!(r.result["scxrd"]["refinedLattices"], json!([]));
    // A setting of this step, of Find lattices and of Find spots.
    for patch in [
        json!({"symmetry_angle_tolerance": 2.0}),
        json!({"merge_angle": 1.0}),
        json!({"threshold": 6.0}),
    ] {
        let (mut c, _) = enstatite();
        run(&mut c).unwrap();
        let mut changed = serde_json::to_value(&c.config).unwrap();
        for (k, v) in patch.as_object().unwrap() {
            changed[k] = v.clone();
        }
        let changed: Config = serde_json::from_value(changed).unwrap();
        c.invalidate(c.config.first_changed(&changed));
        assert!(c.refined.is_empty(), "{patch}");
        assert_eq!(c.stages[3].status, "pending");
    }
    // Choosing again before the step ran.
    let (mut c, _) = enstatite();
    assert!(c.choose_symmetry(0, 0).is_err());
}

#[test]
fn no_kept_lattice_refines_nothing() {
    let (mut c, _) = enstatite();
    c.cells[0].kept = false;
    let e = run(&mut c).unwrap_err();
    assert!(e.contains("No lattice kept"), "{e}");
    assert!(c.refined.is_empty() && c.basis.is_none());
    // Through the run command: it stops at Find lattices.
    let (c, _) = enstatite();
    let mut s = Session::new(PathBuf::new());
    s.scxrd = c;
    s.scxrd.cells[0].kept = false;
    s.scxrd.stages[2] = Stage::default();
    let r = call(&mut s, "scxrd_run", json!({"stage":3}));
    assert_eq!(s.scxrd.stages[2].status, "attention", "{:?}", r.result);
    assert_eq!(s.scxrd.stages[3].status, "pending");
}

#[test]
fn a_lattice_with_too_few_spots_says_so_and_the_others_refine() {
    let truth = lattice(ENSTATITE, rotation(0.3, -0.5, 0.8));
    let small = lattice([7.5, 9.2, 12.4, 90., 104., 90.], rotation(1.1, 0.4, -0.2));
    let mut rng = Lcg(11);
    let main = tracks(truth, 0.9, 5000, &mut rng);
    let few = tracks(small, 0.9, 6, &mut rng);
    let mut c = crystal(vec![(sheared(truth), main), (small, few)]);
    let detail = run(&mut c).unwrap();
    assert_eq!(c.refined.len(), 2);
    assert!(c.refined[0].result.is_some());
    let r = &c.refined[1];
    assert_eq!(r.candidates[0].bravais, "mP");
    assert!(r.result.is_none());
    let e = r.error.as_deref().unwrap();
    assert!(e.contains("at least 10"), "{e}");
    assert!(detail.contains("1 of 2 lattices refined"), "{detail}");
    // Only the small lattice kept: the step needs attention.
    c.cells[0].kept = false;
    c.selected = Some(1);
    let e = run(&mut c).unwrap_err();
    assert!(e.contains("at least 10"), "{e}");
    assert!(c.basis.is_none());
}

#[test]
fn the_product_round_trips_through_serialisation() {
    let (mut c, _) = enstatite();
    run(&mut c).unwrap();
    let product = c.refined.clone();
    let json = serde_json::to_string(&product).unwrap();
    assert_eq!(
        serde_json::from_str::<Vec<Refined>>(&json).unwrap(),
        product
    );
    let mut bytes = Vec::new();
    product
        .serialize(&mut rmp_serde::Serializer::new(&mut bytes).with_struct_map())
        .unwrap();
    assert_eq!(
        rmp_serde::from_slice::<Vec<Refined>>(&bytes).unwrap(),
        product
    );
    // A failed lattice carries its reason, not an empty result.
    let failed = Refined {
        lattice: 0,
        candidates: vec![],
        chosen: 0,
        result: None,
        error: Some("why".into()),
    };
    let value = serde_json::to_value(&failed).unwrap();
    assert!(value.get("result").is_none());
    assert_eq!(serde_json::from_value::<Refined>(value).unwrap(), failed);
}

#[test]
fn a_left_handed_lattice_basis_refines_in_a_right_handed_setting() {
    // Find lattices may report a left-handed reduced basis; PhaseSmith refuses
    // a left-handed start, so the setting Dioptas passes must be right handed.
    let truth = lattice(ENSTATITE, rotation(0.3, -0.5, 0.8));
    let t = tracks(truth, 0.9, 5000, &mut Lcg(5));
    let left = [truth[1], truth[0], truth[2]];
    assert!(processing::det(left) < 0.);
    let mut c = crystal(vec![(left, t)]);
    run(&mut c).unwrap();
    let r = &c.refined[0];
    assert!(
        r.candidates
            .iter()
            .all(|c| processing::det(c.idealized) > 0.)
    );
    for choice in 0..r.candidates.len() {
        c.choose_symmetry(0, choice).unwrap();
        let r = &c.refined[0];
        assert!(
            r.error.is_none(),
            "{:?}: {:?}",
            r.candidates[choice].bravais,
            r.error
        );
        assert!(processing::det(r.result.as_ref().unwrap().conventional) > 0.);
    }
}

#[test]
fn a_body_centred_lattice_indexes_only_allowed_reflections() {
    // PhaseSmith refuses indices the centring forbids; indexing goes through
    // its `index`, so an I lattice refines as oI.
    let conventional = lattice([6.1, 7.3, 9.4, 90., 90., 90.], rotation(0.7, 0.1, -0.4));
    let half: V3 = std::array::from_fn(|j| {
        0.5 * (conventional[0][j] + conventional[1][j] + conventional[2][j])
    });
    let primitive = [conventional[0], conventional[1], half];
    let t = tracks(primitive, 1.0, 5000, &mut Lcg(3));
    let mut c = crystal(vec![(primitive, t)]);
    run(&mut c).unwrap();
    let r = &c.refined[0];
    assert_eq!(r.candidates[0].bravais, "oI");
    let fit = r.result.as_ref().unwrap();
    assert_eq!(fit.bravais, "oI");
    for (got, want) in fit.cell.iter().zip([6.1, 7.3, 9.4]) {
        assert!((got - want).abs() < 0.005, "{:?}", fit.cell);
    }
    // The primitive setting of the same lattice refines too.
    let last = r.candidates.len() - 1;
    c.choose_symmetry(0, last).unwrap();
    assert_eq!(c.refined[0].result.as_ref().unwrap().bravais, "aP");
}

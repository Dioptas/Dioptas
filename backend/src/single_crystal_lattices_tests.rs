//! Find lattices on synthetic reciprocal-space spot clouds.
use super::*;

/// Deterministic uniform numbers in [0, 1).
struct Lcg(u64);
impl Lcg {
    fn next(&mut self) -> f64 {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (self.0 >> 11) as f64 / (1u64 << 53) as f64
    }
}
fn rotation(x: f64, y: f64, z: f64) -> [V3; 3] {
    let (sx, cx, sy, cy, sz, cz) = (x.sin(), x.cos(), y.sin(), y.cos(), z.sin(), z.cos());
    [
        [cy * cz, sx * sy * cz - cx * sz, cx * sy * cz + sx * sz],
        [cy * sz, sx * sy * sz + cx * cz, cx * sy * sz - sx * cz],
        [-sy, sx * cy, cx * cy],
    ]
}
fn rotate(r: &[V3; 3], v: V3) -> V3 {
    r.map(|row| fft::dot(row, v))
}
/// Direct cell rows from lengths (Å) and angles (degrees).
fn cell(p: [f64; 6]) -> M3 {
    let [a, b, c, al, be, ga] = p;
    let (al, be, ga) = (al.to_radians(), be.to_radians(), ga.to_radians());
    let cx = c * be.cos();
    let cy = c * (al.cos() - be.cos() * ga.cos()) / ga.sin();
    [
        [a, 0., 0.],
        [b * ga.cos(), b * ga.sin(), 0.],
        [cx, cy, (c * c - cx * cx - cy * cy).sqrt()],
    ]
}
/// Spot position scatter, full width per axis (Å⁻¹): relative to the q range
/// like the Eiger enstatite scan (rms 0.003 Å⁻¹ up to 2 Å⁻¹).
const SCATTER: f64 = 0.002;
const QMAX: f64 = 0.9;
/// Measured nodes of a rotated lattice: those within `qmax` in a DAC-like
/// doughnut around the beam (lab z), of which 90 % are kept (the rest weak or
/// masked), with position scatter (Å⁻¹) like real spots.
fn grain(direct: M3, r: [V3; 3], qmax: f64, rng: &mut Lcg) -> Vec<V3> {
    let direct = direct.map(|row| rotate(&r, row));
    let reciprocal = fft::inverse_transpose(direct).unwrap();
    let span = direct.map(|row| (qmax * fft::dot(row, row).sqrt()).ceil() as i32);
    let mut nodes = vec![];
    for h in -span[0]..=span[0] {
        for k in -span[1]..=span[1] {
            for l in -span[2]..=span[2] {
                let q: V3 = std::array::from_fn(|j| {
                    f64::from(h) * reciprocal[0][j]
                        + f64::from(k) * reciprocal[1][j]
                        + f64::from(l) * reciprocal[2][j]
                });
                let n = fft::dot(q, q).sqrt();
                if n > 0.08 && n < qmax && q[2].abs() < 0.6 * n && rng.next() < 0.9 {
                    nodes.push(q.map(|x| x + (rng.next() - 0.5) * SCATTER));
                }
            }
        }
    }
    nodes
}
fn noise(count: usize, qmax: f64, rng: &mut Lcg) -> Vec<V3> {
    let mut out = vec![];
    while out.len() < count {
        let q: V3 = std::array::from_fn(|_| (2. * rng.next() - 1.) * qmax);
        let n = fft::dot(q, q).sqrt();
        if n > 0.08 && n < qmax {
            out.push(q);
        }
    }
    out
}
/// Interleave so the withheld fifth samples every source evenly.
fn shuffle(mut q: Vec<V3>, rng: &mut Lcg) -> Vec<V3> {
    for i in (1..q.len()).rev() {
        let j = (rng.next() * (i + 1) as f64) as usize;
        q.swap(i, j);
    }
    q
}
const ENSTATITE: [f64; 6] = [5.18, 8.81, 18.23, 90., 90., 90.];
/// A second phase of about the same volume (829 Å³), so both grains give
/// similar spot counts.
const MONOCLINIC: [f64; 6] = [7.5, 9.2, 12.4, 90., 104., 90.];
fn config(method: &str) -> Config {
    Config {
        integration_method: "summation".into(),
        lattice_method: method.into(),
        ..Config::default()
    }
}
fn run(q: &[V3], method: &str) -> Vec<Cell> {
    find(q, &config(method), &Control::default()).unwrap()
}
/// The candidate with this reduced cell: sorted lengths within 0.5 %, volume
/// within 1.5 % (angles may come in the acute or the obtuse setting).
fn matching(cells: &[Cell], expected: [f64; 6]) -> Option<&Cell> {
    let mut want = expected[..3].to_vec();
    want.sort_by(f64::total_cmp);
    let volume = |p: [f64; 6]| {
        let [ca, cb, cg] = [p[3], p[4], p[5]].map(|x| x.to_radians().cos());
        p[0] * p[1] * p[2] * (1. - ca * ca - cb * cb - cg * cg + 2. * ca * cb * cg).sqrt()
    };
    cells.iter().find(|c| {
        let mut got = c.parameters[..3].to_vec();
        got.sort_by(f64::total_cmp);
        got.iter()
            .zip(&want)
            .all(|(g, w)| (g / w - 1.).abs() < 0.005)
            && (volume(c.parameters) / volume(expected) - 1.).abs() < 0.015
    })
}

#[test]
fn one_lattice_is_found_by_both_searches() {
    let rng = &mut Lcg(7);
    let mut q = grain(cell(ENSTATITE), rotation(0.4, 1.1, -0.7), QMAX, rng);
    let measured = q.len();
    q.extend(noise(200, QMAX, rng));
    let q = shuffle(q, rng);
    for method in ["fft", "rows", "both"] {
        let cells = run(&q, method);
        let best = &cells[0];
        assert!(
            matching(&cells[..1], ENSTATITE).is_some(),
            "{method}: {:?}",
            best.parameters
        );
        assert!(
            best.indexed >= measured && best.indexed <= measured + 40,
            "{method}: {} of {measured}",
            best.indexed
        );
        let expected = match method {
            "fft" => Found::Fft,
            "rows" => Found::Rows,
            _ => Found::Both,
        };
        assert_eq!(best.found, expected, "{method}");
        // Supercells and other settings of the same lattice are not listed.
        assert!(
            cells[1..].iter().all(|c| !related(c.direct, best.direct)),
            "{method}: {:?}",
            cells.iter().map(|c| c.parameters).collect::<Vec<_>>()
        );
    }
}

#[test]
fn two_grains_below_half_of_the_spots_are_both_found() {
    let rng = &mut Lcg(11);
    let mut q = grain(cell(ENSTATITE), rotation(0.4, 1.1, -0.7), QMAX, rng);
    let first = q.len();
    q.extend(grain(cell(MONOCLINIC), rotation(-1.3, 0.2, 2.1), QMAX, rng));
    let second = q.len() - first;
    q.extend(noise(400, QMAX, rng));
    let q = shuffle(q, rng);
    for method in ["fft", "rows", "both"] {
        let cells = run(&q, method);
        let summary = || {
            cells
                .iter()
                .map(|c| (c.parameters, c.indexed))
                .collect::<Vec<_>>()
        };
        assert_eq!(cells.len(), 2, "{method}: {:?}", summary());
        for expected in [ENSTATITE, MONOCLINIC] {
            let found = matching(&cells, expected)
                .unwrap_or_else(|| panic!("{method}: {expected:?} missing in {:?}", summary()));
            // Each grain holds well under half of all spots: the former
            // half-of-the-spots gate rejected it.
            assert!(
                found.indexed * 2 < found.total,
                "{method}: {}",
                found.indexed
            );
            // Spots near nodes of both grains belong to neither.
            assert!(
                found.indexed * 10 >= first.min(second) * 9,
                "{method}: {}",
                found.indexed
            );
        }
    }
}

#[test]
fn random_spots_give_no_lattice() {
    let rng = &mut Lcg(3);
    let q = noise(2000, QMAX, rng);
    for method in ["fft", "rows", "both"] {
        let cells = run(&q, method);
        assert!(
            cells.is_empty(),
            "{method}: {:?}",
            cells
                .iter()
                .map(|c| (c.parameters, c.indexed))
                .collect::<Vec<_>>()
        );
    }
}

#[test]
fn a_cancelled_search_stops() {
    let rng = &mut Lcg(5);
    let q = grain(cell(ENSTATITE), rotation(0.4, 1.1, -0.7), 0.6, rng);
    let control = Control::default();
    control.cancel();
    for method in ["fft", "rows", "both"] {
        assert!(find(&q, &config(method), &control).is_err(), "{method}");
    }
}

#[test]
fn a_third_smaller_grain_is_found_in_the_spots_the_others_leave() {
    let rng = &mut Lcg(13);
    let mut q = grain(cell(ENSTATITE), rotation(0.4, 1.1, -0.7), QMAX, rng);
    q.extend(grain(cell(MONOCLINIC), rotation(-1.3, 0.2, 2.1), QMAX, rng));
    // About a tenth of the spots: a small cell measured to lower q.
    let small = [4.9, 6.1, 7.3, 90., 97., 90.];
    let before = q.len();
    q.extend(grain(cell(small), rotation(2.2, -0.9, 0.5), 0.7, rng));
    let third = q.len() - before;
    q.extend(noise(300, QMAX, rng));
    let q = shuffle(q, rng);
    let cells = run(&q, "both");
    let summary: Vec<_> = cells.iter().map(|c| (c.parameters, c.indexed)).collect();
    assert_eq!(cells.len(), 3, "{summary:?}");
    let found = matching(&cells, small).unwrap_or_else(|| panic!("{summary:?}"));
    assert!(found.indexed * 10 < found.total * 2, "{third}: {summary:?}");
    for expected in [ENSTATITE, MONOCLINIC] {
        assert!(matching(&cells, expected).is_some(), "{summary:?}");
    }
}

#[test]
fn the_method_setting_is_checked_and_restarts_find_lattices() {
    let a = config("both");
    assert!(a.check().is_ok());
    for method in ["fft", "rows"] {
        let b = config(method);
        assert!(b.check().is_ok());
        assert_eq!(a.first_changed(&b), 2);
    }
    assert!(config("hough").check().is_err());
}

#[test]
fn older_configs_and_results_load_with_the_defaults() {
    // A config or recipe saved before the setting existed.
    let mut json = serde_json::to_value(Config::default()).unwrap();
    json.as_object_mut().unwrap().remove("lattice_method");
    let old: Config = serde_json::from_value(json).unwrap();
    assert_eq!(old.lattice_method, "both");
    assert_eq!(Config::default().lattice_method, "both");
    // A candidate stored before `found`: it came from the FFT search.
    let cell = Cell {
        direct: cell(ENSTATITE),
        parameters: ENSTATITE,
        indexed: 10,
        total: 20,
        rms: 0.003,
        validation: 3,
        found: Found::Rows,
        merged: None,
        kept: true,
    };
    let mut json = serde_json::to_value(&cell).unwrap();
    assert_eq!(json["found"], "rows");
    json.as_object_mut().unwrap().remove("found");
    let old: Cell = serde_json::from_value(json).unwrap();
    assert_eq!(old.found, Found::Fft);
    // The products' MessagePack (named fields) too.
    let mut bytes = vec![];
    #[derive(Serialize)]
    struct Before {
        direct: M3,
        parameters: [f64; 6],
        indexed: usize,
        total: usize,
        rms: f64,
        validation: usize,
    }
    Before {
        direct: cell.direct,
        parameters: cell.parameters,
        indexed: 10,
        total: 20,
        rms: 0.003,
        validation: 3,
    }
    .serialize(&mut rmp_serde::Serializer::new(&mut bytes).with_struct_map())
    .unwrap();
    let old: Cell = rmp_serde::from_slice(&bytes).unwrap();
    assert_eq!((old.found, old.indexed), (Found::Fft, 10));
}

#[test]
fn supercells_of_diamond_are_recognised() {
    // Primitive diamond (fcc, a = 3.567 Å) and a 3 × 3 × 3 supercell of it,
    // as found on the anvils' residual reflections; enstatite is not.
    let a = 3.567 / 2.;
    let primitive = [[0., a, a], [a, 0., a], [a, a, 0.]];
    assert!(contains_diamond(primitive));
    let r = rotation(0.3, -0.8, 1.9);
    let supercell = primitive.map(|row| rotate(&r, row.map(|x| 3. * x)));
    assert!(contains_diamond(supercell));
    let mixed = [
        primitive[0].map(|x| 2. * x),
        std::array::from_fn(|j| primitive[0][j] + 3. * primitive[1][j]),
        primitive[2].map(|x| 3. * x),
    ];
    assert!(contains_diamond(mixed));
    assert!(!contains_diamond(cell(ENSTATITE)));
    assert!(!contains_diamond(cell(MONOCLINIC)));
}

#[test]
fn equivalent_settings_are_one_lattice_and_supercells_are_not() {
    let a = [[7., 0., 0.], [0., 9., 0.], [0., 0., 11.]];
    assert!(related(a, [[7., 9., 0.], [0., 9., 0.], [0., 0., 11.]]));
    assert!(!related(a, [[14., 0., 0.], [0., 9., 0.], [0., 0., 11.]]));
}

#[test]
fn max_grains_caps_the_list() {
    let rng = &mut Lcg(13);
    let mut q = grain(cell(ENSTATITE), rotation(0.4, 1.1, -0.7), QMAX, rng);
    q.extend(grain(cell(MONOCLINIC), rotation(-1.3, 0.2, 2.1), QMAX, rng));
    q.extend(grain(
        cell([4.9, 6.1, 7.3, 90., 97., 90.]),
        rotation(2.2, -0.9, 0.5),
        0.7,
        rng,
    ));
    q.extend(noise(300, QMAX, rng));
    let q = shuffle(q, rng);
    for grains in [1, 2] {
        let config = Config {
            max_grains: grains,
            ..config("both")
        };
        let cells = find(&q, &config, &Control::default()).unwrap();
        assert_eq!(cells.len(), grains);
        // The strongest grains first.
        assert!(
            matching(&cells[..1], MONOCLINIC).is_some()
                || matching(&cells[..1], ENSTATITE).is_some()
        );
    }
    let mut config = config("both");
    assert_eq!(config.max_grains, 5);
    config.max_grains = 0;
    assert!(config.check().is_err());
    config.max_grains = 21;
    assert!(config.check().is_err());
    // Older configs load with the default; the setting restarts Find lattices.
    let mut json = serde_json::to_value(Config::default()).unwrap();
    json.as_object_mut().unwrap().remove("max_grains");
    let old: Config = serde_json::from_value(json).unwrap();
    assert_eq!(old.max_grains, 5);
    let changed = Config {
        max_grains: 3,
        ..Config::default()
    };
    assert_eq!(Config::default().first_changed(&changed), 2);
}

fn listed(indexed: usize, total: usize, parameters: [f64; 6]) -> Cell {
    Cell {
        direct: cell(parameters),
        parameters,
        indexed,
        total,
        rms: 0.003,
        validation: indexed / 5,
        found: Found::Fft,
        merged: None,
        kept: false,
    }
}
#[test]
fn only_lattices_with_a_clear_share_of_the_spots_are_ticked() {
    use super::super::processing::{carry_ticks, pretick};
    // Enstatite with 8 grains (real spots, 7413 in all): the two smallest
    // (4 % of the spots) stay unticked.
    let mut cells: Vec<Cell> = [2168, 1092, 722, 545, 442, 372, 306, 290]
        .map(|n| listed(n, 7413, ENSTATITE))
        .into();
    pretick(&mut cells);
    let kept: Vec<_> = cells.iter().map(|c| c.kept).collect();
    assert_eq!(kept, [true, true, true, true, true, true, false, false]);
    // Multi-grain set 4: one lattice with 2.6 % of the spots.
    let mut weak = vec![listed(215, 8176, MONOCLINIC)];
    pretick(&mut weak);
    assert!(!weak[0].kept);
    // Far below the strongest lattice, though 5 % of all spots.
    let mut cells = vec![
        listed(9000, 10000, ENSTATITE),
        listed(600, 10000, MONOCLINIC),
    ];
    pretick(&mut cells);
    assert_eq!((cells[0].kept, cells[1].kept), (true, false));
    // Diamond-like cells (the anvils) are never ticked.
    let mut diamond = vec![listed(900, 1000, [2.522, 2.522, 2.522, 60., 60., 60.])];
    pretick(&mut diamond);
    assert!(!diamond[0].kept);
    // A rerun with the same lattices keeps the user's ticks; another list
    // gets the rule again.
    let mut old = vec![listed(2000, 2737, ENSTATITE), listed(300, 2737, MONOCLINIC)];
    old[0].kept = false;
    old[1].kept = true;
    let mut new = vec![listed(1990, 2737, ENSTATITE), listed(310, 2737, MONOCLINIC)];
    assert!(carry_ticks(&old, &mut new));
    assert_eq!((new[0].kept, new[1].kept), (false, true));
    let mut other = vec![listed(1990, 2737, ENSTATITE)];
    assert!(!carry_ticks(&old, &mut other));
    assert!(!carry_ticks(&[], &mut new));
}

/// Two domains of one enstatite crystal, the second turned by `degrees`
/// about a general axis; spots to 2 Å⁻¹ like the Eiger scan.
fn two_domains(degrees: f64, rng: &mut Lcg) -> (Vec<V3>, M3, M3, usize) {
    let r = rotation(0.4, 1.1, -0.7);
    let t = degrees.to_radians() / 3f64.sqrt();
    let turn = rotation(t, t, t);
    let a = cell(ENSTATITE);
    let b = a.map(|row| rotate(&turn, row));
    let mut q = grain(a, r, 2.0, rng);
    q.extend(grain(b, r, 2.0, rng));
    let measured = q.len();
    q.extend(noise(300, 2.0, rng));
    let place = |d: M3| d.map(|row| rotate(&r, row));
    (shuffle(q, rng), place(a), place(b), measured)
}
/// The list after merging `models` (given in these settings) at `limit`.
fn merged(q: &[V3], models: &[M3], limit: f64) -> Vec<(grains::Grain, Option<Merged>)> {
    let training: Vec<bool> = (0..q.len()).map(|i| i % 5 != 0).collect();
    let o = options(&config("both"), 5);
    let controls = null_rotations();
    let found = grains::validate(q, &training, models, &controls, &o).unwrap();
    assert!(
        found.iter().all(|g| g.accepted),
        "both domains validate apart"
    );
    merge_domains(
        q,
        &training,
        found.into_iter().map(|g| (g, None)).collect(),
        &controls,
        &o,
        limit,
    )
    .unwrap()
    .into_iter()
    .filter(|g| g.0.accepted)
    .collect()
}

#[test]
fn misorientation_compares_lattices_in_any_setting() {
    let a = cell(ENSTATITE);
    let t = 0.26f64.to_radians() / 3f64.sqrt();
    let b = a.map(|row| rotate(&rotation(t, t, t), row));
    // Another setting of b: axes permuted and combined, right-handed.
    let other = [
        b[1],
        b[0].map(|v| -v),
        std::array::from_fn(|j| b[2][j] + b[0][j]),
    ];
    for m in [b, other] {
        let angle = misorientation(a, m).unwrap();
        assert!((angle - 0.26).abs() < 0.03, "{angle}");
    }
    // A lattice symmetry rotation (2-fold about c) maps the nodes onto themselves.
    let flipped = [a[0].map(|v| -v), a[1].map(|v| -v), a[2]];
    assert!(misorientation(a, flipped).unwrap() < 1e-9);
    // Other cells are not one crystal.
    assert!(misorientation(a, cell(MONOCLINIC)).is_none());
    assert!(misorientation(a, cell([5.18, 8.81, 18.5, 90., 90., 90.])).is_none());
}

#[test]
fn domains_a_quarter_degree_apart_merge_into_one_lattice() {
    let rng = &mut Lcg(21);
    let (q, a, b, measured) = two_domains(0.26, rng);
    let setting = [b[1], b[0].map(|v| -v), b[2]];
    let list = merged(&q, &[a, setting], default_merge_angle());
    assert_eq!(list.len(), 1);
    let (g, info) = &list[0];
    let info = info.unwrap();
    assert_eq!(info.domains, 2);
    assert!((info.angle - 0.26).abs() < 0.03, "{}", info.angle);
    let indexed = g.training + g.withheld;
    assert!(indexed * 100 >= measured * 95, "{indexed} of {measured}");
    // The whole Find lattices step gives one lattice too.
    let cells = run(&q, "both");
    assert_eq!(
        cells.len(),
        1,
        "{:?}",
        cells.iter().map(|c| c.indexed).collect::<Vec<_>>()
    );
    assert!(
        cells[0].indexed * 100 >= measured * 95,
        "{} of {measured}",
        cells[0].indexed
    );
    assert!(matching(&cells, ENSTATITE).is_some());
}

#[test]
fn domains_two_degrees_apart_or_merging_off_stay_apart() {
    let rng = &mut Lcg(23);
    let (q, a, b, _) = two_domains(2., rng);
    let list = merged(&q, &[a, b], default_merge_angle());
    assert_eq!(list.len(), 2);
    assert!(list.iter().all(|g| g.1.is_none()));
    let rng = &mut Lcg(21);
    let (q, a, b, _) = two_domains(0.26, rng);
    assert_eq!(merged(&q, &[a, b], 0.).len(), 2);
}

#[test]
fn a_merge_that_loses_spots_is_refused() {
    // Within a 3° limit, but one lattice between domains 2° apart misses
    // most spots beyond about 0.9 Å⁻¹.
    let rng = &mut Lcg(23);
    let (q, a, b, _) = two_domains(2., rng);
    let list = merged(&q, &[a, b], 3.);
    assert_eq!(list.len(), 2);
    assert!(list.iter().all(|g| g.1.is_none()));
}

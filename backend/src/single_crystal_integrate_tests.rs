//! Integrate glue on synthetic data: the step in a session (counts under
//! masks, the intensity in use, profile fallback, snapshot, table, export,
//! invalidation, transfer) and the HKLF 4 writer. The science (prediction,
//! measurement, flags, merging) is PhaseSmith's and tested there.
use super::super::refine::tests::{Lcg, call, lattice, rotation};
use super::*;

#[test]
fn hklf4_lines_are_fixed_width_and_scaled_to_fit() {
    let mut text = Vec::new();
    let rows = [([1i64, -2, 3], 123.456, 7.8), ([-10, 0, 99], -5., 2.)];
    let scale = write_hklf4(rows.iter().copied(), &mut text).unwrap();
    assert_eq!(scale, 1.);
    let text = String::from_utf8(text).unwrap();
    assert_eq!(
        text,
        "   1  -2   3  123.46    7.80\n -10   0  99   -5.00    2.00\n   0   0   0    0.00    0.00\n"
    );
    let mut big = Vec::new();
    let scale = write_hklf4([([1i64, 0, 0], 99990., 100.)].into_iter(), &mut big).unwrap();
    assert!((scale - 0.1).abs() < 1e-12);
    assert!(
        String::from_utf8(big)
            .unwrap()
            .starts_with("   1   0   0 9999.00   10.00")
    );
}

/// erf to 1.5e-7 (Abramowitz & Stegun 7.1.26).
fn erf(x: f64) -> f64 {
    let t = 1. / (1. + 0.3275911 * x.abs());
    let y = 1.
        - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t
            + 0.254829592)
            * t
            * (-x * x).exp();
    y.copysign(x)
}
fn interval(lo: f64, hi: f64, centre: f64, sigma: f64) -> f64 {
    0.5 * (erf((hi - centre) / (sigma * 2f64.sqrt())) - erf((lo - centre) / (sigma * 2f64.sqrt())))
}
/// Standard normal deviate from two uniforms (Box-Muller).
fn gauss(rng: &mut Lcg) -> f64 {
    let u = rng.next().max(1e-300);
    (-2. * u.ln()).sqrt() * (std::f64::consts::TAU * rng.next()).cos()
}

/// A spot to draw: centre x, y, ω, total counts and ω spread (degrees).
struct Spot {
    xyz: V3,
    counts: f64,
    spread: f64,
}
/// Frame `f`: a tilted background plane, the spots (Gaussian, 0.8 px) and
/// Poisson-like noise, seeded per frame.
fn frame(f: usize, spots: &[Spot], s: &ps::Scan, shape: [usize; 2]) -> Vec<f64> {
    let [h, w] = shape;
    let mut v: Vec<f64> = (0..h * w)
        .map(|i| 30. + 0.02 * (i % w) as f64 + 0.01 * (i / w) as f64)
        .collect();
    let [lo, hi] = s.bounds(f);
    for spot in spots {
        let share = interval(lo, hi, spot.xyz[2], spot.spread);
        if share * spot.counts < 1e-3 {
            continue;
        }
        let (cx, cy) = (spot.xyz[0], spot.xyz[1]);
        for y in (cy as isize - 6).max(0)..(cy as isize + 7).min(h as isize) {
            for x in (cx as isize - 6).max(0)..(cx as isize + 7).min(w as isize) {
                let fx = interval(x as f64 - 0.5, x as f64 + 0.5, cx, 0.8);
                let fy = interval(y as f64 - 0.5, y as f64 + 0.5, cy, 0.8);
                v[y as usize * w + x as usize] += spot.counts * share * fx * fy;
            }
        }
    }
    let mut rng = Lcg(1000 + f as u64);
    v.iter()
        .map(|&m| (m + m.sqrt() * gauss(&mut rng)).max(0.))
        .collect()
}

/// A session with a 20-frame scan of 128 × 128 px TIFFs holding the spots of
/// a cubic 5 Å crystal on the geometry of the calibration, after Refine
/// geometry (stages 0-4 marked done, the lattice refined as cP).
fn integrated_session() -> (tempfile::TempDir, Session, M3) {
    let dir = tempfile::tempdir().unwrap();
    let poni = dir.path().join("detector.poni");
    std::fs::write(
        &poni,
        "poni_version: 2\nDetector: Detector\nDetector_config: {\"pixel1\":0.00125,\"pixel2\":0.00125}\nDistance: 0.15\nPoni1: 0.08\nPoni2: 0.08\nRot1: 0\nRot2: 0\nRot3: 0\nWavelength: 2.846e-11\n",
    )
    .unwrap();
    let write = |folder: &Path, frames: &[Vec<f64>]| -> Vec<String> {
        std::fs::create_dir_all(folder).unwrap();
        frames
            .iter()
            .enumerate()
            .map(|(i, v)| {
                let path = folder.join(format!("scan_{i:04}.tif"));
                // Stored rows run top-down; Dioptas arrays bottom-up.
                let counts: Vec<u16> = v
                    .as_chunks::<128>()
                    .0
                    .iter()
                    .rev()
                    .flatten()
                    .map(|x| x.round().clamp(0., 65000.) as u16)
                    .collect();
                tiff::encoder::TiffEncoder::new(File::create(&path).unwrap())
                    .unwrap()
                    .write_image::<tiff::encoder::colortype::Gray16>(128, 128, &counts)
                    .unwrap();
                path.to_string_lossy().into_owned()
            })
            .collect()
    };
    let config = |s: &Session| Config {
        confirmed: true,
        integration_method: "summation".into(),
        background: false,
        cell_masks_enabled: false,
        axis: [-1., 0., 0.],
        omega_start: -5.,
        integration_d_min: Some(1.2),
        profile_fitting: Some(false),
        ..s.scxrd.config.clone()
    };
    let open = |paths: Vec<String>| {
        let mut s = Session::new(PathBuf::new());
        assert_eq!(
            call(&mut s, "scxrd_load", json!({"paths":paths})).result["ok"],
            true
        );
        let r = call(
            &mut s,
            "scxrd_file",
            json!({"operation":"calibration","path":poni}),
        );
        assert_eq!(r.result["ok"], true, "{:?}", r.result);
        let c = config(&s);
        let r = call(&mut s, "scxrd_settings", json!({"config":c}));
        assert_eq!(r.result["ok"], true, "{:?}", r.result);
        s
    };
    // The geometry the session derives from the calibration.
    let flat = vec![vec![30.; 128 * 128]; 20];
    let probe = open(write(&dir.path().join("flat"), &flat));
    let g = probe.scxrd.pose_geometry().unwrap().native();
    let direct = lattice([5., 5., 5., 90., 90., 90.], rotation(0.4, 0.2, -0.3));
    let s = scan_of(&probe.scxrd.config, 20, &[]).unwrap();
    let l = ps::Lattice::new(direct, Bravais::CubicP).unwrap();
    let p = ps::predict(
        &[l],
        &g,
        &s,
        [128, 128],
        &ps::PredictOptions::new(1.2, 0.5),
        None,
    )
    .unwrap();
    assert!(p.len() >= 8, "{}", p.len());
    let spots: Vec<Spot> = p
        .iter()
        .map(|p| Spot {
            xyz: p.xyz,
            counts: 2000.,
            spread: 0.05 / p.zeta.abs().max(0.05),
        })
        .collect();
    let frames: Vec<Vec<f64>> = (0..20).map(|f| frame(f, &spots, &s, [128, 128])).collect();
    let mut session = open(write(&dir.path().join("spots"), &frames));
    let c = &mut session.scxrd;
    c.cells = vec![super::super::refine::tests::found(direct)];
    c.selected = Some(0);
    let cell = [5., 5., 5., 90., 90., 90.];
    c.refined = vec![refine::Refined {
        lattice: 0,
        candidates: vec![refine::Candidate {
            bravais: "cP".into(),
            transform: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            cell,
            constrained: cell,
            idealized: direct,
            length_deviation: 0.,
            angle_deviation: 0.,
        }],
        chosen: 0,
        result: Some(refine::Refinement {
            bravais: "cP".into(),
            conventional: direct,
            cell,
            cell_su: [0.001, 0.001, 0.001, 0., 0., 0.],
            volume: 125.,
            volume_su: 0.1,
            rms: 0.001,
            used: 50,
            owned: 50,
            converged: true,
        }),
        error: None,
    }];
    c.adopt_refinement();
    for stage in &mut c.stages[..5] {
        stage.status = "complete".into();
    }
    (dir, session, direct)
}

#[test]
fn the_step_measures_shows_exports_and_is_cleared_by_its_settings() {
    let (dir, mut s, _) = integrated_session();
    let r = call(&mut s, "scxrd_run", json!({"stage":5}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(
        s.scxrd.stages[5].status, "complete",
        "{:?}",
        s.scxrd.stages[5].detail
    );
    let i = s.scxrd.integration.clone().unwrap();
    let l = &i.lattices[0];
    assert_eq!(i.settings.d_min, 1.2);
    assert_eq!(l.stats.laue, "m-3m");
    assert!(l.stats.usable >= 5, "{:?}", l.stats);
    assert!(l.stats.r_int.is_some_and(|r| r < 0.2), "{:?}", l.stats);
    for r in l.rows.iter().filter(|r| r.usable()) {
        assert!(r.intensity / r.sigma > 10., "{r:?}");
    }
    // Summation only: the intensity in use is the summed one, no profile.
    assert!(!i.settings.profiles && l.stats.profile.is_none());
    assert!(l.rows.iter().all(|r| !r.profiled
        && r.profile.is_none()
        && r.intensity.to_bits() == r.summed[0].to_bits()));
    assert_eq!(l.stats.predicted, l.rows.len());
    assert!(l.rows.iter().all(|r| r.flags & ps::HIDDEN == 0));
    // The older later steps read the first lattice's reflections.
    assert_eq!(s.scxrd.reflections.len(), l.stats.measured);
    // Snapshot: summary, markers of the shown frame, table page.
    let snap = &r.result["scxrd"];
    assert_eq!(
        snap["integration"]["lattices"][0]["stats"]["usable"],
        l.stats.usable
    );
    let box_size = snap["integration"]["defaults"]["box_size"]
        .as_u64()
        .unwrap();
    assert!(box_size >= 5 && box_size % 2 == 1, "{box_size}");
    assert_eq!(
        snap["integration"]["defaults"]["profiles"],
        PROFILES_DEFAULT
    );
    assert_eq!(snap["integratedTable"]["count"], l.rows.len());
    let frame = l.rows.iter().find(|r| r.usable()).unwrap().frames[0];
    let r = call(&mut s, "scxrd_frame", json!({"frame":frame}));
    assert!(
        !r.result["scxrd"]["integratedMarkers"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let r = call(
        &mut s,
        "scxrd_table",
        json!({"kind":"integrated","lattice":0,"offset":0,"filter":"usable"}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let table = &r.result["scxrd"]["integratedTable"];
    assert_eq!(table["count"], l.stats.usable);
    let first = &table["rows"][0];
    assert_eq!(first["summed"][0], first["i"]);
    assert!(first["profile"].is_null() && first["profiled"] == false);
    let r = call(
        &mut s,
        "scxrd_table",
        json!({"kind":"integrated","lattice":3,"offset":0}),
    );
    assert_eq!(r.result["ok"], false);
    // Export: HKLF 4 of the usable reflections and the cell beside it.
    let path = dir.path().join("lattice-1.hkl");
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"hkl","lattice":0,"path":path}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let text = std::fs::read_to_string(&path).unwrap();
    assert_eq!(text.lines().count(), l.stats.usable + 1);
    assert!(text.lines().all(|line| line.len() == 28));
    let p4p = std::fs::read_to_string(path.with_extension("p4p")).unwrap();
    assert!(
        p4p.contains("CELL   5.00000 5.00000 5.00000 90.0000"),
        "{p4p}"
    );
    // Transfer (development reload and restart recovery) carries the step.
    let saved = s.scxrd.transfer("g", false).unwrap();
    for kind in [Transfer::Development, Transfer::Recovery] {
        let (c, summary) = Crystal::restore(
            Ok(saved.essentials.clone()),
            Ok(saved.products.clone()),
            "g",
            kind,
            &Control::default(),
        );
        assert!(summary.is_none(), "{summary:?}");
        assert_eq!(c.stages[5].status, "complete");
        assert_eq!(c.integration.as_ref(), Some(&i));
        assert_eq!(c.reflections.len(), l.stats.measured);
    }
    // Without a done Refine geometry it is not carried.
    let mut products: Value = rmp_serde::from_slice(&saved.products).unwrap();
    products["pose_stage"]["status"] = json!("pending");
    let (c, _) = Crystal::restore(
        Ok(saved.essentials.clone()),
        Ok(rmp_serde::to_vec_named(&products).unwrap()),
        "g",
        Transfer::Development,
        &Control::default(),
    );
    assert!(c.integration.is_none() && c.stages[5].status == "pending");
    // An Integrate setting clears only this step and later ones.
    let mut changed = s.scxrd.config.clone();
    changed.rocking_width = Some(1.);
    assert_eq!(s.scxrd.config.first_changed(&changed), 5);
    let r = call(&mut s, "scxrd_settings", json!({"config":changed}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert!(s.scxrd.integration.is_none() && s.scxrd.reflections.is_empty());
    assert_eq!(s.scxrd.stages[5].status, "pending");
    assert!(s.scxrd.stages[..5].iter().all(|st| st.status == "complete"));
    assert_eq!(s.scxrd.integration_settings().unwrap().rocking, 1.);
    // Out-of-range or even boxes are refused.
    for size in [2, 10] {
        changed.integration_box = Some(size);
        let r = call(&mut s, "scxrd_settings", json!({"config":changed}));
        assert_eq!(r.result["ok"], false);
    }
    // An earlier step clears it too.
    call(&mut s, "scxrd_run", json!({"stage":5}));
    assert!(s.scxrd.integration.is_some());
    s.scxrd.invalidate(4);
    assert!(s.scxrd.integration.is_none());
}

#[test]
fn masked_centres_are_counted_and_profiles_fall_back_to_summation() {
    let (_dir, mut s, _) = integrated_session();
    let r = call(&mut s, "scxrd_run", json!({"stage":5}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let base = s.scxrd.integration.clone().unwrap().lattices.remove(0);
    // A shape estimate (too few spots here for PhaseSmith's) is the default
    // and survives Integrate changes.
    let shape = Some(Shape {
        rocking: 0.73,
        rocking_sigma: 0.12,
        box_size: Some(11),
        spot_sigma: Some([1.2, 1.2]),
        reflections: 40,
        at_step_floor: false,
    });
    s.scxrd.integration_shape = shape;
    let d = s.scxrd.integration_defaults().unwrap();
    assert_eq!((d.box_size, d.rocking, d.rocking_floor), (11, 0.73, false));
    // A step-floor estimate says so until the user sets a width.
    s.scxrd.integration_shape = shape.map(|s| Shape {
        at_step_floor: true,
        ..s
    });
    assert!(s.scxrd.integration_settings().unwrap().rocking_floor);
    s.scxrd.config.rocking_width = Some(0.6);
    assert!(!s.scxrd.integration_settings().unwrap().rocking_floor);
    s.scxrd.config.rocking_width = None;
    s.scxrd.integration_shape = shape;
    // Reflections centred on an excluded frame count as under masks.
    let scan = scan_of(&s.scxrd.config, 20, &[]).unwrap();
    let centred = |f: usize| {
        base.rows
            .iter()
            .filter(|r| scan.frame_of(r.xyz[2]) == f)
            .count()
    };
    let frame = (0..20).max_by_key(|&f| centred(f)).unwrap();
    assert!(centred(frame) > 0);
    s.scxrd.excluded_frames = vec![frame];
    s.scxrd.invalidate(5);
    assert_eq!(
        s.scxrd.integration_shape, shape,
        "an Integrate change keeps the estimate"
    );
    let r = call(&mut s, "scxrd_run", json!({"stage":5}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let l = &s.scxrd.integration.as_ref().unwrap().lattices[0];
    assert_eq!(l.stats.hidden, base.stats.hidden + centred(frame));
    assert_eq!(l.stats.predicted, base.stats.predicted - centred(frame));
    assert_eq!(l.stats.predicted, l.rows.len());
    let snap = &r.result["scxrd"]["integration"]["lattices"][0]["stats"];
    assert_eq!(snap["hidden"], l.stats.hidden);
    // Profile fitting is an Integrate setting; too few strong reflections
    // to learn profiles leave every reflection on its summed intensity.
    s.scxrd.excluded_frames.clear();
    let mut changed = s.scxrd.config.clone();
    changed.profile_fitting = Some(true);
    assert_eq!(s.scxrd.config.first_changed(&changed), 5);
    let r = call(&mut s, "scxrd_settings", json!({"config":changed}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let r = call(&mut s, "scxrd_run", json!({"stage":5}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let i = s.scxrd.integration.as_ref().unwrap();
    let l = &i.lattices[0];
    assert!(i.settings.profiles);
    let status = l.stats.profile.clone().unwrap();
    for r in &l.rows {
        let used = if r.profiled {
            r.profile.map(|p| p.intensity).unwrap()
        } else {
            r.summed[0]
        };
        assert_eq!(r.intensity.to_bits(), used.to_bits(), "{r:?}");
    }
    // The summed values do not depend on profile fitting.
    let profiled = l.clone();
    let mut changed = s.scxrd.config.clone();
    changed.profile_fitting = Some(false);
    call(&mut s, "scxrd_settings", json!({"config":changed}));
    let r = call(&mut s, "scxrd_run", json!({"stage":5}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let summed = &s.scxrd.integration.as_ref().unwrap().lattices[0];
    assert_eq!(summed.rows.len(), profiled.rows.len());
    for (a, b) in summed.rows.iter().zip(&profiled.rows) {
        assert_eq!(a.summed.map(f64::to_bits), b.summed.map(f64::to_bits));
    }
    if status.starts_with("failed") {
        assert_eq!(profiled.stats.profiled, 0);
        assert_eq!(profiled.stats.usable, summed.stats.usable, "{status}");
    }
    // A pose change drops the estimate.
    s.scxrd.invalidate(4);
    assert!(s.scxrd.integration_shape.is_none());
}

#[test]
fn phasesmith_errors_are_told_apart_by_kind() {
    use phasesmith_single_crystal::spots::SpotError;
    let control = Control::default();
    let cancelled = failure(&control, SpotError("measurement cancelled".into()));
    assert_eq!(cancelled, "Integrate was cancelled.");
    let read = failure(
        &control,
        SpotError("frame read failed at frame 7: disk gone".into()),
    );
    assert!(read.starts_with("Integrate could not read a frame") && read.contains("frame 7"));
    assert!(failure(&control, SpotError("bad box".into())).starts_with("Integrate failed: "));
    assert_eq!(profile_reasons(0), "");
    assert_eq!(
        profile_reasons(phasesmith_single_crystal::spots::profiles::MISMATCH | ps::OVERLAP),
        "overlap, mismatch"
    );
}

#[test]
fn the_engine_names_the_linked_phasesmith() {
    // Cargo.lock's version must be the one the PhaseSmith crates were built as.
    let expected = format!(
        "PhaseSmith {} / ",
        phasesmith_io::NATIVE_CIF_BACKEND_VERSION
    );
    assert!(ENGINE.starts_with(&expected), "{ENGINE}");
    let commit = ENGINE.rsplit(" / ").next().unwrap();
    assert!(
        commit.len() == 8 && commit.chars().all(|c| c.is_ascii_hexdigit()),
        "{ENGINE}"
    );
}

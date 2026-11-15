//! Find spots: setting changes redo only the affected part, and every path
//! gives exactly the result of a fresh full run.
use super::*;
fn call(s: &mut Session, action: &str, payload: Value) -> Reply {
    s.invoke(&Request {
        id: 1,
        action: action.into(),
        payload,
        cached_buffers: vec![],
    })
}
fn settings(s: &mut Session, c: &Config) {
    let r = call(s, "scxrd_settings", json!({"config":c}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
}
fn run(s: &mut Session) {
    let r = call(s, "scxrd_run", json!({"stage":1}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
}
/// Observations and tracks with every float as its exact bit pattern.
fn record(c: &Crystal) -> Value {
    let bits = |v: f64| format!("{:016x}", v.to_bits());
    json!({
        "peaks": c.peaks.iter().map(|p| json!([p.frame, bits(p.xy[0]), bits(p.xy[1]),
            bits(p.intensity), p.flags, p.bounds, p.track])).collect::<Vec<_>>(),
        "tracks": c.tracks.iter().map(|t| json!([t.observed.map(bits), t.first, t.last,
            t.bounds, t.flags])).collect::<Vec<_>>(),
        "detail": c.stages[1].detail,
    })
}
fn digest_of(v: &Value) -> String {
    let mut hash = Sha256::new();
    hash.update(v.to_string().as_bytes());
    format!("{:x}", hash.finalize())
}

/// Find spots on the Eiger enstatite scan with all masks, then each setting
/// change in turn (as a user would), compared with the result recorded from
/// the code before the Find spots speed-ups (15.11.2026): counts and every
/// observation's frame, centroid, intensity, flags, box and track, and every
/// track. `DIOPTAS_SCXRD_FIND_SPOTS_RECORD` writes the records to a file;
/// `DIOPTAS_SCXRD_FIND_SPOTS_REFERENCE` compares spot by spot with such a file.
#[test]
#[ignore = "Local Eiger scan and PONI required (DIOPTAS_SCXRD_MEASURED_DIR)"]
fn measured_find_spots_matches_reference() {
    let root =
        PathBuf::from(std::env::var("DIOPTAS_SCXRD_MEASURED_DIR").expect("measured directory"));
    let mut s = Session::new(PathBuf::new());
    let r = call(
        &mut s,
        "scxrd_load",
        json!({"path":root.join("eiger_0000.h5")}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let poni = root.join("CeO2_20240620_1849_dioptas.poni");
    let r = call(
        &mut s,
        "scxrd_file",
        json!({"operation":"calibration","path":poni}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let mut c = Config {
        confirmed: true,
        integration_method: "summation".into(),
        protocol: None,
        background: false,
        axis: [-1., 0., 0.],
        omega_start: -37.5,
        omega_step: 0.5,
        exposure: 0.5,
        cell_masks_enabled: true,
        dac_enabled: true,
        seat_enabled: true,
        seat_threshold: 0.6,
        seat_guard: 20,
        diamond_enabled: true,
        persistent_enabled: true,
        link_radius: 3.,
        refine_geometry: false,
        ..s.scxrd.config.clone()
    };
    settings(&mut s, &c);
    // (label, change, shown frame)
    type Change = fn(&mut Config);
    let steps: [(&str, Change, usize); 8] = [
        ("defaults", |_| {}, 0),
        ("threshold 6", |c| c.threshold = 6., 0),
        ("threshold 4", |c| c.threshold = 4., 72),
        ("min area 5", |c| c.min_pixels = 5, 72),
        ("link radius 5", |c| c.link_radius = 5., 72),
        ("min area 3", |c| c.min_pixels = 3, 72),
        ("link radius 3", |c| c.link_radius = 3., 0),
        ("threshold 5", |c| c.threshold = 5., 0),
    ];
    let mut records = vec![];
    for (label, change, frame) in steps {
        change(&mut c);
        settings(&mut s, &c);
        s.scxrd.frame = frame;
        // When the live preview first shows the shown frame.
        let control = Arc::new(Control::default());
        let done = std::sync::atomic::AtomicBool::new(false);
        let clock = std::time::Instant::now();
        let first_preview = std::thread::scope(|scope| {
            let watch = scope.spawn(|| {
                while !done.load(std::sync::atomic::Ordering::Relaxed) {
                    let p = control.progress_reply().result;
                    if p["progress"]["scxrdPreview"]["frame"] == frame {
                        return Some(clock.elapsed().as_secs_f64());
                    }
                    std::thread::sleep(std::time::Duration::from_millis(2));
                }
                None
            });
            let r = s.invoke_controlled(
                &Request {
                    id: 1,
                    action: "scxrd_run".into(),
                    payload: json!({"stage":1}),
                    cached_buffers: vec![],
                },
                control.clone(),
            );
            assert_eq!(r.result["ok"], true, "{:?}", r.result);
            done.store(true, std::sync::atomic::Ordering::Relaxed);
            watch.join().unwrap()
        });
        let seconds = clock.elapsed().as_secs_f64();
        let r = record(&s.scxrd);
        let preview = first_preview.map_or("-".into(), |t| format!("{t:.2} s"));
        let components = s
            .scxrd
            .detections
            .as_ref()
            .and_then(|d| d.components.as_ref())
            .map_or(0, |c| c.iter().map(Vec::len).sum::<usize>());
        eprintln!(
            "{label:14} {seconds:6.2} s (shown frame {frame} at {preview})  {} obs  {} tracks  {components} components kept  {}",
            s.scxrd.peaks.len(),
            s.scxrd.tracks.len(),
            digest_of(&r)
        );
        records.push(json!({"label":label,"record":r}));
    }
    if let Ok(path) = std::env::var("DIOPTAS_SCXRD_FIND_SPOTS_RECORD") {
        std::fs::write(path, serde_json::to_string(&records).unwrap()).unwrap();
    }
    if let Ok(path) = std::env::var("DIOPTAS_SCXRD_FIND_SPOTS_REFERENCE") {
        let reference: Vec<Value> =
            serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        for (a, b) in records.iter().zip(&reference) {
            let label = &a["label"];
            for kind in ["peaks", "tracks"] {
                let (x, y) = (
                    a["record"][kind].as_array().unwrap(),
                    b["record"][kind].as_array().unwrap(),
                );
                assert_eq!(x.len(), y.len(), "{label} {kind} count");
                for (i, (p, q)) in x.iter().zip(y).enumerate() {
                    assert_eq!(p, q, "{label} {kind} {i}");
                }
            }
        }
    }
    let digests: Vec<_> = records.iter().map(|r| digest_of(&r["record"])).collect();
    assert_eq!(
        digests, REFERENCE_DIGESTS,
        "records differ from the reference"
    );
}
/// Digests of the records of `measured_find_spots_matches_reference`,
/// recorded with the code before the Find spots speed-ups.
const REFERENCE_DIGESTS: [&str; 8] = [
    "4ec8c17691f77c389ed1d6b722fe4ef1a9e115da43997da959c1fdebd6479930",
    "5d9ca3682d214aade35e123eceaa0d9b9a9ee308aea46d5954fd338fa4d98d88",
    "24213c66f4e5640d392f60c6c365784d172428b555a08123103be1c93f3fed1e",
    "0b593b55eb444d396d5c291b65054e3469eaad3ab5a197cae9db307c44e2758c",
    "cf1d40e6ad7d5b57480178a9721c81e23794cf7cad338571a0bc40dafd2917f7",
    "b0d97c08a2380dd8a8e82a6cff7dc9b48e86ede6a2202423c7d09d5b1900f35a",
    "24213c66f4e5640d392f60c6c365784d172428b555a08123103be1c93f3fed1e",
    "4ec8c17691f77c389ed1d6b722fe4ef1a9e115da43997da959c1fdebd6479930",
];

/// 12 frames of 48×48 counts: background 20 with Poisson-like noise, a 3×3
/// reflection moving 4 px per frame along x on frames 2-7 (linked at Link
/// radius 5, not at 3), and on every frame a 3×3, a 2×2 (4 px) and a 1×2
/// (2 px) spot, so Minimum area 3 and 5 keep different spots.
fn spot_session() -> (tempfile::TempDir, Session) {
    let dir = tempfile::tempdir().unwrap();
    let (h, w) = (48usize, 48usize);
    let mut seed = 777u64;
    let mut normal = move || {
        let mut u = || {
            seed = seed
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            ((seed >> 11) as f64 + 0.5) / (1u64 << 53) as f64
        };
        let (a, b) = (u(), u());
        (-2. * a.ln()).sqrt() * (std::f64::consts::TAU * b).cos()
    };
    let mut paths = vec![];
    for f in 0..12usize {
        let mut counts = vec![0u16; h * w];
        for y in 0..h {
            for x in 0..w {
                let mut b: f64 = 20.;
                let mover = 8 + 4 * f.saturating_sub(2);
                if (2..8).contains(&f) && y.abs_diff(12) <= 1 && x.abs_diff(mover) <= 1 {
                    b += 300.;
                }
                if y.abs_diff(36) <= 1 && x.abs_diff(10 + f % 3) <= 1 {
                    b += 250.;
                }
                if (30..32).contains(&y) && (30..32).contains(&x) {
                    b += 250.;
                }
                if y == 40 && (38..40).contains(&x) {
                    b += 250.;
                }
                counts[y * w + x] = (b + normal() * b.sqrt()).round().max(0.) as u16;
            }
        }
        let path = dir.path().join(format!("spots_{f:04}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&path).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray16>(w as u32, h as u32, &counts)
            .unwrap();
        paths.push(path.to_string_lossy().into_owned());
    }
    let mut s = Session::new(PathBuf::new());
    let r = call(&mut s, "scxrd_load", json!({"paths":paths}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let c = spot_config(&s);
    settings(&mut s, &c);
    (dir, s)
}
fn spot_config(s: &Session) -> Config {
    Config {
        confirmed: true,
        integration_method: "summation".into(),
        protocol: None,
        background: false,
        dac_enabled: false,
        seat_enabled: false,
        diamond_enabled: false,
        persistent_enabled: false,
        threshold: 5.,
        min_pixels: 3,
        link_radius: 3.,
        ..s.scxrd.config.clone()
    }
}
/// The result of a fresh session with these settings and shown frame.
fn fresh(c: &Config, frame: usize) -> Value {
    let (_dir, mut s) = spot_session();
    settings(&mut s, c);
    s.scxrd.frame = frame;
    run(&mut s);
    record(&s.scxrd)
}

/// A Link radius change links the kept observations again without finding
/// them anew, and gives what a fresh run with that radius gives.
#[test]
fn link_radius_change_relinks_without_detecting() {
    let (_dir, mut s) = spot_session();
    run(&mut s);
    let observed = s.scxrd.detections.clone().expect("observations kept");
    let tracks = s.scxrd.tracks.len();
    let mut c = s.scxrd.config.clone();
    c.link_radius = 5.;
    settings(&mut s, &c);
    assert_eq!(s.scxrd.stages[1].status, "pending");
    run(&mut s);
    let again = s.scxrd.detections.clone().unwrap();
    assert!(Arc::ptr_eq(&observed, &again), "observations found anew");
    assert!(
        s.scxrd.tracks.len() < tracks,
        "the moving spot is one track at 5 px"
    );
    assert_eq!(record(&s.scxrd), fresh(&c, 0));
    // Settings the observations depend on find them anew, and equal a fresh run.
    for change in [
        (|c: &mut Config| c.threshold = 7.) as fn(&mut Config),
        |c| c.min_pixels = 5,
    ] {
        change(&mut c);
        settings(&mut s, &c);
        run(&mut s);
        let now = s.scxrd.detections.clone().unwrap();
        assert!(!Arc::ptr_eq(&again, &now));
        assert_eq!(record(&s.scxrd), fresh(&c, 0));
    }
    // A mask change finds them anew too.
    let before = s.scxrd.detections.clone().unwrap();
    s.scxrd.mask.push([0, 0, 4, 4]);
    s.scxrd.invalidate(1);
    run(&mut s);
    assert!(!Arc::ptr_eq(&before, &s.scxrd.detections.clone().unwrap()));
}

/// A Minimum area change measures the kept components again without
/// detecting, and gives what a fresh run with that minimum gives, whether
/// the minimum rises or falls; other detection settings detect anew.
#[test]
fn min_area_change_measures_without_detecting() {
    let (_dir, mut s) = spot_session();
    let mut c = s.scxrd.config.clone();
    c.min_pixels = 1;
    settings(&mut s, &c);
    run(&mut s);
    let components = |s: &Session| {
        s.scxrd
            .detections
            .as_ref()
            .and_then(|d| d.components.clone())
            .expect("components kept")
    };
    let kept = components(&s);
    let all: usize = kept.iter().map(Vec::len).sum();
    let spots = s.scxrd.peaks.len();
    assert!(
        spots > 0 && spots == all,
        "every component is a spot at 1 px"
    );
    let mut counts = vec![spots];
    for min in [4, 9, 2, 1] {
        c.min_pixels = min;
        settings(&mut s, &c);
        assert_eq!(s.scxrd.stages[1].status, "pending");
        run(&mut s);
        assert!(
            Arc::ptr_eq(&kept, &components(&s)),
            "detected anew at {min}"
        );
        assert_eq!(record(&s.scxrd), fresh(&c, 0), "min area {min}");
        counts.push(s.scxrd.peaks.len());
    }
    assert!(counts[2] < counts[1] && counts[1] < counts[0], "{counts:?}");
    assert_eq!(counts[4], counts[0]);
    c.threshold = 7.;
    settings(&mut s, &c);
    run(&mut s);
    assert!(!Arc::ptr_eq(&kept, &components(&s)));
    assert_eq!(record(&s.scxrd), fresh(&c, 0));
}

/// Detecting the shown frame first changes nothing in the result, whichever
/// frame is shown (also an excluded one).
#[test]
fn shown_frame_first_gives_the_same_result() {
    let (_dir, s) = spot_session();
    let c = s.scxrd.config.clone();
    let reference = fresh(&c, 0);
    assert!(reference["peaks"].as_array().unwrap().len() >= 12);
    for frame in [5, 11] {
        assert_eq!(fresh(&c, frame), reference, "shown frame {frame}");
    }
    let (_dir, mut s) = spot_session();
    s.scxrd.excluded_frames = vec![4];
    s.scxrd.frame = 4;
    run(&mut s);
    let excluded = record(&s.scxrd);
    let (_dir, mut s) = spot_session();
    s.scxrd.excluded_frames = vec![4];
    run(&mut s);
    assert_eq!(record(&s.scxrd), excluded);
}

/// The run-wise shadow fill gives exactly the per-pixel mask (`excluded`):
/// DAC cells, seat fields with lit, dark and edge cells, blocks that do not
/// divide the detector, frames outside the shadow range and the per-block
/// illumination of profile masks.
#[test]
fn shadow_fill_equals_the_per_pixel_mask() {
    let mut seed = 99u64;
    let mut next = move || {
        seed = seed
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (seed >> 33) as usize
    };
    for (h, w, block) in [(37usize, 53usize, 8usize), (64, 64, 16), (21, 30, 4)] {
        let (rows, columns) = (h.div_ceil(block), w.div_ceil(block));
        let cells = rows * columns;
        let frames = 4;
        let seat: Vec<u8> = (0..frames * cells)
            .map(|i| match next() % 4 {
                0 => 0,
                1 => 255,
                2 => 127 - (i % 2) as u8,
                _ => (next() % 256) as u8,
            })
            .collect();
        let dac: Vec<bool> = (0..frames * cells).map(|_| next() % 7 == 0).collect();
        let illumination: Vec<bool> = (0..frames * cells).map(|_| next() % 3 == 0).collect();
        for (seat, dac) in [
            (seat.clone(), dac.clone()),
            (seat.clone(), vec![]),
            (vec![], dac.clone()),
        ] {
            let shadows = Shadows {
                first: 1,
                last: frames,
                block,
                columns,
                cells,
                illumination: illumination.clone(),
                dac,
                seat,
                report: Value::Null,
            };
            for frame in 0..=frames + 1 {
                let mut fast = vec![false; h * w];
                fast[3] = true;
                shadows.fill(frame, &mut fast, w);
                let slow: Vec<bool> = (0..h * w)
                    .map(|i| i == 3 || shadows.excluded(frame, i, w))
                    .collect();
                assert_eq!(fast, slow, "{h}x{w} block {block} frame {frame}");
            }
        }
    }
}

/// The count-identity guard: through the raw-chunk reader a frame is hashed
/// on its first read only, and still every read whose counts differ from the
/// recorded digest fails: a source recording another digest (a restored
/// project) and a file changed on disk.
#[test]
fn raw_reads_keep_the_count_identity_guard() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("scan.h5");
    let fixture = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/combined-counts.h5");
    std::fs::copy(fixture, &path).unwrap();
    let mut s = Session::new(PathBuf::new());
    let r = call(&mut s, "scxrd_load", json!({"path":path}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let c = &s.scxrd;
    let (counts, raw) = c.decode_raw_snapshot(1).expect("raw-chunk reader");
    let frame = c.sources[1].frame;
    assert!(raw.verified(frame).unwrap().get().is_none());
    assert!(c.sources[1].digest.get().is_none());
    assert_eq!(c.read(1).unwrap(), counts);
    let recorded = c.sources[1].digest.get().cloned().unwrap();
    assert_eq!(recorded, digest(&counts));
    assert_eq!(raw.verified(frame).unwrap().get(), Some(&recorded));
    assert_eq!(c.read(1).unwrap(), counts);
    // A source recording other counts is refused although the frame was
    // checked through this reader.
    let mut other = s.scxrd.clone();
    other.sources[1].digest = Arc::new(OnceLock::from("0".repeat(64)));
    assert!(other.read(1).unwrap_err().contains("counts changed"));
    // A changed file is refused: the snapshot no longer reads it and the
    // general reader decodes the new counts.
    std::thread::sleep(std::time::Duration::from_millis(20));
    {
        let f = hdf5::File::create(&path).unwrap();
        f.new_dataset::<u32>()
            .shape((3, 64, 80))
            .create("counts")
            .unwrap()
            .write_raw(&vec![7u32; 3 * 64 * 80])
            .unwrap();
    }
    assert!(s.scxrd.read(1).unwrap_err().contains("counts changed"));
}

/// The block-wise count digest is the recorded format: SHA-256 of every value
/// as little-endian f64 bytes in order (saved projects keep their digests).
#[test]
fn count_digest_keeps_the_recorded_format() {
    let data: Vec<f64> = (0..20_000)
        .map(|i| match i % 5 {
            0 => f64::NAN,
            1 => -0.,
            2 => f64::INFINITY,
            _ => i as f64 * 0.37,
        })
        .collect();
    for n in [0, 1, 8191, 8192, 8193, 20_000] {
        let mut hash = Sha256::new();
        for v in &data[..n] {
            hash.update(v.to_le_bytes());
        }
        assert_eq!(digest(&data[..n]), format!("{:x}", hash.finalize()), "{n}");
    }
}

/// 96×96, 12 frames, two reflections per frame and a 2×2 hot pixel on every
/// frame; frame 5 also holds a grid of 64 spots (a frame that looks into the
/// cell body).
fn busy_session() -> (tempfile::TempDir, Session) {
    let dir = tempfile::tempdir().unwrap();
    let (h, w) = (96usize, 96usize);
    let mut seed = 99u64;
    let mut normal = move || {
        let mut u = || {
            seed = seed
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            ((seed >> 11) as f64 + 0.5) / (1u64 << 53) as f64
        };
        let (a, b) = (u(), u());
        (-2. * a.ln()).sqrt() * (std::f64::consts::TAU * b).cos()
    };
    let mut paths = vec![];
    for f in 0..12usize {
        let mut counts = vec![0u16; h * w];
        for y in 0..h {
            for x in 0..w {
                let mut b: f64 = 20.;
                if y.abs_diff(12) <= 1 && x.abs_diff(12 + 5 * f) <= 1 {
                    b += 300.;
                }
                if y.abs_diff(84) <= 1 && x.abs_diff(80 - 5 * f) <= 1 {
                    b += 300.;
                }
                if (50..52).contains(&y) && (6..8).contains(&x) {
                    b += 400.;
                }
                if f == 5
                    && (22..86).contains(&y)
                    && (16..80).contains(&x)
                    && (y - 22) % 8 <= 1
                    && (x - 16) % 8 <= 1
                {
                    b += 300.;
                }
                counts[y * w + x] = (b + normal() * b.sqrt()).round().max(0.) as u16;
            }
        }
        let path = dir.path().join(format!("busy_{f:04}.tif"));
        tiff::encoder::TiffEncoder::new(File::create(&path).unwrap())
            .unwrap()
            .write_image::<tiff::encoder::colortype::Gray16>(w as u32, h as u32, &counts)
            .unwrap();
        paths.push(path.to_string_lossy().into_owned());
    }
    let mut s = Session::new(PathBuf::new());
    let r = call(&mut s, "scxrd_load", json!({"paths":paths}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    let c = Config {
        persistent_enabled: true,
        ..spot_config(&s)
    };
    settings(&mut s, &c);
    (dir, s)
}
fn spots_on(c: &Crystal, frame: usize) -> usize {
    c.peaks.iter().filter(|p| p.frame == frame).count()
}

/// Busy frames: far above the scan's typical count by both the ratio and the
/// robust spread, and never on a few frames or a handful of spots.
#[test]
fn busy_frames_are_outliers_of_the_spot_count() {
    let frames =
        |counts: &[usize]| -> Vec<(usize, usize)> { counts.iter().copied().enumerate().collect() };
    // The enstatite scan: frame 0 looks into the cell body (1225 vs median 22).
    let mut ens = vec![1225, 57];
    ens.extend((0..142).map(|i| 10 + (i * 7) % 30));
    assert_eq!(processing::unusual_frames(&frames(&ens)), vec![0]);
    // Genuinely variable counts (a multi-grain scan ramping 200 → 700 → 200).
    let ramp: Vec<usize> = (0..144)
        .map(|i| 200 + (500. * (i as f64 / 143. * std::f64::consts::PI).sin()) as usize)
        .collect();
    assert!(processing::unusual_frames(&frames(&ramp)).is_empty());
    // A few frames, or very few spots: nothing to judge against.
    assert!(processing::unusual_frames(&frames(&[3, 2, 900, 4, 3])).is_empty());
    assert!(processing::unusual_frames(&frames(&[0, 1, 0, 1, 40, 0, 1, 0, 1, 0])).is_empty());
    assert!(processing::unusual_frames(&[]).is_empty());
    // Ten times the median but within the robust spread is not busy.
    let spread: Vec<usize> = (0..40)
        .map(|i| if i % 2 == 0 { 5 } else { 60 })
        .chain([70])
        .collect();
    assert!(processing::unusual_frames(&frames(&spread)).is_empty());
}

/// Find spots names the busy frame; excluding it leaves its spots out of
/// every step, says so in the snapshot, is undoable, and taking it back gives
/// the first result again. A run straight after the edit (no settings reply
/// in between) still masks the persistent hot pixel.
#[test]
fn a_busy_frame_is_named_and_can_be_excluded_and_taken_back() {
    masks::DIAMOND_REPLY_LIMIT.set(0);
    let (_dir, mut s) = busy_session();
    run(&mut s);
    let first = record(&s.scxrd);
    assert!(spots_on(&s.scxrd, 5) >= 60, "{}", spots_on(&s.scxrd, 5));
    assert!(
        s.scxrd.peaks.iter().all(|p| p.xy[0] > 9.),
        "hot pixel masked"
    );
    let snap = call(&mut s, "scxrd_snapshot", json!({})).result;
    assert_eq!(snap["scxrd"]["busyFrames"], json!([5]));

    let r = call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"exclude_frames","frames":[5],"exclude":true}),
    );
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(r.result["scxrd"]["excludedFrames"], json!([5]));
    assert_eq!(r.result["scxrd"]["busyFrames"], json!([]));
    assert!(s.scxrd.peaks.is_empty() && s.scxrd.stages[0].status == "pending");
    run(&mut s);
    assert_eq!(spots_on(&s.scxrd, 5), 0);
    assert!(s.scxrd.peaks.len() + 60 <= first["peaks"].as_array().unwrap().len());
    assert!(
        s.scxrd.peaks.iter().all(|p| p.xy[0] > 9.),
        "hot pixel masked after the edit"
    );
    assert_eq!(s.scxrd.busy_frames(), Vec::<usize>::new());
    // Excluding again changes nothing.
    let revision = s.scxrd.revision;
    call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"exclude_frames","frames":[5],"exclude":true}),
    );
    assert_eq!(
        (s.scxrd.revision, s.scxrd.stages[1].status.as_str()),
        (revision, "complete")
    );

    // Undo (one entry: the no-op above records none) restores the run
    // before the exclusion.
    let r = call(&mut s, "scxrd_edit", json!({"operation":"undo"}));
    assert_eq!(r.result["ok"], true, "{:?}", r.result);
    assert_eq!(r.result["scxrd"]["redoLabel"], "exclude frames");
    assert!(s.scxrd.excluded_frames.is_empty());
    assert_eq!(record(&s.scxrd), first);

    // Exclude and take back: the same result as before.
    call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"exclude_frames","frames":[5],"exclude":true}),
    );
    run(&mut s);
    let r = call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"exclude_frames","frames":[5],"exclude":false}),
    );
    assert_eq!(r.result["scxrd"]["excludedFrames"], json!([]));
    run(&mut s);
    assert_eq!(record(&s.scxrd), first);
    // Out-of-range frames and the fixed protocol are refused.
    let r = call(
        &mut s,
        "scxrd_edit",
        json!({"operation":"exclude_frames","frames":[12],"exclude":true}),
    );
    assert_eq!(r.result["ok"], false);
}

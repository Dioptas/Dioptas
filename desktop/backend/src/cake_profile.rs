//! Qt's fractional radial-window extraction on the owned, corrected f64 cake.
//! This is a projection of an existing cake, never a second integrator.
use super::*;

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct Profile {
    x: Vec<f64>,
    y: Vec<f64>,
    unit: &'static str,
    radial: f64,
    radial_unit: String,
    two_theta: f64,
    bins: usize,
    shift_bins: i64,
    clipped: bool,
}

fn extract(
    data: &[f64],
    shape: [usize; 2],
    radial: [f64; 2],
    azimuth: [f64; 2],
    selected: f64,
    bins: usize,
    shift_degrees: f64,
) -> Result<(Vec<f64>, Vec<f64>, i64, bool), String> {
    let [rows, columns] = shape;
    if rows == 0 || columns == 0 || data.len() != rows * columns {
        return Err("Cake dimensions and scientific samples disagree.".into());
    }
    let position = if columns == 1 {
        // Single-bin metadata has identical endpoints.
        ((selected - radial[0]).abs() <= 32. * f64::EPSILON * radial[0].abs().max(1.))
            .then_some(0.0)
    } else {
        let position = (selected - radial[0]) / (radial[1] - radial[0]) * (columns - 1) as f64;
        // Allow conversion roundoff at the endpoint centers only.
        (position >= -1e-9 && position <= (columns - 1) as f64 + 1e-9)
            .then_some(position.clamp(0., (columns - 1) as f64))
    };
    let Some(position) = position else {
        return Ok((vec![], vec![], 0, false));
    };
    // Qt: tth_center = partial_index + .5; left/right = center +/- bins/2.
    // Integrating the overlap reproduces its y1 + y2 + y3, but clips at
    // detector edges instead of negative-index wrapping or IndexError.
    let left = position + 0.5 - bins as f64 / 2.;
    let right = position + 0.5 + bins as f64 / 2.;
    let start = left.floor().max(0.) as usize;
    let end = (right.ceil().max(0.) as usize).min(columns);
    let weights: Vec<_> = (start..end)
        .map(|col| (right.min((col + 1) as f64) - left.max(col as f64)).max(0.))
        .collect();
    let mut y = Vec::with_capacity(rows);
    for row in 0..rows {
        let mut total = 0.;
        for (offset, weight) in weights.iter().enumerate() {
            if *weight > 0. {
                total += weight * data[row * columns + start + offset];
            }
        }
        y.push(total / bins as f64);
    }
    let step = if rows > 1 {
        (azimuth[1] - azimuth[0]) / (rows - 1) as f64
    } else {
        0.
    };
    let period = step * rows as f64;
    // Match the existing full-cake display's Math.round (ties toward +infinity).
    let shift = if period >= 359. {
        (shift_degrees / period * rows as f64 + 0.5).floor() as i64
    } else {
        0
    };
    y.rotate_right(shift.rem_euclid(rows as i64) as usize);
    let x = (0..rows)
        .map(|row| azimuth[0] + (row as f64 - shift as f64) * step)
        .collect();
    Ok((x, y, shift, left < 0. || right > columns as f64))
}

impl Session {
    pub(super) fn cake_profile(&mut self, args: &Value, save: bool) -> Result<Reply, String> {
        check_keys(
            args,
            &[
                "two_theta",
                "bins",
                "shift",
                "path",
                "directory",
                "suggested_name",
            ],
        )?;
        let bins = integer(&args["bins"], "Integral width", 1, 1_000_000)?;
        let shift = finite(&args["shift"], "Azimuth shift", -180., 180.)?;
        let tth = finite(&args["two_theta"], "Selected 2θ", 0., 180.)?;
        // Validate the destination before requesting potentially expensive data.
        let destination = if save {
            let file = path(args)?;
            let extension = file
                .extension()
                .and_then(|s| s.to_str())
                .unwrap_or("xy")
                .to_ascii_lowercase();
            if !["xy", "dat", "txt", "csv"].contains(&extension.as_str()) {
                return Err(
                    "Save the azimuthal profile as XY, DAT, TXT or CSV (two columns, no errors)."
                        .into(),
                );
            }
            Some(file.to_owned())
        } else {
            None
        };
        self.control.check()?;
        let requested = self.control.cake_requested();
        let result = self.ensure_cake();
        self.control.request_cake(requested);
        result?;
        let cake = self
            .displayed_cake()
            .ok_or("No scientific cake is available.")?;
        let data = self
            .displayed_cake_values()
            .ok_or("No scientific cake samples are available.")?;
        let m = &cake.metadata;
        let range = |name: &str| -> Result<[f64; 2], String> {
            Ok([
                m[name][0].as_f64().ok_or("Missing cake axis.")?,
                m[name][1].as_f64().ok_or("Missing cake axis.")?,
            ])
        };
        let unit = m["unit"].as_str().ok_or("Missing scientific cake unit.")?;
        let selected = linked::convert(tth, "2th_deg", unit, self.settings.geometry.wavelength);
        let (x, y, shift_bins, clipped) = extract(
            data,
            [
                m["fullHeight"].as_u64().ok_or("Missing cake height.")? as usize,
                m["fullWidth"].as_u64().ok_or("Missing cake width.")? as usize,
            ],
            range("radialRange")?,
            range("azimuthRange")?,
            selected,
            bins,
            shift,
        )?;
        let profile = Profile {
            x,
            y,
            unit: "azimuth_deg",
            radial: selected,
            radial_unit: unit.into(),
            two_theta: tth,
            bins,
            shift_bins,
            clipped,
        };
        self.control.check()?;
        if let Some(file) = destination {
            use std::fmt::Write;
            if profile.x.is_empty() {
                return Err(
                    "Select a radial position within the cake before saving its profile.".into(),
                );
            }
            let csv = file
                .extension()
                .is_some_and(|e| e.eq_ignore_ascii_case("csv"));
            let separator = if csv { "," } else { " " };
            let mut text = format!(
                "# Dioptas azimuthal profile\n# radial = {:.17e} {}; 2theta = {:.17e} deg; width = {} bins; shift = {} azimuth bins; clipped = {}\n# azimuth_deg{}intensity_au\n",
                profile.radial, profile.radial_unit, tth, bins, shift_bins, clipped, separator
            );
            for (&x, &y) in profile.x.iter().zip(&profile.y) {
                if !x.is_finite() || !y.is_finite() {
                    return Err(
                        "Profile contains nonfinite samples; export was not replaced.".into(),
                    );
                }
                writeln!(text, "{x:.17e}{separator}{y:.17e}").map_err(|e| e.to_string())?;
            }
            self.control.check()?;
            atomic_write(&file, text.as_bytes())?;
            return Ok(Reply::metadata(json!({"ok":true,"savedPath":file})));
        }
        Ok(Reply::metadata(json!({"ok":true,"cakeProfile":profile})))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn profile(position: f64, width: usize, shift: f64) -> (Vec<f64>, Vec<f64>, i64, bool) {
        let values = [
            10., 20., 30., 40., 50., 100., 200., 300., 400., 500., -1., -2., -3., -4., -5., 0., 1.,
            0., 1., 0.,
        ];
        extract(
            &values,
            [4, 5],
            [0., 4.],
            [-135., 135.],
            position,
            width,
            shift,
        )
        .unwrap()
    }
    #[test]
    fn qt_fractional_window_and_width_divisor() {
        assert_eq!(profile(2., 1, 0.).1, [30., 300., -3., 0.]);
        assert_eq!(profile(2.5, 1, 0.).1, [35., 350., -3.5, 0.5]);
        assert_eq!(profile(2.7, 1, 0.).1[0], 37.);
        assert_eq!(profile(2.5, 2, 0.).1, profile(2.5, 1, 0.).1);
        assert_eq!(profile(2., 2, 0.).1, [30., 300., -3., 0.5]);
        assert_eq!(profile(2., 3, 0.).1, [30., 300., -3., 2. / 3.]);
    }
    #[test]
    fn edges_clip_without_wrapping_or_renormalizing_and_outside_is_empty() {
        assert_eq!(profile(0., 1, 0.).1[0], 10.);
        assert_eq!(profile(4., 1, 0.).1[0], 50.);
        assert_eq!(profile(0., 2, 0.).1[0], 10.);
        assert_eq!(profile(4., 2, 0.).1[0], 35.);
        assert!(profile(0., 2, 0.).3);
        assert_eq!(profile(2., 1_000_000, 0.).1[0], 150. / 1_000_000.);
        assert!(profile(-0.1, 1, 0.).0.is_empty());
        assert!(profile(4.1, 1, 0.).0.is_empty());
    }
    #[test]
    fn roll_matches_cake_centers_and_negative_half_ties() {
        let p = profile(2., 1, 90.);
        assert_eq!(p.0, [-225., -135., -45., 45.]);
        assert_eq!(p.1, [0., 30., 300., -3.]);
        assert_eq!(p.2, 1);
        assert_eq!(profile(2., 1, -45.).2, 0);
        assert_eq!(profile(2., 1, 45.).2, 1);
        let p = extract(&[1., 2.], [2, 1], [3., 3.], [0., 10.], 3., 1, 90.).unwrap();
        assert_eq!(p.0, [0., 10.]);
        assert_eq!(p.1, [1., 2.]);
        assert_eq!(p.2, 0);
        let rounded = extract(
            &[1., 2.],
            [2, 1],
            [3., 3.],
            [0., 10.],
            3. + 4. * f64::EPSILON,
            1,
            0.,
        )
        .unwrap();
        assert_eq!(rounded.1, [1., 2.]);
    }
    #[cfg(feature = "dioptrin")]
    fn call(s: &mut Session, action: &str, mut payload: Value) -> Reply {
        payload["requested_products"] = json!({"cake":false,"rings":false});
        let r = s.invoke(&Request {
            id: 1,
            action: action.into(),
            payload,
            cached_buffers: vec![],
        });
        assert_eq!(r.result["ok"], true, "{action}: {}", r.result);
        r
    }
    #[cfg(feature = "dioptrin")]
    fn setup(temp: &Path) -> Session {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let poni = temp.join("g.poni");
        std::fs::write(&poni,"PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.1\nPoni1: 0.003\nPoni2: 0.004\nRot1: 0\nRot2: 0\nRot3: 0\nSplineFile: None\nWavelength: 4e-11\n").unwrap();
        let image = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/combined-counts.h5");
        let mut s = Session::new(root);
        call(
            &mut s,
            "integration_settings",
            json!({"bins":48,"cake_bins":12,"trim_zeros":false}),
        );
        call(&mut s, "open_calibration", json!({"path":poni}));
        call(
            &mut s,
            "open_image",
            json!({"path":image,"dataset":"/counts"}),
        );
        s
    }
    #[cfg(feature = "dioptrin")]
    fn numbers(v: &Value) -> Vec<f64> {
        v.as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_f64().unwrap())
            .collect()
    }
    #[cfg(feature = "dioptrin")]
    fn verify_qt(s: &mut Session) -> Value {
        // Only this explicitly requested product may build a missing cake.
        call(
            s,
            "cake_profile",
            json!({"two_theta":1.,"bins":1,"shift":0}),
        );
        let m = s.displayed_cake().unwrap().metadata.clone();
        let data = s.displayed_cake_values().unwrap().clone();
        let n = m["fullWidth"].as_u64().unwrap() as usize;
        let rows = m["fullHeight"].as_u64().unwrap() as usize;
        let unit = m["unit"].as_str().unwrap();
        let low = m["radialRange"][0].as_f64().unwrap();
        let step = (m["radialRange"][1].as_f64().unwrap() - low) / (n - 1) as f64;
        let settings = s.settings.clone();
        let image = s.image.as_ref().unwrap().values.clone();
        let pattern = s.pattern.clone();
        let selected = s.project.selected;
        let revision = s.revision;
        let mut last = Value::Null;
        for index in [0., 0.7, 20., 20.5, 20.7, (n - 1) as f64] {
            for bins in [1, 2, 3, 9, 1_000_000] {
                let coordinate = low + index * step;
                let tth =
                    linked::convert(coordinate, unit, "2th_deg", s.settings.geometry.wavelength);
                let p = call(
                    s,
                    "cake_profile",
                    json!({"two_theta":tth,"bins":bins,"shift":90}),
                )
                .result["cakeProfile"]
                    .clone();
                let y = numbers(&p["y"]);
                assert_eq!(y.len(), rows);
                let left = index + 0.5 - bins as f64 / 2.;
                let right = index + 0.5 + bins as f64 / 2.;
                // Literal Qt y1/slice/y3, clipping missing radial columns.
                let sample = |row: usize, col: isize| -> f64 {
                    if col < 0 || col >= n as isize {
                        0.
                    } else {
                        data[row * n + col as usize]
                    }
                };
                let shift = p["shiftBins"].as_i64().unwrap();
                for (row, actual) in y.iter().enumerate() {
                    let row = (row as i64 - shift).rem_euclid(rows as i64) as usize;
                    let y1 = (left.ceil() - left).abs() * sample(row, left.floor() as isize);
                    let y2: f64 = (left.ceil().max(0.) as usize
                        ..(right.floor().max(0.) as usize).min(n))
                        .map(|col| data[row * n + col])
                        .sum();
                    let y3 = (right - right.floor()) * sample(row, right.floor() as isize);
                    let expected = (y1 + y2 + y3) / bins as f64;
                    let conversion_roundoff = 1e-12
                        * data[row * n..(row + 1) * n]
                            .iter()
                            .copied()
                            .map(f64::abs)
                            .fold(0., f64::max);
                    assert!(
                        (actual - expected).abs()
                            < 3e-10 * (1. + expected.abs()) + conversion_roundoff,
                        "{index} / {bins}: {actual} != {expected}"
                    );
                }
                assert_eq!(p["radialUnit"], unit);
                assert_eq!(p["unit"], "azimuth_deg");
                assert!(p.get("sigma").is_none());
                assert!(p.get("azimuthalStd").is_none());
                assert!(Arc::ptr_eq(s.displayed_cake_values().unwrap(), &data));
                assert!(Arc::ptr_eq(&s.image.as_ref().unwrap().values, &image));
                assert!(s.settings == settings);
                assert_eq!(s.pattern, pattern);
                assert_eq!(s.revision, revision);
                assert_eq!(s.project.selected, selected);
                last = p;
            }
        }
        last
    }
    #[test]
    #[cfg(feature = "dioptrin")]
    fn native_owned_cakes_masks_corrections_units_and_combination_follow_qt_projection() {
        let temp = tempfile::tempdir().unwrap();
        let mut s = setup(temp.path());
        assert!(s.cake.is_none());
        verify_qt(&mut s);
        let uncorrected = s.cake_values.as_ref().unwrap().clone();
        let mask = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/asymmetric.mask");
        call(&mut s, "mask_file", json!({"path":mask}));
        // A shared image background uses the existing correction owner.
        let image = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/combined-counts.h5");
        call(
            &mut s,
            "integration_image_background",
            json!({"path":image,"scale":0.2,"offset":1.2}),
        );
        call(
            &mut s,
            "integration_correction",
            json!({"kind":"cbn","enabled":true,"parameters":{"tilt":7,"tilt_rotation":31,"diamond_thickness":1.9}}),
        );
        verify_qt(&mut s);
        assert_ne!(*uncorrected, **s.cake_values.as_ref().unwrap());
        for wavelength in [0.4, 0.8] {
            let g = s.settings.geometry.clone();
            let polarization = s.settings.polarization;
            call(
                &mut s,
                "manual_geometry",
                json!({"convention":"pyfai","values":{
                "dist":g.dist,"poni1":g.poni1,"poni2":g.poni2,"rot1":g.rot1,"rot2":g.rot2,"rot3":g.rot3,
                "pixel1":g.pixel1,"pixel2":g.pixel2,"wavelength":wavelength*1e-10,"polarization_factor":polarization}}),
            );
            for unit in ["2th_deg", "q_A^-1", "d_A"] {
                call(&mut s, "integration_settings", json!({"unit":unit}));
                verify_qt(&mut s);
            }
        }
        call(&mut s, "configuration", json!({"operation":"duplicate"}));
        let selected = s.project.selected;
        for unit in ["q_A^-1", "d_A", "2th_deg"] {
            call(&mut s, "integration_settings", json!({"unit":unit}));
            call(
                &mut s,
                "combination_settings",
                json!({"patterns":true,"cakes":true}),
            );
            verify_qt(&mut s);
            assert_eq!(s.project.selected, selected);
            // Source grid ownership belongs to combination, not this extractor.
            // Axis relabeling may retain an earlier declared scientific unit;
            // verify_qt always derives its reference from that actual unit.
        }
        let before = call(
            &mut s,
            "cake_profile",
            json!({"two_theta":1.,"bins":3,"shift":-90}),
        )
        .result;
        let project = temp.path().join("profile.dio");
        call(&mut s, "save_project", json!({"path":project}));
        let mut restored = Session::new(s.root.clone());
        call(&mut restored, "open_project", json!({"path":project}));
        let after = call(
            &mut restored,
            "cake_profile",
            json!({"two_theta":1.,"bins":3,"shift":-90}),
        )
        .result;
        assert_eq!(after, before);
        assert_eq!(restored.project.selected, selected);
    }
    #[test]
    #[cfg(feature = "dioptrin")]
    fn exports_keep_native_precision_and_fail_or_cancel_atomically() {
        let temp = tempfile::tempdir().unwrap();
        let mut s = setup(temp.path());
        let args = json!({"two_theta":1.,"bins":3,"shift":90});
        let p = call(&mut s, "cake_profile", args.clone()).result["cakeProfile"].clone();
        let file = temp.path().join("azimuth.csv");
        let mut save = args.clone();
        save["path"] = json!(file);
        call(&mut s, "save_cake_profile", save.clone());
        let bytes = std::fs::read(&file).unwrap();
        let text = String::from_utf8(bytes.clone()).unwrap();
        assert!(text.contains("azimuth_deg,intensity_au"));
        let rows: Vec<_> = text.lines().filter(|l| !l.starts_with('#')).collect();
        for (i, row) in rows.iter().enumerate() {
            let fields: Vec<f64> = row.split(',').map(|v| v.parse().unwrap()).collect();
            assert_eq!(fields.len(), 2);
            assert_eq!(fields[0], p["x"][i].as_f64().unwrap());
            assert_eq!(fields[1], p["y"][i].as_f64().unwrap());
        }
        let xy = temp.path().join("azimuth.xy");
        let mut xy_save = args.clone();
        xy_save["path"] = json!(xy);
        call(&mut s, "save_cake_profile", xy_save);
        let xy_text = std::fs::read_to_string(xy).unwrap();
        for (i, row) in xy_text.lines().filter(|l| !l.starts_with('#')).enumerate() {
            let fields: Vec<f64> = row.split_whitespace().map(|v| v.parse().unwrap()).collect();
            assert_eq!(
                fields,
                vec![p["x"][i].as_f64().unwrap(), p["y"][i].as_f64().unwrap()]
            );
        }
        // Invalid width/extension/out-of-range and cancellation never replace output.
        for (key, value) in [
            ("bins", json!(0)),
            ("bins", json!(2.5)),
            ("two_theta", json!(170.)),
        ] {
            let mut bad = save.clone();
            bad[key] = value;
            let r = s.invoke(&Request {
                id: 1,
                action: "save_cake_profile".into(),
                payload: bad,
                cached_buffers: vec![],
            });
            assert_eq!(r.result["ok"], false, "{}", r.result);
            assert_eq!(std::fs::read(&file).unwrap(), bytes);
        }
        let control = Arc::new(crate::control::Control::default());
        control.cancel();
        let r = s.invoke_controlled(
            &Request {
                id: 1,
                action: "save_cake_profile".into(),
                payload: save,
                cached_buffers: vec![],
            },
            control,
        );
        assert_eq!(r.result["ok"], false);
        assert_eq!(std::fs::read(&file).unwrap(), bytes);
        let bad = temp.path().join("existing.xye");
        std::fs::write(&bad, b"keep").unwrap();
        let mut save = args;
        save["path"] = json!(bad);
        assert_eq!(
            s.invoke(&Request {
                id: 1,
                action: "save_cake_profile".into(),
                payload: save,
                cached_buffers: vec![]
            })
            .result["ok"],
            false
        );
        assert_eq!(std::fs::read(&bad).unwrap(), b"keep");
        assert_eq!(
            std::fs::read_dir(temp.path())
                .unwrap()
                .filter_map(Result::ok)
                .filter(|e| e.file_name().to_string_lossy().starts_with(".tmp"))
                .count(),
            0
        );
    }
}

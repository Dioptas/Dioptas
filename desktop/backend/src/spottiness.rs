//! Population azimuthal spread of the original integrated signal, not counting error.
use crate::{control::Control, pattern::Curve};
use serde_json::{Value, json};
use std::{io::Write, path::Path};

/// Same cutoff and undefined-value convention as Qt's relative_spread.
fn relative(mean: &[f64], std: &[f64]) -> Vec<f64> {
    let threshold = mean
        .iter()
        .filter(|v| v.is_finite())
        .map(|v| v.abs())
        .fold(1.0, f64::max)
        * 1e-12;
    mean.iter()
        .zip(std)
        .map(|(&m, &s)| {
            let ratio = if m.is_finite() && s.is_finite() && m > threshold {
                s / m
            } else {
                f64::NAN
            };
            if ratio.is_finite() { ratio } else { f64::NAN }
        })
        .collect()
}

pub(crate) fn diagnostic(curve: &Curve) -> Option<Value> {
    let std = curve.spread.as_ref()?;
    Some(json!({"x":curve.x,"mean":curve.y,"std":std,"relative":relative(&curve.y, std)}))
}

pub(crate) fn export(
    path: &Path,
    curve: &Curve,
    unit: &str,
    control: &Control,
) -> Result<(), String> {
    let std = curve.spread.as_ref().ok_or(
        "Azimuthal std is unavailable; enable Show Spottiness and integrate an image first.",
    )?;
    if curve.x.len() != curve.y.len() || std.len() != curve.x.len() {
        return Err("Spottiness arrays differ in length; no CSV was published.".into());
    }
    let ratios = relative(&curve.y, std);
    control.check()?;
    crate::session::file_workflow::atomic_render(path, |file| {
        writeln!(file, "# radial [{unit}],integrated_mean,azimuthal_std,relative_spread\n# Original integrated signal before pattern background subtraction; population spread, not Poisson counting error; undefined values are NaN")
            .map_err(|e| e.to_string())?;
        for (i, &ratio) in ratios.iter().enumerate() {
            if i % 1024 == 0 {
                control.check()?;
            }
            writeln!(
                file,
                "{:.17e},{:.17e},{:.17e},{ratio:.17e}",
                curve.x[i], curve.y[i], std[i]
            )
            .map_err(|e| e.to_string())?;
        }
        file.sync_all().map_err(|e| e.to_string())?;
        control.check()
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    #[test]
    fn cancellation_during_csv_preserves_the_previous_destination() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("spread.csv");
        std::fs::write(&path, "previous").unwrap();
        let control = Arc::new(Control::default());
        let writer_control = control.clone();
        let writer_path = path.clone();
        let curve = Curve {
            x: Arc::new(vec![1.; 100_000]),
            y: Arc::new(vec![2.; 100_000]),
            sigma: None,
            spread: Some(Arc::new(vec![3.; 100_000])),
        };
        let writer =
            std::thread::spawn(move || export(&writer_path, &curve, "2th_deg", &writer_control));
        // Observe the staged file, then cancel before its many rows finish.
        let started = std::time::Instant::now();
        while std::fs::read_dir(dir.path()).unwrap().count() == 1 {
            assert!(started.elapsed().as_secs() < 10);
            std::thread::yield_now();
        }
        control.cancel();
        assert!(writer.join().unwrap().is_err());
        assert_eq!(std::fs::read_to_string(path).unwrap(), "previous");
        assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(), 1);
    }

    #[test]
    fn qt_cutoff_and_atomic_publication() {
        let mean = vec![0., -1., 1e-12, 2e-12, 1., f64::NAN, f64::INFINITY];
        let std = vec![1., 1., 1., 1., f64::MAX, 1., 1.];
        let ratios = relative(&mean, &std);
        assert!(ratios[..3].iter().all(|r| r.is_nan()));
        assert_eq!(ratios[3], 5e11);
        assert_eq!(ratios[4], f64::MAX);
        assert!(ratios[5..].iter().all(|r| r.is_nan()));
        assert!(relative(&[2e-12, 1.], &[f64::MAX, 1.])[0].is_nan());
        assert!(relative(&[1e-3, 1e9], &[1., 1.])[0].is_nan());
        let curve = Curve {
            x: Arc::new((0..7).map(f64::from).collect()),
            y: Arc::new(mean),
            sigma: None,
            spread: Some(Arc::new(std)),
        };
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("spread.csv");
        std::fs::write(&path, "previous").unwrap();
        let control = Control::default();
        control.cancel();
        assert!(export(&path, &curve, "q_A^-1", &control).is_err());
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "previous");
        assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(), 1);
        export(&path, &curve, "q_A^-1", &Control::default()).unwrap();
        let csv = std::fs::read_to_string(&path).unwrap();
        assert!(csv.contains("radial [q_A^-1]"));
        assert_eq!(csv.lines().filter(|l| !l.starts_with('#')).count(), 7);
    }
}

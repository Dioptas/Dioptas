//! Existing cBN/plate/slab formulas with scalar setup outside the pixel loop.
use crate::control::Control;
use rayon::prelude::*;
use serde_json::Value;

type Kernel = Box<dyn Fn(f64, f64) -> f64 + Sync>;
fn kernel(kind: &str, p: &Value) -> Result<Kernel, String> {
    let n = |key: &str| p[key].as_f64().unwrap();
    if kind == "plate" || kind == "slab" {
        let thickness = n("thickness");
        let mu = n("absorption_coefficient");
        let tilt = n(&format!("{kind}_tilt")).to_radians();
        let rotation = n(&format!("{kind}_rotation")).to_radians();
        let (tilt_cos, tilt_sin) = (tilt.cos(), tilt.sin());
        let incident = mu / tilt_cos.abs().max(1e-10);
        let slab = kind == "slab";
        Ok(Box::new(move |tth, azi| {
            if thickness == 0.0 || mu == 0.0 {
                return 1.0;
            }
            let cosine = (tilt_cos * tth.cos() + tilt_sin * tth.sin() * (azi - rotation).cos())
                .abs()
                .max(1e-10);
            let outgoing = mu / cosine;
            if !slab {
                return (-outgoing * thickness).exp();
            }
            let difference = (outgoing - incident).abs() * thickness;
            let ratio = if difference == 0.0 {
                1.0
            } else {
                -(-difference).exp_m1() / difference
            };
            thickness * (-incident.min(outgoing) * thickness).exp() * ratio
        }))
    } else if kind == "cbn" {
        let diam = n("diamond_thickness");
        let ds = n("seat_thickness");
        let (radius1, radius2) = (n("small_cbn_seat_radius"), n("large_cbn_seat_radius"));
        let tilt = -n("tilt").to_radians();
        let rotation = n("tilt_rotation").to_radians() + std::f64::consts::FRAC_PI_2;
        let (tilt_cos, tilt_sin) = (tilt.cos(), tilt.sin());
        let (rotation_cos, rotation_sin) = (rotation.cos(), rotation.sin());
        let offset = n("center_offset");
        let angle = n("center_offset_angle").to_radians();
        let diamond_abs_length = n("diamond_abs_length");
        let cbn_abs_length = n("cbn_abs_length");
        let boundaries = ((radius1 / diam).atan(), (radius2 / (diam + ds)).atan());
        let alpha0 = std::f64::consts::FRAC_PI_2 - ((radius2 - radius1) / ds).atan();
        Ok(Box::new(move |tth, azi| {
            let (mut r1, mut r2) = (radius1, radius2);
            if offset != 0.0 {
                let beta = azi
                    - (offset * (std::f64::consts::PI - (azi + angle)).sin() / r1).asin()
                    + angle;
                r1 = (r1 * r1 + offset * offset - 2.0 * r1 * offset * beta.cos()).sqrt();
                r2 = (r2 * r2 + offset * offset - 2.0 * r2 * offset * beta.cos()).sqrt();
            }
            let dot = tilt_cos * tth.cos() + rotation_sin * tilt_sin * azi.cos() * tth.sin()
                - rotation_cos * tilt_sin * azi.sin() * tth.sin();
            let tt = dot.clamp(-1.0, 1.0).acos();
            let (ts1, ts2) = if offset == 0. {
                boundaries
            } else {
                ((r1 / diam).atan(), (r2 / (diam + ds)).atan())
            };
            let seat = if tt >= ts2 {
                ds / tt.cos()
            } else if tt > ts1 && tt < ts2 {
                let alpha = if offset == 0. {
                    alpha0
                } else {
                    std::f64::consts::FRAC_PI_2 - ((r2 - r1) / ds).atan()
                };
                let gamma = std::f64::consts::PI - (alpha + tt + std::f64::consts::FRAC_PI_2);
                (diam * tt.tan() - r1) * alpha.sin() / gamma.sin()
            } else {
                0.0
            };
            (-diam / tt.cos() / diamond_abs_length).exp() * (-seat / cbn_abs_length).exp()
        }))
    } else {
        Err("Unsupported analytical correction.".into())
    }
}

pub(crate) fn build(
    kind: &str,
    p: &Value,
    tth: &[f64],
    azi: &[f64],
    control: &Control,
) -> Result<Vec<f64>, String> {
    let kernel = kernel(kind, p)?;
    let mut values = vec![0.; tth.len()];
    crate::worker_pool::install(|| {
        values
            .par_chunks_mut(16384)
            .enumerate()
            .try_for_each(|(chunk, out)| {
                control.check()?;
                let start = chunk * 16384;
                for (j, value) in out.iter_mut().enumerate() {
                    *value = kernel(tth[start + j], azi[start + j]);
                    if !value.is_finite() || *value <= 0. {
                        return Err(
                            "Correction is not finite and positive across this detector."
                                .to_string(),
                        );
                    }
                }
                Ok(())
            })
    })?;
    Ok(values)
}

//! Deterministic rotation frames from an independent Ewald construction.
//! No PhaseSmith prediction/indexing routines or reference atomic coordinates.
use std::{
    fs::{self, File},
    path::PathBuf,
};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let root = PathBuf::from(std::env::args().nth(1).ok_or("output directory required")?);
    fs::create_dir_all(&root)?;
    let size = 256usize;
    let nf = 161;
    let zero = -40.;
    let step = 0.5;
    let distance = 0.03;
    let pixel = 0.00015;
    let wavelength = 0.5;
    let centre = 127.5;
    let lengths = [7., 9., 11.];
    let angles: [f64; 3] = [0.27, 0.39, 0.62];
    let (sa, ca) = angles[0].sin_cos();
    let (sb, cb) = angles[1].sin_cos();
    let (sc, cc) = angles[2].sin_cos();
    let rotate = |q: [f64; 3]| {
        let a = [q[0], ca * q[1] - sa * q[2], sa * q[1] + ca * q[2]];
        let b = [cb * a[0] + sb * a[2], a[1], -sb * a[0] + cb * a[2]];
        [cc * b[0] - sc * b[1], sc * b[0] + cc * b[1], b[2]]
    };
    let mut crossings = Vec::new();
    for h in -8i32..=8 {
        for k in -10i32..=10 {
            for l in -12i32..=12 {
                if [h, k, l] == [0, 0, 0]
                    || (h * h * 17 + k * k * 11 + l * l * 7 + h * k * 3).rem_euclid(5) != 0
                {
                    continue;
                }
                let q = rotate([
                    f64::from(h) / lengths[0],
                    f64::from(k) / lengths[1],
                    f64::from(l) / lengths[2],
                ]);
                let norm = q.iter().map(|v| v * v).sum::<f64>();
                if norm > 1.2f64.powi(2) {
                    continue;
                }
                let radius = q[1].hypot(q[2]);
                if radius < 1e-8 {
                    continue;
                }
                let sin = -wavelength * norm / (2. * radius);
                if sin.abs() >= 1. {
                    continue;
                }
                let phase = q[2].atan2(q[1]);
                for base in [
                    sin.asin() - phase,
                    std::f64::consts::PI - sin.asin() - phase,
                ] {
                    for turn in -1..=1 {
                        let omega = base + f64::from(turn) * std::f64::consts::TAU;
                        let degrees = omega.to_degrees();
                        if !(-38.5..38.5).contains(&degrees) {
                            continue;
                        }
                        let (s, c) = omega.sin_cos();
                        let ray = [
                            wavelength * q[0],
                            wavelength * (c * q[1] - s * q[2]),
                            1. + wavelength * (s * q[1] + c * q[2]),
                        ];
                        if ray[2] <= 0. {
                            continue;
                        }
                        let x = centre + distance * ray[1] / (pixel * ray[2]);
                        let y = centre + distance * ray[0] / (pixel * ray[2]);
                        if x > 14. && x < (size - 14) as f64 && y > 14. && y < (size - 14) as f64 {
                            crossings.push((x, y, degrees, [h, k, l]));
                        }
                    }
                }
            }
        }
    }
    for frame in 0..nf {
        let omega = zero + frame as f64 * step + step / 2.;
        let mut values = vec![30u32; size * size];
        for &(x, y, w, _) in &crossings {
            let rocking = (-0.5 * ((omega - w) / 0.36).powi(2)).exp();
            if rocking < 1e-5 {
                continue;
            }
            for yy in (y.floor() as usize - 4)..=(y.ceil() as usize + 4) {
                for xx in (x.floor() as usize - 4)..=(x.ceil() as usize + 4) {
                    let signal = 3500.
                        * rocking
                        * (-0.5 * ((xx as f64 - x).powi(2) + (yy as f64 - y).powi(2))
                            / 0.8f64.powi(2))
                        .exp();
                    let stored = (size - 1 - yy) * size + xx;
                    values[stored] += signal.round() as u32;
                }
            }
        }
        let file = File::create(root.join(format!("frame_{frame:04}.tif")))?;
        tiff::encoder::TiffEncoder::new(file)?.write_image::<tiff::encoder::colortype::Gray32>(
            size as u32,
            size as u32,
            &values,
        )?;
    }
    fs::write(
        root.join("detector.poni"),
        format!(
            "poni_version: 2\nDetector: Detector\nDetector_config: {{\"pixel1\":{pixel},\"pixel2\":{pixel}}}\nDistance: {distance}\nPoni1: {}\nPoni2: {}\nRot1: 0\nRot2: 0\nRot3: 0\nWavelength: {}\n",
            pixel * (centre + 0.5),
            pixel * (centre + 0.5),
            wavelength * 1e-10
        ),
    )?;
    fs::write(
        root.join("truth.json"),
        serde_json::to_vec_pretty(
            &serde_json::json!({"frames":nf,"shape":[size,size],"omega_start":zero,"omega_step":step,"exposure":step,"axis":[1,0,0],"cell":[7,9,11,90,90,90],"crossings":crossings,"construction":"Independent analytic rotation-about-x Ewald equation and perspective projection; original TIFF rows reversed for Dioptas bottom-left coordinates"}),
        )?,
    )?;
    println!(
        "{} crossings, {nf} frames at {}",
        crossings.len(),
        root.display()
    );
    Ok(())
}

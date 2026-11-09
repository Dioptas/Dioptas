//! Finite angular windows for native LUTs, including sectors across ±pi.
//! Geometry/corner evaluation and CSR execution remain Dioptrin's APIs.
use dioptrin::{
    geometry::Geometry,
    integration::RadialUnit,
    lut::{Lut1d, Lut2d},
};
use std::f64::consts::{PI, TAU};

type Point = [f64; 2];
pub struct Grid {
    pub lut: Lut2d,
    pub radial: [f64; 2],
    pub azimuth: [f64; 2],
    radial_step: f64,
}
pub fn angular(range: Option<[f64; 2]>) -> [f64; 2] {
    let [a, mut b] = range.unwrap_or([-180.0, 180.0]);
    if b <= a {
        b += 360.0;
    }
    [a.to_radians(), b.to_radians()]
}
fn unwrap(a: f64, center: f64) -> f64 {
    center + (a - center + PI).rem_euclid(TAU) - PI
}
fn area(p: &[Point]) -> f64 {
    if p.len() < 3 {
        return 0.0;
    }
    p.iter()
        .zip(p.iter().cycle().skip(1))
        .take(p.len())
        .map(|(a, b)| a[0] * b[1] - a[1] * b[0])
        .sum::<f64>()
        .abs()
        * 0.5
}
fn clip(p: &[Point], axis: usize, bound: f64, above: bool) -> Vec<Point> {
    let mut out = Vec::with_capacity(p.len() + 2);
    if p.is_empty() {
        return out;
    }
    let mut last = *p.last().unwrap();
    let mut inside = if above {
        last[axis] >= bound
    } else {
        last[axis] <= bound
    };
    for &point in p {
        let next = if above {
            point[axis] >= bound
        } else {
            point[axis] <= bound
        };
        if next != inside {
            let t = (bound - last[axis]) / (point[axis] - last[axis]);
            out.push([
                last[0] + t * (point[0] - last[0]),
                last[1] + t * (point[1] - last[1]),
            ]);
        }
        if next {
            out.push(point);
        }
        last = point;
        inside = next;
    }
    out
}
fn rectangle(p: &[Point], r: [f64; 2], a: [f64; 2]) -> Vec<Point> {
    clip(
        &clip(
            &clip(&clip(p, 0, r[0], true), 0, r[1], false),
            1,
            a[0],
            true,
        ),
        1,
        a[1],
        false,
    )
}
pub fn build(
    g: &Geometry,
    radial_unit: RadialUnit,
    bins: usize,
    azimuth_bins: usize,
    range: Option<[f64; 2]>,
    nss: usize,
) -> Result<Grid, String> {
    build_on_range(g, radial_unit, bins, azimuth_bins, range, nss, None)
}

#[allow(clippy::too_many_arguments)]
pub fn build_on_range(
    g: &Geometry,
    radial_unit: RadialUnit,
    bins: usize,
    azimuth_bins: usize,
    range: Option<[f64; 2]>,
    nss: usize,
    radial_range: Option<[f64; 2]>,
) -> Result<Grid, String> {
    let (tth, azi) = g.angular_corners();
    let radial = radial_unit.convert_from_tth(&tth, g.poni.wavelength);
    let (rmin, rmax, dr) = if let Some([lo, hi]) = radial_range {
        (lo, hi, (hi - lo) / bins as f64)
    } else if nss > 1 {
        let center_radial = radial_unit.convert_from_tth(&g.calc_tth_all(), g.poni.wavelength);
        dioptrin::math::histogram::ss_tth_min_max_step(g, &center_radial, bins, nss, radial_unit)
    } else {
        let min = radial.iter().copied().fold(f64::INFINITY, f64::min);
        let max = radial.iter().copied().fold(f64::NEG_INFINITY, f64::max) + 10.0 * f64::EPSILON;
        (min, max, (max - min) / bins as f64)
    };
    let angles = angular(range);
    let da = (angles[1] - angles[0]) / azimuth_bins as f64;
    let mut buckets = vec![Vec::<(usize, f64)>::new(); bins * azimuth_bins];
    let centers = g.calc_azimuth_all();
    let [h, w] = [g.dim1, g.dim2];
    let mut entries = 0usize;
    let mut sample_radial = Vec::new();
    let mut sample_azimuth = Vec::new();
    let chunk_pixels = (1_000_000 / (nss * nss)).max(1);
    let mut chunk_start = 0;
    for (i, &center_azimuth) in centers.iter().enumerate().take(h * w) {
        if nss > 1 {
            if i.is_multiple_of(chunk_pixels) {
                chunk_start = i;
                let stop = (i + chunk_pixels).min(h * w);
                let mut rr = Vec::with_capacity((stop - i) * nss * nss);
                let mut cc = Vec::with_capacity(rr.capacity());
                for pixel in i..stop {
                    for a in 0..nss {
                        for b in 0..nss {
                            rr.push((pixel / w) as f64 + (a as f64 + 0.5) / nss as f64);
                            cc.push((pixel % w) as f64 + (b as f64 + 0.5) / nss as f64);
                        }
                    }
                }
                let (t, a) = g.calc_tth_and_azimuth(&rr, &cc);
                sample_radial = radial_unit.convert_from_tth(&t, g.poni.wavelength);
                sample_azimuth = a;
            }
            let offset = (i - chunk_start) * nss * nss;
            for (&rv, &av) in sample_radial[offset..offset + nss * nss]
                .iter()
                .zip(&sample_azimuth[offset..offset + nss * nss])
            {
                let av = angles[0] + (av - angles[0]).rem_euclid(TAU);
                if av >= angles[1] {
                    continue;
                }
                if radial_range.is_some() && (rv < rmin || rv >= rmax) {
                    continue;
                }
                let rb = (((rv - rmin) / dr).floor() as usize).min(bins - 1);
                let ab = (((av - angles[0]) / da).floor() as usize).min(azimuth_bins - 1);
                buckets[ab * bins + rb].push((i, 1.0 / (nss * nss) as f64));
                entries += 1;
            }
        } else {
            let ids = g.corner_indices(i);
            let center = unwrap(center_azimuth, (angles[0] + angles[1]) * 0.5);
            let p: Vec<_> = ids
                .iter()
                .map(|&j| {
                    [
                        radial[j],
                        unwrap(azi[j], center_azimuth) + center - center_azimuth,
                    ]
                })
                .collect();
            let total = area(&p);
            if total <= 1e-30 {
                continue;
            }
            let low = p.iter().map(|p| p[0]).fold(f64::INFINITY, f64::min);
            let high = p.iter().map(|p| p[0]).fold(f64::NEG_INFINITY, f64::max);
            let first = ((low - rmin) / dr).floor().max(0.0) as usize;
            let last = (((high - rmin) / dr).floor() as usize).min(bins - 1);
            for shift in [-TAU, 0.0, TAU] {
                let poly: Vec<_> = p.iter().map(|p| [p[0], p[1] + shift]).collect();
                let amin = poly
                    .iter()
                    .map(|p| p[1])
                    .fold(f64::INFINITY, f64::min)
                    .max(angles[0]);
                let amax = poly
                    .iter()
                    .map(|p| p[1])
                    .fold(f64::NEG_INFINITY, f64::max)
                    .min(angles[1]);
                if amin >= amax {
                    continue;
                }
                let a_first = ((amin - angles[0]) / da).floor().max(0.0) as usize;
                let a_last = (((amax - angles[0]) / da).floor() as usize).min(azimuth_bins - 1);
                for ab in a_first..=a_last {
                    for rb in first..=last {
                        let fraction = area(&rectangle(
                            &poly,
                            [rmin + rb as f64 * dr, rmin + (rb + 1) as f64 * dr],
                            [angles[0] + ab as f64 * da, angles[0] + (ab + 1) as f64 * da],
                        )) / total;
                        if fraction > 0.0 {
                            buckets[ab * bins + rb].push((i, fraction));
                            entries += 1;
                        }
                    }
                }
            }
        }
        if entries > 64 * 1024 * 1024 {
            return Err("Sector lookup exceeds the 64-million-entry memory bound; reduce binning or supersampling.".into());
        }
    }
    let mut row_ptr = vec![0];
    let mut col_idx = Vec::with_capacity(entries);
    let mut values = Vec::with_capacity(entries);
    for bucket in buckets {
        // Sum subpixel contributions before squaring weights for Poisson errors.
        let mut bucket = bucket;
        bucket.sort_unstable_by_key(|v| v.0);
        let mut at = 0;
        while at < bucket.len() {
            let id = bucket[at].0;
            let mut weight = 0.0;
            while at < bucket.len() && bucket[at].0 == id {
                weight += bucket[at].1;
                at += 1;
            }
            col_idx.push(id);
            values.push(weight);
        }
        row_ptr.push(col_idx.len());
    }
    Ok(Grid {
        lut: Lut2d {
            row_ptr,
            col_idx,
            values: Some(values),
            n_tth: bins,
            n_azimuthal: azimuth_bins,
        },
        radial: [rmin + dr * 0.5, rmax - dr * 0.5],
        radial_step: dr,
        azimuth: [
            (angles[0] + da * 0.5).to_degrees(),
            (angles[1] - da * 0.5).to_degrees(),
        ],
    })
}
pub fn collapse(grid: Grid) -> Lut1d {
    let step = grid.radial_step;
    Lut1d {
        row_ptr: grid.lut.row_ptr,
        col_idx: grid.lut.col_idx,
        values: grid.lut.values,
        hist_min: grid.radial[0] - step * 0.5,
        hist_step: step,
    }
}

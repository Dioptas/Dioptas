//! Acquisition gap margins can be wider than the generic detector catalogue.
//! Infer only long, nearly uniform sentinel strips adjoining known gap bands;
//! zero-valued individual pixels and dark images are not generic bad pixels.
pub(crate) fn extend_gaps(mask: &mut [u8], image: &[f64], [h, w]: [usize; 2], dtype: &str) -> bool {
    if h == 0 || w == 0 || mask.len() != h * w || image.len() != mask.len() {
        return false;
    }
    let maximum = match dtype {
        "U16" => u16::MAX as f64,
        "I16" => i16::MAX as f64,
        "U32" => u32::MAX as f64,
        "I32" | "F64" => i32::MAX as f64,
        _ => return true,
    };
    let flag = |v: f64| {
        v == 0.
            || v == -1.
            || v == maximum
            || (["U32", "F64"].contains(&dtype) && (v == i32::MAX as f64 || v == u32::MAX as f64))
    };
    let rows: Vec<_> = (0..h)
        .map(|r| mask[r * w..(r + 1) * w].iter().all(|&v| v != 0))
        .collect();
    let cols: Vec<_> = (0..w)
        .map(|c| (0..h).all(|r| mask[r * w + c] != 0))
        .collect();
    fn segments(gaps: &[bool]) -> Vec<(usize, usize)> {
        let mut result = vec![];
        let mut start = None;
        for i in 0..=gaps.len() {
            if i < gaps.len() && !gaps[i] {
                start.get_or_insert(i);
            } else if let Some(a) = start.take() {
                result.push((a, i));
            }
        }
        result
    }
    let blocks_r = segments(&rows);
    let blocks_c = segments(&cols);
    if !rows.iter().any(|&v| v) && !cols.iter().any(|&v| v) {
        return true;
    }
    let mut established = true;
    for &(r0, r1) in &blocks_r {
        for &(c0, c1) in &blocks_c {
            // Narrow slivers and uniform zero exposures cannot establish a margin.
            if r1 - r0 < 16 || c1 - c0 < 16 {
                continue;
            }
            let middle = (r0 + r1) / 2;
            if (c0..c1).filter(|&c| !flag(image[middle * w + c])).count() * 10 < c1 - c0 {
                established = false;
                continue;
            }
            for reverse in [false, true] {
                for d in 0..32.min((r1 - r0) / 4) {
                    let r = if reverse { r1 - 1 - d } else { r0 + d };
                    let count = (c0..c1).filter(|&c| flag(image[r * w + c])).count();
                    if count * 100 < (c1 - c0) * 99 {
                        break;
                    }
                    for c in c0..c1 {
                        if flag(image[r * w + c]) {
                            mask[r * w + c] = 1;
                        }
                    }
                }
                for d in 0..32.min((c1 - c0) / 4) {
                    let c = if reverse { c1 - 1 - d } else { c0 + d };
                    let count = (r0..r1).filter(|&r| flag(image[r * w + c])).count();
                    if count * 100 < (r1 - r0) * 99 {
                        break;
                    }
                    for r in r0..r1 {
                        if flag(image[r * w + c]) {
                            mask[r * w + c] = 1;
                        }
                    }
                }
            }
        }
    }
    established
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn margins_follow_max_zero_and_minus_one_but_not_valid_zero_pixels_or_dark_frames() {
        let [h, w] = [128, 160];
        let mut base = vec![0; h * w];
        for r in 60..64 {
            base[r * w..(r + 1) * w].fill(1);
        }
        for r in 0..h {
            base[r * w + 78..r * w + 82].fill(1);
        }
        for value in [0., -1., i32::MAX as f64] {
            let mut data = vec![120.; h * w];
            for r in 57..68 {
                for c in 0..w {
                    data[r * w + c] = value;
                }
            }
            for r in 0..h {
                for c in 75..85 {
                    data[r * w + c] = value;
                }
            }
            data[10 * w + 10] = 0.;
            data[9 * w + 10] = i32::MAX as f64;
            let mut mask = base.clone();
            extend_gaps(&mut mask, &data, [h, w], "I32");
            for r in 57..68 {
                assert!(mask[r * w..(r + 1) * w].iter().all(|&v| v == 1));
            }
            for r in 0..h {
                assert!(mask[r * w + 75..r * w + 85].iter().all(|&v| v == 1));
            }
            assert_eq!(mask[10 * w + 10], 0);
            assert_eq!(mask[9 * w + 10], 0);
        }
        let mut mask = base.clone();
        extend_gaps(&mut mask, &vec![0.; h * w], [h, w], "I32");
        assert_eq!(mask, base);
        let mut mask = base.clone();
        extend_gaps(&mut mask, &vec![0.; h * w], [h, w], "F64");
        assert_eq!(mask, base);
    }
}

#[cfg(test)]
mod optional_benchmark {
    #[test]
    #[ignore = "requires an external full-resolution Eiger test image"]
    fn time_full_resolution_gap_extension() {
        let path = std::env::var("DIOPTAS_EIGER_IMAGE").expect("DIOPTAS_EIGER_IMAGE");
        let image =
            crate::image::Image::open(std::path::Path::new(&path), &serde_json::json!({})).unwrap();
        let detector = dioptrin::detector::named("Eiger2 CdTe 9M").unwrap();
        let base = detector.builtin_mask(image.shape).unwrap();
        let mut times = vec![];
        for _ in 0..30 {
            let mut mask = base.clone();
            let start = std::time::Instant::now();
            super::extend_gaps(&mut mask, &image.values, image.shape, &image.source_dtype);
            times.push(start.elapsed().as_secs_f64() * 1000.);
            std::hint::black_box(mask);
        }
        times.sort_by(f64::total_cmp);
        println!(
            "Gap extension only, {}x{}: median {:.3} ms; min {:.3}, max {:.3}; 30 repeats",
            image.shape[0], image.shape[1], times[15], times[0], times[29]
        );
    }
}

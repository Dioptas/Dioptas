//! Compare the actual custom-pattern dispatcher with its previous strict kernels.
use super::*;
use dioptrin::lut::{self, AzimuthalIntegrationResult};

fn options() -> Options {
    Options {
        bins: 31,
        automatic_bins: false,
        cake_bins: 18,
        unit: "2th_deg".into(),
        polarization: 0.83,
        errors: false,
        supersampling: 1,
        pyfai: false,
        solid_angle: true,
        azimuth: Some([-110., 65.]),
        cake_azimuth: None,
        trim: false,
        spread: false,
        dynamic_mask: false,
        csc: false,
        auto_layout: false,
    }
}

/// The old dispatcher, using the SAME frozen LUT as the candidate. Rebuilding
/// a pixel-split table independently can change the within-bin pixel order.
fn previous(
    plan: &mut Plan,
    data: &[f64],
    supplied: Option<&[f64]>,
    mask: &[u8],
    o: &Options,
) -> AzimuthalIntegrationResult {
    plan.prepare_general(o).unwrap();
    if o.pyfai && !o.dynamic_mask && !o.spread && supplied.is_none() {
        let r = plan
            .fixed_compatibility(o, mask)
            .unwrap()
            .integrate_frame(data, o.errors)
            .unwrap();
        return AzimuthalIntegrationResult {
            radial: r.radial,
            intensity: r.intensity,
            errors: r.errors,
            azimuthal_std: vec![],
        };
    }
    let lut = plan.general_1d.as_ref().unwrap();
    let norm = plan.normalization.as_ref().unwrap();
    let poisson = (o.errors && supplied.is_none())
        .then(|| data.iter().map(|v| v.max(0.)).collect::<Vec<_>>());
    let variance = supplied.or(poisson.as_deref());
    if o.spread {
        lut::integrate1d_with_azimuthal_std(data, lut, Some(mask), norm, variance)
    } else {
        let (radial, intensity, errors) = if let Some(v) = variance {
            let (x, y, e) = lut::integrate1d_with_errors(data, v, lut, Some(mask), norm);
            (x, y, Some(e))
        } else {
            let (x, y) = lut::integrate1d(data, lut, Some(mask), norm);
            (x, y, None)
        };
        AzimuthalIntegrationResult {
            radial,
            intensity,
            errors,
            azimuthal_std: vec![],
        }
    }
}
fn same(a: &[f64], b: &[f64]) {
    assert_eq!(a.len(), b.len());
    for (i, (a, b)) in a.iter().zip(b).enumerate() {
        assert_eq!(a.to_bits(), b.to_bits(), "bin {i}: {a} != {b}");
    }
}
fn same_result(a: &AzimuthalIntegrationResult, b: &AzimuthalIntegrationResult) {
    same(&a.radial, &b.radial);
    same(&a.intensity, &b.intensity);
    same(&a.azimuthal_std, &b.azimuthal_std);
    match (&a.errors, &b.errors) {
        (Some(a), Some(b)) => same(a, b),
        (None, None) => (),
        _ => panic!("error availability changed"),
    }
}
fn parameters(shape: [usize; 2]) -> Parameters {
    Parameters {
        pixel1: 1e-4,
        pixel2: 1.3e-4,
        poni1: shape[0] as f64 * 4.3e-5,
        poni2: shape[1] as f64 * 5.7e-5,
        dist: 0.04,
        ..Parameters::default()
    }
}
#[test]
fn fixed_custom_patterns_preserve_every_result_bit_and_reuse_the_snapshot() {
    crate::worker_pool::pool(Some(2)).unwrap().install(|| {
        let shape = [19, 23];
        let p = parameters(shape);
        let mask: Vec<_> = (0..shape[0] * shape[1])
            .map(|i| {
                if i % 19 == 0 {
                    255
                } else {
                    u8::from(i % 17 == 0)
                }
            })
            .collect();
        for unit in ["2th_deg", "q_A^-1", "q_nm^-1"] {
            for solid in [false, true] {
                for pyfai in [false, true] {
                    for ss in [1, 2] {
                        for angle in [None, Some([-110., 65.]), Some([160., -150.])] {
                            let mut o = options();
                            o.unit = unit.into();
                            o.solid_angle = solid;
                            o.pyfai = pyfai;
                            o.supersampling = ss;
                            o.azimuth = angle;
                            let mut plan = Plan::new(key(shape, &p, &mask, &o, false)).unwrap();
                            for errors in [false, true] {
                                o.errors = errors;
                                for frame in [0., 2.3] {
                                    let data: Vec<_> = (0..mask.len())
                                        .map(|i| {
                                            if mask[i] != 0 {
                                                f64::NAN
                                            } else {
                                                ((i * 37) % 103) as f64 * frame - 17.3
                                            }
                                        })
                                        .collect();
                                    let expected = previous(&mut plan, &data, None, &mask, &o);
                                    let actual =
                                        plan.general_pattern(&data, None, &mask, &o).unwrap();
                                    same_result(&actual, &expected);
                                    let snapshot = plan
                                        .compatibility_1d
                                        .as_ref()
                                        .expect("custom grids use a prepared snapshot")
                                        .clone();
                                    same_result(
                                        &plan.general_pattern(&data, None, &mask, &o).unwrap(),
                                        &expected,
                                    );
                                    assert!(Arc::ptr_eq(
                                        &snapshot,
                                        plan.compatibility_1d.as_ref().unwrap()
                                    ));
                                }
                            }
                        }
                    }
                }
            }
        }
    });
}
#[test]
fn supplied_variances_spread_and_changing_masks_keep_their_original_kernels() {
    crate::worker_pool::pool(Some(2)).unwrap().install(|| {
        let shape = [17, 21];
        let p = parameters(shape);
        let data: Vec<_> = (0..shape[0] * shape[1])
            .map(|i| ((i * 37) % 103) as f64 - 41.7)
            .collect();
        let variance: Vec<_> = data.iter().map(|x| x.abs() * 2. + 3.).collect();
        for pyfai in [false, true] {
            for spread in [false, true] {
                for dynamic in [false, true] {
                    for supplied in [false, true] {
                        if !spread && !dynamic && !supplied {
                            continue;
                        }
                        let mut o = options();
                        o.pyfai = pyfai;
                        o.spread = spread;
                        o.dynamic_mask = dynamic;
                        o.errors = true;
                        let mask = vec![0; data.len()];
                        let mut plan = Plan::new(key(shape, &p, &mask, &o, false)).unwrap();
                        for stride in [7, 11, 19] {
                            let mask: Vec<_> =
                                (0..data.len()).map(|i| u8::from(i % stride == 0)).collect();
                            let v = supplied.then_some(variance.as_slice());
                            let expected = previous(&mut plan, &data, v, &mask, &o);
                            let actual = plan.general_pattern(&data, v, &mask, &o).unwrap();
                            same_result(&actual, &expected);
                            assert!(
                                plan.compatibility_1d.is_none(),
                                "unsupported paths must not capture a fixed mask"
                            );
                        }
                    }
                }
            }
        }
    });
}
#[test]
fn all_masked_zero_and_nonfinite_custom_frames_retain_legacy_results() {
    crate::worker_pool::pool(Some(2)).unwrap().install(|| {
        let shape = [7, 9];
        let p = parameters(shape);
        let mut o = options();
        for masked in [false, true] {
            let mask = vec![u8::from(masked); shape[0] * shape[1]];
            let mut plan = Plan::new(key(shape, &p, &mask, &o, false)).unwrap();
            for value in [0., -0., -3., f64::INFINITY, f64::NEG_INFINITY, f64::NAN] {
                let data = vec![value; mask.len()];
                for errors in [false, true] {
                    o.errors = errors;
                    let expected = previous(&mut plan, &data, None, &mask, &o);
                    same_result(
                        &plan.general_pattern(&data, None, &mask, &o).unwrap(),
                        &expected,
                    );
                }
            }
        }
    });
}

#[test]
fn fixed_custom_cache_rebuilds_after_scientific_inputs_change() {
    crate::worker_pool::pool(Some(2)).unwrap().install(|| {
        let mut cache = Engine::default();
        let mut o = options();
        let mut p = parameters([19, 23]);
        let mut last = None;
        for step in 0..7 {
            let shape = if step == 6 { [23, 19] } else { [19, 23] };
            let mut mask = vec![0; shape[0] * shape[1]];
            match step {
                1 => mask[5] = 1,
                2 => p.dist *= 1.03,
                3 => o.polarization = 0.4,
                4 => o.azimuth = Some([160., -150.]),
                5 => o.bins += 3,
                _ => (),
            }
            let data: Vec<_> = (0..mask.len())
                .map(|i| ((i * 37) % 101) as f64 - 7.)
                .collect();
            let plan = cache
                .pattern_plan(key(shape, &p, &mask, &o, false))
                .unwrap();
            let expected = previous(plan, &data, None, &mask, &o);
            let actual = plan.general_pattern(&data, None, &mask, &o).unwrap();
            same_result(&actual, &expected);
            let snapshot = plan.compatibility_1d.as_ref().unwrap().clone();
            if let Some(old) = last {
                assert!(!Arc::ptr_eq(&old, &snapshot))
            }
            last = Some(snapshot);
        }
        assert_eq!(cache.pattern_builds, 7);
    });
}

/// Explicit local benchmark; results are printed, never written into the repo.
/// DIOPTRIN_FIXTURES must point to a directory containing v1.poni and
/// CeO2_Pilatus1M.tif (Dioptrin's documented test fixture).
#[test]
#[ignore = "requires external Pilatus fixtures and an idle machine; run in release mode"]
fn benchmark_prepared_custom_patterns() {
    use std::{hint::black_box, time::Instant};
    let root = std::env::var("DIOPTRIN_FIXTURES").expect("set DIOPTRIN_FIXTURES");
    let frame = dioptrin::frame::Frame::from_tiff(format!("{root}/CeO2_Pilatus1M.tif")).unwrap();
    let g = dioptrin::poni::Poni::load(&format!("{root}/v1.poni")).unwrap();
    let p = Parameters {
        dist: g.distance,
        poni1: g.poni1,
        poni2: g.poni2,
        rot1: g.rot1,
        rot2: g.rot2,
        rot3: g.rot3,
        pixel1: g.pixel1,
        pixel2: g.pixel2,
        wavelength: g.wavelength,
        ..Parameters::default()
    };
    let shape = [frame.dim1, frame.dim2];
    let data: Vec<_> = frame
        .data
        .iter()
        .enumerate()
        .map(|(i, x)| x - (i % 7) as f64 * 3.2)
        .collect();
    let mask: Vec<_> = (0..data.len()).map(|i| u8::from(i % 19 == 0)).collect();
    let threads = std::env::var("DIOPTAS_BENCH_THREADS")
        .ok()
        .map(|s| s.parse().unwrap())
        .unwrap_or(crate::worker_pool::effective(None));
    crate::worker_pool::pool(Some(threads)).unwrap().install(|| {
        for (name,angle,solid,pyfai) in [("custom_sector",Some([-110.,65.]),true,false),("no_solid_angle",None,false,false),("pyfai_control",Some([-110.,65.]),true,true)] {
            let mut o=options();o.bins=1250;o.azimuth=angle;o.solid_angle=solid;o.pyfai=pyfai;o.polarization=0.99;
            let mut plan=Plan::new(key(shape,&p,&mask,&o,false)).unwrap();plan.prepare_general(&o).unwrap();
            let setup=Instant::now();plan.fixed_compatibility(&o,&mask).unwrap();let setup_ms=setup.elapsed().as_secs_f64()*1e3;
            for errors in [false,true] {o.errors=errors;
                let expected=previous(&mut plan,&data,None,&mask,&o);let actual=plan.general_pattern(&data,None,&mask,&o).unwrap();same_result(&actual,&expected);
                let run=|plan:&mut Plan,candidate:bool,repeats:usize| {let start=Instant::now();for _ in 0..repeats {if candidate {black_box(plan.general_pattern(&data,None,&mask,&o).unwrap());}else{black_box(previous(plan,&data,None,&mask,&o));}}start.elapsed().as_secs_f64()*1e6/repeats as f64};
                run(&mut plan,false,8);run(&mut plan,true,8);
                let mut old=vec![];let mut new=vec![];
                for i in 0..31 {if i%2==0 {old.push(run(&mut plan,false,48));new.push(run(&mut plan,true,48));}else{new.push(run(&mut plan,true,48));old.push(run(&mut plan,false,48));}}
                old.sort_by(f64::total_cmp);new.sort_by(f64::total_cmp);
                println!("{}",json!({"case":name,"errors":errors,"threads":threads,"baseline_us":old[15],"prepared_us":new[15],"speedup":old[15]/new[15],"setup_ms":setup_ms,"bitwise_equal":true,"samples":31,"repeats":48,"base_p10_p90_us":[old[3],old[27]],"plan_p10_p90_us":[new[3],new[27]]}));
            }
        }
    });
}

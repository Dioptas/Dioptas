//! Independent evaluations of the editor equations against the pinned PeriTheos.
//! These sample implementation agreement, not source-paper validity or fit quality.
use dioptas_backend::{Session, protocol::Request};
use peritheos::{IsothermalEos, ThermalEos, isothermal::*, thermal::*};
use serde_json::{Value, json};
use std::path::Path;
const V0: f64 = 2.5;
const K0: f64 = 160.0;
const KP: f64 = 4.6;
const KPP: f64 = -0.028;
const TR: f64 = 298.15;
const R: f64 = 8.31446261815324;
const N: f64 = 2.0;
fn close(label: &str, actual: f64, expected: f64, tolerance: f64) {
    assert!(
        (actual - expected).abs() <= tolerance * expected.abs().max(1.0),
        "{label}: native={actual:.14e}, displayed={expected:.14e}"
    );
}
fn integrate(f: impl Fn(f64) -> f64, a: f64, b: f64) -> f64 {
    let count = 512;
    let h = (b - a) / count as f64;
    let mut sum = f(a) + f(b);
    for i in 1..count {
        sum += if i % 2 == 0 { 2.0 } else { 4.0 } * f(a + h * i as f64);
    }
    sum * h / 3.0
}
fn d3(y: f64) -> f64 {
    3.0 / y.powi(3)
        * integrate(
            |z| {
                if z == 0.0 {
                    0.0
                } else {
                    z.powi(3) / z.exp_m1()
                }
            },
            0.0,
            y,
        )
}
fn bm3_at(v: f64, v0: f64, k: f64, kp: f64) -> f64 {
    let f = ((v0 / v).powf(2.0 / 3.0) - 1.0) / 2.0;
    3.0 * k * f * (1.0 + 2.0 * f).powf(2.5) * (1.0 + 1.5 * (kp - 4.0) * f)
}
fn cold(v: f64) -> f64 {
    bm3_at(v, V0, K0, KP)
}
fn reference() -> BM3 {
    BM3::new(V0, K0, KP).unwrap()
}
fn derivative(f: impl Fn(f64) -> f64, v: f64) -> f64 {
    let h = v * 1e-5;
    (f(v - 2.0 * h) - 8.0 * f(v - h) + 8.0 * f(v + h) - f(v + 2.0 * h)) / (12.0 * h)
}
fn compare<M: ThermalEos>(label: &str, model: M, expected: impl Fn(f64, f64) -> f64) {
    for x in [0.82, 1.0, 1.04] {
        for t in [TR, 600.0, 1600.0] {
            close(
                label,
                model.pressure(V0 * x, t).unwrap(),
                expected(V0 * x, t),
                2e-7,
            );
        }
    }
}
#[test]
fn all_eleven_isothermal_equations() {
    let models: Vec<(&str, Box<dyn IsothermalEos>)> = vec![
        ("BM2", Box::new(BM2::new(V0, K0).unwrap())),
        (
            "BM2Reference",
            Box::new(BM2Reference::new(V0, K0, 12.0).unwrap()),
        ),
        ("BM3", Box::new(reference())),
        ("BM4", Box::new(BM4::new(V0, K0, KP, KPP).unwrap())),
        (
            "NaturalStrain2",
            Box::new(NaturalStrain2::new(V0, K0).unwrap()),
        ),
        (
            "NaturalStrain3",
            Box::new(NaturalStrain3::new(V0, K0, KP).unwrap()),
        ),
        (
            "NaturalStrain4",
            Box::new(NaturalStrain4::new(V0, K0, KP, KPP).unwrap()),
        ),
        ("Murnaghan", Box::new(Murnaghan::new(V0, K0, KP).unwrap())),
        ("Vinet", Box::new(Vinet::new(V0, K0, KP).unwrap())),
        (
            "ModifiedTait",
            Box::new(ModifiedTait::new(V0, K0, KP, KPP).unwrap()),
        ),
        (
            "Holzapfel",
            Box::new(Holzapfel::new(V0, K0, KP, N, 12.0).unwrap()),
        ),
    ];
    for (name, model) in models {
        close(name, model.bulk_modulus(V0).unwrap(), K0, 1e-12);
        let expected_prime = match name {
            "BM2" | "BM2Reference" => 4.0,
            "NaturalStrain2" => 2.0,
            _ => KP,
        };
        close(
            name,
            model.bulk_modulus_derivative(V0, 1e-5).unwrap(),
            expected_prime,
            2e-8,
        );
        if ["BM4", "NaturalStrain4", "ModifiedTait"].contains(&name) {
            let second = derivative(|v| model.bulk_modulus_derivative(v, 1e-4).unwrap(), V0)
                / derivative(|v| model.pressure(v).unwrap(), V0);
            close(name, second, KPP, 2e-6);
        }
        for x in [0.72_f64, 0.92, 1.0, 1.06] {
            let v = V0 * x;
            let f = (x.powf(-2.0 / 3.0) - 1.0) / 2.0;
            let base = 3.0 * K0 * f * (1.0 + 2.0 * f).powf(2.5);
            let expected = match name {
                "BM2" => base,
                "BM2Reference" => base + 12.0,
                "BM3" => cold(v),
                "BM4" => {
                    let zeta = 0.75 * (4.0 - KP);
                    let xi = 0.375 * (K0 * KPP + (KP - 4.0) * (KP - 3.0) + 35.0 / 9.0);
                    base * (1.0 - 2.0 * zeta * f + 4.0 * xi * f * f)
                }
                "NaturalStrain2" | "NaturalStrain3" | "NaturalStrain4" => {
                    let f = -x.ln() / 3.0;
                    let a = if name.ends_with('2') {
                        0.0
                    } else {
                        1.5 * (KP - 2.0)
                    };
                    let b = if name.ends_with('4') {
                        1.5 * (K0 * KPP + 1.0 + (KP - 2.0) + (KP - 2.0).powi(2))
                    } else {
                        0.0
                    };
                    3.0 * K0 / x * (f + a * f * f + b * f.powi(3))
                }
                "Murnaghan" => K0 / KP * (x.powf(-KP) - 1.0),
                "Vinet" => {
                    let x = x.cbrt();
                    3.0 * K0 * (1.0 - x) / x.powi(2) * (1.5 * (KP - 1.0) * (1.0 - x)).exp()
                }
                "ModifiedTait" => {
                    let a = (1.0 + KP) / (1.0 + KP + K0 * KPP);
                    let b = KP / K0 - KPP / (1.0 + KP);
                    let c = (1.0 + KP + K0 * KPP) / (KP * KP + KP - K0 * KPP);
                    (((x + a - 1.0) / a).powf(-1.0 / c) - 1.0) / b
                }
                "Holzapfel" => {
                    let x = x.cbrt();
                    let pfg = 1003.6 * (12.0 * N / (10.0 * V0)).powf(5.0 / 3.0);
                    let c0 = -(3.0 * K0 / pfg).ln();
                    let c2 = 1.5 * (KP - 3.0) - c0;
                    3.0 * K0
                        * (c0 * (1.0 - x)).exp()
                        * (x.powi(-5) - x.powi(-4))
                        * (1.0 + c2 * x - c2 * x * x)
                }
                _ => unreachable!(),
            };
            close(name, model.pressure(v).unwrap(), expected, 2e-12);
            // Also verifies the K=-V dP/dV definition used in parameter help.
            close(
                name,
                model.bulk_modulus(v).unwrap(),
                -v * derivative(|u| model.pressure(u).unwrap(), v),
                2e-8,
            );
        }
    }
    close(
        "Murnaghan Kprime=0",
        Murnaghan::new(V0, K0, 0.0)
            .unwrap()
            .pressure(0.9 * V0)
            .unwrap(),
        K0 * (1.0_f64 / 0.9).ln(),
        1e-12,
    );
}
#[test]
fn debye_einstein_laws_references_and_cvmax() {
    for q in [0.0, 1.2] {
        for variable in [false, true] {
            for baseline in [
                ThermalPressureReference::ReferenceTemperature,
                ThermalPressureReference::AbsoluteZero,
                ThermalPressureReference::ReferenceIsentrope,
            ] {
                for cv in [None, Some(43.0)] {
                    let law = if variable {
                        DebyeTemperatureLaw::VariableExponent
                    } else {
                        DebyeTemperatureLaw::IntegratedGruneisen
                    };
                    let model = MieGruneisenDebye::new_with_heat_capacity(
                        reference(),
                        TR,
                        500.0,
                        1.6,
                        q,
                        N,
                        cv,
                        law,
                        baseline,
                    )
                    .unwrap();
                    compare("MGD", model, |v, t| {
                        let x = v / V0;
                        let gamma = 1.6 * x.powf(q);
                        let theta = 500.0
                            * if variable {
                                x.powf(-gamma)
                            } else if q == 0.0 {
                                x.powf(-1.6)
                            } else {
                                (-1.6 / q * (x.powf(q) - 1.0)).exp()
                            };
                        let energy = |temp| cv.unwrap_or(3.0 * N * R) * temp * d3(theta / temp);
                        let ref_energy = match baseline {
                            ThermalPressureReference::AbsoluteZero => 0.0,
                            ThermalPressureReference::ReferenceIsentrope => {
                                energy(TR * theta / 500.0)
                            }
                            _ => energy(TR),
                        };
                        cold(v) + 1e-4 * gamma / v * (energy(t) - ref_energy)
                    });
                }
            }
        }
    }
    compare(
        "MGE",
        MieGruneisenEinstein::new(reference(), TR, 500.0, 1.6, 1.2, N).unwrap(),
        |v, t| {
            let x = v / V0;
            let theta = 500.0 * (-1.6 / 1.2 * (x.powf(1.2) - 1.0)).exp();
            cold(v)
                + 1e-4 * 1.6 * x.powf(1.2) / v
                    * 3.0
                    * N
                    * R
                    * theta
                    * (1.0 / (theta / t).exp_m1() - 1.0 / (theta / TR).exp_m1())
        },
    );
}
#[test]
fn reference_state_choices() {
    for (expansion, volume) in [
        (
            ThermalExpansionLaw::Constant,
            ReferenceVolumeLaw::IntegratedExpansivity,
        ),
        (
            ThermalExpansionLaw::LinearTemperature,
            ReferenceVolumeLaw::IntegratedExpansivity,
        ),
        (
            ThermalExpansionLaw::LinearReferenceTemperature,
            ReferenceVolumeLaw::IntegratedExpansivity,
        ),
        (
            ThermalExpansionLaw::Constant,
            ReferenceVolumeLaw::LinearTemperature,
        ),
        (
            ThermalExpansionLaw::LinearTemperature,
            ReferenceVolumeLaw::Berman,
        ),
    ] {
        for reciprocal in [false, true] {
            let alpha1 = if expansion == ThermalExpansionLaw::Constant {
                0.0
            } else {
                2e-8
            };
            let model = ThermalReferenceState::new(
                reference(),
                TR,
                3e-5,
                if reciprocal { 0.0 } else { -0.015 },
                alpha1,
                expansion,
                volume,
            )
            .unwrap()
            .with_temperature_laws(
                if reciprocal {
                    Some([1e-7, 2e-11, 1e-15])
                } else {
                    None
                },
                2e-5,
            )
            .unwrap()
            .with_linear_pressure_derivative(-1e-4)
            .unwrap();
            compare("AlphaKT", model, |v, t| {
                let dt = t - TR;
                let v0 = V0
                    * match volume {
                        ReferenceVolumeLaw::LinearTemperature => 1.0 + 3e-5 * dt,
                        ReferenceVolumeLaw::Berman => 1.0 + 3e-5 * dt + alpha1 * dt * dt / 2.0,
                        _ => (3e-5 * dt
                            + match expansion {
                                ThermalExpansionLaw::LinearTemperature => {
                                    alpha1 * (t * t - TR * TR) / 2.0
                                }
                                ThermalExpansionLaw::LinearReferenceTemperature => {
                                    alpha1 * dt * dt / 2.0
                                }
                                _ => 0.0,
                            })
                        .exp(),
                    };
                let k = if reciprocal {
                    1.0 / (1.0 / K0
                        + 1e-7 * dt
                        + 2e-11 * (t * t - TR * TR)
                        + 1e-15 * (t.powi(3) - TR.powi(3)))
                } else {
                    K0 - 0.015 * dt
                };
                bm3_at(v, v0, k, KP - 1e-4 * dt + 2e-5 * dt * (t / TR).ln())
            });
        }
    }
}
#[test]
fn pressure_polynomials_holland_powell_and_tange() {
    compare(
        "Linear",
        LinearThermalPressure::new(reference(), TR, 0.004).unwrap(),
        |v, t| cold(v) + 0.004 * (t - TR),
    );
    compare(
        "Log",
        LogVolumeThermalPressure::new(reference(), TR, 0.004, -0.01).unwrap(),
        |v, t| cold(v) + (0.004 - 0.01 * (V0 / v).ln()) * (t - TR),
    );
    compare(
        "Taylor",
        SecondOrderTaylorThermalPressure::new(
            reference(),
            TR,
            0.02,
            0.2,
            1.1,
            0.003,
            2.0,
            1e-7,
            0.001,
        )
        .unwrap(),
        |v, t| {
            let de = 1.0 - v / V0 - 0.02;
            let dt = t - TR;
            cold(v) + 0.2 + 1.1 * de + 0.003 * dt + de * de + 0.5e-7 * dt * dt + 0.0005 * de * dt
        },
    );
    let hp = |t: f64| {
        let y = 500.0 / TR;
        let cv = 3.0 * N * R * y * y * y.exp() / y.exp_m1().powi(2);
        let energy = |temp: f64| 3.0 * N * R * 500.0 / (500.0 / temp).exp_m1();
        3e-5 * K0 / cv * (energy(t) - energy(TR))
    };
    compare(
        "HP",
        HollandPowellThermalPressure::new(reference(), TR, 500.0, 3e-5, N).unwrap(),
        |v, t| cold(v) + hp(t),
    );
    let tait = ModifiedTait::new(V0, K0, KP, KPP).unwrap();
    compare(
        "ThermalTait",
        ThermalModifiedTait::new(tait, TR, 500.0, 3e-5, N).unwrap(),
        |v, t| tait.pressure(v).unwrap() + hp(t),
    );
    for b in [0.0, 2.5] {
        let debye =
            AsymptoticPowerLawMieGruneisenDebye::new(reference(), TR, 500.0, 1.6, 0.2, b, N)
                .unwrap();
        let pressure = |v: f64, t: f64| {
            let x = v / V0;
            let gamma = 1.6 * (1.0 + 0.2 * (x.powf(b) - 1.0));
            let theta = 500.0
                * if b == 0.0 {
                    x.powf(-1.6)
                } else {
                    (-1.6 * (0.8 * x.ln() + 0.2 / b * (x.powf(b) - 1.0))).exp()
                };
            cold(v) + 1e-4 * gamma / v * 3.0 * N * R * (t * d3(theta / t) - TR * d3(theta / TR))
        };
        compare("Tange", debye, pressure);
        compare(
            "TangeExcess",
            AsymptoticPowerLawMieGruneisenDebyeExcess::new(debye, 0.001, 1.7).unwrap(),
            |v, t| {
                pressure(v, t)
                    + 1e-4 * 0.001 * 1.7 / (2.0 * V0) * (v / V0).powf(0.7) * (t * t - TR * TR)
            },
        );
    }
    compare(
        "DebyeQuadratic",
        DebyeQuadraticThermalPressure::new(reference(), TR, 500.0, 1.6, 1.2, N, 2e-7, 1.7).unwrap(),
        |v, t| {
            let x = v / V0;
            let theta = 500.0 * (-1.6 / 1.2 * (x.powf(1.2) - 1.0)).exp();
            cold(v)
                + 1e-4 * 1.6 * x.powf(1.2) / v
                    * 3.0
                    * N
                    * R
                    * (t * d3(theta / t) - TR * d3(theta / TR))
                + 2e-7 * x.powf(1.7) * (t * t - TR * TR)
        },
    );
}
#[test]
fn dewaele_zero_point_units_and_beta_domain() {
    let create = |beta| {
        Dewaele2006::new(
            reference(),
            TR,
            500.0,
            1.6,
            0.5,
            beta,
            2e-5,
            1.2,
            3e-5,
            1.7,
            N,
        )
    };
    assert!(create(0.0).is_err());
    for absolute in [false, true] {
        for zp in [false, true] {
            if zp && !absolute {
                continue;
            }
            let model = create(2.0)
                .unwrap()
                .with_thermal_pressure_reference(if absolute {
                    ThermalPressureReference::AbsoluteZero
                } else {
                    ThermalPressureReference::ReferenceTemperature
                })
                .unwrap()
                .with_zero_point_pressure(zp)
                .unwrap();
            compare("Dewaele", model, |v, t| {
                let x = v / V0;
                let gamma = 0.5 + 1.1 * x * x;
                let theta = 500.0 * x.powf(-0.5) * (1.1 / 2.0 * (1.0 - x * x)).exp();
                let p = |t: f64| {
                    1e-4 * 3.0 * N * R / v
                        * (gamma * t * d3(theta / t)
                            + 0.5 * (1.2 * 2e-5 * x.powf(1.2) + 1.7 * 3e-5 * x.powf(1.7)) * t * t)
                };
                cold(v) + p(t) - if absolute { 0.0 } else { p(TR) }
                    + if zp {
                        1e-4 * 9.0 * N * R * gamma * theta / (8.0 * v)
                    } else {
                        0.0
                    }
            });
        }
    }
}
fn double_ion(v: f64, t: f64, log: bool) -> f64 {
    let theta = |initial: f64, a: f64, b: f64| initial * (v / V0).powf(-b) * (a * (V0 - v)).exp();
    let a = theta(300.0, 0.1, 0.8);
    let b = theta(700.0, 0.15, 0.9);
    let moment = theta(450.0, 0.12, 0.85);
    let w = if log {
        (b / moment).ln() / (b / a).ln()
    } else {
        (b - moment) / (b - a)
    };
    let f = |theta: f64| {
        R * (9.0 * theta / 8.0 + 3.0 * t * (1.0 - (-theta / t).exp()).ln() - t * d3(theta / t))
    };
    N * (w * f(a) + (1.0 - w) * f(b))
}
#[test]
fn both_double_debye_free_energy_derivatives() {
    for tr in [None, Some(TR)] {
        let mut arithmetic = DoubleDebyeHelmholtz::new(
            reference(),
            V0,
            300.0,
            0.1,
            0.8,
            700.0,
            0.15,
            0.9,
            450.0,
            0.12,
            0.85,
            N,
            2e-5,
            2.2,
            1.3,
            17.0,
        )
        .unwrap();
        let mut log = DoubleDebyeLogMomentHelmholtz::new(
            reference(),
            V0,
            300.0,
            0.1,
            0.8,
            700.0,
            0.15,
            0.9,
            450.0,
            0.12,
            0.85,
            N,
            2e-5,
            17.0,
        )
        .unwrap();
        if let Some(t) = tr {
            arithmetic = arithmetic.with_reference_temperature(t).unwrap();
            log = log.with_reference_temperature(t).unwrap();
        }
        let noncold = |v: f64, t: f64, is_log: bool| {
            double_ion(v, t, is_log)
                - if is_log {
                    N * R * 2e-5 * t * t
                } else {
                    0.5 * N * R * 2e-5 * (v / 2.2).powf(1.3) * t * t
                }
        };
        compare("DoubleDebye", arithmetic, |v, t| {
            cold(v)
                - 1e-4
                    * derivative(
                        |u| noncold(u, t, false) - tr.map_or(0.0, |tr| noncold(u, tr, false)),
                        v,
                    )
        });
        compare("DoubleDebyeLog", log, |v, t| {
            cold(v)
                - 1e-4
                    * derivative(
                        |u| noncold(u, t, true) - tr.map_or(0.0, |tr| noncold(u, tr, true)),
                        v,
                    )
        });
    }
}
fn bose(theta: f64, t: f64, d: f64) -> f64 {
    theta * (d - 1.0) / (2.0 * d)
        + t * theta * d / ((t * d + theta) * ((1.0 + theta / (t * d)).powf(d) - 1.0))
}
fn einstein(theta: f64, t: f64) -> f64 {
    theta / 2.0 + theta / (theta / t).exp_m1()
}
#[test]
fn multi_oscillator_and_sokolova_alias_equation() {
    let params = SokolovaParameters {
        tr: TR,
        qe1o: 350.0,
        me1: 2.0,
        qe2o: 700.0,
        me2: 1.0,
        delta: 0.1,
        t: 2.0,
        a_0: 12.0,
        m: 1.2,
        g: 1.7,
        e_0: 20.0,
        beta: 0.3,
        qbo: 200.0,
        d: 4.0,
        mb: 2.0,
        qb1o: 500.0,
        d1: 3.0,
        mb1: 1.0,
    };
    let bulk = |v: f64| -v * derivative(cold, v);
    let gamma = |x: f64| {
        let v = V0 * x;
        let p = cold(v);
        let k = bulk(v);
        let kp = derivative(bulk, v) / derivative(cold, v);
        let t = 2.0 - 0.3 * x.cbrt();
        0.1 + (-3.0 * k + 2.0 * p * t + 9.0 * k * kp - 6.0 * t * k)
            / (6.0 * (3.0 * k - 2.0 * p * t))
    };
    compare(
        "MultiOscillator/Sokolova",
        MultiOscillatorGruneisen::new_with_atom_count(reference(), params, N).unwrap(),
        |v, t| {
            let x = v / V0;
            let scale = integrate(|u| gamma(u) / u, x, 1.0).exp();
            let modes = |t| {
                2.0 * bose(200.0 * scale, t, 4.0)
                    + bose(500.0 * scale, t, 3.0)
                    + 2.0 * einstein(350.0 * scale, t)
                    + einstein(700.0 * scale, t)
            };
            cold(v)
                + 1e-4
                    * (R * gamma(x) / v * (modes(t) - modes(TR))
                        + 3.0 * N * R / (2e6 * v)
                            * (12.0 * 1.2 * x.powf(1.2) + 20.0 * 1.7 * x.powf(1.7))
                            * (t * t - TR * TR))
        },
    );
}
#[test]
fn dorogokupets_oganov_four_modes_and_excess_derivatives() {
    let params = DorogokupetsOganov2007Parameters {
        tr: TR,
        theta_b1: 200.0,
        d_b1: 4.0,
        m_b1: 1.5,
        theta_b2: 500.0,
        d_b2: 3.0,
        m_b2: 1.5,
        theta_e1: 350.0,
        m_e1: 1.5,
        theta_e2: 700.0,
        m_e2: 1.5,
        gamma0: 1.6,
        gamma_inf: 0.5,
        beta: 2.0,
        anharmonic_a: 12.0,
        anharmonic_m: 1.2,
        electronic_e: 20.0,
        electronic_g: 1.7,
        defect_h: 6000.0,
        defect_s: 1.0,
    };
    assert!(
        DorogokupetsOganov2007::new(
            reference(),
            DorogokupetsOganov2007Parameters {
                beta: 0.0,
                ..params
            },
            N
        )
        .is_err()
    );
    compare(
        "DO2007",
        DorogokupetsOganov2007::new(reference(), params, N).unwrap(),
        |v, t| {
            let scale = |v: f64| {
                let x = v / V0;
                x.powf(-0.5) * (1.1 / 2.0 * (1.0 - x * x)).exp()
            };
            let p = |t: f64| {
                let x = v / V0;
                let s = scale(v);
                let gamma = 0.5 + 1.1 * x * x;
                let qh = 1e-4 * gamma / v
                    * R
                    * 1.5
                    * (bose(200.0 * s, t, 4.0)
                        + bose(500.0 * s, t, 3.0)
                        + einstein(350.0 * s, t)
                        + einstein(700.0 * s, t));
                let free = |u: f64| {
                    let x = u / V0;
                    let s = scale(u);
                    let anh = [200.0, 500.0, 350.0, 700.0]
                        .iter()
                        .map(|theta| {
                            let theta = theta * s;
                            let ni = 1.0 / (theta / t).exp_m1();
                            let e = theta * (0.5 + ni);
                            1.5 * R * 12e-6 * x.powf(1.2) / 6.0
                                * (e * e + 2.0 * theta * theta * ni * (ni + 1.0))
                        })
                        .sum::<f64>();
                    anh - 1.5 * N * R * 20e-6 * x.powf(1.7) * t * t
                        - 1.5 * N * R * t * (1.0 / x - 6000.0 / (t * x * x)).exp()
                };
                qh - 1e-4 * derivative(free, v)
            };
            cold(v) + p(t) - p(TR)
        },
    );
}
fn call(session: &mut Session, operation: &str, extra: Value) -> Value {
    let mut payload = json!({"index":0,"operation":operation});
    payload
        .as_object_mut()
        .unwrap()
        .extend(extra.as_object().unwrap().clone());
    let response = session.invoke(&Request {
        id: 1,
        action: "integration_phase".into(),
        payload,
        cached_buffers: vec![],
    });
    assert_eq!(response.result["ok"], true, "{}", response.result);
    response.result
}
fn editor(session: &mut Session) -> Value {
    session
        .invoke(&Request {
            id: 1,
            action: "integration_phase_editor".into(),
            payload: json!({"index":0}),
            cached_buffers: vec![],
        })
        .result["phaseEditor"]
        .clone()
}
#[test]
fn editor_optional_defaults_and_unavailable_model() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let mut session = Session::new(root.clone());
    call(
        &mut session,
        "load",
        json!({"path":root.join("desktop/tests/data/jcpds/mo.jcpds")}),
    );
    call(&mut session, "editor_record", json!({"action":"add"}));
    let data = editor(&mut session);
    assert!(
        !data["thermalOptions"]
            .as_array()
            .unwrap()
            .iter()
            .find(|o| o["value"] == "SoundVelocityDebyeHelmholtz")
            .unwrap()["error"]
            .as_str()
            .unwrap()
            .is_empty()
    );
    let rejected=session.invoke(&Request{id:1,action:"integration_phase".into(),payload:json!({"index":0,"operation":"editor_thermal_type","value":"SoundVelocityDebyeHelmholtz"}),cached_buffers:vec![]});
    assert_eq!(rejected.result["ok"], false);
    assert!(
        rejected.result["error"]
            .as_str()
            .unwrap()
            .contains("not implemented")
    );
    for model in ["DoubleDebyeHelmholtz", "DoubleDebyeLogMomentHelmholtz"] {
        call(&mut session, "editor_thermal_type", json!({"value":model}));
        let fields = editor(&mut session)["thermalFields"]
            .as_array()
            .unwrap()
            .clone();
        for f in fields {
            if f["required"] == false && f["default"].is_number() {
                call(
                    &mut session,
                    "editor_thermal_parameter",
                    json!({"parameter":f["key"],"value":Value::Null}),
                );
                assert_eq!(
                    editor(&mut session)["recordData"]["thermal"]["parameters"]
                        [f["key"].as_str().unwrap()],
                    f["default"]
                );
            }
        }
    }
}

#[test]
fn audited_revision_is_the_linked_dependency() {
    assert!(
        include_str!("../Cargo.toml").contains("3c79b1aedf28c348a49cc22d9f24d92895546283"),
        "Re-audit the displayed equations and unavailable-model metadata when updating PeriTheos"
    );
}

#[test]
fn legacy_adapter_inverts_selected_eos_and_keeps_its_special_branches() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let mut session = Session::new(root.clone());
    call(
        &mut session,
        "load",
        json!({"path":root.join("desktop/tests/data/jcpds/mo.jcpds")}),
    );
    call(&mut session, "editor_record", json!({"action":"add"}));
    call(&mut session, "editor_eos_type", json!({"value":"Vinet"}));
    call(
        &mut session,
        "editor_thermal_type",
        json!({"value":"alphakt"}),
    );
    for (key, value) in [
        ("alpha_t0", 3e-5),
        ("d_alpha_dt", 2e-8),
        ("dk0dt", -0.015),
        ("dk0pdt", -1e-4),
    ] {
        call(
            &mut session,
            "editor_parameter",
            json!({"parameter":key,"value":value}),
        );
    }
    let initial = editor(&mut session);
    let params = &initial["recordData"]["eos"]["parameters"];
    let v0 = params["V0"].as_f64().unwrap();
    let k0 = params["K0"].as_f64().unwrap();
    let kp = params["K0_prime"].as_f64().unwrap();
    let dt = 600.0 - 298.0;
    let alpha = 3e-5 + 2e-8 * dt;
    let k = k0 - 0.015 * dt;
    for pressure in [-1.0, 0.0, 10.0] {
        call(
            &mut session,
            "update",
            json!({"pressure":pressure,"temperature":600.0}),
        );
        let v = editor(&mut session)["lattice"]["v"].as_f64().unwrap();
        if pressure < 0.0 {
            close("legacy negative", v, v0 * (1.0 - pressure / k0), 1e-12);
        } else if pressure == 0.0 {
            close("legacy zero", v, v0 * (1.0 + alpha * dt), 1e-12);
        } else {
            let x = (v / v0).cbrt();
            let shifted_kp = kp - 1e-4 * dt;
            let p = 3.0 * k * (1.0 - x) / x.powi(2) * (1.5 * (shifted_kp - 1.0) * (1.0 - x)).exp();
            close("legacy Vinet", p, pressure - alpha * k * dt, 1e-8);
        }
    }
}

#[test]
fn eosmat_cell_to_formula_molar_volume_and_override() {
    let record = json!({"identifier":"audit","reference":"Audit fixture",
        "eos":{"type":"BM3","parameters":{"V0":40.0,"K0":K0,"K0_prime":KP}},
        "thermal":{"type":"MieGruneisenDebye","parameters":{"Tr":TR,"theta0":500.0,"gamma0":1.6,"q":1.2,"n":N}}});
    let mut document = json!({"format_version":2,"name":"Audit fixture","formula":"MgO","formula_units_per_cell":4,"eos_records":[record]});
    for scale in [0.0602214076 / 4.0, 0.03] {
        if scale == 0.03 {
            document["eos_records"][0]["volume"] = json!({"public_to_model_scale":scale});
        }
        let material = peritheos::eosmat::material_from_value(document.clone()).unwrap();
        let model = &material.eos_records[0];
        let v: f64 = 36.0;
        let t = 900.0;
        let x = v / 40.0;
        let theta = 500.0 * (-1.6 / 1.2 * (x.powf(1.2) - 1.0)).exp();
        let expected = bm3_at(v, 40.0, K0, KP)
            + 1e-4 * 1.6 * x.powf(1.2) / (v * scale)
                * 3.0
                * N
                * R
                * (t * d3(theta / t) - TR * d3(theta / TR));
        close(
            "EOSMAT normalization",
            model.pressure(v, t).unwrap(),
            expected,
            1e-8,
        );
        close(
            "public reference volume",
            model.reference_volume(),
            40.0,
            1e-12,
        );
    }
}

#[test]
fn double_debye_coincident_temperature_weight_branch() {
    let a = DoubleDebyeHelmholtz::new(
        reference(),
        V0,
        500.0,
        0.1,
        0.8,
        500.0,
        0.15,
        0.9,
        500.0,
        0.12,
        0.85,
        N,
        0.0,
        1.0,
        0.0,
        0.0,
    )
    .unwrap();
    let l = DoubleDebyeLogMomentHelmholtz::new(
        reference(),
        V0,
        500.0,
        0.1,
        0.8,
        500.0,
        0.15,
        0.9,
        500.0,
        0.12,
        0.85,
        N,
        0.0,
        0.0,
    )
    .unwrap();
    let expected =
        ((0.15 * V0 + 0.9) - (0.12 * V0 + 0.85)) / ((0.15 * V0 + 0.9) - (0.1 * V0 + 0.8));
    close(
        "coincident arithmetic",
        a.double_debye_weights(V0).unwrap().0,
        expected,
        1e-12,
    );
    close(
        "coincident logarithmic",
        l.double_debye_weights(V0).unwrap().0,
        expected,
        1e-12,
    );
    let equal = DoubleDebyeHelmholtz::new(
        reference(),
        V0,
        500.0,
        0.1,
        0.8,
        500.0,
        0.1,
        0.8,
        500.0,
        0.1,
        0.8,
        N,
        0.0,
        1.0,
        0.0,
        0.0,
    )
    .unwrap();
    close(
        "coincident equal gamma",
        equal.double_debye_weights(V0).unwrap().0,
        0.5,
        1e-12,
    );
}

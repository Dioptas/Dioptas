//! Uniform-scatterer transmission averages over illuminated sample volumes.
//! Rays are unit 3D directions: their intersection parameter is already a 3D
//! path length. A capillary ray crosses one wall on entry and one on exit.
use crate::{control::Control, geometry::Geometry};
use rayon::prelude::*;
use serde_json::{Value, json};
use std::{f64::consts::PI, sync::Arc};

const QUADRATURE_TOL: f64 = 2e-5;
const INTERPOLATION_TOL: f64 = 2e-5;

pub(crate) fn provenance() -> Value {
    json!({"model":"uniform-footprint-rays-v1","quadrature_relative_tolerance":QUADRATURE_TOL,"interpolation_relative_tolerance":INTERPOLATION_TOL,
        "cylinder_beam":"uniform strip","sphere_beam":"uniform circular footprint","container_wall":"one crossing per incident/outgoing ray"})
}

#[derive(Clone)]
struct CachedMap {
    kind: String,
    parameters: Value,
    geometry: Geometry,
    shape: [usize; 2],
    values: Arc<Vec<f64>>,
}
#[derive(Clone, Default)]
pub(crate) struct Maps {
    entries: Vec<CachedMap>,
    builds: usize,
    hits: usize,
}
impl Maps {
    pub fn bytes(&self) -> usize {
        self.entries.iter().map(|e| e.values.len() * 8).sum()
    }
    pub fn diagnostics(&self) -> Value {
        json!({"sampleCorrectionBuilds":self.builds,"sampleCorrectionHits":self.hits})
    }
    pub fn lookup(
        &mut self,
        kind: &str,
        parameters: &Value,
        geometry: &Geometry,
        shape: [usize; 2],
    ) -> Option<Arc<Vec<f64>>> {
        let e = self.entries.iter().find(|e| {
            e.kind == kind
                && e.parameters == *parameters
                && e.geometry == *geometry
                && e.shape == shape
        })?;
        self.hits += 1;
        Some(e.values.clone())
    }
    pub fn store(
        &mut self,
        kind: &str,
        parameters: Value,
        geometry: Geometry,
        shape: [usize; 2],
        values: Vec<f64>,
    ) -> Arc<Vec<f64>> {
        let values = Arc::new(values);
        self.entries.retain(|e| e.kind != kind);
        self.entries.push(CachedMap {
            kind: kind.into(),
            parameters,
            geometry,
            shape,
            values: values.clone(),
        });
        self.builds += 1;
        values
    }
}

#[derive(Clone, Copy)]
struct Axis {
    low: f64,
    high: f64,
    n: usize,
}
impl Axis {
    fn new(low: f64, high: f64, n: usize) -> Self {
        Self {
            low,
            high,
            n: if high - low <= 1e-13 { 1 } else { n },
        }
    }
    fn at(self, i: usize) -> f64 {
        if self.n == 1 {
            self.low
        } else {
            self.low + (self.high - self.low) * i as f64 / (self.n - 1) as f64
        }
    }
    fn position(self, x: f64) -> (usize, usize, f64) {
        if self.n == 1 {
            return (0, 0, 0.);
        }
        let v = ((x - self.low) / (self.high - self.low) * (self.n - 1) as f64)
            .clamp(0., (self.n - 1) as f64);
        let lo = (v as usize).min(self.n - 2);
        (lo, lo + 1, v - lo as f64)
    }
}
struct Table {
    x: Axis,
    y: Axis,
    values: Vec<f64>,
}
impl Table {
    fn value(&self, x: f64, y: f64) -> f64 {
        let (x0, x1, fx) = self.x.position(x);
        let (y0, y1, fy) = self.y.position(y);
        let a = self.values[x0 * self.y.n + y0] * (1. - fy) + self.values[x0 * self.y.n + y1] * fy;
        let b = self.values[x1 * self.y.n + y0] * (1. - fy) + self.values[x1 * self.y.n + y1] * fy;
        a * (1. - fx) + b * fx
    }
}

#[derive(Clone, Copy)]
struct Point {
    x: f64,
    y: f64,
    z: f64,
    incident: f64,
    wall: f64,
    weight: f64,
}
struct Model {
    points: Vec<Point>,
    radius: f64,
    mu: f64,
    wall_delta: f64,
    wall_mu: f64,
    sphere: bool,
}
impl Model {
    // x,y coordinates are dimensionless angular arguments: sphere (2theta,0),
    // cylinder (angle in the cross-section plane, inverse projected norm).
    // Inverse norm makes the outgoing optical depth linear in the second axis,
    // avoiding a poorly resolved 1/norm singularity near parallel rays.
    fn value(&self, x: f64, y: f64) -> f64 {
        let (s, c) = x.sin_cos();
        let projection = if self.sphere { 1. } else { 1. / y };
        let mut sum = 0.;
        for p in &self.points {
            let b = if self.sphere {
                p.x * c + p.y * s
            } else {
                projection * (p.x * c + p.y * s)
            };
            let a = projection * projection;
            let gap = (self.radius * self.radius - p.x * p.x - p.y * p.y - p.z * p.z).max(0.);
            let root = (b * b + a * gap).sqrt();
            let outgoing = if b >= 0. {
                gap / (root + b)
            } else {
                (root - b) / a
            };
            let wall = if self.wall_mu > 0. && self.wall_delta > 0. {
                self.wall_delta / ((b * b + a * (gap + self.wall_delta)).sqrt() + root)
            } else {
                0.
            };
            sum += p.weight
                * (-self.mu * (p.incident + outgoing) - self.wall_mu * (p.wall + wall)).exp();
        }
        sum
    }
}

/// Gauss-Legendre nodes/weights on [low,high], computed independently of Python.
fn gauss(n: usize, low: f64, high: f64) -> Vec<(f64, f64)> {
    let mut nodes = vec![(0., 0.); n];
    for i in 0..n.div_ceil(2) {
        let mut z = (PI * (i as f64 + 0.75) / (n as f64 + 0.5)).cos();
        let derivative = loop {
            let (mut p0, mut p1) = (1., z);
            for j in 2..=n {
                let p = ((2 * j - 1) as f64 * z * p1 - (j - 1) as f64 * p0) / j as f64;
                p0 = p1;
                p1 = p;
            }
            let derivative = n as f64 * (z * p1 - p0) / (z * z - 1.);
            let next = z - p1 / derivative;
            if (next - z).abs() < 2e-15 {
                z = next;
                break derivative;
            }
            z = next;
        };
        let weight = (high - low) / ((1. - z * z) * derivative * derivative);
        nodes[i] = ((low + high) / 2. - (high - low) * z / 2., weight);
        nodes[n - 1 - i] = ((low + high) / 2. + (high - low) * z / 2., weight);
    }
    nodes
}

fn model(kind: &str, p: &Value, order: usize, incident_norm: f64) -> Model {
    let n = |k: &str| p[k].as_f64().unwrap();
    let radius = n("radius");
    let mu = n("absorption_coefficient");
    let beam = n("beam_width");
    let sphere = kind == "sphere";
    let wall_mu = if sphere {
        0.
    } else {
        n("container_absorption_coefficient")
    };
    let wall = if sphere { 0. } else { n("wall_thickness") };
    let wall_delta = wall * (2. * radius + wall);
    let gx = gauss(order, -1., 1.);
    let mut points = vec![];
    if beam == 0. {
        for &(x, w) in &gx {
            points.push(Point {
                x: radius * x,
                y: 0.,
                z: 0.,
                incident: radius * (x + 1.) / incident_norm,
                wall: wall / incident_norm,
                weight: w,
            });
        }
    } else {
        let bound = (beam / (2. * radius)).min(1.).asin();
        let transverse = gauss(order, if sphere { 0. } else { -bound }, bound);
        for (alpha, wa) in transverse {
            let (s, c) = alpha.sin_cos();
            let r = radius * s;
            let half = radius * c;
            for &(x, wx) in &gx {
                let weight = wa * wx * c * c * if sphere { s } else { 1. };
                if sphere {
                    // Uniform cylindrical footprint needs the full azimuthal
                    // average. Restricting scattering points to (x,rho,0) is biased.
                    for j in 0..2 * order {
                        let (sp, cp) = (2. * PI * j as f64 / (2 * order) as f64).sin_cos();
                        points.push(Point {
                            x: half * x,
                            y: r * cp,
                            z: r * sp,
                            incident: half * (x + 1.),
                            wall: 0.,
                            weight,
                        });
                    }
                } else {
                    let wall_path = if wall > 0. {
                        wall_delta / ((half * half + wall_delta).sqrt() + half) / incident_norm
                    } else {
                        0.
                    };
                    points.push(Point {
                        x: half * x,
                        y: r,
                        z: 0.,
                        incident: half * (x + 1.) / incident_norm,
                        wall: wall_path,
                        weight,
                    });
                }
            }
        }
    }
    let total = points.iter().map(|p| p.weight).sum::<f64>();
    for p in &mut points {
        p.weight /= total;
    }
    Model {
        points,
        radius,
        mu,
        wall_delta,
        wall_mu,
        sphere,
    }
}

fn relative(a: f64, b: f64) -> f64 {
    (a - b).abs() / a.abs().max(b.abs()).max(1e-300)
}
fn converged_model(
    kind: &str,
    p: &Value,
    incident: f64,
    x: Axis,
    y: Axis,
    control: &Control,
) -> Result<Model, String> {
    let probes: Vec<_> = (0..9)
        .flat_map(|i| {
            (0..if y.n == 1 { 1 } else { 9 }).map(move |j| {
                (
                    x.low + (x.high - x.low) * i as f64 / 8.,
                    if y.n == 1 {
                        y.low
                    } else {
                        y.low + (y.high - y.low) * j as f64 / 8.
                    },
                )
            })
        })
        .collect();
    let mut previous: Option<Vec<f64>> = None;
    for order in [12, 24, 48, 80] {
        control.check()?;
        let candidate = model(kind, p, order, incident);
        let values: Result<Vec<_>, String> = probes
            .par_iter()
            .map(|&(x, y)| {
                control.check()?;
                Ok(candidate.value(x, y))
            })
            .collect();
        let values = values?;
        if let Some(old) = previous
            && values
                .iter()
                .zip(old)
                .all(|(&a, b)| relative(a, b) <= QUADRATURE_TOL)
        {
            return Ok(candidate);
        }
        previous = Some(values);
    }
    Err(format!(
        "{kind} absorption did not converge at these parameters; reduce optical depth or change the sample model."
    ))
}
fn table(model: &Model, x: Axis, y: Axis, control: &Control) -> Result<Table, String> {
    let mut size = 33;
    loop {
        control.check()?;
        let x = Axis::new(x.low, x.high, size);
        let y = Axis::new(y.low, y.high, if model.sphere { 1 } else { size });
        control.publish(json!({"running":true,"current":0,"total":x.n*y.n,"label":"Calculating sample absorption"}));
        let values: Result<Vec<_>, String> = (0..x.n * y.n)
            .into_par_iter()
            .map(|i| {
                control.check()?;
                Ok(model.value(x.at(i / y.n), y.at(i % y.n)))
            })
            .collect();
        let result = Table {
            x,
            y,
            values: values?,
        };
        // Check every cell midpoint, not just a few favorable detector pixels.
        let rows = x.n.saturating_sub(1).max(1);
        let cols = y.n.saturating_sub(1).max(1);
        let errors: Result<Vec<_>, String> = (0..rows * cols)
            .into_par_iter()
            .map(|i| {
                control.check()?;
                let a = (x.at(i / cols) + x.at((i / cols + 1).min(x.n - 1))) / 2.;
                let b = (y.at(i % cols) + y.at((i % cols + 1).min(y.n - 1))) / 2.;
                Ok(relative(model.value(a, b), result.value(a, b)))
            })
            .collect();
        if errors?.iter().all(|e| *e <= INTERPOLATION_TOL) {
            return Ok(result);
        }
        if size >= if model.sphere { 1025 } else { 257 } {
            return Err("Sample absorption interpolation did not converge; these parameters are outside the qualified numerical range.".into());
        }
        size = 2 * size - 1;
    }
}

pub(crate) fn build(
    kind: &str,
    p: &Value,
    tth: &[f64],
    azi: &[f64],
    control: &Control,
) -> Result<Vec<f64>, String> {
    crate::worker_pool::install(|| build_in_pool(kind, p, tth, azi, control))
}
fn build_in_pool(
    kind: &str,
    p: &Value,
    tth: &[f64],
    azi: &[f64],
    control: &Control,
) -> Result<Vec<f64>, String> {
    control.check()?;
    if tth.is_empty() || tth.len() != azi.len() || tth.iter().chain(azi).any(|v| !v.is_finite()) {
        return Err("Sample absorption requires matching, finite detector angles.".into());
    }
    let n = |key: &str| p[key].as_f64().unwrap();
    let radius = n("radius");
    let mu = n("absorption_coefficient");
    if radius == 0.
        || (mu == 0.
            && (kind == "sphere"
                || n("container_absorption_coefficient") == 0.
                || n("wall_thickness") == 0.))
    {
        return Ok(vec![1.; tth.len()]);
    }
    control.check()?;
    let (incident, coords) = if kind == "sphere" {
        (1., tth.iter().map(|&t| (t, 0.)).collect::<Vec<_>>())
    } else {
        let tilt = n("axis_tilt").to_radians();
        let rot = n("axis_rotation").to_radians();
        let axis = [tilt.sin() * rot.cos(), tilt.sin() * rot.sin(), tilt.cos()];
        let incident = (1. - axis[0] * axis[0]).max(0.).sqrt();
        if incident < 1e-8 {
            return Err("An infinite cylinder parallel to the incident beam has no finite transmission model; change its axis or sample model.".into());
        }
        let u = [
            (1. - axis[0] * axis[0]) / incident,
            -axis[0] * axis[1] / incident,
            -axis[0] * axis[2] / incident,
        ];
        let v = [
            axis[1] * u[2] - axis[2] * u[1],
            axis[2] * u[0] - axis[0] * u[2],
            axis[0] * u[1] - axis[1] * u[0],
        ];
        let coords: Result<Vec<_>, String> = tth.iter().zip(azi).map(|(&t, &a)| {
            let d = [t.cos(), t.sin() * a.cos(), t.sin() * a.sin()];
            let qu = u.iter().zip(d).map(|(u, d)| u * d).sum::<f64>();
            let qv = v.iter().zip(d).map(|(v, d)| v * d).sum::<f64>();
            let norm = qu.hypot(qv);
            if norm < 1e-8 {
                return Err("A detector ray parallel to the infinite cylinder axis cannot be corrected; change the geometry or sample model.".into());
            }
            Ok((qv.abs().atan2(qu), 1. / norm))
        }).collect();
        (incident, coords?)
    };
    let mut bounds = [
        f64::INFINITY,
        f64::NEG_INFINITY,
        f64::INFINITY,
        f64::NEG_INFINITY,
    ];
    for &(x, y) in &coords {
        bounds[0] = bounds[0].min(x);
        bounds[1] = bounds[1].max(x);
        bounds[2] = bounds[2].min(y);
        bounds[3] = bounds[3].max(y);
    }
    let x = Axis::new(bounds[0], bounds[1], 33);
    let y = Axis::new(bounds[2], bounds[3], 33);
    control.publish(json!({"running":true,"current":0,"total":4,"label":"Checking sample absorption convergence"}));
    let model = converged_model(kind, p, incident, x, y, control)?;
    let table = table(&model, x, y, control)?;
    let factors: Vec<_> = coords.into_iter().map(|(x, y)| table.value(x, y)).collect();
    if factors
        .iter()
        .any(|f| !f.is_finite() || *f <= 0. || *f > 1. + 1e-12)
    {
        return Err("Sample transmission is zero or nonfinite; its absorption correction is not recoverable.".into());
    }
    control.check()?;
    Ok(factors)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn p() -> Value {
        json!({"radius":0.2,"absorption_coefficient":1.3,"beam_width":0.,"axis_tilt":0.,"axis_rotation":0.,"wall_thickness":0.,"container_absorption_coefficient":0.})
    }
    #[test]
    fn sphere_pencil_forward_and_backscatter_match_closed_integrals() {
        let p = p();
        let r = build("sphere", &p, &[0., PI], &[0., 0.], &Control::default()).unwrap();
        let mr = 0.26f64;
        assert!((r[0] - (-2. * mr).exp()).abs() < 1e-12);
        assert!((r[1] - (-(-4. * mr).exp_m1() / (4. * mr))).abs() < 1e-12);
    }
    #[test]
    fn tilted_cylinder_forward_path_and_single_wall_crossings_are_exact() {
        let mut p = p();
        p["axis_tilt"] = json!(35.);
        p["wall_thickness"] = json!(0.03);
        p["container_absorption_coefficient"] = json!(2.1);
        let incident = 35f64.to_radians().cos();
        let r = build("cylinder", &p, &[0.], &[0.], &Control::default()).unwrap();
        assert!((r[0] - (-2. * (0.26 + 2.1 * 0.03) / incident).exp()).abs() < 1e-12);
        p["absorption_coefficient"] = json!(0.);
        let r = build("cylinder", &p, &[0.], &[0.], &Control::default()).unwrap();
        assert!((r[0] - (-2. * 2.1 * 0.03 / incident).exp()).abs() < 1e-12);
    }
    #[test]
    fn full_sphere_forward_volume_average_matches_closed_integral() {
        let mut p = p();
        p["beam_width"] = json!(1.);
        let r = build("sphere", &p, &[0.], &[0.], &Control::default()).unwrap();
        let k = 0.52f64;
        let expected = 3. * (2. - (-k).exp() * (k * k + 2. * k + 2.)) / k.powi(3);
        assert!((r[0] - expected).abs() < 1e-12);
    }
    #[test]
    fn cancellation_and_undefined_infinite_cylinder_fail_explicitly() {
        let mut p = p();
        p["axis_tilt"] = json!(90.);
        assert!(build("cylinder", &p, &[0.1], &[0.], &Control::default()).is_err());
        let c = Control::default();
        c.cancel();
        assert!(
            build("sphere", &p, &[0.1], &[0.], &c)
                .unwrap_err()
                .contains("cancelled")
        );
    }
}

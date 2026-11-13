//! Qt/React geometric masks. Operations run on detached user masks.
use super::*;
// Match skimage's two-ray even/odd boundary rule, including its vertex
// tolerance. A one-ray scanline fill differs on almost-integer arc boundaries.
// Reference: scikit-image/skimage/_shared/geometry.pyx (BSD-3-Clause).
fn polygon(
    mask: &mut [u8],
    shape: [usize; 2],
    vertices: &[[f64; 2]],
    value: u8,
    control: &Control,
) -> Result<(), String> {
    let [h, w] = shape;
    let bounds = |axis: usize, limit: usize| {
        let low = vertices
            .iter()
            .map(|p| p[axis])
            .fold(f64::INFINITY, f64::min)
            .floor()
            .max(0.) as usize;
        let high = vertices
            .iter()
            .map(|p| p[axis])
            .fold(f64::NEG_INFINITY, f64::max)
            .ceil()
            .min((limit - 1) as f64);
        (low, high)
    };
    let (r0, r1) = bounds(1, h);
    let (c0, c1) = bounds(0, w);
    if r1 < r0 as f64 || c1 < c0 as f64 {
        return Ok(());
    }
    for r in r0..=r1 as usize {
        control.check()?;
        for c in c0..=c1 as usize {
            if c.is_multiple_of(256) {
                control.check()?;
            }
            let mut previous = vertices[vertices.len() - 1];
            let mut left = 0;
            let mut right = 0;
            let mut vertex = false;
            for &point in vertices {
                let [x, y] = [point[0] - c as f64, point[1] - r as f64];
                let [px, py] = [previous[0] - c as f64, previous[1] - r as f64];
                if x.abs() < 1e-12 && y.abs() < 1e-12 {
                    vertex = true;
                    break;
                }
                if (y > 0.) != (py > 0.) && (x * py - px * y) / (py - y) > 0. {
                    right += 1;
                }
                if (y < 0.) != (py < 0.) && (x * py - px * y) / (py - y) < 0. {
                    left += 1;
                }
                previous = point;
            }
            if vertex || right % 2 != left % 2 || right % 2 == 1 {
                mask[r * w + c] = value;
            }
        }
    }
    Ok(())
}
fn arc(p: &[[f64; 2]]) -> Result<Vec<[f64; 2]>, String> {
    let [[xa, ya], [xb, yb], [xc, yc], edge] = [p[0], p[1], p[2], p[3]];
    let denom = 2. * (xa * (yb - yc) + xb * (yc - ya) + xc * (ya - yb));
    if denom.abs() < 1e-12 {
        return Err("Arc points must be distinct and not collinear.".into());
    }
    let (a, b, c) = (xa * xa + ya * ya, xb * xb + yb * yb, xc * xc + yc * yc);
    let center = [
        (a * (yb - yc) + b * (yc - ya) + c * (ya - yb)) / denom,
        (a * (xc - xb) + b * (xa - xc) + c * (xb - xa)) / denom,
    ];
    let radius = (xa - center[0]).hypot(ya - center[1]);
    let angle = |x: f64, y: f64| (y - center[1]).atan2(x - center[0]);
    let (mut start, middle, mut end) = (angle(xa, ya), angle(xb, yb), angle(xc, yc));
    if (end < start && start < middle) || (middle < end && end < start) {
        end += std::f64::consts::TAU;
    } else if (start < middle && middle < end) || (end < middle && middle < start) {
    } else if (start < end && end < middle) || (middle < start && start < end) {
        start += std::f64::consts::TAU;
    } else {
        return Err("Choose three distinct points along the arc.".into());
    }
    let width = (radius - (edge[0] - center[0]).hypot(edge[1] - center[1])).abs();
    let points = |r: f64| {
        (0..50)
            .map(|i| {
                let a = if i == 49 {
                    end
                } else {
                    start + (end - start) * (i as f64 / 49.)
                };
                [center[0] + r * a.cos(), center[1] + r * a.sin()]
            })
            .collect::<Vec<_>>()
    };
    let mut result = points(radius + width);
    result.extend(points(radius - width).into_iter().rev());
    Ok(result)
}
impl Session {
    pub(super) fn geometric_mask(&mut self, args: &Value, defer: bool) -> Result<Reply, String> {
        self.require_image()?;
        check_keys(
            args,
            &[
                "operation",
                "points",
                "erase",
                "threshold",
                "unit",
                "lower",
                "upper",
                "outside",
                "defer_integration",
            ],
        )?;
        let operation = args["operation"]
            .as_str()
            .ok_or("Choose a mask operation.")?;
        let shape = self.image.as_ref().unwrap().shape;
        let [h, w] = shape;
        let erase = args
            .get("erase")
            .map_or(Ok(false), |v| boolean(v, "Unmask"))?;
        let value = u8::from(!erase);
        let mut vertices = vec![];
        if ["rectangle", "circle", "polygon", "arc"].contains(&operation) {
            let points = args["points"]
                .as_array()
                .filter(|a| a.len() >= 2 && a.len() <= 10000)
                .ok_or("Select the shape's points on the detector.")?;
            let count = match operation {
                "rectangle" | "circle" => 2,
                "arc" => 4,
                _ => points.len(),
            };
            if points.len() != count || (operation == "polygon" && points.len() < 3) {
                return Err("Incorrect number of points for this selection.".into());
            }
            for p in points {
                let p = p
                    .as_array()
                    .filter(|a| a.len() == 2)
                    .ok_or("Each point needs x and y coordinates.")?;
                vertices.push([
                    finite(&p[0], "x", 0., w as f64 - 1e-6)?,
                    finite(&p[1], "y", 0., h as f64 - 1e-6)?,
                ]);
            }
        }
        let mut mask = self.mask.as_ref().clone();
        self.control
            .publish(json!({"running":true,"current":0,"total":h,"label":"Applying mask"}));
        match operation {
            "rectangle" => {
                let [[x0, y0], [x1, y1]] = [vertices[0], vertices[1]];
                for r in (y0.min(y1).round_ties_even() as usize)
                    ..(y0.max(y1).round_ties_even() as usize).min(h)
                {
                    self.control.check()?;
                    mask[r * w + x0.min(x1).round_ties_even() as usize
                        ..r * w + (x0.max(x1).round_ties_even() as usize).min(w)]
                        .fill(value);
                }
            }
            "circle" => {
                let [cx, cy] = vertices[0].map(|v| v as usize);
                let radius = (vertices[1][0] - vertices[0][0])
                    .hypot(vertices[1][1] - vertices[0][1]) as usize;
                if radius > 0 {
                    for r in cy.saturating_sub(radius)..=(cy + radius).min(h - 1) {
                        self.control.check()?;
                        for c in cx.saturating_sub(radius)..=(cx + radius).min(w - 1) {
                            if ((r as f64 - cy as f64) / radius as f64).powi(2)
                                + ((c as f64 - cx as f64) / radius as f64).powi(2)
                                < 1.
                            {
                                mask[r * w + c] = value;
                            }
                        }
                    }
                }
            }
            "polygon" => polygon(&mut mask, shape, &vertices, value, &self.control)?,
            "arc" => polygon(&mut mask, shape, &arc(&vertices)?, value, &self.control)?,
            "above" | "below" => {
                let t = finite(&args["threshold"], "Threshold", -1e30, 1e30)?;
                for (i, v) in self.scientific_values().iter().enumerate() {
                    if i % w == 0 {
                        self.control.check()?;
                    }
                    if (operation == "above" && *v > t) || (operation == "below" && *v < t) {
                        mask[i] = value;
                    }
                }
            }
            "range" => self.mask_radial_range(&mut mask, args, value)?,
            "grow" | "shrink" => {
                let combine = |a: u8, b: u8| if operation == "grow" { a | b } else { a & b };
                // Each assignment sees the preceding pass, as in MaskModel.
                for r in (1..h).rev() {
                    self.control.check()?;
                    for c in 0..w {
                        mask[r * w + c] = combine(mask[r * w + c], mask[(r - 1) * w + c]);
                    }
                }
                for r in 0..h - 1 {
                    self.control.check()?;
                    for c in 0..w {
                        mask[r * w + c] = combine(mask[r * w + c], mask[(r + 1) * w + c]);
                    }
                }
                for r in 0..h {
                    self.control.check()?;
                    for c in (1..w).rev() {
                        mask[r * w + c] = combine(mask[r * w + c], mask[r * w + c - 1]);
                    }
                }
                for r in 0..h {
                    self.control.check()?;
                    for c in 0..w - 1 {
                        mask[r * w + c] = combine(mask[r * w + c], mask[r * w + c + 1]);
                    }
                }
            }
            "invert" => {
                for (i, v) in mask.iter_mut().enumerate() {
                    if i % w == 0 {
                        self.control.check()?;
                    }
                    *v = 1 - *v;
                }
            }
            "clear" => mask.fill(0),
            "cosmic" => self.add_lacosmic(&mut mask, shape)?,
            _ => return Err("Unknown mask operation.".into()),
        }
        self.control.check()?;
        self.replace_mask_mode(mask, !erase);
        self.settings.use_mask = true;
        self.calculate(defer)?;
        self.control.check()?;
        self.revision += 1;
        Ok(self.snapshot(false))
    }
    fn add_lacosmic(&self, mask: &mut [u8], shape: [usize; 2]) -> Result<(), String> {
        let detected = crate::lacosmic::detect(&self.scientific_values(), shape, &self.control)?;
        // Qt always adds these hits, including when the drawing mode is Unmask.
        for (pixel, hit) in mask.iter_mut().zip(detected) {
            *pixel |= hit;
        }
        Ok(())
    }
    fn mask_radial_range(&self, mask: &mut [u8], args: &Value, value: u8) -> Result<(), String> {
        if !self.settings.calibrated {
            return Err("Calibrate the detector before masking a radial range.".into());
        }
        let unit = args
            .get("unit")
            .and_then(Value::as_str)
            .unwrap_or("2th_deg");
        if !["2th_deg", "q_A^-1", "d_A"].contains(&unit) {
            return Err("Choose a supported radial unit.".into());
        }
        let bound = |key: &str| {
            args.get(key)
                .filter(|v| !v.is_null())
                .map(|v| finite(v, "Range bound", 0., f64::MAX))
                .transpose()
        };
        let (lower, upper) = (bound("lower")?, bound("upper")?);
        if (lower.is_none() && upper.is_none()) || lower.zip(upper).is_some_and(|(a, b)| a > b) {
            return Err("Enter ordered, non-negative range bounds.".into());
        }
        let outside = args
            .get("outside")
            .map_or(Ok(false), |v| boolean(v, "Outside"))?;
        #[cfg(not(feature = "dioptrin"))]
        {
            let _ = (mask, value, unit, outside);
            Err("Radial masks require the optional Dioptrin geometry engine.".into())
        }
        #[cfg(feature = "dioptrin")]
        {
            let [h, w] = self.image.as_ref().unwrap().shape;
            let geometry = self.native_geometry([h, w])?;
            let tth = geometry.calc_tth_all();
            for (i, t) in tth.iter().enumerate() {
                if i % w == 0 {
                    self.control.check()?;
                }
                let r = match unit {
                    "q_A^-1" => {
                        4. * std::f64::consts::PI * (t / 2.).sin()
                            / (self.settings.geometry.wavelength * 1e10)
                    }
                    "d_A" => self.settings.geometry.wavelength * 1e10 / (2. * (t / 2.).sin()),
                    _ => t.to_degrees(),
                };
                let selected = lower.is_none_or(|a| r >= a) && upper.is_none_or(|b| r <= b);
                if !r.is_nan() && (selected != outside) {
                    mask[i] = value;
                }
            }
            Ok(())
        }
    }
}

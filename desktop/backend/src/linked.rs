//! Shared, subpixel detector/cake/pattern click inspection.
use super::*;
#[derive(Clone)]
pub(super) struct Inspection {
    geometry: Geometry,
    generation: u64,
    value: Arc<Value>,
}
pub(super) fn convert(value: f64, from: &str, to: &str, wavelength: f64) -> f64 {
    crate::pattern::convert_coordinate(value, from, to, wavelength)
}

impl Session {
    pub(super) fn linked_snapshot(&self) -> Value {
        let Some(i) = &self.inspection else {
            return Value::Null;
        };
        if !self.settings.calibrated
            || i.geometry != self.settings.geometry
            || i.generation != self.image_generation
        {
            return Value::Null;
        }
        let mut value = i.value.as_ref().clone();
        value["radial"] = json!(convert(
            value["twoTheta"].as_f64().unwrap(),
            "2th_deg",
            &self.settings.unit,
            self.settings.geometry.wavelength
        ));
        value
    }
    pub(super) fn validation_position(&mut self, args: &Value) -> Result<Reply, String> {
        #[cfg(not(feature = "dioptrin"))]
        {
            let _ = args;
            Err("Linked geometry inspection requires the optional Dioptrin engine.".into())
        }
        #[cfg(feature = "dioptrin")]
        {
            check_keys(args, &["source", "x", "y", "azimuth"])?;
            self.require_image()?;
            if !self.settings.calibrated {
                return Err("Calibrate an image before inspecting a linked position.".into());
            }
            let source = args["source"].as_str().ok_or("Choose a validation view.")?;
            let x = finite(&args["x"], "Position", -1e12, 1e12)?;
            let image = self.image.as_ref().unwrap();
            let native = self.native_geometry(image.shape)?;
            let previous = self.linked_snapshot();
            let mut azimuth = previous["azimuth"].as_f64();
            let mut image_point = Value::Null;
            let tth = match source {
                "image" => {
                    let y = finite(&args["y"], "y", 0.0, image.shape[0] as f64 - 1e-9)?;
                    finite(&args["x"], "x", 0.0, image.shape[1] as f64 - 1e-9)?;
                    let (t, a) = native.calc_tth_and_azimuth(&[y], &[x]);
                    azimuth = Some(a[0].to_degrees());
                    image_point = json!({"x":x,"y":y});
                    t[0].to_degrees()
                }
                "cake" => {
                    if let Some(a) = args.get("azimuth") {
                        azimuth = Some(
                            (finite(a, "Azimuth", -1e12, 1e12)? + 180.0).rem_euclid(360.0) - 180.0,
                        );
                    }
                    x
                }
                "pattern" => convert(
                    x,
                    &self.settings.unit,
                    "2th_deg",
                    self.settings.geometry.wavelength,
                ),
                _ => return Err("Unknown validation view.".into()),
            };
            finite(&json!(tth), "2θ position", 0.0, 180.0)?;
            let contours = crate::peak_search::full_contours(
                &native.calc_tth_all(),
                image.shape,
                tth.to_radians(),
            );
            if let Some(azimuth) = azimuth
                && image_point.is_null()
            {
                let points: Vec<[f64; 2]> = contours
                    .as_array()
                    .unwrap()
                    .iter()
                    .flat_map(|p| {
                        p["points"]
                            .as_array()
                            .unwrap()
                            .iter()
                            .map(|v| [v[0].as_f64().unwrap(), v[1].as_f64().unwrap()])
                    })
                    .collect();
                if !points.is_empty() {
                    let rows: Vec<_> = points.iter().map(|p| p[1]).collect();
                    let cols: Vec<_> = points.iter().map(|p| p[0]).collect();
                    let angles = native.calc_azimuth(&rows, &cols);
                    let closest = angles
                        .iter()
                        .enumerate()
                        .map(|(i, &a)| {
                            (
                                i,
                                ((a - azimuth.to_radians() + std::f64::consts::PI)
                                    .rem_euclid(std::f64::consts::TAU)
                                    - std::f64::consts::PI)
                                    .abs(),
                            )
                        })
                        .min_by(|a, b| a.1.total_cmp(&b.1))
                        .unwrap();
                    if closest.1 < 1f64.to_radians() {
                        image_point = json!({"x":points[closest.0][0],"y":points[closest.0][1]});
                    }
                }
            }
            let linked = json!({"twoTheta":tth,"radial":convert(tth,"2th_deg",&self.settings.unit,self.settings.geometry.wavelength),"contours":contours,"azimuth":azimuth,"imagePoint":image_point});
            self.inspection = Some(Inspection {
                geometry: self.settings.geometry.clone(),
                generation: self.image_generation,
                value: Arc::new(linked.clone()),
            });
            Ok(Reply::metadata(json!({"ok":true,"linked":linked})))
        }
    }
}

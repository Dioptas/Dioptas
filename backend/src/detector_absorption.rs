//! Oblique detector efficiency from calibrated physical pixel positions.
use crate::{control::Control, geometry::Geometry};
use rayon::prelude::*;
use std::sync::{Arc, Mutex};

#[derive(Clone)]
struct Map {
    geometry: Geometry,
    shape: [usize; 2],
    depth: f64,
    values: Arc<Vec<f64>>,
}

// Shared by processing snapshots and read-only previews. Keep only one map;
// image counts, backgrounds and frame generations do not affect efficiency.
#[derive(Clone, Default)]
pub(crate) struct Maps(Arc<Mutex<Option<Map>>>);
impl Maps {
    pub fn bytes(&self) -> usize {
        self.0
            .lock()
            .unwrap()
            .as_ref()
            .map_or(0, |m| m.values.len() * 8)
    }

    pub fn get(
        &self,
        geometry: &Geometry,
        shape: [usize; 2],
        thickness: f64,
        absorption_length: f64,
        control: &Control,
    ) -> Result<Arc<Vec<f64>>, String> {
        control.check()?;
        let depth = thickness / absorption_length;
        if !depth.is_finite() || depth <= 0. {
            return Err("Detector thickness and absorption length must be positive.".into());
        }
        if let Some(m) = self.0.lock().unwrap().as_ref()
            && m.geometry == *geometry
            && m.shape == shape
            && m.depth == depth
        {
            return Ok(m.values.clone());
        }
        let mut trace = crate::frame_trace::FrameTrace::new(
            "detector-absorption-map",
            (shape[0] * shape[1]) as u64,
        );
        let native = geometry.native_geometry(shape)?;
        let nonflat = native.detector().filter(|d| !d.is_flat());
        let normal_efficiency = -(-depth).exp_m1();
        trace.mark("geometry and scalar setup");
        let mut values = vec![0.; shape[0] * shape[1]];
        crate::worker_pool::install(|| {
            values
                .par_chunks_mut(shape[1])
                .enumerate()
                .try_for_each(|(row, out)| {
                    control.check()?;
                    for (col, value) in out.iter_mut().enumerate() {
                        let [z, y, x] =
                            native.detector_position(row as f64 + 0.5, col as f64 + 0.5);
                        let ray = [geometry.dist + z, y - geometry.poni1, x - geometry.poni2];
                        let distance = ray.iter().map(|v| v * v).sum::<f64>().sqrt();
                        // Work in the detector frame: rotating both the ray and
                        // surface normal by the calibrated rotations cancels out.
                        let cosine = if let Some(detector) = nonflat {
                            let corners = detector.corners(shape, row, col);
                            let a: [f64; 3] =
                                std::array::from_fn(|k| corners[2][k] - corners[0][k]);
                            let b: [f64; 3] =
                                std::array::from_fn(|k| corners[3][k] - corners[1][k]);
                            let n = [
                                a[1] * b[2] - a[2] * b[1],
                                a[2] * b[0] - a[0] * b[2],
                                a[0] * b[1] - a[1] * b[0],
                            ];
                            let dot = n.iter().zip(ray).map(|(a, b)| a * b).sum::<f64>();
                            dot.abs() / (n.iter().map(|v| v * v).sum::<f64>().sqrt() * distance)
                        } else {
                            ray[0].abs() / distance
                        };
                        if !cosine.is_finite() || cosine <= 0. {
                            return Err(
                                "Detector absorption requires a finite, nonzero incidence cosine."
                                    .to_string(),
                            );
                        }
                        *value = -(-depth / cosine.min(1.)).exp_m1() / normal_efficiency;
                    }
                    Ok(())
                })
        })?;
        trace.mark("path and efficiency kernel");
        control.check()?;
        let values = Arc::new(values);
        *self.0.lock().unwrap() = Some(Map {
            geometry: geometry.clone(),
            shape,
            depth,
            values: values.clone(),
        });
        Ok(values)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn calibrated_incidence_is_stable_from_thin_to_opaque_sensors() {
        let control = Control::default();
        let mut geometry = Geometry {
            dist: 0.1,
            poni1: 0.00005,
            poni2: 0.00005,
            pixel1: 0.0001,
            pixel2: 0.0001,
            rot1: 0.4,
            rot2: -0.3,
            rot3: 0.7,
            ..Default::default()
        };
        for depth in [1e-9, 40. / 150., 1e9] {
            let maps = Maps::default();
            let values = maps.get(&geometry, [3, 4], depth, 1., &control).unwrap();
            assert_eq!(values[0], 1.); // Pixel centered exactly at the PONI.
            let expected_cos = 0.1 / (0.01 + 0.0002f64.powi(2) + 0.0003f64.powi(2)).sqrt();
            let expected = -(-depth / expected_cos).exp_m1() / -(-depth).exp_m1();
            assert!((values[11] - expected).abs() < 2e-15);
            // Rigid calibration rotation acts on both normal and ray.
            geometry.rot3 += 0.1;
            assert_eq!(
                *values,
                *maps.get(&geometry, [3, 4], depth, 1., &control).unwrap()
            );
        }
    }

    #[test]
    fn snapshots_reuse_maps_and_geometry_shape_or_sensor_edits_invalidate_them() {
        let control = Control::default();
        let geometry = Geometry::default();
        let maps = Maps::default();
        let first = maps.get(&geometry, [3, 4], 40., 150., &control).unwrap();
        let again = maps
            .clone()
            .get(&geometry, [3, 4], 40., 150., &control)
            .unwrap();
        assert!(Arc::ptr_eq(&first, &again));
        let edited = maps.get(&geometry, [3, 4], 44., 150., &control).unwrap();
        assert!(!Arc::ptr_eq(&first, &edited));
        assert_ne!(*first, *edited);
        let mut changed = geometry.clone();
        changed.poni1 += 0.001;
        let moved = maps.get(&changed, [3, 4], 44., 150., &control).unwrap();
        assert_ne!(*edited, *moved);
        let reshaped = maps.get(&changed, [4, 3], 44., 150., &control).unwrap();
        assert!(!Arc::ptr_eq(&moved, &reshaped));
        assert_eq!(maps.bytes(), 12 * 8);
        control.cancel();
        assert!(maps.get(&changed, [4, 3], 44., 150., &control).is_err());
    }

    #[test]
    fn mapped_surface_normals_follow_orientation_and_image_transforms() {
        use dioptrin::detector::{Detector, DetectorTransform, PixelMap};
        // A mapped plane z = 0.7 x has a known normal [1, 0, -0.7].
        let shape = [2, 3];
        let mut corners = vec![];
        for row in 0..shape[0] {
            for col in 0..shape[1] {
                corners.push([[0., 0.], [1., 0.], [1., 1.], [0., 1.]].map(|[dy, dx]| {
                    let x = (col as f64 + dx) * 0.001;
                    [0.7 * x, (row as f64 + dy) * 0.001, x]
                }));
            }
        }
        for orientation in 1..=4 {
            for operation in [
                DetectorTransform::Identity,
                DetectorTransform::Left,
                DetectorTransform::Horizontal,
            ] {
                let mut detector = Detector::custom(0.001, 0.001);
                detector.orientation = orientation;
                detector.max_shape = Some(shape);
                detector.map = PixelMap::Corners {
                    shape,
                    values: Arc::new(corners.clone()),
                };
                let detector = detector.transformed(operation).unwrap();
                let shape = detector.max_shape.unwrap();
                let geometry = Geometry {
                    dist: 0.1,
                    detector: Some(Arc::new(detector)),
                    ..Default::default()
                };
                let native = geometry.native_geometry(shape).unwrap();
                let map = Maps::default()
                    .get(&geometry, shape, 1., 2., &Control::default())
                    .unwrap();
                for (i, &value) in map.iter().enumerate() {
                    let [z, y, x] = native.detector_position(
                        (i / shape[1]) as f64 + 0.5,
                        (i % shape[1]) as f64 + 0.5,
                    );
                    let cosine =
                        0.1 / (1.49f64.sqrt() * ((0.1 + z).powi(2) + y * y + x * x).sqrt());
                    let expected = -(-0.5 / cosine).exp_m1() / -(-0.5f64).exp_m1();
                    assert!(
                        (value - expected).abs() < 2e-15,
                        "{orientation} {operation:?}"
                    );
                }
            }
        }
    }
}

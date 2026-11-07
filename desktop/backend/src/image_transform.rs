//! Image/detector transformations retain source samples and coordinate histories.
use super::*;
use crate::transform::{self, Transform};
impl Session {
    pub(super) fn reorient_view(&mut self, target: &[Transform]) -> Result<(), String> {
        if target == self.settings.transformations {
            return Ok(());
        }
        let image = self.image.as_mut().ok_or("Open an image first.")?;
        let shape = image.shape;
        let mut mapping = transform::inverse(&self.settings.transformations);
        mapping.extend_from_slice(target);
        self.mask = transform::apply(&self.mask, shape, &mapping, &self.control)?;
        for snapshot in self.undo.iter_mut().chain(self.redo.iter_mut()) {
            snapshot.user = transform::apply(&snapshot.user, shape, &mapping, &self.control)?;
        }
        image.orient(target, &self.control)?;
        self.settings.transformations = target.to_vec();
        self.image_generation += 1;
        self.image_raster = Some(Raster::image(&image.values, image.shape));
        self.processed_values = None;
        self.processed_raster = None;
        self.inspection = None;
        #[cfg(feature = "dioptrin")]
        {
            self.prepared = None;
        }
        Ok(())
    }
    pub(super) fn image_transform(&mut self, args: &Value, defer: bool) -> Result<Reply, String> {
        self.require_image()?;
        check_keys(args, &["operation", "defer_integration"])?;
        let op = match args["operation"].as_str() {
            Some("rotate_left") => Some(Transform::RightArray),
            Some("rotate_right") => Some(Transform::LeftArray),
            Some("flip_horizontal") => Some(Transform::Horizontal),
            Some("flip_vertical") => Some(Transform::Vertical),
            Some("reset") => None,
            _ => return Err("Unknown image transformation.".into()),
        };
        if op.is_none() && self.settings.transformations.is_empty() {
            return Ok(self.snapshot(true));
        }
        let before = self.calibration_snapshot();
        let mut target = self.settings.transformations.clone();
        if let Some(op) = op {
            if target.len() >= 1024 {
                return Err(
                    "Reset image transformations before adding more than 1024 operations.".into(),
                );
            }
            self.settings
                .original_pixels
                .get_or_insert([self.settings.geometry.pixel1, self.settings.geometry.pixel2]);
            if op.swaps_axes() {
                std::mem::swap(
                    &mut self.settings.geometry.pixel1,
                    &mut self.settings.geometry.pixel2,
                );
            }
            target.push(op);
        } else {
            target.clear();
            if let Some([p1, p2]) = self.settings.original_pixels.take() {
                self.settings.geometry.pixel1 = p1;
                self.settings.geometry.pixel2 = p2;
            }
        }
        self.control
            .publish(json!({"running":true,"current":0,"total":1,"label":"Transforming image"}));
        self.reorient_view(&target)?;
        // Keep valid ROI slices; a rotated rectangular detector can clip them.
        if let Some([r0, r1, c0, c1]) = self.settings.roi {
            let [h, w] = self.image.as_ref().unwrap().shape;
            self.settings.roi =
                (r0 < r1.min(h) && c0 < c1.min(w)).then_some([r0, r1.min(h), c0, c1.min(w)]);
        }
        self.calibration.picks.clear();
        self.calibration.rms = None;
        self.calibration.dirty = self.settings.calibrated;
        self.calibration.saved = false;
        self.calculate(defer)?;
        self.control.check()?;
        self.revision += 1;
        let after = self.calibration_snapshot();
        self.calibration_history
            .record("image_transform", before, after, self.revision);
        Ok(self.snapshot(true))
    }
}

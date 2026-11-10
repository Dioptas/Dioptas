//! Detector changes are decided before publishing pixels or reusing geometry.
use super::*;

impl Session {
    pub(super) fn image_change(
        &self,
        image: &Image,
        args: &Value,
    ) -> Result<Option<Reply>, String> {
        let reset = args
            .get("reset_calibration")
            .map(|v| boolean(v, "Reset calibration"))
            .transpose()?
            .unwrap_or(false);
        let keep = args
            .get("keep_calibration")
            .map(|v| boolean(v, "Keep calibration"))
            .transpose()?
            .unwrap_or(false);
        if reset && keep {
            return Err("Choose either keeping or resetting the calibration.".into());
        }
        if keep {
            if !self.settings.calibrated {
                return Err("There is no calibration to keep.".into());
            }
            self.source_geometry().sync_shape(image.source_shape)?;
        }
        // Without a calibration, changing source dimensions only invalidates
        // image-coordinate state. It must never ask to reset a nonexistent fit.
        if !self.settings.calibrated || keep {
            return Ok(None);
        }
        let expected = self.image.as_ref().map(|i| i.source_shape).or_else(|| {
            self.settings
                .geometry
                .detector
                .as_ref()
                .and_then(|d| d.max_shape)
        });
        // A manufacturer-defined binning can resolve the first image safely.
        // Subsequent source-size changes always require an explicit decision.
        if self.image.is_none()
            && self
                .settings
                .geometry
                .validate_shape(image.source_shape)
                .is_ok()
        {
            return Ok(None);
        }
        if !reset
            && let Some(expected) = expected
            && expected != image.source_shape
        {
            let mut options = image.options.clone();
            options["path"] = json!(image.path);
            options["frame"] = json!(image.frame);
            return Ok(Some(Reply::metadata(json!({"ok":true,"cancelled":true,
                "imageChange":{"path":image.path,"frame":image.frame,
                    "previousShape":expected,"newShape":image.source_shape,"options":options,
                    "canKeepCalibration":self.source_geometry().sync_shape(image.source_shape).is_ok()}}))));
        }
        Ok(None)
    }

    fn source_geometry(&self) -> Geometry {
        let mut g = self.settings.geometry.clone();
        if !self.settings.transformations.is_empty() {
            g.detector = self.settings.original_detector.clone();
            if let Some([p1, p2]) = self.settings.original_pixels {
                g.pixel1 = p1;
                g.pixel2 = p2;
            }
        }
        g
    }

    /// Forget coordinates tied to the old source plane, retaining the geometry
    /// and all scientific preferences that remain meaningful for the new plane.
    pub(super) fn reset_image_coordinates(&mut self, shape: [usize; 2]) {
        self.settings.geometry = self.source_geometry();
        self.settings.transformations.clear();
        self.settings.original_pixels = None;
        self.settings.original_detector = None;
        if !self.settings.calibrated {
            let g = &mut self.settings.geometry;
            if g.validate_shape(shape).is_err() {
                g.detector = None;
                g.frame_pixels = None;
                g.detector_file = None;
                g.distortion_file = None;
            }
            if g.detector.is_none() {
                g.auto_assign = true;
            }
        }
        self.settings.roi = None;
        self.mask = Arc::new(vec![0; shape[0] * shape[1]]);
        self.effective_mask = self.mask.clone();
        self.mask_filename = None;
        self.mask_raster = None;
        self.plugins = Plugins::default();
        self.undo.clear();
        self.redo.clear();
        self.calibration.picks.clear();
        self.calibration.rms = None;
        self.calibration.dirty = false;
        self.calibration_history = Default::default();
        self.integration_history = Default::default();
        self.patterns.extracted = None;
        self.inspection = None;
        *self.inspection_contour.borrow_mut() = None;
        *self.inspection_field.borrow_mut() = None;
        *self.detector_mask.borrow_mut() = None;
        #[cfg(feature = "dioptrin")]
        {
            *self.native_geometry_cache.borrow_mut() = None;
            *self.ring_cache.borrow_mut() = None;
        }
    }

    pub(super) fn reset_detector_state(&mut self) -> Result<(), String> {
        if self.image.is_some() {
            self.reorient_view(&[])?;
        }
        let reference = self.calibration.reference.clone();
        let custom = self.calibration.custom.clone();
        let start = self.calibration.start;
        self.settings.geometry = Geometry {
            dist: start[0],
            wavelength: start[6],
            ..Default::default()
        };
        self.settings.calibrated = false;
        self.settings.calibration_name = None;
        self.settings.calibration_path = None;
        self.settings.original_pixels = None;
        self.settings.original_detector = None;
        self.settings.transformations.clear();
        self.settings.use_mask = false;
        self.settings.roi = None;
        self.settings.auto_save = false;
        self.calibration = Calibration::default();
        self.calibration.reference = reference;
        self.calibration.custom = custom;
        self.calibration.start = start;
        self.calibration.reference_wavelength = start[6];
        self.processing = Default::default();
        self.processed_values = None;
        self.processed_raster = None;
        self.plugins = Plugins::default();
        self.mask = Arc::new(vec![0; self.image.as_ref().map_or(0, |i| i.values.len())]);
        self.effective_mask = self.mask.clone();
        self.mask_raster = None;
        self.mask_filename = None;
        self.undo.clear();
        self.redo.clear();
        self.calibration_history = Default::default();
        self.integration_history = Default::default();
        if !self.patterns.imported {
            self.patterns.raw = None;
        }
        self.patterns.extracted = None;
        self.pattern = None;
        self.cake = None;
        self.cake_values = None;
        self.inspection = None;
        *self.inspection_contour.borrow_mut() = None;
        *self.inspection_field.borrow_mut() = None;
        *self.detector_mask.borrow_mut() = None;
        self.files.stop_autoprocess();
        #[cfg(feature = "dioptrin")]
        {
            self.engine = Default::default();
            self.prepared = None;
            self.sigma = None;
            *self.native_geometry_cache.borrow_mut() = None;
            *self.ring_cache.borrow_mut() = None;
        }
        Ok(())
    }
}

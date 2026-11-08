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
                    "previousShape":expected,"newShape":image.source_shape,"options":options}}))));
        }
        Ok(None)
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

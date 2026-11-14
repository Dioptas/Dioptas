//! Shared original-count seat/illumination and full-exposure DAC masks.
//! Conventions and kernels are identical to PhaseSmith's standalone coordinator.
use super::*;
use spots::frame_validity as validity;
#[derive(Clone)]
pub(super) struct Shadows {
    pub first: usize,
    pub last: usize,
    pub block: usize,
    pub columns: usize,
    pub cells: usize,
    pub illumination: Vec<bool>,
    pub dac: Vec<bool>,
    pub report: Value,
}
impl Shadows {
    pub fn excluded(&self, frame: usize, pixel: usize, width: usize) -> bool {
        if frame < self.first || frame > self.last {
            return true;
        }
        let cell = (frame - self.first) * self.cells
            + (pixel / width / self.block) * self.columns
            + pixel % width / self.block;
        self.illumination.get(cell).copied().unwrap_or(false)
            || self.dac.get(cell).copied().unwrap_or(false)
    }
    /// Share of the measured seat-shadow cells that the geometric DAC mask
    /// also excludes. Both describe the same cell body, so a low share means
    /// the declared rotation axis, angles or DAC axis disagree with the data.
    /// Frames the DAC mask closes completely carry no information. None
    /// without both masks or with too little measured shadow to judge.
    pub fn dac_agreement(&self) -> Option<f64> {
        if self.dac.is_empty() || self.illumination.is_empty() || self.cells == 0 {
            return None;
        }
        let (mut both, mut seat) = (0, 0);
        for (dac, measured) in self
            .dac
            .chunks(self.cells)
            .zip(self.illumination.chunks(self.cells))
        {
            if dac.iter().all(|&v| v) {
                continue;
            }
            for (&d, &m) in dac.iter().zip(measured) {
                seat += usize::from(m);
                both += usize::from(m && d);
            }
        }
        (seat >= self.cells / 10).then(|| both as f64 / seat as f64)
    }
}
pub(super) fn fingerprint(values: &[bool]) -> String {
    let mut hash = Sha256::new();
    for chunk in values.chunks(65536) {
        hash.update(chunk.iter().map(|&b| u8::from(b)).collect::<Vec<_>>());
    }
    format!("{:x}", hash.finalize())
}
impl Crystal {
    pub(super) fn prepare_shadows(&mut self, control: &Control) -> Result<(), String> {
        if self.shadows.is_some() || !(self.config.dac_enabled || self.config.seat_enabled) {
            return Ok(());
        }
        let first = (0..self.sources.len())
            .find(|i| !self.excluded_frames.contains(i))
            .ok_or("All frames are excluded.")?;
        let last = (0..self.sources.len())
            .rfind(|i| !self.excluded_frames.contains(i))
            .unwrap();
        let shape = validity::Shape {
            height: self.shape[0],
            width: self.shape[1],
            block: self.config.shadow_block,
        };
        let [rows, columns] = shape.coarse().map_err(err)?;
        let cells = rows * columns;
        let frames = last - first + 1;
        if frames
            .checked_mul(cells)
            .is_none_or(|n| n > validity::MAX_CELLS)
        {
            return Err("Shadow mask exceeds the native coarse-cell budget; increase block size or reduce scan length.".into());
        }
        let mut illumination = vec![];
        let mut scales = vec![1.; frames];
        let mut references = vec![];
        if self.config.seat_enabled {
            let mut coarse = Vec::with_capacity(frames * cells);
            let mut available = vec![];
            for frame in first..=last {
                control.check()?;
                let raw = self.read(frame)?;
                let mask = self.base_mask(&raw, frame);
                let c = validity::coarsen(&raw, &mask, shape).map_err(err)?;
                coarse.extend(c.values);
                available.push(c.available);
                control.publish(json!({"running":true,"current":frame-first+1,"total":frames,"label":"Estimating original-count cell-seat shadows"}));
            }
            let estimate = validity::estimate(
                &coarse,
                &available,
                shape,
                validity::SeatOptions {
                    threshold: self.config.seat_threshold,
                    guard_pixels: self.config.seat_guard,
                    ..Default::default()
                },
            )
            .map_err(err)?;
            illumination = estimate.excluded;
            scales = estimate.detection_scales;
            references = estimate
                .reference_indices
                .iter()
                .map(|i| i + first)
                .collect();
        }
        let mut dac = vec![];
        if self.config.dac_enabled {
            let mut g = self
                .initial_geometry
                .ok_or("Load a detector calibration before preparing DAC shadows.")?
                .native();
            g.axis = self.config.axis;
            for frame in first..=last {
                control.check()?;
                let low = self.config.omega_start + frame as f64 * self.config.omega_step;
                dac.extend(
                    validity::dac_mask(
                        g,
                        [low, low + self.config.exposure],
                        shape,
                        validity::DacOptions {
                            axis_at_zero: self.config.dac_axis,
                            half_opening_degrees: self.config.dac_half_opening,
                        },
                    )
                    .map_err(err)?
                    .excluded,
                );
            }
        }
        let report = json!({"first":first,"last":last,"block":shape.block,"coarseShape":[rows,columns],"illuminationSha256":fingerprint(&illumination),"dacSha256":fingerprint(&dac),"illuminationExcluded":illumination.iter().filter(|&&v|v).count(),"dacExcluded":dac.iter().filter(|&&v|v).count(),"referenceFrames":references,"detectionScales":scales,"geometry":"initial calibrated affine geometry; whole closed exposure and whole block footprint","intensities":"original counts, never divided by illumination scale"});
        self.shadows = Some(Arc::new(Shadows {
            first,
            last,
            block: shape.block,
            columns,
            cells,
            illumination,
            dac,
            report,
        }));
        Ok(())
    }
}

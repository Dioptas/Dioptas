//! Display-only marching-squares paths for calibration ring overlays.
use crate::contours::contours_at_step;

/// Display-only marching-squares paths. Coordinates are detector pixel centers;
/// fitting and searches always use the original full-resolution field.
pub fn contours(angles: &[f64], shape: [usize; 2], targets: &[(usize, f64)]) -> serde_json::Value {
    contours_at_step(
        angles,
        shape,
        targets,
        shape[0].max(shape[1]).div_ceil(450).max(1),
    )
}

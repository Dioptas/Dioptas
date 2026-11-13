//! Shared-axis Chebyshev least squares. Only the right-hand side changes from
//! frame to frame: preserve the original NumPy-compatible SVD and solve order,
//! while preparing its matrix/decomposition once for a Batch operation.
use nalgebra::{DMatrix, DVector, Dyn, linalg::SVD};

pub(crate) struct ChebyshevFit {
    axis: Vec<f64>,
    degree: usize,
    matrix: DMatrix<f64>,
    svd: SVD<f64, Dyn, Dyn>,
    cutoff: f64,
}
impl ChebyshevFit {
    pub fn new(x: &[f64], degree: usize) -> Result<Self, String> {
        let terms = degree + 1;
        if x.len() < 2
            || x.len()
                .checked_mul(terms)
                .is_none_or(|n| n > 16 * 1024 * 1024)
        {
            return Err("Background polynomial exceeds the bounded fitting matrix; reduce order or bin count.".into());
        }
        let extent = x[x.len() - 1] - x[0];
        if extent == 0.0 || !extent.is_finite() {
            return Err("Background fit needs distinct, finite endpoints.".into());
        }
        let mut matrix = DMatrix::zeros(x.len(), terms);
        for (i, &v) in x.iter().enumerate() {
            let t = 2.0 * (v - x[0]) / extent - 1.0;
            matrix[(i, 0)] = 1.0;
            if terms > 1 {
                matrix[(i, 1)] = t;
            }
            for j in 2..terms {
                matrix[(i, j)] = 2.0 * t * matrix[(i, j - 1)] - matrix[(i, j - 2)];
            }
        }
        // Keep column scaling and singular-value cutoff identical to chebfit.
        for j in 0..terms {
            let norm = matrix.column(j).norm();
            let scale = if norm == 0.0 { 1.0 } else { norm };
            matrix.column_mut(j).scale_mut(1.0 / scale);
        }
        let svd = matrix.clone().svd(true, true);
        let largest = svd.singular_values.iter().copied().fold(0.0, f64::max);
        Ok(Self {
            axis: x.to_vec(),
            degree,
            matrix,
            svd,
            cutoff: x.len() as f64 * f64::EPSILON * largest,
        })
    }
    pub fn matches(&self, x: &[f64], degree: usize) -> bool {
        self.degree == degree && self.axis == x
    }
    pub fn fit(&self, y: &[f64]) -> Result<Vec<f64>, String> {
        if y.len() != self.axis.len() {
            return Err("Background fit arrays differ in length.".into());
        }
        let coefficients = self
            .svd
            .solve(&DVector::from_column_slice(y), self.cutoff)
            .map_err(|_| "Background polynomial solve failed.")?;
        let fitted = &self.matrix * coefficients;
        if fitted.iter().any(|v| !v.is_finite()) {
            return Err("Background polynomial is not finite.".into());
        }
        Ok(fitted.as_slice().to_vec())
    }
}

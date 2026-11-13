//! Lossless detector permutations. Source storage and scientific orientation are separate.
use crate::control::Control;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Transform {
    #[serde(rename = "rotate_matrix_p90")]
    LeftArray,
    #[serde(rename = "rotate_matrix_m90")]
    RightArray,
    #[serde(rename = "fliplr")]
    Horizontal,
    #[serde(rename = "flipud")]
    Vertical,
}
impl Transform {
    pub fn inverse(self) -> Self {
        match self {
            Self::LeftArray => Self::RightArray,
            Self::RightArray => Self::LeftArray,
            other => other,
        }
    }
    pub fn swaps_axes(self) -> bool {
        matches!(self, Self::LeftArray | Self::RightArray)
    }
}
pub fn parse(value: &serde_json::Value) -> Result<Vec<Transform>, String> {
    let a = value
        .as_array()
        .filter(|a| a.len() <= 1024)
        .ok_or("Image transformations need at most 1024 supported operations.")?;
    a.iter()
        .map(|v| {
            serde_json::from_value(v.clone()).map_err(|_| "Unknown image transformation.".into())
        })
        .collect()
}
pub fn inverse(ops: &[Transform]) -> Vec<Transform> {
    ops.iter().rev().map(|t| t.inverse()).collect()
}
pub fn shape(mut shape: [usize; 2], ops: &[Transform]) -> [usize; 2] {
    for op in ops {
        if op.swaps_axes() {
            shape.swap(0, 1);
        }
    }
    shape
}
/// Compose the log into one signed-stride permutation, so cost is independent
/// of the number of clicks and no interpolation or numeric conversion occurs.
pub fn apply<T: Copy>(
    data: &Arc<Vec<T>>,
    input: [usize; 2],
    ops: &[Transform],
    control: &Control,
) -> Result<Arc<Vec<T>>, String> {
    let mut size = input;
    let (mut origin, mut rows, mut cols) = (0_isize, input[1] as isize, 1_isize);
    for op in ops {
        let (h, w) = (size[0] as isize, size[1] as isize);
        match op {
            Transform::LeftArray => {
                origin += (w - 1) * cols;
                (rows, cols) = (-cols, rows);
                size.swap(0, 1);
            }
            Transform::RightArray => {
                origin += (h - 1) * rows;
                (rows, cols) = (cols, -rows);
                size.swap(0, 1);
            }
            Transform::Horizontal => {
                origin += (w - 1) * cols;
                cols = -cols;
            }
            Transform::Vertical => {
                origin += (h - 1) * rows;
                rows = -rows;
            }
        }
    }
    if data.is_empty() || (size == input && origin == 0 && rows == input[1] as isize && cols == 1) {
        return Ok(data.clone());
    }
    if input[0].checked_mul(input[1]) != Some(data.len()) {
        return Err("Detector permutation dimensions differ.".into());
    }
    let mut result = Vec::with_capacity(data.len());
    for r in 0..size[0] {
        control.check()?;
        let first = origin + r as isize * rows;
        for c in 0..size[1] {
            result.push(data[(first + c as isize * cols) as usize]);
        }
    }
    Ok(Arc::new(result))
}

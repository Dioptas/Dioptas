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

use Transform::{Horizontal, LeftArray, RightArray, Vertical};
/// The eight views any button sequence reduces to, named after the
/// calibration buttons. `transpose` mirrors along the main diagonal.
pub const ORIENTATIONS: [(&str, &[Transform]); 8] = [
    ("none", &[]),
    ("rotate_right", &[LeftArray]),
    ("rotate_left", &[RightArray]),
    ("rotate_180", &[LeftArray, LeftArray]),
    ("flip_horizontal", &[Horizontal]),
    ("flip_vertical", &[Vertical]),
    ("transpose", &[LeftArray, Vertical]),
    ("transverse", &[LeftArray, Horizontal]),
];
fn same_view(a: &[Transform], b: &[Transform]) -> bool {
    const SHAPE: [usize; 2] = [3, 5];
    let labels = Arc::new((0usize..15).collect::<Vec<_>>());
    let control = Control::default();
    shape(SHAPE, a) == shape(SHAPE, b)
        && apply(&labels, SHAPE, a, &control).ok() == apply(&labels, SHAPE, b, &control).ok()
}
/// Name of the view a transformation log produces.
pub fn orientation_name(ops: &[Transform]) -> &'static str {
    ORIENTATIONS
        .iter()
        .find(|(_, canonical)| same_view(ops, canonical))
        .map(|(name, _)| *name)
        .expect("rotations and flips form a closed group of eight views")
}
/// Shortest transformation log for a recorded orientation name.
pub fn orientation_ops(name: &str) -> Option<Vec<Transform>> {
    ORIENTATIONS
        .iter()
        .find(|(known, _)| known.eq_ignore_ascii_case(name.trim()))
        .map(|(_, ops)| ops.to_vec())
}
#[cfg(test)]
mod orientation_tests {
    use super::*;
    #[test]
    fn button_sequences_reduce_to_named_views() {
        assert_eq!(orientation_name(&[]), "none");
        assert_eq!(
            orientation_name(&[RightArray, RightArray, RightArray]),
            "rotate_right"
        );
        assert_eq!(orientation_name(&[Horizontal, Vertical]), "rotate_180");
        assert_eq!(orientation_name(&[Horizontal, Horizontal]), "none");
        for (name, ops) in ORIENTATIONS {
            assert_eq!(orientation_name(ops), name);
            assert_eq!(orientation_ops(name).as_deref(), Some(ops));
        }
        assert_eq!(orientation_ops("Rotate_Left"), Some(vec![RightArray]));
        assert_eq!(orientation_ops("sideways"), None);
        // Transpose: element (r, c) of the view is element (c, r) of the source.
        let source = Arc::new((0usize..6).collect::<Vec<_>>());
        let view = apply(
            &source,
            [2, 3],
            &orientation_ops("transpose").unwrap(),
            &Control::default(),
        )
        .unwrap();
        assert_eq!(*view, vec![0, 3, 1, 4, 2, 5]);
    }
}

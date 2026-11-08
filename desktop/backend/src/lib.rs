#![recursion_limit = "256"]
//! Native processing for the existing desktop command/binary-raster contract.
//! The default runtime uses Dioptrin directly, without Python.
mod contours;
pub mod control;
mod custom_actions;
mod detector_mask;
pub mod display;
mod frame_trace;
mod geometry;
pub mod image;
#[cfg(feature = "dioptrin")]
mod integration;
mod lacosmic;
mod map_math;
mod map_preview;
mod mask_plugins;
mod pattern;
#[cfg(feature = "dioptrin")]
mod peak_search;
mod phase_crystal;
mod phase_references;
mod phase_sites;
mod phases;
mod processing;
pub mod protocol;
#[cfg(feature = "dioptrin")]
mod sample_absorption;
mod scan;
#[cfg(feature = "dioptrin")]
mod sector;
mod series;
pub mod session;
mod transform;
pub mod transport;

pub use session::Session;

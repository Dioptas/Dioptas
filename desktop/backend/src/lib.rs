#![recursion_limit = "256"]
//! Native processing for the existing desktop command/binary-raster contract.
//! File input has no Python dependency. Numerical engines are optional adapters.
mod contours;
pub mod control;
mod custom_actions;
pub mod display;
mod geometry;
pub mod image;
#[cfg(feature = "dioptrin")]
mod integration;
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
mod scan;
#[cfg(feature = "dioptrin")]
mod sector;
mod series;
pub mod session;
pub mod transport;

pub use session::Session;

#![recursion_limit = "256"]
//! Native processing for the existing desktop command/binary-raster contract.
//! The default runtime uses Dioptrin directly, without Python.
#[cfg(feature = "dioptrin")]
mod analytical_absorption;
mod background_fit;
mod background_workers;
mod batch_background;
mod batch_pattern_background;
mod batch_waterfall;
mod contours;
pub mod control;
mod correction_maps;
#[cfg(feature = "dioptrin")]
mod correction_preview;
mod custom_actions;
#[cfg(feature = "dioptrin")]
mod detector_absorption;
mod detector_mask;
pub mod display;
mod frame_trace;
mod geometry;
mod hdf5_loading;
mod hdf5_sources;
mod history_transfer;
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
mod phase_dac;
mod phase_record_metadata;
mod phase_references;
mod phase_sites;
mod phases;
mod processing;
pub mod protocol;
#[cfg(feature = "dioptrin")]
mod pyfai_splitting;
#[cfg(feature = "dioptrin")]
mod sample_absorption;
mod scan;
#[cfg(feature = "dioptrin")]
mod sector;
mod series;
pub mod session;
mod spottiness;
mod transform;
pub mod transport;
mod waterfall_spacing;
mod worker_pool;

pub use session::Session;

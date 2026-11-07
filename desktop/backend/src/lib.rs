#![recursion_limit = "256"]
//! Native processing for the existing desktop command/binary-raster contract.
//! File input has no Python dependency. Numerical engines are optional adapters.
pub mod display;
mod geometry;
pub mod image;
#[cfg(feature = "dioptrin")]
mod integration;
pub mod protocol;
pub mod session;
pub mod transport;

pub use session::Session;

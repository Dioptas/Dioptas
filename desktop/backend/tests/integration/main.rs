//! Single integration-test binary for the backend.
//!
//! Each former `tests/<name>.rs` file is a module here, so the whole
//! dependency tree (static HDF5, Dioptrin, PhaseSmith, ...) is linked once
//! instead of once per file. Feature- or profile-gated files keep their
//! `#![cfg(...)]` as an inner attribute of the module. Run one former file
//! with `cargo test --test integration <name>::`.
mod batch_background;
mod batch_export_background;
mod batch_waterfall;
mod cake_axis;
mod calibration;
mod combined_workflows;
mod configuration_navigation;
mod correction_previews;
mod dac_thermal_pressure;
mod desktop_consolidation;
mod detector_gap_margins;
mod detector_switch;
mod detectors;
mod development_reload;
mod functional_flows;
mod geometry_masks;
mod hdf5_external_offsets;
mod hdf5_master_vds;
mod hdf5_sources;
mod lacosmic;
mod mask_plugins;
mod native_session;
mod overlay_uid;
mod pattern_figure_export;
mod peritheos_distribution;
mod phase_equation_audit;
mod phase_order;
mod phase_record_defaults;
mod phase_record_metadata;
mod processing_workers;
mod project_dataset_reuse;
mod projects;
mod pyfai_typed_image;
mod requested_products;
mod review_backend_regressions;
mod spottiness;
mod zero_trimming;

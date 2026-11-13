# Desktop documentation

Setup and running instructions are in the
[development guide](../DEVELOPMENT.md); working rules are in [AGENTS.md](../AGENTS.md).

## Workflow guides

- [Batch image series](guide/BATCH.md)
- [Calibration workflow](guide/CALIBRATION.md)
- [Custom actions](guide/CUSTOM_ACTIONS.md)
- [Native feature status](guide/FEATURES.md)
- [Integration workflow](guide/INTEGRATION.md)
- [Layout and plot interaction](guide/LAYOUT_AND_INTERACTION.md)
- [Map workspace](guide/MAP.md)

## Architecture and contracts

- [Native command execution contract](architecture/COMMAND_CONTRACT.md)
- [DAC thermal-pressure fraction](architecture/DAC_THERMAL_PRESSURE.md)
- [Native dependency security](architecture/DEPENDENCY_SECURITY.md)
- [Host, processor and binary transport](architecture/HOST_AND_TRANSPORT.md)
- [Native EoS publication record editing](architecture/PHASE_RECORD_METADATA.md)
- [Application processing workers](architecture/PROCESSING_WORKERS.md)
- [Reference data and Python cleanup](architecture/REFERENCE_DATA.md)
- [Display products and rendering](architecture/RENDERING.md)
- [Single Crystal XRD](architecture/SCXRD_WORKFLOW.md)
- [Native previous-session recovery](architecture/SESSION_RECOVERY.md)
- [Desktop UI components](architecture/UI_COMPONENTS.md)
- [Mask, Integration and Map implementation](architecture/VIEW_DEVELOPMENT.md)

## Releases and updates

- [Application updates](release/APP_UPDATES.md)
- [Linux installer candidates](release/NATIVE_LINUX_RELEASE.md)
- [Native installer candidates](release/NATIVE_RELEASE.md)
- [Windows installer candidates](release/NATIVE_WINDOWS_RELEASE.md)
- [Dioptas 0.14.0-rc.1 — Rust desktop](release/RELEASE_0.14.0-rc.1.md)

## Qt parity and qualification

- [Native Batch backgrounds](parity/BATCH_BACKGROUND_NATIVE.md)
- [Batch processing in the React desktop](parity/BATCH_PARITY.md)
- [Native Batch 3D surface display](parity/BATCH_SURFACE_PARITY.md)
- [Native Batch rectangle to waterfall overlays](parity/BATCH_WATERFALL_PARITY.md)
- [Native azimuthal cake profile — 2026-11-10](parity/CAKE_PROFILE_PARITY.md)
- [Cake 2θ/Q display — November 10, 2026](parity/CAKE_Q_AXIS_PARITY.md)
- [Calibration workflow comparison](parity/CALIBRATION_PARITY.md)
- [Detector combination in the consolidated Rust desktop](parity/DETECTOR_COMBINATION_PARITY.md)
- [Standalone detector image](parity/DETECTOR_WINDOW_PARITY.md)
- [HDF5 master files and explicit source contracts](parity/HDF5_MASTER_VDS_PARITY.md)
- [Native HDF5 image-source selection](parity/HDF5_SOURCE_PARITY.md)
- [Integration workflow comparison](parity/INTEGRATION_PARITY.md)
- [Map workflow parity (2026-11-04)](parity/MAP_PARITY.md)
- [Mask mode: Qt parity and verification](parity/MASK_PARITY.md)
- [Native Batch export qualification — November 10, 2026](parity/NATIVE_BATCH_EXPORT.md)
- [Native correction Plot / Back previews](parity/NATIVE_CORRECTION_PREVIEW_PARITY.md)
- [Native correction and counting-uncertainty qualification](parity/NATIVE_CORRECTION_UNCERTAINTY_PARITY.md)
- [Native detector geometry qualification](parity/NATIVE_DETECTOR_PARITY.md)
- [Native functional coverage and CI](parity/NATIVE_FUNCTIONAL_COVERAGE.md)
- [Native image orientation and geometric masks](parity/NATIVE_GEOMETRY_MASK_PARITY.md)
- [Native integration qualification — 2026-11-07](parity/NATIVE_INTEGRATION_PARITY.md)
- [Native LA Cosmic operation](parity/NATIVE_LACOSMIC_PARITY.md)
- [Native projects and configurations](parity/NATIVE_PROJECT_PARITY.md)
- [Native cylinder and sphere absorption qualification](parity/NATIVE_ROUND_SAMPLE_CORRECTION_PARITY.md)
- [Standalone Rust application — 2026-11-08](parity/NATIVE_STANDALONE_PARITY.md)
- [Native combined-workflow regression coverage](parity/NATIVE_WORKFLOW_REGRESSIONS.md)
- [Integration pattern figure editor — November 10, 2026](parity/PATTERN_FIGURE_EXPORT_PARITY.md)
- [EoS Material Database explorer](parity/PHASE_DATABASE_PARITY.md)
- [React/Tauri phase editor](parity/PHASE_EDITOR_PARITY.md)
- [Phase Editor GUI workflow tests](parity/PHASE_EDITOR_WORKFLOW_TESTS.md)
- [Phase Editor equation and parameter audit](parity/PHASE_EQUATION_AUDIT.md)
- [Integration Phase controls](parity/PHASE_PARITY.md)
- [SCXRD validation and boundaries](parity/SCXRD_VALIDATION.md)
- [Native Spottiness diagnostic](parity/SPOTTINESS_PARITY.md)

## Performance records

- [Polygon integration: broad CSC/CSR selection](performance/INTEGRATION_LAYOUT_CROSSOVER.md)
- [Massif peak-picking performance](performance/MASSIF_PERFORMANCE.md)
- [Correction calculation and Plot performance](performance/NATIVE_CORRECTION_PERFORMANCE.md)
- [Calibrated detector absorption and map reuse](performance/NATIVE_DETECTOR_ABSORPTION_PERFORMANCE.md)
- [Native display preparation and transfer](performance/NATIVE_DISPLAY_TRANSFER_PERFORMANCE.md)
- [Eiger Batch throughput in the native GUI](performance/NATIVE_GUI_SERIES_PERFORMANCE.md)
- [Detector-image phase-line updates](performance/NATIVE_PHASE_GUIDE_PERFORMANCE.md)
- [Corrected images and dynamic masks in native series](performance/NATIVE_PROCESSED_SERIES_PIPELINE.md)
- [Large Batch/Map project persistence benchmark](performance/NATIVE_PROJECT_PERSISTENCE_PERFORMANCE.md)
- [Parallel pyFAI-compatible Batch and Map integration](performance/NATIVE_PYFAI_SERIES_PIPELINE.md)
- [pyFAI-compatible throughput: direct decoder input](performance/NATIVE_PYFAI_SERIES_THROUGHPUT.md)
- [Single-image pyFAI-compatible integration](performance/NATIVE_PYFAI_SINGLE_IMAGE_PERFORMANCE.md)
- [Native Batch/Map frame pipeline](performance/NATIVE_SERIES_PIPELINE.md)
- [Spot and Cosmic mask performance](performance/NATIVE_SPATIAL_MASK_PERFORMANCE.md)
- [Pattern WebGL rendering and benchmark](performance/PATTERN_WEBGL_BENCHMARK.md)
- [Cached pyFAI-compatible integration](performance/PYFAI_CACHED_PERFORMANCE.md)
- [Batch 3D navigation](performance/SURFACE_NAVIGATION_PERFORMANCE.md)

## Dated reviews and migration records

- [Eiger gap margins and Map selection qualification](history/NATIVE_MASK_SELECTION_FIXES.md)
- [Native macOS verification — 2026-11-06](history/NATIVE_VERIFICATION.md)
- [Validated Opus review fixes](history/OPUS_REVIEW_FIXES.md)
- [Python removal audit — November 12, 2026](history/PYTHON_REMOVAL_AUDIT.md)
- [Rust desktop consolidation — November 8, 2026](history/RUST_DESKTOP_CONSOLIDATION.md)
- [SCXRD review record](history/SCXRD_REVIEW.md)
- [MgSiO3: matched PhaseSmith/Dioptas protocol comparison](history/SCXRD_RINT_COMPARISON.md)
- [Shared interface and design audit](history/UI_DESIGN_AUDIT.md)

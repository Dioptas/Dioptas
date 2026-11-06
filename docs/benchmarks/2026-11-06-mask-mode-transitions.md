# Fixed/dynamic mask-mode transitions

Repeated dynamic → fixed → dynamic regression tests exercise both real BatchModel and MapModel, with threshold and static-mask changes. Each mode's output is compared against per-frame reference dispatch. Dynamic worker threads stop on entry to fixed mode, while the one immutable shared plan remains cached. Returning to dynamic mode creates new lightweight worker/plugin contexts referencing that SAME plan, avoiding a geometry/weight rebuild.

Mask, image factor and threshold edits do not change the geometry plan. Shape, calibration, binning, method, native radial unit or polarization changes replace the plan on next use. Explicit full cleanup still releases workers and plan. The cache retains at most one plan per Configuration, so switching modes trades bounded retained memory for avoiding repeated setup.

At the Dioptrin core level, a mask-mode switch now preserves already valid CSR/CSC layouts and normalization caches. Mode selection does not change the inputs those caches depend on. Actual mask edits invalidate mask-specific tables/denominators; correction edits invalidate normalization; geometry changes replace the tables. Rust tests check retained caches, changing masks, numerical parity and original CSR allocation identity across repeated mode transitions.

This refines the earlier benchmark-era policy, which released the shared dynamic plan on entry to fixed mode. Historical timings and source hashes remain unchanged. The setup-time saving applies when a NEW plan is required; ordinary mask-mode switches now reuse the existing plan.

Tests: `test_repeated_fixed_dynamic_round_trips_reuse_plan_and_preserve_results` in `test_dynamic_frame_workers.py`, plus `switching_policy_retains_valid_layouts_and_corrections_preserve_fixed_table` and `fixed_dynamic_switches_preserve_geometry_weights_and_refresh_mask_results` in Dioptrin.

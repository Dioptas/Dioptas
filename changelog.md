# 0.10.1 (15.08.2026)

## Fixes

- Phase temperatures can no longer be set below absolute zero. If a very high temperature or pressure lies outside the numerical domain of the selected equation of state, Dioptas now keeps the last valid phase condition and reflection positions and shows a brief tooltip instead of exposing a calculation error. Changes made with **apply to all** are atomic, and switching to an EoS reference that cannot evaluate the current conditions is likewise rolled back safely.

# 0.10.0 (14.08.2026)

## Highlights

- **Build a map while a scan is running.** Load the first image or images, switch on **Live**, and Dioptas appends new frames as soon as they have finished writing. This also works on beamline network storage. Files from other scans in the same folder are ignored, the grid can be given its final size at any time, and existing blanks, rearrangements and excluded points are preserved.

- **Find pressure standards and sample phases in the new offline EoS database.** The **DB** button in the Phase panel searches 120 bundled materials by name, alias or chemical composition. The database includes 147 publication-checked equation-of-state records, with references, reported parameter uncertainties and experimental fit ranges where available. Select a published record and load it directly as a phase; no internet connection is needed.

- **Use published or custom equations of state without losing their provenance.** A material can contain several literature records, selectable from the phase table. The Phase Editor supports Birch-Murnaghan, Murnaghan, Vinet, Modified Tait, Natural Strain and Holzapfel equations, together with constant-coefficient and Mie-Grüneisen thermal models. Published records are read-only; duplicate one before changing it so edited values cannot retain the original attribution. Complete materials can be shared as `.eosmat` files.

- **Export propagated counting errors.** Enable **Calculate Poisson errors** in the 1D integration options to retain an uncertainty for every integrated point. The new `.xye` output and GSAS `.fxye` output write those errors directly. Calculation is opt-in because it adds integration time; choosing an error-bearing export can enable it and reintegrate the current image for you.

## Improvements

- CIF imports now retain the material name, formula, space group, atom sites and original CIF reflection source. Custom EoS records can store references, reported errors, fixed parameters and fit ranges. A `.eosmat` round-trip keeps this complete material description; `.jcpds` remains available for legacy interoperability.

- Version 2 and 3 JCPDS files, including the older fixed-width format still found in beamline collections, load again.

- Calibrant reflections are numbered consistently on the image, cake and pattern views. The numbers follow the visible part of a zoomed view, and separate checkboxes can hide the labels or all calibrant lines.

- **autoprocess** now detects finished files on network storage and waits for a file to stop growing before loading it.

- File loaders recognize common wrong-file selections and explain where the file belongs without replacing the data already on screen.

- Color images are converted to grayscale intensity images for display and integration. Unsupported image shapes now produce one clear error instead of repeated dialogs.

- Mask-plugin settings have a **Restore Defaults** action, and the calibration validation page remembers whether pyFAI or Fit2D parameters were last selected.

- The application icon has been refreshed. On Windows it now also appears correctly on the taskbar on the first run after unpacking Dioptas.

## Fixes

- An unsuccessful automatic calibration-ring search no longer discards peaks that were picked manually.

- Re-enabling a dynamic mask after changing images now computes the mask for the current image instead of showing the previous result.

- Resetting a project and switching configurations no longer leave calibrant overlays or the wrong ring number on screen.

- Intensity histograms work for 8-bit images.

- Publication citations in the EoS database now retain the complete author list, and symmetry-equivalent cubic reflections use the conventional `(100)` representative.

# 0.9.0 (03.08.2026)

## Breaking changes

- **Project files (.dio) written by Dioptas 0.8.7 or earlier can no longer be opened.** The project file format was reorganised; opening an older project shows a message naming the version that can still read it, and earlier Dioptas releases remain available on PyPI and GitHub for exactly that. Images, calibrations, masks and patterns are unaffected — they live in standard formats outside the project file. On first start after upgrading, the automatically saved session from the previous version is likewise dropped once.

## New Features

- **Map layers.** Each window of the pattern produces one layer of the map, and its *Value* chooses what is measured: the plain sum, a background-subtracted sum, mean, max, **peak area** (with a linear background removed), **peak position** — which makes a d-spacing, and therefore strain, map — or **peak width (FWHM)**. A **?** beside the table explains exactly how each value is computed.

- **Several map windows, and math between them.** Every window is drawn in the pattern plot in its own colour (click the swatch in its row to change it) and can be dragged there. *Computed layers* combine windows by name — `A/B` for a phase fraction, `(A-B)/(A+B)` for a contrast — and can reference overlays: `A - ovl(bkg_empty)` maps the difference to a reference pattern. The displayed layer is picked with the radio button beside it or the Layer box below the map.

- **Repairable map grids.** The point list shows one row per grid cell, so a frame dropped by the beamline is visible and fixable: insert or remove blank cells, reorder rows by dragging or one step at a time, or leave a bad point out — it stays in the list, struck through, until it is put back. **Check filename numbering** finds missing file numbers and inserts a blank for each automatically. The Grid dialog accepts any grid size (not only exact factorizations of the point count) and adds **serpentine (snake) scans**, axis swapping and mirroring.

- The detector image sits beside the map controls while there is room, and moves into the tabs when the panel becomes too narrow for both.

- **Undo and redo work across the whole application**, not just the mask: Ctrl+Z / Ctrl+Shift+Z (Cmd on macOS) in every mode, with the buttons at the top of the left sidebar. Covered are settings of every kind, mask edits, calibration peak picking and refinement, loading images and patterns, overlays, phases, and the image corrections. One drag of a spinbox is one step, and undoing an image load brings the previous image and its mask back. The separate Undo buttons in mask mode and calibration are gone, as are the never-functional Ctrl+O/Ctrl+A mask shortcuts.

- **Calibration is now a step-by-step wizard** — 1. Image, 2. Pick Rings, 3. Calibrate, 4. Validation. Each page shows only what its step needs, completed steps can be revisited from the stepper, and loading an existing calibration jumps straight to validation.

- Picked calibration peaks can be managed in a table — reassign a group's ring, highlight it in the image, delete selected groups — instead of only clearing everything and starting over.

- The validation step shows image, cake and pattern side by side with a linked 2θ marker in all three, and overlays the calibrant's (and loaded phases') reflections in every view. Parameters can be fixed to chosen values before calibrating.

- Calibration parameters can be typed in directly ("Enter Manually") without a .poni file, and the wavelength can also be entered as an energy in keV.

- Setup values still at their shipped defaults — distance, wavelength, pixel size, calibrant — carry an orange border until confirmed, since a silently wrong default is the easiest way to a nonsense calibration.

- Calibration peaks are now saved in project files; they were previously lost on save.

- Project files are considerably smaller, and saving is atomic: an interrupted or failed save can no longer damage the existing file.

## Bugfixes

- Undoing an image load did nothing, and a second undo could not bring the first image back; the history could then drift from what was on screen.

- Undoing a picked calibration peak left the ring number advanced, so the next pick went to the wrong ring.

- Undoing and redoing a phase repainted it in a different colour each time; restored phases keep their colour.

- Loading a project into a session that already had phases or overlays added to them instead of replacing them, doubling them with every load.

- Copying a phase marked it as modified although nothing was edited.

- On macOS, drop-down boxes took an extra click before their list would stay open; the lists also open below the box now instead of covering the full screen height.

- The calibration view showed the literal text "position_lbl" until the mouse first moved over the image.

- After loading an existing calibration, Pick Rings showed as not started; steps a loaded calibration makes unnecessary now show as skipped, with a tooltip saying why.

- Values in disabled input fields were rendered so dim they were unreadable on the dark theme.

- Phase names in the pattern plot were drawn on top of the y-axis.

- The batch view labelled a missing calibration or mask file "undefined"; it now says "none loaded".

- The point masking tool's size and threshold fields were unlabelled numbers.

- The Bkg and X tabs of the integration view were cut off mid-control at small window heights.

- Empty calibration and batch views now say how to load data instead of showing a black void.

- Sporadic "wrapped C/C++ object has been deleted" errors coming from the plot labels are fixed.

- Updating the background region while batch data was loaded crashed.

## Appearance

- A consistent monochrome icon set replaces the coloured legacy icons across the overlay and phase lists, the batch toolbar, the detector panel and the mask plugin rows (which get a real settings gear, and a stamp for imprint instead of the letter "I"). Buttons that discard a whole list are red; the toggle buttons beside the pattern plot are grouped, carry tooltips, and show an amber fill when active.

# 0.8.7 (29.07.2026)

## New Features

- the map can be undocked into its own window, which keeps working whatever mode the main window shows; this makes it usable next to the integration view, where clicking a map point loads that image and integrates it with the settings set there — with the large image, the phase lines and all the usual controls at hand. The docked state is saved with the session

- while the map is undocked, the region that selects which part of the pattern it sums also appears in the integration pattern, so the map can be re-sliced without leaving that view; it converts between the displayed unit and the unit the map was integrated in, so it works in 2θ, Q and d

- the map selection marker now follows whichever image is loaded, so stepping through files anywhere in Dioptas moves it, and it hides for images that are not part of the map

## Improvements

- images are stored in their own dtype and compressed in project files, instead of being converted to 32-bit floats: a project holding a 2048² 16-bit image drops from about 17 MB to 4.5 MB, and reloading an image now returns exactly the data that was loaded (converting to float doubled the size of 16-bit detector data and lost precision above 16.7 million counts)

- the mask is stored compressed in project files (gzip level 1): a saved mask shrinks about 190x (4.2 MB to 22 KB for a 2048² detector, 18 MB to 0.12 MB for a 4M one), which also makes the session autosave far cheaper; gzip is a built-in HDF5 filter, so older Dioptas versions still read these files

- the mask undo/redo history stores bit-packed snapshots instead of full byte-per-pixel arrays, cutting its memory by 8x (about 900 MB to 113 MB for a 4M-pixel detector at the 50-step depth)

## Bugfixes

- switching on smoothing in the map hid the position, intensity and filename information below the map plot when hovering over it, because the smoothed image is upscaled and the mouse position was read in that upscaled grid

- checking whether a batch file contains processed data left the file open when reading it raised, which then blocked every later write to that file (same failure mode as the autosave handle leak)

- saving the session (autosave or on close) crashed with "Object of type bool is not JSON serializable" after restoring a previous session, because loading assigned numpy booleans from the project file into the settings; on top of that, the failed save leaked its open file handle, so every following autosave failed with "unable to truncate a file which is already open" — numpy scalars now serialize, and save/load always close the project file even when they fail partway

- the corrections panel layout was off after the parameter form rework: input fields stretched across the whole panel, tabs with only a few parameters spread their rows over the full height, and the plot buttons sat at the far right edge — fields now keep a compact width, rows are packed to the top, formula inputs line up with the parameter labels, and the plot buttons sit next to (or below) the values they belong to

- settings stored as tuples (the mask region of interest, phase colors) came back as lists after a project round-trip, because JSON has no tuple type

- adding a configuration renamed the calibration of both the new and the original configuration to "transfer" (the name of the temporary file the calibration is transferred through), which was then shown in the calibration label and saved into project files

- setting an integer intensity factor (e.g. from a script) silently wrapped uint16 image pixel values around; the factor is now coerced to float

- after loading a project or resetting, calibration parameter changes did not invalidate the cached multi-geometry, so combined patterns/cakes of multiple configurations could go stale

- map change signals were shared between all configurations (class-level), causing cross-configuration crosstalk; they are now per-instance and the map view follows the selected configuration

- the cBN seat correction GUI had crossed field wiring: the anvil and seat absorption length fields fed each other's parameters, and restoring a project scrambled the center offset and absorption length fields

- the pattern axis labels and unit buttons could go stale when switching to a configuration with a different integration unit (the previous unit was shadow-copied in the controller)

- the batch view's d-spacing display now inverts the x-axis like the pattern plot

## Distribution

- 0.8.6 never reached PyPI: the Apple-silicon wheel failed because Homebrew's OpenMP library requires a newer macOS than the wheel was tagged for, and the Intel wheel job waited 24 hours for a runner that GitHub has retired — with one wheel job failing, the publishing step was skipped without the release run drawing attention to it. The Apple-silicon wheel is now built for macOS 14 and later, the Intel wheel is built on a current runner without OpenMP (so it keeps working on older macOS, with the spot mask running serially), and a final check now fails the release run if publishing did not happen

- updated pillow (12.3.0), lxml (6.1.1), pygments (2.20.0) and setuptools (83.0.0) to resolve security advisories

- added psygnal (>=0.15.1) as a dependency

## Internal

- restoring settings from a project file no longer needs per-field code: the generic params documents are applied wholesale on top of the legacy restore, so any settings field added in future round-trips automatically

- the periodic session backup now only writes when something actually changed, instead of rewriting the whole project (including image data) every ten minutes in an idle session; closing Dioptas still saves unconditionally

- the remaining hand-written `update_gui` pushes (mask transparency radio buttons, the integration view's mask/transparency/autoprocess widgets and calibration label, the configuration factor field) are now declarative bindings; the binder gained number-field and radio-pair binding kinds

- the automatic (smooth Bruckner) background settings — smoothing width, iterations, polynomial order and the fitted x-range — are now canonical evented state in `PatternParams` with the pattern model pushing them into the pattern computation, instead of living in spinboxes and inside xypattern's internals; project save/load no longer reaches into those internals, and the range restored from a project is no longer clamped against whichever pattern happens to be loaded at that moment

- `Configuration.copy()` now copies every setting generically instead of a hand-picked subset (it silently dropped the mask usage, integration unit, cake settings and auto-integrate flags)
- the integration window layout mode, image dock state and overlay waterfall separation moved into the evented view state and are now saved in project files; the auto-create-pattern checkbox is bound to the persisted setting, so loading a project restores it (it previously always showed unchecked)

- settings writes are now uniform: side effects (re-integration, watcher activation, background recalculation, overlay pattern math) moved from property setters into params event subscriptions, so writing `params.<field>` directly behaves exactly like the property write for every writer (GUI, scripts, pipeline); the headless pipeline uses the hold() mechanism for its deliberately integration-free writes

- ImgModel's settings (autoprocess, factor, background scaling/offset, file iteration mode) moved into an evented `ImgParams` dataclass following the no-state-in-models direction; the file iteration mode is now persisted in project files (previously lost on save); img params changes surface on `configuration_params_changed` with an `img.` prefix, and the background image scale/offset spinboxes bind reactively to them
- PatternModel's settings (unit, file iteration mode) moved into an evented `PatternParams` dataclass, surfacing on `configuration_params_changed` with a `pattern.` prefix and saved generically in the project file's pattern group
- MaskModel's settings (drawing mode, ROI) moved into an evented `MaskParams` dataclass with a `mask.` prefix on the store surface; the mask/unmask drawing mode is now persisted in project files (previously lost on save)
- CalibrationModel's settings (start values, fit wavelength, fixed refinement values, use mask, polarization factor, supersampling, solid angle correction, distortion spline, dioptrin usage) moved into an evented `CalibrationParams` dataclass with a `calibration.` prefix; the calibration workflow settings (start values, fit/fixed flags) are now persisted in project files, while the machine-specific dioptrin settings are deliberately not restored on load; removed the dead `fit_distance` attribute (the distance checkbox acts through the fixed refinement values)
- image transformations are now stored canonically as a name list in `ImgParams.transformations` with the callable list derived from it; MapModel's window/dimension moved into `MapParams` (`map.` prefix) and PhaseModel's same-conditions flag into `PhaseParams` (`phase.` prefix, global — forwarded without rewiring); the same-conditions flag is now persisted in project files
- per-item display state moved into evented params: each overlay's name/color/visibility/scaling/offset lives in an `OverlayItemParams` (scaling and offset write through to the underlying pattern math), and each phase's color/visibility in a `PhaseItemParams` — replacing the parallel `phase_colors`/`phase_visible` lists, which remain as read-only views; per-item params documents are saved in each overlay/phase group of the project file

- the model Signal class is now backed by psygnal, gaining batched/paused emission while keeping the existing API
- introduced an evented parameter dataclass layer (`dioptas.model.state`): Configuration settings now live in a `ConfigurationParams` object that is saved generically into project files; the 1D azimuth range and trim-trailing-zeros settings are now persisted (they were previously lost on save)
- pattern/cake integration and the combined cake are now derived computations (`Derived`) with a single suppression primitive (`hold()`); this replaces the auto_integrate connect/disconnect cycling, the temporary flag-toggling dances in model and controllers, and the multiple-file-loading signal rewiring
- project files now carry an explicit `format_version` root attribute; the versioning policy for .dio files (application version vs. layout version vs. params encoding version) is documented in `dioptas/model/state/hdf5.py`, and files written by newer Dioptas versions load best-effort instead of failing
- added a declarative widget-binding layer (`dioptas/controller/binding.py`): bindings declare model→widget rendering (with widget signals blocked automatically) and widget→model writes once, replacing hand-written update_gui methods and their blockSignals sandwiches; Options, Background, Calibration, Pattern, Batch and Correction controllers are migrated
- the integration unit now has a single write path with a model-level `integration_unit_changed` signal; the pattern and batch views react to it instead of double-handling the same button clicks
- correction parameters are edited in named form fields (`ParameterFormWidget`) instead of table cells addressed by row index
- the image/cake view mode moved from a widget attribute into evented view state (`ViewParams.img_mode` on the model); the mode switch runs in reaction to state changes, and the view mode is now saved in and restored from project files
- added a store-level settings-change surface: `DioptasModel.configuration_params_changed` emits `(field, new, old)` for every settings change of the current configuration, and widget bindings re-render individually on matching field events — settings changed from scripts or other controllers now appear in the GUI immediately
# 0.8.6 (27.07.2026)

## New Features

- added Spot Mask plugin for detecting and masking single-crystal diffraction spots in powder data using per-2θ-bin median+MAD outlier statistics, with optional fast mean+std method (algorithm based on AlbertVong/XRD-Powder-Mask)
- added geometry support to the mask plugin interface — plugins can declare `needs_geometry = True` to receive calibration parameters (2θ/azimuth arrays, beam center, wavelength, etc.)
- mask plugins can now receive the user-drawn mask via `existing_mask` to exclude pre-masked pixels (e.g., detector gaps) from their statistics
- added info icons next to plugin settings parameters with instant-on-hover descriptions
- added imprint button to each plugin row that bakes the current plugin mask into the user-drawn mask and disables the plugin (full undo/redo support — undoing an imprint reverts the mask and re-enables the plugin)
- added Ctrl/Cmd + Left/Right keyboard shortcut to load previous/next image in all modules; the existing pattern position-line shortcut in Integration mode now requires the Alt modifier (Alt + Left/Right, with Shift or Ctrl/Cmd for ×10 or fractional steps)
- added geometry diagrams to the slab, cylinder, and plate absorption correction tabs illustrating beam direction, tilt/rotation conventions, and the coordinate system
- correction tabs now show a bullet indicator when the corresponding correction is enabled, making active corrections visible without switching tabs

## Bugfixes

- fixed Save Pattern and Save Combined Pattern dialogs not remembering the last directory between saves
- fixed plugins not recomputing when the user draws a new mask (detector gaps were ignored until next image load)
- fixed infinite recursion when drawing masks with dynamic or geometry-aware plugins enabled
- fixed Spot Mask bleeding across narrow detector gaps when smoothing parameters were tuned aggressively
- fixed Spot Mask raising `UnboundLocalError` and disabling itself when smoothing was enabled and the user mask was empty

## Distribution

- PyPI releases now ship binary wheels for Linux, Windows, and macOS (x86_64 and arm64) on Python 3.11–3.13, so the accelerated Spot Mask C extension is available without a compiler
- the C extension build is now optional when installing from source — `pip install dioptas` falls back to the pure NumPy implementation if no compiler is available

# 0.8.5 (12.04.2026)

## New Features

- added mask plugin system for extensible automated masking — supports static (per-shape) and dynamic (per-image) plugins with configurable settings, discoverable via Python entry points or `~/.dioptas/plugins/masks/` directory
- added built-in Threshold Mask plugin for masking pixels above/below configurable intensity limits
- added built-in Cosmic Ray Mask plugin for detecting cosmic ray artifacts using local z-score statistics with iterative filtering
- added flat field correction support for compensating pixel-to-pixel sensitivity variations
- plugin settings dialogs show algorithm description, masked pixel count, and update the mask live as parameters are changed
- added startup update checker that notifies users when a new Dioptas version is available on GitHub

## Bugfixes

- fixed mask plugin overlays not showing in Integration and Calibration views
- fixed project save baking dynamic plugin masks into the static mask data — now only saves user-drawn mask and persists plugin enabled state and settings separately
- fixed plugin checkbox state not updating after loading a project
- fixed calibration peak search not using plugin masks
- fixed xraydb.sqlite not included in PyInstaller bundle, causing all absorption corrections to fail in released executables

## Distribution

- added Windows installer (Inno Setup) — no admin required, installs to user AppData
- added macOS DMG installer with drag-to-Applications layout
- added Linux AppImage for single-file portable distribution

## Documentation

- added Mask Plugins documentation page with plugin authoring guide, installation methods, settings schema reference, and API reference

# 0.8.4 (25.03.2026)

## New Features

- added headless scripting API (`dioptas.pipeline.Pipeline`) for integration from Python scripts and Jupyter notebooks — load full setup from `.dio` project files, integrate single or batch images without the GUI
- added slab sample absorption correction with depth-integrated Busing & Levy (1957) formula — supports tilted slabs, automatic μ calculation from chemical formula via xraydb
- added cylinder sample absorption correction with numerical integration over beam footprint (Paalman & Pings, 1962) — supports axis orientation, variable beam width (pencil beam to full illumination), and optional glass capillary container correction
- added sphere sample absorption correction with pencil beam and finite beam modes — appropriate for synchrotron experiments with small beams on large ball samples
- added plate sample absorption correction for flat plate samples in Debye-Scherrer geometry
- added beam_width parameter to cylinder and sphere corrections for continuous control between pencil beam and full illumination
- added xraydb dependency for automatic calculation of linear absorption coefficients from chemical formula and X-ray energy
- added GUI tabs for slab, cylinder, sphere, and plate corrections in the Corrections panel with formula input, automatic μ calculation, and Plot button
- added centralized logging system with in-memory ring buffer — recent activity log is shown in crash dialog for better bug reports; configurable via `DIOPTAS_LOG_LEVEL` and `DIOPTAS_LOG_FILE` environment variables
- save/load all absorption corrections (slab, cylinder, sphere, plate), supersampling factor, and overlay/phase colors and visibility in `.dio` project files

## Bugfixes

- fixed non-ASCII (Chinese, accented, etc.) characters in file paths — batch processing and project save/load now correctly preserve Unicode filenames via UTF-8 HDF5 strings
- fixed mask cleared when enabling correction after loading `.dio` project
- fixed `cake_azimuth_range` comparison crash on numpy arrays when loading projects
- fixed file format loading returning byte ordinals instead of characters in project files
- fixed overlay visibility checkbox not updating when moving overlays up or down
- improved error handling: replaced silent `except: pass` blocks with proper logging across the model layer, narrowed bare `except:` to specific exception types

## Code Quality

- added type hints to the entire model layer (23 files) — all method signatures, instance attributes, and return types annotated with Python 3.11+ syntax
- modernized class definitions across the entire codebase (55 files) — replaced `class Foo(object):` with `class Foo:` and `super(ClassName, self)` with `super()`
- removed Qt dependencies from the model layer
- cleaned up docstrings: removed redundant `:type:` and `:param X: type` annotations where type hints are now in the signature

## Testing

- added pytest-cov for test coverage reporting in CI
- increased model layer test coverage from 70% to 78% with 120 new unit tests
- added 7 unit tests for Unicode file path handling
- dropped Python 3.9/3.10 from CI matrix (unsupported since `requires-python >= 3.11`)
- consolidated CI_frontend into single pytest invocation for faster runs
- changed pytest default from `-sv` (noisy) to `-v --tb=short` (clean)

## Documentation

- rewrote all documentation pages for v0.8.3 with updated content covering Map module, batch processing, Log/Sqrt scaling, Transfer Function correction, and all new features
- captured fresh screenshots with current dark material theme
- added new Map module documentation page
- added Scripting API documentation page with full reference and examples
- added auto-generated API reference using Sphinx autodoc for Pipeline, all model classes, corrections, and utilities
- added `.readthedocs.yaml` and switched to sphinx_rtd_theme for ReadTheDocs builds
- added equations and references (Busing & Levy 1957, Paalman & Pings 1962) to absorption correction documentation

# 0.8.3 (stable 20.03.2026)

## New Features

- added mask_changed signal to MaskModel, decoupling mask display updates from image updates across all modes
- calibration peak picking now highlights peaks belonging to the currently selected ring in a different color
- added "Clear Ring" button in calibration mode to delete all picked peaks for the current ring
- calibration mode "use mask" checkbox now sets the per-configuration use_mask flag, keeping it in sync with integration mode

## Bugfixes

- fixed mask display not updating correctly when switching configurations in mask, calibration, and integration modes
- fixed mask checkbox and transparency state not syncing when switching configurations in calibration mode
- fixed mask disappearing when switching to mask mode due to stale image data on the widget
- fixed threshold masking (above/below) ignoring the mask/unmask radio button selection
- fixed mask data being destroyed when switching configurations due to unnecessary dimension reset
- fixed MultiGeometry cache not invalidating when calibration parameters or detector shape changed

## Other

- added CI release workflow that creates GitHub releases with executables on tag push
- existing build workflows now only run on branch pushes to avoid duplicate builds on tags

# 0.8.2 (stable 17.03.2026)

## Improvements

- use pyFAI MultiGeometry for combining patterns and cakes across multiple configurations, replacing the previous stitching/interpolation approach with proper weighted averaging

# 0.8.1 (stable 05.03.2026)

## Bugfixes

- fixed parallel bitshuffle decompression failing for HDF5 files with multi-byte dtypes (e.g. int32) — the chunk header block size was incorrectly passed in bytes instead of elements, causing map loading to crash

# 0.8.0 (stable 04.03.2026)

## New Features

- map state (positions, integrated data) is now saved and restored in .dio project files
- added "Reintegrate" checkbox to map widget
- added contour line overlay to map image with smooth cubic upsampling
- added smooth/interpolated map image toggle with adjustable zoom-based smoothing
- added log/sqrt y-axis scaling toggles for pattern plot
- added autoscale toggle button to map image
- added "Match intensity" right-click context menu to overlay table for automatic overlay scaling to match the current pattern
- overlay scale and offset step spinboxes now allow finer steps (down to 0.0001) and display only significant digits
- improved default intensity scaling of images - based on percentile values instead of min/max to avoid outliers dominating the scaling
- colormap popup now introduces a percentile-based slider to adjust this percentile scale
- improved batch integration progress dialog
- added Dioptrin as alternative integration backend for significantly faster integration performance, including parallel bitshuffle decompression for hdf5 files (this requires Dioptrin license)

## Bugfixes

- frame navigation in multi-frame files (HDF5, etc.) now works after loading a project
- desktop shortcut creation now works on macOS
- stale mask is hidden when image shape changes
- mask is correctly fetched after loading first file in map batch integration
- resolved pyFAI 2025.10 deprecation warnings
- fixed image shape mismatch handling to prevent crashes

## Other

- relicensed from GPL-3.0 to MIT
- removed legacy MapModel and renamed MapModel2 to MapModel
- upgraded Pillow to fix CVE-2026-25990

# 0.7.2 (stable 10.01.2026)

## Bugfixes

- orientation from ponifiles is now correctly saved in a dioptas project file - thus, upon reloading it still works
- masking an arc is now more robust and will not cause error messages
- mouse hovering over not-yet-integrated pixels in the map will not cause an error anymore

## Build

- switched from poetry to uv


# 0.7.1 (stable 03.04.2025)

## Bugfixes

- fixes python 3.9 compatibility
- fixes an issue with installation of a dependency of extra_data on windows (zlib-*). extra_data is now only installed on Linux. This means files generated directly by karabo at EUXFEL will not be able to be loaded in Dioptas on Windows and Mac OS X. The main reason is that extra_data is primarily developed for EuXFEL users using linux. They do not actively support other platforms.


# 0.7.0 (stable 01.04.2025)

## New Features

- adding python 3.13 compatibility
- compatibility with pyFAI 2025.3.0 - this includes a new poni file format and a new way of handling detector orientation. Resulting in transferability of poni files between Dioptas and scripts written with pyFAI without the need to flip the image upside down.

## Bugfixes

- fixes issues on some system with a newer watchdog installation (above 3.0)
- adds 'tiff' files to autoprocessing
- images in hdf5 files which can not be handled by fabio are now also loaded flipped upside down (as it is for all other file types). This ensures compatibility of orientation with Fit2D parameters.
- the same treatment as for hdf5 files is now also applied to karabo files.

**ATTENTION**: This might change the orientation of your data and is a breaking change. If you load a calibration file created in a dioptas version prior to 0.7.0 in combination with hdf5 files (e.g. from ESRF) or karabo files (e.g. from EuXFEL) and want to keep the original orientation, you need to flip the image upside down manually. (This can be done by clicking the "Flip vertical" button in the calibration view under calibration parameters on the right. Once clicked the flipping will be applied to all images loaded from that point on).

# 0.6.1 (18.06.2024)

## New Features

- maps can now be saved as png, tiff or txt files.

## Bug Fixes

- fixes a problem which occured when saving a list of phases with non english locale setting
  (e.g. comma as decimal separator)
- autosaving integrated patterns with activated background subtraction is working again

# 0.6.0 (10.04.2024)

Codewise this is the biggest upgrade since the release of Dioptas. Over 3000 commits (changes) since 0.5.9
have been made.

## New Features

    - Complete GUI overhaul with a Material inspired design
    - Added a new Map Mode for exploring data collected in a 2D grid
    - Multiple files loaded can now be averaged (new batch mode average selection availlable)
    - added the option to add custom "external actions" via providing json file upon start of Dioptas. This allows to
      add custom actions to the main window, which can be used to start external programs or scripts. The commands will
      be executed with two addidtional arguments, the path to the currently loaded image file and the current frame
      number. The external action buttons are appearing on the lower left of the main window.

## Bug Fixes

    - fixed some issues related to memory when using HDF5 files
    - clicking calibrate without having defined peaks will result in a critical message box and
      not an error anymore
    - when the automatic refinement will not find any points it will show a critical message
      box with this information and the program does not show an error
    - many small improvements

# 0.5.9 (stable 13.11.2023)

## New Features

    - Intensity scaling is now persistent across Calibration, Mask and Integration tab
    - Additional configuration available  the scaling of images

## Bug Fixes

    - autoscaling images with detector gaps and large values in them (e.g. ESRF Dectris data) will now automatically ignore
      these gaps
    - when importing cifs all rhombohedral space groups can now also be in a hexagonal setting (was previously only possible for 167)

# 0.5.8 (stable 29.09.2023)

## New features:

    - scale menu next to the image color scale (Thanks to @t20100)
        - can be opened by clicking the gear wheel
        - allows for manual selection of minimum and maximum values
        - scaling can be set to logarithmic and square root (default is linear)
        - extra button to redo the autoscaling
    - autoscale implementation is now better working with large values (e.g. ESRF Dectris Eiger images)
      (Thanks to @t20100)

## Bug Fixes:

    - fix issues with type of the radial bin number being float instead of int -> this caused issues with the
      integration of cake when setting a manual radial bin number
    - cosmic removal is now working again
    - fixes issue with auto peak number increasing while the checkbox for it was unchecked
    - no more error message when mouse is hovering over the cake image at 0 indices of the image
    - changing the color of an overlay or phase item is now working correctly again
    - the mask is now correctly reset when batch integration is started with images of different shape

# 0.5.7 (stable 24.04.2023)

## New features:

    - saving in batch window will now also save background subtracted patterns, if enabled in the pattern widget
    - upgraded dependency pyqt5 to pyqt6 which should result in improvements for high dpi screens
    - added a new "integrate" button to the batch widget, which will integrate all images in the batch widget
    - now compatible with python 3.11, whenever possible the created executables are compiled with python 3.11
    - dropping support for python 3.6, 3.7 and 3.8 and focussing on compatibility with python 3.9, 3.10 and 3.11

## Bug Fixes:

    - fix numpy float conversion issue due to deprecated numpy.float
    - reading cif files with missing volume tag will now work correctly and the volume will be calculated from cell
      parameters (PR #140, thanks to @ScottNotFound)

# 0.5.6 (stable 23.11.2022)

    - Removed image files from pypi distribution.

# 0.5.5 (stable 22.11.2022)

## New Features:

    - added a normalize button to the batch widget, which will normalize all batch integrated patterns
      to the starting area (i.e. the first 10-30 values of the pattern)
    - batch integration starts immediate after selecting the files
    - added browsing between folders in batch widget

## Bug Fixes:

    - fixed issue with image transformations (rotations and flips)
    - fix issues with font size on some high dpi settings in white text boxes
    - improve resize behavior (dragging the splitter) in the integration view
    - fixed issue with resizing batch widget when filepaths were long

# 0 .5.4 (stable 20.12.2021)

## New Features:

    - made openGL dependency for Batch widget addition optional. --> this means executables are now working properly
      under Mac OS X again
    - Batch waterfall plot is now possible with background subtraction enabled
    - Batch heatmap can now be trimmed along x axis (new T Button) - region of trimming is synchronized with the
      main Dioptas background controls
    - improvements on Batch widget interface - buttons are now only visible when necessary, added more tooltips,
      slightly redesigned gui, improved background calculation with d-spacing as axis unit

## Bug Fixes:

    - fixes issue with mask button toggle when in cake mode
    - fixes the error appearing when clicking into the cake image in the integration window
    - fixes axes not updating when zooming in and out in cake widget and batch widget
    - fixes background subtraction as shown in contour plot of Batch widget (2D view) and in waterfall/overlays 1D
      representation of the main Dioptas window
    - fixes switching between x-axis units (2th, d-spacing, Q) in Batch widget
    - fixes intensity estimation in Batch widget (lower right corner) when background subtraction is activated.
    - fixes issues with representation of phases inside the contour plot of Batch widget, e.g. resetting of the
      "Show Phases" button state upon file information reloading, updating position of the phases upon user input, etc
    - sources selection box is not shown in pattern control widget anymore
    - tth/q/d vertical green line position is now correctly synchronized between image, cake, pattern and batch widget

# 0.5.3a (stable 10/10/2021)

## New Features:

    - pip package has now the correct dependencies

## Bug Fixes:

    - small bug fixes for batch integration (checks whether calibration or mask is loaded)

# 0.5.3 (stable 10/04/2021)

## New Features:

    - added a batch integration view (thanks to hard work of Mikhail Karnevskiy @ DESY). Here you can batch integrate
      your collection series and interact with a contour or 3D plot of the integrated patterns -> this also includes
      visualization of phases lines
    - reading ESRF hdf5 data files is now possible
    - combined patterns from multiple configurations can now be saved as a file (save button on the upper right)

## Bug Fixes:

    - no longer remove integrated intensities below 0, instead now only values with equal to 0 are removed
      (this should fix all the issues with background corrected images)
    - reimplemented the automatic file recognition algorithm of the autoprocess integration function. This should now
      work much more reliable also on network drives and linux systems
    - QT high dpi scaling is now only activated for Windows and Mac OS X -> Disabling it on Linux fixes the display bugs
      encountered here and it is usable with low and high dpi screens (it was not working correctly)

# 0.5.2 (stable 11/26/2020)

## New Features:

    - Added an azimuthal histogram for the cake view, please check the X-Tab in the integration view to change the
      integration bins in 2 theta direction
    - Azimuthal range for 1d integration can now be set in the X-Tab

## Bug Fixes:

    - fix calibration algorithm, which was currently failing most of the time for difficult geometries. It should now
      work correctly again as in 0.5.0
    - fix display bug which was showing horizontal scroll bar in "calibration parameters" on some linux systems
    - disable QT high dpi mode for Linux platforms, which was causing very tiny font sizes. It is working correctly
      without it
    - fixed pixel width/height definition in the detector calibration definition (it was applied interchanged)

# 0.5.1 (stable 05/05/2020)

## New Features:

    - Phase lines can now be shown in the Cake Widget. Intensity is shown as thickness and opacity of the lines.
    - Phase line parameters can now be copied out of the jcpds widget by using ctrl+c and used directly in your
      preferred table/text editor
    - Added a Detector Groupbox in the Calibration Widget. Predefined Detectors can now be loaded as well as Nexus
      Detector files. This enables to load e.g. Nexus detector h5 files which include positions for each pixel.
      (distortion correction and also useful for combined detector modules not adjacent to each other).
    - Added a Continuous Delivery Pipelines, which automatically create executables for all operating systems
      (Thanks to Github Actions)

## Bug Fixes:

    - having parameters fixed during calibration works now correctly
    - the refine button now also works without automatic refinement and with just a calibration loaded from a file
    - reading trigonal rhombic cif files works now correctly
    - setting the dk/dT parameter now changes the Bulk Modulus of a phase. This parameter was previously ignored.
    - entering the range for the automatic background subtraction works now correctly
    - the motor setup widget is now not showing anymore after starting Dioptas on OS X
    - fixed double logarithm for the intensity distribution display histogram
    - (re)loading of a project with image transformations should now work correctly
    - loading cif files with the newer '_space_group_IT_number' representation work now correctly
    - green line in cake widget is now shown correctly upon reloading dioptas

# 0.5.0 (stable 03/05/2019)

## New Features:

    - Added the capability of using detector distortion correction defined by spline files generated from Fit2D (please
      see the calibration parameters)
    - PONI and rotation parameters can now be fixed during the calibration
    - redesigned parts of the GUI: (1) the top controls in the Integration view no adapt to the used width, and split
      into two groups to make use of the space. (2) Overlay and Phase Control Widgets now are mainly controlled by
      buttons and the important parameter can be changed for each item individually in the table. (3) There is now a
      a different view mode for the integration view, where image and integrated pattern are shown on the left, and all
      control panels are on the right. This can be activated by using the change view button on the lower left.
    - the cBN Seat Correction and Detector Incidence Absoprtion Correction Controls have been redesigned
    - Added the option to use a transfer correction for image intensities. Please see the Cor tab in the integration
      view
    - azimuthal bins and azimuthal range for the cake integration can now be adjusted manually in the X tab
    - the cake image can now be exported (press the save button below the image)
    - auto-extracted Pattern background can now be saved as file or later reused as overlay
    - the background subtraction algorithm is now also rewritten in cython, which should make deployment easier
    - a button was added to undo the last peak selection in the calibration tab
    - the jcpds editor now also shows q-values for each line

## Bug Fixes:

    - cosmic removal in the mask panel is now working again
    - changing the radial bins in the X tab in the integration view works now correctly again
    - phases with trigonal symmetry should now work correctly
    - saved background range should now correctly restore after restarting Dioptas
    - browsing files works now correctly from 10 to 9 without leading zeros
    - loading a *.poni file prior to an image will not result in an error message anymore

# 0.4.1 (stable 12/22/2017)

## New Features:

    - easier step selection for pressure, temperature in the phases widget and scaling and offset in the overlay widget,
      the steps are now selected by a spinbox which behaves more or less logarithmically (0.1, 1, 5, 10, 50, 100 etc.)
    - the solid angle correction can now be switched off and on (please see the X-tab in the Integration View)

## Bug Fixes:

    - Overlays overlays are now recovered in order when opening a previously saved project with more than 10 overlays
    - cif and jcpds now als can handle trigonal symmetry (not only hexagonal)
    - auto zoom for cakes works now correctly when browsing through several files
    - entering numbers with a "," as a decimal separator work now correctly
    - loading new files with automatic background subtraction enabled will now correctly keep the x limits constant

# 0.4.0 (stable 07/26/2017)

## New Features:

    - added the possibility to work with multiple detector configurations at the same time (enabled by the C button on  the upper left)
    - all your work (including mutliple configurations) can be saved into project files
    - Dioptas can restore the previous working session on start
    - there is now a Dioptas icon instead of the generic python icon
    - unmasking geometric shapes are now green instead of red, to clarify which mode is selected
    - added the option to use arcs for masking
    - Dioptas is now completely Python 3.5/3.6 compatible
    - Dioptas can now save pattern files as "FXYE" files (GSAS-II format)
    - background subtracted or other modified (absorption correction etc.) Images can now be saved in batch mode
    - lists of phases including their pressure and temperature values can now be saved and loaded
    - the cake mode in the integration window now shows azimuth and tth/q axes
    - the cake image can now be shifted in azimuth, to have a better possibility to view features which where before only at the edges

## Bug Fixes:

    - fixed issues with changing units when having automatic background subtraction enabled
    - strong zooming into pattern view will not cause an error due to rescaling of the phase lines anymore
    - fixed issue with compromised Dioptas settings files, Dioptas will now start even if the settings can't be loaded
    - fixed strange masking artifacts at the edges when using the polygon masking tool
    - fixed undock/dock process, which was not working propoerly (only image was shown without pattern after docking the img widget
    - fixed image view scaling when loading differently sized images or switching between cake and image mode
    - fixed the CeO2 calibration file (there was a (9,0,0) reflection, which does not exist, instead at close position here should be a (8, 4, 0) reflection)

# 0.3.1 (stable 4/21/2016)

## New Features:

    - added compatibility for *.spe files (from Princeton instruments).
    - added capability for beamlines using epics and Image Tags to move to the position where the image was collected
    - added a new error Dialog which will popup on any error and show the error message, which then can be send to
    clemens.prescher@gmail.com, so I can fix it

## Bug Fixes:

    - cif files with errors in atomic coordinates can now be loaded too
    - adding AMCSD cif compatibility
    - fixed an error with file paths on windows causing it to not load any cif files
    - fixed some typos
    - fixing bug with fit2d parameter input
    - fixing bug with background image loading

# 0.3.0 (stable 02/11/2016)

## New Features:

    - It is now possible to load *.cif files in the Phase tab in the integration module. Loading a cif file will
      automatically calculate the intensities of all hkl with a given minimum intensity and minimum d spacing.
    - Dioptas can now load tiff tags and display them in a separate window. This is very practical if the beamline
      setup writes extra information as tags into the tif file such as position or exposure time etc.
    - The overlay tab has a new waterfall feature which automatically creates a waterfall plot with a given offset of
      all loaded overlays, whereby the most recent one is closest to the current integrated pattern.
    - the selected region and image shading is now synchronized between the calibration, mask and image view
    - negative pressures are now allowed for phases, although unphysical, it might give some hint when searching for a
      matching structure. The bulk modulus here is kept constant with pressures below 0. (Since the Birch Murnaghan EOS
      misbehaves at these conditions).
    - There is now a white cross marking the clicked position on the image in the Integration module. This marker will
      move to the corresponding position when switching between 'cake' and 'image' mode. This allows for tracking of
      individual peaks easily.
    - The default filename for the "save mask", "save pattern" and "save image" file dialogs will be the current image
      basename with the appropriate extension.
    - Added a lot more calibrants from pyFAI library. All NIST calibrants should be present with the appropriate
      references in the files.
    - Dioptas has been completely refactored by rewriting almost all of the GUI code, which will make future releases
      much faster, so stay tuned

## Bug Fixes:

    - mar345 files are now correctly loaded
    - autoprocessing of files, i.e. automatically loading newly collected files should now be much more reliable and
      especially the check for new files takes much less network bandwidth
    - jcpds editor content is now properly updated with the values of a newly added phase, which will be the new
      selected one
    - calculation of d-spacings for monoclinic space group jcpds is now correct, there was a sign error in the last term

# 0.2.4 (stable 04/13/2015)

## New Features:

    - Gui reorganization in the integration view: (1) autoscale button and transparent mask button are now shown within
      the image view. (2) the quick action buttons save image, save pattern etc. are now shown in the pattern widget
    - automatic background subtraction under BKG tab in the integration window. can also be accessed from
      the bg button in the pattern widget. By pressing inspect it shows both the original pattern and background
      within the limits for the extraction process. Please adjust the parameters according to your data.
    - File browsing step can now be modified to be different from 1 by entering an integer in the step text field
      below the arrows.
    - The absorption lengths for the diamond and seat corrections can now be adjusted. (They should be chosen according
      to the energy used for the XRD experiment)

# 0.2.3 (stable 12/09/2014)

## New Features:

    - Dioptas now saves the calibration when closing and will automatically open after restarting the program
    - mask files are now saved in a compressed tif format which reduces the file size from before 16 Mb to now less than
      40 kb
    - Added the option to use "Oblique Incidence Angle Detector Absorption correction", which basically corrects for the
      angle dependent path length in the detector scintillator and tries to correct the intensities correspondingly.
      This is especially useful at very high energies.
    - the cBN seat correction has been upgraded to include an Offset and Offset tilt parameter which corrects for
      misalignment of the sample in respect to the cBN seat
    - both, cBN seat correction and Oblique Incidence Angle Detector Absorption correction have been moved to a new tab
      ("Cor") in the Integration window

## Bug Fixes

    - fixed a bug which was causing Dioptas to crash when auto-processing new files and the rate of new files in the folder
      was faster than Dioptas could process them
    - fixed a bug which was causing the first calibration to fail for images with a different pixel size than 79um
    - fixed a bug which was causing the pixel size not to update when loading a calibration "*.poni" file
    - fixed a bug which was producing NAN intensity values in saved spectra when using masks

# 0.2.2 (stable 10/22/2014)

## New Features

    - defining an image as background prior to integration has been implemented. The controls can be found in the Bkg
        tab in the integration widget
    - it is now possible to do an absorption correction for cBN seats based on the geometry and rotation of the cell.
        Further details of the calculation can be found in the manual.
    - the pressure of each phase is now shown next to it in the pattern view and not only in the phase tab.
    - the image window in the integration widget can now be undocked, which creates a separate window for the image
        view whereby the windows are still connected (the green line). This enables the use of Dioptas over 2 Monitors
        for having a better overview.

## Bug Fixes

    - It is now possible to load images with different shapes, after calibration has been done. Although you might wanna
      use a different calibration for different detectors/images.
    - The gui has been updated to look reasonable good also on OS X 10.10 Yosemite.

# 0.2.1 (stable 09/09/2014)

## New Features

    - in the "X"-tab in the integration widget there are now two new options for integration available
    - it is now possible to change the number of bins for integration in the GUI (under X). After each change to the
        number the pattern will be integrated again automatically, to see the effects of different bin numbers easily.
    - the standard number of bin has been increased by a factor of approximately 0.9
    - additionally, the images can now be supersampled, up to a factor of 5. Supersampling divides a pixel into equal
        area subpixel which leads in the end to a smoother pattern. A supersampling factor of 2 will divide each pixel
        into four subpixel, a factor of 3 into 9 and so on. Depending on the initial image size the integration of the
        supersampled image can take very long (especially the first integration where the lookup table/sparse matrix is
        created). To reset the supersampling just type 1 into the spinbox.
    - the available pattern file formats checkboxes have been moved from the X menu to Spec to be more easily visible
    - the speed of the calibration procedure has been improved
    - it is now possible to leave the detector distance constant during calibration (Warning: This is the pyFAI geometry
        detector distance, not the fit2d detector distance. The Fit2D detector distance could still vary a little bit
        during the calibration procedure due to the different geometries of Fit2D and pyFAI)

## Bug Fixes:

    - MAC version - fixed a bug which caused the image to be flipped vertically
    - Polarization correction - fixed a bug which either caused the polarization correction to not be applied or being
                                with the wrong sign. Checked now everything again against Fit2D and should be working
                                correctly
    - Saving the pattern in the vector based .svg format is now working

# 0.2.0 (stable 08/29/2014)

    - Finished the JCPDS editor (pops up when you select a phase and select edit)
    - Fixed several small bugs using jcpds files (triclinic works now)
    - added inverse grey scale to the available image color scales

# 0.1.5 (stable 08/20/2014)

## Bug Fixes:

    - Fixed the header format of xy files in windows
    - .xy header now correctly shows the polarization factor
    - the temperature step in the user interface for phases now correctly changes the step of the temperature spin box
    - erroneous jcpds files will now give an error messagebox and will be handled correctly - no restart needed anymore

# 0.1.4 (stable 08/10/2014)

## New Features:

    - spectra can now be saved in .xy, .chi and dat format
    - they can be selected for automatic creation of pattern files when loading images

## Bug Fixes:

    - auto - creation of pattern now also works when the folder was inserted by typing it into the line item.
    - loading a new file was always creating an index by time of all the files, which slowed down the loading of new files
      considerably. - this is now done only once when loading a file from a new folder
    - setting the image working directory by typing it into the textfield now works correctly
    - changing the working directory while having enabled autoprocess will not load a file automatically anymore
    - the selection color in tables of integration view has been changed to orange, in order to overcome the visibility
      problem of the Checkboxes on Windows
    - browsing in cake mode did reset the integrator everytime which made it very slow. Fixed this bug, browsing in cake
      mode should now be almost as fast as only using integration

# 0.1.3 (stable 08/05/2014)

## New Features

    - implemented option to use mask for calibration refinement

## Bug Fixes:

    - fixed a bug when using phase lines which caused the pattern plot to flow

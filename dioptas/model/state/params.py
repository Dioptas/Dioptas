# SPDX-License-Identifier: MIT

"""Evented parameter dataclasses — the serializable settings layer.

Params classes hold everything the user can set, as opposed to loaded data
(images, patterns) or derived results (integrated patterns, cakes). They are
plain dataclasses, so the whole tree can be serialized generically (see
hdf5.py), and evented via psygnal: assigning a new value to a field emits
``instance.events.<field>(new_value, old_value)`` as well as the aggregated
``instance.events`` group signal. Assigning an equal value emits nothing.

In-place mutation of mutable fields (``params.working_directories["mask"] =
...``) does not emit — assign a new object to the field when listeners need
to know.
"""

from __future__ import annotations

import copy as _copy
import dataclasses
import uuid as _uuid
import os
from dataclasses import dataclass, field
from typing import Any, ClassVar

from psygnal import SignalGroupDescriptor

__all__ = [
    "apply_params",
    "CalibrationParams",
    "ConfigurationParams",
    "ImgParams",
    "MapParams",
    "MapRoiParams",
    "MaskParams",
    "OverlayItemParams",
    "PatternParams",
    "PhaseItemParams",
    "PhaseParams",
    "ViewParams",
    "default_working_directories",
]


def apply_params(
    target: Any,
    source: Any,
    fields: set[str] | None = None,
    exclude: set[str] | None = None,
) -> None:
    """Copies field values from *source* onto the existing *target* instance.

    The target keeps its identity, so event subscriptions on it stay valid,
    and every differing field emits its change event (and therefore runs
    its reactions). Mutable values are deep-copied so the two instances do
    not share state. Pass *fields* to restrict the copy to a subset, or
    *exclude* to skip individual fields.
    """
    for f in dataclasses.fields(target):
        if fields is not None and f.name not in fields:
            continue
        if exclude is not None and f.name in exclude:
            continue
        value = getattr(source, f.name)
        if isinstance(value, (dict, list, set)):
            value = _copy.deepcopy(value)
        setattr(target, f.name, value)


def default_working_directories() -> dict[str, str]:
    return {
        "calibration": "",
        "mask": "",
        "image": os.path.expanduser("~"),
        "pattern": "",
        "overlay": "",
        "phase": "",
        "batch": os.path.expanduser("~"),
    }


@dataclass
class ViewParams:
    """View state of the GUI that is not derivable from the data models.

    Owned by DioptasModel (a single, stable instance — load applies fields
    onto it instead of replacing it, so event subscriptions stay valid).
    Controllers write it and react to its change events; keeping it in the
    model makes it persistable and testable without widgets.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: what the integration image panel shows: "Image" or "Cake"
    img_mode: str = "Image"

    #: integration window layout: "normal" or "alternative"
    view_mode: str = "normal"

    #: whether the image panel is docked in the main window
    img_docked: bool = True

    #: whether the map panel is docked in the main window; when undocked it
    #: keeps working in its own window regardless of the mode shown
    map_docked: bool = True

    #: y separation applied by the overlay waterfall action
    waterfall_separation: float = 100.0

    #: which representation the calibration wizard's validation step shows
    #: the fitted parameters in: "pyFAI" or "Fit2d" (the tab labels). Users
    #: feeding other programs (CrysAlis etc.) live on the Fit2d tab, so the
    #: choice survives restarts with the session.
    calibration_param_display: str = "pyFAI"


@dataclass
class ImgParams:
    """User-settable parameters of an ImgModel.

    Owned by :class:`dioptas.model.ImgModel.ImgModel`, which exposes them
    through delegating properties that add side effects (image
    recalculation, directory-watcher activation). Writing the fields here
    directly bypasses those side effects but still emits change events.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    autoprocess: bool = False
    #: int default is deliberate: it keeps pristine img_data in the image's
    #: native dtype (uint16 * 1 stays uint16); any user-set factor is
    #: coerced to float by ImgModel.factor so integer multiplication can
    #: never wrap the pixel values
    factor: float = 1

    background_scaling: float = 1.0
    background_offset: float = 0.0

    #: how prev/next iterate through files: "number" or "time"
    file_iteration_mode: str = "number"

    #: applied image transformations by name, in application order (see
    #: ImgModel.TRANSFORMATION_FUNCTIONS); the callable list is derived
    transformations: list[str] = field(default_factory=list)

    # The file on screen. The pixels are an external payload: re-readable
    # from this path, so the path is the state and the arrays are caches
    # (ImgModel reconciles by re-reading when these change behind it).
    filename: str = ""
    #: position in a multi-image file, 1-based as shown to the user
    series_pos: int = 1
    #: background image file; empty = no background loaded
    background_filename: str = ""

    #: Active image corrections by name ("cbn", "oiadac", "transfer",
    #: "flat_field", "slab", ...), each holding that correction's scalar
    #: parameters. Arrays (transfer/flat-field reference images, the tth/azi
    #: grids) are caches rebuilt from these and the live calibration — the
    #: filenames inside the dicts are the state. Always assign a NEW dict;
    #: in-place mutation does not emit.
    corrections: dict[str, dict] = field(default_factory=dict)


@dataclass
class CalibrationParams:
    """User-settable parameters of a CalibrationModel.

    Owned by :class:`dioptas.model.CalibrationModel.CalibrationModel`; the
    model's properties delegate here. The pyFAI geometry, detector and
    calibrant objects are calibration *data* and stay in the model — only
    plain settings live here.

    ``use_dioptrin`` and ``dioptrin_num_workers`` are machine-specific:
    they are saved with the params document but deliberately not restored
    from project files (their effective defaults depend on the machine the
    project is opened on).
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    start_values: dict[str, float] = field(
        default_factory=lambda: {
            "dist": 200e-3,
            "wavelength": 0.3344e-10,
            "polarization_factor": 0.99,
        }
    )
    fit_wavelength: bool = False
    #: parameters held fixed during refinement (e.g. "dist", "rot1") and
    #: the values they are pinned to
    fixed_values: dict[str, float] = field(default_factory=dict)
    use_mask: bool = False

    polarization_factor: float = 0.99
    supersampling_factor: int = 1
    correct_solid_angle: bool = True
    distortion_spline_filename: str | None = None

    use_dioptrin: bool = False
    dioptrin_num_workers: int = 1

    # --- the calibration result (moved here in step 2b) -----------------
    # Declared detector-first on purpose: apply_params walks fields in
    # declaration order, and the detector must be in place before a geometry
    # is applied on top of it (the order project loading always used).

    #: DetectorModes value: 1 custom, 2 nexus file, 3 predefined
    detector_mode: int = 1
    #: pyFAI detector name when detector_mode is predefined
    detector_name: str = ""
    #: NeXus detector file when detector_mode is nexus
    detector_filename: str = ""
    #: the pyFAI geometry config (plain dict of floats/str) — the *result*
    #: of calibrating; None until a calibration exists
    geometry: dict | None = None
    is_calibrated: bool = False
    #: the .poni file the calibration came from or was saved to ("" when
    #: calibrated in-session and never saved)
    poni_filename: str = ""
    #: display name; "current" for an unsaved in-session calibration
    calibration_name: str = ""

    #: Picked calibration peaks as ((ring, ((x, y), ...)), ...) — one entry
    #: per pick, in pick order. Plain nested tuples so the generic
    #: serializer, snapshot equality and JSON survive them untouched; the
    #: model exposes numpy views through its points/points_index properties.
    peak_selections: tuple = ()


@dataclass
class MaskParams:
    """User-settable parameters of a MaskModel.

    Owned by :class:`dioptas.model.MaskModel.MaskModel`; the model's
    properties delegate here.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: drawing mode: True masks, False unmasks
    mode: bool = True

    #: rectangular region of interest as (x1, x2, y1, y2); None = disabled
    roi: tuple[int, int, int, int] | None = None


@dataclass
class MapRoiParams:
    """One window of the pattern and how it becomes a map layer.

    Owned by :class:`dioptas.model.MapModel.MapModel` through
    :attr:`MapParams.rois`. What the reduction keys mean is documented in
    :mod:`dioptas.model.map_reduction`.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: identifies the layer, and is what expressions refer to
    name: str = "A"

    #: window on the radial axis, in the unit the map was integrated in
    x_min: float = 0.0
    x_max: float = 0.0

    #: one of dioptas.model.map_reduction.REDUCTIONS
    reduction: str = "sum"

    #: take off the straight line joining the window edges first. The
    #: peak-shape reductions do this regardless.
    subtract_background: bool = False

    #: colour of the region drawn in the pattern plot
    color: str = "#40e0d0"


@dataclass
class MapParams:
    """User-settable parameters of a MapModel.

    Owned by :class:`dioptas.model.MapModel.MapModel`; the model computes
    defaults for window and dimension when map data is loaded, so None means
    "not determined yet". The layout fields below describe how the ordered
    points are laid out on that grid — see
    :mod:`dioptas.model.map_layout`.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: windows of the pattern, each producing one map layer. The map used to
    #: have exactly one, which is still what a freshly loaded map gets.
    rois: list[MapRoiParams] = field(default_factory=list)

    #: name of the layer drawn in the map plot — an ROI or an expression
    active_layer: str = "A"

    #: named layers computed from the ROI layers, as {name: expression},
    #: e.g. {"A/B": "A/B"}. Referring to an ROI by name gives its values.
    expressions: dict[str, str] = field(default_factory=dict)

    #: (rows, columns) grid the map points are arranged in
    dimension: tuple[int, int] | None = None

    #: grid cells in row-major order, each holding the index of the point
    #: shown there or None for a blank. None means the plain sequential
    #: arrangement, which is what a scan without dropped frames wants.
    slots: list[int | None] | None = None

    #: reverse every other row — serpentine ("snake") scans
    snake: bool = False

    #: swap the fast and slow axes of the arranged grid
    transpose: bool = False

    #: mirror the arranged grid left/right and top/bottom
    flip_horizontal: bool = False
    flip_vertical: bool = False

    #: indices of points left out of the map (saturated frames, beam dumps).
    #: They keep their cell and stay selectable, but read as blank.
    excluded_points: list[int] = field(default_factory=list)


@dataclass
class OverlayItemParams:
    """User-settable display state of a single overlay.

    Owned by :class:`dioptas.model.OverlayModel.Overlay`, which delegates
    its display attributes here (scaling/offset additionally write through
    to the underlying xypattern.Pattern, which applies them in its math).
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: stable identity, so state can reference this overlay (e.g. as the
    #: pattern background) across reorderings, undo steps and project files
    uid: str = field(default_factory=lambda: _uuid.uuid4().hex)

    name: str = ""
    color: str = ""
    visible: bool = True
    scaling: float = 1.0
    offset: float = 0.0


@dataclass
class PhaseItemParams:
    """User-settable display state of a single phase (jcpds content is data)."""

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: stable identity across reorderings, undo steps and project files
    uid: str = field(default_factory=lambda: _uuid.uuid4().hex)

    #: RGB color as a (r, g, b) sequence
    color: tuple = (255, 255, 255)
    visible: bool = True


@dataclass
class PhaseParams:
    """User-settable parameters of the (global) PhaseModel."""

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: apply pressure/temperature changes to all phases at once
    same_conditions: bool = True


@dataclass
class PatternParams:
    """User-settable parameters of a PatternModel.

    Owned by :class:`dioptas.model.PatternModel.PatternModel`; the model's
    properties delegate here. Writing fields directly bypasses model side
    effects but still emits change events.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    #: unit of the current pattern's x-axis ("", "2th_deg", "q_A^-1", "d_A")
    unit: str = ""

    # Where the current pattern came from. "integrated" patterns are derived
    # (recomputed from image + calibration on restore) and their filename is
    # the *image* the integration ran on — reloading it as a pattern file
    # would parse a TIFF as two-column text. Only "file" patterns reload.
    pattern_source: str = "integrated"
    pattern_filename: str = ""

    #: uid of the overlay serving as the pattern background. "" = no
    #: background (the default); an OverlayItemParams.uid = that overlay;
    #: None = anonymous — a raw-array background restored from an old project
    #: that no overlay owns, which resolution deliberately leaves alone.
    #: Only the legacy project loader ever writes None.
    background_overlay_uid: str | None = ""

    #: how prev/next iterate through pattern files: "number" or "time"
    file_iteration_mode: str = "number"

    # Automatic (smooth Bruckner) background subtraction. These are the
    # canonical values; PatternModel pushes them into the xypattern Pattern,
    # which owns the actual computation.
    auto_bkg_enabled: bool = False
    auto_bkg_smoothing: float = 0.1
    auto_bkg_iterations: int = 50
    auto_bkg_poly_order: int = 50
    #: [x_min, x_max] range the background is fitted over; None = full range
    auto_bkg_roi: list[float] | None = None


@dataclass
class ConfigurationParams:
    """User-settable parameters of a single Configuration.

    Owned by :class:`dioptas.model.Configuration.Configuration`, which
    exposes them through delegating properties that add side effects
    (re-integration, signal re-wiring). Reading/writing the fields here
    directly bypasses those side effects but still emits change events.
    """

    events: ClassVar[SignalGroupDescriptor] = SignalGroupDescriptor()

    working_directories: dict[str, str] = field(
        default_factory=default_working_directories
    )

    use_mask: bool = False
    transparent_mask: bool = False

    integration_rad_points: int | None = None
    integration_unit: str = "2th_deg"
    oned_azimuth_range: list[float] | None = None
    trim_trailing_zeros: bool = True
    calculate_poisson_errors: bool = False

    cake_azimuth_points: int = 360
    cake_azimuth_range: list[float] | None = None

    auto_integrate_pattern: bool = True
    auto_integrate_cake: bool = False

    auto_save_integrated_pattern: bool = False
    integrated_patterns_file_formats: list[str] = field(
        default_factory=lambda: [".xy"]
    )

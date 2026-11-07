# SPDX-License-Identifier: MIT

"""Immutable integration inputs and worker-safe pyFAI computation."""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
import logging
import threading
from typing import Any

import numpy as np
from pyFAI.integrator.azimuthal import AzimuthalIntegrator

from .loader.fusedHdf5 import FusedHdf5Source
from .loader.combinedHdf5 import CombinedLoadEngine, PreparedPattern
from .util.spottiness import integrate_spottiness, trim_spread
from .util.calc import supersample_image, trim_trailing_zeros

logger = logging.getLogger(__name__)


class _DioptrinBackend:
    """One native integrator and the settings already applied to it."""

    def __init__(self, integrator) -> None:
        self.integrator = integrator
        self.method = None
        self.unit = None
        self.mask = _UNSET
        self.polarization = _UNSET
        self.layout = None
        self.fused = None
        self.fused_key = None


@dataclass(frozen=True)
class IntegrationTask:
    """All state needed to integrate without touching live Dioptas models."""

    image: np.ndarray
    revision: int
    mask: np.ndarray | None
    geometry_config: dict[str, Any]
    filename: str
    unit: str
    polarization_factor: float | None
    correct_solid_angle: bool
    supersampling_factor: int
    pattern_num_points: int | None
    pattern_azimuth_range: tuple[float, float] | None
    trim_trailing_zeros: bool
    calculate_errors: bool
    calculate_pattern: bool
    cake_radial_points: int | None
    cake_azimuth_points: int
    cake_azimuth_range: tuple[float, float] | None
    calculate_cake: bool
    prefer_dioptrin: bool = False
    dioptrin_geometry_config: dict[str, float] | None = None
    calculate_azimuthal_std: bool = False
    dioptrin_sparse_layout: str = "csc"
    fused_hdf5_source: FusedHdf5Source | None = None
    fused_num_workers: int = 8
    precomputed_pattern: PreparedPattern | None = None


@dataclass(frozen=True)
class PatternIntegrationResult:
    radial: np.ndarray
    intensity: np.ndarray
    sigma: np.ndarray | None
    num_points: int
    azimuthal_std: np.ndarray | None = None


@dataclass(frozen=True)
class CakeIntegrationResult:
    intensity: np.ndarray
    radial: np.ndarray
    azimuthal: np.ndarray
    num_points: int


@dataclass(frozen=True)
class IntegrationResult:
    filename: str
    unit: str
    revision: int
    pattern: PatternIntegrationResult | None
    cake: CakeIntegrationResult | None


class PersistentIntegrationEngine:
    """Serial, reusable pyFAI/Dioptrin state for one integration worker.

    Both backends build geometry-dependent lookup state. Recreating an
    integrator for every browsed image discards that state and makes the warm
    path roughly an order of magnitude slower. This object is safe to submit
    through one dedicated worker thread. The lock protects explicit direct
    callers as well, but Dioptrin's native object must not migrate between
    pool threads.
    """

    def __init__(self, *, pyfai_factory=AzimuthalIntegrator) -> None:
        self._pyfai_factory = pyfai_factory
        self._pyfai_integrator = None
        self._dioptrin_backends: OrderedDict[str, _DioptrinBackend] = OrderedDict()
        self._dioptrin_unavailable = False
        self._geometry_key = None
        self._lock = threading.Lock()
        self._combined_loader = CombinedLoadEngine()

    @property
    def pyfai_integrator(self):
        return self._pyfai_integrator

    @property
    def dioptrin_integrator(self):
        if not self._dioptrin_backends:
            return None
        return next(reversed(self._dioptrin_backends.values())).integrator

    def compute(self, task: IntegrationTask) -> IntegrationResult:
        with self._lock:
            self._select_geometry(task)
            return self._compute_locked(task)

    def load_combined(self, request):
        with self._lock:
            return self._combined_loader.load(request)

    def close(self) -> None:
        """Drop native backend objects on their owning worker thread."""
        with self._lock:
            self._combined_loader.close()
            self._pyfai_integrator = None
            self._dioptrin_backends.clear()
            self._geometry_key = None
            self._dioptrin_unavailable = False

    @contextmanager
    def reuse_for_configuration(self, configuration):
        """Lend a warm native backend to an isolated bulk configuration.

        Called on this engine's dedicated worker, after loading the first
        frame. GUI models never receive the native object. Bulk and preview
        jobs share that lane so setters cannot race with another integration.
        """
        calibration = configuration.calibration_model
        task = configuration.create_integration_task(allow_fused=False)
        if (task is None or not task.prefer_dioptrin
                or configuration.has_dynamic_mask
                or not calibration.can_use_dioptrin_batch(
                    task.unit, task.pattern_azimuth_range)):
            yield
            return
        with self._lock:
            self._select_geometry(task)
            unit = "2th_deg" if task.unit == "d_A" else task.unit
            backend = self._ensure_dioptrin(task, unit)
            if backend is None:
                yield
                return
            self._configure_dioptrin(backend, task, unit)
            # Prepare lazy geometry/LUT/normalization on the owner before
            # admitting a queue of large frames. A cold parallel batch can
            # otherwise block its Python producer (and the GUI's GIL) while
            # every worker waits for that initialization. Warm calls reuse it.
            points = task.pattern_num_points or _calculate_num_points(
                self._ensure_pyfai(task), task.image.shape)
            backend.integrator.integrate1d(
                np.ascontiguousarray(task.image, dtype=np.float64), points)
            original = calibration._dioptrin_integrator
            polarization = calibration._dioptrin_polarization_state
            calibration._dioptrin_integrator = backend.integrator
            calibration._dioptrin_polarization_state = (
                backend.integrator, task.polarization_factor
            )
            try:
                yield
            finally:
                calibration._dioptrin_integrator = original
                calibration._dioptrin_polarization_state = polarization
                # Bulk paths set native options directly. Reconcile them on
                # the next preview rather than trusting old setter bookkeeping.
                # Unchanged native setters preserve the LUT.
                backend.method = None
                backend.unit = None
                backend.mask = _UNSET
                backend.polarization = _UNSET

    def _select_geometry(self, task: IntegrationTask) -> None:
        key = (
            _freeze_geometry(task.geometry_config),
            _freeze_geometry(task.dioptrin_geometry_config),
            task.image.shape,
        )
        if key != self._geometry_key:
            self._geometry_key = key
            self._pyfai_integrator = None
            self._dioptrin_backends.clear()
            self._dioptrin_unavailable = False

    def _ensure_pyfai(self, task: IntegrationTask):
        if self._pyfai_integrator is None:
            integrator = self._pyfai_factory()
            integrator.set_config(task.geometry_config)
            self._pyfai_integrator = integrator
        return self._pyfai_integrator

    def _ensure_dioptrin(self, task: IntegrationTask, unit: str):
        if not task.prefer_dioptrin or task.dioptrin_geometry_config is None:
            return None
        backend = self._dioptrin_backends.pop(unit, None)
        if backend is not None:
            self._dioptrin_backends[unit] = backend
            return backend
        if self._dioptrin_unavailable:
            return None
        try:
            import dioptrin

            integrator = dioptrin.Integrator.from_poni_dict(
                task.dioptrin_geometry_config,
                method="pixel_split",
                polarization_factor=task.polarization_factor,
                unit=unit,
            )
        except Exception:
            # Availability and licensing can change independently of a
            # restored project. Keep the worker usable through pyFAI, but do
            # not hide why the preferred backend was disabled.
            logger.info("Dioptrin worker backend unavailable; using pyFAI", exc_info=True)
            self._dioptrin_unavailable = True
            return None
        backend = _DioptrinBackend(integrator)
        self._dioptrin_backends[unit] = backend
        # Pattern and cake need at most two native units at once. Keeping this
        # bounded avoids unbounded native geometry/LUT memory when users cycle
        # through display units; eviction happens on the owning worker thread.
        while len(self._dioptrin_backends) > 2:
            self._dioptrin_backends.popitem(last=False)
        return backend

    def _configure_dioptrin(
        self, backend: _DioptrinBackend, task, unit: str
    ) -> None:
        integrator = backend.integrator
        if hasattr(integrator, "set_sparse_layout"):
            integrator.set_sparse_layout(task.dioptrin_sparse_layout)
        if backend.layout != task.dioptrin_sparse_layout:
            backend.fused = None
            backend.layout = task.dioptrin_sparse_layout
        method = (
            ("supersampled", task.supersampling_factor)
            if task.supersampling_factor > 1
            else ("pixel_split", None)
        )
        if method != backend.method:
            backend.fused = None
            if method[0] == "supersampled":
                integrator.set_method(method[0], n_ss=method[1])
            else:
                integrator.set_method(method[0])
            backend.method = method

        if unit != backend.unit:
            backend.fused = None
            integrator.set_unit(unit)
            backend.unit = unit

        mask = task.mask.astype(np.uint8) if task.mask is not None else None
        if not _arrays_equal(mask, backend.mask):
            backend.fused = None
            integrator.set_mask(mask)
            backend.mask = (
                np.array(mask, copy=True) if mask is not None else None
            )

        if task.polarization_factor != backend.polarization:
            backend.fused = None
            integrator.set_polarization_factor(task.polarization_factor)
            backend.polarization = task.polarization_factor

    def _compute_locked(self, task: IntegrationTask) -> IntegrationResult:
        pattern = None
        cake = None

        if task.calculate_pattern:
            prepared = task.precomputed_pattern
            if prepared is not None and prepared.matches(task):
                pattern = _finish_pattern_dioptrin(
                    prepared.loaded.result, task, prepared.loaded.request.settings.points)
            if pattern is None:
                if _can_use_dioptrin_pattern(task):
                    pattern_unit = "2th_deg" if task.unit == "d_A" else task.unit
                    dioptrin = self._ensure_dioptrin(task, pattern_unit)
                else:
                    dioptrin = None
                if dioptrin is not None:
                    self._configure_dioptrin(
                        dioptrin,
                        task,
                        pattern_unit,
                    )
                    pattern = _integrate_pattern_dioptrin(
                        dioptrin.integrator,
                        self._ensure_pyfai(task),
                        task,
                        backend=dioptrin,
                    )
                if pattern is None:
                    image, mask = _pyfai_inputs(task)
                    pattern = _integrate_pattern(
                        self._ensure_pyfai(task), task, image, mask
                    )

        if task.calculate_cake:
            dioptrin = (
                self._ensure_dioptrin(task, "2th_deg")
                if _can_use_dioptrin_cake(task)
                else None
            )
            if dioptrin is not None:
                self._configure_dioptrin(dioptrin, task, "2th_deg")
                cake = _integrate_cake_dioptrin(
                    dioptrin.integrator,
                    self._ensure_pyfai(task),
                    task,
                )
            if cake is None:
                image, mask = _pyfai_inputs(task)
                cake = _integrate_cake(
                    self._ensure_pyfai(task), task, image, mask
                )

        return IntegrationResult(
            filename=task.filename,
            unit=task.unit,
            revision=task.revision,
            pattern=pattern,
            cake=cake,
        )


def compute_integration(task: IntegrationTask) -> IntegrationResult:
    """One-shot computation; application controllers reuse an engine instead."""
    return PersistentIntegrationEngine().compute(task)


def _pyfai_inputs(
    task: IntegrationTask,
) -> tuple[np.ndarray, np.ndarray | None]:
    image = task.image
    mask = task.mask

    if task.supersampling_factor > 1:
        image = supersample_image(image, task.supersampling_factor)
        if mask is not None:
            mask = supersample_image(mask, task.supersampling_factor)
    return image, mask


def _freeze_geometry(value):
    if isinstance(value, dict):
        return tuple(
            (str(key), _freeze_geometry(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_geometry(item) for item in value)
    if isinstance(value, np.ndarray):
        return (value.dtype.str, value.shape, value.tobytes())
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


_UNSET = object()


def _arrays_equal(left, right) -> bool:
    if left is _UNSET or right is _UNSET:
        return False
    if left is None or right is None:
        return left is right
    return np.array_equal(left, right)


def _can_use_dioptrin_pattern(task: IntegrationTask) -> bool:
    return (
        task.pattern_azimuth_range is None
        and task.correct_solid_angle
        and task.unit in ("2th_deg", "q_A^-1", "q_nm^-1", "d_A")
    )


def _can_use_dioptrin_cake(task: IntegrationTask) -> bool:
    azimuth = task.cake_azimuth_range
    wraps = azimuth is not None and azimuth[0] > azimuth[1]
    return task.correct_solid_angle and not wraps


def _try_fused_pattern(backend, task, num_points, image):
    source = task.fused_hdf5_source
    if (backend is None or source is None or task.calculate_azimuthal_std
            or task.dioptrin_sparse_layout != "csc"
            or not (task.dioptrin_geometry_config.get("wavelength", 0) > 0)):
        return None
    try:
        import dioptrin_io_fused as dioptrin_io
    except (ImportError, OSError):
        return None
    factory = getattr(dioptrin_io, "FusedHdf5Integrator", None)
    if factory is None:
        return None
    key = (source.filename, source.dataset, source.identity, image.shape,
           num_points, task.fused_num_workers)
    source.check()
    try:
        if key != backend.fused_key or backend.fused is None:
            try:
                backend.fused = factory(
                    source.filename, source.dataset, task.dioptrin_geometry_config,
                    num_points, mask=backend.mask,
                    unit=backend.unit, polarization_factor=task.polarization_factor,
                    supersampling=task.supersampling_factor,
                    num_workers=task.fused_num_workers,
                )
            except dioptrin_io.UnsupportedFusedLayout:
                backend.fused = False
                logger.debug("Native fused layout unsupported; using current image", exc_info=True)
            backend.fused_key = key
        if backend.fused is False:
            return None
        try:
            result = backend.fused.integrate1d(
                source.frame, errors=task.calculate_errors, expected_image=image)
        except dioptrin_io.SourceImageMismatch:
            # Editing/replacing NumPy pixels must never be bypassed by rereading.
            logger.debug("Captured pixels differ from native source; using current image")
            return None
        logger.debug("Single-frame fused HDF5 integration with %s block workers", task.fused_num_workers)
        return result
    finally:
        # Even an admission/mismatch fallback must not hide a changed source.
        source.check()


def _integrate_pattern_dioptrin(
    integrator,
    pyfai_integrator,
    task: IntegrationTask,
    *, backend=None,
) -> PatternIntegrationResult | None:
    image = np.ascontiguousarray(task.image, dtype=np.float64)
    num_points = task.pattern_num_points or _calculate_num_points(
        pyfai_integrator, image.shape
    )
    result = _try_fused_pattern(backend, task, num_points, image)
    try:
        if result is None:
            result = integrator.integrate1d(
                image,
                num_points,
                **({"errors": True} if task.calculate_errors else {}),
                **({"azimuthal_std": True} if task.calculate_azimuthal_std else {}),
            )
    except TypeError:
        # Older Dioptrin versions may lack errors or independent spread.
        return None

    return _finish_pattern_dioptrin(result, task, num_points)


def _finish_pattern_dioptrin(result, task, num_points):
    radial = np.asarray(result.radial)
    intensity = np.asarray(result.intensity)
    sigma = (
        np.asarray(result.errors)
        if task.calculate_errors and getattr(result, "errors", None) is not None
        else None
    )
    if task.calculate_errors and sigma is None:
        return None
    std = getattr(result, "azimuthal_std", None) if task.calculate_azimuthal_std else None
    if task.calculate_azimuthal_std and std is None:
        return None
    if std is not None:
        std = np.asarray(std)
    if task.unit == "d_A":
        wavelength = task.geometry_config["wavelength"]
        radial = wavelength / (2 * np.sin(radial / 360 * np.pi)) * 1e10
    if std is None and np.sum(intensity) != 0 and task.trim_trailing_zeros:
        radial, intensity = trim_trailing_zeros(radial, intensity)
        if sigma is not None:
            sigma = sigma[: len(intensity)]
    if std is not None and task.trim_trailing_zeros:
        radial, intensity, sigma, std = trim_spread(radial, intensity, sigma, std)
    return PatternIntegrationResult(radial, intensity, sigma, num_points, std)


def _integrate_cake_dioptrin(
    integrator,
    pyfai_integrator,
    task: IntegrationTask,
) -> CakeIntegrationResult:
    image = np.ascontiguousarray(task.image, dtype=np.float64)
    num_points = task.cake_radial_points or _calculate_num_points(
        pyfai_integrator, image.shape
    )
    azimuth_range = task.cake_azimuth_range
    azimuth_range_rad = (
        tuple(np.radians(azimuth_range)) if azimuth_range is not None else None
    )
    result = integrator.integrate2d(
        image,
        num_points,
        task.cake_azimuth_points,
        azimuthal_range=azimuth_range_rad,
    )
    intensity = np.asarray(result.intensity).reshape(
        task.cake_azimuth_points, num_points
    )
    if result.radial is not None:
        radial = np.asarray(result.radial)
    else:
        radial_values = pyfai_integrator.center_array(
            image.shape, unit="2th_deg"
        )
        radial_min, radial_max = radial_values.min(), radial_values.max()
        half_step = (radial_max - radial_min) / num_points / 2
        radial = np.linspace(
            radial_min + half_step,
            radial_max - half_step,
            num_points,
        )
    if result.azimuthal is not None:
        azimuthal = np.asarray(result.azimuthal)
    else:
        azi_min = azimuth_range[0] if azimuth_range else -180.0
        azi_max = azimuth_range[1] if azimuth_range else 180.0
        half_step = (azi_max - azi_min) / task.cake_azimuth_points / 2
        azimuthal = np.linspace(
            azi_min + half_step,
            azi_max - half_step,
            task.cake_azimuth_points,
        )
    return CakeIntegrationResult(intensity, radial, azimuthal, num_points)


def _integrate_pattern(
    integrator: AzimuthalIntegrator,
    task: IntegrationTask,
    image: np.ndarray,
    mask: np.ndarray | None,
) -> PatternIntegrationResult | None:
    if not task.calculate_pattern:
        return None

    num_points = task.pattern_num_points or _calculate_num_points(
        integrator, image.shape
    )
    kwargs = dict(
        method="csr",
        unit="2th_deg" if task.unit == "d_A" else task.unit,
        azimuth_range=task.pattern_azimuth_range,
        mask=mask,
        polarization_factor=task.polarization_factor,
        correctSolidAngle=task.correct_solid_angle,
    )
    if task.calculate_errors:
        kwargs["error_model"] = "poisson"

    std = None
    if task.calculate_azimuthal_std:
        result, spread_intensity, std = integrate_spottiness(
            integrator, image, num_points, kwargs
        )
    else:
        try:
            result = integrator.integrate1d(image, num_points, **kwargs)
        except NameError:
            # Preserve the fallback for unavailable configured engines.
            kwargs["method"] = "csr"
            result = integrator.integrate1d(image, num_points, **kwargs)

    radial = np.asarray(result.radial)
    intensity = np.asarray(result.intensity)
    sigma = (
        np.asarray(result.sigma)
        if task.calculate_errors and result.sigma is not None
        else None
    )
    if std is not None:
        intensity = spread_intensity
    if task.unit == "d_A":
        radial = integrator.wavelength / (2 * np.sin(radial / 360 * np.pi)) * 1e10

    if std is None and np.sum(intensity) != 0 and task.trim_trailing_zeros:
        radial, intensity = trim_trailing_zeros(radial, intensity)
        if sigma is not None:
            sigma = sigma[: len(intensity)]

    if std is not None and task.trim_trailing_zeros:
        radial, intensity, sigma, std = trim_spread(radial, intensity, sigma, std)
    return PatternIntegrationResult(radial, intensity, sigma, num_points, std)


def _integrate_cake(
    integrator: AzimuthalIntegrator,
    task: IntegrationTask,
    image: np.ndarray,
    mask: np.ndarray | None,
) -> CakeIntegrationResult | None:
    if not task.calculate_cake:
        return None

    num_points = task.cake_radial_points or _calculate_num_points(
        integrator, image.shape
    )
    result = integrator.integrate2d(
        image,
        num_points,
        task.cake_azimuth_points,
        azimuth_range=task.cake_azimuth_range,
        method="csr",
        mask=mask,
        # Configuration.integrate_image_2d historically keeps cake radial
        # coordinates in two-theta regardless of the 1D pattern display unit.
        unit="2th_deg",
        polarization_factor=task.polarization_factor,
        correctSolidAngle=task.correct_solid_angle,
    )
    return CakeIntegrationResult(
        intensity=np.asarray(result.intensity),
        radial=np.asarray(result.radial),
        azimuthal=np.asarray(result.azimuthal),
        num_points=num_points,
    )


def _calculate_num_points(
    integrator: AzimuthalIntegrator,
    image_shape: tuple[int, int],
    max_dist_factor: float = 2.0,
) -> int:
    fit2d = integrator.getFit2D()
    center_x = fit2d["centerX"]
    center_y = fit2d["centerY"]
    width, height = image_shape
    side1 = max(abs(width - center_x), center_x) if 0 < center_x < width else width
    side2 = (
        max(abs(height - center_y), center_y)
        if 0 < center_y < height
        else height
    )
    return int(np.sqrt(side1**2 + side2**2) * max_dist_factor)

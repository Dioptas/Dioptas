# SPDX-License-Identifier: MIT
"""One native decode supplies immutable display pixels and a fixed-mask pattern."""
from dataclasses import dataclass
import os

import h5py
import numpy as np

from .fusedHdf5 import FusedHdf5Source, file_identity


def native_unit(unit):
    return "2th_deg" if unit == "d_A" else unit


def geometry_key(poni):
    return tuple(sorted(poni.items()))


@dataclass(frozen=True)
class LoadSettings:
    geometry: tuple
    shape: tuple
    unit: str
    points: int
    polarization: float | None
    supersampling: int
    workers: int


@dataclass(frozen=True)
class LoadRequest:
    source: FusedHdf5Source
    settings: LoadSettings
    mask: np.ndarray | None
    errors: bool


@dataclass(frozen=True)
class LoadedPattern:
    request: LoadRequest
    image: np.ndarray
    result: object

    def matches(self, task):
        r, s = self.request, self.request.settings
        return (task.prefer_dioptrin and task.dioptrin_sparse_layout == "csc"
            and task.correct_solid_angle and task.pattern_azimuth_range is None
            and not task.calculate_azimuthal_std
            and geometry_key(task.dioptrin_geometry_config or {}) == s.geometry
            and task.image.shape == s.shape and native_unit(task.unit) == s.unit
            and task.pattern_num_points in (None, s.points)
            and task.polarization_factor == s.polarization
            and task.supersampling_factor == s.supersampling
            and (not task.calculate_errors or r.errors))


@dataclass(frozen=True)
class PreparedPattern:
    loaded: LoadedPattern
    image: np.ndarray
    mask: np.ndarray | None

    def matches(self, task):
        return (self.image is task.image and not task.image.flags.writeable
            and self.mask is task.mask
            and (task.mask is None or not task.mask.flags.writeable)
            and self.loaded.matches(task))


def masks_equal(a, b):
    if a is None or b is None:
        return a is b
    return np.array_equal(a, b)


class CombinedLoadEngine:
    """Used and closed only on the native integration owner thread."""
    def __init__(self):
        self.backend = None
        self.settings = None
        self.mask = None
        self.source = None

    def close(self):
        self.backend = None
        self.settings = None
        self.source = None
        self.mask = None

    def load(self, request):
        try:
            import dioptrin_io_fused as bridge
        except (ImportError, OSError):
            return None
        factory = getattr(bridge, "FusedHdf5Integrator", None)
        if factory is None or not hasattr(factory, "load_integrate1d"):
            return None
        source, settings = request.source, request.settings
        source_key = (source.filename, source.dataset, source.identity)
        source.check()
        try:
            try:
                if (self.backend is None or self.settings != settings
                        or not masks_equal(self.mask, request.mask)):
                    self.backend = factory(source.filename, source.dataset,
                        dict(settings.geometry), settings.points,
                        mask=(np.ascontiguousarray(request.mask, dtype=np.uint8)
                              if request.mask is not None else None),
                        unit=settings.unit, polarization_factor=settings.polarization,
                        supersampling=settings.supersampling, num_workers=settings.workers)
                    self.settings = settings
                    self.mask = request.mask
                    self.source = source_key
                elif self.source != source_key:
                    self.backend.set_source(source.filename, source.dataset)
                    self.source = source_key
            except bridge.UnsupportedFusedLayout:
                return None
            return self.backend.load_integrate1d(source.frame, errors=request.errors)
        finally:
            source.check()


def eligible_dataset(dataset, path):
    if (not isinstance(dataset, h5py.Dataset) or len(dataset.shape) != 3
            or dataset.is_virtual or dataset.chunks != (1, *dataset.shape[1:])
            or dataset.dtype.kind != "u" or dataset.dtype.itemsize not in (2, 4)
            or not dataset.dtype.isnative
            or os.path.realpath(dataset.file.filename) != os.path.realpath(path)):
        return False
    props = dataset.id.get_create_plist()
    if props.get_nfilters() != 1:
        return False
    codec, _, parameters, _ = props.get_filter(0)
    return codec == 32008 and len(parameters) >= 5 and parameters[4] == 2


def load_combined(configuration, filename, index, invoke, *, existing_loader=None):
    """Prepare metadata on the GUI, invoke native work on its owner, publish once.

    New files use the same authoritative LImA default dataset and header as FabIO.
    Existing explicitly selected HDF5 readers retain their selected dataset.
    Unsupported layouts/settings return before decoding so normal loading runs once.
    """
    from .FabioLoader import FabioLoader
    from .hdf5Loader import Hdf5Image
    from ..util.integration import detect_fast_path
    cal, img = configuration.calibration_model, configuration.img_model
    if (not configuration.auto_integrate_pattern or not cal.is_calibrated
            or not cal.use_dioptrin or cal.dioptrin_sparse_layout != "csc"
            or configuration.has_dynamic_mask or img.img_changed.blocked
            or not cal.correct_solid_angle or configuration.oned_azimuth_range is not None
            or configuration.calculate_azimuthal_std or not detect_fast_path(img)
            or configuration.integration_unit not in ("2th_deg", "q_A^-1", "q_nm^-1", "d_A")):
        return None
    path = os.path.abspath(filename)
    try:
        identity = file_identity(path)
    except OSError:
        return None
    if existing_loader is not None and identity != img._loaded_file_signature:
        return None
    opened = None
    facade = None
    loader = existing_loader
    if loader is not None and img.series_get_image != getattr(loader, "get_image", None):
        return None
    try:
        image = getattr(loader, "fabio_image", loader)
        dataset = getattr(image, "dataset", None)
        if loader is None:
            try:
                opened = h5py.File(path, "r")
                entry_name = opened.attrs.get("default")
                if entry_name is None:
                    return None
                dataset = opened[entry_name]["measurement/data"]
            except (OSError, KeyError, ValueError):
                return None
        if loader is None:
            # FabIO's format factory parses magic/metadata, without read(frame).
            # Preserve its authoritative facade; do not guess for other HDF5 schemas.
            from fabio.openimage import _openimage
            from fabio.limaimage import LimaImage
            try:
                facade = _openimage(path)
                if not isinstance(facade, LimaImage):
                    return None
                facade._readheader(path)
            except (OSError, KeyError, ValueError):
                return None
        if (not eligible_dataset(dataset, path) or not 0 <= index < dataset.shape[0]
                or tuple(cal.detector.shape or ()) != dataset.shape[1:]):
            return None
        shape = dataset.shape[1:]
        if configuration.use_mask:
            if configuration.mask_model.mask_dimension != shape:
                return None
            mask = configuration.mask_model.get_mask()
        elif configuration.mask_model.roi is not None:
            if configuration.mask_model.mask_dimension != shape:
                return None
            mask = configuration.mask_model.roi_mask
        else:
            mask = None
        mask = cal._prepare_integration_mask(mask)
        if mask is not None:
            if mask.shape != shape or np.all(mask):
                return None
            mask = np.array(mask, dtype=bool, copy=True, order="C")
            mask.setflags(write=False)
        poni = cal._get_poni_dict()
        if not (poni.get("wavelength", 0) > 0):
            return None
        points = configuration.integration_rad_points or cal.calculate_number_of_pattern_points(shape, 2)
        request = LoadRequest(FusedHdf5Source(path, dataset.name, index, identity),
            LoadSettings(geometry_key(poni), shape, native_unit(configuration.integration_unit),
                         points, cal.polarization_factor, cal.supersampling_factor,
                         min(8, max(1, cal.dioptrin_num_workers))), mask,
            configuration.calculate_poisson_errors)
        loaded = invoke(request)
        if loaded is None:
            return None
        pixels, result = loaded
        request.source.check()
        if loader is None:
            # Header parsing reads metadata only. Native counts replace FabIO's
            # normal dataset[frame] call, preserving its LImA save/header facade.
            facade.data = pixels
            request.source.check()
            facade.h5, facade.dataset = opened, dataset
            facade._nframes, facade.currentframe, facade.filename = dataset.shape[0], index, path
            loader = FabioLoader.__new__(FabioLoader)
            loader.fabio_image, loader.series_max = facade, dataset.shape[0]
            opened = None  # owned by the facade from here
        elif isinstance(loader, FabioLoader):
            loader.fabio_image.data = pixels
            loader.fabio_image.currentframe = index
        image = pixels[::-1]
        cached = LoadedPattern(request, image, result)
        payload = dict(img_data=image, combined_pattern=cached, loader=loader,
            source_identity=request.source.identity,
            series_max=loader.series_max, series_get_image=loader.get_image)
        if isinstance(loader, FabioLoader):
            payload["img_data_fabio"] = loader.fabio_image
        elif isinstance(loader, Hdf5Image):
            payload.update(sources=loader.image_sources, select_source=loader.select_source)
        return payload
    finally:
        if opened is not None:
            opened.close()

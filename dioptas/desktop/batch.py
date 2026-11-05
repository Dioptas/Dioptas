# SPDX-License-Identifier: MIT
"""Qt BatchModel commands for the desktop series workspace."""

from pathlib import Path
import re

import numpy as np

from dioptas.model.Configuration import Configuration
from dioptas.model.worker_configuration import (
    capture_worker_configuration,
    build_worker_configuration,
)
from .display import image_levels
from .image_batch import ImageBatchWorkflow


class BatchWorkflow(ImageBatchWorkflow):
    def _batch_commands(self):
        return {
            "image_batch_mode": self._set_image_batch_mode,
            "batch_snapshot": self._batch_snapshot,
            "batch_load_data": self._batch_load_data,
            "batch_folder_step": self._batch_folder_step,
            "batch_unit": self._batch_unit,
            "batch_normalization_settings": self._batch_normalization_settings,
            "batch_load": self._batch_load,
            "integration_save_batch": self._batch_save,
            "batch_folder": self._batch_folder,
            "batch_open": self._batch_open,
            "batch_select": self._batch_select,
            "batch_normalize": self._batch_normalize,
            "batch_levels": self._batch_levels,
        }

    def _batch_load_data(self, paths=None):
        if paths is None and self._choose_file:
            paths = self._choose_file("batch_images", False)
        if not paths:
            return {"cancelled": True}
        if isinstance(paths, str):
            paths = [paths]
        first = self._path(paths[0], "image")
        if Path(first).suffix.lower() in {".h5", ".hdf5", ".nxs"}:
            import h5py
            with h5py.File(first, "r") as source:
                processed = "processed/result" in source or ("data" in source and "binning" in source)
            if processed:
                if len(paths) != 1:
                    raise ValueError("Open one processed batch at a time.")
                return self._batch_open(first)
        return self._batch_load(paths=paths)

    def _batch_folder_step(self, direction=1):
        b = self._require_batch()
        if direction not in (-1, 1) or b.files is None or not len(b.files):
            raise ValueError("Load raw image files before stepping through folders.")
        paths = b.get_next_folder_filenames() if direction == 1 else b.get_previous_folder_filenames()
        if not paths:
            raise ValueError("No matching image files in the neighboring folder.")
        return self._batch_load(paths=paths)

    def _batch_unit(self, unit):
        b = self._require_batch()
        if unit not in {"2th_deg", "q_A^-1", "d_A"}:
            raise ValueError("Choose 2theta, Q or d.")
        if unit != b.integration_unit and "2th_deg" in {unit, b.integration_unit} and getattr(b, "_desktop_wavelength", None) is None:
            raise ValueError("This stored batch has no recorded wavelength for that conversion.")
        self.configuration.integration_unit = unit
        return {**self._batch_select(self._batch_index()), **self._batch_snapshot()}

    def _batch_normalization_settings(self, start, stop, reference):
        b = self._require_batch()
        if any(isinstance(v, bool) or int(v) != v for v in (start, stop, reference)) or not 0 <= start <= stop < len(b.binning) or not 0 <= reference < len(b.data):
            raise ValueError("Choose inclusive normalization bins and a reference frame within the batch.")
        if b.normalization_enabled:
            b.normalize((int(start), int(stop)+1), int(reference))
            return {**self._batch_select(self._batch_index()), **self._batch_snapshot()}
        b.normalization_range = (int(start), int(stop)+1)
        b.normalization_reference = int(reference)
        return {**self._state(), **self._batch_snapshot()}

    def _require_batch(self):
        b = self.configuration.batch_model
        if b.data is None or not len(b.data):
            raise ValueError("Load and integrate batch images first.")
        return b

    def _batch_snapshot(self):
        b = self.configuration.batch_model
        if b.data is None or not len(b.data):
            return {"batch": None}
        if getattr(b, "_desktop_display_source", None) is not b.data:
            from uuid import uuid4
            b._desktop_display_source = b.data
            b._desktop_display_id = uuid4().hex
        profile = self._batch_pattern(b, self._batch_index())
        linked = self._linked_snapshot()
        clicked_owner, clicked = getattr(self, "_batch_clicked", (None, None))
        entries = []
        for i in range(len(b.data)):
            path, frame = b.get_image_info(i)
            path = str(path) if path not in (None, "NA") else ""
            entries.append(
                {
                    "path": path,
                    "name": Path(path).name if path else "Stored pattern",
                    "frame": int(frame or 0) + 1,
                }
            )
        files = []
        for file_index, path in enumerate(b.files if b.files is not None else []):
            indices = [i for i, entry in enumerate(entries) if entry["path"] == str(path)]
            frames = int(b.file_map[file_index+1] - b.file_map[file_index]) if b.file_map is not None and len(b.file_map) > file_index+1 else len(indices)
            files.append({"path": str(path), "name": Path(path).name, "frames": frames, "first": indices[0] if indices else None})
        return {
            "batch": {
                "id": b._desktop_display_id,
                "raster": self._raster(b.data, max_side=None, histogram=True),
                "x": profile["x"],
                "wavelength": getattr(b, "_desktop_wavelength", None),
                "unit": profile["unit"],
                "sourceUnit": b.integration_unit,
                "entries": entries,
                "files": files,
                "pattern": profile,
                "selected": self._batch_index(),
                "total": int(b.n_img_all or len(b.data)),
                "canReintegrate": bool(b.raw_available),
                "normalized": bool(b.normalization_enabled),
                "normalizationRange": list(b.normalization_range),
                "normalizationReference": int(b.normalization_reference),
                "calibration": b.used_calibration,
                "phaseLines": self._pattern_reference_data("d_A")["phaseLines"],
                "position": (
                    {"x": linked["twoTheta"], "unit": "2th_deg"}
                    if linked is not None else clicked if clicked_owner is b else None
                ),
                "mask": b.used_mask,
            }
        }

    def _batch_pattern(self, batch, index):
        from dioptas.model.util.calc import convert_units
        unit = self.configuration.integration_unit
        wavelength = getattr(batch, "_desktop_wavelength", None)
        if wavelength is None and unit != batch.integration_unit and "2th_deg" in {unit, batch.integration_unit}:
            unit = batch.integration_unit
        x = np.asarray(batch.binning)
        if unit != batch.integration_unit:
            if "2th_deg" not in {unit, batch.integration_unit}:
                x = 2 * np.pi / x
            else:
                x = convert_units(x, wavelength, batch.integration_unit, unit)
        return {
            "x": x.tolist(),
            "y": [float(v) if np.isfinite(v) else None for v in batch.data[index]],
            "unit": unit,
        }

    def _batch_index(self):
        b = self.configuration.batch_model
        index = (
            getattr(self, "_batch_selected", 0)
            if getattr(self, "_batch_owner", None) is b
            else 0
        )
        return max(0, min(index, len(b.data) - 1)) if b.data is not None else 0

    def _batch_folder(self, path=None):
        if path is None and self._choose_file:
            path = self._choose_file("directory", False)
        if not path:
            return {"cancelled": True}
        folder = Path(path).expanduser().resolve()
        if not folder.is_dir():
            raise ValueError("Choose a batch image folder.")
        extensions = {
            ".tif",
            ".tiff",
            ".edf",
            ".cbf",
            ".h5",
            ".hdf5",
            ".nxs",
            ".mar3450",
        }
        paths = sorted(
            (
                p
                for p in folder.iterdir()
                if p.is_file() and p.suffix.lower() in extensions
            ),
            key=lambda p: [
                int(v) if v.isdigit() else v.lower() for v in re.split(r"(\d+)", p.name)
            ],
        )
        if not paths:
            raise ValueError("No supported detector images were found in this folder.")
        return self._batch_load(paths=[str(p) for p in paths])

    def _batch_load(self, paths=None, reintegrate=False, start=1, stop=None, step=1):
        c = self.configuration
        if not c.is_calibrated:
            raise ValueError("Load a PONI calibration before integrating batch images.")
        old = c.batch_model
        if reintegrate:
            if not old.raw_available:
                raise ValueError(
                    "Reload the original images to reintegrate this stored batch."
                )
            paths = list(old.files)
        if paths is None and self._choose_file:
            paths = self._choose_file("batch_images", False)
        if isinstance(paths, str):
            paths = [paths]
        if not paths:
            return {"cancelled": True}
        if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
            raise ValueError("Batch source must be an ordered list of image paths.")
        paths = [self._path(p, "image") for p in paths]
        state = capture_worker_configuration(c)
        # A stored batch may refer to raw files that have moved. Start the
        # candidate with the newly selected source, not a stale live filename.
        state.image["filename"], state.image["series_pos"] = paths[0], 1
        worker = build_worker_configuration(state)
        b = worker.batch_model
        self._cancel_refinement.clear()
        self._progress = {
            "running": True,
            "current": 0,
            "total": len(paths),
            "label": "Reading batch files",
        }
        try:
            # Count the frames exposed by the existing image loader. Validate on the
            # isolated graph before publishing any data to the live session.
            positions, file_map = [], [0]
            expected = c.img_model.img_data.shape if self._has_image else None
            for i, path in enumerate(paths):
                if self._cancel_refinement.is_set():
                    return {"cancelled": True}
                worker.img_model.load(path)
                if expected is None:
                    expected = worker.img_model.img_data.shape
                if worker.img_model.img_data.shape != expected:
                    raise ValueError(
                        f"Batch image must have the current detector shape: {Path(path).name}"
                    )
                positions.extend((i, f) for f in range(worker.img_model.series_max))
                file_map.append(len(positions))
                self._progress["current"] = i + 1
            total = len(positions)
            stop = total if stop is None else stop
            if (
                any(isinstance(v, bool) or int(v) != v for v in (start, stop, step))
                or not 1 <= start <= stop <= total
                or step < 1
            ):
                raise ValueError(
                    f"Choose frames 1–{total}, an increasing range and a positive integer stride."
                )
            b.files, b.pos_map_all = np.asarray(paths), np.asarray(positions)
            b.file_map, b.n_img_all, b.raw_available = np.asarray(file_map), total, True
            count = len(range(int(start) - 1, int(stop), int(step)))

            def progress(current):
                self._progress = {
                    "running": True,
                    "current": current,
                    "total": count,
                    "label": "Integrating batch",
                }
                return not self._cancel_refinement.is_set()

            progress(0)
            wrapped = self._integration_wrapped(worker.oned_azimuth_range)
            if wrapped:
                worker.calibration_model.pattern_geometry.reset()
                worker.calibration_model.pattern_geometry.setChiDiscAtZero()
            b.integrate_raw_data(
                int(start) - 1, int(stop), int(step), use_all=True, callback_fn=progress
            )
            if self._cancel_refinement.is_set():
                return {"cancelled": True}
            if b.data is None or len(b.data) != count:
                raise ValueError("The batch did not produce all requested patterns.")
            b._desktop_wavelength = float(c.calibration_model.wavelength)
            b.configuration = c
            c.batch_model = b
            self._batch_selected, self._batch_owner = 0, b
            return {
                **self._batch_select(0),
                **self._batch_snapshot(),
                "batchOpened": True,
            }
        finally:
            self._progress = {**self._progress, "running": False}

    def _batch_open(self, path=None):
        path = self._path(path, "batch_open")
        if path is None:
            return {"cancelled": True}
        # Qt's reader may load a calibration and mask. Keep those side effects
        # in a candidate graph: importing patterns never changes live geometry.
        candidate = Configuration()
        candidate.auto_integrate_pattern = candidate.auto_integrate_cake = False
        b = candidate.batch_model
        b.load_proc_data(path)
        if (
            b.data is None
            or b.data.dtype.kind not in "fiu"
            or b.data.ndim != 2
            or not len(b.data)
            or b.binning is None
            or b.data.shape[1] != len(b.binning)
            or not len(b.binning)
        ):
            raise ValueError(
                "The file must contain a non-empty pattern matrix and radial axis."
            )
        if b.integration_unit not in {"2th_deg", "q_A^-1", "d_A"} or not np.all(
            np.isfinite(b.binning)
        ):
            raise ValueError("The batch radial axis or unit is unsupported.")
        if b.binning.ndim != 1:
            raise ValueError("The radial axis must be one-dimensional.")
        if b.pos_map is not None and (
            b.files is None
            or b.pos_map.shape != (len(b.data), 2)
            or not np.issubdtype(b.pos_map.dtype, np.integer)
            or np.any(b.pos_map < 0)
            or np.any(b.pos_map[:, 0] >= len(b.files))
        ):
            raise ValueError("The stored frame-to-file mapping is invalid.")
        import h5py

        with h5py.File(path, "r") as f:
            value = (
                f["processed/result"].attrs.get("desktop_wavelength_m")
                if "processed/result" in f
                else None
            )
        b._desktop_wavelength = (
            float(value)
            if value is not None and np.isfinite(value) and value > 0
            else None
        )
        # Imported series remain browsable even if their original files moved.
        b.raw_available = False
        b.configuration = self.configuration
        self.configuration.batch_model = b
        self._batch_selected, self._batch_owner = 0, b
        return {**self._batch_select(0), **self._batch_snapshot(), "batchOpened": True}

    def _batch_select(self, index, position=None):
        b = self._require_batch()
        if (
            isinstance(index, bool)
            or int(index) != index
            or not 0 <= index < len(b.data)
        ):
            raise ValueError("Choose a frame within the integrated batch.")
        index = int(index)
        angle = None
        if position is not None:
            from .integration import finite
            from dioptas.model.util.calc import convert_units
            if not isinstance(position, dict) or position.get("unit") not in {"2th_deg", "q_A^-1", "d_A"}:
                raise ValueError("Choose a valid batch radial position.")
            position = {"x": finite(position.get("x"), "Batch radial position"), "unit": position["unit"]}
            wavelength = getattr(b, "_desktop_wavelength", None)
            if position["unit"] == "2th_deg":
                angle = finite(position["x"], "2theta", 0, 180)
            elif wavelength:
                with np.errstate(invalid="ignore", divide="ignore"):
                    angle = finite(float(convert_units(position["x"], wavelength, position["unit"], "2th_deg")), "2theta", 0, 180)
        path, frame = b.get_image_info(index)
        response = {}
        warning = None
        available = path and Path(path).is_file()
        if available:
            try:
                self.configuration.img_model.load(path, int(frame))
            except (OSError, ValueError, IndexError):
                available = False
        self._has_image = bool(available)
        if available:
            self.configuration.calibration_model.clear_peaks()
            self._fit_rms = None
            # Populate Integration's detector/cake through the usual correction
            # and integration path, then restore the stored series profile.
            self._calculate()
            response.update(
                image=self._raster(self.configuration.img_model.img_data, max_side=None, histogram=True),
                rawImage=self._raster(self.configuration.img_model.raw_img_data, max_side=None, histogram=True),
                mask=self._raster(self.configuration.mask_model.get_display_mask(), mask=True, max_side=None),
            )
        else:
            self._cake = None
            warning = "Raw detector image unavailable; showing the stored pattern."
        profile = self._batch_pattern(b, index)
        x, y = np.asarray(profile["x"]), b.data[index]
        # Stored profiles retain their own radial unit and intensities. Current
        # image/cake processing never silently replaces the batch matrix.
        self.configuration.pattern_model.set_pattern(x, y, str(path or ""), unit=profile["unit"])
        self._refresh_integration_pattern()
        self._integration_dirty = False
        self._batch_selected, self._batch_owner = index, b
        self._revision += 1
        if position is not None:
            self._batch_clicked = (b, position)
            response["batchPosition"] = position
            response["batchWavelength"] = getattr(b, "_desktop_wavelength", None)
            if available and self.configuration.is_calibrated and angle is not None:
                response.update(self._validation_position(source="cake", x=angle))
        return {
            **response,
            **self._state(),
            "pattern": self._pattern,
            "cake": self._cake,
            "clearImage": not bool(available),
            "batchSelection": index,
            "batchWarning": warning,
        }

    def _batch_normalize(self, enabled=True, start=1, stop=None, reference=1):
        b = self._require_batch()
        if enabled:
            stop = len(b.binning) if stop is None else stop
            if any(
                isinstance(v, bool) or int(v) != v for v in (start, stop, reference)
            ):
                raise ValueError("Normalization bins and reference must be integers.")
            b.normalize((int(start) - 1, int(stop)), int(reference) - 1)
        else:
            b.restore_normalization()
        return {**self._batch_select(self._batch_index()), **self._batch_snapshot()}

    def _batch_levels(self, **settings):
        return {"batchLevels": image_levels(self._require_batch().data, **settings)}

    def _batch_save(self, path=None):
        from copy import copy
        import os
        import tempfile
        import h5py

        b = self._require_batch()
        path = self._path(path, "batch", save=True)
        if path is None:
            return {"cancelled": True}
        if not Path(path).suffix:
            path += ".h5"
        if Path(path).suffix.lower() not in {".csv", ".h5", ".hdf5", ".nxs"}:
            raise ValueError("Save a batch as HDF5 or CSV.")
        fd, temporary = tempfile.mkstemp(
            prefix=".dioptas-batch-", suffix=Path(path).suffix, dir=Path(path).parent
        )
        os.close(fd)
        try:
            if Path(path).suffix.lower() == ".csv":
                b.save_as_csv(temporary)
            else:
                export = copy(b)
                # Empty paths explicitly represent missing raw provenance.
                if export.files is None or export.pos_map is None:
                    export.files = np.asarray([""])
                    export.pos_map = np.column_stack(
                        (np.zeros(len(b.data), dtype=int), np.arange(len(b.data)))
                    )
                if export.file_map is None:
                    export.file_map = np.asarray([0, len(b.data)])
                export.used_calibration = export.used_calibration or ""
                export.save_proc_data(temporary)
                with h5py.File(temporary, "r+") as f:
                    if getattr(b, "_desktop_wavelength", None) is not None:
                        f["processed/result"].attrs["desktop_wavelength_m"] = (
                            b._desktop_wavelength
                        )
                    f["processed/result"].attrs["desktop_normalized"] = bool(
                        b.normalization_enabled
                    )
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return {"savedPath": path}

    def _save_batch_project(self, project):
        """Optional .dio extension. Qt ignores this desktop series document."""
        import h5py
        import json

        b = self.configuration.batch_model
        if b.data is None:
            return
        group = project.create_group("react_desktop_batch")
        group.attrs["version"] = 1
        for name in (
            "data",
            "binning",
            "azimuthal_std",
            "bkg",
            "file_map",
            "pos_map",
            "pos_map_all",
        ):
            value = getattr(b, name)
            if value is not None:
                group.create_dataset(name, data=value)
        if b.files is not None:
            group.create_dataset("files", data=list(b.files), dtype=h5py.string_dtype())
        group.attrs["metadata"] = json.dumps(
            {
                "unit": b.integration_unit,
                "wavelength": getattr(b, "_desktop_wavelength", None),
                "selected": self._batch_index(),
                "total": b.n_img_all,
                "raw": bool(b.raw_available),
                "calibration": b.used_calibration,
                "mask": b.used_mask,
                "mask_shape": b.used_mask_shape,
                "normalized": bool(b.normalization_enabled),
                "normalization_range": list(b.normalization_range),
                "normalization_reference": int(b.normalization_reference),
            }
        )
        if b.normalization_enabled:
            source = group.create_group("normalization_source")
            for name, value in zip(
                ("data", "spread", "background"), b._normalization_source
            ):
                if value is not None:
                    source.create_dataset(name, data=value)
            source.create_dataset("factors", data=b._normalization_factors)

    def _restore_batch_project(self, path):
        import h5py
        import json
        from dioptas.model.BatchModel import BatchModel

        with h5py.File(path, "r") as f:
            if "react_desktop_batch" not in f:
                return
            group = f["react_desktop_batch"]
            meta = json.loads(group.attrs["metadata"])
            b = BatchModel(self.configuration)
            for name in (
                "data",
                "binning",
                "azimuthal_std",
                "bkg",
                "file_map",
                "pos_map",
                "pos_map_all",
            ):
                if name in group:
                    setattr(b, name, group[name][()])
            if "files" in group:
                b.files = np.asarray(group["files"].asstr()[()])
            b.integration_unit, b.n_img, b.n_img_all = (
                meta["unit"],
                len(b.data),
                meta["total"],
            )
            b.raw_available = meta["raw"]
            b._desktop_wavelength = meta.get("wavelength")
            b.used_calibration, b.used_mask, b.used_mask_shape = (
                meta["calibration"],
                meta["mask"],
                meta["mask_shape"],
            )
            b.normalization_range, b.normalization_reference = (
                tuple(meta["normalization_range"]),
                meta["normalization_reference"],
            )
            if meta["normalized"]:
                source = group["normalization_source"]
                b._normalization_source = tuple(
                    source[n][()] if n in source else None
                    for n in ("data", "spread", "background")
                )
                b._normalized_data, b._normalized_background = b.data, b.bkg
                b._normalization_factors = source["factors"][()]
            self.configuration.batch_model = b
            self._batch_owner, self._batch_selected = b, int(meta["selected"])

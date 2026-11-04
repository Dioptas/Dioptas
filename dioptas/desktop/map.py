# SPDX-License-Identifier: MIT
"""Map commands; all scientific access stays on DesktopBridge's owning thread.

Uses the same isolated integration task, layout, reduction, expression and batch
normalization models as Qt. Display rows are top-origin, as in Qt's map panel.
"""
from __future__ import annotations

from pathlib import Path
import math
import json
import os
import re

import h5py
import numpy as np
from PIL import Image

from dioptas.model.BatchModel import BatchModel
from dioptas.model.Configuration import Configuration
from dioptas.model.MapModel import MapModel, MapPointInfo
from dioptas.model.map_task import compute_map_integration, apply_map_integration
from dioptas.model.worker_configuration import capture_worker_configuration
from dioptas.model.map_reduction import REDUCTIONS
from .display import image_levels


class MapWorkflow:
    def _map_commands(self):
        return {
            "map_snapshot": self._map_snapshot,
            "map_load": self._map_load,
            "map_folder": self._map_folder,
            "map_batch": self._map_batch,
            "map_grid": self._map_grid,
            "map_roi": self._map_roi,
            "map_expression": self._map_expression,
            "map_layer": self._map_layer,
            "map_select": self._map_select,
            "map_arrange": self._map_arrange,
            "map_normalize": self._map_normalize,
            "map_export": self._map_export,
            "map_levels": self._map_levels,
            "map_display": self._map_display,
            "map_mask": self._map_mask,
            "map_poll": self._map_poll,
        }

    def _map_snapshot(self):
        m = self.configuration.map_model
        if m.map is None:
            return {"map": None}
        b = self._map_normalization_model()
        selection = getattr(self, "_map_selected", None)
        if getattr(self, "_map_selected_model", None) is not m:
            selection = None
        if self._has_image:
            image = self.configuration.img_model
            info = m.point_infos[selection] if selection is not None and 0 <= selection < len(m.point_infos) else None
            if info is None or info.filepath != image.filename or info.frame_index != image.series_pos - 1:
                selection = m.get_index_of_file(image.filename, max(0, image.series_pos - 1))
        coords = m.get_point_coordinates(selection) if selection is not None else None
        # Qt plots flipud(map) and translates y back to top-origin rows.
        payload = {
            "raster": self._raster(np.flipud(m.map), max_side=None, histogram=True),
            "unit": m.pattern_unit,
            "points": m.num_points,
            "canRebuild": bool(m.filepaths),
            "dimension": list(m.dimension),
            "presets": [list(d) for d in m.possible_dimensions or []],
            "snake": m.snake, "transpose": m.transpose,
            "flip_horizontal": m.flip_horizontal, "flip_vertical": m.flip_vertical,
            "active": m.active_layer,
            "rois": [dict(name=r.name, min=r.x_min, max=r.x_max,
                          reduction=r.reduction, background=r.subtract_background,
                          color=r.color) for r in m.rois],
            "expressions": dict(m.expressions),
            "selected": selection,
            "selectedCell": list(coords) if coords is not None else None,
            "selectedSlot": m.get_slot_of_point(selection) if selection is not None else getattr(self, "_map_slot", None),
            "normalized": b.normalization_enabled,
            "normalizationRange": [int(v) for v in b.normalization_range],
            "normalizationReference": int(b.normalization_reference),
            "normalizationCoordinates": self._map_normalization_coordinates(m, b),
            "slots": m.get_slots(),
            "labels": m.get_slot_labels(),
            "excluded": list(m.excluded_points),
            # Sent once on map edits, never on detector/map pointer movement.
            "indices": m.index_map.tolist(),
            "slotIndices": m.slot_map.tolist(),
            "values": [[float(v) if np.isfinite(v) else None for v in row] for row in m.map],
        }
        return {"map": payload}

    def _map_response(self):
        self._revision += 1
        return {**self._state(), **self._map_snapshot()}

    def _require_map(self):
        m = self.configuration.map_model
        if m.map is None:
            raise ValueError("Load map image data or a processed batch first.")
        return m

    def _map_folder(self, path=None):
        if path is None:
            raise ValueError("Choose a scan folder in the native desktop application.")
        folder = Path(path).expanduser().resolve()
        if not folder.is_dir():
            raise ValueError("Choose a scan folder.")
        extensions = {".tif", ".tiff", ".edf", ".cbf", ".h5", ".hdf5", ".nxs", ".mar3450"}
        # Natural order is explicit and reproducible; explicit file selections
        # retain their supplied order, including multi-frame file order.
        def key(p):
            return [int(v) if v.isdigit() else v.lower() for v in re.split(r"(\d+)", p.name)]
        paths = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in extensions), key=key)
        if not paths:
            raise ValueError("No supported detector images were found in this folder.")
        return self._map_load(paths=[str(p) for p in paths])

    def _map_load(self, paths=None, reintegrate=False):
        m = self.configuration.map_model
        if reintegrate:
            paths = m.filepaths
        if paths is None and self._choose_file:
            chosen = self._choose_file("map_images", False)
            paths = [chosen] if isinstance(chosen, str) else chosen
        if not paths:
            return {"cancelled": True}
        if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
            raise ValueError("Map source must be an ordered list of image paths.")
        paths = [self._path(p, "image") for p in paths]
        if not self.configuration.calibration_model.is_calibrated:
            raise ValueError("Load a PONI calibration before integrating map images.")
        self._cancel_refinement.clear()
        self._progress = {"running": True, "current": 0, "total": len(paths), "label": "Integrating map"}
        def progress(current, total):
            self._progress = {"running": True, "current": current, "total": total or len(paths), "label": "Integrating map"}
            return not self._cancel_refinement.is_set()
        try:
            result = compute_map_integration(capture_worker_configuration(self.configuration), paths, progress)
            if self._cancel_refinement.is_set():
                return {"cancelled": True}
            if not len(result.pattern_intensities):
                raise ValueError("No image frames were integrated.")
            apply_map_integration(m, result)
            self._map_batch_owner = None
            return self._map_select(index=0)
        finally:
            self._progress = {**self._progress, "running": False}

    def _map_batch(self, path=None):
        path = self._path(path, "map_batch")
        if path is None:
            return {"cancelled": True}
        # Batch readers can load a calibration/mask; keep these effects in an
        # isolated candidate so importing intensities cannot alter live geometry.
        candidate = Configuration()
        candidate.auto_integrate_pattern = candidate.auto_integrate_cake = False
        b = candidate.batch_model
        b.load_proc_data(path)
        if b.data is None or b.binning is None or b.data.ndim != 2 or b.data.shape[1] != len(b.binning) or not len(b.data):
            raise ValueError("The batch does not contain a non-empty pattern matrix and radial axis.")
        if b.integration_unit not in {"2th_deg", "q_A^-1", "d_A"}:
            raise ValueError(f"Unsupported batch radial unit: {b.integration_unit}")
        infos = []
        for i in range(len(b.data)):
            if b.files is not None and b.pos_map is not None:
                file_index, frame = b.pos_map[i]
                infos.append(MapPointInfo(str(b.files[file_index]), int(frame)))
            else:
                # Missing provenance stays missing: no fabricated detector image.
                infos.append(MapPointInfo("", i))
        m = self.configuration.map_model
        m.set_integration_results(np.array(b.binning), np.array(b.data), infos,
                                  list(dict.fromkeys(p.filepath for p in infos if p.filepath)),
                                  pattern_unit=b.integration_unit)
        self._map_batch_owner = None
        return self._map_select(index=0)

    def _map_grid(self, rows=None, columns=None, snake=None, transpose=None,
                  flip_horizontal=None, flip_vertical=None):
        m = self._require_map()
        if rows is not None or columns is not None:
            r, c = rows if rows is not None else m.dimension[0], columns if columns is not None else m.dimension[1]
            if int(r) != r or int(c) != c or min(r, c) < 1 or r*c < m.num_points or r*c > 4_000_000:
                raise ValueError("The grid must hold all scan points (maximum 4 million cells).")
            m.set_dimension((int(r), int(c)))
        for field, value in dict(snake=snake, transpose=transpose, flip_horizontal=flip_horizontal, flip_vertical=flip_vertical).items():
            if value is not None:
                if not isinstance(value, bool):
                    raise ValueError("Scan orientation must be a boolean.")
                setattr(m, field, value)
        return self._map_response()

    def _map_roi(self, op="update", name=None, minimum=None, maximum=None,
                 reduction=None, background=None, new_name=None, color=None, activate=False):
        m = self._require_map()
        if op == "add":
            roi = m.add_roi()
            m.active_layer = roi.name
        elif op == "remove":
            if not m.remove_roi(name):
                raise ValueError("Keep at least one map window.")
        elif op == "update":
            roi = m.get_roi(name)
            if roi is None:
                raise ValueError("Unknown map window.")
            lo = roi.x_min if minimum is None else float(minimum)
            hi = roi.x_max if maximum is None else float(maximum)
            if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
                raise ValueError("Window limits must be finite and increasing.")
            kind = roi.reduction if reduction is None else reduction
            if kind not in REDUCTIONS:
                raise ValueError("Unknown map reduction.")
            if color is not None and (not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color)):
                raise ValueError("Choose a six-digit window color.")
            if new_name is not None and new_name != name:
                if not new_name.isidentifier() or not m.rename_roi(name, new_name):
                    raise ValueError("Choose a unique window identifier.")
            m._suspend_rebuild = True
            try:
                roi.x_min, roi.x_max = lo, hi
                if color is not None:
                    roi.color = color
                roi.reduction = kind
                if background is not None:
                    roi.subtract_background = bool(background)
            finally:
                m._suspend_rebuild = False
            m._roi_changed()
            if activate:
                m.active_layer = roi.name
        else:
            raise ValueError("Unknown window action.")
        return self._map_response()

    def _map_expression(self, name, expression="", remove=False, new_name=None):
        m = self._require_map()
        if remove:
            m.remove_expression(name)
        else:
            from dioptas.model import map_expression
            # Validate before publication; Qt's model deliberately falls back
            # when a saved expression becomes invalid, so reject new typos here.
            problem = map_expression.validate(expression, {r.name for r in m.rois}, overlay_exists=m.overlay_exists)
            if problem:
                raise ValueError(problem)
            values = map_expression.evaluate(expression, {r.name: m.layer_values(r.name) for r in m.rois}, ovl=m.overlay_window_value)
            if values is None or not np.any(np.isfinite(values)):
                raise ValueError("Expression must use existing window names and produce finite values.")
            target = name if new_name is None else new_name.strip()
            if not target or (target != name and (name not in m.expressions or target in m.layer_names())):
                raise ValueError("Choose a unique expression layer name.")
            if not m.set_expression(target, expression):
                raise ValueError("Choose a layer name distinct from window names.")
            if target != name:
                m.remove_expression(name)
            m.active_layer = target
        return self._map_response()

    def _map_layer(self, name):
        m = self._require_map()
        if name not in m.layer_names():
            raise ValueError("Unknown map layer.")
        m.active_layer = name
        return self._map_response()

    def _map_select(self, index=None, row=None, column=None, slot=None, reintegrate=False, integration_view=False):
        m = self._require_map()
        if row is not None and column is not None:
            row, column = int(row), int(column)
            index = m.get_point_index(row, column)
            visible = m.get_slot_at(row, column)
            slot = m.get_row_of_visible_slot(visible) if visible is not None else None
        elif slot is not None:
            slot = int(slot)
            index = m.get_point_of_slot(slot)
        if index is not None:
            index = int(index)
            if not 0 <= index < m.num_points:
                raise ValueError("Map point is outside the scan.")
            slot = m.get_slot_of_point(index)
        self._map_selected, self._map_slot, self._map_selected_model = index, slot, m
        response = {}
        warning = None
        if index is not None:
            info = m.point_infos[index]
            if info.filepath and Path(info.filepath).is_file():
                m.select_point_by_index(index)
                self._has_image = True
                response["image"] = self._raster(self.configuration.img_model.img_data, max_side=None, histogram=True)
                response["rawImage"] = self._raster(self.configuration.img_model.raw_img_data, max_side=None, histogram=True)
                response["mask"] = self._raster(self.configuration.mask_model.get_display_mask(), mask=True, max_side=None)
            else:
                self._has_image = False
                warning = "Raw detector image unavailable; showing the stored pattern."
            if reintegrate and not integration_view:
                if not self._has_image or not self.configuration.is_calibrated:
                    raise ValueError("Reintegration needs the original image and a loaded calibration.")
                x, y = self.configuration.integrate_image_1d(update_pattern_model=False)
                unit = m.pattern_unit
                if self.configuration.integration_unit != unit:
                    from dioptas.model.util.calc import convert_units
                    x = convert_units(x, self.configuration.calibration_model.wavelength,
                                      self.configuration.integration_unit, unit)
            else:
                x, y, unit = m.pattern_x, m.pattern_intensities[index], m.pattern_unit
            self.configuration.pattern_model.set_pattern(x, y, info.filepath, unit=unit)
            self._pattern = {"x": np.asarray(x).tolist(), "y": [float(v) if np.isfinite(v) else None for v in y], "unit": unit,
                             **self._pattern_reference_data(unit)}
        else:
            self._has_image = False
            self._pattern = None
        self._cake = None
        self._rings = []
        self._elapsed = None
        # Map keeps its stored 1D profile. Other views calculate the complete
        # shared image/cake/overlays with the current integration settings.
        self._integration_dirty = bool(self._has_image and self.configuration.is_calibrated)
        if integration_view and self._integration_dirty:
            # A detached map drives the complete Integration workspace without
            # changing the scan's stored or normalized profiles.
            self._calculate()
            response.update(self._snapshot(), mapWarning=warning)
        else:
            response.update(self._map_response(), pattern=self._pattern, cake=None,
                            rings=self._rings, linked=self._linked_snapshot(), mapWarning=warning)
        return response

    def _map_arrange(self, op, slot=None, index=None, offset=0):
        m = self._require_map()
        if op == "gaps":
            count = m.detect_gaps()
            result = self._map_response()
            result["mapWarning"] = f"Filename numbering: {count} blank cells inserted." if count else "No unambiguous filename gaps found (multi-frame files use frame order)."
            return result
        if op == "exclude":
            if index is None or not 0 <= int(index) < m.num_points:
                raise ValueError("Select a scan point to exclude or include.")
            m.set_point_excluded(int(index), not m.is_point_excluded(int(index)))
        else:
            slot = int(slot)
            if not 0 <= slot < m.num_slots:
                raise ValueError("Select an arrangement cell first.")
            if op == "insert":
                m.insert_blank(slot)
            elif op == "remove":
                if not m.can_remove_blank(slot):
                    raise ValueError("Only blank cells can be removed.")
                m.remove_blank(slot)
            elif op == "move":
                target = slot + int(offset)
                if not 0 <= target < m.num_slots:
                    raise ValueError("The cell cannot move outside the grid.")
                m.move_slot(slot, target)
                self._map_slot = target
            else:
                raise ValueError("Unknown arrangement action.")
        return self._map_response()

    def _map_mask(self, use_mask=None, transparent_mask=None, reintegrate=False):
        c = self.configuration
        for value in (use_mask, transparent_mask):
            if value is not None and not isinstance(value, bool):
                raise ValueError("Mask settings must be boolean.")
        if use_mask is not None:
            c.use_mask = use_mask
            self._integration_dirty = True
        if transparent_mask is not None:
            c.transparent_mask = transparent_mask
        selected = self._map_snapshot()["map"]
        if use_mask is not None and reintegrate and selected and selected["selected"] is not None:
            return self._map_select(index=selected["selected"], reintegrate=True)
        # Display changes must preserve the selected stored map pattern.
        return self._map_response()

    def _map_poll(self, follow=True, check_only=False):
        """One bounded, owning-thread Live tick; no watcher or Qt event loop.

        Require unchanged size/mtime in consecutive polls before opening a
        numbered continuation. New frames in an already loaded HDF5 file are
        not inferred from its file size; this follows Qt's new-file workflow.
        """
        from dioptas.model.map_layout import filename_number
        m = self._require_map()
        if not m.filepaths or not self.configuration.is_calibrated:
            raise ValueError("Load the first calibrated scan images before starting Live.")
        if self._map_normalization_model().normalization_enabled:
            raise ValueError("Restore original patterns before appending live images.")
        directory = Path(m.filepaths[-1]).resolve().parent
        if not directory.is_dir():
            raise ValueError("The live scan folder is unavailable.")
        if getattr(self, "_map_poll_model", None) is not m:
            self._map_poll_model, self._map_poll_signatures = m, {}
        previous = self._map_poll_signatures
        signatures = {}
        extensions = {Path(p).suffix.lower() for p in m.filepaths}
        prefix = os.path.commonprefix([Path(p).stem for p in m.filepaths]).rstrip("0123456789")
        present = {str(Path(p).resolve()) for p in m.filepaths}
        numbers = [filename_number(p) for p in m.filepaths]
        highest = max((n for n in numbers if n is not None), default=None)
        candidates = []
        for path in directory.iterdir():
            if not path.is_file() or path.suffix.lower() not in extensions or not path.name.startswith(prefix):
                continue
            resolved = str(path.resolve())
            number = filename_number(path.name)
            if resolved in present or number is None or highest is None or (number <= highest and resolved not in previous):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            signature = (stat.st_size, stat.st_mtime_ns)
            signatures[resolved] = signature
            if stat.st_size > 0 and previous.get(resolved) == signature:
                candidates.append((number, resolved))
        self._map_poll_signatures = signatures
        if check_only:
            return {"mapPending": len(candidates)}
        if not candidates:
            return {}
        # Restore the selected raw image after integration when Follow is off.
        selected = self._map_snapshot()["map"]["selected"]
        before = m.num_points
        failed = m.append_files([p for _, p in sorted(candidates)[:2]])
        if m.num_points == before:
            return {"mapWarning": "Live: waiting for readable scan files."} if failed else {}
        self._map_batch_owner = None
        result = self._map_select(index=m.num_points - 1 if follow else selected)
        if failed:
            result["mapWarning"] = f"Live: {len(failed)} scan file(s) could not be read; retrying."
        return result

    def _map_normalization_model(self):
        m = self.configuration.map_model
        if getattr(self, "_map_batch_owner", None) is not m:
            # Reuse Qt's normalization model without replacing the independent
            # batch workspace's data or its own restore history.
            b = BatchModel(self.configuration)
            b.data, b.binning = m.pattern_intensities, m.pattern_x
            b.integration_unit = m.pattern_unit
            self._map_normalization_batch = b
            self._map_batch_owner = m
            self._map_normalization_definition = None
        return self._map_normalization_batch

    def _map_normalization_coordinates(self, m, batch):
        definition = getattr(self, "_map_normalization_definition", None)
        if definition is not None:
            return dict(definition)
        if not batch.normalization_enabled and m.active_roi is not None:
            roi = m.active_roi
            return {"minimum": roi.x_min, "maximum": roi.x_max, "unit": m.pattern_unit}
        x = np.asarray(m.pattern_x, dtype=float)
        start, stop = batch.normalization_range
        start, stop = max(0, min(int(start), len(x)-1)), max(1, min(int(stop), len(x)))
        if stop <= start:
            start, stop = 0, len(x)
        # Cell boundaries reproduce a legacy [start, stop) interval exactly.
        delta = float(x[1] - x[0]) if len(x) > 1 else max(abs(float(x[0])) * 0.01, 1e-6)
        low = (x[start-1] + x[start]) / 2 if start else x[0] - delta / 2
        high = (x[stop-1] + x[stop]) / 2 if stop < len(x) else x[-1] + (x[-1] - x[-2] if len(x) > 1 else delta) / 2
        if not np.all(np.isfinite([low, high])):
            finite = x[np.isfinite(x)]
            low, high = (float(finite.min()), float(finite.max())) if len(finite) else (0.0, 1.0)
        return {"minimum": float(min(low, high)), "maximum": float(max(low, high)), "unit": m.pattern_unit}

    def _map_normalize(self, enabled=True, start=0, stop=None, reference=0,
                       minimum=None, maximum=None, unit=None, window=None):
        m = self._require_map()
        b = self._map_normalization_model()
        definition = None
        if enabled:
            if window is not None:
                roi = m.get_roi(window)
                if roi is None:
                    raise ValueError("Choose an existing pattern window for normalization.")
                minimum, maximum, unit = roi.x_min, roi.x_max, m.pattern_unit
            if minimum is not None or maximum is not None or unit is not None:
                if minimum is None or maximum is None or unit not in {"2th_deg", "q_A^-1", "d_A"}:
                    raise ValueError("Choose a radial unit and both normalization limits.")
                low, high = float(minimum), float(maximum)
                if not np.all(np.isfinite([low, high])) or low >= high:
                    raise ValueError("Normalization limits must be finite and increasing.")
                if low < 0 or (unit == "d_A" and low == 0) or (unit == "2th_deg" and high > 180):
                    raise ValueError("Choose a physical radial range: nonnegative Q, positive d, or 2θ between 0° and 180°.")
                bounds = np.asarray([low, high])
                if unit != m.pattern_unit:
                    if {unit, m.pattern_unit} <= {"q_A^-1", "d_A"}:
                        with np.errstate(divide="ignore", invalid="ignore"):
                            bounds = 2 * np.pi / bounds
                    else:
                        from dioptas.model.util.calc import convert_units
                        c = self.configuration.calibration_model
                        if not c.is_calibrated or not c.wavelength or c.wavelength <= 0:
                            raise ValueError("Converting an angular normalization range needs a loaded calibration.")
                        with np.errstate(divide="ignore", invalid="ignore"):
                            bounds = convert_units(bounds, c.wavelength, unit, m.pattern_unit)
                    if bounds is None or not np.all(np.isfinite(bounds)):
                        raise ValueError("The normalization range cannot be converted to the stored radial unit.")
                from dioptas.model.map_reduction import window_indices
                indices = window_indices(m.pattern_x, sorted(bounds))
                if not len(indices):
                    raise ValueError("The normalization range contains no stored pattern samples.")
                if np.any(np.diff(indices) != 1):
                    raise ValueError("The normalization range must select contiguous stored samples.")
                start, stop = int(indices[0]), int(indices[-1]) + 1
                definition = {"minimum": low, "maximum": high, "unit": unit}
                if window is not None:
                    definition["window"] = window
            b.normalize((int(start), int(stop if stop is not None else len(m.pattern_x))), int(reference))
            self._map_normalization_definition = definition
        else:
            b.restore_normalization()
        m.set_integration_results(m.pattern_x, b.data, m.point_infos, m.filepaths, m.pattern_unit, keep_layout=True)
        index = getattr(self, "_map_selected", None)
        return self._map_select(index=index) if index is not None else self._map_response()

    def _map_display(self, smooth=1, contours=0):
        from .map_display import preview
        m = self._require_map()
        if int(smooth) != smooth or not 1 <= smooth <= 10 or int(contours) != contours or not 0 <= contours <= 20:
            raise ValueError("Use smoothing 1–10 and contour count 0–20.")
        if m.map.size * max(smooth*smooth, 9 if contours else 1) > 4_000_000:
            raise ValueError("Display interpolation would exceed 4 million cells; reduce smoothing or disable contours.")
        image, paths = preview(m.map, int(smooth), int(contours))
        result = self._raster(image, max_side=None)
        # RasterView draws the upsampled bitmap over the original scan extent.
        result.update(fullWidth=m.map.shape[1], fullHeight=m.map.shape[0], step=1/smooth)
        return {"mapPreview": result, "mapContours": paths}

    def _map_levels(self, **settings):
        levels = image_levels(np.flipud(self._require_map().map), **settings)
        return {"mapLevels": levels}

    def _map_export(self, path=None, png_data=None):
        m = self._require_map()
        path = self._path(path, "map_png" if png_data else "map_export", save=True)
        if path is None:
            return {"cancelled": True}
        suffix = Path(path).suffix.lower()
        if not suffix:
            path += ".png" if png_data else ".txt"
            suffix = ".png" if png_data else ".txt"
        if suffix == ".txt":
            np.savetxt(path, m.map, fmt="%g")
        elif suffix == ".png" and png_data:
            import base64
            import io
            image = Image.open(io.BytesIO(base64.b64decode(png_data, validate=True)))
            image.save(path, format="PNG")
        elif suffix in {".tif", ".tiff"}:
            data = np.asarray(m.map, dtype=float)
            finite = data[np.isfinite(data)]
            minimum = finite.min() if finite.size else 0
            span = np.ptp(finite) if finite.size else 0
            normalized = (data-minimum)/span if span else np.zeros_like(data)
            Image.fromarray((np.nan_to_num(normalized, nan=0.0)*np.iinfo(np.uint32).max).astype(np.uint32)).save(path)
        else:
            raise ValueError("Save tabular text (.txt), normalized TIFF (.tiff), or use the map panel Save PNG action. Use Save project for lossless map and pattern data.")
        return {"savedPath": path}

    def _save_map_normalization(self, project):
        b = getattr(self, "_map_normalization_batch", None)
        if getattr(self, "_map_batch_owner", None) is self.configuration.map_model and b is not None and b.normalization_enabled:
            g = project.create_group("react_map_normalization")
            g.create_dataset("original", data=b._normalization_source[0])
            g.attrs["range"] = b.normalization_range
            g.attrs["reference"] = b.normalization_reference
            definition = getattr(self, "_map_normalization_definition", None)
            if definition is not None:
                g.attrs["coordinates"] = json.dumps(definition)

    def _restore_map_normalization(self, path):
        self._map_selected = self._map_slot = None
        if self.configuration.map_model.map is not None and not self.configuration.img_model.filename:
            self._has_image = False
        self._map_batch_owner = None
        with h5py.File(path, "r") as project:
            if "react_map_normalization" not in project:
                return
            g = project["react_map_normalization"]
            m = self.configuration.map_model
            b = self._map_normalization_model()
            original = g["original"][...]
            if m.pattern_intensities is None or original.shape != m.pattern_intensities.shape:
                return
            b.reset_data()
            b.data, b.binning = original, m.pattern_x
            b.integration_unit = m.pattern_unit
            b.normalize(tuple(g.attrs["range"]), int(g.attrs["reference"]))
            self._map_normalization_definition = json.loads(g.attrs["coordinates"]) if "coordinates" in g.attrs else None
            m.set_integration_results(m.pattern_x, b.data, m.point_infos, m.filepaths, m.pattern_unit, keep_layout=True)
            self._map_batch_owner = m

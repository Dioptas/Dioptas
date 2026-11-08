"""Qt Image-tab multi-file actions on isolated existing image models."""
from pathlib import Path
import tempfile

import numpy as np

from dioptas.model.worker_configuration import capture_worker_configuration, build_worker_configuration
from .image_export import save_tiff_data


class ImageBatchWorkflow:
    def _set_image_batch_mode(self, mode):
        if mode not in {"integrate", "add", "average", "save"}:
            raise ValueError("Choose integrate, add, average or save.")
        self._image_batch_mode = mode
        self._revision += 1
        return self._state()

    def _process_image_batch(self, paths, mode=None, output_directory=None):
        mode = mode or getattr(self, "_image_batch_mode", "integrate")
        if mode not in {"integrate", "add", "average", "save"}:
            raise ValueError("Choose integrate, add, average or save.")
        if mode == "integrate":
            return self._batch_load(paths=paths)
        self._cancel_refinement.clear()
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
            raise ValueError("Choose an ordered list of image files.")
        paths = [self._path(p, "image") for p in paths]
        if mode in {"add", "average"}:
            from dioptas.model.ImgModel import ImgModel
            expected = self._expected_image_shape()
            first_shape = tuple(ImgModel().get_image_data(paths[0])["img_data"].shape)
            if expected and first_shape != expected:
                raise ValueError(
                    "Combined images must match the current detector dimensions. "
                    "Open one image first to change the detector setup and reset calibration."
                )
        output = None
        if mode == "save":
            if output_directory is None and self._choose_file:
                output_directory = self._choose_file("directory", False)
            if not output_directory:
                return {"cancelled": True}
            output = Path(output_directory).expanduser().resolve()
            if not output.is_dir():
                raise ValueError("Choose an existing output folder.")
            names = ["batch_" + Path(p).stem + ".tiff" for p in paths]
            if len(set(names)) != len(names) or any((output / name).exists() for name in names):
                raise ValueError("Batch output filenames must be unique and must not already exist.")
        state = capture_worker_configuration(self.configuration)
        state.image["filename"], state.image["series_pos"] = paths[0], 1
        worker = build_worker_configuration(state)
        image = worker.img_model
        image.blockSignals(True)
        self._progress = {"running": True, "current": 0, "total": len(paths), "label": "Saving batch images" if output else "Combining batch images"}
        try:
            with tempfile.TemporaryDirectory(dir=output) as staging:
                expected = image.raw_img_data.shape
                for i, path in enumerate(paths):
                    if self._cancel_refinement.is_set():
                        return {"cancelled": True}
                    if output:
                        image.load(path)
                        save_tiff_data(Path(staging) / names[i], image.img_data)
                    elif i:
                        data = image.get_image_data(path)["img_data"]
                        for transform in image.img_transformations:
                            data = transform(data)
                        if data.shape != expected:
                            raise ValueError("Batch images must have matching detector shapes.")
                        image.add(path)
                    self._progress["current"] = i + 1
                if self._cancel_refinement.is_set():
                    return {"cancelled": True}
                if output:
                    published = []
                    try:
                        for name in names:
                            target = output / name
                            with target.open("xb") as destination:
                                published.append(target)
                                destination.write((Path(staging) / name).read_bytes())
                    except Exception:
                        for target in published:
                            target.unlink(missing_ok=True)
                        raise
                    return {"savedPaths": [str(output / name) for name in names], "imageBatchSaved": True}
                if mode == "average":
                    image._img_data = image._img_data / len(paths)
                    image._calculate_img_data()
                combined = np.array(image.raw_img_data, copy=True)
            live = self.configuration.img_model
            live.load(paths[0])
            live._img_data = combined
            live._calculate_img_data()
            self.configuration.calibration_model.clear_peaks()
            self._fit_rms = None
            self._has_image = True
            self._calculate()
            return self._snapshot(include_image=True)
        finally:
            image.blockSignals(False)
            self._progress["running"] = False

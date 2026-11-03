"""Test-only JSON-lines host: browser automation exercises real Dioptas models.

Tauri uses dioptas.desktop.stdio; the legacy host uses pywebview directly.
Neither native host uses this browser-test process.
"""

import contextlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
with contextlib.redirect_stdout(sys.stderr):
    from dioptas.desktop.bridge import DesktopBridge

artifacts = root / "desktop" / "artifacts"
artifacts.mkdir(exist_ok=True)


def choose_file(kind, save):
    if kind == "map_images":
        return sorted(str(p) for p in (root / "dioptas/tests/data/map").glob("*.tif"))
    if kind == "map_png":
        return str(artifacts / "map.png")
    if kind == "map_export":
        return str(artifacts / "map.txt")
    if kind == "map_batch":
        return str(artifacts / "map-batch.h5")
    if save:
        return str(
            artifacts
            / {
                "project": "experiment.dio",
                "pattern": "pattern.xy",
                "calibration": "calibration.poni",
                "peaks": "calibration-peaks.json",
                "batch": "batch.h5",
                "mask": "mask.mask",
                "image_export": "saved-image.png",
                "cake_export": "saved-cake.png",
            }[kind]
        )
    if kind == "overlays":
        return [str(artifacts / "overlay-one.xy"), str(artifacts / "overlay-two.xy")]
    if kind == "pattern":
        return str(artifacts / "pattern.xy")
    if kind == "phase":
        return str(root / "dioptas/tests/data/jcpds/au_version3.jcpds")
    if kind == "directory":
        return str(artifacts)
    if kind == "mask":
        return str(artifacts / "mask.mask")
    if kind == "project":
        return str(artifacts / "experiment.dio")
    if kind == "calibration":
        return str(artifacts / "calibration.poni")
    if kind == "peaks":
        return str(artifacts / "calibration-peaks.json")
    return str(root / "dioptas/tests/data/CeO2_Pilatus1M.tif")


# Like pywebview, dispatch independent requests on separate threads so progress
# and cancellation can bypass the scientific session's mutation lock.
from concurrent.futures import ThreadPoolExecutor
import threading

protocol = sys.__stdout__
sys.stdout = sys.stderr
session = DesktopBridge(choose_file=choose_file)
write_lock = threading.Lock()


def dispatch(request):
    result = session.invoke(request["action"], request.get("payload"))
    encoded = json.dumps({"id": request["id"], "result": result}, allow_nan=False)
    with write_lock:
        protocol.write(encoded + "\n")
        protocol.flush()


try:
    with ThreadPoolExecutor(max_workers=4) as workers:
        for line in sys.stdin:
            workers.submit(dispatch, json.loads(line))
finally:
    session.close()

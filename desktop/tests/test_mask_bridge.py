"""Progress and cancellation stay responsive during a model plugin call."""

from concurrent.futures import ThreadPoolExecutor
import threading
import time

import numpy as np

from dioptas.desktop.bridge import DesktopBridge


def test_mask_plugin_cancel_bypasses_owning_worker_and_restores_state():
    bridge = DesktopBridge()
    entered, release = threading.Event(), threading.Event()
    try:
        assert bridge.invoke("example")["ok"]

        def install_on_owner():
            plugin = bridge._session.configuration.mask_plugin_manager.get_plugin(
                "Threshold Mask"
            )

            def compute(image, **kwargs):
                entered.set()
                assert release.wait(10)
                return np.ones(image.shape, dtype=bool)

            plugin.compute_mask = compute

        bridge._worker.submit(install_on_owner).result()
        with ThreadPoolExecutor(max_workers=1) as caller:
            pending = caller.submit(
                bridge.invoke,
                "mask_plugin",
                {"name": "Threshold Mask", "enabled": True},
            )
            assert entered.wait(10)
            start = time.monotonic()
            assert bridge.invoke("progress")["progress"]["running"]
            assert bridge.invoke("cancel_refinement")["ok"]
            assert time.monotonic() - start < 1
            release.set()
            result = pending.result(timeout=10)
        assert not result["ok"] and "cancelled" in result["error"]
        state = bridge.invoke("state")["state"]
        assert state["maskedPixels"] == 0
        assert not state["maskDetails"]["plugins"][0]["enabled"]
    finally:
        release.set()
        bridge.close()

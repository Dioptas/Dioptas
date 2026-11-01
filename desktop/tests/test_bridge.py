"""Webview dispatch must respect thread-affine native processing objects."""

from concurrent.futures import ThreadPoolExecutor
import threading

from dioptas.desktop import bridge


def test_processing_lifetime_has_one_owner_and_cancel_bypasses_busy_worker(monkeypatch):
    lifetime = []
    entered = threading.Event()
    cancelled = threading.Event()

    class ThreadBoundSession:
        def __init__(self, **kwargs):
            self.owner = threading.get_ident()
            lifetime.append(("created", self.owner))

        def invoke(self, action, arguments=None):
            if action == "progress":
                return {"ok": True, "running": entered.is_set()}
            if action == "cancel_refinement":
                cancelled.set()
                return {"ok": True}
            assert threading.get_ident() == self.owner
            if action == "blocking_fit":
                entered.set()
                assert cancelled.wait(5), "Cancellation was queued behind the fit"
            return {"ok": True, "owner": self.owner}

        def __del__(self):
            lifetime.append(("released", threading.get_ident()))

    monkeypatch.setattr(bridge, "DesktopSession", ThreadBoundSession)
    processor = bridge.DesktopBridge()
    try:
        with ThreadPoolExecutor(max_workers=2) as callers:
            first = callers.submit(processor.invoke, "state").result()
            blocked = callers.submit(processor.invoke, "blocking_fit")
            assert entered.wait(5)
            assert processor.invoke("progress")["running"]
            assert processor.invoke("cancel_refinement")["ok"]
            assert blocked.result(timeout=5)["owner"] == first["owner"]
            assert callers.submit(processor.invoke, "state").result() == first
    finally:
        processor.close()
    assert lifetime == [("created", first["owner"]), ("released", first["owner"])]
    assert not processor.invoke("state")["ok"]

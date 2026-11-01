# SPDX-License-Identifier: MIT
"""Keep native processing objects on one thread across webview requests."""

from concurrent.futures import ThreadPoolExecutor
import gc
import threading

from .session import DesktopSession


class DesktopBridge:
    """A webview can dispatch successive calls on different threads.

    Serializing calls with a lock is insufficient for thread-affine native
    integrators. Construct, use and release the session on the same worker.
    Only the plain progress data and cancellation event bypass this worker.
    """

    def __init__(self, choose_file=None, *, binary_images=False):
        self._dispatch_lock = threading.Lock()
        self._closed = False
        self._worker = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="dioptas-processing"
        )
        try:
            self._session = self._worker.submit(
                DesktopSession, choose_file=choose_file, binary_images=binary_images
            ).result()
        except BaseException:
            self._worker.shutdown()
            raise

    def invoke(self, action, arguments=None):
        with self._dispatch_lock:
            if self._closed:
                return {"ok": False, "error": "The desktop session is closed."}
            if action in {"progress", "cancel_refinement"}:
                return self._session.invoke(action, arguments)
            pending = self._worker.submit(self._invoke_on_worker, action, arguments)
        return pending.result()

    def _invoke_on_worker(self, action, arguments):
        # Do not keep a caller-thread reference to the scientific session:
        # window closure can coincide with the final processing response.
        return self._session.invoke(action, arguments)

    def _release(self):
        self._session = None
        # Shared models contain signal/history cycles. Release those native
        # objects here too, before the owning processing thread exits.
        gc.collect()

    def close(self):
        with self._dispatch_lock:
            if self._closed:
                return
            self._closed = True
            released = self._worker.submit(self._release)
        released.result()
        self._worker.shutdown()

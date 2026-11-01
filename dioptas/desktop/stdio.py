# SPDX-License-Identifier: MIT
"""Local Tauri processing transport. Stdin/stdout carry JSON; no sockets.

Scientific objects keep the same dedicated owning thread as the pywebview
host. Progress/cancel are dispatched by the reader even while fitting is busy.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sys
import threading


def serve(stream, protocol, session):
    write_lock = threading.Lock()

    def dispatch(request):
        identifier = request.get("id") if isinstance(request, dict) else None
        try:
            if not isinstance(request, dict) or not isinstance(identifier, int):
                raise ValueError("A request needs an integer id.")
            action = request.get("action")
            if not isinstance(action, str):
                raise ValueError("A request needs a command name.")
            if action == "__host__":
                import psutil

                widgets = sys.modules.get("PyQt6.QtWidgets")
                process = psutil.Process()
                listeners = sum(
                    connection.status == psutil.CONN_LISTEN
                    for owner in (process, process.parent())
                    if owner is not None
                    for connection in owner.connections(kind="tcp")
                )
                result = {
                    "ok": True,
                    "protocol": 1,
                    "transport": "stdio",
                    "pid": os.getpid(),
                    "qtApplication": bool(widgets and widgets.QApplication.instance()),
                    "tcpListeners": listeners,
                }
            else:
                result = session.invoke(action, request.get("payload"))
            encoded = json.dumps({"id": identifier, "result": result}, allow_nan=False)
        except Exception as exc:
            encoded = json.dumps({"id": identifier, "result": {"ok": False, "error": str(exc)}})
        with write_lock:
            protocol.write(encoded + "\n")
            protocol.flush()

    workers = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dioptas-command")
    try:
        for line in stream:
            try:
                request = json.loads(line)
            except (ValueError, TypeError):
                dispatch(None)
                continue
            if isinstance(request, dict) and request.get("action") in {"progress", "cancel_refinement"}:
                dispatch(request)
            else:
                workers.submit(dispatch, request)
    finally:
        # Dropping the native host's pipe cancels a fit before waiting for it.
        session.invoke("cancel_refinement")
        workers.shutdown(wait=True)
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Dioptas local processing pipe")
    parser.add_argument("--example", action="store_true")
    args = parser.parse_args()

    # Protect framing from Python prints AND native-library writes to fd 1.
    # Only the duplicated descriptor remains connected to the host's pipe.
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr

    from .bridge import DesktopBridge

    session = DesktopBridge()
    if args.example:
        result = session.invoke("example")
        if not result["ok"]:
            session.close()
            raise RuntimeError(result["error"])
    try:
        serve(sys.stdin, protocol, session)
    finally:
        protocol.close()


if __name__ == "__main__":
    main()

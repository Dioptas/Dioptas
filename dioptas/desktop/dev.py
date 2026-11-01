# SPDX-License-Identifier: MIT
"""Owned localhost Vite frontend for source-checkout hot reload."""

import atexit
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


class LiveFrontend:
    def __init__(self):
        desktop = Path(__file__).resolve().parents[2] / "desktop"
        vite = desktop / "node_modules/vite/bin/vite.js"
        node = shutil.which("node")
        if not node or not vite.is_file():
            raise RuntimeError("Live preview requires Node and frontend dependencies: cd desktop && npm ci")
        # Use our own free loopback port, never reuse another project's server.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self._probes = []
        self.url = f"http://127.0.0.1:{port}"
        self.process = subprocess.Popen(
            [node, str(vite), "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
            cwd=desktop, stdin=subprocess.DEVNULL, stdout=sys.stderr, stderr=sys.stderr,
        )
        atexit.register(self.close)
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError("The live frontend could not start; see the Vite output.")
                try:
                    with urlopen(self.url + "/@vite/client", timeout=0.4) as response:
                        if response.status == 200:
                            return
                except (URLError, TimeoutError):
                    time.sleep(0.1)
            raise RuntimeError("Timed out waiting for the live frontend.")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)

        for path in self._probes:
            path.unlink(missing_ok=True)
        self._probes.clear()

    def verify_reload(self, window):
        """Native smoke probe: edit a disposable CSS module, never user source."""
        import json
        import uuid
        token = uuid.uuid4().hex
        path = Path(__file__).resolve().parents[2] / "desktop/src" / f"__dioptas_live_check_{token}.css"
        self._probes.append(path)
        path.write_text(":root { --dioptas-hmr-check: before; }\n")
        module = f"import '/src/{path.name}';"
        window.evaluate_js(f"""(() => {{
            window.__dioptasLiveProbe = {json.dumps(token)};
            const script = document.createElement('script');
            script.type = 'module'; script.textContent = {json.dumps(module)};
            document.head.appendChild(script);
        }})()""")
        def wait_for(value):
            for _ in range(80):
                result = window.evaluate_js("getComputedStyle(document.documentElement).getPropertyValue('--dioptas-hmr-check').trim()")
                if result == value:
                    return True
                time.sleep(0.1)
            return False
        if not wait_for("before"):
            return False
        path.write_text(":root { --dioptas-hmr-check: after; }\n")
        return wait_for("after") and window.evaluate_js(f"window.__dioptasLiveProbe === {json.dumps(token)}")

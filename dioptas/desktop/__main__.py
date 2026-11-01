# SPDX-License-Identifier: MIT
"""Launch the experimental React desktop client with an in-process bridge."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Dioptas React desktop preview")
    parser.add_argument(
        "--example",
        action="store_true",
        help="Open the real CeO2 source-checkout fixture",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable webview developer tools"
    )
    parser.add_argument("--dev", action="store_true", help="Live React/CSS updates using Vite in this source checkout")
    parser.add_argument("--smoke", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        import webview
    except ImportError:
        parser.error(
            "Install the desktop extra first: uv sync --python 3.13 --extra desktop"
        )
    from .bridge import DesktopBridge

    entry = Path(__file__).parent / "ui" / "index.html"
    if not args.dev and not entry.is_file():
        parser.error("Build the interface first: cd desktop && npm ci && npm run build")

    window = None

    def choose_file(kind, save):
        if kind == "directory":
            result = window.create_file_dialog(webview.FileDialog.FOLDER)
            return result if isinstance(result, str) else result[0] if result else None
        filters = {
            "image": (
                "Detector images (*.tif;*.tiff;*.edf;*.cbf;*.h5;*.hdf5;*.nxs;*.mar3450)",
                "All files (*.*)",
            ),
            "calibration": ("PONI calibration (*.poni)",),
            "project": ("Dioptas project (*.dio)",),
            "pattern": ("Diffraction pattern (*.xy;*.xye;*.chi;*.dat;*.fxye)",),
            "phase": ("Diffraction phase (*.jcpds;*.cif;*.eosmat;*.json)",),
            "batch": ("Integrated batch (*.h5;*.csv)",),
            "mask": ("Detector mask (*.mask;*.npy;*.tif;*.edf)",),
            "detector": ("Detector definition (*.h5;*.hdf5;*.nxs)",),
            "distortion": ("Distortion spline (*.spline)",),
            "calibrant": ("Calibrant d spacings (*.D;*.d)",),
        }
        result = window.create_file_dialog(
            webview.FileDialog.SAVE if save else webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=filters[kind],
            save_filename={
                "project": "experiment.dio",
                "pattern": "pattern.xy",
                "calibration": "calibration.poni",
            }.get(kind, ""),
        )
        return result if isinstance(result, str) else result[0] if result else None

    session = DesktopBridge(choose_file=choose_file)
    if args.example:
        result = session.invoke("example")
        if not result["ok"]:
            parser.error(result["error"])

    # The single-file bundle is supplied as HTML: no local HTTP/API server.
    class Bridge:
        # Expose only commands, never the session's model or public properties.
        def invoke(self, action, payload=None):
            return session.invoke(action, payload)

    live_frontend = None
    try:
        if args.dev:
            from .dev import LiveFrontend
            live_frontend = LiveFrontend()
            source = {"url": live_frontend.url}
        else:
            source = {"html": entry.read_text(encoding="utf-8")}
    except Exception as exc:
        session.close()
        parser.error(str(exc))

    window = webview.create_window(
        "Dioptas · Live preview" if args.dev else "Dioptas · Desktop preview",
        **source,
        js_api=Bridge(),
        width=1440,
        height=940,
        min_size=(1000, 700),
        background_color="#101419",
        text_select=True,
    )
    if args.smoke:
        import json
        import os
        import time

        def smoke():
            try:
                for _ in range(100):
                    time.sleep(0.2)
                    ready = window.evaluate_js(
                        "document.querySelector('[data-testid=detector-canvas]') !== null"
                    )
                    if ready:
                        break
                else:
                    raise RuntimeError("Native React interface did not mount")
                report = window.evaluate_js(
                    "({title: document.title, canvases: document.querySelectorAll('canvas').length, "
                    "calibrationVisible: document.querySelector('[aria-label=\"Calibration steps\"]') !== null, "
                    "imageVisible: document.body.innerText.includes('CeO2_Pilatus1M.tif'), "
                    "bridge: !!window.pywebview.api.invoke})"
                )
                report["histogramVisible"] = window.evaluate_js(
                    "document.querySelector('[data-testid=\"intensity-histogram\"]') !== null"
                )
                report["wheelEventPrevented"] = window.evaluate_js("""
                    (() => {
                        const canvas = document.querySelector('[data-testid="detector-canvas"]');
                        const box = canvas.getBoundingClientRect();
                        const event = new WheelEvent('wheel', {
                            bubbles: true, cancelable: true, deltaY: -120,
                            clientX: box.x + box.width / 2,
                            clientY: box.y + box.height / 2
                        });
                        return !canvas.dispatchEvent(event) && event.defaultPrevented;
                    })()
                """)
                if live_frontend:
                    report["hotReloadVerified"] = live_frontend.verify_reload(window)
                    if not report["hotReloadVerified"]:
                        raise RuntimeError("The native frontend did not apply the live CSS update")
                display = session.invoke("state")["image"]
                report["fullResolutionDisplay"] = (
                    display["step"] == 1
                    and display["width"] == display["fullWidth"]
                    and display["height"] == display["fullHeight"]
                )
                import sys
                import psutil

                qt_widgets = sys.modules.get("PyQt6.QtWidgets")
                report["qtApplication"] = bool(
                    qt_widgets and qt_widgets.QApplication.instance()
                )
                report["renderer"] = webview.guilib.renderer
                report["tcpListeners"] = sum(
                    connection.status == psutil.CONN_LISTEN
                    for connection in psutil.Process().connections(kind="tcp")
                )
                print(json.dumps({"nativeSmoke": report}), flush=True)
                if (
                    not report["bridge"]
                    or not report["imageVisible"]
                    or not report["calibrationVisible"]
                    or not report["histogramVisible"]
                    or not report["wheelEventPrevented"]
                    or not report["fullResolutionDisplay"]
                    or report["qtApplication"]
                    or report["tcpListeners"]
                ):
                    raise RuntimeError("Native session did not reach the interface")
            except Exception as exc:
                print(json.dumps({"nativeSmokeError": str(exc)}), flush=True)
                os._exit(1)
            finally:
                window.destroy()

        try:
            webview.start(smoke, debug=args.debug, http_server=False)
        finally:
            session.close()
            if live_frontend:
                live_frontend.close()
    else:
        try:
            webview.start(debug=args.debug, http_server=False)
        finally:
            session.close()
            if live_frontend:
                live_frontend.close()


if __name__ == "__main__":
    main()

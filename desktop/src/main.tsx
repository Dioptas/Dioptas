import { createRoot } from "react-dom/client";
import App from "./App";
import { DetachedBatchWindow } from "./DetachedBatchWindow";
import { DetachedMapWindow } from "./DetachedMapWindow";
import { NativePhaseEditor } from "./NativePhaseEditor";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { NativeCalibrationTooltip } from "./NativeCalibrationTooltip";
import { installNativeColorPickerAnchors } from "./nativeColorPicker";
import { installSpinBoxWheel } from "./spinBoxWheel";
import "./style.css";
import "./buttons.css";
import "./surfaces.css";
import "./navigation.css";
import "./calibrationSetup.css";
import "./calibrationNavigation.css";
import "./uiTheme.css";

// Keep the webview's Reload/Inspect menu out of the entire desktop interface,
// including dialogs rendered through portals. Plot right-button gestures remain active.
document.addEventListener("contextmenu", (event) => event.preventDefault());

installNativeColorPickerAnchors();
installSpinBoxWheel();

if (
  import.meta.env.VITE_DIOPTAS_PATTERN_BENCHMARK === "1" &&
  isTauri() &&
  getCurrentWindow().label === "main"
) {
  import("./patternBenchmark").then(({ installPatternBenchmark }) => {
    const element = document.getElementById("root")!;
    element.style.cssText =
      "display:flex;width:1000px;height:600px;background:#101518";
    installPatternBenchmark(element);
  });
} else {
  createRoot(document.getElementById("root")!).render(
    (isTauri() && getCurrentWindow().label === "batch-window") ||
      new URLSearchParams(location.search).has("batch_window") ? (
      <DetachedBatchWindow />
    ) : (isTauri() && getCurrentWindow().label === "map-window") ||
      new URLSearchParams(location.search).has("map_window") ? (
      <DetachedMapWindow />
    ) : isTauri() && getCurrentWindow().label === "calibration-tooltip" ? (
      <NativeCalibrationTooltip />
    ) : isTauri() && getCurrentWindow().label === "phase-editor" ? (
      <NativePhaseEditor />
    ) : (
      <App />
    ),
  );
}

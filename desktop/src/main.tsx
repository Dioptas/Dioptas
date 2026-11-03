import { createRoot } from "react-dom/client";
import App from "./App";
import { NativePhaseEditor } from "./NativePhaseEditor";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { NativeCalibrationTooltip } from "./NativeCalibrationTooltip";
import { installNativeColorPickerAnchors } from "./nativeColorPicker";
import "./style.css";
import "./buttons.css";
import "./surfaces.css";
import "./navigation.css";
import "./calibrationSetup.css";
import "./calibrationNavigation.css";

// Keep the webview's Reload/Inspect menu out of the entire desktop interface,
// including dialogs rendered through portals. Plot right-button gestures remain active.
document.addEventListener("contextmenu", (event) => event.preventDefault());

installNativeColorPickerAnchors();

createRoot(document.getElementById("root")!).render(
  isTauri() && getCurrentWindow().label === "calibration-tooltip" ? (
    <NativeCalibrationTooltip />
  ) : isTauri() && getCurrentWindow().label === "phase-editor" ? (
    <NativePhaseEditor />
  ) : (
    <App />
  ),
);

import { createRoot } from "react-dom/client";
import App from "./App";
import "./style.css";
import "./buttons.css";
import "./surfaces.css";

// Keep the webview's Reload/Inspect menu out of the entire desktop interface,
// including dialogs rendered through portals. Plot right-button gestures remain active.
document.addEventListener("contextmenu", (event) => event.preventDefault());

createRoot(document.getElementById("root")!).render(<App />);

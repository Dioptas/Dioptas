import { createLucideIcon } from "lucide-react";

/** Offset diffraction traces for the compact Waterfall action. */
export const WaterfallIcon = createLucideIcon("Waterfall", [
  ["path", { d: "M3 7h4l2-4 2 4h10", key: "top" }],
  ["path", { d: "M3 13h7l2-4 2 4h7", key: "middle" }],
  ["path", { d: "M3 19h10l2-4 2 4h4", key: "bottom" }],
]);

/** One background glyph for both overlay selection and pattern capture. */
export const PatternBackgroundIcon = createLucideIcon("PatternBackground", [
  ["path", { d: "M3 15h4l3-9 4 9h7", key: "pattern" }],
  ["path", { d: "M3 20h18", stroke: "#e77777", key: "background" }],
]);

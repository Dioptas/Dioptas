import { useState } from "react";
export type MaskShape =
  "navigate" | "point" | "circle" | "rectangle" | "polygon" | "arc";
export type MaskPoint = [number, number];
export interface MaskOverlay {
  paths: MaskPoint[][];
  ellipse?: { cx: number; cy: number; rx: number; ry: number };
  erase: boolean;
}
export interface PluginSpec {
  type: string;
  default?: string | number | boolean;
  label?: string;
  description?: string;
  min?: number;
  max?: number;
  step?: number;
  choices?: string[];
}
export interface MaskPlugin {
  name: string;
  description: string;
  enabled: boolean;
  settings: Record<string, string | number | boolean>;
  schema: Record<string, PluginSpec>;
  maskedPixels: number;
}
export interface MaskDetails {
  mode: boolean;
  filename: string | null;
  plugins: MaskPlugin[];
}
export function useMaskTools() {
  const [shape, setShape] = useState<MaskShape>("navigate");
  const [erase, setErase] = useState(false);
  const [diameter, setDiameter] = useState(20);
  return { shape, setShape, erase, setErase, diameter, setDiameter };
}
export type MaskTools = ReturnType<typeof useMaskTools>;
export const shapeHelp: Record<MaskShape, string> = {
  navigate: "Left-drag zoom · right-drag pan · right-click out",
  point:
    "Click to stamp · drag to zoom · Shift-drag to paint · Ctrl-drag or right-drag to pan · Q/W adjusts diameter",
  circle:
    "Click the center, move outward, then click the circle's edge. Esc cancels.",
  rectangle: "Click two opposite corners. Esc cancels the selection.",
  polygon: "Click vertices; double-click or Enter to finish. Esc cancels.",
  arc: "Click start, middle and end along an arc, then click its width. Esc cancels.",
};
export function previewMask(
  shape: MaskShape,
  points: MaskPoint[],
  hover: MaskPoint | null,
  erase: boolean,
): MaskOverlay {
  const result: MaskOverlay = { paths: [], erase };
  if (!points.length) return result;
  const p = [...points, ...(hover ? [hover] : [])];
  if ((shape === "rectangle" || shape === "circle") && p.length >= 2) {
    const [[x1, y1], [x2, y2]] = p;
    if (shape === "circle")
      result.ellipse = {
        cx: x1,
        cy: y1,
        rx: Math.hypot(x2 - x1, y2 - y1),
        ry: Math.hypot(x2 - x1, y2 - y1),
      };
    else
      result.paths = [
        [
          [x1, y1],
          [x2, y1],
          [x2, y2],
          [x1, y2],
        ],
      ];
  } else if (shape === "arc" && p.length >= 3) {
    const [[ax, ay], [bx, by], [cx, cy]] = p;
    const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
    if (Math.abs(d) < 1e-10) {
      result.paths = [p];
      return result;
    }
    const a = ax * ax + ay * ay,
      b = bx * bx + by * by,
      c = cx * cx + cy * cy;
    const x = (a * (by - cy) + b * (cy - ay) + c * (ay - by)) / d,
      y = (a * (cx - bx) + b * (ax - cx) + c * (bx - ax)) / d;
    const r = Math.hypot(ax - x, ay - y),
      start = Math.atan2(ay - y, ax - x),
      mid = Math.atan2(by - y, bx - x),
      end = Math.atan2(cy - y, cx - x);
    const tau = 2 * Math.PI,
      positive = (v: number) => ((v % tau) + tau) % tau;
    let sweep = positive(end - start);
    if (positive(mid - start) > sweep) sweep -= tau;
    const width =
      p.length >= 4 ? Math.abs(r - Math.hypot(p[3][0] - x, p[3][1] - y)) : 1;
    const edge = (radius: number) =>
      Array.from({ length: 50 }, (_, i): MaskPoint => [
        x + radius * Math.cos(start + (sweep * i) / 49),
        y + radius * Math.sin(start + (sweep * i) / 49),
      ]);
    result.paths = [[...edge(r + width), ...edge(r - width).reverse()]];
  } else result.paths = [p];
  return result;
}

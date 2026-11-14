import { createLucideIcon } from "lucide-react";

/**
 * A shaded x-range between two edges. It carries no curve or image so it reads
 * the same on the 1D pattern and on the 2D cake, where the band spans all azimuths.
 */
export const RegionBandIcon = createLucideIcon("RegionBand", [
  [
    "rect",
    {
      x: "6",
      y: "4",
      width: "12",
      height: "16",
      fill: "currentColor",
      fillOpacity: "0.25",
      stroke: "none",
      key: "band",
    },
  ],
  ["path", { d: "M6 3v18", key: "left-edge" }],
  ["path", { d: "M18 3v18", key: "right-edge" }],
]);

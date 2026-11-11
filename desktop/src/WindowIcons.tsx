import { createLucideIcon } from "lucide-react";

/** The ExternalLink window outline, with its arrow pointing back inside. */
export const DockWindowIcon = createLucideIcon("DockWindow", [
  ["path", { d: "M16 14h-6V8", key: "arrowhead" }],
  ["path", { d: "M21 3 10 14", key: "arrow" }],
  [
    "path",
    {
      d: "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6",
      key: "window",
    },
  ],
]);

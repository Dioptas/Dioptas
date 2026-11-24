// Pure path constants for prebuilt UI test harnesses (zero Vite imports so
// smoke checks running against prebuilt HTML never load Vite eagerly).
import path from "node:path";
import { fileURLToPath } from "node:url";

export const root = fileURLToPath(new URL("../", import.meta.url));
export const harnessOutDir = path.join(root, "target/test-harnesses");
export const harnessEntries = [
  "scripts/batch_surface_harness.html",
  "scripts/rendering_fixture.html",
  "scripts/ui_fixture.html",
];

export const harnessOutputPath = (entry) => path.join(harnessOutDir, entry);

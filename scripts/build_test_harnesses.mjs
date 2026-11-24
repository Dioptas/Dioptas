// Prebuilds the standalone HTML harnesses used by headless UI smoke checks so
// each check serves a single-file bundle instead of starting a cold Vite dev
// server. Outputs live under target/test-harnesses/ so dist/ stays clean.
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

export const root = fileURLToPath(new URL("../", import.meta.url));
export const harnessOutDir = path.join(root, "target/test-harnesses");
export const harnessEntries = [
  "scripts/batch_surface_harness.html",
  "scripts/rendering_fixture.html",
  "scripts/ui_fixture.html",
];

export const harnessOutputPath = (entry) => path.join(harnessOutDir, entry);

export async function buildTestHarnesses() {
  await mkdir(harnessOutDir, { recursive: true });
  for (const entry of harnessEntries) {
    await build({
      configFile: false,
      root,
      plugins: [react(), viteSingleFile()],
      logLevel: "error",
      build: {
        outDir: harnessOutDir,
        emptyOutDir: false,
        rollupOptions: { input: path.join(root, entry) },
      },
    });
  }
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  await buildTestHarnesses();
}

// Prebuilds the standalone HTML harnesses used by headless UI smoke checks so
// each check serves a single-file bundle instead of starting a cold Vite dev
// server. Outputs live under target/test-harnesses/ so dist/ stays clean.
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";
import {
  harnessEntries,
  harnessOutDir,
  harnessOutputPath,
  root,
} from "./test_harness_paths.mjs";

export { harnessEntries, harnessOutDir, harnessOutputPath, root };

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

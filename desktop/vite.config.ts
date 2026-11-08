import { execFileSync } from "node:child_process";
import { cpSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

let revision = "unknown";
try {
  revision = execFileSync("git", ["describe", "--always", "--dirty"], {
    cwd: fileURLToPath(new URL("../", import.meta.url)),
    encoding: "utf8",
  }).trim();
} catch {
  /* Source archives have no Git metadata. */
}
export default defineConfig({
  define: {
    "import.meta.env.VITE_DIOPTAS_BUILD": JSON.stringify(
      `0.1.0 ${revision} built ${new Date().toISOString()}`,
    ),
  },
  plugins: [
    react(),
    viteSingleFile(),
    {
      name: "bundle-colormap-attribution",
      apply: "build",
      closeBundle() {
        cpSync(
          fileURLToPath(new URL("./licenses", import.meta.url)),
          fileURLToPath(
            new URL("../dioptas/desktop/ui/licenses", import.meta.url),
          ),
          { recursive: true },
        );
      },
    },
  ],
  server: {
    watch: {
      ignored: [
        "**/backend/target/**",
        "**/src-tauri/target/**",
        "**/src-tauri/binaries/**",
        "**/src-tauri/resources/**",
        "**/artifacts/**",
      ],
    },
  },
  build: { outDir: "../dioptas/desktop/ui", emptyOutDir: true },
});

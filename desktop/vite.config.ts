import { execFileSync } from "node:child_process";
import { cpSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";
import { reactHookRefresh } from "./scripts/react_hook_refresh.mjs";

const { version } = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf8"),
);

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
    "import.meta.env.VITE_DIOPTAS_VERSION": JSON.stringify(version),
    "import.meta.env.VITE_DIOPTAS_BUILD": JSON.stringify(
      `${version} ${revision} built ${new Date().toISOString()}`,
    ),
  },
  plugins: [
    reactHookRefresh(),
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
        "**/security/glib-regression/target/**",
        "**/src-tauri/binaries/**",
        "**/src-tauri/resources/**",
        "**/artifacts/**",
      ],
    },
  },
  build: { outDir: "../dioptas/desktop/ui", emptyOutDir: true },
});

import { cpSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
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
  build: { outDir: "../dioptas/desktop/ui", emptyOutDir: true },
});

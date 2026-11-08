// Build only a historical frontend. Use this checkout's isolated Python models
// and dependencies; never reset a checkout or start a visible preview.
import { execFileSync } from "node:child_process";
import { mkdir, symlink, lstat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const requested =
  process.argv.find((arg) => arg.startsWith("--ref="))?.slice(6) ?? "b418d66b";
const ref = execFileSync(
  "git",
  ["rev-parse", "--verify", "--end-of-options", `${requested}^{commit}`],
  { cwd: root, encoding: "utf8" },
).trim();
const output = path.join(root, "desktop/artifacts/ui-audit/baseline-frontend");
await mkdir(output, { recursive: true });
const archive = execFileSync(
  "git",
  [
    "archive",
    ref,
    "desktop/src",
    "desktop/index.html",
    "desktop/vite.config.ts",
    "desktop/licenses",
  ],
  { cwd: root, maxBuffer: 32 * 1024 * 1024 },
);
execFileSync("tar", ["-xf", "-", "-C", output], { input: archive });
const dependencies = path.join(output, "desktop/node_modules");
try {
  await lstat(dependencies);
} catch (error) {
  if (error.code !== "ENOENT") throw error;
  await symlink(path.join(root, "desktop/node_modules"), dependencies, "dir");
}
execFileSync(
  path.join(root, "desktop/node_modules/.bin/vite"),
  [
    "build",
    path.join(output, "desktop"),
    "--config",
    path.join(output, "desktop/vite.config.ts"),
    "--outDir",
    path.join(output, "ui"),
  ],
  { cwd: root, stdio: "inherit" },
);
execFileSync(
  process.execPath,
  [
    path.join(root, "desktop/scripts/ui_audit.mjs"),
    "--stage=before",
    `--baseline-ref=${ref}`,
    `--ui=${path.join(output, "ui/index.html")}`,
  ],
  { cwd: root, stdio: "inherit" },
);

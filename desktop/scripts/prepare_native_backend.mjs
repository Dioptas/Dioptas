// Build the processor in Tauri's target/profile and stage its external binary.
// This hook uses Rust/C tooling only; Python is a test/reference dependency.
import { spawn, execFileSync } from "node:child_process";
import { chmod, copyFile, mkdir, rename, rm } from "node:fs/promises";
import { createInterface } from "node:readline";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { prepareStandaloneResources } from "./prepare_standalone_resources.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const args = process.argv.slice(2);
if (
  args.length > 1 ||
  args.some((a) => !["--debug", "--release", "--tauri"].includes(a))
) {
  throw Error("Use backend:prepare with --debug, --release or --tauri.");
}
const release =
  args.includes("--release") ||
  (args.includes("--tauri") && process.env.TAURI_ENV_DEBUG !== "true");
const host = execFileSync("rustc", ["-vV"], { encoding: "utf8" }).match(
  /^host: (.+)$/m,
)?.[1];
if (!host) throw Error("Cannot determine the Rust host target.");
const target = process.env.TAURI_ENV_TARGET_TRIPLE || host;
if (target === "universal-apple-darwin") {
  throw Error(
    "Build each macOS architecture separately; universal packaging is not qualified yet.",
  );
}
const command = process.env.CARGO || "cargo";
const buildArgs = [
  "build",
  "--locked",
  "--manifest-path",
  "backend/Cargo.toml",
  "--bin",
  "dioptas-processor",
  "--message-format=json-render-diagnostics",
  ...(release ? ["--release"] : []),
  ...(target !== host ? ["--target", target] : []),
];
console.log(
  `Building Dioptas Rust processor (${target}, ${release ? "release" : "debug"}).`,
);
const child = spawn(command, buildArgs, {
  cwd: desktop,
  stdio: ["ignore", "pipe", "inherit"],
  env: {
    ...process.env,
    ...(target.includes("apple-darwin")
      ? { MACOSX_DEPLOYMENT_TARGET: "14.0" }
      : {}),
  },
});
let executable;
const lines = createInterface({ input: child.stdout });
lines.on("line", (line) => {
  let message;
  try {
    message = JSON.parse(line);
  } catch {
    console.log(line);
    return;
  }
  if (
    message.reason === "compiler-artifact" &&
    message.target?.name === "dioptas-processor" &&
    message.executable &&
    message.features?.includes("dioptrin")
  ) {
    executable = message.executable;
  }
});
await new Promise((resolve, reject) => {
  child.on("error", reject);
  child.on("close", (code) =>
    code === 0
      ? resolve()
      : reject(Error(`Processor build exited with ${code}.`)),
  );
});
if (!executable)
  throw Error("Build did not produce a Dioptrin-enabled processor.");
const directory = path.join(desktop, "src-tauri/binaries");
await mkdir(directory, { recursive: true });
const destination = path.join(
  directory,
  `dioptas-processor-${target}${target.includes("windows") ? ".exe" : ""}`,
);
const temporary = `${destination}.${process.pid}.tmp`;
try {
  await copyFile(executable, temporary);
  await chmod(temporary, 0o755);
  await rename(temporary, destination);
} finally {
  await rm(temporary, { force: true });
}
console.log(`Staged ${path.relative(desktop, destination)}.`);
await prepareStandaloneResources(target);

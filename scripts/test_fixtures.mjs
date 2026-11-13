// Generate native test input; no application or independent reference code is involved.
import { execFileSync } from "node:child_process";
import path from "node:path";
import { root } from "./native_backend_client.mjs";
// Runs one of the backend's example programs. CI's UI jobs set
// DIOPTAS_GATE_PREBUILT=1 and run the binary another job built; otherwise
// cargo builds it first.
export function runExample(name, ...args) {
  if (process.env.DIOPTAS_GATE_PREBUILT === "1")
    return execFileSync(
      path.join(
        root,
        "target/debug/examples",
        process.platform === "win32" ? `${name}.exe` : name,
      ),
      args,
      { cwd: root, stdio: "inherit" },
    );
  return execFileSync(
    "cargo",
    [
      "run",
      "--quiet",
      "--locked",
      "--manifest-path",
      path.join(root, "backend/Cargo.toml"),
      "--example",
      name,
      "--",
      ...args,
    ],
    { cwd: root, stdio: "inherit" },
  );
}
export function testFixture(kind, file, ...args) {
  const binary =
    process.env.DIOPTAS_TEST_FIXTURES ??
    path.join(
      root,
      "target/debug/examples",
      process.platform === "win32" ? "test_fixtures.exe" : "test_fixtures",
    );
  execFileSync(binary, [kind, file, ...args.map(String)], { stdio: "pipe" });
}

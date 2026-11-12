// Generate native test input; no application or independent reference code is involved.
import { execFileSync } from "node:child_process";
import path from "node:path";
import { root } from "./native_backend_client.mjs";
export function testFixture(kind, file, ...args) {
  const binary =
    process.env.DIOPTAS_TEST_FIXTURES ??
    path.join(
      root,
      "desktop/backend/target/debug/examples",
      process.platform === "win32" ? "test_fixtures.exe" : "test_fixtures",
    );
  execFileSync(binary, [kind, file, ...args.map(String)], { stdio: "pipe" });
}

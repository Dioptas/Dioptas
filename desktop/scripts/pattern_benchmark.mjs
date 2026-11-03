import { preparePatternBaseline } from "./pattern_benchmark_baseline.mjs";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const desktop = fileURLToPath(new URL("../", import.meta.url));
const backend = process.argv.includes("--original")
  ? "original"
  : process.argv.includes("--webgl")
    ? "webgl2"
    : "canvas2d";
const engine = process.argv.includes("--webkit") ? "webkit" : "chromium";
const tag =
  process.argv.find((a) => a.startsWith("--tag="))?.slice(6) ?? backend;
await mkdir(`${desktop}artifacts`, { recursive: true });
const cleanupBaseline =
  backend === "original" ? await preparePatternBaseline() : async () => {};
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0, hmr: false },
});
await server.listen();
const browser = await (engine === "webkit" ? webkit : chromium).launch({
  headless: !process.argv.includes("--headed"),
});
try {
  const page = await browser.newPage({
    viewport: { width: 1100, height: 700 },
    deviceScaleFactor: process.argv.includes("--retina") ? 2 : 1,
  });
  await page.exposeFunction("__patternBenchmarkProgress", (result) =>
    console.log(JSON.stringify(result)),
  );
  page.on("pageerror", (e) => console.log("PAGE ERROR", e.message));
  await page.goto(
    `${server.resolvedUrls.local[0]}scripts/pattern_benchmark.html`,
  );
  await page.waitForFunction(() => window.__patternBenchmark);
  const report = await page.evaluate(
    ({ backend, caseName }) =>
      window.__patternBenchmark.run({ backend, caseName }),
    {
      backend,
      caseName: process.argv.find((a) => a.startsWith("--case="))?.slice(7),
    },
  );
  await writeFile(
    `${desktop}artifacts/pattern-${engine}-${tag}.json`,
    JSON.stringify(report, null, 2),
  );
  console.log(`Saved pattern-${engine}-${tag}.json`);
} finally {
  await browser.close();
  await server.close();
  await cleanupBaseline();
}

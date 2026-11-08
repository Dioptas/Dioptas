// Headless click-to-React-paint benchmark. The test bridge hydrates each native
// buffer once into an ArrayBuffer, matching production buffer identity/reuse.
// OS IPC/compositor latency is deliberately outside this headless measurement.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  return index < 0 ? fallback : args[index + 1];
};
const baseline = option("--baseline", null);
const current = option(
  "--processor",
  path.join(root, "desktop/backend/target/debug/dioptas-processor"),
);
let oldUi = option("--old-ui", null);
if (args.includes("--compare-busy-ui")) {
  const { build } = await import("vite");
  const directory = path.join(
    root,
    "desktop/artifacts/image-navigation/busy-ui",
  );
  let replaced = false;
  await build({
    plugins: [
      {
        name: "benchmark-busy-navigation",
        enforce: "pre",
        transform(code, id) {
          if (id.endsWith("/src/App.tsx")) {
            const baseline = code.replace('command === "next_image" ||', "");
            replaced = baseline !== code;
            return baseline;
          }
        },
      },
    ],
    build: { outDir: directory, emptyOutDir: true },
  });
  assert.equal(
    replaced,
    true,
    "Could not generate the busy-navigation baseline",
  );
  oldUi = path.join(directory, "index.html");
}
const median = (values) =>
  [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
const reports = [];
for (const [browserName, browserType] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const browser = await browserType.launch({ headless: true });
  try {
    for (const [label, executable, html] of [
      ...(oldUi ? [["busy-ui", baseline ?? current, oldUi]] : []),
      ...(baseline ? [["quiet-ui", baseline, null]] : []),
      ["optimized", current, null],
    ]) {
      const native = nativeClient({ executable });
      const page = await browser.newPage({
        viewport: { width: 1100, height: 760 },
      });
      const sent = new Set();
      const errors = [];
      const calls = [];
      page.on("pageerror", (error) => errors.push(error.message));
      const call = async (action, payload = {}) => {
        const start = performance.now();
        const response = await native.invoke(action, payload);
        calls.push({ action, ms: performance.now() - start });
        assert.equal(response.ok, true, `${action}: ${response.error}`);
        return response;
      };
      try {
        await call("open_image", {
          path: path.join(root, "dioptas/tests/data/image_001.tif"),
        });
        await call("open_calibration", {
          path: path.join(root, "dioptas/tests/data/LaB6_40keV_MarCCD.poni"),
        });
        await page.exposeFunction("__nativeInvoke", async (action, payload) => {
          const response = await call(action, payload);
          const incoming = [];
          const visit = (value) => {
            if (!value || typeof value !== "object") return;
            if (value.bufferId && !sent.has(value.bufferId)) {
              sent.add(value.bufferId);
              incoming.push([
                value.bufferId,
                native.buffers.get(value.bufferId).toString("base64"),
              ]);
            }
            for (const item of Object.values(value)) visit(item);
          };
          visit(response);
          return { response, incoming };
        });
        await page.addInitScript(() => {
          const buffers = new Map();
          window.__pending = 0;
          window.__navigationCount = 0;
          const hydrate = (value) => {
            if (Array.isArray(value)) return value.map(hydrate);
            if (!value || typeof value !== "object") return value;
            if (value.bufferId)
              return { ...value, data: buffers.get(value.bufferId) };
            return Object.fromEntries(
              Object.entries(value).map(([key, item]) => [key, hydrate(item)]),
            );
          };
          window.pywebview = {
            api: {
              invoke: async (action, payload) => {
                const track = !["pixel", "progress"].includes(action);
                if (track) window.__pending++;
                try {
                  const { response, incoming } = await window.__nativeInvoke(
                    action,
                    payload,
                  );
                  for (const [id, encoded] of incoming) {
                    const text = atob(encoded);
                    const bytes = new Uint8Array(text.length);
                    for (let i = 0; i < text.length; i++)
                      bytes[i] = text.charCodeAt(i);
                    buffers.set(id, bytes.buffer);
                  }
                  const hydrated = hydrate(response);
                  if (action === "next_image") {
                    window.__navigationCount++;
                    window.__navigationHydratedAt = performance.now();
                  }
                  return hydrated;
                } finally {
                  if (track) window.__pending--;
                }
              },
            },
          };
        });
        await page.goto(
          pathToFileURL(
            html ?? path.join(root, "dioptas/desktop/ui/index.html"),
          ).href,
        );
        await page.getByTestId("detector-canvas").waitFor();
        await page.waitForFunction(
          () => window.__pending === 0 && !document.querySelector(".spin"),
        );
        await page
          .getByRole("button", { name: "Integration", exact: true })
          .click();
        const step = (direction) =>
          page.evaluate(async (direction) => {
            const count = window.__navigationCount;
            const start = performance.now();
            document
              .querySelector(
                `[aria-label="Integration ${direction > 0 ? "next" : "previous"} image"]`,
              )
              .click();
            await new Promise((resolve, reject) => {
              const check = () => {
                if (performance.now() - start > 15000)
                  return reject(Error("Navigation timed out"));
                if (window.__navigationCount > count && window.__pending === 0)
                  requestAnimationFrame(() => requestAnimationFrame(resolve));
                else requestAnimationFrame(check);
              };
              requestAnimationFrame(check);
            });
            const finish = performance.now();
            return {
              totalMs: finish - start,
              responseToPaintMs: finish - window.__navigationHydratedAt,
            };
          }, direction);
        await step(1);
        await step(-1);
        calls.length = 0;
        const times = [];
        for (let i = 0; i < 12; i++)
          times.push(await step(i % 2 === 0 ? 1 : -1));
        assert.deepEqual(errors, []);
        assert.equal(await page.getByRole("dialog").count(), 0);
        const record = {
          browser: browserName,
          label,
          medianClickToPaintMs: median(times.map((row) => row.totalMs)),
          medianResponseToPaintMs: median(
            times.map((row) => row.responseToPaintMs),
          ),
          times,
          medianNativeRoundtripMs: median(
            calls
              .filter((call) => call.action === "next_image")
              .map((call) => call.ms),
          ),
          commands: calls.reduce(
            (counts, call) => ({
              ...counts,
              [call.action]: (counts[call.action] ?? 0) + 1,
            }),
            {},
          ),
          renderer: await page
            .getByTestId("detector-canvas")
            .getAttribute("data-renderer"),
          shape: [2048, 2048],
        };
        reports.push(record);
        console.log(JSON.stringify(record));
      } finally {
        await page.close();
        await native.close();
      }
    }
  } finally {
    await browser.close();
  }
}
const output = path.join(root, "desktop/artifacts/image-navigation/ui.json");
await mkdir(path.dirname(output), { recursive: true });
await writeFile(
  output,
  JSON.stringify(
    {
      scope:
        "Headless local warm navigation; binary buffer identity retained, test bridge replaces Tauri IPC; two animation frames after React response; physical display latency unmeasured",
      reports,
    },
    null,
    2,
  ) + "\n",
);

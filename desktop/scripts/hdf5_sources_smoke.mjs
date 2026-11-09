import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import path from "node:path";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { setInterfaceTextSize } from "./plot_navigation.mjs";
const desktop = path.join(root, "desktop"),
  artifacts = path.join(desktop, "artifacts/hdf5-sources");
await mkdir(artifacts, { recursive: true });
const temporary = await mkdtemp(path.join(tmpdir(), "dioptas-hdf5-source-"));
const fixture = path.join(temporary, "sources.h5"),
  project = path.join(temporary, "sources.dio");
execFileSync(
  "cargo",
  [
    "run",
    "--quiet",
    "--locked",
    "--manifest-path",
    path.join(desktop, "backend/Cargo.toml"),
    "--example",
    "hdf5_source_fixture",
    "--",
    fixture,
  ],
  { cwd: desktop, stdio: "inherit" },
);
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const reports = [];
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient(),
      browser = await type.launch({ headless: true });
    const page = await browser.newPage({
        viewport: { width: 1440, height: 940 },
      }),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const call = async (action, payload = {}) => {
      const r = await native.invoke(action, payload);
      assert.equal(r.ok, true, `${action}: ${r.error}`);
      return r;
    };
    const button = (name) => page.getByRole("button", { name, exact: true });
    const selector = () =>
      page.getByRole("combobox", { name: "Image source", exact: true });
    async function ready() {
      await page.waitForFunction(
        () => !window.__sourcePending && !document.querySelector(".spin"),
      );
      await page.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
    }
    async function choose(dataset) {
      await selector().selectOption(dataset);
      await ready();
    }
    const report = { browser: name, headless: true, checks: [] };
    try {
      await call("open_image", { path: fixture, frame: 3 });
      await call("manual_geometry", {
        convention: "pyfai",
        values: {
          dist: 150,
          poni1: 1.2,
          poni2: 1.6,
          rot1: 0,
          rot2: 0,
          rot3: 0,
          wavelength: 0.4,
          pixel1: 100,
          pixel2: 100,
          polarization_factor: 0.99,
        },
      });
      await call("integration_settings", {
        bins: 24,
        cake_bins: 12,
        trim_zeros: false,
      });
      await page.exposeFunction(
        "__sourceInvoke",
        async (action, payload = {}) => {
          if (
            ["save_project", "open_project"].includes(action) &&
            !payload.path
          )
            payload = { ...payload, path: project };
          return native.browserResult(await native.invoke(action, payload));
        },
      );
      await page.addInitScript(() => {
        window.__sourcePending = 0;
        window.pywebview = {
          api: {
            invoke: async (action, payload) => {
              window.__sourcePending++;
              try {
                return await window.__sourceInvoke(action, payload);
              } finally {
                window.__sourcePending--;
              }
            },
          },
        };
      });
      await page.goto(server.resolvedUrls.local[0]);
      await selector().waitFor();
      await ready();
      assert.equal(await selector().inputValue(), "/a");
      await choose("/b");
      let state = (await call("state")).state;
      assert.equal(state.selectedImageSource, "/b");
      assert.equal(state.integration.frames, 2);
      assert.equal(state.integration.frame, 2);
      await button("Integration").click();
      await ready();
      await page.getByRole("tab", { name: "Image", exact: true }).click();
      await selector().waitFor();
      const frame = page.getByRole("spinbutton", {
        name: "Frame position (1–2)",
        exact: true,
      });
      assert.equal(await frame.inputValue(), "2");
      await frame.fill("1");
      await frame.press("Enter");
      await ready();
      assert.equal((await call("state")).state.integration.frame, 1);
      await choose("/a");
      assert.equal((await call("state")).state.integration.frames, 4);
      report.checks.push(
        "Calibration and Integration dropdown; clamped frame, count and one-based frame navigation",
      );
      for (const large of [false, true]) {
        await page.setViewportSize({ width: 1000, height: 668 });
        await setInterfaceTextSize(page, large);
        await selector().scrollIntoViewIfNeeded();
        const box = await selector().boundingBox();
        assert.ok(
          box &&
            box.x >= 0 &&
            box.x + box.width <= 1000 &&
            box.y >= 0 &&
            box.y + box.height <= 668,
        );
        await page.screenshot({
          path: path.join(
            artifacts,
            `${name}-${large ? "large" : "normal"}.png`,
          ),
        });
      }
      report.checks.push("1000×668 layout at both text sizes");
      await page.setViewportSize({ width: 1440, height: 940 });
      await setInterfaceTextSize(page, false);
      const before = await call("state");
      for (const escape of [false, true]) {
        await selector().focus();
        await selector().selectOption("/c");
        const dialog = page.getByRole("dialog", {
          name: "Image dimensions changed",
        });
        await dialog.waitFor();
        assert.deepEqual((await call("state")).state, before.state);
        if (escape) await page.keyboard.press("Escape");
        else await button("Cancel").click();
        await dialog.waitFor({ state: "detached" });
        await ready();
        assert.equal(await selector().inputValue(), "/a");
        assert.deepEqual((await call("state")).state, before.state);
        await page.waitForFunction(
          () =>
            document.activeElement?.getAttribute("aria-label") ===
            "Image source",
        );
      }
      report.checks.push(
        "size prompt before mutation; Cancel/Escape preserve source, geometry, pixels and focus",
      );
      await choose("/bad");
      const error = page.getByRole("dialog", {
        name: "Couldn’t load image source",
      });
      await error.waitFor();
      await error.getByRole("button", { name: "OK", exact: true }).click();
      await ready();
      assert.equal(await selector().inputValue(), "/a");
      assert.deepEqual((await call("state")).state, before.state);
      report.checks.push(
        "U64 precision failure uses existing error dialog and preserves source",
      );
      await choose("/b");
      await button("Save project").click();
      await ready();
      await choose("/a");
      await button("Open project").click();
      const drafts = page.getByRole("dialog", {
        name: "Replace unapplied edits?",
      });
      if (await drafts.count())
        await drafts
          .getByRole("button", { name: "Open project", exact: true })
          .click();
      await ready();
      assert.equal(await selector().inputValue(), "/b");
      report.checks.push(
        "GUI project save/reopen retains source selection and catalog",
      );
      await selector().selectOption("/c");
      await button("Open and reset calibration").click();
      await ready();
      state = (await call("state")).state;
      assert.equal(state.selectedImageSource, "/c");
      assert.deepEqual(state.shape, [16, 20]);
      assert.equal(state.calibrated, false);
      assert.equal(
        await button("Integration").getAttribute("aria-pressed"),
        "true",
      );
      assert.equal(
        await page
          .getByRole("tab", { name: "Image", exact: true })
          .getAttribute("aria-selected"),
        "true",
      );
      assert.equal(await selector().inputValue(), "/c");
      report.checks.push(
        "accepted size reset preserves Integration Image and the correct source",
      );
      assert.deepEqual(errors, []);
      reports.push(report);
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "report.json"),
    JSON.stringify(reports, null, 2) + "\n",
  );
  console.log(JSON.stringify(reports, null, 2));
} finally {
  await server.close();
  await rm(temporary, { recursive: true, force: true });
}

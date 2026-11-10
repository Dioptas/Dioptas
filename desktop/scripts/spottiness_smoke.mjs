import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-spottiness-ui-"));
const artifacts = path.join(root, "desktop/artifacts/spottiness");
await mkdir(artifacts, { recursive: true });
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient(),
      browser = await type.launch({ headless: true });
    try {
      let exportMode = "cancel";
      const errors = [];
      const invoke = async (a, p = {}) => {
        const r = await native.invoke(a, p);
        assert.equal(r.ok, true, `${a}: ${r.error}`);
        return r;
      };
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      });
      await invoke("integration_settings", {
        bins: 128,
        cake_bins: 12,
        poisson_errors: true,
      });
      await invoke("open_image", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
      });
      await invoke("integration_phase", {
        operation: "load",
        path: path.join(root, "dioptas/tests/data/jcpds/mo.jcpds"),
      });
      const page = await browser.newPage({
        viewport: { width: 1000, height: 668 },
      });
      page.setDefaultTimeout(20000);
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (a, p) => {
        if (a === "integration_save_spottiness") {
          if (exportMode === "cancel") return { ok: true, cancelled: true };
          return native.browserResult(
            await native.invoke(a, {
              ...p,
              path: path.join(
                temp,
                exportMode === "error" ? "missing/spread.csv" : `${name}.csv`,
              ),
            }),
          );
        }
        return native.browserResult(await invoke(a, p));
      });
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
        };
      });
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await page.getByRole("tab", { name: "Pattern", exact: true }).click();
      const show = page.getByRole("checkbox", {
        name: "Show Spottiness",
        exact: true,
      });
      const relative = page.getByRole("checkbox", {
        name: "Relative spread (std / mean)",
        exact: true,
      });
      const save = page.getByRole("button", {
        name: "Save Spottiness…",
        exact: true,
      });
      assert.equal(await relative.isEnabled(), false);
      assert.equal(await save.isEnabled(), false);
      await show.click();
      await page
        .getByRole("region", { name: "Spottiness diagnostic", exact: true })
        .waitFor();
      await relative.click();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Relative spread (std / mean)"]')
            ?.checked,
      );
      const main = page.locator(
        '.spottiness-main canvas[data-testid="pattern-canvas"]',
      );
      const diag = page.locator(
        '.spottiness-diagnostic canvas[data-testid="pattern-canvas"]',
      );
      const bounds = async (c) =>
        c.evaluate((e) =>
          Object.fromEntries(
            ["x-min", "x-max", "y-min", "y-max"].map((k) => [
              k,
              Number(e.getAttribute("data-view-" + k)),
            ]),
          ),
        );
      async function aligned() {
        await page.waitForFunction(() => {
          const a = document.querySelector(
              '.spottiness-main canvas[data-testid="pattern-canvas"]',
            ),
            b = document.querySelector(
              '.spottiness-diagnostic canvas[data-testid="pattern-canvas"]',
            );
          return (
            a &&
            b &&
            ["min", "max"].every(
              (k) =>
                a.getAttribute("data-view-x-" + k) ===
                b.getAttribute("data-view-x-" + k),
            )
          );
        });
      }
      await aligned();
      async function drag(c) {
        const b = await c.boundingBox();
        await page.mouse.move(b.x + b.width * 0.35, b.y + b.height * 0.35);
        await page.mouse.down();
        await page.mouse.move(b.x + b.width * 0.75, b.y + b.height * 0.7, {
          steps: 8,
        });
        await page.mouse.up();
      }
      assert(Number(await diag.getAttribute("data-reference-count")) > 0);
      assert.equal(
        await diag.getAttribute("data-reference-count"),
        await main.getAttribute("data-reference-count"),
      );
      const full = await bounds(main);
      await drag(main);
      await aligned();
      const zoom = await bounds(main);
      assert(zoom["x-max"] - zoom["x-min"] < full["x-max"] - full["x-min"]);
      await drag(diag);
      await aligned();
      const zoom2 = await bounds(main);
      assert(zoom2["x-max"] - zoom2["x-min"] < zoom["x-max"] - zoom["x-min"]);
      const diagBox = await diag.boundingBox();
      await page.mouse.move(
        diagBox.x + diagBox.width * 0.55,
        diagBox.y + diagBox.height * 0.4,
      );
      await page.waitForTimeout(180);
      assert.match(await page.locator(".app-status").innerText(), /std\/mean/);
      assert.equal(
        await page
          .getByRole("button", { name: "Pattern auto range", exact: true })
          .getAttribute("aria-pressed"),
        "false",
      );
      await diag.focus();
      await page.keyboard.press("f");
      await aligned();
      assert.equal(
        await page
          .getByRole("button", { name: "Pattern auto range", exact: true })
          .getAttribute("aria-pressed"),
        "true",
      );
      const reset = await bounds(main);
      assert.equal(reset["x-min"], full["x-min"]);
      assert.equal(reset["x-max"], full["x-max"]);
      await save.click();
      await page.waitForFunction(
        () =>
          !Array.from(document.querySelectorAll("button")).find(
            (b) => b.textContent === "Save Spottiness…",
          )?.disabled,
      );
      exportMode = "save";
      await save.click();
      await page.waitForTimeout(250);
      assert.match(
        await readFile(path.join(temp, `${name}.csv`), "utf8"),
        /integrated_mean,azimuthal_std,relative_spread/,
      );
      exportMode = "error";
      await save.click();
      await page.getByRole("dialog").waitFor();
      await page
        .getByRole("dialog")
        .getByRole("button", { name: /Close|OK|Dismiss/ })
        .click();
      await page
        .getByRole("button", { name: "Dismiss error", exact: true })
        .click();
      for (const label of ["Q", "d", "2θ"]) {
        await page
          .getByRole("button", { name: `Pattern unit ${label}`, exact: true })
          .click();
        await page.waitForFunction(
          (label) =>
            document
              .querySelector(`[aria-label="Pattern unit ${label}"]`)
              ?.getAttribute("aria-pressed") === "true",
          label,
        );
        await aligned();
      }
      await diag.click({ position: { x: 150, y: 40 } });
      await page.waitForFunction(() => {
        const a = document.querySelector(
            '.spottiness-main canvas[data-testid="pattern-canvas"]',
          ),
          b = document.querySelector(
            '.spottiness-diagnostic canvas[data-testid="pattern-canvas"]',
          );
        return (
          a?.getAttribute("data-linked-position") &&
          a.getAttribute("data-linked-position") ===
            b?.getAttribute("data-linked-position")
        );
      });
      for (const larger of [false, true]) {
        if (larger) {
          await page
            .getByRole("button", { name: "Settings", exact: true })
            .click();
          await page
            .getByRole("button", { name: "Larger", exact: true })
            .click();
          await page.keyboard.press("Escape");
        }
        await save.scrollIntoViewIfNeeded();
        const box = await save.boundingBox();
        assert(box.x >= 0 && box.x + box.width <= 1001);
        assert(box.y + box.height <= 668);
        await aligned();
        const b = await diag.boundingBox();
        assert(b.height >= 100 && b.width > 200);
        await page.screenshot({
          path: path.join(
            artifacts,
            `${name}-${larger ? "larger" : "standard"}.png`,
          ),
        });
      }
      await show.click();
      await page
        .getByRole("region", { name: "Spottiness diagnostic", exact: true })
        .waitFor({ state: "detached" });
      assert.equal(await relative.isEnabled(), false);
      assert.equal(await save.isEnabled(), false);
      // A combined curve cannot inherit one detector's population statistic.
      await invoke("integration_settings", { azimuthal_std: true });
      await invoke("configuration", { operation: "duplicate" });
      await invoke("combination_settings", { patterns: true });
      await page.reload();
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await page.getByRole("tab", { name: "Pattern", exact: true }).click();
      await page
        .getByText("Azimuthal std is unavailable for combined patterns.", {
          exact: false,
        })
        .waitFor();
      assert.equal(await save.isEnabled(), false);
      assert.equal(
        await page
          .getByRole("region", { name: "Spottiness diagnostic", exact: true })
          .count(),
        0,
      );
      assert.deepEqual(errors, []);
      console.log(
        `${name}: linked zoom/reset, relative footer, CSV/cancel/error, compact Standard/Larger passed`,
      );
    } finally {
      await browser.close();
      await native.close();
    }
  }
} finally {
  await rm(temp, { recursive: true, force: true });
}

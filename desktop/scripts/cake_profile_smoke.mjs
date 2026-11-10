import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-cake-profile-"));
const artifacts = path.join(root, "desktop/artifacts/cake-profile");
await mkdir(artifacts, { recursive: true });
const receipt = [];
try {
  const poni = path.join(temp, "g.poni");
  await writeFile(
    poni,
    "PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.1\nPoni1: 0.003\nPoni2: 0.004\nRot1: 0\nRot2: 0\nRot3: 0\nSplineFile: None\nWavelength: 4e-11\n",
  );
  for (const [engine, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await type.launch({ headless: true });
    try {
      const calls = [],
        errors = [];
      let pending = 0,
        cancelSave = false;
      const profiles = [];
      const invoke = async (action, payload = {}) => {
        pending++;
        try {
          calls.push([action, structuredClone(payload)]);
          if (action === "save_cake_profile") {
            if (cancelSave) return { ok: true, cancelled: true };
            payload = { ...payload, path: path.join(temp, `${engine}.xy`) };
          }
          const reply = await native.invoke(action, payload);
          assert.equal(reply.ok, true, `${action}: ${reply.error}`);
          if (reply.cakeProfile) profiles.push(reply.cakeProfile);
          return reply;
        } finally {
          pending--;
        }
      };
      const hidden = { requested_products: { cake: false, rings: false } };
      await invoke("integration_settings", {
        bins: 48,
        cake_bins: 36,
        trim_zeros: false,
        ...hidden,
      });
      await invoke("open_calibration", { path: poni, ...hidden });
      await invoke("open_image", {
        path: path.join(
          root,
          "desktop/backend/tests/fixtures/combined-counts.h5",
        ),
        dataset: "/counts",
        ...hidden,
      });
      const page = await browser.newPage({
        viewport: { width: 1440, height: 900 },
      });
      page.setDefaultTimeout(25000);
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (a, p) =>
        native.browserResult(await invoke(a, p)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
        };
      });
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
      const button = (name) => page.getByRole("button", { name, exact: true });
      const idle = async () => {
        await page.waitForFunction(() => !document.querySelector(".spin"));
        await page.waitForTimeout(100);
        while (pending) await page.waitForTimeout(30);
      };
      await button("Integration").click();
      await idle();
      assert.equal(
        calls.some(([a]) => a === "cake_profile"),
        false,
      );
      await button("Azimuthal profile").click();
      await idle();
      const panel = page.getByRole("region", {
        name: "Azimuthal profile",
        exact: true,
      });
      assert.ok(await panel.isVisible());
      assert.ok(
        await panel
          .getByText("Click a calibrated detector, cake or pattern position.")
          .isVisible(),
      );
      const radialPlot = page
        .locator(".pattern-panel")
        .getByTestId("pattern-canvas");
      const dimensions = (canvas) =>
        canvas.evaluate((el) => ({
          left: +el.dataset.plotLeft,
          top: +el.dataset.plotTop,
          width: +el.dataset.plotWidth,
          height: +el.dataset.plotHeight,
        }));
      const clickPlot = async (canvas, x = 0.55, y = 0.55) => {
        const d = await dimensions(canvas);
        await canvas.click({
          position: { x: d.left + d.width * x, y: d.top + d.height * y },
        });
        await idle();
      };
      // Detector and radial-plot clicks select the same native physical position.
      await clickPlot(page.getByTestId("detector-canvas"));
      await panel.getByTestId("pattern-canvas").waitFor();
      await clickPlot(radialPlot);
      const profilePlot = panel.getByTestId("pattern-canvas");
      await profilePlot.waitFor();
      await idle();
      assert.ok(profiles.length > 0);
      assert.equal(profiles.at(-1).unit, "azimuth_deg");
      assert.equal(profiles.at(-1).x.length, 36);
      const field = page.getByLabel("Integral width", { exact: true });
      await field.fill("3");
      await field.press("Enter");
      await idle();
      assert.equal(profiles.at(-1).bins, 3);
      const savesBeforeInvalid = calls.filter(
        ([a]) => a === "save_cake_profile",
      ).length;
      await field.fill("0");
      await button("Save azimuthal profile").click();
      assert.equal(
        calls.filter(([a]) => a === "save_cake_profile").length,
        savesBeforeInvalid,
      );
      assert.equal(
        await field.evaluate((input) => input.validity.valid),
        false,
      );
      await field.fill("3");
      await field.press("Enter");
      await idle();
      const fullView = await profilePlot.getAttribute("data-view-x-max");
      // The profile uses shared navigation and keeps zoom when the radial selection changes.
      await profilePlot.focus();
      await profilePlot.press("+");
      await idle();
      const zoomView = await profilePlot.getAttribute("data-view-x-max");
      assert.ok(+zoomView < +fullView);
      await clickPlot(radialPlot, 0.65);
      await profilePlot.waitFor();
      await idle();
      assert.equal(await profilePlot.getAttribute("data-view-x-max"), zoomView);
      await profilePlot.press("f");
      await idle();
      await clickPlot(profilePlot, 0.55);
      assert.ok(
        calls.filter(([a]) => a === "validation_position").at(-1)[1].azimuth !=
          null,
      );
      await profilePlot.hover();
      await page.waitForTimeout(150);
      const footer = await page.locator(".app-status").innerText();
      assert.match(footer, /χ/);
      assert.match(footer, /Q/);
      assert.match(footer, /2θ/);
      await button("Cake").click();
      await idle();
      await clickPlot(page.getByTestId("cake-canvas"));
      await page.getByLabel("Cake azimuth shift", { exact: true }).fill("90");
      await idle();
      assert.equal(profiles.at(-1).shiftBins, 9);
      await button("Save azimuthal profile").click();
      await idle();
      const text = await readFile(path.join(temp, `${engine}.xy`), "utf8");
      assert.match(text, /# azimuth_deg intensity_au/);
      assert.equal(
        text.split("\n").filter((l) => l && !l.startsWith("#")).length,
        36,
      );
      cancelSave = true;
      await button("Save azimuthal profile").click();
      await idle();
      assert.equal(
        await readFile(path.join(temp, `${engine}.xy`), "utf8"),
        text,
      );
      await profilePlot.waitFor();
      for (const [size, larger] of [
        [{ width: 1440, height: 900 }, false],
        [{ width: 1000, height: 668 }, false],
        [{ width: 1000, height: 668 }, true],
      ]) {
        await page.setViewportSize(size);
        if (larger) {
          await button("Settings").click();
          await page.getByRole("tab", { name: "General", exact: true }).click();
          await page
            .getByRole("button", { name: "Larger", exact: true })
            .click();
          await button("Close settings").click();
        }
        await idle();
        await profilePlot.waitFor();
        const layout = await panel.evaluate((el) => {
          const r = el.getBoundingClientRect(),
            p = el.parentElement.getBoundingClientRect();
          const controls = [...el.querySelectorAll("input,button")]
            .filter((e) => e.offsetParent)
            .map((e) => ({
              name: e.ariaLabel,
              r: e.getBoundingClientRect().toJSON(),
            }));
          return {
            r: r.toJSON(),
            p: p.toJSON(),
            scroll: el.scrollWidth,
            width: el.clientWidth,
            controls,
          };
        });
        assert.ok(layout.scroll <= layout.width + 1, JSON.stringify(layout));
        assert.ok(layout.r.bottom <= layout.p.bottom + 1);
        assert.ok(layout.r.height >= 140);
        const tools = await page
          .getByRole("group", {
            name: "Integration image controls",
            exact: true,
          })
          .boundingBox();
        assert.ok(
          tools.y + tools.height <= layout.p.bottom + 1,
          JSON.stringify({ tools, layout }),
        );
        for (const c of layout.controls)
          assert.ok(
            c.r.right <= layout.r.right + 1 &&
              c.r.bottom <= layout.r.bottom + 1,
            JSON.stringify(c),
          );
        await page.screenshot({
          path: path.join(
            artifacts,
            `${engine}-${size.width}-${larger ? "larger" : "standard"}.png`,
          ),
        });
      }
      // Closing the profile and returning to Image restores ordinary lazy cake demand.
      await button("Azimuthal profile").click();
      await button("Image").click();
      await idle();
      const count = profiles.length;
      await button("Pattern unit Q").click();
      await idle();
      assert.equal(profiles.length, count);
      const lastSettings = calls
        .filter(([a]) => a === "integration_settings")
        .at(-1);
      assert.equal(lastSettings[1].requested_products.cake, false);
      await button("Settings").click();
      await page
        .getByRole("tab", { name: "Configurations", exact: true })
        .click();
      await page
        .getByRole("checkbox", { name: "Enable configurations", exact: true })
        .check();
      await button("Close settings").click();
      await idle();
      await page
        .getByRole("group", { name: "Project configurations" })
        .getByRole("button", { name: "Duplicate", exact: true })
        .click();
      await idle();
      await button("Combined cake").click();
      await idle();
      await button("Azimuthal profile").click();
      await idle();
      await clickPlot(radialPlot);
      await profilePlot.waitFor();
      await idle();
      assert.equal(profiles.at(-1).radialUnit, "q_A^-1");
      const selected = (await invoke("state")).state.configurationIndex;
      await page
        .getByLabel("Active configuration", { exact: true })
        .selectOption("0");
      await idle();
      await clickPlot(radialPlot);
      await profilePlot.waitFor();
      await idle();
      assert.equal((await invoke("state")).state.configurationIndex, 0);
      assert.notEqual(selected, 0);
      assert.deepEqual(errors, []);
      receipt.push({
        engine,
        profiles: profiles.length,
        layouts: 3,
        exportRows: 36,
        cancelledSavePreserved: true,
        lazyDemandRestored: true,
        combinedQProfileAndConfigurationSelection: true,
        errors,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "receipt.json"),
    JSON.stringify(receipt, null, 2),
  );
  console.log(JSON.stringify(receipt, null, 2));
} finally {
  await rm(temp, { recursive: true, force: true });
}

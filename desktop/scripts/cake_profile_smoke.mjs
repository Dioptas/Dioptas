import {
  checkCakeProfileInteraction,
  checkCakeProfileWidthResize,
} from "./cake_profile_interaction.mjs";
import { shiftCakeProfile } from "../src/shiftCakeProfile.ts";
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
      let holdNextProfile = false,
        releaseProfile;
      const invoke = async (action, payload = {}) => {
        pending++;
        try {
          calls.push([action, structuredClone(payload)]);
          if (action === "cake_profile" && holdNextProfile) {
            holdNextProfile = false;
            await new Promise((resolve) => {
              releaseProfile = resolve;
            });
          }
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
        // Observe the actual profile stroke without changing native samples.
        const context = CanvasRenderingContext2D.prototype;
        for (const name of ["beginPath", "moveTo", "lineTo", "stroke"]) {
          const original = context[name];
          context[name] = function (...args) {
            if (this.canvas.dataset.testid === "cake-profile-canvas") {
              if (name === "beginPath") this.profilePath = [];
              if (name === "moveTo" || name === "lineTo")
                this.profilePath?.push([name, ...args]);
              if (
                name === "stroke" &&
                this.strokeStyle === "#ffffff" &&
                this.lineWidth === 1.5
              )
                window.__profileCurve = this.profilePath;
            }
            return original.apply(this, args);
          };
        }
        for (const name of ["clearRect", "fillRect"]) {
          const original = context[name];
          context[name] = function (...args) {
            if (this.canvas.dataset.testid === "cake-canvas") {
              if (name === "clearRect") window.__profileBand = null;
              else if (this.fillStyle === "#ff9500")
                window.__profileBand = args;
            }
            return original.apply(this, args);
          };
        }
      });
      await page.goto(
        pathToFileURL(path.join(root, "desktop/dist/index.html")).href,
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
      assert.equal(await button("Azimuthal profile").count(), 0);
      await button("Cake").click();
      await idle();
      await button("Azimuthal profile").click();
      await idle();
      const panel = page.getByRole("region", {
        name: "Azimuthal profile",
        exact: true,
      });
      assert.ok(await panel.isVisible());
      assert.equal(
        await panel.locator("canvas").getAttribute("aria-description"),
        "Click a ring.",
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
      // Joint Q-axis/profile regression: labels must never redefine the f64
      // grid used by extraction or move either plot's retained viewport.
      const assertUnitTransitions = async (sourceUnit) => {
        const cakeCanvas = page.getByTestId("cake-canvas");
        if (!(await cakeCanvas.isVisible())) await button("Cake").click();
        await idle();
        const original = structuredClone(profiles.at(-1));
        const source = (await invoke("state")).cake;
        assert.equal(source.unit, sourceUnit);
        const cakeView = () =>
          cakeCanvas.evaluate((el) => [
            el.dataset.viewXMin,
            el.dataset.viewXMax,
            el.dataset.viewYMin,
            el.dataset.viewYMax,
          ]);
        await cakeCanvas.focus();
        await cakeCanvas.press("+");
        await profilePlot.focus();
        await profilePlot.press("+");
        await idle();
        const retainedCake = await cakeView();
        const retainedProfile =
          await profilePlot.getAttribute("data-view-x-max");
        for (const label of ["2θ", "Q", "d", "2θ", "Q"]) {
          const previousProfiles = profiles.length;
          const currentUnit = (await invoke("state")).state.unit;
          await button(`Pattern unit ${label}`).click();
          await idle();
          if (currentUnit !== { "2θ": "2th_deg", Q: "q_A^-1", d: "d_A" }[label])
            assert.ok(profiles.length > previousProfiles);
          assert.deepEqual(profiles.at(-1), original);
          await assertProfileWindow();
          assert.equal((await invoke("state")).cake.bufferId, source.bufferId);
          assert.equal(
            await cakeCanvas.getAttribute("data-radial-source-unit"),
            sourceUnit,
          );
          assert.equal(
            await cakeCanvas.getAttribute("data-radial-display-unit"),
            label === "2θ" ? "2th_deg" : "q_A^-1",
          );
          assert.deepEqual(await cakeView(), retainedCake);
          assert.equal(
            await profilePlot.getAttribute("data-view-x-max"),
            retainedProfile,
          );
        }
        await page.screenshot({
          path: path.join(
            artifacts,
            `${engine}-joint-${sourceUnit === "2th_deg" ? "angular" : "q"}-source.png`,
          ),
        });
        await cakeCanvas.press("f");
        await profilePlot.press("f");
        await idle();
      };
      // The panel and its toolbar toggle belong exclusively to Cake mode.
      assert.ok(await page.getByTestId("cake-canvas").isVisible());
      await button("Image").click();
      await idle();
      assert.equal(await panel.isVisible(), false);
      assert.equal(await button("Azimuthal profile").count(), 0);
      const hiddenReads = profiles.length;
      await button("Pattern unit Q").click();
      await idle();
      assert.equal(
        calls.filter(([a]) => a === "integration_settings").at(-1)[1]
          .requested_products.cake,
        false,
      );
      await clickPlot(page.getByTestId("detector-canvas"));
      assert.equal(profiles.length, hiddenReads);
      await button("Cake").click();
      await idle();
      await clickPlot(radialPlot);
      const profilePlot = panel.getByTestId("cake-profile-canvas");
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
      const cakeCanvas = page.getByTestId("cake-canvas");
      const assertProfileWindow = async () => {
        const nativeRange = profiles.at(-1).radialWindow;
        const actual = await cakeCanvas.evaluate((el) => {
          const d = el.dataset;
          return {
            source: d.profileWindow?.split(",").map(Number),
            drawn: window.__profileBand,
            min: +d.viewXMin,
            max: +d.viewXMax,
            left: +d.plotLeft,
            top: +d.plotTop,
            width: +d.plotWidth,
            height: +d.plotHeight,
            columns: +d.fullWidth,
          };
        });
        assert.deepEqual(actual.source, nativeRange);
        const scale = actual.width / (actual.max - actual.min);
        const low = Math.max(0, nativeRange[0]);
        const high = Math.min(actual.columns, nativeRange[1]);
        const expected = [
          actual.left + (low - actual.min) * scale,
          actual.top,
          (high - low) * scale,
          actual.height,
        ];
        expected.forEach((v, i) =>
          assert.ok(Math.abs(actual.drawn[i] - v) < 1e-8),
        );
      };
      await assertProfileWindow();
      const widthToggle = button("Show profile bin width");
      assert.equal(await widthToggle.getAttribute("aria-pressed"), "true");
      const beforeToggle = {
        reads: profiles.length,
        saves: calls.filter(([a]) => a === "save_cake_profile").length,
      };
      await widthToggle.click();
      await idle();
      assert.equal(await cakeCanvas.getAttribute("data-profile-window"), null);
      assert.equal(await page.evaluate(() => window.__profileBand), null);
      await widthToggle.click();
      await idle();
      await assertProfileWindow();
      assert.equal(profiles.length, beforeToggle.reads);
      assert.equal(
        calls.filter(([a]) => a === "save_cake_profile").length,
        beforeToggle.saves,
      );
      await cakeCanvas.press("+");
      await idle();
      await assertProfileWindow();
      await cakeCanvas.press("f");
      await idle();
      let readsBeforeHold;
      await checkCakeProfileWidthResize(page, profilePlot, cakeCanvas, idle, {
        hold() {
          readsBeforeHold = calls.filter(([a]) => a === "cake_profile").length;
          holdNextProfile = true;
        },
        async started() {
          for (let i = 0; i < 50 && !releaseProfile; i++)
            await page.waitForTimeout(10);
          assert.ok(releaseProfile);
        },
        calls() {
          return (
            calls.filter(([a]) => a === "cake_profile").length - readsBeforeHold
          );
        },
        release() {
          releaseProfile();
          releaseProfile = undefined;
        },
      });
      await assertProfileWindow();
      const assertShared = async () => {
        const read = async (canvas) =>
          canvas.evaluate((el) => {
            const r = el.getBoundingClientRect(),
              d = el.dataset;
            return {
              x: r.x,
              width: r.width,
              top: r.y + +d.plotTop,
              bottom: r.y + +d.plotTop + +d.plotHeight,
              yMin: +d.viewYMin,
              yMax: +d.viewYMax,
            };
          });
        const a = await read(profilePlot),
          b = await read(cakeCanvas);
        assert.ok(a.x + a.width <= b.x + 1, JSON.stringify({ a, b }));
        assert.ok(
          Math.abs(a.top - b.top) < 1.1 && Math.abs(a.bottom - b.bottom) < 1.1,
          JSON.stringify({ a, b }),
        );
        assert.ok(
          Math.abs(a.yMin - b.yMin) < 1e-8 && Math.abs(a.yMax - b.yMax) < 1e-8,
          JSON.stringify({ a, b }),
        );
      };
      await assertShared();
      await cakeCanvas.press("+");
      await idle();
      await checkCakeProfileWidthResize(page, profilePlot, cakeCanvas, idle);
      await cakeCanvas.press("f");
      await idle();
      await assertProfileWindow();
      // Edge-clipping status must not squeeze or reposition the width/save controls.
      const resizeHandle = page.getByRole("separator", {
        name: "Profile and cake divider",
        exact: true,
      });
      await resizeHandle.focus();
      const narrowSteps = Math.ceil(
        (Number(await resizeHandle.getAttribute("aria-valuenow")) -
          Number(await resizeHandle.getAttribute("aria-valuemin"))) /
          8,
      );
      for (let i = 0; i < narrowSteps; i++)
        await resizeHandle.press("ArrowLeft");
      await idle();
      const toolbarGeometry = () =>
        panel.locator(".cake-profile-tools").evaluate((el) =>
          [
            el,
            el.querySelector("label"),
            el.querySelector("input"),
            ...el.querySelectorAll("button"),
          ].map((node) => {
            const r = node.getBoundingClientRect();
            return [r.x, r.y, r.width, r.height];
          }),
        );
      const fixedToolbar = await toolbarGeometry();
      const binsCount = Number(
        await cakeCanvas.getAttribute("data-full-width"),
      );
      for (const [position, clipped] of [
        [0.75 / binsCount, true],
        [0.55, false],
        [1 - 0.75 / binsCount, true],
        [0.55, false],
      ]) {
        await clickPlot(cakeCanvas, position, 0.5);
        await assertProfileWindow();
        assert.equal(profiles.at(-1).clipped, clipped);
        assert.deepEqual(
          await toolbarGeometry(),
          fixedToolbar,
          "Cake position must not move or resize the toolbar",
        );
        assert.equal(await panel.getByText("⋯", { exact: true }).count(), 0);
        if (clipped)
          assert.match(
            await button("Save azimuthal profile").getAttribute("title"),
            /cake edge/,
          );
      }
      await resizeHandle.press("Home");
      await idle();
      await clickPlot(cakeCanvas, 0.85, 0.5);
      for (const width of [1, 3, 9]) {
        await field.fill(String(width));
        await field.press("Enter");
        await idle();
        await profilePlot.press("f");
        await idle();
        const gapped = structuredClone(profiles.at(-1));
        await assertProfileWindow();
        assert.ok(
          gapped.y.includes(0),
          "The native fixture must contain empty rows",
        );
        const nonzero = gapped.y.filter(
          (v) => v != null && v !== 0 && Number.isFinite(v),
        );
        assert.ok(
          nonzero.length > 1,
          "The fixture must also contain populated rows",
        );
        const rendered = await profilePlot.evaluate((el) => ({
          path: window.__profileCurve,
          min: +el.dataset.viewXMin,
          max: +el.dataset.viewXMax,
          top: +el.dataset.plotTop,
          height: +el.dataset.plotHeight,
          yMin: +el.dataset.viewYMin,
          yMax: +el.dataset.viewYMax,
        }));
        const expectedRows = gapped.y.flatMap((value, row) => {
          if (value == null || value === 0 || !Number.isFinite(value))
            return [];
          const previous = gapped.y[row - 1];
          return [
            [
              previous == null || previous === 0 || !Number.isFinite(previous)
                ? "moveTo"
                : "lineTo",
              row,
            ],
          ];
        });
        assert.deepEqual(
          rendered.path.map(([op, , y]) => [
            op,
            Math.round(
              rendered.yMax -
                ((y - rendered.top) / rendered.height) *
                  (rendered.yMax - rendered.yMin) -
                0.5,
            ),
          ]),
          expectedRows,
          "Zero rows must create gaps, with no line joining across them",
        );
        const low = Math.min(...nonzero),
          high = Math.max(...nonzero);
        const pad = Math.max((high - low) * 0.05, Math.abs(low) * 1e-6, 1e-6);
        assert.ok(Math.abs(rendered.min - (low - pad)) < 1e-10);
        assert.ok(Math.abs(rendered.max - (high + pad)) < 1e-10);
        await button("Save azimuthal profile").click();
        await idle();
        const savedWithZeros = (
          await readFile(path.join(temp, `${engine}.xy`), "utf8")
        )
          .split("\n")
          .filter((line) => line && !line.startsWith("#"))
          .map((line) => Number(line.trim().split(/\s+/)[1]));
        assert.deepEqual(
          savedWithZeros,
          gapped.y,
          "Export retains all native values, including zeros",
        );
        await panel.locator("..").screenshot({
          path: path.join(artifacts, `${engine}-gaps-width-${width}.png`),
        });
      }
      await field.fill("3");
      await field.press("Enter");
      await idle();
      await clickPlot(cakeCanvas, 0.55, 0.5);
      for (const orientation of ["vertical", "horizontal"]) {
        await button("Cake histogram settings").click();
        await page
          .getByLabel("Cake histogram orientation", { exact: true })
          .selectOption(orientation);
        await button("Close cake display settings").click();
        await idle();
        await assertShared();
        await assertProfileWindow();
      }
      const scienceBeforeResize = await invoke("state");
      const extractedBeforeResize = structuredClone(profiles.at(-1));
      await checkCakeProfileInteraction(
        page,
        profilePlot,
        cakeCanvas,
        idle,
        profiles.at(-1).y,
      );
      const scienceAfterResize = await invoke("state");
      assert.equal(
        scienceAfterResize.cake.bufferId,
        scienceBeforeResize.cake.bufferId,
      );
      assert.deepEqual(scienceAfterResize.pattern, scienceBeforeResize.pattern);
      assert.deepEqual(profiles.at(-1), extractedBeforeResize);
      const widthBeforeToggle = (await profilePlot.boundingBox()).width;
      await button("Profile Y-range zoom").click();
      await idle();
      await panel.locator("..").screenshot({
        path: path.join(artifacts, `${engine}-vertical-slice.png`),
      });
      await button("Azimuthal profile").click();
      await idle();
      await button("Azimuthal profile").click();
      await idle();
      assert.ok(
        Math.abs((await profilePlot.boundingBox()).width - widthBeforeToggle) <
          1.1,
      );
      assert.equal(
        await profilePlot.getAttribute("data-zoom-mode"),
        "vertical",
      );
      await button("Profile rectangle zoom").click();
      await profilePlot.press("f");
      await idle();
      const originalY = +(await cakeCanvas.getAttribute("data-view-y-max"));
      const radialBeforeProfileZoom =
        await cakeCanvas.getAttribute("data-view-x-max");
      const fullView = await profilePlot.getAttribute("data-view-x-max");
      // The profile uses shared navigation and keeps zoom when the radial selection changes.
      await profilePlot.focus();
      await profilePlot.press("+");
      await idle();
      const zoomView = await profilePlot.getAttribute("data-view-x-max");
      assert.ok(+zoomView < +fullView);
      await assertShared();
      assert.ok(
        +(await cakeCanvas.getAttribute("data-view-y-max")) < originalY,
      );
      assert.equal(
        await cakeCanvas.getAttribute("data-view-x-max"),
        radialBeforeProfileZoom,
      );
      await cakeCanvas.press("+");
      await idle();
      await assertShared();
      await profilePlot.press("ArrowUp");
      await idle();
      await assertShared();
      await profilePlot.press("f");
      await idle();
      await assertShared();
      assert.equal(+(await cakeCanvas.getAttribute("data-view-y-max")), 36);
      await profilePlot.press("+");
      await idle();

      const retainedX = await profilePlot.getAttribute("data-view-x-max");
      await clickPlot(radialPlot, 0.65);
      await profilePlot.waitFor();
      await idle();
      assert.equal(
        await profilePlot.getAttribute("data-view-x-max"),
        retainedX,
      );
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
      await clickPlot(page.getByTestId("cake-canvas"));
      await idle();
      const sourceProfile = structuredClone(profiles.at(-1));
      const readsBeforeShift = calls.filter(
        ([a]) => a === "cake_profile",
      ).length;
      for (const shift of [-180, -95, -5, 0, 5, 95, 180, 90]) {
        await page
          .getByLabel("Cake azimuth shift", { exact: true })
          .fill(String(shift));
        await idle();
        // Compare the display wrap to the independent native extraction/export path.
        const reference = await native.invoke("cake_profile", {
          two_theta: sourceProfile.twoTheta,
          bins: sourceProfile.bins,
          shift,
        });
        assert.equal(reference.ok, true, reference.error);
        const expected = reference.cakeProfile;
        const displayed = shiftCakeProfile(sourceProfile, shift);
        assert.deepEqual(displayed.y, expected.y);
        assert.equal(displayed.shiftBins, expected.shiftBins);
        displayed.x.forEach((x, i) =>
          assert.ok(Math.abs(x - expected.x[i]) < 1e-10),
        );
        assert.equal(
          +(await profilePlot.getAttribute("data-profile-row-count")),
          36,
        );
        assert.equal(
          +(await profilePlot.getAttribute("data-profile-shift-bins")),
          expected.shiftBins,
        );
        assert.equal(await profilePlot.getAttribute("aria-description"), null);
        assert.equal(
          calls.filter(([a]) => a === "cake_profile").length,
          readsBeforeShift,
        );
        await assertShared();
        await assertProfileWindow();
      }
      await assertUnitTransitions("2th_deg");
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
        await assertShared();
        const controlCenters = await panel.evaluate((el) =>
          [
            ".field-label > span",
            ".field-label input",
            '[aria-label="Show profile bin width"] svg',
            '[aria-label="Save azimuthal profile"] svg',
          ].map((selector) => {
            const r = el.querySelector(selector).getBoundingClientRect();
            return r.y + r.height / 2;
          }),
        );
        assert.ok(
          Math.max(...controlCenters) - Math.min(...controlCenters) < 0.5,
          `Bins label, input and Save icon must share a vertical center: ${controlCenters}`,
        );
        const layout = await panel.evaluate((el) => {
          const r = el.getBoundingClientRect(),
            p = el.closest(".integration-image-pane").getBoundingClientRect();
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
      await button("Cake").click();
      await idle();
      await button("Azimuthal profile").click();
      await idle();
      await clickPlot(radialPlot);
      await profilePlot.waitFor();
      await idle();
      assert.equal(profiles.at(-1).radialUnit, "q_A^-1");
      await assertUnitTransitions("q_A^-1");
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
        unitTransitionsKeepSourceProfileAndBothViewports: true,
        profileLeftOfCakeWithSharedAzimuth: true,
        profileHiddenInImageMode: true,
        resizableWidthAndAxisDrag: true,
        stableToolbarAtCakeEdges: true,
        verticallyCenteredControls: true,
        immediateSliderWrapMatchesNative: true,
        zeroSamplesDrawGapsAndExportUnchanged: true,
        zeroGapWidths: [1, 3, 9],
        nativeBinWindowOverlay: true,
        profileToggleOnlyInCake: true,
        profileVerticalSliceAndRectangle: true,
        liveWidthEdgeDragAndCoalescing: true,
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

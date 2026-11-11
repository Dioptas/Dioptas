import { checkCakeProfileInteraction } from "./cake_profile_interaction.mjs";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm, mkdir, writeFile, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { selectIntegrationDisplay } from "./integration_display.mjs";
import { setInterfaceTextSize } from "./plot_navigation.mjs";
const temporary = await mkdtemp(
  path.join(tmpdir(), "dioptas-detector-source-"),
);
const source = path.join(temporary, "sources.h5"),
  artifacts = path.join(root, "desktop/artifacts/detector-window");
execFileSync(
  "cargo",
  [
    "run",
    "--quiet",
    "--locked",
    "--manifest-path",
    path.join(root, "desktop/backend/Cargo.toml"),
    "--example",
    "hdf5_source_fixture",
    "--",
    source,
  ],
  { cwd: root, stdio: "inherit" },
);
// A disabled, loaded flat field is still a valid Qt correction preview.
const flat = path.join(temporary, "flat.npy");
let header = "{'descr': '<f8', 'fortran_order': False, 'shape': (24, 32), }";
while ((10 + header.length + 1) % 64) header += " ";
header += "\n";
const flatBytes = Buffer.alloc(10 + header.length + 768 * 8);
flatBytes.set(Buffer.from([147, 78, 85, 77, 80, 89, 1, 0]));
flatBytes.writeUInt16LE(header.length, 8);
flatBytes.write(header, 10);
for (let i = 0; i < 768; i++)
  flatBytes.writeDoubleLE(2 + i / 768, 10 + header.length + i * 8);
await writeFile(flat, flatBytes);
const results = [];
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    let browser;
    try {
      assert.equal((await native.invoke("__host__")).runtime, "rust");
      await native.invoke("open_image", {
        path: source,
        dataset: "/a",
        frame: 3,
      });
      await native.invoke("manual_geometry", {
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
      await native.invoke("integration_settings", {
        bins: 24,
        cake_bins: 12,
        trim_zeros: false,
      });
      assert.equal(
        (await native.invoke("integration_flat_field", { path: flat })).ok,
        true,
      );
      assert.equal(
        (await native.invoke("integration_flat_field", { enabled: false })).ok,
        true,
      );
      browser = await type.launch({ headless: true });
      const context = await browser.newContext({
          viewport: { width: 1000, height: 668 },
        }),
        errors = [];
      context.on("page", (p) =>
        p.on("pageerror", (e) => errors.push(e.message)),
      );
      let previewRequests = 0;
      let profileRequests = 0;
      await context.exposeBinding("__nativeInvoke", async (_, a, p = {}) => {
        if (a === "integration_correction_preview") previewRequests++;
        if (a === "cake_profile") profileRequests++;
        if (a === "save_cake_profile")
          p = { ...p, path: path.join(temporary, `${name}-profile.xy`) };
        return native.browserResult(await native.invoke(a, p));
      });
      await context.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
        };
      });
      const page = await context.newPage();
      page.setDefaultTimeout(20000);
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
      const ready = async () => {
        await page.waitForFunction(() => !document.querySelector(".spin"));
        await page.waitForTimeout(180);
      };
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await ready();
      await page.getByRole("tab", { name: "Image", exact: true }).click();
      await selectIntegrationDisplay(page, "image");
      const popup = page.waitForEvent("popup");
      await page
        .getByRole("button", { name: "Undock detector image", exact: true })
        .click();
      let child = await popup;
      await child.getByTestId("detector-canvas").waitFor();
      const checkShape = async (w, h) =>
        child.waitForFunction(
          ([w, h]) => {
            const d = document.querySelector(
              '[data-testid="detector-canvas"]',
            )?.dataset;
            return d?.fullWidth === String(w) && d?.fullHeight === String(h);
          },
          [w, h],
        );
      await checkShape(32, 24);
      await page.getByLabel("Image source", { exact: true }).selectOption("/b");
      await ready();
      assert.equal(
        (await native.invoke("state")).state.selectedImageSource,
        "/b",
      );
      assert.equal((await native.invoke("state")).state.integration.frame, 2);
      // Source metadata and pixels are published together (B clamps A's frame 3 to B2).
      await child.mouse.move(400, 300);
      await child.waitForTimeout(250);
      assert.match(
        await child.getByTestId("detector-readout").innerText(),
        /31/,
      );
      const science = async () => {
        const reply = await native.invoke("state");
        return {
          state: reply.state,
          pattern: reply.pattern,
          image: reply.image.bufferId,
          rawImage: reply.rawImage.bufferId,
          mask: reply.mask.bufferId,
        };
      };
      // Joint regression with the already consolidated Q axis and profile view.
      await page
        .getByRole("button", { name: "Pattern unit Q", exact: true })
        .click();
      await ready();
      await child.mouse.click(400, 300);
      await ready();
      await child
        .getByRole("button", { name: "Azimuthal profile", exact: true })
        .click();
      await ready();
      let profile = child.getByRole("region", {
        name: "Azimuthal profile",
        exact: true,
      });
      await profile.getByTestId("cake-profile-canvas").waitFor();
      await child.getByRole("button", { name: "Image", exact: true }).click();
      await ready();
      assert.equal(await profile.isVisible(), false);
      const hiddenProfileReads = profileRequests;
      await child.getByTestId("detector-canvas").click();
      await ready();
      assert.equal(profileRequests, hiddenProfileReads);
      await child.getByRole("button", { name: "Cake", exact: true }).click();
      await ready();
      await profile.getByTestId("cake-profile-canvas").waitFor();
      assert.equal((await native.invoke("state")).state.unit, "q_A^-1");
      await profile
        .getByRole("button", { name: "Save azimuthal profile", exact: true })
        .click();
      await ready();
      assert.match(
        await readFile(path.join(temporary, `${name}-profile.xy`), "utf8"),
        /[0-9]/,
      );
      const sourceScience = await science();
      const checkProfileAlignment = async () => {
        const read = async (node) =>
          node.evaluate((el) => {
            const r = el.getBoundingClientRect(),
              d = el.dataset;
            return {
              x: r.x,
              right: r.right,
              top: r.y + +d.plotTop,
              bottom: r.y + +d.plotTop + +d.plotHeight,
              min: +d.viewYMin,
              max: +d.viewYMax,
            };
          });
        const p = await read(profile.getByTestId("cake-profile-canvas")),
          c = await read(child.getByTestId("cake-canvas"));
        assert.ok(
          p.right <= c.x + 1 &&
            Math.abs(p.top - c.top) < 1.1 &&
            Math.abs(p.bottom - c.bottom) < 1.1,
          JSON.stringify({ p, c }),
        );
        assert.equal(p.min, c.min);
        assert.equal(p.max, c.max);
      };
      await checkProfileAlignment();
      await checkCakeProfileInteraction(
        child,
        profile.getByTestId("cake-profile-canvas"),
        child.getByTestId("cake-canvas"),
        ready,
      );
      await profile.getByTestId("cake-profile-canvas").press("+");
      await ready();
      await checkProfileAlignment();
      await child.getByTestId("cake-canvas").press("+");
      await ready();
      await checkProfileAlignment();
      await profile.getByTestId("cake-profile-canvas").press("f");
      await ready();
      await checkProfileAlignment();
      await child.screenshot({
        path: path.join(artifacts, `${name}-shared-profile.png`),
      });
      const sourceMaximum = await child
        .getByTestId("cake-canvas")
        .getAttribute("data-intensity-max");
      await page.getByRole("tab", { name: "Corrections", exact: true }).click();
      await page
        .getByRole("navigation", { name: "Correction type" })
        .getByRole("button", { name: "Flat field", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Plot correction", exact: true })
        .click();
      await ready();
      await child.locator(".detached-detector-heading").waitFor();
      assert.match(
        await child.locator(".detached-detector-heading").innerText(),
        /Mean-normalized.*dimensionless/,
      );
      await child.mouse.move(400, 300);
      await child.waitForTimeout(250);
      assert.match(
        await child.getByTestId("detector-readout").innerText(),
        /Factor/,
      );
      assert.equal(previewRequests, 1, "Detached preview was calculated twice");
      const readsDuringPreview = profileRequests;
      assert.equal(
        await profile.isVisible(),
        false,
        "Profile is only shown beside a cake, not a correction map",
      );
      await ready();
      assert.equal(profileRequests, readsDuringPreview);

      assert.deepEqual(
        await science(),
        sourceScience,
        "Detached preview changed the scientific session",
      );
      await child
        .getByRole("button", {
          name: "Back from correction preview",
          exact: true,
        })
        .click();
      await child
        .locator(".detached-detector-heading")
        .waitFor({ state: "detached" });
      await child.waitForFunction(
        (max) =>
          document.querySelector('[data-testid="cake-canvas"]')?.dataset
            .intensityMax === max,
        sourceMaximum,
      );
      // Close while a correction is shown: its owner and viewport return intact.
      await page
        .getByRole("button", { name: "Plot correction", exact: true })
        .click();
      await ready();
      await child.locator(".detached-detector-heading").waitFor();
      await child.mouse.move(400, 300);
      await child.mouse.wheel(0, -180);
      await child.waitForTimeout(180);
      const previewX = await child
        .getByTestId("detector-canvas")
        .getAttribute("data-view-x-min");
      await child.close();
      const restoredPreview = page.locator(
        '.correction-preview [data-testid="detector-canvas"]',
      );
      await restoredPreview.waitFor();
      assert.equal(
        await restoredPreview.getAttribute("data-view-x-min"),
        previewX,
      );
      const reopened = page.waitForEvent("popup");
      await page
        .getByRole("button", { name: "Undock detector image", exact: true })
        .click();
      child = await reopened;
      profile = child.getByRole("region", {
        name: "Azimuthal profile",
        exact: true,
      });
      await child.locator(".detached-detector-heading").waitFor();
      assert.equal(
        previewRequests,
        2,
        "Closing/reopening recalculated the correction preview",
      );
      await child
        .getByRole("button", {
          name: "Back from correction preview",
          exact: true,
        })
        .click();
      await child
        .locator(".detached-detector-heading")
        .waitFor({ state: "detached" });
      await child
        .getByRole("button", { name: "Azimuthal profile", exact: true })
        .click();
      await ready();
      await child.getByRole("button", { name: "Image", exact: true }).click();
      await ready();
      assert.equal(await profile.isVisible(), false);
      await page.getByRole("tab", { name: "Image", exact: true }).click();
      await page
        .getByRole("button", { name: "Calibration", exact: true })
        .click();
      await page
        .getByRole("tab", { name: "Step 1: Image & setup", exact: true })
        .click();
      await ready();
      await page
        .getByRole("button", { name: "Rotate image +90°", exact: true })
        .click();
      await ready();
      await checkShape(24, 32);
      assert.equal((await native.invoke("state")).state.calibrated, true);
      await page
        .getByRole("button", {
          name: "Reset image transformations",
          exact: true,
        })
        .click();
      await ready();
      await checkShape(32, 24);
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await ready();
      await page.getByLabel("Image source", { exact: true }).selectOption("/c");
      const dialog = page.getByRole("dialog");
      await dialog.waitFor();
      await page.getByRole("button", { name: "Cancel", exact: true }).click();
      await ready();
      await checkShape(32, 24);
      assert.equal(
        (await native.invoke("state")).state.selectedImageSource,
        "/b",
      );
      await page.getByLabel("Image source", { exact: true }).selectOption("/c");
      await dialog.waitFor();
      await page
        .getByRole("button", {
          name: "Open and reset calibration",
          exact: true,
        })
        .click();
      await ready();
      await checkShape(20, 16);
      assert.equal((await native.invoke("state")).state.calibrated, false);
      for (const large of [false, true]) {
        await setInterfaceTextSize(page, large);
        await child.waitForFunction(
          (l) =>
            document.querySelector(".app").dataset.textSize ===
            (l ? "large" : "normal"),
          large,
        );
        await child.setViewportSize({ width: 520, height: 460 });
        await child.waitForTimeout(150);
        const layout = await child
          .getByTestId("detector-canvas")
          .evaluate((c) => ({
            width: innerWidth,
            scroll: document.documentElement.scrollWidth,
            d: { ...c.dataset },
            b: c.getBoundingClientRect().toJSON(),
          }));
        assert.ok(layout.scroll <= layout.width);
        assert.ok(
          layout.b.width > 200 &&
            layout.b.height > 200 &&
            layout.b.right <= layout.width,
        );
        assert.ok(
          await child
            .locator(".app")
            .evaluate((el) => el.getBoundingClientRect().width <= innerWidth),
        );
        const scale =
          +layout.d.plotWidth /
          (+layout.d.viewXMax - +layout.d.viewXMin) /
          (+layout.d.plotHeight / (+layout.d.viewYMax - +layout.d.viewYMin));
        assert.ok(Math.abs(scale - 1) < 0.00001);
        await child.screenshot({
          path: path.join(
            artifacts,
            `${name}-${large ? "larger" : "standard"}-compact.png`,
          ),
        });
      }
      await child
        .getByRole("button", { name: "Dock detector image", exact: true })
        .click();
      await page.getByTestId("detector-canvas").waitFor();
      assert.equal(
        (await native.invoke("state")).state.selectedImageSource,
        "/c",
      );
      assert.deepEqual(errors, []);
      results.push({
        browser: name,
        sourceFrameClamp: true,
        correctionPreview: true,
        correctionBackAndClose: true,
        previewScienceUnchanged: true,
        noDuplicatePreviewCalculation: true,
        retainedCakeQAndProfile: true,
        sharedAzimuth: true,
        resizableProfileAndOuterAxisDrag: true,
        profileOnlyInCake: true,
        orientation: true,
        calibratedSourceCancel: true,
        sourceReset: true,
        compactTextSizes: ["Standard", "Larger"],
        squarePixels: true,
        errors,
      });
    } finally {
      await browser?.close();
      await native.close();
    }
  }
  await mkdir(artifacts, { recursive: true });
  await writeFile(
    path.join(artifacts, "source-results.json"),
    JSON.stringify(results, null, 2) + "\n",
  );
  console.log(JSON.stringify(results, null, 2));
} finally {
  await rm(temporary, { recursive: true, force: true });
}

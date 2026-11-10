// Real Rust failures through React file controls. Only the OS chooser is
// replaced by a selected path for this headless browser check.
import assert from "node:assert/strict";
import {
  mkdtemp,
  mkdir,
  writeFile,
  copyFile,
  realpath,
  rm,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/native-file-errors");
await mkdir(artifacts, { recursive: true });
const temp = await realpath(
  await mkdtemp(path.join(os.tmpdir(), "dioptas-file-errors-")),
);
const eiger = path.join(temp, "eiger.poni");
await writeFile(
  eiger,
  `poni_version: 2.1\nDetector: Eiger2CdTe_9M\nDetector_config: {"orientation": 2}\nDistance: 0.1839103128035422\nPoni1: 0.11374917888680143\nPoni2: 0.11053144274970403\nRot1: 0.012275635675880966\nRot2: 0.012776464559415958\nRot3: -3.4968839362494736e-09\nWavelength: 3.738e-11\n`,
);
const receipts = [];
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await type.launch({ headless: true });
    const errors = [];
    let selected = eiger;
    const call = async (action, payload = {}) => {
      const result = await native.invoke(action, payload);
      assert.equal(result.ok, true, `${action}: ${result.error}`);
      return result;
    };
    try {
      await call("example");
      const page = await browser.newPage({
        viewport: { width: 1100, height: 760 },
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (action, payload) => {
        const result = await native.invoke(
          action,
          ["open_calibration", "open_image"].includes(action)
            ? { ...payload, path: selected }
            : payload,
        );
        // Make transient busy-state flicker observable even on a fast machine.
        if (action === "next_image")
          await new Promise((resolve) => setTimeout(resolve, 200));
        return native.browserResult(result);
      });
      await page.addInitScript(() => {
        window.__pending = 0;
        window.__navigationCompleted = 0;
        window.pywebview = {
          api: {
            invoke: async (a, p) => {
              const track = !["progress", "pixel"].includes(a);
              if (track) window.__pending++;
              try {
                return await window.__nativeInvoke(a, p);
              } finally {
                if (track) window.__pending--;
                if (a === "next_image") window.__navigationCompleted++;
              }
            },
          },
        };
      });
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
      await page.getByTestId("detector-canvas").waitFor();
      const ready = async () => {
        await page.waitForFunction(
          () => window.__pending === 0 && !document.querySelector(".spin"),
        );
        assert.deepEqual(errors, []);
      };
      await ready();
      const before = await call("state");
      const load = page.getByRole("button", {
        name: "Load .poni",
        exact: true,
      });
      await load.click();
      const dialog = page.getByRole("dialog", {
        name: "Couldn’t load calibration",
      });
      await dialog.waitFor();
      await ready();
      assert.match(
        await dialog.innerText(),
        /Open the matching detector image/,
      );
      assert.equal(
        await dialog.locator("details").evaluate((el) => el.open),
        false,
      );
      assert.equal(
        await dialog
          .getByRole("button", { name: "OK", exact: true })
          .evaluate((el) => el === document.activeElement),
        true,
      );
      await page.screenshot({
        path: path.join(artifacts, `${name}-short.png`),
      });
      await dialog.getByText("Details", { exact: true }).click();
      assert.match(await dialog.innerText(), /3108 × 3262/);
      assert.match(await dialog.innerText(), /981 × 1043/);
      const after = await call("state");
      assert.deepEqual(after.state.calibration, before.state.calibration);
      assert.equal(after.image.bufferId, before.image.bufferId);
      await dialog.getByRole("button", { name: "OK", exact: true }).click();
      assert.equal(await dialog.count(), 0);
      await load.click();
      await dialog.waitFor();
      await page.keyboard.press("Escape");
      assert.equal(await dialog.count(), 0);
      selected = path.join(temp, "missing.poni");
      await load.click();
      await dialog.waitFor();
      assert.match(
        await dialog.innerText(),
        /selected file could not be loaded/,
      );
      await dialog
        .getByText("Error report and recent steps", { exact: true })
        .click();
      const fileReport = await dialog
        .getByRole("textbox", { name: "Error report", exact: true })
        .inputValue();
      assert.match(fileReport, /Recent steps/);
      assert.match(fileReport, /open_calibration.*failed/);
      assert.match(fileReport, /missing\.poni/);
      assert.match(fileReport, /Build: 0.1.0/);
      await dialog.getByRole("button", { name: "OK", exact: true }).click();
      selected = path.join(root, "dioptas/tests/data/LaB6_40keV_MarCCD.poni");
      await load.click();
      await ready();
      assert.equal(await dialog.count(), 0);
      assert.equal(
        (await call("state")).state.calibration.pyfai.dist,
        0.196711580484,
      );
      // Beamline use: repeatedly click Next at the end, then retry after
      // another image arrives. Both ordering modes must remain usable.
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await page.getByRole("tab", { name: "Image", exact: true }).click();
      const nextImage = page.getByRole("button", {
        name: "Integration next image",
        exact: true,
      });
      const previousImage = page.getByRole("button", {
        name: "Integration previous image",
        exact: true,
      });
      const fixture = path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif");
      for (const mode of ["Name", "Time"]) {
        const directory = path.join(temp, `${name}-${mode}`);
        await mkdir(directory);
        const first = path.join(directory, "scan_001.tif");
        const second = path.join(directory, "scan_002.tif");
        await copyFile(fixture, first);
        selected = first;
        await page
          .getByRole("button", { name: "Load image…", exact: true })
          .click();
        await ready();
        await page
          .getByRole("combobox", { name: "Image file order", exact: true })
          .selectOption(mode === "Name" ? "number" : "time");
        await ready();
        const beforeEnd = await call("state");
        for (const button of [previousImage, nextImage, nextImage]) {
          await page.evaluate(() => {
            window.__navigationFlicker = [];
            window.__navigationObserver = new MutationObserver((changes) => {
              if (changes.some((change) => change.attributeName === "disabled"))
                window.__navigationFlicker.push("controls disabled");
              if (document.querySelector(".workflow-status .spin"))
                window.__navigationFlicker.push("busy spinner");
            });
            window.__navigationObserver.observe(document.body, {
              subtree: true,
              childList: true,
              attributes: true,
              attributeFilter: ["disabled"],
            });
          });
          await button.click();
          await ready();
          assert.deepEqual(
            await page.evaluate(() => {
              window.__navigationObserver.disconnect();
              return window.__navigationFlicker;
            }),
            [],
          );
          assert.match(
            await page.locator(".workflow-status").innerText(),
            button === previousImage
              ? /No previous image available/
              : /No new image available/,
          );
          assert.equal(await page.getByRole("dialog").count(), 0);
          assert.deepEqual(await call("state"), beforeEnd);
          assert.equal(await nextImage.isEnabled(), true);
        }
        await copyFile(fixture, second);
        await nextImage.click();
        await ready();
        assert.equal((await call("state")).state.imagePath, second);
        // The worker can finish before React publishes the image and clears
        // the quiet boundary notice. Wait for that visible completion too.
        await page.waitForFunction(
          () =>
            !/No (new|previous) image available/.test(
              document.querySelector(".workflow-status")?.textContent ?? "",
            ),
        );
        assert.doesNotMatch(
          await page.locator(".workflow-status").innerText(),
          /No (new|previous) image available/,
        );
        await previousImage.click();
        await ready();
        assert.equal((await call("state")).state.imagePath, first);
        const completed = await page.evaluate(
          () => window.__navigationCompleted,
        );
        await page.evaluate(() => {
          const next = document.querySelector(
            '[aria-label="Integration next image"]',
          );
          const previous = document.querySelector(
            '[aria-label="Integration previous image"]',
          );
          next.click();
          previous.click();
          next.click();
        });
        await page.waitForFunction(
          (count) => window.__navigationCompleted === count + 3,
          completed,
        );
        await ready();
        assert.equal((await call("state")).state.imagePath, second);
        await previousImage.click();
        await ready();
        assert.equal((await call("state")).state.imagePath, first);
      }
      await page.evaluate(() => {
        Object.defineProperty(navigator, "clipboard", {
          configurable: true,
          value: {
            writeText: async (text) => {
              window.__copiedReport = text;
            },
          },
        });
        window.dispatchEvent(
          new ErrorEvent("error", {
            error: new Error("Test unexpected interface failure"),
          }),
        );
      });
      const unexpected = page.getByRole("dialog", {
        name: "An error occurred",
        exact: true,
      });
      await unexpected.waitFor();
      await unexpected
        .getByRole("button", { name: "Copy error report", exact: true })
        .click();
      const copied = await page.evaluate(() => window.__copiedReport);
      assert.match(copied, /Test unexpected interface failure/);
      assert.match(copied, /LaB6_40keV_MarCCD/);
      assert.match(copied, /Switch mode/);
      await unexpected
        .getByText("Error report and recent steps", { exact: true })
        .click();
      assert.equal(
        await unexpected
          .getByRole("textbox", { name: "Error report", exact: true })
          .inputValue(),
        copied,
      );
      await page.screenshot({
        path: path.join(artifacts, `${name}-report.png`),
      });
      await unexpected.getByRole("button", { name: "OK", exact: true }).click();
      await page.evaluate(() =>
        window.dispatchEvent(
          new PromiseRejectionEvent("unhandledrejection", {
            promise: Promise.resolve(),
            reason: new Error("Test asynchronous failure"),
          }),
        ),
      );
      await unexpected.waitFor();
      await page.keyboard.press("Escape");
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        atomicMismatch: true,
        focusedShortDialog: true,
        expandableDetails: true,
        okAndEscape: true,
        genericFileFailure: true,
        appendedPoni: true,
        recentStepsAndCopy: true,
        unexpectedAndUnhandledErrors: true,
        imageBoundaryNoopsAndRetry: ["number", "time"],
        quietImageNavigationAndFooterNotice: true,
        rapidImageNavigationUsesSelectionQueue: true,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
} finally {
  await rm(temp, { recursive: true, force: true });
}
await writeFile(
  path.join(artifacts, "receipt.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));

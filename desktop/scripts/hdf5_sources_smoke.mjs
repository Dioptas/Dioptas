import assert from "node:assert/strict";
import {
  copyFile,
  mkdir,
  mkdtemp,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
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
const fixture = path.join(temporary, "sources_001.h5"),
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
    temporary,
  ],
  { cwd: desktop, stdio: "inherit" },
);
const secondFile = path.join(temporary, "sources_002.h5"),
  thirdFile = path.join(temporary, "sources_003.h5");
await copyFile(fixture, secondFile);
await copyFile(fixture, thirdFile);
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
      browser = await type.launch({
        headless: true,
        ...(type === chromium
          ? { ignoreDefaultArgs: ["--hide-scrollbars"] }
          : {}),
      });
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
    const watchFolder = path.join(temporary, `watch-${name}`);
    await mkdir(watchFolder);
    let chosenFolder = watchFolder,
      cancelFolder = false,
      chosenImage = fixture;
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
          if (action === "integration_image_directory" && !payload.path) {
            if (cancelFolder) return { ok: true, cancelled: true };
            payload = { ...payload, path: chosenFolder };
          }
          if (action === "open_image" && !payload.path)
            payload = { ...payload, path: chosenImage };
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
      for (const mode of ["add", "average", "save", "integrate"]) {
        await page
          .getByRole("combobox", { name: "Batch mode", exact: true })
          .selectOption(mode);
        await ready();
        assert.equal(
          (await call("state")).state.integration.imageBatchMode,
          mode,
        );
      }
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
      const previousFrame = button("Integration previous frame"),
        nextFrame = button("Integration next frame"),
        frameStep = page.getByRole("spinbutton", {
          name: "Frame step",
          exact: true,
        }),
        framePosition = page.getByRole("spinbutton", {
          name: "Frame position (1–4)",
          exact: true,
        });
      assert.equal(await previousFrame.isDisabled(), true);
      await frameStep.fill("2");
      await frameStep.press("Enter");
      await nextFrame.click();
      await ready();
      assert.equal(await framePosition.inputValue(), "3");
      assert.equal((await call("state")).state.integration.frame, 3);
      await nextFrame.click();
      await ready();
      assert.equal(await framePosition.inputValue(), "4");
      assert.equal(await nextFrame.isDisabled(), true);
      await previousFrame.click();
      await ready();
      assert.equal(await framePosition.inputValue(), "2");
      await previousFrame.click();
      await ready();
      assert.equal(await framePosition.inputValue(), "1");
      assert.equal(await previousFrame.isDisabled(), true);
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(fixture),
      );
      await frameStep.fill("0");
      await frameStep.press("Enter");
      assert.equal(await frameStep.inputValue(), "2");
      // The two clicks occur before either command returns. Both must advance.
      await frameStep.fill("1");
      await frameStep.press("Enter");
      await nextFrame.evaluate((element) => {
        element.click();
        element.click();
      });
      await ready();
      assert.equal(await framePosition.inputValue(), "3");
      await frameStep.fill("2");
      await frameStep.press("Enter");
      await page
        .getByRole("spinbutton", { name: "File step", exact: true })
        .fill("3");
      await page.getByRole("tab", { name: "Pattern", exact: true }).click();
      await page.getByRole("tab", { name: "Image", exact: true }).click();
      assert.equal(await frameStep.inputValue(), "2");
      assert.equal(
        await page
          .getByRole("spinbutton", { name: "File step", exact: true })
          .inputValue(),
        "3",
      );
      report.checks.push(
        "Calibration and Integration dropdown; clamped frame, count and one-based frame navigation",
        "Frame arrows and independent step; boundary clamping, rapid queued clicks, invalid-step recovery and retained step across tabs",
      );
      const fileStep = page.getByRole("spinbutton", {
          name: "File step",
          exact: true,
        }),
        nextFile = button("Integration next image"),
        previousFile = button("Integration previous image");
      await fileStep.fill("1");
      await fileStep.press("Enter");
      await nextFile.click();
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(secondFile),
      );
      assert.equal(await framePosition.inputValue(), "1");
      await nextFrame.click();
      await ready();
      assert.equal(await framePosition.inputValue(), "3");
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(secondFile),
      );
      await nextFile.click();
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(thirdFile),
      );
      assert.equal(await framePosition.inputValue(), "1");
      await nextFile.click();
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(thirdFile),
      );
      assert.equal(await framePosition.inputValue(), "1");
      await fileStep.fill("2");
      await fileStep.press("Enter");
      await previousFile.click();
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(fixture),
      );
      assert.equal(await framePosition.inputValue(), "1");
      await nextFile.click();
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(thirdFile),
      );
      await previousFile.click();
      await ready();
      await previousFile.click();
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(fixture),
      );
      assert.equal(await framePosition.inputValue(), "1");
      assert.equal(await frameStep.inputValue(), "2");
      await nextFrame.click();
      await ready();
      assert.equal(await framePosition.inputValue(), "3");
      report.checks.push(
        "File arrows skip stacks and reset to frame 1; independent file/frame steps, missing-file boundaries and selected-source retention",
      );
      // Shortcuts use the file step, and never intercept text-editing keys.
      await nextFile.focus();
      await page.keyboard.press("PageDown");
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(thirdFile),
      );
      await previousFile.focus();
      await page.keyboard.press("PageUp");
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(fixture),
      );
      await page
        .getByRole("textbox", { name: "Image filename", exact: true })
        .focus();
      await page.keyboard.press("PageDown");
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(fixture),
      );
      await nextFile.focus();
      assert.equal(
        await nextFile.evaluate((element) => {
          return [
            new KeyboardEvent("keydown", {
              key: "ArrowRight",
              ctrlKey: true,
              bubbles: true,
              cancelable: true,
            }),
            new KeyboardEvent("keydown", {
              key: "ArrowLeft",
              metaKey: true,
              bubbles: true,
              cancelable: true,
            }),
          ].every(
            (event) => element.dispatchEvent(event) && !event.defaultPrevented,
          );
        }),
        true,
        "App leaves macOS modified-arrow shortcuts untouched",
      );
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(fixture),
      );
      await button("Settings").click();
      await page.keyboard.press("PageDown");
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(fixture),
      );
      await page.keyboard.press("Escape");
      await ready();
      const longSource = "/entry_0000/measurement/data";
      await choose(longSource);
      assert.equal(await selector().getAttribute("title"), longSource);
      const labels = await selector().locator("option").allTextContents();
      assert.equal(
        new Set(labels).size,
        labels.length,
        "Dataset labels must remain distinct",
      );
      const longFrame = page.getByRole("spinbutton", {
        name: "Frame position (1–625)",
        exact: true,
      });
      await longFrame.fill("625");
      await longFrame.press("Enter");
      await ready();
      assert.equal((await call("state")).state.integration.frame, 625);
      assert.equal(await nextFrame.isDisabled(), true);
      await longFrame.fill("0");
      await longFrame.press("Enter");
      await ready();
      assert.equal(await longFrame.getAttribute("aria-invalid"), "true");
      assert.equal((await call("state")).state.integration.frame, 625);
      await longFrame.press("Escape");
      assert.equal(await longFrame.inputValue(), "625");
      const sidebar = page.locator(".integration-layout > .sidebar");
      const imagePanelBox = await sidebar.boundingBox();
      for (const tab of ["Overlay", "Phase", "Image"]) {
        await page.getByRole("tab", { name: tab, exact: true }).click();
        const box = await sidebar.boundingBox();
        assert.equal(box.y, imagePanelBox.y);
        assert.equal(
          box.height,
          imagePanelBox.height,
          "Switching Integration tabs preserves the splitter position",
        );
      }
      // Capture the actual controls with long source names at normal and compact widths.
      for (const width of [1440, 1000])
        for (const large of [false, true]) {
          await page.setViewportSize({ width, height: 940 });
          await setInterfaceTextSize(page, large);
          await page
            .getByRole("tabpanel", { name: "Image controls", exact: true })
            .evaluate((element) => {
              element.scrollTop = 0;
            });
          const sourceBox = await selector().boundingBox();
          assert.ok(
            sourceBox.width <= 320 && sourceBox.height <= 32,
            "Source selector stays compact",
          );
          for (const arrow of [
            nextFile,
            previousFile,
            nextFrame,
            previousFrame,
          ]) {
            const box = await arrow.boundingBox();
            assert.ok(
              box.width === 32 && box.height === 30,
              "Navigation arrows have compact, usable targets",
            );
          }
          const controls = page.locator(".integration-image-files-aligned");
          assert.equal(
            await controls.evaluate(
              (element) => element.scrollWidth <= element.clientWidth,
            ),
            true,
          );
          const loadBox = await button("Load image…").boundingBox(),
            previousBox = await previousFile.boundingBox();
          assert.ok(
            Math.abs(loadBox.y - previousBox.y) < 2 &&
              previousBox.x - loadBox.x - loadBox.width < 12,
            "File arrows sit next to Load image",
          );
          for (const [arrow, step] of [
            [nextFile, fileStep],
            [nextFrame, frameStep],
          ]) {
            const arrowBox = await arrow.boundingBox();
            const stepLabel = await step.locator("..").boundingBox();
            assert.ok(
              Math.abs(
                arrowBox.y +
                  arrowBox.height / 2 -
                  stepLabel.y -
                  stepLabel.height / 2,
              ) < 2 && stepLabel.x - arrowBox.x - arrowBox.width <= 14,
              "Each step sits beside its browsing buttons",
            );
          }
          const filenameBox = await page
            .getByRole("textbox", { name: "Image filename", exact: true })
            .boundingBox();
          const folderBox = await button("Choose image folder").boundingBox();
          assert.ok(
            Math.abs(
              filenameBox.y +
                filenameBox.height / 2 -
                folderBox.y -
                folderBox.height / 2,
            ) < 2,
            "Folder stays beside the filename",
          );
          assert.ok(
            Math.abs(filenameBox.x - sourceBox.x) < 2 &&
              Math.abs(filenameBox.x - loadBox.x) < 2,
            "Load, File and Source share their aligned control column",
          );
          assert.equal(
            await page
              .getByRole("textbox", { name: "Image directory", exact: true })
              .count(),
            0,
            "No permanent folder input row",
          );
          assert.equal(await button("Show full source path").count(), 0);
          assert.equal(await button("Show all image sources").count(), 0);
          if (width === 1440) {
            const box = await controls.boundingBox();
            assert.ok(
              box.height < 235,
              "Aligned rows remain compact at both text sizes",
            );
          }
          await page.screenshot({
            path: path.join(
              artifacts,
              `${name}-navigation-${width}-${large ? "large" : "normal"}.png`,
            ),
          });
        }
      await page.setViewportSize({ width: 1440, height: 940 });
      await setInterfaceTextSize(page, false);
      await choose("/a");
      report.checks.push(
        "Compact arrows beside Load; file shortcuts and editing/Settings guards; distinct long dataset labels, direct 625-frame entry and invalid-frame recovery; responsive source/folder grouping",
      );
      const location = page.getByLabel("Image location", { exact: true });
      const automatic = page.getByRole("checkbox", {
        name: "Autoprocess",
        exact: true,
      });
      await button("Choose image folder").click();
      await ready();
      assert.equal(
        (await call("state")).state.integration.imageDirectory,
        await realpath(watchFolder),
      );
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(fixture),
      );
      await automatic.click();
      await ready();
      assert.equal(await automatic.isChecked(), true);
      assert.match(await location.innerText(), /Watching:/);
      assert.ok(
        (await location.textContent()).includes(await realpath(watchFolder)),
      );
      cancelFolder = true;
      await button("Choose image folder").click();
      await ready();
      assert.equal(
        (await call("state")).state.integration.imageDirectory,
        await realpath(watchFolder),
      );
      cancelFolder = false;
      const filename = page.getByRole("textbox", {
        name: "Image filename",
        exact: true,
      });
      await filename.fill(secondFile);
      await filename.press("Enter");
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(secondFile),
      );
      assert.equal(
        (await call("state")).state.integration.imageDirectory,
        await realpath(watchFolder),
      );
      assert.ok(
        (await location.textContent()).includes(await realpath(watchFolder)),
      );
      const incoming = path.join(watchFolder, "incoming_001.h5");
      await copyFile(fixture, incoming);
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Image filename"]')?.value ===
          "incoming_001.h5",
      );
      await ready();
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(incoming),
      );
      const watchNext = path.join(temporary, `watch-next-${name}`);
      await mkdir(watchNext);
      await copyFile(fixture, path.join(watchNext, "existing.h5"));
      chosenFolder = watchNext;
      await button("Choose image folder").click();
      await ready();
      for (let i = 0; i < 2; i++) await call("integration_autoprocess_poll");
      assert.equal(
        (await call("state")).state.imagePath,
        await realpath(incoming),
      );
      assert.ok(
        (await location.textContent()).includes(await realpath(watchNext)),
      );
      const nextIncoming = path.join(watchNext, "incoming_002.h5");
      await copyFile(fixture, nextIncoming);
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Image filename"]')?.value ===
          "incoming_002.h5",
      );
      await ready();
      await page.screenshot({
        path: path.join(artifacts, `${name}-aligned-watching.png`),
      });
      await automatic.click();
      await ready();
      assert.equal(await automatic.isChecked(), false);
      assert.doesNotMatch(await location.innerText(), /Watching:/);
      for (const [file, frames, hasSource] of [
        ["single-image.tif", 1, false],
        ["image-stack.tif", 3, false],
        ["single-source.h5", 3, true],
      ]) {
        chosenImage = path.join(temporary, file);
        await button("Load image…").click();
        await ready();
        assert.equal((await call("state")).state.integration.frames, frames);
        assert.equal(
          await selector().count(),
          0,
          "Single image/stack/single-source HDF5 needs no source chooser",
        );
        if (hasSource) {
          assert.equal(
            await page
              .locator(".integration-source-identity")
              .getAttribute("title"),
            "/data",
          );
          await button("File Info").click();
          assert.match(
            await page.locator(".integration-image-info").innerText(),
            /\/data/,
          );
          await button("File Info").click();
        }
        if (frames === 1) {
          assert.equal(
            await page
              .getByRole("group", { name: "Frame navigation", exact: true })
              .count(),
            0,
          );
          assert.equal(await nextFrame.count(), 0);
          assert.equal(await frameStep.count(), 0);
        } else {
          const value = page.getByRole("spinbutton", {
            name: "Frame position (1–3)",
            exact: true,
          });
          await nextFrame.click();
          await ready();
          assert.equal(await value.inputValue(), "3");
        }
        await page.screenshot({
          path: path.join(artifacts, `${name}-aligned-${file}.png`),
        });
      }
      chosenImage = fixture;
      await button("Load image…").click();
      await ready();
      const footerBeforePlane = await page
        .locator(".integration-image-options")
        .boundingBox();
      await choose("/plane");
      assert.equal(
        await page
          .getByRole("group", { name: "Frame navigation", exact: true })
          .count(),
        0,
      );
      const footerAfterPlane = await page
        .locator(".integration-image-options")
        .boundingBox();
      assert.ok(
        footerBeforePlane.y - footerAfterPlane.y >= 30,
        "A 2D source removes the whole frame row",
      );
      await choose("/a");
      const longFile = path.join(
        temporary,
        `detector_measurement_high_pressure_very_long_filename_000123-${name}.h5`,
      );
      await copyFile(fixture, longFile);
      chosenImage = longFile;
      await button("Load image…").click();
      await ready();
      assert.equal(await filename.inputValue(), path.basename(longFile));
      const tail = page.locator(".middle-elided-input .middle-elided-tail");
      assert.ok((await tail.innerText()).includes("000123"));
      await filename.focus();
      assert.notEqual(
        await filename.evaluate((input) => getComputedStyle(input).color),
        "rgba(0, 0, 0, 0)",
      );
      await filename.fill("unfinished filename");
      await filename.press("Escape");
      assert.equal(await filename.inputValue(), path.basename(longFile));
      chosenImage = fixture;
      await button("Load image…").click();
      await ready();
      report.checks.push(
        "Aligned rows; real Folder chooser/cancel; confirmed Watching path; reference browsing keeps the watcher; incoming files and folder retargeting; single image, TIFF stack and passive HDF5 source identity; hidden single-image frame controls and exact long filename editing",
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
        const navigation = page.getByRole("group", {
          name: "Frame navigation",
          exact: true,
        });
        await navigation.scrollIntoViewIfNeeded();
        const navigationBox = await navigation.boundingBox();
        assert.ok(
          navigationBox &&
            navigationBox.x >= 0 &&
            navigationBox.x + navigationBox.width <= 1000,
        );
        assert.equal(
          await navigation.evaluate(
            (element) => element.scrollWidth <= element.clientWidth,
          ),
          true,
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

// Refresh the user-manual screenshots from the current checkout.
//
//   node scripts/capture-manual-screenshots.mjs [--section a,b] [--out dir]
//
// Every image is the real interface in headless Chromium, driven through its
// own controls against the native Rust processor (target/debug/dioptas-processor
// or DIOPTAS_NATIVE_PROCESSOR). Nothing is composited or retouched. Example
// files are copied to a neutral folder first so that no personal path appears
// in a published image. See manual/README.md.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { cp, mkdir, readFile, rm, writeFile, readdir } from "node:fs/promises";
import path from "node:path";
import {
  fixture,
  mapImages,
  root,
  startManualSession,
} from "./manual_capture_harness.mjs";

const args = process.argv.slice(2);
const option = (key, fallback) =>
  args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const allSections = [
  "start",
  "calibration",
  "mask",
  "integration",
  "batch",
  "map",
  "scxrd",
  "configurations",
  "settings",
];
const sections = option("--section", allSections.join(",")).split(",");
for (const name of sections)
  assert.ok(allSections.includes(name), `Unknown section: ${name}`);
const out = path.resolve(
  root,
  option("--out", "manual/src/assets/screenshots"),
);
await mkdir(out, { recursive: true });
const recordPath = path.join(out, "capture-record.json");
let record = { records: [] };
try {
  record = JSON.parse(await readFile(recordPath, "utf8"));
} catch {}
record.method =
  "Actual Dioptas interface in headless Chromium (Playwright) at 1440 × 900, device scale 1.5, connected to the native Rust processor. Driven through the visible controls; no compositing.";
record.sourceCommit = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: root,
  encoding: "utf8",
}).trim();

// Neutral working copy of the redistributable test data.
const work = path.resolve(
  process.env.DIOPTAS_MANUAL_DATA_DIR ??
    (process.platform === "win32"
      ? "C:\\dioptas-manual"
      : "/tmp/dioptas-manual"),
);
await rm(work, { recursive: true, force: true });
const example = path.join(work, "example");
const scan = path.join(work, "scan");
const output = path.join(work, "output");
for (const folder of [example, scan, output])
  await mkdir(folder, { recursive: true });
for (const name of [
  "CeO2_Pilatus1M.tif",
  "CeO2_Pilatus1M.poni",
  "pattern_001.xy",
  "jcpds/au_Anderson.jcpds",
  "jcpds/pt.jcpds",
  "jcpds/re.jcpds",
])
  await cp(fixture(name), path.join(example, path.basename(name)));
for (const file of await mapImages())
  await cp(file, path.join(scan, path.basename(file)));
const scanFiles = async () =>
  (await mapImages()).map((file) => path.join(scan, path.basename(file)));
const ceo2 = path.join(example, "CeO2_Pilatus1M.tif");
const poni = path.join(example, "CeO2_Pilatus1M.poni");

async function session(run) {
  const s = await startManualSession();
  const { page } = s;
  const capture = async (
    name,
    description,
    { clip, target = page, keepPointer = false } = {},
  ) => {
    await s.settle(target);
    assert.deepEqual(s.errors, [], `page errors before ${name}`);
    // The footer carries processing errors; workflow notices elsewhere are fine.
    const alerts = await target
      .getByRole("contentinfo")
      .getByRole("alert")
      .allTextContents();
    assert.deepEqual(alerts, [], `visible error before ${name}`);
    if (!keepPointer) await target.mouse.move(2, 450);
    await target.evaluate(() => document.fonts.ready);
    await target.waitForTimeout(200);
    const file = path.join(out, `${name}.jpg`);
    await target.screenshot({ path: file, type: "jpeg", quality: 90, clip });
    record.records = record.records.filter((item) => item.name !== name);
    record.records.push({
      name,
      file: path.relative(root, file).split(path.sep).join("/"),
      description,
      capturedAt: new Date().toISOString(),
      viewport: target.viewportSize(),
      status: await target
        .getByRole("contentinfo")
        .getByRole("status")
        .first()
        .innerText()
        .catch(() => null),
      sha256: createHash("sha256")
        .update(await readFile(file))
        .digest("hex"),
    });
    record.records.sort((a, b) => a.name.localeCompare(b.name));
    await writeFile(recordPath, JSON.stringify(record, null, 2) + "\n");
    console.log("captured", name);
  };
  // Click a detector position given in image pixels (bottom-left convention).
  const detectorClick = async (x, y, testId = "detector-canvas") => {
    const canvas = page.getByTestId(testId).first();
    const box = await canvas.boundingBox();
    const view = await canvas.evaluate((el) => ({
      left: +el.dataset.plotLeft,
      top: +el.dataset.plotTop,
      width: +el.dataset.plotWidth,
      height: +el.dataset.plotHeight,
      xMin: +el.dataset.viewXMin,
      xMax: +el.dataset.viewXMax,
      yMin: +el.dataset.viewYMin,
      yMax: +el.dataset.viewYMax,
    }));
    const point = {
      x:
        box.x +
        view.left +
        ((x - view.xMin) / (view.xMax - view.xMin)) * view.width,
      y:
        box.y +
        view.top +
        ((view.yMax - y) / (view.yMax - view.yMin)) * view.height,
    };
    await page.mouse.click(point.x, point.y);
    await s.settle();
    return point;
  };
  const field = async (label, value, scope = page) => {
    const input = scope.getByLabel(label, { exact: true });
    await input.fill(String(value));
    await input.press("Enter");
    await s.settle();
  };
  // A calibrated CeO2 session, reached through the same controls a user has.
  const openCalibrated = async () => {
    await s.open();
    s.choose("open_image", ceo2);
    await s.button("Open image").click();
    await s.settle();
    s.choose("open_calibration", poni);
    await s.button("Load .poni").click();
    await s.settle();
  };
  try {
    await run({ ...s, capture, detectorClick, field, openCalibrated });
  } catch (error) {
    if (process.env.MANUAL_DEBUG)
      for (const open of s.context.pages())
        console.error(
          (await open.locator("body").ariaSnapshot())
            .split("\n")
            .filter((line) => !line.includes('option "'))
            .join("\n"),
        );
    throw error;
  } finally {
    const failed = s.log.filter((entry) => !entry.ok);
    if (failed.length) console.warn("Rejected commands:", failed);
    await s.close();
  }
}

const tasks = {
  async start() {
    await session(async (s) => {
      await s.open();
      await s.capture(
        "first-start",
        "Empty workspace directly after start: Calibration mode, Image tab, no image loaded.",
      );
      s.choose("open_image", ceo2);
      await s.button("Open image").click();
      await s.settle();
      s.choose("open_calibration", poni);
      await s.button("Load .poni").click();
      await s.mode("Integration");
      await s.capture(
        "workspace",
        "Integration mode with the CeO2 Pilatus 1M example and its reference calibration: mode bar, detector image, task tabs, pattern and footer.",
      );
      await s.page.getByTestId("detector-canvas").first().hover();
      const point = await s.detectorClick(640, 620);
      await s.page.mouse.move(point.x + 40, point.y - 25);
      await s.page.waitForTimeout(400);
      const viewport = s.page.viewportSize();
      await s.capture(
        "footer-readout",
        "Footer after clicking a detector position: live readout on the left, green Click position, status on the right.",
        {
          keepPointer: true,
          clip: {
            x: 0,
            y: viewport.height - 300,
            width: viewport.width,
            height: 300,
          },
        },
      );
    });
  },
  async calibration() {
    await session(async (s) => {
      await s.open();
      s.choose("open_image", ceo2);
      await s.button("Open image").click();
      await s.settle();
      await s.field("Pixel width in micrometres", 172);
      await s.field("Pixel height in micrometres", 172);
      await s.capture(
        "calibration-image",
        "Calibration, Image tab: the raw CeO2 calibrant image with detector, pixel size and orientation controls.",
      );
      await s.tab("Fit").click();
      await s.page
        .getByLabel("Calibration calibrant", { exact: true })
        .selectOption({ label: "CeO2" });
      await s.field("Wavelength constraint value", 0.4066);
      await s.field("Distance constraint value", 200);
      await s.tab("Peaks").click();
      // One click per ring; automatic peak search follows each ring.
      const centre = { x: 488, y: 514 };
      for (const [radius, angle] of [
        [158.8, 35],
        [183.9, 140],
        [262.3, 215],
        [309.7, 320],
      ]) {
        const a = (angle * Math.PI) / 180;
        await s.detectorClick(
          centre.x + radius * Math.cos(a),
          centre.y + radius * Math.sin(a),
        );
      }
      await s.capture(
        "calibration-peaks",
        "Calibration, Peaks tab: four CeO2 rings picked with automatic peak search, one click each; the group table lists ring, peak count and position.",
      );
      await s.tab("Fit").click();
      await s.capture(
        "calibration-fit-start",
        "Calibration, Fit tab before fitting: calibrant, start values with their Fit checkboxes, and Refinement options.",
      );
      await s.button("Calibrate").click();
      await s.settle(s.page, 1500);
      await s.capture(
        "calibration-fit",
        "Calibration, Fit tab after Calibrate with automatic refinement: fitted geometry and calibrant rings over the image.",
      );
      await s.tab("Validate").click();
      await s.capture(
        "calibration-validate",
        "Calibration, Validate tab: fit residual, geometry in pyFAI convention, ring overlay.",
      );
    });
  },
  async mask() {
    await session(async (s) => {
      await s.openCalibrated();
      await s.mode("Mask");
      // Shapes are placed by clicks: centre then edge, or two corners.
      await s.button("Circle").click();
      await s.detectorClick(488, 514);
      await s.detectorClick(488, 548);
      await s.button("Rectangle").click();
      await s.detectorClick(505, 478);
      await s.detectorClick(972, 520);
      await s.button("Polygon").click();
      for (const [x, y] of [
        [640, 470],
        [972, 365],
        [972, 430],
        [650, 500],
      ])
        await s.detectorClick(x, y);
      await s.page.keyboard.press("Enter");
      await s.settle();
      await s.field("Above threshold counts", 20000);
      await s.button("Above Thresh").click();
      await s.settle();
      await s.capture(
        "mask-tools",
        "Mask mode: a circle over the beam stop, a rectangle and a polygon over its holder, and an upper threshold, made with the tools in the right panel.",
      );
      await s.page.getByLabel("Spot Mask", { exact: true }).click();
      await s.settle();
      await s.button("Spot Mask settings").click();
      await s.settle();
      await s.capture(
        "mask-plugins",
        "Dynamic masking plugins: Spot Mask enabled with its settings open.",
      );
    });
  },
  async integration() {
    await session(async (s) => {
      await s.openCalibrated();
      await s.mode("Integration");
      await s.button("Cake").click();
      await s.settle();
      await s.capture(
        "integration-cake",
        "Integration with the detector display switched to Cake: azimuth against 2θ above the same radial axis as the pattern.",
      );
      await s
        .button("Image")
        .click()
        .catch(() => {});
      await s.tab("Pattern").click();
      await s.capture(
        "integration-pattern",
        "Integration, Pattern tab: pattern file browser, Autocreate formats and Spottiness.",
      );
      await s.tab("Background").click();
      await s.page
        .getByLabel("Subtract automatic pattern background", { exact: true })
        .check();
      await s.settle();
      await s.button("Inspect background").click();
      await s.settle();
      await s.capture(
        "integration-background",
        "Integration, Background tab: automatic pattern background with Inspect on, showing the estimated background under the measured pattern.",
      );
      await s.button("Inspect background").click();
      await s.page
        .getByLabel("Subtract automatic pattern background", { exact: true })
        .uncheck();
      await s.settle();
      await s.tab("Corrections").click();
      await s.button("cBN seat").click();
      await s.settle();
      await s.capture(
        "integration-corrections",
        "Integration, Corrections tab with the cBN seat correction selected (not applied).",
      );
      await s.tab("Overlay").click();
      await s.button("As Overlay").first().click();
      await s.settle();
      s.choose("integration_overlay:load", [
        path.join(example, "pattern_001.xy"),
      ]);
      await s.button("Add overlay files").click();
      await s.settle();
      await s.capture(
        "integration-overlays",
        "Integration, Overlay tab: the current pattern stored as an overlay and a second pattern file loaded, with scale, offset and waterfall controls.",
      );
      await s.button("Clear overlays").click();
      await s.settle();
      const confirm = s.page.getByRole("dialog");
      if (await confirm.count())
        await confirm.getByRole("button").last().click();
      await s.settle();
      await s.tab("Phase").click();
      for (const name of ["au_Anderson.jcpds", "pt.jcpds"]) {
        s.choose("integration_phase_files", path.join(example, name));
        await s.button("Add phase…").click();
        await s.settle();
      }
      await s.capture(
        "integration-phases",
        "Integration, Phase tab: gold and platinum JCPDS references loaded over the CeO2 example to show the phase table and reflection markers. They are not phases of this sample.",
      );
      await s.button("Export pattern figure").click();
      await s.settle(s.page, 800);
      await s.capture(
        "pattern-figure",
        "Pattern figure export dialog with the current pattern and phase references.",
      );
    });
  },
  async batch() {
    await session(async (s) => {
      await s.openCalibrated();
      await s.mode("Integration");
      s.choose("open_image", await scanFiles());
      const popup = s.context.waitForEvent("page", { timeout: 60000 });
      await s.button("Load image…").click();
      const batch = await popup;
      await batch.waitForLoadState();
      await s.settle(batch, 1500);
      await s.capture(
        "batch-window",
        "Batch window with nine detector images integrated into one series.",
        { target: batch },
      );
      await batch
        .getByRole("button", { name: "Dock batch below image", exact: true })
        .click();
      await s.settle(s.page, 1500);
      await s.capture(
        "batch-docked",
        "Batch docked below the detector image in Integration; the selected frame drives image and pattern.",
      );
    });
  },
  async map() {
    await session(async (s) => {
      await s.openCalibrated();
      await s.mode("Map");
      await s.capture("map-empty", "Map mode before a scan is loaded.");
      s.choose("map_load", await scanFiles());
      await s.button("Load images to build a map").click();
      await s.settle(s.page, 1500);
      await s.capture(
        "map-points",
        "Map mode with nine scan images: scan map, detector image, Points tab and the selected point's pattern.",
      );
      await s.tab("Layers").click();
      await s.capture(
        "map-layers",
        "Map mode, Layers tab: pattern windows and expressions that define the displayed map layer.",
      );
      await s.tab("Grid").click();
      await s.capture("map-grid", "Map mode, Grid tab: scan dimensions.");
    });
  },
  async scxrd() {
    const folder = path.join(root, "artifacts/scxrd-fixture");
    let frames;
    try {
      frames = (await readdir(folder))
        .filter((name) => name.endsWith(".tif"))
        .sort();
    } catch {
      console.warn(
        "Skipping scxrd: generate the synthetic scan first with\n  cargo run --locked --manifest-path backend/Cargo.toml --example scxrd_fixture -- artifacts/scxrd-fixture",
      );
      return;
    }
    const scxrdData = path.join(work, "rotation-scan");
    await mkdir(scxrdData, { recursive: true });
    for (const name of [...frames, "detector.poni"])
      await cp(path.join(folder, name), path.join(scxrdData, name));
    await session(async (s) => {
      const { page } = s;
      await s.open();
      await s.mode("Single Crystal XRD");
      await s.capture(
        "scxrd-start",
        "Single Crystal XRD before a rotation scan is loaded: stage tabs and the Frames setup.",
      );
      const panel = page.getByRole("complementary", {
        name: "Single-crystal workflow controls",
      });
      s.choose(
        "scxrd_load",
        frames.map((name) => path.join(scxrdData, name)),
      );
      await s.button("Load frames…", panel).click();
      await page.getByLabel("Rotation frame", { exact: true }).waitFor();
      await s.settle();
      await page
        .getByLabel("Single-crystal workflow", { exact: true })
        .selectOption("summation");
      await page.getByLabel("First exposure start").fill("-40");
      await page.getByLabel("Rotation step", { exact: false }).fill("0.5");
      await page.getByLabel("Exposure width").fill("0.5");
      await page
        .getByRole("checkbox", { name: /^I checked the frame order/ })
        .check();
      await s.button("Apply settings").click();
      await s.settle();
      s.choose("scxrd_file:calibration", path.join(scxrdData, "detector.poni"));
      await s.button("Load .poni…").click();
      await s.settle();
      await s.capture(
        "scxrd-frames",
        "Single Crystal XRD, Frames: a synthetic 161-frame rotation scan with declared acquisition and a loaded calibration (exploratory summation workflow).",
      );
      await s.tab("Peaks").click();
      await s.button("Run peaks").click();
      await page
        .getByRole("tab", { name: "Cell", exact: true, selected: true })
        .waitFor({ timeout: 180000 });
      await s.settle();
      await s.tab("Peaks").click();
      await s.capture(
        "scxrd-peaks",
        "Single Crystal XRD, Peaks: detected peaks linked into tracks on the synthetic scan.",
      );
      await s.tab("Cell").click();
      await s.button("Run cell").click();
      await s.button("Select cell 1").waitFor({ timeout: 180000 });
      await s.settle();
      await s.capture(
        "scxrd-cell",
        "Single Crystal XRD, Cell: candidate cells from blind indexing of the synthetic scan, waiting for a choice.",
      );
    });
  },
  async configurations() {
    await session(async (s) => {
      await s.openCalibrated();
      await s.button("Settings").click();
      await s.tab("Configurations").click();
      await s.page.getByLabel("Enable configurations", { exact: true }).check();
      await s.settle();
      await s.capture(
        "settings-configurations",
        "Settings, Configurations: configurations enabled, with the browsing rules for filename and folder numbers.",
      );
      await s.mode("Integration");
      await s.capture(
        "configuration-toolbar",
        "Integration with the configuration toolbar enabled above the workspace.",
      );
    });
  },
  async settings() {
    await session(async (s) => {
      await s.openCalibrated();
      await s.button("Settings").click();
      await s.settle();
      await s.capture(
        "settings-general",
        "Settings, General: interface text size, processing workers and updates.",
      );
      await s.tab("Integration").click();
      await s.capture(
        "settings-integration",
        "Settings, Integration: radial coordinate and bins, method, azimuth ranges, cake bins and corrections.",
      );
      await s.tab("Keyboard shortcuts").click();
      await s.capture(
        "settings-shortcuts",
        "Settings, Keyboard shortcuts: the built-in reference.",
      );
      await s.tab("Phase").click();
      await s.capture(
        "settings-phase",
        "Settings, Phase: DAC thermal pressure.",
      );
      await s.tab("Custom actions").click();
      await s.button("Add action").click();
      await s.settle();
      await s.page.getByLabel("Button name", { exact: true }).fill("Lookup");
      await s.page
        .getByLabel("Program or executable script", { exact: true })
        .fill("/usr/bin/python3");
      await s.page
        .getByRole("textbox", { name: /^Arguments/ })
        .fill(
          "/beamline/tools/lookup_motors.py\n--image={image_path}\n--frame={frame_index}",
        );
      await s.capture(
        "custom-action-form",
        "Settings, Custom actions: a new action with program, arguments, input placeholders and the sidebar preview. The script path is an example.",
      );
      await s.button("Save action").click();
      await s.settle();
      await s.capture(
        "custom-action-saved",
        "Settings, Custom actions after Save action: the action in the list and its button above Undo and Redo in the sidebar.",
      );
    });
  },
};

for (const name of sections) {
  if (!tasks[name]) {
    console.warn(`Section ${name} is not implemented yet`);
    continue;
  }
  console.log(`# ${name}`);
  await tasks[name]();
}
await rm(work, { recursive: true, force: true });

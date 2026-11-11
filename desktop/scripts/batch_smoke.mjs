import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium, webkit } from "playwright";
import { selectIntegrationDisplay } from "./integration_display.mjs";
import { nativeClient } from "./native_backend_client.mjs";
const root = fileURLToPath(new URL("../../", import.meta.url));
const engineName = process.argv.includes("--webkit") ? "webkit" : "chromium";
const artifacts = path.join(
  root,
  "desktop/artifacts/batch-window/rust",
  engineName,
);
await mkdir(artifacts, { recursive: true });
const temporary = await mkdtemp(path.join(tmpdir(), "dioptas-batch-window-"));
// Generate scaled real TIFFs using Rust, including all fixture preparation.
execFileSync(
  "cargo",
  [
    "run",
    "--quiet",
    "--locked",
    "--manifest-path",
    path.join(root, "desktop/backend/Cargo.toml"),
    "--example",
    "batch_window_fixture",
    "--",
    path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
    temporary,
  ],
  { cwd: root, stdio: "inherit" },
);
const paths = Array.from({ length: 6 }, (_, i) =>
  path.join(temporary, `series_${i + 1}.tif`),
);
const native = nativeClient();
let processed = false;
const logs = native.diagnostics,
  requests = [];
async function invoke(action, payload = {}) {
  if (action === "open_image" && payload.multiple && !payload.paths)
    payload = { ...payload, paths };
  if (action === "open_image" && payload.batch_mode === "save")
    payload = { ...payload, output_directory: temporary };
  if (action === "batch_load_data")
    payload = {
      ...payload,
      paths: processed ? [path.join(artifacts, "batch.h5")] : paths,
    };
  if (action === "integration_save_batch" && !payload.path)
    payload = { ...payload, path: path.join(artifacts, "batch.h5") };
  if (
    action === "integration_phase" &&
    payload.operation === "load" &&
    !payload.path
  )
    payload = {
      ...payload,
      path: path.join(root, "dioptas/tests/data/jcpds/au_version3.jcpds"),
    };
  if (action === "integration_phase_files" && !payload.paths)
    payload = {
      ...payload,
      paths: [path.join(root, "dioptas/tests/data/jcpds/au_version3.jcpds")],
    };
  requests.push(action);
  const reply = await native.invoke(action, payload);
  assert.equal(reply.ok, true, `${action}: ${reply.error}`);
  return native.browserResult(reply);
}
const engine = process.argv.includes("--webkit") ? webkit : chromium;
const browser = await engine.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1600, height: 1000 },
});
const page = await context.newPage();
const errors = [];
context.on("page", (p) => p.on("pageerror", (e) => errors.push(e.message)));
page.on("pageerror", (e) => errors.push(e.message));
let selectionGate = null,
  selectionStarted = null;
await page.exposeFunction("__dioptasInvoke", async (action, payload) => {
  if (action === "batch_select" && selectionGate) {
    selectionStarted?.();
    await selectionGate;
  }
  return invoke(action, payload);
});
await page.addInitScript(() => {
  window.pywebview = {
    api: {
      invoke: async (a, p) => {
        window.__pending = (window.__pending ?? 0) + 1;
        try {
          return await window.__dioptasInvoke(a, p);
        } finally {
          window.__pending--;
        }
      },
    },
  };
  window.addEventListener("message", (e) => {
    if (e.data?.message?.command === "batch_select")
      window.__lastBatchRequest = e.data.message.args.index;
  });
});
const ready = async () => {
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  await page.waitForFunction(
    () =>
      document.querySelector(".app") &&
      !document.querySelector(".spin") &&
      !window.__pending,
  );
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
};
const click = async (p, name) => {
  await p.getByRole("button", { name, exact: true }).click();
};
const selected = async (p, n) => {
  await p.waitForFunction((n) => {
    const panel = document.querySelector('[aria-label="Batch series"]');
    return (
      panel?.dataset.selectedFrame === String(n - 1) &&
      panel.getAttribute("aria-busy") === "false"
    );
  }, n);
  await ready();
  assert.equal((await invoke("state")).batch.selected, n - 1);
};
const readRange = (p) =>
  p
    .getByTestId("batch-heatmap")
    .evaluate((c) => [
      +c.dataset.viewXMin,
      +c.dataset.viewXMax,
      +c.dataset.viewYMin,
      +c.dataset.viewYMax,
    ]);
const sameRange = (a, b) =>
  a.forEach((x, i) => assert(Math.abs(x - b[i]) < 1e-5, `${a} vs ${b}`));
const checkBatchLayout = async (p) => {
  for (const name of [
    "Load raw/proc data",
    "Previous batch folder",
    "Next batch folder",
    "Save batch data",
  ]) {
    assert(
      await p.getByRole("button", { name, exact: true }).isVisible(),
      `${name} must stay visible`,
    );
    const button = await p
      .getByRole("button", { name, exact: true })
      .boundingBox();
    const header = await p.locator(".batch-series-toolbar").boundingBox();
    assert(
      button.x >= header.x - 1 &&
        button.x + button.width <= header.x + header.width + 1,
      `${name} overflows its toolbar`,
    );
  }
  const histogram = await p
    .locator(".batch-overview-image > .image-intensity")
    .boundingBox();
  const plot = await p.getByTestId("batch-heatmap").boundingBox();
  const view = await p.locator(".batch-2d-view").boundingBox();
  const image = await p.locator(".batch-overview-image").boundingBox();
  const optionsLocator = p.locator(".batch-2d-view > .batch-options");
  const options = (await optionsLocator.count())
    ? await optionsLocator.boundingBox()
    : null;
  assert(
    image.width >= view.width - (options?.width ?? 0) - 8,
    "Batch plot uses the available dock width; its color legend must not steal a column",
  );

  assert(
    histogram.x + histogram.width <= plot.x + 1,
    JSON.stringify({ histogram, plot }),
  );
  const bar = await p
    .locator(".batch-overview-image")
    .getByTestId("intensity-colour-bar")
    .boundingBox();
  const window = await p
    .locator(".batch-overview-image")
    .getByTestId("intensity-selected-window")
    .boundingBox();
  assert(bar.x + bar.width < window.x, JSON.stringify({ bar, window }));
  if (await p.locator(".batch-docked").count()) {
    assert.equal(
      await p
        .getByRole("group", { name: "Batch plot options", exact: true })
        .count(),
      0,
    );
  } else {
    const modes = await p
      .getByRole("group", { name: "Batch plot options", exact: true })
      .boundingBox();
    assert(modes.x >= plot.x + plot.width - 1);
  }
};
let child;
try {
  assert.equal((await native.invoke("__host__")).runtime, "rust");
  assert.equal((await invoke("example")).ok, true);
  assert.equal(
    (
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      })
    ).ok,
    true,
  );
  await page.goto("file://" + path.join(root, "dioptas/desktop/ui/index.html"));
  await ready();
  assert.equal(
    await page.getByRole("button", { name: "Batch", exact: true }).count(),
    0,
  );
  await click(page, "Integration");
  const batchButton = page.getByRole("button", {
    name: "Batch view…",
    exact: true,
  });
  assert.equal(await batchButton.getAttribute("aria-pressed"), "false");
  assert.equal(
    await page
      .getByRole("group", { name: "Integration image controls", exact: true })
      .getByRole("button", { name: "Batch view…", exact: true })
      .count(),
    0,
  );
  const fileInfo = page.getByRole("button", { name: "File Info", exact: true });
  assert.equal(await fileInfo.getAttribute("aria-expanded"), "false");
  await fileInfo.click();
  // Qt's Image-tab modes share the same chooser; only Integrate opens Batch.
  for (const mode of ["add", "average", "save"]) {
    await page
      .getByRole("combobox", { name: "Batch mode", exact: true })
      .selectOption(mode);
    await ready();
    await click(page, "Load image…");
    if (mode === "save")
      await page
        .getByRole("status")
        .filter({ hasText: "Saved 6 batch files" })
        .waitFor();
    else
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Image filename"]')?.value ===
          "series_1.tif",
      );
    await ready();
    if (mode === "save")
      assert.equal(
        (await readdir(temporary)).filter((name) =>
          /^batch_series_\d+\.tiff$/.test(name),
        ).length,
        6,
      );
    assert.equal(context.pages().length, 1);
    assert.equal((await invoke("state")).batch, null);
  }
  await page
    .getByRole("combobox", { name: "Batch mode", exact: true })
    .selectOption("integrate");
  await ready();
  assert.equal(await fileInfo.getAttribute("aria-expanded"), "true");
  await fileInfo.click();
  const opened = context.waitForEvent("page");
  await click(page, "Load image…");
  child = await opened;
  await child.waitForLoadState();
  await selected(child, 1);
  // Cake is generated on demand in Rust; make it visible before checking it.
  await selectIntegrationDisplay(page, "cake");
  await ready();
  assert.equal(await batchButton.getAttribute("aria-pressed"), "true");
  assert.equal(
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
  // Hold a real frame load: controls/canvases stay mounted and rapid clicks queue.
  let releaseSelection;
  selectionGate = new Promise((resolve) => (releaseSelection = resolve));
  const selectionEntered = new Promise(
    (resolve) => (selectionStarted = resolve),
  );
  await click(child, "Next batch frame");
  await selectionEntered;
  assert.equal(
    await page
      .getByRole("button", { name: "Load image…", exact: true })
      .isDisabled(),
    false,
  );
  assert.equal(await page.locator(".spin").count(), 0);
  assert.equal(await page.getByTestId("detector-canvas").count(), 1);
  assert.equal(
    await child
      .getByRole("button", { name: "Next batch frame", exact: true })
      .isDisabled(),
    false,
  );
  await child.getByTestId("batch-heatmap").press("End");
  await page.waitForFunction(() => window.__lastBatchRequest === 5);
  releaseSelection();
  selectionGate = null;
  await selected(child, 6);
  await child.getByTestId("batch-heatmap").press("Home");
  await selected(child, 1);
  assert.equal(await child.locator(".intensity-histogram").count(), 1);
  assert.equal(await child.getByTestId("detector-canvas").count(), 0);
  await click(child, "Next batch frame");
  await selected(child, 2);
  let state = await invoke("state");
  assert.equal(state.state.imageName, "series_2.tif");
  assert(state.cake && state.pattern);
  assert.equal(await page.getByTestId("cake-canvas").count(), 1);
  await selectIntegrationDisplay(page, "cake");
  assert(await page.getByTestId("cake-canvas").isVisible());
  const canvas = child.getByTestId("batch-heatmap"),
    b = await canvas.boundingBox();
  await child.waitForFunction(() => {
    const c = document.querySelector('[data-testid="batch-heatmap"]'),
      box = c.getBoundingClientRect(),
      dpr = c.width / box.width;
    const brightness = (fraction) => {
      const data = c
        .getContext("2d")
        .getImageData(
          Math.round(80 * dpr),
          Math.round((12 + (box.height - 58) * fraction) * dpr),
          Math.floor((box.width - 110) * dpr),
          1,
        ).data;
      let sum = 0;
      for (let i = 0; i < data.length; i += 4) sum += data[i];
      return sum;
    };
    // Last frame is six times brighter and must be at the top.
    return brightness(0.5 / 6) > brightness(5.5 / 6) * 1.1;
  });
  // Acquisition order runs upwards: bottom displays frame 1, top the last.
  await child.mouse.click(b.x + 100, b.y + 12 + ((b.height - 58) * 5.5) / 6);
  await selected(child, 1);
  await canvas.press("ArrowUp");
  await selected(child, 2);
  await canvas.press("ArrowDown");
  await selected(child, 1);
  await child.mouse.click(b.x + 100, b.y + 12 + ((b.height - 58) * 0.5) / 6);
  await selected(child, 6);
  await child.mouse.click(b.x + 100, b.y + 12 + ((b.height - 58) * 1.5) / 6);
  await selected(child, 5);
  state = await invoke("state");
  assert.equal(state.state.imageName, "series_5.tif");
  assert(state.cake);
  assert(state.linked);
  await child.waitForFunction(() =>
    Number.isFinite(
      Number(
        document.querySelector('[data-testid="batch-heatmap"]').dataset
          .linkedPosition,
      ),
    ),
  );
  // Shared physical click state must cross the companion boundary both ways.
  const firstBatchSelection = state.linked;
  const firstBatchRaster = state.batch.raster.bufferId;
  const waitPatternMarker = (radial) =>
    page.waitForFunction(
      (value) =>
        Math.abs(
          Number(
            document.querySelector('[data-testid="pattern-canvas"]').dataset
              .linkedPosition,
          ) - value,
        ) < 1e-8,
      radial,
    );
  const waitBatchMarker = (radial) =>
    child.waitForFunction(
      (value) =>
        Math.abs(
          Number(
            document.querySelector('[data-testid="batch-heatmap"]').dataset
              .linkedPosition,
          ) - value,
        ) < 1e-8,
      radial,
    );
  const sharedClick = async () => {
    const fields = await page
      .getByTestId("click-readout")
      .locator("[data-field]")
      .allTextContents();
    assert.ok(fields.length > 0);
    await child.getByTestId("batch-click-readout").waitFor();
    await child.waitForFunction(
      (expected) =>
        JSON.stringify(
          [
            ...document.querySelectorAll(
              '[data-testid="batch-click-readout"] [data-field]',
            ),
          ].map((el) => el.textContent),
        ) === JSON.stringify(expected),
      fields,
    );
    return fields;
  };
  await waitPatternMarker(firstBatchSelection.radial);
  await waitBatchMarker(firstBatchSelection.radial);
  assert.equal(
    await page.getByTestId("click-readout").getAttribute("data-plot"),
    "batch",
  );
  const batchClickFields = await sharedClick();
  const patternPlot = page.getByTestId("pattern-canvas");
  const patternPoint = await patternPlot.evaluate((el) => ({
    x: +el.dataset.plotLeft + +el.dataset.plotWidth * 0.45,
    y: +el.dataset.plotTop + +el.dataset.plotHeight * 0.5,
  }));
  await patternPlot.click({ position: patternPoint });
  await ready();
  const patternSelected = await invoke("state");
  assert.equal(
    patternSelected.batch.selected,
    4,
    "Pattern click changed the selected Batch frame",
  );
  assert.equal(
    patternSelected.batch.raster.bufferId,
    firstBatchRaster,
    "Pattern click replaced the Batch intensity matrix",
  );
  assert.ok(
    Math.abs(patternSelected.linked.radial - firstBatchSelection.radial) > 1e-3,
  );
  await waitPatternMarker(patternSelected.linked.radial);
  await waitBatchMarker(patternSelected.linked.radial);
  assert.equal(
    await page.getByTestId("click-readout").getAttribute("data-plot"),
    "pattern",
  );
  const patternClickFields = await sharedClick();
  assert.notDeepEqual(patternClickFields, batchClickFields);
  const nextBatchPoint = await canvas.evaluate((el) => ({
    x: +el.dataset.plotLeft + +el.dataset.plotWidth * 0.62,
    y:
      +el.dataset.plotTop +
      ((+el.dataset.viewYMax - 4.5) /
        (+el.dataset.viewYMax - +el.dataset.viewYMin)) *
        +el.dataset.plotHeight,
  }));
  await canvas.click({ position: nextBatchPoint });
  await selected(child, 5);
  const secondBatchSelection = await invoke("state");
  assert.ok(
    Math.abs(
      secondBatchSelection.linked.radial - patternSelected.linked.radial,
    ) > 1e-3,
  );
  await waitPatternMarker(secondBatchSelection.linked.radial);
  await waitBatchMarker(secondBatchSelection.linked.radial);
  assert.equal(
    await page.getByTestId("click-readout").getAttribute("data-plot"),
    "batch",
  );
  assert.notDeepEqual(await sharedClick(), patternClickFields);
  await child.mouse.move(b.x + 140, b.y + 80);
  await child.locator('.batch-reading [data-field="I"]').waitFor();
  assert(await child.locator('.batch-reading [data-field="2θ"]').isVisible());
  assert(
    await child.locator('.batch-reading [data-field="Frame"]').isVisible(),
  );
  assert.equal(
    (
      await invoke("integration_phase", {
        operation: "load",
        path: path.join(root, "dioptas/tests/data/jcpds/au_version3.jcpds"),
      })
    ).ok,
    true,
  );
  // Refresh the main command state through a real UI command, as in normal use.
  await click(child, "Next batch frame");
  await selected(child, 6);
  await click(child, "Previous batch frame");
  await selected(child, 5);
  await click(child, "Show batch phases");
  await child.waitForFunction(
    () =>
      Number(
        document.querySelector('[data-testid="batch-heatmap"]').dataset
          .phaseLineCount,
      ) > 0,
  );
  await child.mouse.move(b.x + 140, b.y + 80);
  await child.locator('.batch-reading [data-field="I"]').waitFor();
  await child.screenshot({ path: path.join(artifacts, "batch-phases.png") });
  await click(child, "Show batch phases");
  // Both zoom modes share the blue selection, and a slice keeps all frame rows.
  const dragZoom = async (mode) => {
    await click(
      child,
      `Batch ${mode === "rectangle" ? "rectangle" : "X-range"} zoom`,
    );
    const before = await readRange(child);
    const x = b.x + 120,
      y = b.y + 50,
      endY = mode === "rectangle" ? y + 90 : y + 1;
    await child.mouse.move(x, y);
    await child.mouse.down();
    await child.mouse.move(x + 140, endY, { steps: 5 });
    // Sample the selection edge, away from the orange selected-frame marker.
    await child.waitForFunction(() => {
      const c = document.querySelector('[data-testid="batch-heatmap"]'),
        dpr = c.width / c.getBoundingClientRect().width,
        data = c
          .getContext("2d")
          .getImageData(
            Math.floor(118 * dpr),
            Math.floor(60 * dpr),
            Math.ceil(5 * dpr),
            Math.ceil(30 * dpr),
          ).data;
      for (let i = 0; i < data.length; i += 4)
        if (data[i + 2] > data[i] + 40 && data[i + 1] > data[i] + 30)
          return true;
      return false;
    });
    await child.mouse.up();
    const after = await readRange(child);
    assert(after[1] - after[0] < before[1] - before[0]);
    if (mode === "rectangle")
      assert(after[3] - after[2] < before[3] - before[2]);
    else sameRange(after.slice(2), before.slice(2));
    await selected(child, 5); // A zoom drag must not select a different frame.
    await canvas.press("f");
    sameRange(await readRange(child), before);
  };
  await dragZoom("rectangle");
  await dragZoom("horizontal");
  // Cake and Batch both accept zooms beginning in the canvas axis margins.
  for (const mode of ["rectangle", "horizontal"]) {
    await click(
      child,
      `Batch ${mode === "rectangle" ? "rectangle" : "X-range"} zoom`,
    );
    const before = await readRange(child);
    const bounds = await canvas.evaluate((c) => ({
      left: +c.dataset.plotLeft,
      top: +c.dataset.plotTop,
      width: +c.dataset.plotWidth,
      height: +c.dataset.plotHeight,
    }));
    // A click, or a drag remaining in the left gutter, must stay inert.
    await child.mouse.click(b.x + 3, b.y + bounds.top + 30);
    await child.mouse.move(b.x + 3, b.y + bounds.top + 20);
    await child.mouse.down();
    await child.mouse.move(b.x + 3, b.y + bounds.top + 70, { steps: 4 });
    await child.mouse.up();
    sameRange(await readRange(child), before);
    await child.mouse.move(b.x + 3, b.y + 3);
    await child.mouse.down();
    await child.mouse.move(
      b.x + bounds.left + bounds.width / 2,
      b.y + bounds.top + bounds.height / 2,
      { steps: 5 },
    );
    await child.mouse.up();
    const after = await readRange(child);
    assert(after[1] - after[0] < before[1] - before[0]);
    if (mode === "rectangle")
      assert(after[3] - after[2] < before[3] - before[2]);
    else sameRange(after.slice(2), before.slice(2));
    await selected(child, 5);
    await canvas.press("f");
    sameRange(await readRange(child), before);
  }
  // Files/2D/Options grouping and normalization directly beside the plot axis.
  await child.getByRole("tab", { name: "Files", exact: true }).click();
  assert.equal(
    await child
      .getByRole("columnheader", { name: "Raw file name", exact: true })
      .count(),
    1,
  );
  assert.equal(
    await child
      .getByRole("columnheader", { name: "N images", exact: true })
      .count(),
    1,
  );
  await click(child, "Select batch file 3");
  await selected(child, 3);
  await child.getByRole("tab", { name: "2D", exact: true }).click();
  assert.equal(await canvas.getAttribute("data-zoom-mode"), "horizontal");
  await child.getByRole("button", { name: "Options", exact: true }).click();
  assert(
    await child
      .getByRole("button", { name: "Apply normalization region", exact: true })
      .isDisabled(),
  );
  const maximumAngle = child.getByLabel("Normalization maximum 2θ", {
    exact: true,
  });
  await maximumAngle.fill("-1");
  const errorId = await maximumAngle.getAttribute("aria-describedby");
  assert(errorId);
  assert((await child.locator(`[id="${errorId}"]`).innerText()).includes("2θ"));
  assert(
    await child
      .getByRole("button", { name: "Apply normalization region", exact: true })
      .isDisabled(),
  );
  await child.getByLabel("Normalization minimum 2θ", { exact: true }).fill("0");
  await child
    .getByLabel("Normalization maximum 2θ", { exact: true })
    .fill("180");
  await click(child, "Apply normalization region");
  await child.waitForTimeout(100);
  await ready();
  await child.getByRole("tab", { name: "2D", exact: true }).click();
  await click(child, "Normalize batch");
  await child.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Normalize batch"]')
        ?.getAttribute("aria-pressed") === "true",
  );
  assert.equal((await invoke("state")).batch.normalized, true);
  const normalizedBatch = (await invoke("state")).batch;
  assert.deepEqual(normalizedBatch.normalizationRange, [
    0,
    normalizedBatch.x.length,
  ]);
  assert.equal((await invoke("state")).batch.normalizationReference, 0);
  await click(child, "Normalize batch");
  await child.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Normalize batch"]')
        ?.getAttribute("aria-pressed") === "false",
  );
  // Unit/scale buttons keep stored arrays intact and use the recorded wavelength.
  await click(child, "Batch unit Q");
  await child.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Batch unit Q"]')
        ?.getAttribute("aria-pressed") === "true",
  );
  assert.equal((await invoke("state")).pattern.unit, "q_A^-1");
  await ready();
  await child.getByRole("button", { name: "Options", exact: true }).click();
  await child
    .getByLabel("Normalization minimum Q", { exact: true })
    .fill("0.5");
  await child
    .getByLabel("Normalization maximum Q", { exact: true })
    .fill("1.5");
  await click(child, "Apply normalization region");
  // Companion mutations cross postMessage before entering the main queue.
  // Wait for the real processor result rather than treating an idle main view
  // before message delivery as command completion.
  const qBatch = (await invoke("state")).batch;
  assert.equal(qBatch.unit, "q_A^-1");
  const included = qBatch.x.flatMap((x, i) =>
    x >= 0.5 && x <= 1.5 ? [i] : [],
  );
  assert.ok(included.length > 1, "Q region must contain stored samples");
  const expectedBins = [included[0], included.at(-1) + 1];
  const applyDeadline = Date.now() + 10000;
  while (
    JSON.stringify((await invoke("state")).batch.normalizationRange) !==
    JSON.stringify(expectedBins)
  ) {
    assert(
      Date.now() < applyDeadline,
      "Q normalization settings reach the processor as inclusive stored bins",
    );
    await child.waitForTimeout(30);
  }
  await ready();
  assert.deepEqual(
    (await invoke("state")).batch.normalizationRange,
    expectedBins,
  );
  await child.screenshot({
    path: path.join(artifacts, "batch-normalization-q.png"),
  });
  await child.getByRole("tab", { name: "2D", exact: true }).click();
  await click(child, "Batch unit d");
  await child.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Batch unit d"]')
        ?.getAttribute("aria-pressed") === "true",
  );
  await ready();
  await child.getByRole("button", { name: "Options", exact: true }).click();
  const minimumD = Number(
    await child
      .getByLabel("Normalization minimum d", { exact: true })
      .inputValue(),
  );
  const maximumD = Number(
    await child
      .getByLabel("Normalization maximum d", { exact: true })
      .inputValue(),
  );
  assert(Math.abs(minimumD - (2 * Math.PI) / qBatch.x[included.at(-1)]) < 1e-9);
  assert(Math.abs(maximumD - (2 * Math.PI) / qBatch.x[included[0]]) < 1e-9);
  await child.getByRole("tab", { name: "2D", exact: true }).click();
  await click(child, "Batch unit 2θ");
  await child.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Batch unit 2θ"]')
        ?.getAttribute("aria-pressed") === "true",
  );
  const lower = child.getByRole("slider", {
    name: "Batch lower intensity handle",
    exact: true,
  });
  const upper = child.getByRole("slider", {
    name: "Batch upper intensity handle",
    exact: true,
  });
  const lowBefore = Number(await lower.getAttribute("aria-valuenow"));
  const highBefore = Number(await upper.getAttribute("aria-valuenow"));
  const handleBox = await lower.boundingBox();
  await child.mouse.move(
    handleBox.x + handleBox.width / 2,
    handleBox.y + handleBox.height / 2,
  );
  await child.mouse.down();
  await child.mouse.move(
    handleBox.x + handleBox.width / 2,
    handleBox.y + handleBox.height / 2 - 15,
  );
  await child.mouse.up();
  assert(Number(await lower.getAttribute("aria-valuenow")) > lowBefore);
  assert.equal(Number(await upper.getAttribute("aria-valuenow")), highBefore);
  await click(child, "Batch auto intensity");
  await checkBatchLayout(child);
  await click(child, "Square root batch intensity");
  assert.equal(
    await child
      .getByRole("button", { name: "Square root batch intensity", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
  await click(child, "Square root batch intensity");
  assert.equal(
    await child
      .getByRole("button", { name: "Square root batch intensity", exact: true })
      .getAttribute("aria-pressed"),
    "false",
  );
  await child.getByRole("tab", { name: "Files", exact: true }).click();
  await child.getByLabel("Batch frame step", { exact: true }).fill("2");
  await ready();
  await click(child, "Integrate");
  await child.waitForFunction(() =>
    document
      .querySelector(".batch-frame-number")
      ?.textContent.includes("3/6 loaded"),
  );
  await selected(child, 1);
  assert.equal((await invoke("state")).batch.entries.length, 3);
  await click(child, "Save batch data");
  await child
    .getByRole("button", { name: "Choose file…", exact: true })
    .click();
  await child.waitForTimeout(200);
  await ready();
  // Source contrast and overview zoom survive docking across webviews.
  await click(child, "Batch histogram settings");
  await child.getByLabel("Batch minimum intensity", { exact: true }).fill("10");
  await child
    .getByLabel("Batch minimum intensity", { exact: true })
    .press("Enter");
  await click(child, "Close batch display settings");
  const wheel = await canvas.evaluate((c) => {
    const b = c.getBoundingClientRect(),
      e = new WheelEvent("wheel", {
        deltaY: -140,
        clientX: b.x + 120,
        clientY: b.y + 120,
        bubbles: true,
        cancelable: true,
      });
    c.dispatchEvent(e);
    return e.defaultPrevented;
  });
  assert.equal(wheel, true);
  await child.waitForTimeout(80);
  const range = await readRange(child);
  const display = await child.evaluate(() =>
    JSON.parse(localStorage.getItem("dioptas-batch:display")),
  );
  assert.equal(display.limits[0], 10);
  await child.screenshot({ path: path.join(artifacts, "batch-window.png") });
  {
    const closing = child.waitForEvent("close");
    await click(child, "Dock batch below image");
    await closing;
  }
  child = null;
  const dock = page.locator(".batch-dock");
  await dock.waitFor();
  await selected(page, 1);
  assert.equal(
    await dock.locator(".image-intensity").getAttribute("data-orientation"),
    "vertical",
  );
  assert.equal(
    await dock.getByLabel("Batch start frame", { exact: true }).isVisible(),
    false,
  );
  assert.equal(
    await dock
      .getByRole("button", { name: "Normalize batch", exact: true })
      .isVisible(),
    true,
  );
  sameRange(await readRange(page), range);
  // Phase edits must update an already docked batch without a snapshot reload.
  const snapshotReads = requests.filter((a) => a === "batch_snapshot").length;
  const phaseToggle = dock.getByRole("button", {
    name: "Show batch phases",
    exact: true,
  });
  await page.getByRole("tab", { name: "Phase", exact: true }).click();
  await click(page, "Removes all phases");
  await ready();
  assert(await phaseToggle.isDisabled());
  await click(page, "Add phase…");
  await ready();
  assert(await phaseToggle.isEnabled());
  await phaseToggle.click();
  const phaseCount = () =>
    dock
      .getByTestId("batch-heatmap")
      .getAttribute("data-phase-line-count")
      .then(Number);
  assert((await phaseCount()) > 0);
  await page.getByLabel("Show phase 1", { exact: true }).click();
  await ready();
  assert(await phaseToggle.isDisabled());
  assert.equal(await phaseCount(), 0);
  await page.getByLabel("Show phase 1", { exact: true }).click();
  await ready();
  assert(await phaseToggle.isEnabled());
  assert((await phaseCount()) > 0);
  sameRange(await readRange(page), range);
  await selected(page, 1);
  assert.equal(
    requests.filter((a) => a === "batch_snapshot").length,
    snapshotReads,
  );
  await phaseToggle.click();
  await page.getByRole("tab", { name: "Image", exact: true }).click();
  await dock.getByRole("button", { name: "Options", exact: true }).click();
  assert(
    await dock.getByLabel("Batch start frame", { exact: true }).isVisible(),
  );
  assert(
    await dock
      .getByLabel("Normalization minimum 2θ", { exact: true })
      .isVisible(),
  );
  await dock.getByLabel("Batch frame step", { exact: true }).fill("2");
  await dock.getByRole("tab", { name: "2D", exact: true }).click();
  await checkBatchLayout(page);
  await page
    .getByRole("button", { name: "Pattern unit Q", exact: true })
    .click();
  await ready();
  assert.equal((await invoke("state")).pattern.unit, "q_A^-1");
  assert.equal(
    await dock.getByTestId("batch-heatmap").getAttribute("data-unit"),
    "q_A^-1",
  );
  await click(page, "Logarithmic pattern intensity");
  assert.equal(
    await dock
      .getByTestId("batch-heatmap")
      .getAttribute("data-intensity-scale"),
    "log",
  );
  await click(page, "Square root pattern intensity");
  assert.equal(
    await dock
      .getByTestId("batch-heatmap")
      .getAttribute("data-intensity-scale"),
    "sqrt",
  );
  await click(page, "Square root pattern intensity");
  assert.equal(
    await dock
      .getByTestId("batch-heatmap")
      .getAttribute("data-intensity-scale"),
    "linear",
  );
  assert.equal(
    await dock
      .getByRole("tab", { name: "2D", exact: true })
      .getAttribute("aria-selected"),
    "true",
  );
  await page
    .getByRole("button", { name: "Pattern unit 2θ", exact: true })
    .click();
  await ready();
  await dock.getByRole("tab", { name: "2D", exact: true }).click();
  sameRange(await readRange(page), range);
  await dock.getByRole("button", { name: "Options", exact: true }).click();
  assert.equal(
    await dock.getByLabel("Batch frame step", { exact: true }).inputValue(),
    "2",
  );
  await dock.getByLabel("Batch frame step", { exact: true }).fill("1");
  await dock.getByRole("tab", { name: "2D", exact: true }).click();
  assert.equal(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem("dioptas-batch:display")).limits[0],
    ),
    10,
  );
  const image = await page.locator(".cake-panel").boundingBox(),
    dockBox = await dock.boundingBox(),
    controls = await page.locator(".integration-controls").boundingBox(),
    pattern = await page.locator(".pattern-panel").boundingBox();
  assert(dockBox.y >= image.y + image.height - 1);
  assert(dockBox.x < controls.x && dockBox.x + dockBox.width <= controls.x);
  assert(pattern.x >= dockBox.x + dockBox.width);
  assert.equal(
    await dock.getByLabel("Batch frame slider", { exact: true }).count(),
    0,
  );
  assert.equal(await dock.locator(".batch-navigation-row").count(), 0);
  assert.equal(
    await dock.getByTestId("batch-heatmap").getAttribute("data-zoom-mode"),
    "horizontal",
  );
  await dock.getByTestId("batch-heatmap").press("ArrowUp");
  await selected(page, 2);
  assert.equal((await invoke("state")).state.imageName, "series_3.tif");
  assert((await invoke("state")).cake);
  const divider = page.getByRole("separator", {
    name: "Image and batch divider",
    exact: true,
  });
  await divider.focus();
  await divider.press("ArrowUp");
  assert((await dock.boundingBox()).height > dockBox.height);
  const beforeDrag = await dock.boundingBox();
  const beforeImage = await page.locator(".cake-panel").boundingBox();
  const beforePlot = await dock.getByTestId("batch-heatmap").boundingBox();
  const handle = await divider.boundingBox();
  await page.mouse.move(
    handle.x + handle.width / 2,
    handle.y + handle.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    handle.x + handle.width / 2,
    handle.y + handle.height / 2 - 50,
  );
  await page.mouse.up();
  await page.waitForTimeout(100);
  assert((await dock.boundingBox()).height > beforeDrag.height + 40);
  assert(
    (await page.locator(".cake-panel").boundingBox()).height <
      beforeImage.height - 40,
  );
  assert(
    (await dock.getByTestId("batch-heatmap").boundingBox()).height >
      beforePlot.height + 40,
  );
  await divider.dblclick();
  await click(page, "Collapse batch overview");
  assert((await dock.boundingBox()).height < 50);
  await click(page, "Expand batch overview");
  await page.waitForFunction(() => {
    const c = document.querySelector('[data-testid="batch-heatmap"]');
    return c?.width > 200 && c?.height > 100;
  });
  await page.waitForTimeout(80);
  await page.screenshot({ path: path.join(artifacts, "batch-docked.png") });
  for (const large of [false, true]) {
    await page.setViewportSize({ width: 1000, height: 700 });
    await page
      .locator(".app")
      .evaluate(
        (app, big) =>
          app.setAttribute("data-text-size", big ? "large" : "normal"),
        large,
      );
    await page.waitForTimeout(100);
    const boxes = await page
      .locator(
        ".integration-left-pane,.batch-dock,.integration-controls,.pattern-panel",
      )
      .evaluateAll((nodes) =>
        nodes.map((n) => {
          const b = n.getBoundingClientRect();
          return {
            x: b.x,
            y: b.y,
            width: b.width,
            height: b.height,
            right: b.right,
            bottom: b.bottom,
          };
        }),
      );
    assert(
      boxes.every(
        (b) =>
          b.width > 100 &&
          b.height > 90 &&
          b.x >= 0 &&
          b.right <= 1000 &&
          b.bottom <= 700,
      ),
      JSON.stringify(boxes),
    );
    await dock.getByRole("button", { name: "Options", exact: true }).click();
    const optionBounds = await dock
      .locator(".batch-settings-content")
      .boundingBox();
    for (const label of [
      "Batch start frame",
      "Batch stop frame",
      "Batch frame step",
    ]) {
      const input = dock.getByLabel(label, { exact: true });
      await input.scrollIntoViewIfNeeded();
      const field = await input.boundingBox();
      assert(
        field.x >= optionBounds.x &&
          field.x + field.width <= optionBounds.x + optionBounds.width,
      );
      assert(
        field.y >= optionBounds.y &&
          field.y + field.height <= optionBounds.y + optionBounds.height,
      );
    }
    if (large)
      await page.screenshot({
        path: path.join(artifacts, "batch-docked-options.png"),
      });
    await dock.getByRole("tab", { name: "2D", exact: true }).click();
  }
  await page.screenshot({
    path: path.join(artifacts, "batch-docked-small.png"),
  });
  const compactPlot = await dock.getByTestId("batch-heatmap").boundingBox();
  assert(compactPlot.height - 58 >= 150, JSON.stringify(compactPlot));
  await checkBatchLayout(page);
  const dockStyle = await dock
    .locator(".batch-series-panel")
    .evaluate((e) => [
      getComputedStyle(e).borderWidth,
      getComputedStyle(e).borderRadius,
    ]);
  assert.deepEqual(dockStyle, ["0px", "0px"]);
  const pathBounds = await dock
    .locator(".batch-folder-label")
    .evaluate((e) => ({
      box: e.getBoundingClientRect().right,
      text: e.firstElementChild.getBoundingClientRect().right,
    }));
  assert(
    Math.abs(pathBounds.box - pathBounds.text) < 1,
    JSON.stringify(pathBounds),
  );
  // Compact layouts switch Image/Batch tabs and omit their vertical splitter.
  // Restore the wide layout before exercising the shared divider and image tools.
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page
    .locator(".app")
    .evaluate((app) => app.setAttribute("data-text-size", "normal"));
  await ready();
  const grip = (e) => {
    const s = getComputedStyle(e);
    return [s.width, s.height, s.backgroundColor, s.opacity];
  };
  await divider.evaluate((e) => e.blur());
  await page.mouse.move(0, 0);
  assert.deepEqual(
    await divider.locator("span").evaluate(grip),
    await page
      .getByRole("separator", {
        name: "Controls and pattern divider",
        exact: true,
      })
      .locator("span")
      .evaluate(grip),
  );
  await selectIntegrationDisplay(page, "image");
  assert.equal(
    await page.locator(".integration-cake-shift").boundingBox(),
    null,
  );
  await page.screenshot({
    path: path.join(artifacts, "batch-docked-detector.png"),
  });
  await selectIntegrationDisplay(page, "cake");
  await click(page, "Hide batch view");
  assert.equal(await dock.count(), 0);
  assert.equal(await batchButton.getAttribute("aria-pressed"), "false");
  assert.equal((await invoke("state")).batch.entries.length, 3);
  await click(page, "Batch view…");
  await dock.waitFor();
  const retainedFrame = (await invoke("state")).batch.selected;
  await click(page, "Batch view…");
  assert.equal(await dock.count(), 0);
  assert.equal(await batchButton.getAttribute("aria-pressed"), "false");
  assert.equal(
    await page.evaluate(() => localStorage.getItem("dioptas-batch:open")),
    "false",
  );
  assert.equal((await invoke("state")).batch.selected, retainedFrame);
  await click(page, "Batch view…");
  await dock.waitFor();
  const reopened = context.waitForEvent("page");
  await click(page, "Detach batch");
  child = await reopened;
  await child.waitForLoadState();
  await selected(child, 2);
  assert.equal(await dock.count(), 0);
  sameRange(await readRange(child), range);
  await click(page, "Batch view…");
  assert.equal(context.pages().length, 2);
  assert(!child.isClosed());
  await selected(child, 2);
  sameRange(await readRange(child), range);
  await child.close();
  child = null;
  await page.waitForTimeout(500);
  const again = context.waitForEvent("page");
  await click(page, "Batch view…");
  child = await again;
  await child.waitForLoadState();
  await selected(child, 2);
  // A fresh frontend restores layout without reopening scientific files itself.
  {
    const closing = child.waitForEvent("close");
    await click(child, "Dock batch below image");
    await closing;
  }
  child = null;
  await page.setViewportSize({ width: 1600, height: 1000 });
  const imageDivider = page.getByRole("separator", {
    name: "Image and analysis divider",
    exact: true,
  });
  const controlsDivider = page.getByRole("separator", {
    name: "Controls and pattern divider",
    exact: true,
  });
  await imageDivider.focus();
  await imageDivider.press("Home");
  await imageDivider.press("ArrowRight");
  await imageDivider.press("ArrowRight");
  await controlsDivider.focus();
  await controlsDivider.press("Home");
  await controlsDivider.press("ArrowDown");
  await controlsDivider.press("ArrowDown");
  await controlsDivider.press("ArrowDown");
  await divider.dblclick();
  await divider.focus();
  for (let i = 0; i < 3; i++) await divider.press("ArrowUp");
  await click(page, "Collapse batch overview");
  await page.reload();
  await ready();
  await dock.waitFor();
  assert.equal(await imageDivider.getAttribute("aria-valuenow"), "54");
  assert.equal(await controlsDivider.getAttribute("aria-valuenow"), "44");
  assert(
    await dock.evaluate((e) => e.classList.contains("batch-dock-collapsed")),
  );
  await click(page, "Expand batch overview");
  assert(Math.abs((await dock.boundingBox()).height - 380) < 2);
  await divider.focus();
  for (let i = 0; i < 10; i++) await divider.press("ArrowUp");
  const preferred = await page.evaluate(() =>
    localStorage.getItem("dioptas-batch:dock-height"),
  );
  await page.setViewportSize({ width: 1000, height: 700 });
  await page.waitForTimeout(100);
  assert((await dock.boundingBox()).height < Number(preferred));
  assert.equal(
    await page.evaluate(() =>
      localStorage.getItem("dioptas-batch:dock-height"),
    ),
    preferred,
  );
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.waitForTimeout(100);
  assert(Math.abs((await dock.boundingBox()).height - Number(preferred)) < 2);
  await click(page, "Hide batch view");
  await page.reload();
  await ready();
  assert.equal(await dock.count(), 0);
  await click(page, "Integration");
  await click(page, "Batch view…");
  await dock.waitFor();
  let restoredPopup = context.waitForEvent("page");
  await click(page, "Detach batch");
  child = await restoredPopup;
  await selected(child, 2);
  restoredPopup = context.waitForEvent("page");
  await page.reload();
  child = await restoredPopup;
  await child.waitForLoadState();
  await selected(child, 2);
  assert.equal(
    await page.evaluate(() => localStorage.getItem("dioptas-batch:open")),
    "true",
  );
  await child.close();
  child = null;
  await page.waitForFunction(
    () => localStorage.getItem("dioptas-batch:open") === "false",
  );
  await page.reload();
  await ready();
  assert.equal(context.pages().length, 1);
  await click(page, "Integration");
  restoredPopup = context.waitForEvent("page");
  await click(page, "Batch view…");
  child = await restoredPopup;
  await selected(child, 2);
  // A stored-only series must clear stale detector/cake pixels in Integration.
  for (const file of paths) await rm(file);
  processed = true;
  await click(child, "Load raw/proc data");
  await selected(child, 1);
  state = await invoke("state");
  assert.equal(state.state.hasImage, false);
  assert.equal(state.cake, null);
  assert.equal(await page.getByTestId("detector-canvas").count(), 0);
  assert.equal(await page.getByTestId("cake-canvas").count(), 0);
  assert.equal(await page.getByTestId("pattern-canvas").count(), 1);
  await child.close();
  child = null;
  await page.waitForFunction(
    () => localStorage.getItem("dioptas-batch:open") === "false",
  );
  await page.evaluate(() => {
    localStorage.setItem("dioptas-layout:image-share", "NaN");
    localStorage.setItem("dioptas-layout:controls-share", "Infinity");
    localStorage.setItem("dioptas-batch:dock-height", "invalid");
    localStorage.setItem("dioptas-batch:collapsed", "invalid");
    localStorage.setItem("dioptas-batch:docked", "true");
  });
  await page.reload();
  await ready();
  await click(page, "Integration");
  assert.equal(await imageDivider.getAttribute("aria-valuenow"), "50");
  assert.equal(await controlsDivider.getAttribute("aria-valuenow"), "38");
  await click(page, "Batch view…");
  await dock.waitFor();
  assert(Math.abs((await dock.boundingBox()).height - 320) < 2);
  assert(await dock.getByTestId("batch-heatmap").isVisible());
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(
      artifacts,
      `batch-smoke${engine === webkit ? "-webkit" : ""}.json`,
    ),
    JSON.stringify(
      {
        ok: true,
        runtime: "rust",
        browser: engineName,
        processorPid: native.child.pid,
        fixtureGenerator: "rust",
        companionWindow: true,
        lowerLeftDock: true,
        linkedCake: true,
        detachedBatchToPatternClick: true,
        patternToDetachedBatchClick: true,
        sharedClickReadouts: true,
        preservedDisplay: true,
        requests,
        consoleErrors: errors,
      },
      null,
      2,
    ),
  );
  console.log(`${engineName} (rust): Batch companion/dock smoke passed`);
} catch (e) {
  await page
    .screenshot({ path: path.join(artifacts, "batch-failure-main.png") })
    .catch(() => {});
  if (child)
    await child
      .screenshot({ path: path.join(artifacts, "batch-failure-window.png") })
      .catch(() => {});
  throw e;
} finally {
  await browser.close();
  await native.close();
  await writeFile(path.join(artifacts, "batch-smoke.log"), logs.join(""));
  await rm(temporary, { recursive: true, force: true });
}

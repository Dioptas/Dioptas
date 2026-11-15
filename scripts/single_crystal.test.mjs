import assert from "node:assert/strict";
import { test } from "node:test";
import {
  crystalDefaults,
  crystalConfigError,
  crystalFlags,
  dacEstimatePatch,
  dacEstimateSummary,
  exploratoryCrystalConfig,
  latticeFoundLabel,
  latticeMethod,
  latticeMethods,
  maxGrains,
  cellVolume,
  maskResult,
  maskTotal,
  setupSummary,
  sharedImageRequest,
  sharedMaskNote,
  stepPatch,
  widthFollowsStep,
  workflowDefaults,
  busyFramesNote,
  excludedFramesNote,
  mergeAngle,
  mergedNote,
  bravaisName,
  candidateCell,
  deviationLabel,
  refinedCellLines,
  symmetryTolerance,
  withUncertainty,
} from "../src/singleCrystalDomain.ts";
import { crystalPixelReading } from "../src/singleCrystalReadout.ts";
import { stepNumber } from "../src/numericDraft.ts";
test("mask spin boxes step on their grid without float drift and stay in bounds", () => {
  // Below / × lit: 0.1 steps within 0.01-0.99.
  assert.equal(stepNumber(0.5, 0.1, 1, { min: 0.01, max: 0.99 }), 0.6);
  assert.equal(stepNumber(0.6, 0.1, 1, { min: 0.01, max: 0.99 }), 0.7);
  assert.equal(stepNumber(0.7, 0.1, -1, { min: 0.01, max: 0.99 }), 0.6);
  assert.equal(stepNumber(0.9, 0.1, 1, { min: 0.01, max: 0.99 }), 0.99);
  assert.equal(stepNumber(0.1, 0.1, -1, { min: 0.01, max: 0.99 }), 0.01);
  // From a typed value between grid points, the first step lands on the grid.
  assert.equal(stepNumber(0.65, 0.1, 1, { min: 0.01, max: 0.99 }), 0.7);
  assert.equal(stepNumber(0.65, 0.1, -1, { min: 0.01, max: 0.99 }), 0.6);
  // Half-opening: 0.5° steps, below 90°.
  assert.equal(stepNumber(41, 0.5, 1, { positive: true, max: 89.9 }), 41.5);
  assert.equal(stepNumber(89.5, 0.5, 1, { positive: true, max: 89.9 }), 89.9);
  assert.equal(stepNumber(0.5, 0.5, -1, { positive: true, max: 89.9 }), 0.5);
  // Margin: 20 px steps on multiples of 20 (from the old default 16 too),
  // 0-4096; a typed 25 stays exact until stepped.
  const margin = { integer: true, min: 0, max: 4096 };
  assert.equal(stepNumber(16, 20, 1, margin), 20);
  assert.equal(stepNumber(16, 20, -1, margin), 0);
  assert.equal(stepNumber(25, 20, 1, margin), 40);
  assert.equal(stepNumber(20, 20, -1, margin), 0);
  assert.equal(stepNumber(4090, 20, 1, margin), 4096);
  // Diamond detection level: whole sigma steps within 3-50.
  assert.equal(stepNumber(10, 1, -1, { min: 3, max: 50 }), 9);
  assert.equal(stepNumber(3, 1, -1, { min: 3, max: 50 }), 3);
  assert.equal(stepNumber(7.5, 1, 1, { min: 3, max: 50 }), 8);
  assert.equal(stepNumber(50, 1, 1, { min: 3, max: 50 }), 50);
  // Diamond Min. size and Margin: steps of 5 on multiples of 5.
  assert.equal(stepNumber(10, 5, 1, { integer: true, min: 0, max: 200 }), 15);
  assert.equal(stepNumber(0, 5, -1, { integer: true, min: 0, max: 200 }), 0);
  assert.equal(stepNumber(198, 5, 1, { integer: true, min: 0, max: 200 }), 200);
  const size = { integer: true, min: 1 };
  assert.equal(stepNumber(1, 5, 1, size), 5);
  assert.equal(stepNumber(20, 5, 1, size), 25);
  assert.equal(stepNumber(5, 5, -1, size), 1);
  assert.equal(stepNumber(3, 5, -1, size), 1);
  // Diamond d tolerance: 0.5 % steps within 0.01-20.
  const tolerance = { min: 0.01, max: 20 };
  assert.equal(stepNumber(3, 0.5, 1, tolerance), 3.5);
  assert.equal(stepNumber(0.5, 0.5, -1, tolerance), 0.01);
  assert.equal(stepNumber(19.5, 0.5, 1, tolerance), 20);
  // At a bound a step changes nothing (the field then sends nothing).
  for (const [value, step, direction, limits] of [
    [0, 20, -1, margin],
    [4096, 20, 1, margin],
    [1, 5, -1, size],
    [0.01, 0.1, -1, { min: 0.01, max: 0.99 }],
    [0.99, 0.1, 1, { min: 0.01, max: 0.99 }],
    [0.5, 0.5, -1, { positive: true, max: 89.9 }],
    [89.9, 0.5, 1, { positive: true, max: 89.9 }],
    [0.01, 0.5, -1, tolerance],
    [20, 0.5, 1, tolerance],
  ])
    assert.equal(
      stepNumber(value, step, direction, limits),
      value,
      `${value} ${step} ${direction}`,
    );
});
test("SC readout preserves top-down detector rows and uses its own wavelength", () => {
  const data = {
    shape: [256, 256],
    config: crystalDefaults,
    frame: 4,
    geometry: { wavelength: 1 },
  };
  const top = crystalPixelReading(
    data,
    { x: 3, y: 255 },
    { value: 123, twoTheta: 60 },
  );
  const bottom = crystalPixelReading(
    data,
    { x: 3, y: 0 },
    { value: 123, twoTheta: 60 },
  );
  assert.equal(top.fields[1].value, "0");
  assert.equal(bottom.fields[1].value, "255");
  assert.equal(top.fields[2].value, "123");
  assert.equal(top.fields.find((f) => f.label === "d").value, "1");
  assert.equal(top.fields.find((f) => f.label === "ω").value, "-31.750°");
});
test("SC drafts report all bounded kernel inputs and degenerate metrics", () => {
  assert.equal(crystalConfigError(crystalDefaults), null);
  for (const patch of [
    { smoothness: 0 },
    { link_radius: 100 },
    { tolerance: 0 },
    { polarization: 2 },
    { saturation: 0 },
    { omega_start: 1e6 },
    { min_pixels: 1.2 },
    { metric: [1, 1, 1, 1, 1, 179] },
  ])
    assert.notEqual(crystalConfigError({ ...crystalDefaults, ...patch }), null);
});

test("native tracks preserve partial/duplicate warnings and native reflection eligibility", () => {
  assert.match(crystalFlags(256, undefined, true), /partial/);
  assert.match(crystalFlags(128, undefined, true), /multiple/);
  assert.match(crystalFlags(131072, true), /usable.*mismatch/);
  assert.match(crystalFlags(0, false), /excluded/);
  const excluded = crystalFlags(41234, false);
  assert.match(
    excluded,
    /masked.*background.*partial.*incomplete profile.*no usable profile/,
  );
  assert.doesNotMatch(excluded, /flags 41234/);
  assert.match(crystalFlags(1024, false), /no data/);
  assert.match(crystalFlags(2048, false), /aperture boundary/);
  assert.match(crystalFlags(16384, false), /profile fit failed/);
  assert.notEqual(crystalFlags(1 << 20), "usable");
});

test("SC rotation defaults are the DAC scan's: -34° start, 0.5° frames", () => {
  assert.equal(crystalDefaults.omega_start, -34);
  assert.equal(crystalDefaults.omega_step, 0.5);
  assert.equal(crystalDefaults.exposure, 0.5);
});
test("lean SC settings start with only the geometric DAC opening mask", () => {
  const lean = exploratoryCrystalConfig(crystalDefaults);
  assert.equal(lean.integration_method, "summation");
  assert.equal(lean.confirmed, true);
  assert.equal(lean.background, false);
  assert.equal(lean.dac_enabled, true);
  assert.equal(lean.seat_enabled, false);
  assert.equal(lean.diamond_enabled, false);
  // Seat shadow, when switched on: below 0.6 × each block's lit level, 20 px
  // margin (on the 20 px spin grid).
  assert.equal(lean.seat_threshold, 0.6);
  assert.equal(lean.seat_guard, 20);
  // Diamond spots: regions of at least 120 px, grown by a round 10 px margin.
  assert.equal(lean.diamond_min_size, 120);
  assert.equal(lean.diamond_margin, 10);
  assert.equal(lean.diamond_level, 10);
  assert.equal(
    crystalConfigError({ ...lean, diamond_level: 2 }) !== null,
    true,
  );
  assert.equal(
    crystalConfigError({ ...lean, diamond_margin: 201 }) !== null,
    true,
  );
  assert.equal(crystalConfigError(lean), null);
  // Once lean, the user's mask choices are kept.
  const chosen = { ...lean, seat_enabled: true, dac_enabled: false };
  assert.deepEqual(exploratoryCrystalConfig(chosen), chosen);
});
test("a DAC estimate changes only what it determines and says so in one line", () => {
  const base = {
    before: 0.54,
    after: 0.93,
    startRange: [-37.5, -36.5],
    openingRange: [41.5, 42.5],
    darkShare: 0.17,
    frames: [0, 14, 71, 129, 143],
    block: 34,
    seconds: 0.7,
  };
  const both = {
    ...base,
    status: "both",
    omegaStart: -37.5,
    halfOpening: 42,
  };
  assert.deepEqual(dacEstimatePatch(both), {
    omega_start: -37.5,
    dac_half_opening: 42,
  });
  assert.equal(
    dacEstimateSummary(both),
    "Start -37.50°, opening 42.00° · fit 54 → 93 %",
  );
  const one = { ...both, status: "opening_only", omegaStart: null };
  assert.deepEqual(dacEstimatePatch(one), { dac_half_opening: 42 });
  assert.match(
    dacEstimateSummary(one),
    /one end only: start kept, opening 42\.00°/,
  );
  for (const status of ["no_shadow", "undetermined"]) {
    const none = { ...base, status, omegaStart: null, halfOpening: null };
    assert.deepEqual(dacEstimatePatch(none), {});
    assert.match(dacEstimateSummary(none), /nothing changed/);
  }
  // Applied through the lean settings, the estimate keeps the DAC mask on.
  const applied = exploratoryCrystalConfig({
    ...exploratoryCrystalConfig(crystalDefaults),
    ...dacEstimatePatch(both),
  });
  assert.equal(applied.omega_start, -37.5);
  assert.equal(applied.dac_half_opening, 42);
  assert.equal(applied.dac_enabled, true);
});
test("Single Crystal spin boxes are the native Dioptas spin box", async () => {
  const { readFile } = await import("node:fs/promises");
  const read = (name) =>
    readFile(new URL(`../src/${name}`, import.meta.url), "utf8");
  const field = await read("CommitNumberField.tsx");
  // Same control and wheel rule as the phase editor and overlay controls.
  assert.match(field, /className="numeric-stepper"/);
  assert.match(field, /useSpinBoxWheel\(/);
  // No second, hand-drawn stepper.
  for (const name of [
    "CommitNumberField.tsx",
    "ui/ui.css",
    "singleCrystal.css",
  ])
    assert.doesNotMatch(await read(name), /commit-number-step/);
  // Arrows always shown, like the overlay controls and data table.
  assert.match(
    await read("singleCrystal.css"),
    /\.sc-panel input\.numeric-stepper::-webkit-inner-spin-button\s*\{\s*opacity: 1;/,
  );
});
test("Find spots spin boxes step on their grid and stay within the accepted ranges", () => {
  const threshold = { min: 1, max: 100 };
  assert.equal(stepNumber(5, 0.5, 1, threshold), 5.5);
  assert.equal(stepNumber(5, 0.5, -1, threshold), 4.5);
  assert.equal(stepNumber(5.2, 0.5, 1, threshold), 5.5);
  assert.equal(stepNumber(1, 0.5, -1, threshold), 1);
  assert.equal(stepNumber(100, 0.5, 1, threshold), 100);
  const area = { integer: true, min: 1, max: 1000 };
  assert.equal(stepNumber(3, 1, 1, area), 4);
  assert.equal(stepNumber(1, 1, -1, area), 1);
  assert.equal(stepNumber(1000, 1, 1, area), 1000);
  const link = { min: 0.1, max: 30 };
  assert.equal(stepNumber(3, 0.5, 1, link), 3.5);
  assert.equal(stepNumber(0.5, 0.5, -1, link), 0.1);
  assert.equal(stepNumber(0.1, 0.5, -1, link), 0.1);
  assert.equal(stepNumber(0.1, 0.5, 1, link), 0.5);
  assert.equal(stepNumber(29.8, 0.5, 1, link), 30);
  // The field limits match the accepted configuration ranges.
  for (const [key, value] of [
    ["threshold", 0.5],
    ["threshold", 100.5],
    ["min_pixels", 0],
    ["min_pixels", 1001],
    ["link_radius", 0.05],
    ["link_radius", 30.5],
  ])
    assert.ok(
      crystalConfigError({ ...crystalDefaults, [key]: value }),
      `${key} ${value}`,
    );
});
test("the Mask mode mask is on by default and says why when it cannot apply", () => {
  assert.equal(crystalDefaults.shared_mask_enabled, true);
  assert.equal(
    exploratoryCrystalConfig(crystalDefaults).shared_mask_enabled,
    true,
  );
  // The user's choice is kept once lean.
  const off = {
    ...exploratoryCrystalConfig(crystalDefaults),
    shared_mask_enabled: false,
  };
  assert.equal(exploratoryCrystalConfig(off).shared_mask_enabled, false);
  assert.equal(sharedMaskNote("ready"), null);
  assert.equal(sharedMaskNote("shape"), "other shape");
  assert.equal(sharedMaskNote("none"), "empty");
  assert.equal(sharedMaskNote(undefined), "empty");
});
test("the shown SC frame opens as the shared image only on request", async () => {
  // The file and file frame of the shown frame, through the shared loader;
  // the shared calibration is not part of the request.
  assert.deepEqual(
    sharedImageRequest({ source: { path: "/scan/eiger_0000.h5", frame: 41 } }),
    { path: "/scan/eiger_0000.h5", frame: 41 },
  );
  assert.equal(sharedImageRequest({ source: null }), null);
  assert.equal(sharedImageRequest({}), null);
  const { readFile } = await import("node:fs/promises");
  const view = await readFile(
    new URL("../src/SingleCrystalWorkspace.tsx", import.meta.url),
    "utf8",
  );
  // One explicit button; browsing frames only asks for scxrd_frame.
  assert.equal(view.match(/run\(\s*"open_image"/g)?.length, 1);
  assert.match(view, /aria-label="Show frame in other modes"/);
  const browse = view.slice(
    view.indexOf("const changeFrame"),
    view.indexOf("const commitFrameDraft"),
  );
  assert.match(browse, /scxrd_frame/);
  assert.doesNotMatch(browse, /open_image/);
  // Returning to the mode refreshes the state, which takes over a changed
  // Mask mode mask.
  assert.match(view, /active && !wasActive\.current[\s\S]{0,80}scxrd_snapshot/);
  assert.match(view, /Mask mode mask/);
});
test("persistent pixels start off; their frame share steps by 5 % within 20-100 %", async () => {
  assert.equal(crystalDefaults.persistent_enabled, false);
  assert.equal(crystalDefaults.persistent_fraction, 50);
  const lean = exploratoryCrystalConfig(crystalDefaults);
  assert.equal(lean.persistent_enabled, false);
  assert.equal(crystalConfigError({ ...lean, persistent_enabled: true }), null);
  // Below 20 % a diamond reflection (about 15 of 144 frames) could pass.
  assert.notEqual(
    crystalConfigError({ ...lean, persistent_fraction: 15 }),
    null,
  );
  assert.notEqual(
    crystalConfigError({ ...lean, persistent_fraction: 101 }),
    null,
  );
  const bounds = { min: 20, max: 100 };
  assert.equal(stepNumber(50, 5, 1, bounds), 55);
  assert.equal(stepNumber(20, 5, -1, bounds), 20);
  assert.equal(stepNumber(98, 5, 1, bounds), 100);
  const { readFile } = await import("node:fs/promises");
  const view = await readFile(
    new URL("../src/SingleCrystalWorkspace.tsx", import.meta.url),
    "utf8",
  );
  // One row; its one stepped field when the row is open.
  assert.match(view, /Persistent pixels/);
  assert.match(
    view,
    /case "persistent":\s*return \(\s*<CommitNumberField\s+label="Frames"\s+unit="%"[\s\S]{0,200}step=\{5\}\s+min=\{20\}\s+max=\{100\}/,
  );
});
test("collapsed Setup tells start, step, axis, sense and wavelength in one line", () => {
  const c = { ...crystalDefaults, omega_start: -37.5, axis: [-1, 0, 0] };
  assert.equal(
    setupSummary(c, 0.28457),
    "\u221237.5° · step 0.5° · vertical \u21bb · λ 0.2846 Å",
  );
  // A width apart from the step is shown; horizontal counterclockwise.
  assert.equal(
    setupSummary(
      { ...c, exposure: 0.25, axis: [0, 1, 0], omega_start: 12 },
      null,
    ),
    "12° · step 0.5° / 0.25° · horizontal \u21ba · no calibration",
  );
});
test("width per frame follows step unless set apart", () => {
  const c = { ...crystalDefaults, omega_step: 0.5, exposure: 0.5 };
  assert.equal(widthFollowsStep(c, false), true);
  // Following: one settings command changes both.
  assert.deepEqual(stepPatch(c, 0.25, false), {
    omega_step: 0.25,
    exposure: 0.25,
  });
  // Chosen apart, or an existing different width: only the step changes.
  assert.equal(widthFollowsStep(c, true), false);
  assert.deepEqual(stepPatch(c, 1, true), { omega_step: 1 });
  const apart = { ...c, exposure: 0.4 };
  assert.equal(widthFollowsStep(apart, false), false);
  assert.deepEqual(stepPatch(apart, 1, false), { omega_step: 1 });
});
test("each mask row shows its own number; the cell switch covers only the cell masks", () => {
  // Older recipes say masks_enabled (backend alias); the GUI sends the new name.
  assert.equal(crystalDefaults.cell_masks_enabled, true);
  assert.equal("masks_enabled" in crystalDefaults, false);
  const c = {
    ...exploratoryCrystalConfig(crystalDefaults),
    dac_half_opening: 41,
    seat_enabled: true,
    diamond_enabled: true,
    persistent_enabled: true,
  };
  const counts = {
    total: 18.96,
    dac: 17.8,
    seat: 17.99,
    diamonds: 1344,
    persistent: 1876,
    shared: 300,
  };
  const row = (key, config = c, status = "ready") =>
    maskResult(key, config, counts, status);
  assert.equal(row("dac"), "41°");
  assert.equal(row("seat"), "18.0\u00a0%");
  assert.equal(row("diamond"), "1344 spots");
  assert.equal(row("persistent"), "1876\u00a0px");
  assert.equal(row("shared"), "300\u00a0px");
  assert.equal(row("shared", c, "none"), "empty");
  assert.equal(row("shared", c, "shape"), "other shape");
  assert.equal(
    maskResult("diamond", c, { ...counts, diamonds: 1 }, "ready"),
    "1 spot",
  );
  // Off masks show nothing; the cell switch hides only the cell masks' numbers.
  assert.equal(row("seat", { ...c, seat_enabled: false }), null);
  const cellOff = { ...c, cell_masks_enabled: false };
  for (const key of ["dac", "seat", "diamond"])
    assert.equal(row(key, cellOff), null);
  assert.equal(row("persistent", cellOff), "1876\u00a0px");
  // Not made yet: no numbers (the DAC opening is a setting).
  assert.equal(maskResult("seat", c, undefined, "ready"), null);
  assert.equal(maskResult("dac", c, undefined, "ready"), "41°");
  assert.equal(maskTotal(counts), "19.0\u00a0% masked");
  assert.equal(maskTotal(undefined), null);
});
test("mask rows: one open at a time, keyboard reachable, cell switch on its group", async () => {
  const { readFile } = await import("node:fs/promises");
  const view = await readFile(
    new URL("../src/SingleCrystalWorkspace.tsx", import.meta.url),
    "utf8",
  );
  assert.match(view, /useState<MaskKey \| null>\(null\)/);
  assert.match(view, /aria-expanded=\{open\}/);
  assert.match(view, /aria-controls=/);
  assert.match(view, />\s*Diamond anvil cell\s*</);
  assert.match(view, /cell_masks_enabled: e\.target\.checked/);
  // Rows with fields carry a disclosure mark (turned down when open, CSS).
  assert.match(view, /<ChevronRight[\s\S]{0,80}className="sc-mask-chevron"/);
  assert.match(
    await readFile(
      new URL("../src/singleCrystal.css", import.meta.url),
      "utf8",
    ),
    /\.sc-mask-toggle\[aria-expanded="true"\] \.sc-mask-chevron \{\s*transform: rotate\(90deg\)/,
  );
  // Gone: the whole-step switch and the summary line of the step.
  assert.doesNotMatch(view, /sc-step-switch|[^_]masks_enabled/);
  // Setup: the shared compact disclosure, choice kept in browser storage.
  assert.match(view, /className="compact-section sc-setup"/);
  assert.match(view, /"dioptas-scxrd:setup-open"/);
});

test("Find lattices: Max. grains 5 by default, older configs load with it; cell volume", () => {
  assert.equal(crystalDefaults.max_grains, 5);
  const { max_grains: _, ...older } = crystalDefaults;
  assert.equal(maxGrains(older), 5);
  for (const bad of [0, 21, 2.5, "3"]) assert.equal(maxGrains({ max_grains: bad }), 5);
  assert.equal(maxGrains({ max_grains: 1 }), 1);
  assert.equal(maxGrains({ max_grains: 20 }), 20);
  // Enstatite (Pbca) and a monoclinic cell.
  assert.ok(Math.abs(cellVolume([8.81, 5.18, 18.23, 90, 90, 90]) - 831.95) < 0.1);
  assert.ok(
    Math.abs(cellVolume([7.5, 9.2, 12.4, 90, 104, 90]) - 7.5 * 9.2 * 12.4 * Math.sin((104 * Math.PI) / 180)) < 1e-6,
  );
});

test("Find lattices: one row per lattice with its tick; the shown lattice marks its spots", async () => {
  const { readFile } = await import("node:fs/promises");
  const view = await readFile(new URL("../src/SingleCrystalWorkspace.tsx", import.meta.url), "utf8");
  assert.match(view, /operation: "keep",\s*index: i,\s*keep: e\.target\.checked/);
  assert.match(view, /\{ operation: "show", index: i \}/);
  assert.match(view, /p\.lattice === shownLattice \+ 1/);
  assert.match(view, /label="Max\. grains"[\s\S]{0,200}step=\{1\}[\s\S]{0,40}integer[\s\S]{0,40}min=\{1\}[\s\S]{0,40}max=\{20\}/);
  // The former candidate cards with a "Use lattice" button are gone.
  assert.doesNotMatch(view, /Use lattice/);
});

test("Find lattices search: FFT + row search by default, older configs load with it", () => {
  assert.equal(crystalDefaults.lattice_method, "both");
  assert.deepEqual(
    latticeMethods.map((m) => [m.value, m.label]),
    [
      ["both", "FFT + row search"],
      ["fft", "FFT"],
      ["rows", "Row search"],
    ],
  );
  // A config or recipe from before the setting has no lattice_method.
  const { lattice_method: _, ...older } = crystalDefaults;
  assert.equal(latticeMethod(older), "both");
  assert.equal(latticeMethod({ lattice_method: "nonsense" }), "both");
  for (const m of ["both", "fft", "rows"])
    assert.equal(latticeMethod({ ...crystalDefaults, lattice_method: m }), m);
  // The exploratory conversion keeps the chosen search.
  assert.equal(
    exploratoryCrystalConfig({ ...crystalDefaults, lattice_method: "rows" })
      .lattice_method,
    "rows",
  );
  // Candidate labels; results from before the field came from the FFT.
  assert.equal(latticeFoundLabel("fft"), "FFT");
  assert.equal(latticeFoundLabel("rows"), "Rows");
  assert.equal(latticeFoundLabel("both"), "FFT · Rows");
  assert.equal(latticeFoundLabel(undefined), "FFT");
});

test("Minimum area: 2 px in the summation workflow, 3 px in the fixed profile protocol", () => {
  const lean = exploratoryCrystalConfig(crystalDefaults);
  assert.equal(lean.min_pixels, 2);
  assert.equal(crystalConfigError(lean), null);
  // Switching the workflow sets it; switching back restores it.
  const profile = {
    ...lean,
    integration_method: "profile",
    ...workflowDefaults("profile"),
  };
  assert.equal(profile.min_pixels, 3);
  assert.equal(profile.threshold, 5);
  const back = {
    ...profile,
    integration_method: "summation",
    ...workflowDefaults("summation"),
  };
  assert.equal(back.min_pixels, 2);
  // An existing summation config keeps its value.
  assert.equal(exploratoryCrystalConfig({ ...lean, min_pixels: 3 }).min_pixels, 3);
  assert.equal(exploratoryCrystalConfig({ ...lean, min_pixels: 7 }).min_pixels, 7);
});

test("Find spots names busy frames in one line and offers to exclude them, or to take excluded frames back", async () => {
  assert.equal(busyFramesNote([]), "");
  assert.equal(busyFramesNote([0]), "1 frame with unusually many spots: 1");
  assert.equal(busyFramesNote([0, 4]), "2 frames with unusually many spots: 1, 5");
  assert.equal(excludedFramesNote([]), "");
  assert.equal(excludedFramesNote([4, 0]), "Excluded frames: 1, 5");
  assert.equal(excludedFramesNote([0]), "Excluded frame: 1");
  const { readFile } = await import("node:fs/promises");
  const view = await readFile(new URL("../src/SingleCrystalWorkspace.tsx", import.meta.url), "utf8");
  // Under the Find spots row, in the summation workflow only.
  assert.match(view, /\{stage === 1 && framesNotes\(data\)\}/);
  assert.match(view, /integration_method !== "summation"\) return null/);
  // One click excludes (or includes) through the backend and finds the spots again.
  assert.match(view, /\{ operation: "exclude_frames", frames, exclude \}/);
  assert.match(view, /busyFramesNote\(busy\),\s*"Exclude",\s*\(\) => excludeFrames\(busy, true\)/);
  assert.match(view, /"Include",\s*\(\) => excludeFrames\(d\.excludedFrames, false\)/);
  assert.match(view, /run\(\s*"scxrd_run",\s*\{ stage, automatic: false \}/);
});

test("Find lattices: Merge within 0.5° by default, older configs load with it; merged rows say so in their detail line", async () => {
  assert.equal(crystalDefaults.merge_angle, 0.5);
  assert.equal(mergeAngle({}), 0.5);
  assert.equal(mergeAngle({ merge_angle: 0 }), 0);
  assert.equal(mergeAngle({ merge_angle: 2.5 }), 2.5);
  assert.equal(mergeAngle({ merge_angle: 9 }), 0.5);
  assert.equal(mergedNote(undefined), "");
  assert.equal(mergedNote({ domains: 2, angle: 0.2612 }), "2 domains, 0.26°");
  const { readFile } = await import("node:fs/promises");
  const view = await readFile(new URL("../src/SingleCrystalWorkspace.tsx", import.meta.url), "utf8");
  assert.match(view, /label="Merge within"\s*unit="°"\s*value=\{mergeAngle\(data\.config\)\}\s*onCommit=\{\(v\) => setConfig\(\{ merge_angle: v \}\)\}\s*step=\{0\.1\}\s*min=\{0\}\s*max=\{5\}/);
  // Only in the detail line that opens on click, not on the main row.
  assert.match(view, /sc-lattice-details[\s\S]{0,300}mergedNote\(cell\.merged\)/);
});

test("Refine lattice: values with standard uncertainties in crystallographic notation", () => {
  assert.equal(withUncertainty(18.23014, 0.00123), "18.2301(12)");
  assert.equal(withUncertainty(18.2301, 0.0035), "18.230(4)");
  // Up to 19 in two digits, otherwise one; 19.6 rounds to one digit.
  assert.equal(withUncertainty(104.123, 0.0149), "104.123(15)");
  assert.equal(withUncertainty(5.18123, 0.000196), "5.1812(2)");
  assert.equal(withUncertainty(833.21, 0.09), "833.21(9)");
  // Uncertainties of 1 and more: the value rounded to them.
  assert.equal(withUncertainty(833.2, 12), "833(12)");
  assert.equal(withUncertainty(833.2, 25), "830(30)");
  // A fixed value has none.
  assert.equal(withUncertainty(90, 0, 0), "90");
  assert.equal(withUncertainty(Number.NaN, 0.1), "—");
});

test("Refine lattice: candidate rows and the refined cell", () => {
  const oP = {
    bravais: "oP",
    cell: [5.181, 8.812, 18.229, 90.03, 89.98, 90.01],
    constrained: [5.181, 8.812, 18.229, 90, 90, 90],
    length_deviation: 0,
    angle_deviation: 0.034,
  };
  assert.deepEqual(candidateCell(oP), { lengths: "5.181 · 8.812 · 18.229 Å", angles: "" });
  assert.equal(deviationLabel(oP), "0.00 % · 0.03°");
  const mP = { ...oP, bravais: "mP", constrained: [5.181, 8.812, 18.229, 90, 90.02, 90] };
  assert.equal(candidateCell(mP).angles, "β 90.02°");
  const aP = { ...oP, bravais: "aP", constrained: oP.cell };
  assert.equal(candidateCell(aP).angles, "α 90.03° · β 89.98° · γ 90.01°");
  assert.equal(deviationLabel(aP), "—");
  const hP = { ...oP, bravais: "hP", constrained: [3, 3, 5, 90, 90, 120], length_deviation: 0.0012 };
  assert.equal(candidateCell(hP).angles, "γ 120.00°");
  assert.equal(deviationLabel(hP), "0.12 % · 0.03°");
  assert.equal(bravaisName("oP"), "Primitive orthorhombic");
  assert.equal(bravaisName("hR"), "Rhombohedral (hexagonal axes)");
  const lines = refinedCellLines({
    bravais: "oP",
    conventional: [],
    cell: [5.18123, 8.8213, 18.23014, 90, 90, 90],
    cell_su: [0.0003, 0.0005, 0.00123, 0, 0, 0],
    volume: 833.21,
    volume_su: 0.09,
    rms: 0.00213,
    used: 3412,
    owned: 3460,
    converged: true,
  });
  assert.deepEqual(lines, {
    lengths: "5.1812(3) · 8.8213(5) · 18.2301(12) Å",
    angles: "90 · 90 · 90°",
    volume: "833.21(9) Å³",
    fit: "3412 spots · rms 0.0021 Å⁻¹",
  });
  // Monoclinic beta carries its uncertainty; a fit that did not converge says so.
  const m = refinedCellLines({
    bravais: "mP",
    conventional: [],
    cell: [7.5, 9.2, 12.4, 90, 104.1234, 90],
    cell_su: [0.001, 0.001, 0.001, 0, 0.0021, 0],
    volume: 830,
    volume_su: 0.2,
    rms: 0.003,
    used: 40,
    owned: 50,
    converged: false,
  });
  assert.equal(m.angles, "90 · 104.123(2) · 90°");
  assert.match(m.fit, /not converged$/);
});

test("Refine lattice: tolerances default to PhaseSmith's 1 % and 1°, older configs load with them", () => {
  assert.equal(crystalDefaults.symmetry_length_tolerance, 1);
  assert.equal(crystalDefaults.symmetry_angle_tolerance, 1);
  assert.equal(symmetryTolerance(undefined), 1);
  assert.equal(symmetryTolerance(0), 1);
  assert.equal(symmetryTolerance(12), 1);
  assert.equal(symmetryTolerance(3), 3);
  const lean = exploratoryCrystalConfig(crystalDefaults);
  assert.equal(crystalConfigError(lean), null);
  assert.match(crystalConfigError({ ...lean, symmetry_angle_tolerance: 11 }) ?? "", /Angle tolerance/);
});

test("Refine lattice is the fourth step: tolerances in its settings, one candidate table per kept lattice", async () => {
  const { readFile } = await import("node:fs/promises");
  const view = await readFile(new URL("../src/SingleCrystalWorkspace.tsx", import.meta.url), "utf8");
  assert.match(view, /"Find lattices",\s*"Refine lattice",\s*\] as const/);
  assert.match(view, /const lastStage = data\?\.geometry \? 3 : 1/);
  assert.match(view, /label="Lengths within"\s*unit="%"[\s\S]{0,600}step=\{0\.5\}\s*min=\{0\.1\}\s*max=\{10\}/);
  assert.match(view, /label="Angles within"\s*unit="°"[\s\S]{0,600}step=\{0\.5\}\s*min=\{0\.1\}\s*max=\{10\}/);
  // A row press refines the lattice as that type through the backend.
  assert.match(view, /\{ operation: "symmetry", index: r\.lattice, choice \}/);
  assert.match(view, /role="radio"\s*aria-checked=\{chosen\}/);
  assert.match(view, /data\.refinedLattices\.map\(\(r\) => symmetryGroup\(r\)\)/);
  // Each lattice is a disclosure group.
  assert.match(view, /className="sc-mask-toggle sc-symmetry-toggle"\s*aria-expanded=\{open\}/);
});

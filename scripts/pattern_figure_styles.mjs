import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

export async function exerciseFigureStyles(page, artifacts, engine) {
  const button = (name) => page.getByRole("button", { name, exact: true });
  const tab = (name) => page.getByRole("tab", { name, exact: true }).click();
  const number = (name) => page.getByRole("spinbutton", { name, exact: true });
  const select = page.getByRole("combobox", {
    name: "Saved figure style",
    exact: true,
  });
  const styleName = page.getByRole("textbox", {
    name: "Figure style name",
    exact: true,
  });
  await tab("Layout");
  await button("Reset figure settings").click();
  await number("Figure font size (pt)").fill("9");
  await number("Figure width (mm)").fill("175");
  await tab("Curves");
  await page
    .getByLabel("Figure curve 1 color", { exact: true })
    .fill("#0072b2");
  await number("Figure curve 1 width").fill("1.4");
  await page
    .getByRole("combobox", { name: "Figure curve 1 style", exact: true })
    .selectOption("dash");
  await tab("Phases");
  assert(await button("Move figure phase 1 up").isDisabled());
  assert(await button("Move figure phase 3 down").isDisabled());
  await button("Move figure phase 1 down").click();
  await page
    .getByLabel("Figure phase 1 color", { exact: true })
    .fill("#b63b60");
  await number("Figure phase row spacing (mm)").fill("7");
  await number("Figure phase tick height (mm)").fill("3");
  const guides = page.getByRole("checkbox", {
    name: "Show phase row guides",
    exact: true,
  });
  await guides.uncheck();
  const inspect = () =>
    page.getByTestId("pattern-figure-artwork").evaluate((artwork) => {
      const svg = artwork.querySelector("svg");
      const rows = [
        ...svg.querySelectorAll('g[aria-label^="Phase reference row:"]'),
      ].map((row) => ({
        label: row.getAttribute("aria-label"),
        segments: [...row.querySelectorAll("path")].map((p) =>
          p
            .getAttribute("d")
            .match(/^M([\d.e+-]+) ([\d.e+-]+)L([\d.e+-]+) ([\d.e+-]+)$/)
            .slice(1)
            .map(Number),
        ),
      }));
      return {
        rows,
        clip: svg
          .querySelector("clipPath path")
          .getAttribute("d")
          .match(/^M([\d.e+-]+) ([\d.e+-]+)h([\d.e+-]+)/)
          .slice(1)
          .map(Number),
      };
    });
  let geometry = await inspect();
  assert.deepEqual(
    geometry.rows.map((row) => row.label),
    [
      "Phase reference row: MgO",
      "Phase reference row: CeO₂",
      "Phase reference row: Fe₃O₄",
    ],
  );
  const expectedX = [
    [16.5, 22.4, 29],
    [19, 27],
    [18, 24],
  ];
  geometry.rows.forEach((row, i) => {
    assert.equal(
      row.segments.length,
      expectedX[i].length,
      "Guides must be absent without losing reflections",
    );
    row.segments.forEach(([x0, y0, x1, y1], j) => {
      assert.equal(x0, x1);
      assert(
        Math.abs(y0 - y1 - (3 * 72) / 25.4) < 1e-7,
        "Tick height must use physical millimeters",
      );
      const [left, , width] = geometry.clip;
      assert(
        Math.abs(x0 - left - ((expectedX[i][j] - 14) / 16) * width) < 1e-7,
        "Phase reordering must preserve radial positions",
      );
    });
    if (i)
      assert(
        Math.abs(
          row.segments[0][1] -
            geometry.rows[i - 1].segments[0][1] -
            (7 * 72) / 25.4,
        ) < 1e-7,
        "Row spacing must use physical millimeters",
      );
  });
  await guides.check();
  const guided = await inspect();
  guided.rows.forEach((row, i) => {
    assert.equal(row.segments.length, geometry.rows[i].segments.length + 1);
    assert.equal(row.segments[0][1], row.segments[0][3]);
  });
  await guides.uncheck();
  await number("Figure phase row spacing (mm)").fill("0");
  await page
    .getByRole("alert")
    .filter({ hasText: "phase row spacing" })
    .waitFor();
  assert(await button("Save figure").isDisabled());
  await number("Figure phase row spacing (mm)").fill("7");
  await tab("Layout");
  await button("Save current style…").click();
  await styleName.fill("Journal");
  await button("Save new style").click();
  await page.getByRole("status").filter({ hasText: "Saved style" }).waitFor();
  const journal = await select.inputValue();
  assert(journal);
  await tab("Phases");
  await number("Figure phase row spacing (mm)").fill("8");
  await tab("Layout");
  assert.equal(
    await select.inputValue(),
    journal,
    "Style selection must survive editing other tabs",
  );
  await button("Apply style").click();
  await button("Save new style").click();
  await page.getByRole("alert").filter({ hasText: "already exists" }).waitFor();
  await number("Figure font size (pt)").fill("12");
  await number("Figure width (mm)").fill("190");
  await button("Apply style").click();
  assert.equal(await number("Figure font size (pt)").inputValue(), "9");
  assert.equal(await number("Figure width (mm)").inputValue(), "175");
  await number("Figure width (mm)").fill("178");
  await styleName.fill("Journal refined");
  await button("Update style").click();
  assert.equal(
    await select.inputValue(),
    journal,
    "Updating/renaming must retain style identity",
  );
  await styleName.fill("Talk");
  await button("Save new style").click();
  const talk = await select.inputValue();
  assert.notEqual(talk, journal);
  await button("Delete style").click();
  assert.equal(await select.locator("option").count(), 2);
  await select.selectOption(journal);
  await page.screenshot({
    path: fileURLToPath(new URL(`${engine}-style-library.png`, artifacts)),
  });
  // A storage failure must be visible and must not mutate the library in memory.
  await page.evaluate(() => {
    window.originalStyleSetItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key === "dioptas-pattern-figure-styles-v1")
        throw Error("storage unavailable");
      return window.originalStyleSetItem.call(this, key, value);
    };
  });
  await styleName.fill("Unsaved");
  await button("Save new style").click();
  await page
    .getByRole("alert")
    .filter({ hasText: "could not be saved" })
    .waitFor();
  assert.equal(await select.locator("option").count(), 2);
  await page.evaluate(() => {
    Storage.prototype.setItem = window.originalStyleSetItem;
  });
  await button("Close figure editor").click();
  await page.evaluate(() => window.openEditor());
  await select.waitFor();
  await select.selectOption(journal);
  await button("Apply style").click();
  assert.equal(await number("Figure width (mm)").inputValue(), "178");
  await tab("Phases");
  assert.equal(await number("Figure phase row spacing (mm)").inputValue(), "7");
  assert.equal(await number("Figure phase tick height (mm)").inputValue(), "3");
  assert.equal(await guides.isChecked(), false);
  geometry = await inspect();
  assert.equal(geometry.rows[0].label, "Phase reference row: MgO");
  await page.screenshot({
    path: fileURLToPath(new URL(`${engine}-phase-row-controls.png`, artifacts)),
  });

  await page.evaluate(async () => {
    const library = await import("/src/patternFigureStyles.ts");
    const figure = window.fixture.patternFigure;
    const check = (condition, message) => {
      if (!condition) throw Error(message);
    };
    const styles = library.loadPatternFigureStyles();
    check(
      styles.length === 1 && styles[0].name === "Journal refined",
      "Named style CRUD did not persist",
    );
    const style = styles[0];
    const source = {
      ...window.figureSource,
      unit: "q_A^-1",
      scale: "log",
      curves: Array.from({ length: 5 }, (_, i) => ({
        ...window.figureSource.curves[0],
        id: `new-${i}`,
        name: `Other sample ${i}`,
        x: [2, 3],
        y: [1, 4],
      })),
      phases: Array.from({ length: 4 }, (_, i) => ({
        phaseIndex: i + 10,
        name: `New phase ${i}`,
        x: 2.5,
        color: "#445566",
        intensity: 1,
      })),
    };
    const settings = figure.defaultPatternFigureSettings(source);
    Object.assign(settings.options, {
      title: "Current title",
      xLabel: "Q custom",
      yLabel: "Counts",
      range: "custom",
      xMin: 2,
      xMax: 3,
      yRange: "custom",
      yMin: 1,
      yMax: 10,
    });
    settings.options.curves.reverse();
    settings.options.curves[1].visible = false;
    settings.options.phaseStyles.reverse();
    settings.options.phaseStyles[0].visible = false;
    const original = JSON.stringify({ source, settings, style });
    const result = library.applyPatternFigureStyle(source, settings, style);
    check(
      JSON.stringify({ source, settings, style }) === original,
      "Applying a style mutated input data or settings",
    );
    for (const key of [
      "title",
      "xLabel",
      "yLabel",
      "range",
      "xMin",
      "xMax",
      "yRange",
      "yMin",
      "yMax",
      "scale",
    ])
      check(
        result.options[key] === settings.options[key],
        `Style changed dataset-specific ${key}`,
      );
    for (const [i, curve] of result.options.curves.entries()) {
      for (const key of ["id", "label", "visible"])
        check(
          curve[key] === settings.options.curves[i][key],
          "Style changed curve identity/order/visibility",
        );
      const slot = style.curves[i % style.curves.length];
      for (const key of ["color", "width", "style"])
        check(
          curve[key] === slot[key],
          "Curve palette did not transfer/repeat",
        );
    }
    result.options.phaseStyles.forEach((phase, i) => {
      for (const key of ["id", "label", "visible"])
        check(
          phase[key] === settings.options.phaseStyles[i][key],
          "Style changed phase identity/order/visibility",
        );
      check(
        phase.color === style.phaseColors[i % style.phaseColors.length],
        "Phase palette did not transfer/repeat",
      );
    });
    figure.renderPatternFigure(source, result.options);
    const noPhases = { ...source, phases: [] };
    const noPhaseSettings = figure.defaultPatternFigureSettings(noPhases);
    figure.renderPatternFigure(
      noPhases,
      library.applyPatternFigureStyle(noPhases, noPhaseSettings, style).options,
    );
    const noPhaseStyle = library.capturePatternFigureStyle(
      "No phases",
      noPhaseSettings,
    );
    const keepColors = library.applyPatternFigureStyle(
      source,
      settings,
      noPhaseStyle,
    );
    check(
      keepColors.options.phaseStyles[0].color ===
        settings.options.phaseStyles[0].color,
      "A style without a phase palette erased phase colors",
    );
    check(
      !JSON.stringify(style).includes("Current title") &&
        !Object.hasOwn(style.appearance, "xMin"),
      "Named styles stored dataset metadata",
    );
    // Corrupt entries are isolated; valid styles survive, including extra fields.
    const bad = structuredClone(style);
    bad.id = "bad";
    bad.name = "Bad";
    bad.curves.push({ color: "bad", width: 1, style: "line" });
    localStorage.setItem(
      library.patternFigureStylesKey,
      JSON.stringify({
        version: 1,
        styles: [
          null,
          bad,
          {
            ...style,
            appearance: { ...style.appearance, title: "stale title" },
          },
        ],
      }),
    );
    const recovered = library.loadPatternFigureStyles();
    check(
      recovered.length === 1 &&
        !Object.hasOwn(recovered[0].appearance, "title"),
      "Malformed template handling lost valid styles or retained source-specific fields",
    );
    localStorage.setItem(library.patternFigureStylesKey, "invalid");
    check(
      library.loadPatternFigureStyles().length === 0,
      "Invalid library did not recover safely",
    );
    library.storePatternFigureStyles(styles);
    // Very tall ticks/long labels reserve space rather than overlapping rows.
    const compact = figure.defaultPatternFigureSettings(
      window.figureSource,
    ).options;
    Object.assign(compact, {
      phaseRowSpacing: 1,
      phaseTickHeight: 6,
      height: 160,
    });
    compact.phaseStyles[0].label =
      "A long phase label that wraps across several lines";
    const svg = new DOMParser().parseFromString(
      figure.renderPatternFigure(window.figureSource, compact),
      "image/svg+xml",
    );
    const rows = [
      ...svg.querySelectorAll('g[aria-label^="Phase reference row:"]'),
    ];
    const bounds = rows.map((row) =>
      [...row.querySelectorAll("path")]
        .map((p) =>
          p
            .getAttribute("d")
            .match(/^M([\d.e+-]+) ([\d.e+-]+)L([\d.e+-]+) ([\d.e+-]+)$/)
            .slice(1)
            .map(Number),
        )
        .filter(([x0, , x1]) => x0 === x1),
    );
    check(
      bounds.every(
        (ticks, i) =>
          !i ||
          Math.min(...ticks.map((t) => t[3])) >
            Math.max(...bounds[i - 1].map((t) => t[1])),
      ),
      "Large phase ticks overlap neighboring rows",
    );
    check(
      JSON.stringify(window.figureSource) === window.beforeEditor,
      "Style/row editing modified scientific source",
    );
  });
  // New controls remain contained at the compact responsive breakpoint.
  await page.setViewportSize({ width: 700, height: 800 });
  for (const textSize of ["normal", "large"]) {
    await page.evaluate((size) => {
      document.querySelector(".app").dataset.textSize = size;
    }, textSize);
    for (const name of ["Layout", "Phases"]) {
      await tab(name);
      assert(
        await page
          .locator(".pattern-figure-controls")
          .evaluate((el) => el.scrollWidth <= el.clientWidth),
        `${name} controls overflow horizontally`,
      );
      await page.screenshot({
        path: fileURLToPath(
          new URL(
            `${engine}-compact-${textSize}-${name.toLowerCase()}.png`,
            artifacts,
          ),
        ),
      });
    }
  }
}

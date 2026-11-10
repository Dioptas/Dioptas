import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { Resvg } from "@resvg/resvg-js";
import { nativeClient } from "./native_backend_client.mjs";
const desktop = fileURLToPath(new URL("../", import.meta.url));
const artifacts = new URL(
  "../artifacts/pattern-figure-editor/",
  import.meta.url,
);
await mkdir(artifacts, { recursive: true });
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const receipts = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch({ headless: true });
    const native = nativeClient();
    try {
      const page = await browser.newPage({
        viewport: { width: 1000, height: 668 },
      });
      const errors = [],
        saved = [];
      let canceled = false;
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__figureSave", async (action, args) => {
        if (canceled) return { ok: true, cancelled: true };
        args.path = fileURLToPath(
          new URL(`${name}-edited.${args.format}`, artifacts),
        );
        const result = await native.invoke(action, args);
        saved.push(result);
        return result;
      });
      await page.goto(
        `${server.resolvedUrls.local[0]}scripts/rendering_fixture.html`,
      );
      await page.waitForFunction(() => window.fixture);
      const sourceResults = await page.evaluate(() => {
        const { patternFigure } = window.fixture;
        const results = [];
        for (const unit of ["2th_deg", "q_A^-1", "d_A"])
          for (const scale of ["linear", "log", "sqrt"]) {
            const convert = (a) => {
              const q = (4 * Math.PI * Math.sin((a * Math.PI) / 360)) / 0.4;
              return unit === "d_A"
                ? (2 * Math.PI) / q
                : unit === "q_A^-1"
                  ? q
                  : a;
            };
            const x = Array.from({ length: 801 }, (_, i) =>
              convert(12 + i * 0.025),
            );
            const y = x.map((_, i) =>
              i === 200 ? null : 20 + 600 * Math.exp(-(((i - 280) / 18) ** 2)),
            );
            const tx = (value) =>
              scale === "log"
                ? Math.log10(value)
                : scale === "sqrt"
                  ? Math.sqrt(value)
                  : value;
            const source = {
              pattern: { x, y, unit },
              unit,
              scale,
              view: {
                xMin: Math.min(convert(14), convert(30)),
                xMax: Math.max(convert(14), convert(30)),
                yMin: tx(1),
                yMax: tx(650),
              },
              curves: [
                { id: "measured", name: "Sample A", color: "#ffffff", x, y },
                {
                  id: "overlay",
                  name: "Reference B",
                  color: "#d55e00",
                  x,
                  y: y.map((v) => (v === null ? null : v * 0.65)),
                },
              ],
              phases: [
                ...[19, 27].map((a, i) => ({
                  phaseIndex: 0,
                  name: "CeO₂",
                  x: convert(a),
                  intensity: 100 / (i + 1),
                  color: "#008844",
                  hkl: [i + 1, 1, 1],
                })),
                ...[16.5, 22.4, 29].map((a, i) => ({
                  phaseIndex: 1,
                  name: "MgO",
                  x: convert(a),
                  intensity: [100, 25, 2][i],
                  color: "#b63b60",
                  hkl: [i + 1, 1, 1],
                })),
                ...[18, 24].map((a, i) => ({
                  phaseIndex: 2,
                  name: "Fe₃O₄",
                  x: convert(a),
                  intensity: [100, 10][i],
                  color: "#7662a2",
                  hkl: [i + 1, 1, 1],
                })),
              ],
            };
            const before = JSON.stringify(source);
            const settings = patternFigure.defaultPatternFigureSettings(source);
            settings.options.title = "Sample <A> & reference";
            settings.options.phaseStyles[0].color = "#008844";
            const svg = patternFigure.renderPatternFigure(
              source,
              settings.options,
            );
            const xml = new DOMParser().parseFromString(svg, "image/svg+xml");
            if (xml.querySelector("parsererror, image, foreignObject"))
              throw Error("Invalid figure SVG");
            const clip = xml
              .querySelector("clipPath path")
              .getAttribute("d")
              .match(/^M([\d.e+-]+) ([\d.e+-]+)h([\d.e+-]+)/);
            const left = Number(clip[1]),
              width = Number(clip[3]);
            const phaseXs = [
              ...xml.querySelectorAll('path[stroke="#008844"]'),
            ].map((p) => Number(p.getAttribute("d").match(/^M([\d.e+-]+)/)[1]));
            for (const p of source.phases.filter((p) => p.phaseIndex === 0)) {
              const expected =
                left +
                ((p.x - source.view.xMin) /
                  (source.view.xMax - source.view.xMin)) *
                  width;
              if (!phaseXs.some((x) => Math.abs(x - expected) < 1e-8))
                throw Error("Phase positions moved in figure export");
            }
            if (
              [...xml.querySelectorAll("text")].some(
                (text) =>
                  !text.hasAttribute("font-size") ||
                  !text.hasAttribute("font-family") ||
                  text.hasAttribute("style"),
              )
            )
              throw Error(
                "SVG typography must use explicit portable font attributes",
              );
            const rows = [
              ...xml.querySelectorAll('g[aria-label^="Phase reference row:"]'),
            ];
            if (rows.length !== 3)
              throw Error("Each phase needs its own stacked reference row");
            const baselines = [];
            rows.forEach((row, phase) => {
              const ticks = [...row.querySelectorAll("path")].filter(
                (p) =>
                  p.getAttribute("stroke") ===
                  settings.options.phaseStyles[phase].color,
              );
              if (
                ticks.length !==
                source.phases.filter((p) => p.phaseIndex === phase).length
              )
                throw Error("A reflection was lost from the reference row");
              const segments = ticks.map((p) =>
                p
                  .getAttribute("d")
                  .match(/^M([\d.e+-]+) ([\d.e+-]+)L([\d.e+-]+) ([\d.e+-]+)/)
                  .slice(1)
                  .map(Number),
              );
              if (
                segments.some(
                  ([x0, y0, x1, y1]) =>
                    x0 !== x1 ||
                    Math.abs(y0 - y1 - settings.options.fontSize * 0.85) > 1e-7,
                )
              )
                throw Error("Reference ticks must have equal height");
              baselines.push(segments[0][1]);
              const widths = ticks.map((p) =>
                Number(p.getAttribute("stroke-width")),
              );
              if (Math.max(...widths) <= Math.min(...widths))
                throw Error(
                  "Intensity weighting should change tick thickness, not tick height",
                );
            });
            if (baselines.some((y, i) => i && y <= baselines[i - 1]))
              throw Error("Reference rows are not stacked below each other");
            const frameSegments = [...xml.documentElement.children]
              .filter((el) => el.tagName === "path")
              .map((el) =>
                el
                  .getAttribute("d")
                  .match(/^M([\d.e+-]+) ([\d.e+-]+)L([\d.e+-]+) ([\d.e+-]+)$/),
              )
              .filter(Boolean)
              .map((match) => match.slice(1).map(Number));
            const lowerAxis = frameSegments.find(
              ([x0, y0, x1, y1]) =>
                Math.abs(x0 - left) < 1e-7 &&
                Math.abs(x1 - left - width) < 1e-7 &&
                y0 === y1 &&
                y0 > Math.max(...baselines),
            );
            if (
              !lowerAxis ||
              !frameSegments.some(
                ([x0, y0, x1, y1]) =>
                  Math.abs(x0 - left) < 1e-7 &&
                  x0 === x1 &&
                  y0 === Number(clip[2]) &&
                  y1 === lowerAxis[1],
              )
            )
              throw Error(
                "The left frame must remain continuous through the phase reference rows",
              );

            settings.options.phases = "plot";
            settings.options.scale = "log";
            settings.options.yRange = "auto";
            patternFigure.renderPatternFigure(source, settings.options);
            if (JSON.stringify(source) !== before)
              throw Error("Figure modified scientific source");
            results.push({ unit, scale, svg });
            if (unit === "2th_deg" && scale === "linear") {
              const single = {
                ...patternFigure.defaultPatternFigureSettings(source).options,
                ...patternFigure.patternFigurePresets["90x80"],
              };
              results.push({
                unit: "single-column",
                scale: "rows",
                svg: patternFigure.renderPatternFigure(source, single),
              });
              single.phaseTickWeight = "uniform";
              const uniform = new DOMParser().parseFromString(
                patternFigure.renderPatternFigure(source, single),
                "image/svg+xml",
              );
              const tickWidths = [
                ...uniform.querySelectorAll(
                  'g[aria-label^="Phase reference row:"] path',
                ),
              ]
                .filter((p) => p.getAttribute("stroke") !== "#c5c5c5")
                .map((p) => Number(p.getAttribute("stroke-width")));
              if (tickWidths.some((width) => Math.abs(width - 0.75) > 1e-6))
                throw Error("Uniform reference tick thickness changed");
              single.phases = "plot";
              single.phaseLegend = "auto";
              const separate = patternFigure.renderPatternFigure(
                source,
                single,
              );
              const legends = new DOMParser().parseFromString(
                separate,
                "image/svg+xml",
              );
              const curveLegend = legends.querySelector(
                'g[aria-label="Curve legend"]',
              );
              const phaseLegend = legends.querySelector(
                'g[aria-label="Phase legend"]',
              );
              if (
                !curveLegend ||
                !phaseLegend ||
                curveLegend.textContent.includes("MgO") ||
                phaseLegend.textContent.includes("Sample A")
              )
                throw Error("Curve and phase legends must be independent");
              results.push({
                unit: "single-column",
                scale: "separate-legends",
                svg: separate,
              });
            }
            if (unit === "2th_deg" && scale === "linear")
              window.figureSource = source;
          }
        return results;
      });
      for (const item of sourceResults) {
        const prefix = `${name}-${item.unit.replaceAll(/[^\w]/g, "")}-${item.scale}`;
        const independent = new Resvg(item.svg, {
          fitTo: { mode: "width", value: 1200 },
        }).render();
        assert(independent.height > 100);
        await writeFile(new URL(`${prefix}.svg`, artifacts), item.svg);
        if (item.unit === "single-column")
          await writeFile(
            new URL(`${prefix}-actual-size.png`, artifacts),
            new Resvg(item.svg).render().asPng(),
          );
        await writeFile(
          new URL(`${prefix}.png`, artifacts),
          independent.asPng(),
        );
      }
      await page.evaluate(() => {
        document.getElementById("fixture").classList.add("app");
        window.beforeEditor = JSON.stringify(window.figureSource);
        window.openEditor = () =>
          window.paint(window.fixture.PatternFigureDialog, {
            source: window.figureSource,
            initialPath: null,
            run: async (action, args, message, callback) => {
              const reply = await window.__figureSave(action, args);
              callback?.(reply);
              window.saveCompleted = (window.saveCompleted ?? 0) + 1;
            },
            onClose: () => {
              window.closedEditor = true;
              window.fixture.root.render(null);
            },
          });
        window.openEditor();
      });
      const dialog = page.getByRole("dialog", {
        name: "Export pattern figure",
        exact: true,
      });
      await dialog.waitFor();
      await page
        .getByRole("combobox", { name: "Figure size preset", exact: true })
        .selectOption("90x80");
      assert.equal(
        await page
          .getByRole("spinbutton", {
            name: "Figure font size (pt)",
            exact: true,
          })
          .inputValue(),
        "8",
      );
      await page.getByRole("tab", { name: "Phases", exact: true }).click();
      await page
        .getByRole("combobox", { name: "Figure phase legend", exact: true })
        .selectOption("auto");
      assert.equal(
        await page
          .getByTestId("pattern-figure-artwork")
          .locator('g[aria-label="Phase legend"]')
          .count(),
        1,
      );
      await page
        .getByRole("combobox", { name: "Figure phase legend", exact: true })
        .selectOption("rows");
      await page
        .getByRole("combobox", {
          name: "Figure phase tick thickness",
          exact: true,
        })
        .selectOption("uniform");
      await page
        .getByRole("combobox", {
          name: "Figure phase tick thickness",
          exact: true,
        })
        .selectOption("intensity");
      await page.screenshot({
        path: fileURLToPath(
          new URL(`${name}-single-column-editor.png`, artifacts),
        ),
      });
      await page
        .getByRole("button", { name: "Actual-size preview", exact: true })
        .click();
      const physicalTextSize = await page
        .getByTestId("pattern-figure-artwork")
        .locator("svg text")
        .first()
        .evaluate((el) => {
          const matrix = el.getScreenCTM();
          return (
            parseFloat(el.getAttribute("font-size")) *
            Math.hypot(matrix.a, matrix.b)
          );
        });
      assert(
        Math.abs(physicalTextSize - (8 * 96) / 72) < 0.1,
        "Single-column text must be 8 pt at actual size",
      );
      await page
        .getByRole("button", { name: "Actual-size preview", exact: true })
        .click();
      await page.getByRole("tab", { name: "Layout", exact: true }).click();
      await page
        .getByRole("combobox", { name: "Figure size preset", exact: true })
        .selectOption("180x115");
      assert.equal(
        await page
          .getByRole("spinbutton", {
            name: "Figure font size (pt)",
            exact: true,
          })
          .inputValue(),
        "10",
      );
      await page
        .getByRole("textbox", { name: "Figure title", exact: true })
        .fill("CeO₂ at 300 K");
      await page
        .getByRole("combobox", { name: "Curve legend position", exact: true })
        .selectOption("below");
      await page
        .getByRole("spinbutton", { name: "Figure width (mm)", exact: true })
        .fill("170");
      await page
        .getByRole("spinbutton", { name: "Figure height (mm)", exact: true })
        .fill("125");
      await page
        .getByRole("spinbutton", { name: "Figure font size (pt)", exact: true })
        .fill("11");
      await page.getByRole("tab", { name: "Curves", exact: true }).click();
      await page
        .getByRole("textbox", { name: "Figure curve 1 label", exact: true })
        .fill("Measured CeO₂");
      await page
        .getByLabel("Figure curve 1 color", { exact: true })
        .fill("#0072b2");
      await page
        .getByRole("combobox", { name: "Figure curve 1 style", exact: true })
        .selectOption("dash");
      await page
        .getByRole("spinbutton", { name: "Figure curve 1 width", exact: true })
        .fill("1.5");
      await page
        .getByRole("button", { name: "Move figure curve 1 later", exact: true })
        .click();
      await page.getByRole("tab", { name: "Phases", exact: true }).click();
      await page
        .getByRole("textbox", { name: "Figure phase 1 label", exact: true })
        .fill("CeO₂ (Fm3̅m)");
      await page.getByRole("tab", { name: "Axes", exact: true }).click();
      await page
        .getByRole("combobox", { name: "Figure horizontal range", exact: true })
        .selectOption("custom");
      await page
        .getByRole("spinbutton", {
          name: "Figure horizontal minimum",
          exact: true,
        })
        .fill("16");
      await page
        .getByRole("spinbutton", {
          name: "Figure horizontal maximum",
          exact: true,
        })
        .fill("29");
      await page
        .getByRole("combobox", { name: "Figure intensity scale", exact: true })
        .selectOption("log");
      await page
        .getByRole("textbox", { name: "Figure horizontal label", exact: true })
        .fill("2θ (°)");
      const svgBefore = await page
        .getByTestId("pattern-figure-artwork")
        .innerHTML();
      let count = await page.evaluate(() => window.saveCompleted ?? 0);
      await page
        .getByRole("button", { name: "Save figure", exact: true })
        .click();
      await page.waitForFunction((n) => window.saveCompleted > n, count);
      assert.equal(saved.at(-1).ok, true);
      const savedSvg = await readFile(
        new URL(`${name}-edited.svg`, artifacts),
        "utf8",
      );
      const normalizedSvg = await page.evaluate((svg) => {
        const div = document.createElement("div");
        div.innerHTML = svg;
        return div.innerHTML;
      }, savedSvg);
      assert.equal(normalizedSvg, svgBefore);
      // Invalid ranges cannot publish a previous valid preview.
      await page
        .getByRole("spinbutton", {
          name: "Figure horizontal maximum",
          exact: true,
        })
        .fill("10");
      await page
        .getByRole("alert")
        .filter({ hasText: "horizontal minimum" })
        .waitFor();
      assert(
        await page
          .getByRole("button", { name: "Save figure", exact: true })
          .isDisabled(),
      );
      await page
        .getByRole("spinbutton", {
          name: "Figure horizontal maximum",
          exact: true,
        })
        .fill("29");
      await page.getByRole("tab", { name: "Layout", exact: true }).click();
      await page
        .getByRole("combobox", { name: "Figure background", exact: true })
        .selectOption("transparent");
      await page
        .getByRole("combobox", { name: "Figure file format", exact: true })
        .selectOption("png");
      await page
        .getByRole("combobox", { name: "Figure PNG resolution", exact: true })
        .selectOption("150");
      count = await page.evaluate(() => window.saveCompleted ?? 0);
      await page
        .getByRole("button", { name: "Save figure", exact: true })
        .click();
      await page.waitForFunction((n) => window.saveCompleted > n, count);
      const png = await readFile(new URL(`${name}-edited.png`, artifacts));
      assert.equal(png.readUInt32BE(16), Math.round((170 / 25.4) * 150));
      assert.equal(png.readUInt32BE(20), Math.round((125 / 25.4) * 150));
      const phys = png.indexOf(Buffer.from("pHYs"));
      assert(phys > 0);
      assert.equal(png.readUInt32BE(phys + 4), Math.round(150 / 0.0254));
      assert.equal(
        await page.evaluate(async (base64) => {
          const image = new Image();
          image.src = `data:image/png;base64,${base64}`;
          await image.decode();
          const canvas = document.createElement("canvas");
          canvas.width = image.width;
          canvas.height = image.height;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(image, 0, 0);
          return ctx.getImageData(0, 0, 1, 1).data[3];
        }, png.toString("base64")),
        0,
        "Transparent PNG lost its alpha channel",
      );
      // Cancellation keeps the editor and every setting available for retry.
      canceled = true;
      await page.getByRole("button", { name: "Save as…", exact: true }).click();
      await page
        .getByRole("status")
        .filter({ hasText: "Save canceled" })
        .waitFor();
      canceled = false;
      for (const textSize of ["standard", "large"]) {
        await page.evaluate((value) => {
          document.querySelector(".app").dataset.textSize =
            value === "large" ? "large" : "normal";
        }, textSize);
        for (const tab of ["Layout", "Axes", "Curves", "Phases"]) {
          await page.getByRole("tab", { name: tab, exact: true }).click();
          const bounds = await dialog.boundingBox();
          assert(
            bounds.x >= 0 &&
              bounds.y >= 0 &&
              bounds.x + bounds.width <= 1000 &&
              bounds.y + bounds.height <= 668,
          );
          const control = page.getByRole("button", {
            name: "Save figure",
            exact: true,
          });
          assert(await control.isVisible());
          const button = await control.boundingBox();
          assert(button.y + button.height <= 668);
          assert(
            await page.evaluate(() => {
              const paper = document
                .querySelector(".pattern-figure-paper")
                .getBoundingClientRect();
              return [
                ...document.querySelectorAll(".pattern-figure-paper svg text"),
              ].every((text) => {
                const r = text.getBoundingClientRect();
                return (
                  r.left >= paper.left &&
                  r.right <= paper.right &&
                  r.top >= paper.top &&
                  r.bottom <= paper.bottom
                );
              });
            }),
            "The fit preview clips a figure label",
          );
          await page.screenshot({
            path: fileURLToPath(
              new URL(
                `${name}-${textSize}-${tab.toLowerCase()}.png`,
                artifacts,
              ),
            ),
          });
        }
      }
      await page.keyboard.press("Escape");
      await page.waitForFunction(() => window.closedEditor);
      await page.evaluate(() => {
        window.closedEditor = false;
        window.openEditor();
      });
      await dialog.waitFor();
      await page.getByRole("tab", { name: "Layout", exact: true }).click();
      assert.equal(
        await page
          .getByRole("textbox", { name: "Figure title", exact: true })
          .inputValue(),
        "CeO₂ at 300 K",
      );
      assert.equal(
        await page
          .getByRole("spinbutton", { name: "Figure width (mm)", exact: true })
          .inputValue(),
        "170",
      );
      assert(
        await page.evaluate(
          () => JSON.stringify(window.figureSource) === window.beforeEditor,
        ),
      );
      await page.evaluate(() => {
        const figure = window.fixture.patternFigure;
        const saved = figure.restorePatternFigure(window.figureSource, "svg");
        const other = {
          ...window.figureSource,
          curves: window.figureSource.curves.map((c, i) => ({
            ...c,
            name: i ? c.name : "Another sample",
          })),
        };
        const dark = { ...saved, options: { ...saved.options, theme: "dark" } };
        figure.rememberPatternFigure(window.figureSource, dark);
        const restored = figure.restorePatternFigure(other, "svg");
        if (
          restored.options.title ||
          restored.options.range !== "view" ||
          restored.options.curves[0].label !== "Another sample" ||
          restored.options.curves[0].color !== "#ffffff"
        )
          throw Error(
            "A new source inherited stale figure labels/ranges or invisible colors",
          );
        figure.rememberPatternFigure(window.figureSource, saved);
        const legacy = JSON.parse(
          localStorage.getItem("dioptas-pattern-figure-v1"),
        );
        legacy.version = 1;
        Object.assign(legacy.settings.options, {
          width: 90,
          height: 80,
          fontSize: 10,
        });
        delete legacy.settings.options.phaseLegend;
        delete legacy.settings.options.phaseTickWeight;
        localStorage.setItem(
          "dioptas-pattern-figure-v1",
          JSON.stringify(legacy),
        );
        const migrated = figure.restorePatternFigure(
          window.figureSource,
          "svg",
        );
        if (
          migrated.options.fontSize !== 8 ||
          migrated.options.phaseLegend !== "rows"
        )
          throw Error("The legacy single-column preset was not migrated");
        localStorage.setItem("dioptas-pattern-figure-v1", "invalid");
        if (
          figure.restorePatternFigure(window.figureSource, "svg").options
            .fontSize !== 10
        )
          throw Error("Invalid preferences did not fall back safely");
        const negative = {
          ...window.figureSource,
          scale: "sqrt",
          view: { ...window.figureSource.view, yMin: -0.3, yMax: 26 },
          curves: window.figureSource.curves.map((c) => ({
            ...c,
            y: c.y.map((v, i) => (i < 80 ? -5 : v)),
          })),
        };
        const options = figure.defaultPatternFigureSettings(negative).options;
        figure.renderPatternFigure(negative, options);
      });
      assert.deepEqual(errors, []);
      receipts.push({
        name,
        unitsAndScales: sourceResults.length,
        independentSvg: true,
        pngDimensionsAndDensity: true,
        settingsRestored: true,
        scientificSourceUnchanged: true,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    new URL("validation.json", artifacts),
    JSON.stringify(receipts, null, 2),
  );
  console.log(JSON.stringify(receipts));
} finally {
  await server.close();
}

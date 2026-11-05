import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile } from "node:fs/promises";
import assert from "node:assert/strict";
import { chromium, webkit } from "playwright";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../../", import.meta.url)).replace(
  /\/$/,
  "",
);
const engine = process.argv.includes("--webkit") ? "webkit" : "chromium";
const out = root + "/desktop/artifacts/integration-processing-" + engine;
await mkdir(out, { recursive: true });
const host = spawn(
  root + "/.venv/bin/python",
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
let id = 0;
const pending = new Map(),
  report = { layouts: [], commands: [], errors: [] };
host.stderr.on("data", () => {});
createInterface({ input: host.stdout }).on("line", (line) => {
  const r = JSON.parse(line);
  const t = pending.get(r.id);
  if (t) {
    clearTimeout(t.timer);
    pending.delete(r.id);
    t.resolve(r.result);
  }
});
function invoke(action, payload = {}) {
  report.commands.push({ action, payload });
  return new Promise((resolve, reject) => {
    const key = ++id;
    const timer = setTimeout(() => reject(Error(action + " timeout")), 45000);
    pending.set(key, { resolve, timer });
    host.stdin.write(JSON.stringify({ id: key, action, payload }) + "\n");
  });
}
const browser = await (engine === "webkit" ? webkit : chromium).launch({
  headless: true,
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
});
page.on("pageerror", (e) => report.errors.push(e.message));
await page.exposeFunction("__invoke", invoke);
await page.addInitScript(() => {
  window.pywebview = {
    api: {
      invoke: async (a, p) => {
        window.__pending = (window.__pending ?? 0) + 1;
        try {
          return await window.__invoke(a, p);
        } finally {
          window.__pending--;
        }
      },
    },
  };
});
const ready = async () => {
  await page.waitForFunction(
    () =>
      !window.__pending &&
      !document.querySelector(".spin") &&
      document.querySelector('[data-testid="pattern-canvas"]')?.dataset
        .regionUpdating !== "true",
  );
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
};
const type = (kind, name) =>
  page
    .getByRole("navigation", { name: kind + " type" })
    .getByRole("button", { name, exact: true });
const field = (name) => page.getByLabel(name, { exact: true });
const button = (name) => page.getByRole("button", { name, exact: true });
const state = async () => (await invoke("state")).state;
async function capture(name) {
  await ready();
  const measured = {
    name,
    ...(await page.locator(".integration-controls").evaluate((el) => {
      const area = el.getBoundingClientRect();
      const form = el.querySelector(
        ".processing-pane:not([hidden]) .processing-page",
      );
      return {
        area: { x: area.x, y: area.y, width: area.width, height: area.height },
        scroll: {
          width: form.clientWidth,
          height: form.clientHeight,
          contentWidth: form.scrollWidth,
          contentHeight: form.scrollHeight,
        },
        overlaps: [
          ...el.querySelectorAll(
            ".processing-pane:not([hidden]) .processing-form .field-label",
          ),
        ].some((label) => {
          const text = label.querySelector("span"),
            input = label.querySelector("input");
          return (
            text &&
            text.getBoundingClientRect().right >
              input.getBoundingClientRect().left + 1
          );
        }),
        rangeVisible: (() => {
          const input = el.querySelector('[aria-label="Background maximum"]');
          return (
            !input ||
            input.getBoundingClientRect().bottom <=
              form.getBoundingClientRect().bottom + 1
          );
        })(),
        fields: [...el.querySelectorAll("input")]
          .filter((i) => i.offsetParent)
          .map((i) => ({
            label: i.ariaLabel,
            value: i.value,
            width: i.getBoundingClientRect().width,
            invalid: !i.validity.valid,
          })),
        text: el.innerText,
      };
    })),
  };
  report.layouts.push(measured);
  assert.ok(
    measured.scroll.contentWidth <= measured.scroll.width + 1,
    name + ": no horizontal overflow",
  );
  assert.equal(
    measured.overlaps,
    false,
    name + ": labels do not overlap inputs",
  );
  assert.equal(
    measured.rangeVisible,
    true,
    name + ": both range bounds visible",
  );
  if (name === "1440-normal-cBNseat")
    assert.ok(
      measured.scroll.contentHeight <= measured.scroll.height + 1,
      "cBN fits without scrolling",
    );
  await page
    .locator(".integration-controls")
    .screenshot({ path: out + "/" + name + ".png" });
}
try {
  for (const [a, p] of [
    ["example", {}],
    [
      "open_calibration",
      { path: root + "/dioptas/tests/data/CeO2_Pilatus1M.poni" },
    ],
  ]) {
    const r = await invoke(a, p);
    if (!r.ok) throw Error(r.error);
  }
  await page.goto("file://" + root + "/dioptas/desktop/ui/index.html");
  await ready();
  await page.getByRole("button", { name: "Integration", exact: true }).click();
  await ready();
  for (const [w, h, size] of [
    [1440, 1000, "normal"],
    [1000, 760, "normal"],
    [1000, 760, "large"],
  ]) {
    await page.setViewportSize({ width: w, height: h });
    await page
      .locator(".app")
      .evaluate((el, s) => (el.dataset.textSize = s), size);
    await page.getByRole("tab", { name: "Background", exact: true }).click();
    await capture(`${w}-${size}-pattern-background`);
    await page.getByLabel("Limit background range", { exact: true }).check();
    await capture(`${w}-${size}-background-range`);
    await page.getByLabel("Limit background range", { exact: true }).uncheck();
    await type("Background", "Image").click();
    await capture(`${w}-${size}-image-background`);
    await type("Background", "Pattern").click();
    await page.getByRole("tab", { name: "Corrections", exact: true }).click();
    for (const name of ["Flat field", "cBN seat", "Detector absorption"]) {
      await page.getByRole("button", { name, exact: true }).click();
      await capture(`${w}-${size}-${name.replaceAll(/[^a-zA-Z]/g, "")}`);
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator(".app").evaluate((el) => (el.dataset.textSize = "normal"));
  await type("Correction", "cBN seat").click();
  await field("Diamond thickness (mm)").fill("2.1");
  await field("Diamond thickness (mm)").press("Enter");
  await ready();
  assert.equal(
    (await state()).integration.corrections.cbn.enabled,
    false,
    "Inactive parameter edits do not apply a correction",
  );
  await page.getByRole("tab", { name: "Background", exact: true }).click();
  await page.getByRole("tab", { name: "Corrections", exact: true }).click();
  assert.equal(
    await field("Diamond thickness (mm)").inputValue(),
    "2.1",
    "Prepared parameters survive navigation",
  );
  await field("Apply cBN seat").check();
  await ready();
  assert.equal((await state()).integration.corrections.cbn.enabled, true);
  assert.equal(
    (await state()).integration.corrections.cbn.parameters.diamond_thickness,
    2.1,
  );
  await field("Diamond thickness (mm)").fill("2.2");
  await field("Diamond thickness (mm)").press("Tab");
  await field("Seat thickness (mm)").fill("5.2");
  await field("Seat thickness (mm)").press("Enter");
  await ready();
  assert.equal(
    (await state()).integration.corrections.cbn.parameters.diamond_thickness,
    2.2,
  );
  assert.equal(
    (await state()).integration.corrections.cbn.parameters.seat_thickness,
    5.2,
  );
  await field("Diamond thickness (mm)").fill("");
  await field("Diamond thickness (mm)").press("Tab");
  await ready();
  assert.equal(
    (await state()).integration.corrections.cbn.parameters.diamond_thickness,
    2.2,
  );
  await field("Diamond thickness (mm)").fill("99");
  await field("Diamond thickness (mm)").press("Escape");
  await ready();
  assert.equal(await field("Diamond thickness (mm)").inputValue(), "2.2");
  await field("Small seat radius (mm)").fill("3");
  await field("Small seat radius (mm)").press("Enter");
  await ready();
  assert.equal(
    (await state()).integration.corrections.cbn.parameters
      .small_cbn_seat_radius,
    0.5,
  );
  assert.equal(await field("Small seat radius (mm)").inputValue(), "0.5");
  assert.ok(
    (await page.getByRole("alert").allTextContents()).some((t) =>
      t.includes("Small seat radius"),
    ),
  );
  await type("Correction", "Detector absorption").click();
  await field("Apply detector absorption").check();
  await ready();
  assert.equal((await state()).integration.corrections.oiadac.enabled, true);
  assert.equal((await state()).integration.corrections.cbn.enabled, true);
  assert.equal(
    await type("Correction", "cBN seat")
      .getByRole("img", { name: "Active", exact: true })
      .count(),
    1,
  );
  await page.getByRole("tab", { name: "Background", exact: true }).click();
  await type("Background", "Image").click();
  assert.equal(await field("Image background scale").isDisabled(), true);
  await button("Load background…").click();
  await ready();
  const count = report.commands.filter(
    (c) => c.action === "integration_image_background",
  ).length;
  await field("Image background scale").fill("0.25");
  assert.equal(
    report.commands.filter((c) => c.action === "integration_image_background")
      .length,
    count,
  );
  await field("Image background scale").press("Tab");
  await field("Image background offset").fill("3");
  await field("Image background offset").press("Enter");
  await ready();
  assert.equal((await state()).integration.imageBackground.scale, 0.25);
  assert.equal((await state()).integration.imageBackground.offset, 3);
  await capture("loaded-image-background");
  await type("Background", "Pattern").click();
  await field("Subtract automatic pattern background").check();
  await ready();
  await field("Smooth width").fill("0.2");
  await field("Iterations").fill("10");
  await field("Polynomial order").fill("5");
  await ready();
  assert.equal((await state()).integration.patternBackground.order, 5);
  const revision = (await state()).revision;
  await button("Inspect background").click();
  await ready();
  assert.equal(
    await button("Inspect pattern background").getAttribute("aria-pressed"),
    "true",
  );
  assert.equal((await state()).revision, revision);
  await field("Limit background range").check();
  await ready();
  await field("Background minimum").fill("2");
  await field("Background maximum").fill("10");
  await ready();
  assert.deepEqual(
    (await state()).integration.patternBackground.range,
    [2, 10],
  );
  await field("Background minimum").fill("11");
  await ready();
  assert.deepEqual(
    (await state()).integration.patternBackground.range,
    [2, 10],
  );
  assert.equal(
    await page.getByRole("alert").textContent(),
    "Minimum must be below maximum.",
  );
  await field("Background maximum").fill("12");
  await ready();
  assert.deepEqual(
    (await state()).integration.patternBackground.range,
    [11, 12],
  );
  await button("Pattern unit Q").click();
  await ready();
  assert.equal(
    await page.locator(".processing-range-unit").textContent(),
    "Q · Å⁻¹",
  );
  await capture("enabled-pattern-background");
  assert.deepEqual(report.errors, []);
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
  await page.screenshot({ path: out + "/full-workspace.png" });
} finally {
  await writeFile(out + "/report.json", JSON.stringify(report, null, 2));
  await browser.close();
  host.stdin.end();
  host.kill();
}
console.log(
  JSON.stringify(
    { out, errors: report.errors, layouts: report.layouts.length },
    null,
    2,
  ),
);

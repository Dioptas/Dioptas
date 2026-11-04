import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium, webkit } from "playwright";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = root + "/desktop/artifacts";
await mkdir(artifacts, { recursive: true });
const host = spawn(
  root + "/.venv/bin/python",
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
let nextId = 0;
const pending = new Map();
const logs = [];
host.stderr.on("data", (d) => logs.push(d.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  try {
    const r = JSON.parse(line);
    const p = pending.get(r.id);
    if (p) {
      clearTimeout(p.timer);
      pending.delete(r.id);
      p.resolve(r.result);
    }
  } catch {
    logs.push(line);
  }
});
const invoke = (action, payload = {}) =>
  new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(Error(`Timeout: ${action}`));
    }, 45000);
    pending.set(id, { resolve, reject, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
const call = async (action, payload = {}) => {
  const r = await invoke(action, payload);
  assert.equal(r.ok, true, r.error);
  return r;
};
let browser;
try {
  await call("example");
  await call("open_calibration", {
    path: root + "/dioptas/tests/data/CeO2_Pilatus1M.poni",
  });
  await call("integration_settings", { bins: 160, cake_bins: 30 });
  await call("integration_overlay", { operation: "capture" });
  browser = await (
    process.argv.includes("--webkit") ? webkit : chromium
  ).launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let delayed = false;
  let incompleteSearch = true;
  const requests = [];
  await page.exposeFunction("__dioptasInvoke", async (action, payload) => {
    requests.push({ action, payload });
    if (
      incompleteSearch &&
      action === "integration_phase_catalog" &&
      payload.query === "unavailable"
    ) {
      incompleteSearch = false;
      return { ok: true };
    }
    if (action === "integration_phase_documentation") return { ok: true };
    const result = await invoke(action, payload);
    if (
      delayed &&
      action === "integration_phase_catalog" &&
      payload.query === "Au"
    )
      await new Promise((resolve) => setTimeout(resolve, 500));
    return result;
  });
  await page.addInitScript(() => {
    localStorage.setItem("dioptas-phase-recent", '{"unexpected":true}');
    localStorage.setItem("dioptas-phase-favourites", '"invalid"');
    window.pywebview = {
      api: { invoke: (a, p) => window.__dioptasInvoke(a, p) },
    };
  });
  const ready = async () => {
    await page.waitForFunction(
      () =>
        !!document.querySelector(".app") && !document.querySelector(".spin"),
    );
    assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
  };
  const click = async (label) => {
    await page.getByRole("button", { name: label, exact: true }).click();
    await ready();
  };
  await page.goto("file://" + root + "/dioptas/desktop/ui/index.html");
  await page.getByRole("button", { name: "Integration", exact: true }).click();
  await ready();
  await page.getByRole("tab", { name: "Phase", exact: true }).click();
  const all = (await call("integration_phase_catalog")).phaseCatalog;
  const gold = all.find((m) => m.id === "gold");
  const db = page.getByRole("dialog", {
    name: "EoS Material Database",
    exact: true,
  });
  const materialTable = db.getByRole("table", {
    name: "Database materials",
    exact: true,
  });
  const recordTable = db.getByRole("table", {
    name: "Material EoS records",
    exact: true,
  });
  const open = async () => {
    await click("Browse EoS Material Database");
    await db.waitFor();
    assert.equal(
      await page
        .getByLabel("Search materials", { exact: true })
        .evaluate((e) => e === document.activeElement),
      true,
    );
  };
  const query = async (text) => {
    await page.getByLabel("Search materials", { exact: true }).fill(text);
    await db
      .locator('section[aria-label="Material results"][aria-busy="false"]')
      .waitFor();
    await ready();
  };
  const select = async (material) =>
    materialTable
      .getByRole("cell", { name: material.name, exact: true })
      .click();
  const selectedRecord = () =>
    recordTable.locator('tbody tr[aria-selected="true"]');
  const loadButton = db.getByRole("button", {
    name: "Load as Phase",
    exact: true,
  });
  await open();
  const materialPane = db.locator('section[aria-label="Material results"]');
  const initialPane = await materialPane.boundingBox();
  const initialSpaceGroup = await materialTable
    .locator("th")
    .last()
    .boundingBox();
  const checkFixedPane = async () => {
    assert.equal((await materialPane.boundingBox()).height, initialPane.height);
    assert.equal(
      (await materialTable.locator("th").last().boundingBox()).x,
      initialSpaceGroup.x,
    );
  };
  assert.equal(
    await db
      .getByRole("tablist", { name: "Material views" })
      .getByRole("tab")
      .first()
      .textContent(),
    "All",
  );
  assert.equal(await db.getByRole("checkbox").count(), 0);
  assert.equal(
    await db.getByRole("button", { name: "Clear", exact: true }).count(),
    0,
  );
  assert.deepEqual(await materialTable.locator("th").allTextContents(), [
    "Material",
    "Space group",
  ]);
  assert.deepEqual(
    await materialTable.locator("tbody tr td:first-child").allTextContents(),
    all.filter((m) => m.diffraction).map((m) => m.name),
  );
  await page
    .getByLabel("Search materials", { exact: true })
    .fill("unavailable");
  await db.getByRole("button", { name: "Retry search", exact: true }).waitFor();
  const attempts = requests.filter(
    (r) =>
      r.action === "integration_phase_catalog" &&
      r.payload.query === "unavailable",
  ).length;
  await page.waitForTimeout(450);
  assert.equal(
    requests.filter(
      (r) =>
        r.action === "integration_phase_catalog" &&
        r.payload.query === "unavailable",
    ).length,
    attempts,
  );
  await db.getByRole("button", { name: "Retry search", exact: true }).click();
  await db
    .locator('section[aria-label="Material results"][aria-busy="false"]')
    .waitFor();
  assert.equal(await loadButton.isDisabled(), true);
  // Changing the query while a real backend result is delayed must not show
  // or load the old query's material, and must resume once the worker is free.
  delayed = true;
  await page.getByLabel("Search materials", { exact: true }).fill("Au");
  await page.waitForFunction(() => !!document.querySelector(".spin"));
  await page.getByLabel("Search materials", { exact: true }).fill("MgFe");
  assert.equal(await loadButton.isDisabled(), true);
  await db
    .locator('section[aria-label="Material results"][aria-busy="false"]')
    .waitFor();
  await ready();
  delayed = false;
  const ranked = (
    await call("integration_phase_catalog", { query: "MgFe" })
  ).phaseCatalog.filter((m) => m.diffraction);
  assert.deepEqual(
    await materialTable.locator("tbody tr td:first-child").allTextContents(),
    ranked.map((m) => m.name),
  );
  await query("gold");
  await select(gold);
  assert.equal(
    await recordTable.locator("tbody tr").count(),
    gold.references.length,
  );
  assert.deepEqual(await recordTable.locator("th").allTextContents(), [
    "Reference",
    "EoS",
    "Thermal",
    "Fit P range",
    "Variant",
  ]);
  assert.equal(await db.locator(".phase-database-inspector, pre").count(), 0);
  assert.equal(
    await db
      .getByRole("tab", { name: "Assessment & source", exact: true })
      .count(),
    0,
  );
  assert.equal(
    await db
      .getByRole("columnheader", { name: "K₀ (GPa)", exact: true })
      .count(),
    0,
  );
  await checkFixedPane();
  for (const [index, reference] of gold.references.entries()) {
    const row = recordTable.locator(`tr[data-reference="${index}"]`);
    assert.equal(
      await row.locator("td").nth(2).textContent(),
      reference.thermal ? "✓" : "—",
    );
    assert.equal(
      await row.locator("td").nth(2).getAttribute("title"),
      reference.thermal || "No thermal model",
    );
    assert.equal(
      await row.locator("td").nth(3).textContent(),
      reference.pressureRange || "—",
    );
  }
  const sameCitation = gold.references
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => r.authors === "Dewaele" && r.year === "2019");
  assert.equal(sameCitation.length, 2);
  const variants = await Promise.all(
    sameCitation.map(({ i }) =>
      recordTable
        .locator(`tr[data-reference="${i}"] td:last-child`)
        .textContent(),
    ),
  );
  assert.ok(variants[0] !== variants[1] && variants.every(Boolean));
  await db.getByRole("button", { name: "Peritheos ↗", exact: true }).click();
  await ready();
  assert.equal(requests.at(-1).payload.reference, gold.defaultReference);
  await db
    .getByRole("button", { name: "Add to favourites", exact: true })
    .click();
  const star = db.getByRole("button", {
    name: "Remove from favourites",
    exact: true,
  });
  assert.equal(await star.getAttribute("aria-pressed"), "true");
  assert.equal(await star.textContent(), "");
  assert.equal(await star.locator("svg").count(), 1);
  await db.getByRole("tab", { name: "Favourites", exact: true }).click();
  assert.equal(await materialTable.locator("tbody tr").count(), 1);
  // Use the native search-field clear icon; there is no duplicate Clear action.
  const searchInput = page.getByLabel("Search materials", { exact: true });
  await searchInput.focus();
  const searchBounds = await searchInput.boundingBox();
  await searchInput.click({
    position: { x: searchBounds.width - 14, y: searchBounds.height / 2 },
  });
  assert.equal(await searchInput.inputValue(), "");
  await db
    .locator('section[aria-label="Material results"][aria-busy="false"]')
    .waitFor();
  await checkFixedPane();
  assert.equal(
    await db
      .getByRole("tab", { name: "Favourites", exact: true })
      .getAttribute("aria-selected"),
    "true",
  );
  // A search starts across the library; clearing it restores the chosen view.
  await query("MgFe");
  assert.equal(
    await db
      .getByRole("tab", { name: "All", exact: true })
      .getAttribute("aria-selected"),
    "true",
  );
  const expected = (
    await call("integration_phase_catalog", { query: "MgFe" })
  ).phaseCatalog.filter((m) => m.diffraction);
  assert.deepEqual(
    await materialTable.locator("tbody tr td:first-child").allTextContents(),
    expected.map((m) => m.name),
  );
  await query("");
  assert.equal(
    await db
      .getByRole("tab", { name: "Favourites", exact: true })
      .getAttribute("aria-selected"),
    "true",
  );
  await query("no such material xyz");
  await checkFixedPane();
  assert.equal(await materialTable.locator("tbody tr").count(), 0);
  assert.equal(await recordTable.locator("tbody tr").count(), 0);
  assert.equal(await loadButton.isDisabled(), true);
  assert.equal(
    await db
      .getByRole("button", { name: "Export .eosmat…", exact: true })
      .isDisabled(),
    true,
  );
  assert.equal(
    await db.getByRole("button", { name: "Peritheos ↗", exact: true }).count(),
    0,
  );
  await query("palladium");
  const palladium = all.find((m) => m.id === "palladium");
  await select(palladium);
  assert.equal(await selectedRecord().count(), 0);
  assert.equal(await loadButton.isDisabled(), true);
  await recordTable.getByRole("button", { name: "EoS", exact: true }).click();
  assert.equal(await selectedRecord().count(), 0);
  assert.equal(await loadButton.isDisabled(), true);
  const explicit = palladium.references.findIndex((r) => !r.loadError);
  await recordTable.locator(`tr[data-reference="${explicit}"]`).click();
  assert.equal(await loadButton.isEnabled(), true);
  await db.getByRole("button", { name: "Peritheos ↗", exact: true }).click();
  await ready();
  assert.equal(requests.at(-1).payload.reference, explicit);
  await recordTable
    .getByRole("button", { name: "Reference", exact: true })
    .click();
  assert.equal(
    await selectedRecord().getAttribute("data-reference"),
    String(explicit),
  );
  await recordTable
    .getByRole("button", { name: "Thermal", exact: true })
    .click();
  assert.equal(
    await selectedRecord().getAttribute("data-reference"),
    String(explicit),
  );
  await recordTable
    .getByRole("button", { name: "Fit P range", exact: true })
    .click();
  assert.equal(
    await selectedRecord().getAttribute("data-reference"),
    String(explicit),
  );
  // Enter loads the identity selected before sorting, not the visible row number.
  await selectedRecord().press("Enter");
  await ready();
  assert.equal(
    (await call("state")).state.integration.phases.at(-1).reference,
    explicit,
  );
  await open();
  await db.getByRole("tab", { name: "Recent", exact: true }).click();
  assert.equal(
    await materialTable
      .locator("tbody tr td:first-child")
      .first()
      .textContent(),
    palladium.name,
  );
  await query("gold");
  await select(gold);
  assert.equal(
    await db
      .getByRole("tablist", { name: "Record inspection", exact: true })
      .count(),
    0,
  );
  for (const large of [false, true]) {
    // The dialog stays usable when the app's existing text setting changes.
    await db.getByRole("button", { name: "Close", exact: true }).click();
    await setInterfaceTextSize(page, large);
    await open();
    await query("gold");
    await select(gold);
    for (const [width, height] of [
      [1440, 1000],
      [1000, 668],
      [800, 600],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(80);
      const metrics = await db.evaluate((el) => {
        const area = el.getBoundingClientRect();
        const row = el.querySelector(
          '.phase-database-records tr[aria-selected="true"]',
        );
        const bounds = row.getBoundingClientRect();
        const scroll = row
          .closest(".data-table-scroll")
          .getBoundingClientRect();
        return {
          width: area.width,
          height: area.height,
          inWindow:
            area.left >= 0 &&
            area.right <= innerWidth &&
            area.top >= 0 &&
            area.bottom <= innerHeight,
          selectedVisible:
            bounds.top >= scroll.top + 27 && bounds.bottom <= scroll.bottom + 1,
          footerVisible: [...el.querySelectorAll("footer button")].every(
            (b) => {
              const r = b.getBoundingClientRect();
              return r.top >= area.top && r.bottom <= area.bottom;
            },
          ),
          noHorizontalRecordScroll:
            row.closest(".data-table-scroll").scrollWidth <=
            row.closest(".data-table-scroll").clientWidth + 1,
          headerSticky:
            getComputedStyle(row.closest("table").querySelector("thead"))
              .position === "sticky",
        };
      });
      assert.ok(
        metrics.inWindow &&
          metrics.footerVisible &&
          metrics.headerSticky &&
          metrics.selectedVisible &&
          metrics.noHorizontalRecordScroll,
        JSON.stringify(metrics),
      );
      // The focused source record must remain reachable by keyboard after resizing.
      await selectedRecord().focus();
      await selectedRecord().press("Home");
      assert.equal(
        await recordTable.locator('tbody tr[aria-selected="true"]').count(),
        1,
      );
      await page.screenshot({
        path:
          artifacts +
          `/phase-database-${width}-${large ? "large" : "normal"}.png`,
      });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Phase browsing excludes EoS-only and assumption-only materials in every view.
  await query("coesite");
  assert.deepEqual(
    await materialTable.locator("tbody tr td:first-child").allTextContents(),
    all
      .filter((m) => m.diffraction && m.name.toLowerCase().includes("coesite"))
      .map((m) => m.name),
  );
  await query("CaSiO3");
  const unavailable = all.filter((m) => !m.diffraction);
  const visibleNames = await materialTable
    .locator("tbody tr td:first-child")
    .allTextContents();
  assert.ok(unavailable.every((m) => !visibleNames.includes(m.name)));
  await query("gold");
  await select(gold);
  await db
    .getByRole("button", { name: "Export .eosmat…", exact: true })
    .click();
  await ready();
  assert.equal(await db.isVisible(), true);
  await db.getByRole("button", { name: "Close", exact: true }).click();
  await open();
  await query("gold");
  await select(gold);
  await page.getByLabel("Search materials", { exact: true }).press("ArrowDown");
  await materialTable.locator('tbody tr[aria-selected="true"]').press("End");
  await page.keyboard.press("Control+f");
  assert.equal(
    await page
      .getByLabel("Search materials", { exact: true })
      .evaluate((e) => e === document.activeElement),
    true,
  );
  await page.keyboard.press("Escape");
  await db.waitFor({ state: "detached" });
  assert.deepEqual(errors, []);
  await writeFile(
    artifacts +
      `/phase-database-${process.argv.includes("--webkit") ? "webkit" : "chromium"}.json`,
    JSON.stringify(
      {
        ok: true,
        materials: all.length,
        records: all.reduce((n, m) => n + m.references.length, 0),
        checks: [
          "ranked formula search",
          "favourites",
          "view restoration",
          "empty states",
          "held defaults",
          "sorted identity and Enter load",
          "concise reference-first records",
          "external documentation links",
          "distinct same-author variants",
          "recent load order",
          "diffraction-capable materials only",
          "fixed material pane height",
          "icon-only favourite toggle",
          "native search clear",
          "thermal model and source pressure ranges",
          "compact and larger-text layouts",
          "focus and keyboard",
        ],
      },
      null,
      2,
    ),
  );
  console.log(
    "Database explorer passed: real-record search, concise record selection, sorting, safeguards, loading, keyboard and compact layouts.",
  );
} catch (error) {
  console.error(error);
  throw error;
} finally {
  await browser?.close();
  host.stdin.end();
  await writeFile(artifacts + "/phase-database.log", logs.join(""));
}

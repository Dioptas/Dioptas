import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, webkit } from "playwright";
const root = fileURLToPath(new URL("../../", import.meta.url));
const legacyIcons = process.argv.includes("--legacy-icons");
const limitedIcons = process.argv.includes("--limited-icons");
const iconMode = legacyIcons ? "legacy" : limitedIcons ? "limited" : "current";
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-commands-"));
const settings = path.join(temp, "commands.json");
const output = path.join(temp, "result with spaces.json");
const script = path.join(temp, "lookup tool.py");
await writeFile(
  script,
  "import sys,json,time\ntime.sleep(0.7)\nopen(sys.argv[1], 'w').write(json.dumps(sys.argv[2:]))\nprint('Motor lookup complete', flush=True)\n",
);
const host = spawn(
  path.join(root, ".venv/bin/python"),
  ["-u", "desktop/scripts/bridge_host.py"],
  {
    cwd: root,
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env, DIOPTAS_CUSTOM_COMMANDS_FILE: settings },
  },
);
let nextId = 0;
const pending = new Map(),
  logs = [];
host.stderr.on("data", (data) => logs.push(data.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  const { id, result } = JSON.parse(line),
    task = pending.get(id);
  if (task) {
    clearTimeout(task.timer);
    pending.delete(id);
    task.resolve(result);
  }
});
function invoke(action, payload = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(Error(`Timed out: ${action}`));
    }, 30000);
    pending.set(id, { timer, resolve, reject });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
}
const browser = await (
  process.argv.includes("--webkit") ? webkit : chromium
).launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
const observedRequests = [];
let rejectNextMutation = false;
page.on("pageerror", (error) => errors.push(error.message));
await page.exposeFunction("__dioptasInvoke", async (action, payload = {}) => {
  observedRequests.push({ action, operation: payload.operation });
  if (
    action === "custom_command" &&
    ["save", "delete"].includes(payload.operation) &&
    rejectNextMutation
  ) {
    rejectNextMutation = false;
    return { ok: false, error: "Injected action settings failure." };
  }
  if (action === "custom_command" && payload.operation === "save") {
    if (limitedIcons && payload.command.icon !== "terminal")
      return { ok: false, error: "Choose an available command icon." };
    if (legacyIcons) {
      payload = { ...payload, command: { ...payload.command } };
      delete payload.command.icon;
    }
  }
  const result = await invoke(action, payload);
  if (action === "custom_command" && legacyIcons && result.customCommands)
    result.customCommands = result.customCommands.map(
      ({ icon, ...command }) => command,
    );
  return result;
});
await page.addInitScript(() => {
  window.pywebview = {
    api: {
      invoke: async (action, payload) => {
        window.__pendingCommands = (window.__pendingCommands ?? 0) + 1;
        try {
          return await window.__dioptasInvoke(action, payload);
        } finally {
          window.__pendingCommands--;
        }
      },
    },
  };
});
const ready = () =>
  page.waitForFunction(
    () =>
      !window.__pendingCommands &&
      !document.querySelector('.custom-command-settings[aria-busy="true"]') &&
      !document.querySelector('.app-status [role="alert"]')?.textContent.trim(),
  );
const button = (name) => page.getByRole("button", { name, exact: true });
const panel = () =>
  page.getByRole("tabpanel", { name: "Custom actions", exact: true });
const openSettings = async () => {
  await button("Settings").click();
  await page.getByRole("tab", { name: "Custom actions", exact: true }).click();
  await page.waitForFunction(() =>
    document
      .querySelector('[aria-label="Undo"]')
      ?.getAttribute("title")
      ?.startsWith("Undo:"),
  );
};
const save = async () => {
  await button("Save action").click();
  await page.getByText("Action saved.", { exact: true }).waitFor();
};
const openIconPicker = async () => {
  await page.getByRole("button", { name: /^Change action icon:/ }).click();
  await page
    .getByRole("dialog", { name: "Button icon", exact: true })
    .waitFor();
};
const selectIcon = async (label) => {
  await openIconPicker();
  await page
    .getByRole("searchbox", { name: "Search action icons" })
    .fill(label);
  await button(`Use ${label} icon`).click();
};
const historyStep = async (name) => {
  await button(name).click();
  await ready();
};
const savedActions = async () =>
  JSON.parse(await readFile(settings, "utf8")).commands;
const runCount = () =>
  observedRequests.filter(
    ({ action, operation }) =>
      action === "custom_command" && operation === "run",
  ).length;
const modifier = process.platform === "darwin" ? "Meta" : "Control";
try {
  await page.goto("file://" + path.join(root, "dioptas/desktop/ui/index.html"));
  await ready();
  await openSettings();
  assert.equal(await button("Undo").isDisabled(), true);
  assert.equal(await button("Redo").isDisabled(), true);
  await button("Add action").click();
  assert.equal(await page.locator(".custom-command-icon-grid").count(), 0);
  await openIconPicker();
  assert.equal(
    await page.locator(".custom-command-icon-grid button").count(),
    57,
  );
  assert.equal(
    await button("Use Terminal icon").getAttribute("aria-pressed"),
    "true",
  );
  await page
    .getByRole("searchbox", { name: "Search action icons" })
    .fill("Microscope");
  await button("Use Microscope icon").click();
  const nameField = page.getByLabel("Button name", { exact: true });
  const longName = "A very long descriptive command name";
  await nameField.fill(longName);
  const preview = page.getByLabel("Sidebar button preview");
  assert.equal(await preview.getAttribute("title"), longName);
  assert.equal(
    await preview
      .locator("span")
      .evaluate((node) => getComputedStyle(node).webkitLineClamp),
    "2",
  );
  assert.ok(
    (await preview.boundingBox()).width <
      (await page.locator(".mode-navigation").boundingBox()).width,
  );
  assert.ok((await nameField.boundingBox()).width < 240);
  await page.getByLabel("Button name", { exact: true }).fill("Motor positions");
  await page
    .getByLabel("Program or executable script")
    .fill(path.join(root, ".venv/bin/python"));
  await page
    .getByLabel("Arguments · one per line")
    .fill([script, output, "{image_path}", "{frame_index}"].join("\n"));
  await save();
  const createdAction = (await savedActions())[0];
  assert.match(await button("Undo").getAttribute("title"), /Create action/);
  rejectNextMutation = true;
  await historyStep("Undo");
  await page
    .getByText("Injected action settings failure.", { exact: true })
    .waitFor();
  assert.equal((await savedActions()).length, 1);
  assert.equal(await button("Undo").isEnabled(), true);
  assert.equal(await button("Redo").isDisabled(), true);
  await historyStep("Undo");
  assert.deepEqual(await savedActions(), []);
  assert.equal(await button("Run Motor positions").count(), 0);
  await historyStep("Redo");
  assert.deepEqual((await savedActions())[0], createdAction);
  await panel()
    .getByRole("button", { name: "Motor positions", exact: true })
    .click();
  await page.getByLabel("Button name", { exact: true }).press("End");
  await page.getByLabel("Button name", { exact: true }).pressSequentially("!");
  assert.equal(await button("Undo").isDisabled(), true);
  await page.getByLabel("Button name", { exact: true }).press(`${modifier}+z`);
  assert.equal(
    await page.getByLabel("Button name", { exact: true }).inputValue(),
    "Motor positions",
  );
  assert.deepEqual((await savedActions())[0], createdAction);
  await button("Cancel").click();
  await page.waitForFunction(
    () => !document.querySelector('[aria-label="Undo"]').disabled,
  );
  await button("Undo").focus();
  await page.keyboard.press(`${modifier}+z`);
  await ready();
  assert.deepEqual(await savedActions(), []);
  await page.waitForFunction(
    () => !document.querySelector('[aria-label="Redo"]').disabled,
  );
  await page.keyboard.press(`${modifier}+Shift+z`);
  await ready();
  await button("Run Motor positions").waitFor();
  assert.equal((await savedActions())[0].id, createdAction.id);
  assert.equal(runCount(), 0);
  await button("Close settings").click();
  await openSettings();
  assert.match(await button("Undo").getAttribute("title"), /Create action/);
  assert.match(
    await button("Run Motor positions").locator("svg").getAttribute("class"),
    /lucide-microscope/,
  );
  assert.equal(await button("Run Motor positions").isDisabled(), true);
  assert.equal(JSON.parse(await readFile(settings, "utf8")).commands.length, 1);
  await button("Close settings").click();
  await button("Open image").click();
  await ready();
  await page.waitForFunction(
    () =>
      document.querySelector('[aria-label="Run Motor positions"]')?.disabled ===
      false,
  );
  await button("Run Motor positions").click();
  await page.waitForFunction(
    () => !!document.querySelector('[aria-label="Run Motor positions"] .spin'),
  );
  assert.equal(await button("Integration").isEnabled(), true);
  assert.equal((await invoke("state")).ok, true);
  await openSettings();
  await page.getByText("Motor positions · Finished", { exact: true }).waitFor();
  assert.match(await button("Undo").getAttribute("title"), /Create action/);
  assert.equal(runCount(), 1);
  assert.deepEqual(JSON.parse(await readFile(output, "utf8")), [
    path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
    "0",
  ]);
  assert.match(
    await page.getByLabel("Motor positions output").innerText(),
    /Motor lookup complete/,
  );
  await panel()
    .getByRole("button", { name: "Motor positions", exact: true })
    .click();
  await button("Calibration path").click();
  await save();
  const editedAction = (await savedActions())[0];
  assert.match(await button("Undo").getAttribute("title"), /Edit action/);
  await historyStep("Undo");
  assert.equal(
    (await savedActions())[0].arguments.includes("{calibration_path}"),
    false,
  );
  assert.equal(await button("Run Motor positions").isEnabled(), true);
  await historyStep("Redo");
  assert.deepEqual((await savedActions())[0], editedAction);
  assert.equal(runCount(), 1);
  assert.equal(await button("Run Motor positions").isDisabled(), true);
  assert.match(
    await button("Run Motor positions").getAttribute("title"),
    /Calibration path unavailable/,
  );
  assert.equal(
    (
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      })
    ).ok,
    true,
  );
  await page.reload();
  await ready();
  await page.waitForFunction(
    () =>
      document.querySelector('[aria-label="Run Motor positions"]')?.disabled ===
      false,
  );
  await openSettings();
  const scienceBefore = (await invoke("state")).state;
  assert.equal(scienceBefore.canUndoMask, true);
  assert.equal(await button("Undo").isDisabled(), true);
  await page.getByRole("tab", { name: "General", exact: true }).click();
  assert.match(await button("Undo").getAttribute("title"), /calibration edit/);
  await page.getByRole("tab", { name: "Custom actions", exact: true }).click();
  assert.equal(await button("Undo").isDisabled(), true);
  assert.deepEqual(
    (await invoke("state")).state.geometry,
    scienceBefore.geometry,
  );
  assert.equal(
    observedRequests.filter(({ action }) =>
      [
        "undo_calibration",
        "redo_calibration",
        "undo_mask",
        "redo_mask",
      ].includes(action),
    ).length,
    0,
  );
  await panel()
    .getByRole("button", { name: "Motor positions", exact: true })
    .click();
  await page.getByText("Current input values", { exact: true }).click();
  await openIconPicker();
  assert.equal(
    await button("Use Microscope icon").getAttribute("aria-pressed"),
    "true",
  );
  const iconSearch = page.getByRole("searchbox", {
    name: "Search action icons",
  });
  await iconSearch.fill("arrow");
  assert.equal(
    await page.locator(".custom-command-icon-grid button").count(),
    10,
  );
  await iconSearch.press("ArrowDown");
  await page
    .locator(".custom-command-icon-grid button:focus")
    .press("ArrowRight");
  await page.locator(".custom-command-icon-grid button:focus").press("Enter");
  assert.equal(await button("Change action icon: Arrow right").count(), 1);
  assert.match(
    await button("Run Motor positions").locator("svg").getAttribute("class"),
    /lucide-microscope/,
  );
  await button("Cancel").click();
  await panel()
    .getByRole("button", { name: "Motor positions", exact: true })
    .click();
  assert.equal(await button("Change action icon: Microscope").count(), 1);
  await selectIcon("Arrow down");
  await save();
  assert.match(
    await button("Run Motor positions").locator("svg").getAttribute("class"),
    /lucide-arrow-down/,
  );
  await panel()
    .getByRole("button", { name: "Motor positions", exact: true })
    .click();
  await selectIcon("Microscope");
  await save();
  await panel()
    .getByRole("button", { name: "Motor positions", exact: true })
    .click();
  await page.getByText("Current input values", { exact: true }).click();
  assert.equal(
    JSON.parse(await readFile(settings, "utf8")).commands[0].icon,
    legacyIcons || limitedIcons ? "terminal" : "microscope",
  );
  assert.match(
    await page.locator(".custom-command-context").innerText(),
    /CeO2_Pilatus1M.poni/,
  );
  const artifacts = path.join(root, "desktop/artifacts");
  await mkdir(artifacts, { recursive: true });
  for (const [width, height] of [
    [1440, 1000],
    [1000, 760],
  ]) {
    await page.setViewportSize({ width, height });
    for (const large of [false, true]) {
      await page
        .locator(".app")
        .evaluate(
          (node, large) =>
            node.setAttribute("data-text-size", large ? "large" : "normal"),
          large,
        );
      await button("Save action").scrollIntoViewIfNeeded();
      assert.equal(
        Math.round(
          (await page.getByLabel("Sidebar button preview").boundingBox()).width,
        ),
        Math.round(
          (
            await page
              .locator(".navigation-custom-commands .workspace-nav")
              .first()
              .boundingBox()
          ).width,
        ),
      );
      const bounds = await button("Save action").boundingBox();
      assert.ok(bounds.y >= 0 && bounds.y + bounds.height <= height);
      assert.equal(
        await page
          .locator(".custom-command-settings")
          .evaluate((node) => node.scrollWidth > node.clientWidth + 2),
        false,
      );
      await page
        .locator(".custom-command-settings")
        .evaluate((node) => (node.scrollTop = 0));
      await page.screenshot({
        path: path.join(
          artifacts,
          `custom-command-${iconMode}-${width}-${large ? "large" : "standard"}.png`,
        ),
      });
      await openIconPicker();
      await page
        .getByRole("searchbox", { name: "Search action icons" })
        .fill("arrow");
      const popup = page.getByRole("dialog", {
        name: "Button icon",
        exact: true,
      });
      const popupBounds = await popup.boundingBox();
      assert.ok(
        popupBounds.x >= 0 &&
          popupBounds.y >= 0 &&
          popupBounds.x + popupBounds.width <= width &&
          popupBounds.y + popupBounds.height <= height,
      );
      await page.screenshot({
        path: path.join(
          artifacts,
          `custom-command-picker-${iconMode}-${width}-${large ? "large" : "standard"}.png`,
        ),
      });
      await page
        .getByRole("searchbox", { name: "Search action icons" })
        .press("Escape");
      assert.equal(await popup.count(), 0);
      assert.equal(await button("Close settings").isVisible(), true);
    }
  }
  await page
    .locator(".app")
    .evaluate((node) => node.setAttribute("data-text-size", "normal"));
  await page.getByLabel("Show button in sidebar").uncheck();
  await save();
  assert.equal(await button("Run Motor positions").count(), 0);
  await panel()
    .getByRole("button", { name: "Motor positions · hidden", exact: true })
    .click();
  await page.getByLabel("Show button in sidebar").check();
  await selectIcon("Calculator");
  await page.getByLabel("Button name", { exact: true }).fill("Updated lookup");
  await save();
  assert.equal(await button("Run Updated lookup").count(), 1);
  assert.match(
    await button("Run Updated lookup").locator("svg").getAttribute("class"),
    /lucide-calculator/,
  );
  if (legacyIcons || limitedIcons) {
    // The compatibility preference must survive the backend's next list,
    // rather than only changing the icon for the immediate save response.
    await page.reload();
    await ready();
    await button("Run Updated lookup").waitFor();
    assert.match(
      await button("Run Updated lookup").locator("svg").getAttribute("class"),
      /lucide-calculator/,
    );
    await openSettings();
  }
  assert.equal(
    await page.getByLabel("Button name", { exact: true }).count(),
    0,
  );
  await button("Delete action: Updated lookup").click();
  await page.getByText("Action deleted.", { exact: true }).waitFor();
  await historyStep("Undo");
  assert.equal(await button("Run Updated lookup").count(), 1);
  await historyStep("Redo");
  assert.deepEqual(await savedActions(), []);
  await historyStep("Undo");
  await panel()
    .getByRole("button", { name: "Updated lookup", exact: true })
    .click();
  await page.getByLabel("Button name", { exact: true }).fill("New branch");
  await save();
  assert.equal(await button("Redo").isDisabled(), true);
  await historyStep("Undo");
  assert.equal(await button("Run Updated lookup").count(), 1);
  await button("Delete action: Updated lookup").click();
  await ready();
  assert.equal(await button("Run Updated lookup").count(), 0);
  assert.deepEqual(JSON.parse(await readFile(settings, "utf8")).commands, []);
  assert.deepEqual(
    await page.evaluate(() =>
      JSON.parse(
        localStorage.getItem("dioptas-custom-command-icons-v1") ?? "{}",
      ),
    ),
    {},
  );
  // Fifteen enabled commands exercise overflow, real execution from the menu,
  // unavailable inputs, and persisted user ordering.
  for (let number = 1; number <= 15; number++) {
    const suffix = String(number).padStart(2, "0");
    const result = await invoke("custom_command", {
      operation: "save",
      command: {
        id: `bulk-${suffix}`,
        name: `Tool ${suffix}`,
        program: path.join(root, ".venv/bin/python"),
        arguments:
          number === 15
            ? [script, output, "from menu", "15"]
            : number === 14
              ? ["{dataset}"]
              : ["-c", `print('Tool ${suffix}')`],
        enabled: true,
        icon: "terminal",
      },
    });
    assert.equal(result.ok, true);
  }
  await page.reload();
  await ready();
  const rail = page.locator(".navigation-custom-commands");
  await button("More actions").waitFor();
  assert.ok((await rail.locator("button").count()) <= 4);
  await button("More actions").click();
  const commandMenu = page.getByRole("dialog", {
    name: "Custom actions",
    exact: true,
  });
  assert.equal(await commandMenu.getByRole("button").count(), 15);
  assert.equal(
    await commandMenu
      .getByRole("button", { name: "Run Tool 14", exact: true })
      .isDisabled(),
    true,
  );
  assert.match(
    await commandMenu
      .getByRole("button", { name: "Run Tool 14", exact: true })
      .innerText(),
    /Dataset unavailable/,
  );
  await page
    .getByRole("searchbox", { name: "Search custom actions" })
    .fill("Tool 15");
  assert.equal(await commandMenu.getByRole("button").count(), 1);
  await page
    .getByRole("searchbox", { name: "Search custom actions" })
    .press("ArrowDown");
  await commandMenu
    .getByRole("button", { name: "Run Tool 15", exact: true })
    .press("Enter");
  assert.equal(await commandMenu.count(), 0);
  await openSettings();
  await page.getByText("Tool 15 · Finished", { exact: true }).waitFor();
  assert.deepEqual(JSON.parse(await readFile(output, "utf8")), [
    "from menu",
    "15",
  ]);
  const entry = (id) =>
    page.locator(`.custom-command-entry[data-command-id="${id}"]`);
  await button("Drag Tool 15 to reorder").dragTo(entry("bulk-01"), {
    targetPosition: { x: 100, y: 3 },
  });
  assert.match(await button("Undo").getAttribute("title"), /Reorder actions/);
  await historyStep("Undo");
  assert.equal(
    await page
      .locator(".custom-command-entry")
      .first()
      .getAttribute("data-command-id"),
    "bulk-01",
  );
  await historyStep("Redo");
  assert.equal(
    await page
      .locator(".custom-command-entry")
      .first()
      .getAttribute("data-command-id"),
    "bulk-15",
  );
  await page.setViewportSize({ width: 1440, height: 1100 });
  await button("Drag Tool 15 to reorder").dragTo(entry("bulk-14"), {
    targetPosition: {
      x: 100,
      y: (await entry("bulk-14").boundingBox()).height - 3,
    },
  });
  assert.equal(
    await page
      .locator(".custom-command-entry")
      .last()
      .getAttribute("data-command-id"),
    "bulk-15",
  );
  await button("Drag Tool 15 to reorder").dragTo(entry("bulk-01"), {
    targetPosition: { x: 100, y: 3 },
  });
  assert.equal(
    await page.locator(".custom-command-entry[data-drop]").count(),
    0,
  );
  assert.equal(await button("Move Tool 15 up").isDisabled(), true);
  assert.equal(
    await rail
      .locator('button[aria-label^="Run "]')
      .first()
      .getAttribute("aria-label"),
    "Run Tool 15",
  );
  await button("Move Tool 15 down").click();
  await button("Drag Tool 15 to reorder").focus();
  await button("Drag Tool 15 to reorder").press("ArrowUp");
  assert.equal(
    await page
      .locator(".custom-command-entry")
      .first()
      .getAttribute("data-command-id"),
    "bulk-15",
  );
  await button("Drag Tool 15 to reorder").press("ArrowDown");
  await page.reload();
  await ready();
  await button("More actions").waitFor();
  await button("More actions").click();
  assert.equal(
    await commandMenu.getByRole("button").nth(0).getAttribute("aria-label"),
    "Run Tool 01",
  );
  assert.equal(
    await commandMenu.getByRole("button").nth(1).getAttribute("aria-label"),
    "Run Tool 15",
  );
  await page
    .getByRole("searchbox", { name: "Search custom actions" })
    .press("Escape");
  assert.equal(await commandMenu.count(), 0);
  assert.equal(
    await button("More actions").evaluate(
      (node) => node === document.activeElement,
    ),
    true,
  );
  for (const [width, height] of [
    [1440, 1000],
    [1000, 760],
    [1000, 668],
  ]) {
    await page.setViewportSize({ width, height });
    for (const large of [false, true]) {
      await page
        .locator(".app")
        .evaluate(
          (node, large) =>
            node.setAttribute("data-text-size", large ? "large" : "normal"),
          large,
        );
      await page.waitForFunction(() => {
        const nav = document.querySelector(".mode-navigation");
        return nav.scrollHeight <= nav.clientHeight + 1;
      });
      assert.ok((await rail.locator("button").count()) <= 4);
      const settingsBounds = await button("Settings").boundingBox();
      const historyBounds = await button("Undo").boundingBox();
      assert.ok(
        settingsBounds.y >= 0 &&
          settingsBounds.y + settingsBounds.height <= height,
      );
      assert.ok(
        historyBounds.y >= 0 &&
          historyBounds.y + historyBounds.height <= settingsBounds.y,
      );
      await button("More actions").click();
      const menuBounds = await commandMenu.boundingBox();
      assert.ok(
        menuBounds.x >= 0 &&
          menuBounds.y >= 0 &&
          menuBounds.x + menuBounds.width <= width &&
          menuBounds.y + menuBounds.height <= height,
      );
      assert.equal(await commandMenu.getByRole("button").count(), 15);
      await page.screenshot({
        path: path.join(
          root,
          "desktop/artifacts",
          `custom-command-overflow-${iconMode}-${width}-${height}-${large ? "large" : "standard"}.png`,
        ),
      });
      await page
        .getByRole("searchbox", { name: "Search custom actions" })
        .press("Escape");
    }
  }
  await openSettings();
  await button("Move Tool 15 up").click();
  assert.equal(await button("Undo").isEnabled(), true);
  assert.equal(
    (
      await invoke("custom_command", {
        operation: "save",
        command: {
          id: "external",
          name: "External",
          program: path.join(root, ".venv/bin/python"),
          arguments: [],
          enabled: true,
        },
      })
    ).ok,
    true,
  );
  const externalSnapshot = await savedActions();
  await historyStep("Undo");
  await page
    .getByText(
      "Custom actions changed outside this window. Action history has been reset.",
      { exact: true },
    )
    .waitFor();
  assert.deepEqual(await savedActions(), externalSnapshot);
  assert.equal(await button("Undo").isDisabled(), true);
  assert.equal(await button("Redo").isDisabled(), true);
  assert.deepEqual(errors, []);
  console.log(
    `Custom actions (${iconMode} icons): undo/redo create/edit/delete/reorder, failure recovery, keyboard/context isolation, external-change protection, 15-action overflow and layouts passed.`,
  );
} catch (error) {
  console.error(logs.join(""));
  throw error;
} finally {
  await browser.close();
  host.stdin.end();
  await new Promise((resolve) => host.once("exit", resolve));
  await rm(temp, { recursive: true, force: true });
}

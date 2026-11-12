import assert from "node:assert/strict";
import {
  copyFile,
  mkdtemp,
  mkdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const temporary = await mkdtemp(path.join(tmpdir(), "dioptas-recovery-ui-"));
const artifacts = path.join(root, "desktop/artifacts/session-recovery");
await mkdir(artifacts, { recursive: true });
const checkpoint = path.join(temporary, "native-session-v1.dio");
const source = path.join(temporary, "source.h5");
const project = path.join(temporary, "experiment.dio");
const call = async (native, action, payload = {}) => {
  const result = await native.invoke(action, payload);
  assert.equal(result.ok, true, `${action}: ${result.error}`);
  return result;
};
const ui = {
  mode: "integration",
  integrationDisplay: "image",
  logImage: true,
  limits: [20, 400],
  detectorAuto: false,
  palette: "grey",
  cakeLog: false,
  cakeLimits: [1, 99],
  cakeAuto: false,
  calibrationStep: 2,
  showConfigurationControls: true,
  validationConvention: "fit2d",
};
try {
  await copyFile(
    path.join(root, "desktop/backend/tests/fixtures/combined-counts.h5"),
    source,
  );
  const previous = nativeClient({
    env: { HOME: temporary, XDG_DATA_HOME: temporary },
  });
  try {
    await call(previous, "open_image", { path: source, dataset: "/counts" });
    await call(previous, "integration_settings", {
      bins: 137,
      use_mask: false,
    });
    await call(previous, "save_project", { path: project });
    await call(previous, "recovery_checkpoint", { path: checkpoint, ui });
  } finally {
    await previous.close();
  }
  await rm(source);
  const lastGood = await readFile(checkpoint);
  const receipts = [];
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch({ headless: true });
    try {
      for (const scenario of [
        "restore",
        "fresh",
        "failure",
        "display-failure",
        "explicit-startup",
      ]) {
        const native = nativeClient({
          env: { HOME: temporary, XDG_DATA_HOME: temporary },
        });
        const context = await browser.newContext({
          viewport: { width: 1000, height: 700 },
        });
        const page = await context.newPage();
        page.setDefaultTimeout(30000);
        const errors = [],
          operations = [];
        let capturedUi;
        page.on("pageerror", (e) => errors.push(e.message));
        await page.exposeFunction("__nativeInvoke", async (action, payload) => {
          if (
            scenario === "display-failure" &&
            action === "state" &&
            operations.includes("restore")
          )
            return { ok: false, error: "Injected workspace display failure" };
          return native.browserResult(await native.invoke(action, payload));
        });
        await page.exposeFunction("__recovery", async (operation, payload) => {
          operations.push(operation);
          if (operation === "status")
            return scenario === "explicit-startup"
              ? {
                  available: false,
                  startup: [{ action: "open_project", path: project }],
                }
              : { available: true, path: checkpoint };
          if (operation === "ui") {
            capturedUi = payload;
            return {};
          }
          if (operation === "fresh") return {};
          if (operation === "restore") {
            const target =
              scenario === "failure"
                ? path.join(temporary, "corrupt.dio")
                : checkpoint;
            const result = await native.invoke("recovery_restore", {
              path: target,
            });
            if (!result.ok) throw Error(result.error);
            return {
              ui: result.recoveryUi,
              missingSources: result.missingSources,
            };
          }
          throw Error(`Unexpected recovery operation: ${operation}`);
        });
        await page.addInitScript(() => {
          window.pywebview = {
            api: {
              invoke: (action, payload) =>
                window.__nativeInvoke(action, payload),
            },
          };
          window.dioptasRecovery = (operation, ui) =>
            window.__recovery(operation, ui);
        });
        await writeFile(
          path.join(temporary, "corrupt.dio"),
          "truncated checkpoint",
        );
        try {
          await page.goto(
            pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html"))
              .href,
          );
          const prompt = page.getByRole("dialog", {
            name: "Restore previous work?",
          });
          if (scenario === "explicit-startup") {
            await page.waitForFunction(() =>
              document.body.textContent.includes("experiment.dio"),
            );
            assert.equal(await prompt.count(), 0);
            assert.equal(operations.includes("restore"), false);
            assert.equal(
              (await call(native, "state")).state.projectName,
              "experiment.dio",
            );
          } else {
            await prompt.waitFor();
            assert.equal(
              await page
                .getByRole("button", { name: "Restore", exact: true })
                .evaluate((e) => e === document.activeElement),
              true,
            );
            if (scenario === "fresh") {
              await page
                .getByRole("button", { name: "Start fresh", exact: true })
                .click();
              await prompt.waitFor({ state: "detached" });
              assert.equal((await call(native, "state")).state.hasImage, false);
              assert.equal(operations.includes("restore"), false);
            } else {
              await page
                .getByRole("button", { name: "Restore", exact: true })
                .click();
              if (scenario === "failure") {
                await page
                  .getByRole("alert")
                  .filter({ hasText: "recovery file was preserved" })
                  .waitFor();
                assert.equal(
                  (await call(native, "state")).state.hasImage,
                  false,
                );
                await page.screenshot({
                  path: path.join(artifacts, `${name}-failed-recovery.png`),
                });
                await page
                  .getByRole("button", { name: "Start fresh", exact: true })
                  .click();
                await prompt.waitFor({ state: "detached" });
              } else if (scenario === "display-failure") {
                await prompt.waitFor({ state: "detached" });
                const notice = page.getByRole("dialog", {
                  name: "Session recovery",
                  exact: true,
                });
                await notice.waitFor();
                assert.match(
                  await notice.innerText(),
                  /workspace could not be displayed/,
                );
                assert.equal(
                  (await call(native, "state")).state.hasImage,
                  true,
                );
                assert.equal(operations.includes("fresh"), false);
              } else {
                await prompt.waitFor({ state: "detached" });
                const notice = page.getByRole("dialog", {
                  name: "Session recovery",
                  exact: true,
                });
                await notice.waitFor();
                assert.match(
                  await notice.innerText(),
                  /Original image files are unavailable/,
                );
                await notice
                  .getByRole("button", { name: "OK", exact: true })
                  .click();
                await page.waitForFunction(
                  () =>
                    document
                      .querySelector('[aria-label="Integration"]')
                      ?.getAttribute("aria-pressed") === "true",
                );
                await page.waitForTimeout(100);
                assert.equal(capturedUi.logImage, true);
                assert.equal(capturedUi.cakeLog, false);
                assert.deepEqual(capturedUi.limits, [20, 400]);
                assert.deepEqual(capturedUi.cakeLimits, [1, 99]);
                assert.equal(capturedUi.validationConvention, "fit2d");
                const restored = await call(native, "state");
                assert.equal(restored.state.projectName, "experiment.dio");
                assert.equal(restored.state.bins, 137);
                assert.equal(restored.state.hasImage, true);
                await page.screenshot({
                  path: path.join(artifacts, `${name}-restored.png`),
                });
                const closed = path.join(temporary, `${name}-closed.dio`);
                await call(native, "recovery_checkpoint", {
                  path: closed,
                  ui: capturedUi,
                });
                const restart = nativeClient({ env: { HOME: temporary } });
                try {
                  const restored = await call(restart, "recovery_restore", {
                    path: closed,
                  });
                  assert.equal(restored.recoveryUi.mode, "integration");
                  assert.equal(restored.state.bins, 137);
                } finally {
                  await restart.close();
                }
              }
            }
          }
          assert.deepEqual(await readFile(checkpoint), lastGood);
          assert.deepEqual(errors, []);
          receipts.push({ browser: name, scenario, passed: true });
        } finally {
          await context.close();
          await native.close();
        }
      }
    } finally {
      await browser.close();
    }
  }
  await writeFile(
    path.join(artifacts, "report.json"),
    JSON.stringify(receipts, null, 2),
  );
  console.log(JSON.stringify(receipts));
} finally {
  await rm(temporary, { recursive: true, force: true });
}

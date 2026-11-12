// Headless check of the update notice, its popover and the Settings card with
// a scripted host. No release server is contacted and nothing is installed.
import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const screenshots = process.argv.includes("--screenshots")
  ? process.argv[process.argv.indexOf("--screenshots") + 1]
  : null;
const engines = process.argv.includes("--webkit")
  ? { webkit }
  : process.argv.includes("--all")
    ? { chromium, webkit }
    : { chromium };
// A disposable fixture: the test never edits files of a live preview.
const fixture = await mkdtemp(path.join(desktop, "scripts/.app-update-test-"));
const relative = path.relative(desktop, fixture);
await writeFile(
  path.join(fixture, "index.html"),
  `<div id="root"></div><script type="module" src="./fixture.tsx"></script>`,
);
await writeFile(
  path.join(fixture, "fixture.tsx"),
  `
import React, { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { Settings } from "lucide-react";
import { Button } from "/src/ui";
import { AppUpdateNotice } from "/src/AppUpdateNotice";
import { AppUpdateSettings } from "/src/AppUpdateSettings";
import { useAppUpdate } from "/src/useAppUpdate";
import "/src/style.css";
import "/src/surfaces.css";
import "/src/navigation.css";
import "/src/sharedFooter.css";
import "/src/settings.css";

const query = new URLSearchParams(location.search);
// Automatic checks stay out of the way unless a step asks for one.
const launchDelay = query.has("auto") ? 50 : 1e9;
const calls = (window.calls = []);
const scripted = (window.scripted = {
  update: { version: query.get("version") ?? "0.15.0", notes: "Faster map loading.\\n\\nNew polygon mask tools.", published: 1794500000, downloaded: false },
  checkError: null, downloadError: null, applyError: null,
});
let finishDownload;
window.finishDownload = () => finishDownload();
const host = {
  async check() {
    calls.push("check");
    if (scripted.checkError) throw scripted.checkError;
    return { supported: true, currentVersion: "0.14.0", update: scripted.update };
  },
  download(progress) {
    calls.push("download");
    window.progress = progress;
    return new Promise((resolve, reject) => {
      finishDownload = () => scripted.downloadError ? reject(scripted.downloadError) : resolve();
    });
  },
  async apply() {
    calls.push("apply");
    if (scripted.applyError) throw scripted.applyError;
    return new Promise(() => {});
  },
  async openPage() { calls.push("openPage"); },
};
function Fixture() {
  const controller = useAppUpdate(host, launchDelay);
  const [ready, setReady] = useState(true);
  window.setReady = setReady;
  return (
    <div className="app" data-text-size="normal" style={{ height: 620 }}>
      <div className="app-body" style={{ display: "flex", height: "100%" }}>
        <nav className="mode-navigation" aria-label="Workspace modes">
          <div className="navigation-utilities">
            <AppUpdateNotice controller={controller} ready={ready} />
            <Button className="workspace-nav navigation-settings" aria-label="Settings">
              <Settings size={20} />
            </Button>
          </div>
        </nav>
        <div className="settings-workspace" style={{ position: "relative", inset: "auto", flex: 1, padding: 24 }}>
          <div className="settings-content"><div className="settings-tabpanel settings-general">
            <AppUpdateSettings controller={controller} />
          </div></div>
        </div>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")).render(<StrictMode><Fixture /></StrictMode>);
`,
);
const server = await createServer({
  root: desktop,
  logLevel: "error",
  server: { host: "127.0.0.1", port: 0, strictPort: false },
});
try {
  await server.listen();
  for (const [name, engine] of Object.entries(engines)) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({
        viewport: { width: 1000, height: 620 },
      });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("console", (message) => {
        if (message.type() === "error") errors.push(message.text());
      });
      const shot = async (label) => {
        if (screenshots)
          await page.screenshot({
            path: path.join(screenshots, `${name}-${label}.png`),
          });
      };
      const url = `${server.resolvedUrls.local[0]}${relative}/index.html`;
      await page.goto(url);
      const rail = page.getByRole("navigation", { name: "Workspace modes" });
      const notice = rail.getByRole("button", {
        name: /update|Dioptas 0\.15/i,
      });
      const dialog = page.getByRole("dialog", { name: "Application update" });
      const check = page.getByRole("button", { name: "Check for updates" });
      const status = page.getByRole("status");

      // Nothing is shown, and nothing is requested, before a check finds one.
      await check.waitFor();
      assert.equal(await notice.count(), 0);
      assert.deepEqual(await page.evaluate(() => window.calls), []);
      assert.equal(
        await page.locator(".navigation-update").evaluate((node) => {
          return getComputedStyle(node).display;
        }),
        "none",
      );

      // An offline check reports only because the user asked for it.
      await page.evaluate(() => (window.scripted.checkError = "offline"));
      await check.click();
      await page.getByText("offline").waitFor();
      assert.equal(await notice.count(), 0);
      await page.evaluate(() => (window.scripted.checkError = null));

      await check.click();
      await notice.waitFor();
      assert.equal(
        await notice.getAttribute("aria-label"),
        "Update available: Dioptas 0.15.0",
      );
      await status.getByText(/Dioptas 0\.15\.0 is available/).waitFor();
      // The notice never opens by itself.
      assert.equal(await dialog.count(), 0);
      const box = await notice.boundingBox();
      const settings = await rail
        .getByRole("button", { name: "Settings" })
        .boundingBox();
      assert(box.width === 40 && box.height === 40, "rail button footprint");
      assert(box.y + box.height <= settings.y, "above Settings");
      assert(box.x >= 0 && box.x + box.width <= 68, "inside the rail");
      await shot("1-notice");

      await notice.click();
      await dialog.waitFor();
      await dialog.getByText("You are using 0.14.0.").waitFor();
      await dialog.getByText("New polygon mask tools.").waitFor();
      const panel = await dialog.boundingBox();
      assert(panel.x >= 68, "popover opens beside the rail");
      assert(
        panel.y >= 0 && panel.y + panel.height <= 620,
        "inside the window",
      );
      await shot("2-available");

      // Later and Escape close without changing anything.
      await dialog.getByRole("button", { name: "Later" }).click();
      assert.equal(await dialog.count(), 0);
      await notice.click();
      await page.keyboard.press("Escape");
      assert.equal(await dialog.count(), 0);
      assert.equal(await notice.count(), 1);

      await notice.click();
      await dialog.getByRole("button", { name: "Download update" }).click();
      await dialog.getByText(/You can keep working/).waitFor();
      await page.evaluate(() => window.progress(12_000_000, 48_000_000));
      await dialog.getByText("12.0 of 48.0 MB").waitFor();
      assert.equal(
        await notice.getAttribute("aria-label"),
        "Downloading Dioptas 0.15.0: 25%",
      );
      assert.equal(
        await dialog.getByRole("progressbar").getAttribute("value"),
        "0.25",
      );
      await shot("3-downloading");
      // A periodic check during the download does not restart it.
      // Clicking elsewhere closes the popover, like the other sidebar menus.
      await check.click();
      await status.getByText(/Dioptas 0\.15\.0 is available/).waitFor();
      assert.equal(await dialog.count(), 0);
      assert.equal(
        await notice.getAttribute("aria-label"),
        "Downloading Dioptas 0.15.0: 25%",
      );
      await notice.click();
      await dialog.getByText("12.0 of 48.0 MB").waitFor();

      // A failed download can be repeated or replaced by a manual download.
      await page.evaluate(() => {
        window.scripted.downloadError =
          "Could not download the update: timeout";
        window.finishDownload();
      });
      await dialog
        .getByRole("alert")
        .getByText(/timeout/)
        .waitFor();
      await shot("4-error");
      await dialog.getByRole("button", { name: "Open download page" }).click();
      await page.evaluate(() => (window.scripted.downloadError = null));
      await dialog.getByRole("button", { name: "Try again" }).click();
      await dialog.getByText(/You can keep working/).waitFor();
      await page.evaluate(() => window.finishDownload());

      const restart = dialog.getByRole("button", { name: "Restart to update" });
      await restart.waitFor();
      assert.equal(
        await notice.getAttribute("aria-label"),
        "Restart to update to Dioptas 0.15.0",
      );
      await dialog.getByText(/Save your project first/).waitFor();
      await shot("5-ready");
      // Restarting waits for running processing.
      await page.evaluate(() => window.setReady(false));
      assert.equal(await restart.isDisabled(), true);
      await dialog
        .getByText(/when the current processing has finished/)
        .waitFor();
      await page.evaluate(() => window.setReady(true));
      assert.equal(await restart.isDisabled(), false);
      assert(!(await page.evaluate(() => window.calls)).includes("apply"));
      await restart.click();
      await dialog.getByText(/Installing…/).waitFor();
      assert.deepEqual(
        await page.evaluate(() => window.calls.filter((c) => c !== "check")),
        ["download", "openPage", "download", "apply"],
      );

      // Skipping hides that version from automatic checks, also after a restart.
      await page.reload();
      await check.click();
      await notice.click();
      await dialog.getByRole("button", { name: "Skip this version" }).click();
      assert.equal(await notice.count(), 0);
      const automaticCheck = async (search) => {
        await page.goto(`${url}?auto=1${search}`);
        await page.waitForFunction(() => window.calls.includes("check"));
        await page.waitForTimeout(200);
      };
      await automaticCheck("");
      assert.equal(await notice.count(), 0);
      // A newer release is announced again.
      await automaticCheck("&version=0.15.1");
      assert.equal(
        await notice.getAttribute("aria-label"),
        "Update available: Dioptas 0.15.1",
      );
      // Asking explicitly brings the skipped version back.
      await page.goto(url);
      await check.click();
      assert.equal(
        await notice.getAttribute("aria-label"),
        "Update available: Dioptas 0.15.0",
      );

      // The automatic check can be switched off and stays off.
      const automatic = page.getByRole("checkbox", {
        name: "Check for updates automatically",
      });
      assert.equal(await automatic.isChecked(), true);
      await automatic.uncheck();
      await page.reload();
      assert.equal(await automatic.isChecked(), false);
      await shot("6-settings");
      assert.deepEqual(errors, []);
      console.log(`${name}: update notice, popover and settings verified`);
    } finally {
      await browser.close();
    }
  }
} finally {
  await server.close();
  await rm(fixture, { recursive: true, force: true });
}

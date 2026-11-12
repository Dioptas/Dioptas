// Real native launcher/output lifetime through the React controller. No Python,
// visible windows, scientific fixtures, or fabricated command responses.
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const directory = await mkdtemp(path.join(tmpdir(), "dioptas-native-actions-"));
const artifacts = path.join(root, "desktop/artifacts/native-custom-actions");
await mkdir(artifacts, { recursive: true });
const receipts = [];
async function until(predicate, message) {
  const deadline = Date.now() + 15_000;
  while (!(await predicate())) {
    assert.ok(Date.now() < deadline, message);
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const files = path.join(directory, name);
    await mkdir(files);
    const settings = path.join(files, "commands.json");
    const gate = path.join(files, "release");
    const result = path.join(files, "descendant-result");
    const script = path.join(files, "launcher.sh");
    await writeFile(
      script,
      `#!/bin/sh
(
  i=0
  while [ ! -f "$1" ] && [ "$i" -lt 1500 ]; do
    i=$((i+1))
    /bin/sleep 0.02
  done
  [ -f "$1" ] || exit 9
  printf 'Late native descendant output\\n' && printf 0 > "$2"
) &
exit 0
`,
    );
    const native = nativeClient({
      env: { DIOPTAS_CUSTOM_COMMANDS_FILE: settings },
    });
    let browser;
    let page;
    let ran = false;
    const errors = [];
    const observed = [];
    let completedPendingLists = 0;
    let lateOutputLists = 0;
    let gateReleased = false;
    const invoke = async (action, payload = {}) => {
      const response = await native.invoke(action, payload);
      assert.equal(response.ok, true, `${action}: ${response.error}`);
      return response;
    };
    try {
      await invoke("custom_command", {
        operation: "save",
        command: {
          id: "launcher",
          name: "Native launcher",
          program: "/bin/sh",
          arguments: [script, gate, result],
          enabled: true,
          icon: "terminal",
        },
      });
      browser = await engine.launch({ headless: true });
      page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
      page.on("pageerror", (error) => errors.push(error.message));
      await page.exposeFunction("__nativeInvoke", async (action, payload) => {
        const response = await invoke(action, payload);
        if (action === "custom_command") {
          const operation = payload?.operation ?? "list";
          const run = response.customCommandRuns?.launcher;
          observed.push({
            operation,
            running: run?.running,
            outputPending: run?.outputPending,
            output: run?.output,
          });
          if (operation === "run") ran = true;
          if (
            operation === "list" &&
            run?.running === false &&
            run.outputPending === true
          )
            completedPendingLists++;
          if (
            gateReleased &&
            operation === "list" &&
            run?.output?.includes("Late native descendant output")
          )
            lateOutputLists++;
        }
        return native.browserResult(response);
      });
      await page.addInitScript(() => {
        window.pywebview = {
          api: {
            invoke: (action, payload) => window.__nativeInvoke(action, payload),
          },
        };
      });
      await page.goto(
        pathToFileURL(path.join(root, "desktop/dist/index.html")).href,
      );
      const button = (label) =>
        page.getByRole("button", { name: label, exact: true });
      await button("Settings").click();
      await page
        .getByRole("tab", { name: "Custom actions", exact: true })
        .click();
      const runButton = button("Run Native launcher");
      const deleteButton = button("Delete action: Native launcher");
      await runButton.waitFor();
      assert.equal(await runButton.isEnabled(), true);
      await runButton.click();
      await page
        .getByText("Native launcher · Finished", { exact: true })
        .waitFor();
      await page.waitForFunction(() => {
        const controls = [
          ...document.querySelectorAll(
            '[aria-label="Run Native launcher"], [aria-label="Delete action: Native launcher"]',
          ),
        ];
        return (
          controls.length === 2 &&
          controls.every((element) => !element.disabled)
        );
      });
      assert.equal(
        await runButton.isEnabled(),
        true,
        "Parent exit must release Run while inherited output remains open",
      );
      assert.equal(
        await deleteButton.isEnabled(),
        true,
        "Parent exit must release Delete while inherited output remains open",
      );
      // Multiple observed list replies make this a polling regression, rather
      // than passing on a single request already in flight at parent exit.
      await until(
        () => completedPendingLists >= 3,
        `${name}: UI stopped polling completed launcher output`,
      );
      assert.equal(
        await readFile(result, "utf8").catch(() => null),
        null,
        "Descendant must still be waiting at its gate",
      );
      await deleteButton.click();
      await until(
        async () =>
          JSON.parse(await readFile(settings, "utf8")).commands.length === 0,
        "Action deletion did not persist",
      );
      await runButton.waitFor({ state: "detached" });
      assert.equal(await runButton.count(), 0);
      gateReleased = true;
      await writeFile(gate, "release");
      await page
        .getByLabel("Native launcher output", { exact: true })
        .waitFor();
      assert.match(
        await page
          .getByLabel("Native launcher output", { exact: true })
          .innerText(),
        /Late native descendant output/,
      );
      await until(
        async () => (await readFile(result, "utf8").catch(() => null)) === "0",
        "Descendant output write failed",
      );
      assert.ok(
        lateOutputLists > 0,
        "Late output must reach the page through its continuing native list requests",
      );
      await until(
        () =>
          observed.some(
            (reply) =>
              reply.operation === "list" &&
              reply.outputPending === false &&
              reply.output?.includes("Late native descendant output"),
          ),
        "UI did not observe descendant pipe EOF",
      );
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        completedPendingLists,
        lateOutputLists,
        runAndDeleteAvailableAfterParentExit: true,
        deletionSafeWithOpenOutput: true,
        descendantWriteSucceeded: true,
        observedEOF: true,
      });
    } catch (error) {
      await writeFile(
        path.join(artifacts, `${name}-failure.json`),
        JSON.stringify({ message: String(error), observed, errors }, null, 2),
      );
      await page
        ?.screenshot({ path: path.join(artifacts, `${name}-failure.png`) })
        .catch(() => {});
      throw error;
    } finally {
      // Release only this fixture's descendant before closing its processor.
      await writeFile(gate, "release");
      if (ran)
        await until(
          async () =>
            (await readFile(result, "utf8").catch(() => null)) === "0",
          "Fixture descendant did not finish during cleanup",
        ).catch(() => {});
      await browser?.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "receipt.json"),
    JSON.stringify(receipts, null, 2) + "\n",
  );
  console.log(JSON.stringify(receipts));
} finally {
  await rm(directory, { recursive: true, force: true });
}

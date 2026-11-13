import { spawn } from "node:child_process";
import { openSync, closeSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

async function execute(args) {
  const directory = await mkdtemp(path.join(os.tmpdir(), "dioptas-hdiutil-"));
  const log = path.join(directory, "output.log");
  const descriptor = openSync(log, "w");
  try {
    // A file avoids waiting on pipes inherited by diskimages-helper.
    const code = await new Promise((resolve, reject) => {
      const child = spawn("hdiutil", args, {
        stdio: ["ignore", descriptor, descriptor],
      });
      child.on("error", reject);
      child.on("exit", resolve);
    });
    const output = await readFile(log, "utf8");
    process.stdout.write(output);
    return { code, output };
  } finally {
    closeSync(descriptor);
    await rm(directory, { recursive: true, force: true });
  }
}

export async function hdiutil(
  args,
  {
    run = execute,
    wait = delay,
    beforeRetry = async () => {},
    attempts = 5,
  } = {},
) {
  for (let attempt = 0; attempt < attempts; attempt++) {
    const result = await run(args);
    if (result.code === 0) return result.output;
    if (!result.output.includes("Resource busy") || attempt === attempts - 1)
      throw Error(
        `hdiutil failed (exit ${result.code}): ${result.output.trim()}`,
      );
    const milliseconds = 2000 * 2 ** attempt;
    console.log(
      `hdiutil resource is busy; retrying in ${milliseconds / 1000}s (${attempt + 2}/${attempts}).`,
    );
    await wait(milliseconds);
    await beforeRetry();
  }
}

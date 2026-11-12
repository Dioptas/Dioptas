import { execFileSync } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

const transientNetworkError =
  /NSURLErrorDomain Code=-(?:1001|1005|1009)|The network connection was lost|The request timed out/i;

export async function stapler(
  args,
  {
    run = (args) =>
      execFileSync("xcrun", ["stapler", ...args], { encoding: "utf8" }),
    wait = delay,
    attempts = 5,
  } = {},
) {
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await run(args);
    } catch (error) {
      const output = `${error.stdout ?? ""}\n${error.stderr ?? ""}\n${error.message}`;
      if (!transientNetworkError.test(output) || attempt === attempts - 1)
        throw error;
      const milliseconds = 2000 * 2 ** attempt;
      console.log(
        `Apple ticket network error; retrying stapler in ${milliseconds / 1000}s (${attempt + 2}/${attempts}).`,
      );
      await wait(milliseconds);
    }
  }
}

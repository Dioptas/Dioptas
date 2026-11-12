// AppImage redistributes OS libraries. Retain a versioned superset of the build
// image's copyright texts, rather than labeling these as Cargo dependencies.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { desktop } from "./release_config.mjs";

export async function systemNotices() {
  const output = path.join(desktop, "artifacts/linux-system-notices");
  await rm(output, { recursive: true, force: true });
  await mkdir(path.join(output, "copyright"), { recursive: true });
  const listing = execFileSync(
    "dpkg-query",
    ["-W", "-f=${binary:Package}\t${Version}\t${db:Status-Status}\n"],
    { encoding: "utf8" },
  );
  const packages = [];
  for (const line of listing.trim().split("\n")) {
    const [name, version, status] = line.split("\t");
    if (status !== "installed") continue;
    const base = name.split(":")[0];
    let bytes;
    try {
      bytes = await readFile(`/usr/share/doc/${base}/copyright`);
    } catch (error) {
      if (error.code === "ENOENT") continue;
      throw error;
    }
    const file = `copyright/${name.replaceAll(":", "_")}.txt`;
    await writeFile(path.join(output, file), bytes);
    packages.push({
      name,
      version,
      file,
      sha256: createHash("sha256").update(bytes).digest("hex"),
    });
  }
  await writeFile(
    path.join(output, "SYSTEM_NOTICES.json"),
    JSON.stringify(
      {
        scope:
          "Superset of installed Debian/Ubuntu build-image package copyright texts. This is not an assertion that all listed packages are bundled or runtime dependencies.",
        packages,
      },
      null,
      2,
    ) + "\n",
  );
  return { packages: packages.length };
}

// AppImage redistributes OS libraries. Retain a versioned superset of the build
// image's copyright texts, rather than labeling these as Cargo dependencies.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  copyFile,
  mkdir,
  readFile,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
import assert from "node:assert/strict";
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
  // WebKit loads GLES with dlopen, so linuxdeploy's ELF dependency scan does
  // not discover this GLVND client. Bundle the client, retaining host GL/EGL
  // dispatch/drivers instead of copying GPU-specific drivers into AppImage.
  const library = "libGLESv2.so.2";
  const source = await realpath(`/usr/lib/x86_64-linux-gnu/${library}`);
  const owner = execFileSync("dpkg-query", ["-S", source], { encoding: "utf8" })
    .trim()
    .split(": ")[0];
  const notice = packages.find(
    (pkg) => pkg.name === owner || pkg.name === owner.split(":")[0],
  );
  assert(notice, `Missing native library copyright: ${owner}`);
  const runtime = path.join(desktop, "artifacts/linux-runtime");
  await mkdir(runtime, { recursive: true });
  await copyFile(source, path.join(runtime, library));
  const extraLibraries = [
    {
      name: library,
      source,
      package: notice.name,
      version: notice.version,
      sha256: createHash("sha256")
        .update(await readFile(source))
        .digest("hex"),
      copyright: notice.file,
    },
  ];
  await writeFile(
    path.join(output, "EXTRA_LIBRARIES.json"),
    JSON.stringify(extraLibraries, null, 2) + "\n",
  );
  return { packages: packages.length, extraLibraries };
}

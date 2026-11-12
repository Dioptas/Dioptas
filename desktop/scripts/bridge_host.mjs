// JSON-lines adapter for headless browser drivers; every scientific command runs in Rust.
import { createInterface } from "node:readline";
import { readdir, mkdir } from "node:fs/promises";
import path from "node:path";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts");
await mkdir(artifacts, { recursive: true });
const data = path.join(root, "desktop/tests/data");
const saved = {
  project: "experiment.dio",
  pattern: "pattern.xy",
  phase_list: "phase_list.txt",
  phase_export: "phase.eosmat",
  phase_reflections: "reflections.txt",
  calibration: "calibration.poni",
  peaks: "calibration-peaks.json",
  batch: "batch.h5",
  mask: "mask.mask",
  image_export: "saved-image.png",
  cake_export: "saved-cake.png",
  map_png: "map.png",
  map_export: "map.txt",
  map_batch: "map-batch.h5",
};
const chooser = {
  open_image: ["image"],
  open_calibration: ["calibration"],
  save_calibration: ["calibration", true],
  load_peaks: ["peaks"],
  save_peaks: ["peaks", true],
  open_project: ["project"],
  save_project: ["project", true],
  load_mask: ["mask"],
  save_mask: ["mask", true],
  batch_load: ["batch_images"],
  batch_open: ["batch_open"],
  map_load: ["map_images"],
  map_batch: ["map_batch"],
  integration_open_pattern: ["pattern"],
  integration_save_pattern: ["pattern", true],
  integration_save_batch: ["batch", true],
  integration_output_directory: ["directory"],
  integration_image_background: ["image"],
  integration_flat_field: ["image"],
  integration_transfer: ["image"],
};
async function choose(kind, save) {
  if (kind === "directory") return artifacts;
  if (kind === "batch_images") return [path.join(data, "CeO2_Pilatus1M.tif")];
  if (kind === "map_images")
    return (await readdir(path.join(data, "map")))
      .filter((n) => n.endsWith(".tif"))
      .sort()
      .map((n) => path.join(data, "map", n));
  if (kind === "batch_open") return path.join(artifacts, "batch.h5");
  if (saved[kind]) return path.join(artifacts, saved[kind]);
  return path.join(data, "CeO2_Pilatus1M.tif");
}
const native = nativeClient();
async function dispatch({ id, action, payload = {} }) {
  try {
    payload = { ...payload };
    const selection = chooser[action];
    const adjustment =
      payload.reset ||
      payload.direction !== undefined ||
      (action === "integration_image_background" &&
        ["scale", "offset", "poisson"].some((k) => payload[k] !== undefined)) ||
      (["integration_flat_field", "integration_transfer"].includes(action) &&
        payload.enabled !== undefined);
    if (selection && !adjustment && !payload.path && !payload.paths) {
      const value = await choose(...selection);
      payload[Array.isArray(value) ? "paths" : "path"] = value;
    }
    if (
      action === "integration_overlay" &&
      payload.operation === "load" &&
      !payload.paths
    )
      payload.paths = ["overlay-one.xy", "overlay-two.xy"].map((n) =>
        path.join(artifacts, n),
      );
    if (
      action === "integration_phase" &&
      payload.operation === "load" &&
      !payload.path
    )
      payload.path = path.join(data, "jcpds/au_version3.jcpds");
    const result = native.browserResult(await native.invoke(action, payload));
    process.stdout.write(JSON.stringify({ id, result }) + "\n");
  } catch (error) {
    process.stdout.write(
      JSON.stringify({ id, result: { ok: false, error: error.message } }) +
        "\n",
    );
  }
}
const pending = new Set();
for await (const line of createInterface({ input: process.stdin })) {
  const task = dispatch(JSON.parse(line));
  pending.add(task);
  task.finally(() => pending.delete(task));
}
await Promise.all(pending);
await native.close();

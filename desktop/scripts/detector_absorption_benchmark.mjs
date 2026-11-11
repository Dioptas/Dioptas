// Full-resolution native stdio timings. Optional executable argument permits
// before/after comparison using the same fixture and integration settings.
import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { nativeClient } from "./native_backend_client.mjs";

const directory = await mkdtemp(
  path.join(tmpdir(), "dioptas-absorption-benchmark-"),
);
const native = nativeClient({ executable: process.argv[2] });
const size = 3072;
try {
  let header = `{'descr': '<f8', 'fortran_order': False, 'shape': (${size}, ${size}), }`;
  while ((10 + header.length + 1) % 64) header += " ";
  header += "\n";
  const bytes = Buffer.alloc(10 + header.length + size * size * 8);
  bytes.set(Buffer.from([147, 78, 85, 77, 80, 89, 1, 0]));
  bytes.writeUInt16LE(header.length, 8);
  bytes.write(header, 10);
  for (let i = 0; i < size * size; i++)
    bytes.writeDoubleLE(100 + (i % 103), 10 + header.length + i * 8);
  const file = path.join(directory, "detector.npy");
  await writeFile(file, bytes);
  const call = async (action, payload = {}) => {
    const start = performance.now();
    const result = await native.invoke(action, payload);
    assert.equal(result.ok, true, `${action}: ${result.error}`);
    return +(performance.now() - start).toFixed(1);
  };
  await call("integration_settings", {
    bins: 512,
    cake_bins: 72,
    method: "subpixel",
    supersampling: 1,
  });
  await call("open_image", { path: file });
  await call("calibration_setup", { detector: "Custom" });
  await call("manual_geometry", {
    convention: "pyfai",
    values: {
      dist: 0.2,
      poni1: 0.115,
      poni2: 0.116,
      pixel1: 75e-6,
      pixel2: 75e-6,
      rot1: 0.12,
      rot2: -0.09,
      rot3: 0.04,
      wavelength: 5e-11,
      polarization_factor: 0.965,
    },
  });
  const enable = await call("integration_correction", {
    kind: "oiadac",
    enabled: true,
  });
  const plot = await call("integration_correction_preview", { kind: "oiadac" });
  const repeatPlot = await call("integration_correction_preview", {
    kind: "oiadac",
  });
  const edit = await call("integration_correction", {
    kind: "oiadac",
    enabled: true,
    parameters: { detector_thickness: 44 },
  });
  console.log(
    JSON.stringify(
      { pixels: size * size, milliseconds: { enable, plot, repeatPlot, edit } },
      null,
      2,
    ),
  );
} finally {
  await native.close();
  await rm(directory, { recursive: true, force: true });
}

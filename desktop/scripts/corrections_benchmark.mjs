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
const size = Number(process.env.DIOPTAS_BENCH_SIZE ?? 1024);
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
  let lastResult;
  const call = async (action, payload = {}) => {
    const start = performance.now();
    const result = await native.invoke(action, payload);
    lastResult = result;
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
  const measurements = [];
  for (const kind of (
    process.env.DIOPTAS_BENCH_KINDS ??
    "flat,transfer,cbn,plate,slab,cylinder,sphere,oiadac"
  ).split(",")) {
    if (kind === "transfer") {
      await call("integration_transfer", { source: "original", path: file });
      await call("integration_transfer", { source: "response", path: file });
    }
    const action =
      kind === "flat"
        ? "integration_flat_field"
        : kind === "transfer"
          ? "integration_transfer"
          : "integration_correction";
    const payload =
      kind === "flat"
        ? { path: file }
        : kind === "transfer"
          ? { enabled: true }
          : { kind, enabled: true };
    const enable = await call(action, payload);
    const applyPixelBytes = native.lastPacketBytes - native.lastHeaderBytes - 4;
    let backgroundReadyMs = 0,
      preloadPolls = 0;
    if (
      lastResult.state?.supportsBackgroundCorrectionPreviews &&
      !process.env.DIOPTAS_BENCH_EARLY_PLOT
    ) {
      const state = lastResult.state;
      const start = performance.now();
      while (true) {
        const response = await native.invoke("integration_correction_preload", {
          revision: state.revision,
          configuration: state.configurationContext,
        });
        assert.equal(response.ok, true, response.error);
        preloadPolls++;
        if (!response.correctionPreviewPending) break;
        assert(
          performance.now() - start < 10000,
          "Background preview timed out",
        );
        await new Promise((resolve) => setTimeout(resolve, 5));
      }
      backgroundReadyMs = +(performance.now() - start).toFixed(1);
    }
    const plot = await call("integration_correction_preview", { kind });
    const plotPixelBytes = native.lastPacketBytes - native.lastHeaderBytes - 4;
    const repeatPlot = await call("integration_correction_preview", { kind });
    const reintegrate = await call("integrate");
    const measurement = {
      kind,
      enable,
      plot,
      repeatPlot,
      reintegrate,
      plotPixelBytes,
      applyPixelBytes,
      backgroundReadyMs,
      preloadPolls,
    };
    measurements.push(measurement);
    console.error(JSON.stringify(measurement));
    await call(
      action,
      kind === "flat"
        ? { reset: true }
        : kind === "transfer"
          ? { enabled: false }
          : { kind, enabled: false },
    );
  }
  console.log(
    JSON.stringify(
      { pixels: size * size, milliseconds: measurements },
      null,
      2,
    ),
  );
  if (process.env.DIOPTAS_TRACE_FRAME)
    console.error(native.diagnostics.join(""));
} finally {
  await native.close();
  await rm(directory, { recursive: true, force: true });
}

// Native stdio latency, including response encoding/transfer. Pass a processor
// executable to compare builds; --large exercises a synthetic 9M detector.
// --phases=N uses distinct lattices/pressures; --all exercises Apply to all.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { nativeClient, root } from "./native_backend_client.mjs";

const directory = await mkdtemp(path.join(tmpdir(), "dioptas-phase-guides-"));
const executable = process.argv.slice(2).find((a) => !a.startsWith("--"));
const native = nativeClient({ executable });
const call = async (action, payload = {}) => {
  const result = await native.invoke(action, payload);
  assert.equal(result.ok, true, `${action}: ${result.error}`);
  return result;
};
try {
  await call("integration_settings", {
    bins: 128,
    cake_bins: 36,
    method: "subpixel",
    supersampling: 1,
  });
  // The application defaults to Apply to all. Make the measured edit scope
  // explicit rather than inheriting that default.
  await call("integration_phase", {
    operation: "same_conditions",
    enabled: false,
  });
  if (process.argv.includes("--large")) {
    const size = 3072;
    let header = `{'descr': '<u2', 'fortran_order': False, 'shape': (${size}, ${size}), }`;
    while ((10 + header.length + 1) % 64) header += " ";
    header += "\n";
    const bytes = Buffer.alloc(10 + header.length + size * size * 2);
    bytes.set(Buffer.from([147, 78, 85, 77, 80, 89, 1, 0]));
    bytes.writeUInt16LE(header.length, 8);
    bytes.write(header, 10);
    const file = path.join(directory, "detector.npy");
    await writeFile(file, bytes);
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
  } else {
    await call("open_calibration", {
      path: path.join(root, "tests/data/CeO2_Pilatus1M.poni"),
    });
    await call("open_image", {
      path: path.join(root, "tests/data/CeO2_Pilatus1M.tif"),
    });
  }
  const phaseFiles = process.argv.includes("--single")
    ? ["mo.jcpds"]
    : Array.from(
        {
          length: Number(
            process.argv
              .find((a) => a.startsWith("--phases="))
              ?.split("=")[1] ?? 3,
          ),
        },
        (_, i) => ["mo.jcpds", "au_version3.jcpds", "pt.jcpds"][i % 3],
      );
  for (const [index, name] of phaseFiles.entries()) {
    await call("integration_phase", {
      operation: "load",
      path: path.join(root, "tests/data/jcpds", name),
    });
    if (process.argv.some((a) => a.startsWith("--phases="))) {
      await call("integration_phase", {
        operation: "parameter",
        index,
        parameter: "a0",
        value: [3.15, 4.08, 3.92][index % 3] * (1 + index * 0.002),
      });
      await call("integration_phase", {
        operation: "update",
        index,
        pressure: index * 2 + 0.25,
      });
    }
  }
  if (process.argv.includes("--all"))
    await call("integration_phase", {
      operation: "same_conditions",
      enabled: true,
    });
  const samples = [];
  for (const pressure of [0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0]) {
    const editStart = performance.now();
    await call("integration_phase", {
      operation: "update",
      index: 0,
      pressure,
    });
    const guideStart = performance.now();
    const { phaseGuides } = await call("integration_phase_guides", {
      binary: process.argv.includes("--binary"),
    });
    const end = performance.now();
    assert.ok(phaseGuides.length > 0);
    const decodedGuides = phaseGuides.map((g) => {
      if (Array.isArray(g.points)) return g;
      const p = g.points,
        bytes = native.buffers.get(p.bufferId);
      const points = Array.from({ length: p.length }, (_, i) => [
        bytes.readDoubleLE((p.offset + i) * 16),
        bytes.readDoubleLE((p.offset + i) * 16 + 8),
      ]);
      return { ...g, points };
    });
    samples.push({
      pressure,
      editMs: +(guideStart - editStart).toFixed(2),
      guidesMs: +(end - guideStart).toFixed(2),
      paths: phaseGuides.length,
      wireBytes: native.lastPacketBytes,
      headerBytes: native.lastHeaderBytes,
      points: phaseGuides.reduce((n, p) => n + p.points.length, 0),
      hash: createHash("sha256")
        .update(JSON.stringify(decodedGuides))
        .digest("hex"),
    });
  }
  console.log(
    JSON.stringify(
      {
        detector: process.argv.includes("--large")
          ? "3072x3072 synthetic tilted"
          : "Pilatus1M fixture",
        phases: phaseFiles.length,
        applyToAll: process.argv.includes("--all"),
        samples,
      },
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

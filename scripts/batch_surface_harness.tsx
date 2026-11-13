// Headless renderer edge cases; real Rust integration is covered separately.
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { BatchSurfaceView } from "../src/BatchSurfaceView";
import { captureBatchSurface } from "../src/batchSurfaceCapture";
import "../src/style.css";
import "../src/batch.css";
const fixture = (rows = 4, cols = 5, invalid = false) => {
  const data = Float32Array.from({ length: rows * cols }, (_, i) =>
    invalid ? NaN : ((i % cols) + 1) * (Math.floor(i / cols) + 1),
  );
  return {
    id: "surface-fixture",
    raster: {
      width: cols,
      height: rows,
      dtype: "f32le",
      data: data.buffer,
      limits: [0, rows * cols],
    },
    x: Array.from({ length: cols }, (_, i) => 20 / (i + 1)),
    unit: "d_A",
    sourceUnit: "d_A",
    wavelength: 1e-10,
    entries: Array.from({ length: rows }, (_, i) => ({
      path: "fixture",
      name: `frame-${i + 1}`,
      frame: i + 1,
    })),
    selected: 0,
    normalized: false,
  };
};
function Harness() {
  const [batch, setBatch] = useState(fixture()),
    [visible, setVisible] = useState(true),
    [range, setRange] = useState(null),
    [limits, setLimits] = useState<[number, number]>([0, 20]),
    [scale, setScale] = useState("linear"),
    [phaseLines, setPhaseLines] =
      useState<import("../src/types").Pattern["phaseLines"]>(undefined),
    [palette, setPalette] = useState("viridis");
  Object.assign(window, {
    surfaceBuffer: batch.raster.data,
    setSurfaceVisible: setVisible,
    setSurfaceFixture: (rows, cols, invalid = false) => {
      setBatch(fixture(rows, cols, invalid));
      setRange(null);
    },
    setSurfaceScale: setScale,
    setSurfaceLimits: setLimits,
    setSurfacePhases: setPhaseLines,
    setSurfaceGuideFixture: () => {
      const rows = 31,
        cols = 201,
        b = fixture(rows, cols),
        x = Array.from({ length: cols }, (_, c) => 0.5 + c * 0.025);
      const data = Float32Array.from({ length: rows * cols }, (_, i) => {
        const q = x[i % cols],
          t = Math.floor(i / cols) / 30;
        return (
          3 +
          (68 + 24 * Math.sin(t * Math.PI)) *
            Math.exp(-0.5 * ((q - 2.2) / 0.12) ** 2) +
          (59 - 29 * t) * Math.exp(-0.5 * ((q - 3.25 - 0.58 * t) / 0.16) ** 2) +
          (12 + 65 * t) * Math.exp(-0.5 * ((q - 4.4) / 0.11) ** 2)
        );
      });
      setBatch({
        ...b,
        x,
        unit: "q_A^-1",
        sourceUnit: "q_A^-1",
        raster: { ...b.raster, data: data.buffer },
      });
      setLimits([0, 120]);
      setRange(null);
      setScale("linear");
    },
    setSurfacePalette: setPalette,
    setSurfacePeakFixture: () => {
      const rows = 64,
        cols = 2048,
        b = fixture(rows, cols),
        data = new Float32Array(rows * cols);
      for (let r = 0; r < rows; r++)
        for (let c = 0; c < cols; c++)
          data[r * cols + c] =
            100 *
            Math.exp(-(((c - 1022) / 1.2) ** 2)) *
            (1 + 0.4 * Math.sin(r / 10));
      setBatch({
        ...b,
        x: Array.from({ length: cols }, (_, c) => 0.05 + c * 0.05),
        unit: "2th_deg",
        sourceUnit: "2th_deg",
        raster: { ...b.raster, data: data.buffer },
      });
      setLimits([0, 150]);
      setScale("linear");
      setRange(null);
    },
    setSurfaceAxisCase: ({
      x,
      unit = "2th_deg",
      limits: nextLimits = [0, 20],
      rows = 11,
      scale = "linear",
    }) => {
      const b = fixture(rows, x.length);
      setBatch({ ...b, x, unit, sourceUnit: unit });
      setLimits(nextLimits);
      setScale(scale);
      setRange(null);
    },
    setSurfaceConstant: (value: number) =>
      setBatch((b) => ({
        ...b,
        raster: {
          ...b.raster,
          data: new Float32Array(b.x.length * b.entries.length).fill(value)
            .buffer,
        },
      })),
    captureSurface: () => captureBatchSurface(),
  });
  return (
    <div
      className="app"
      style={{
        height: "100vh",
        width: "100vw",
        minWidth: 0,
        display: "flex",
        padding: 0,
      }}
    >
      {visible && (
        <BatchSurfaceView
          batch={batch as any}
          phaseLines={phaseLines}
          limits={limits}
          log={scale === "log"}
          sqrt={scale === "sqrt"}
          palette={palette}
          range={range}
          step={1}
          ready={true}
          onRange={setRange as any}
          onSelect={(selected, position) => {
            Object.assign(window, { surfaceSelection: { selected, position } });
            setBatch((b) => ({ ...b, selected }));
          }}
          onNormalize={() => {}}
          reportPlot={(_, reading) =>
            Object.assign(window, { surfaceReading: reading })
          }
        />
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<Harness />);

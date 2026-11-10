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
    [range, setRange] = useState(null),
    [limits, setLimits] = useState<[number, number]>([0, 20]),
    [scale, setScale] = useState("linear"),
    [palette, setPalette] = useState("viridis");
  Object.assign(window, {
    setSurfaceFixture: (rows, cols, invalid = false) => {
      setBatch(fixture(rows, cols, invalid));
      setRange(null);
    },
    setSurfaceScale: setScale,
    setSurfacePalette: setPalette,
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
      <BatchSurfaceView
        batch={batch as any}
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
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<Harness />);

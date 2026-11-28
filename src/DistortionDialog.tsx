import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Dialog, DialogHeader, Input, Portal, Select } from "./ui";
import type { DistortionPreview, State } from "./types";
import type { Run } from "./commandContracts";

type DistortionModelKind =
  "smooth_spline" | "radial_optical" | "bow_z" | "per_module";

const MODEL_DESCRIPTIONS: Record<DistortionModelKind, string> = {
  smooth_spline:
    "General-purpose smooth 2D displacement field. Best for fiber-optic tapers (MAR CCD, Rayonix) or unknown smooth distortions; exports to Fit2D / pyFAI .spline.",
  radial_optical:
    "Low-parameter radial pincushion/barrel distortion. Good for CCD or image-plate optical tapers, especially from a single exposure; exports to .spline.",
  bow_z:
    "Smooth out-of-plane panel curvature (Δz). Best for large flat-panel detectors (PerkinElmer, Varex, Dexela); exports to NeXus .h5.",
  per_module:
    "Independent rigid tile offsets (and optional Δz) for tiled pixel detectors (Pilatus, Eiger, Jungfrau). Works best with 2+ detector positions; exports to NeXus .h5.",
};

function modulePresetForDetector(
  detectorName?: string,
  shape?: [number, number] | null,
): {
  h: string;
  w: string;
  gh: string;
  gw: string;
} | null {
  const name = (detectorName ?? "").toLowerCase();
  if (name.includes("pilatus"))
    return { h: "195", w: "487", gh: "17", gw: "7" };
  if (name.includes("eiger2"))
    return { h: "512", w: "1028", gh: "38", gw: "12" };
  if (name.includes("eiger"))
    return { h: "514", w: "1030", gh: "37", gw: "10" };
  if (name.includes("jungfrau"))
    return { h: "512", w: "1024", gh: "36", gw: "8" };
  if (shape) {
    const [r, c] = shape;
    if (
      (r === 619 && c === 487) ||
      (r === 1043 && c === 981) ||
      (r === 1679 && c === 1475) ||
      (r === 2527 && c === 2463)
    )
      return { h: "195", w: "487", gh: "17", gw: "7" };
    if (
      (r === 1062 && c === 1028) ||
      (r === 2162 && c === 2068) ||
      (r === 3262 && c === 3108) ||
      (r === 4362 && c === 4148)
    )
      return { h: "512", w: "1028", gh: "38", gw: "12" };
    if (
      (r === 1065 && c === 1030) ||
      (r === 2167 && c === 2070) ||
      (r === 3269 && c === 3110) ||
      (r === 4371 && c === 4150)
    )
      return { h: "514", w: "1030", gh: "37", gw: "10" };
    if ((r === 1064 && c === 1030) || (r === 2164 && c === 2070))
      return { h: "512", w: "1024", gh: "36", gw: "8" };
  }
  return null;
}

function DistortionCanvas({ preview }: { preview: DistortionPreview | null }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const cssW = 300;
    const cssH = 300;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.fillStyle = "#16181c";
    ctx.fillRect(0, 0, cssW, cssH);

    if (!preview || !preview.grid.length) {
      ctx.fillStyle = "#8a94a0";
      ctx.font = "13px system-ui, -apple-system, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(
        "Run Estimate to preview distortion field",
        cssW / 2,
        cssH / 2,
      );
      return;
    }

    const [h, w] = preview.shape;
    const pad = 22;
    const availW = cssW - 2 * pad;
    const availH = cssH - 2 * pad - 18;
    const scale = Math.min(availW / Math.max(1, w), availH / Math.max(1, h));
    const rectW = w * scale;
    const rectH = h * scale;
    const ox = (cssW - rectW) / 2;
    const oy = pad + (availH - rectH) / 2;

    // Detector frame outline
    ctx.fillStyle = "#1e2127";
    ctx.strokeStyle = "#3a404a";
    ctx.lineWidth = 1;
    ctx.fillRect(ox, oy, rectW, rectH);
    ctx.strokeRect(ox, oy, rectW, rectH);

    const isBow = preview.model === "bow_z";
    const maxMag = Math.max(
      1e-6,
      ...preview.grid.map(([, , dx, dy]) => Math.hypot(dx, dy)),
    );
    const maxDz = Math.max(
      1e-6,
      ...preview.grid.map(([, , , , dz]) => Math.abs(dz)),
    );

    if (isBow) {
      // Heatmap for out-of-plane Δz(d1, d2)
      const side = Math.round(Math.sqrt(preview.grid.length));
      const cellW = rectW / Math.max(1, side);
      const cellH = rectH / Math.max(1, side);
      for (const [u, v, , , dz] of preview.grid) {
        const t = Math.max(-1, Math.min(1, dz / maxDz));
        const cx = ox + u * rectW;
        const cy = oy + v * rectH;
        const r = t > 0 ? Math.round(60 + 195 * t) : 45;
        const g = Math.round(70 + 80 * (1 - Math.abs(t)));
        const b = t < 0 ? Math.round(60 + 195 * -t) : 55;
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.72)`;
        ctx.fillRect(cx - cellW / 2, cy - cellH / 2, cellW + 0.5, cellH + 0.5);
      }
    }

    // Quiver arrows for in-plane displacement (dx, dy)
    if (!isBow || maxMag > 1e-3) {
      const maxArrowPx = Math.min(rectW, rectH) / 14;
      const arrowScale = maxArrowPx / maxMag;
      ctx.lineWidth = 1.25;
      for (const [u, v, dx, dy] of preview.grid) {
        const mag = Math.hypot(dx, dy);
        const x0 = ox + u * rectW;
        const y0 = oy + v * rectH;
        const len = mag * arrowScale;
        if (len < 0.75) {
          ctx.fillStyle = "#525b68";
          ctx.beginPath();
          ctx.arc(x0, y0, 1.2, 0, Math.PI * 2);
          ctx.fill();
          continue;
        }
        const x1 = x0 + dx * arrowScale;
        const y1 = y0 + dy * arrowScale;
        const frac = Math.min(1, mag / maxMag);
        // Cool teal -> warm orange ramp
        const r = Math.round(72 + 183 * frac);
        const g = Math.round(186 - 37 * frac);
        const b = Math.round(170 - 150 * frac);
        ctx.strokeStyle = `rgb(${r}, ${g}, ${b})`;
        ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();

        const angle = Math.atan2(y1 - y0, x1 - x0);
        const head = Math.min(5, Math.max(2.5, len * 0.38));
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(
          x1 - head * Math.cos(angle - 0.5),
          y1 - head * Math.sin(angle - 0.5),
        );
        ctx.lineTo(
          x1 - head * Math.cos(angle + 0.5),
          y1 - head * Math.sin(angle + 0.5),
        );
        ctx.closePath();
        ctx.fill();
      }
    }

    // Bottom scale caption
    ctx.fillStyle = "#adb7c2";
    ctx.font = "11px system-ui, -apple-system, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    const legend = isBow
      ? `Max |Δz|: ${preview.maxDzUm.toFixed(1)} µm (blue −, red +)`
      : `Max |δ|: ${preview.maxDisplacementPx.toFixed(2)} px · arrows scaled to fit`;
    ctx.fillText(legend, pad, cssH - 6);
  }, [preview]);

  return (
    <canvas
      ref={canvasRef}
      className="distortion-preview-canvas"
      width={300}
      height={300}
      aria-label="Estimated distortion vector field preview"
    />
  );
}

export function DistortionDialog({
  open,
  onClose,
  state,
  ready,
  run,
  preview,
  onClearPreview,
}: {
  open: boolean;
  onClose: () => void;
  state: State | null;
  ready: boolean;
  run: Run;
  preview: DistortionPreview | null;
  onClearPreview: () => void;
}) {
  const summaries = state?.configurationSummaries ?? [];
  const activeIndex = state?.configurationIndex ?? 0;
  const activeShape = state?.shape ?? null;

  const [selectedConfigs, setSelectedConfigs] = useState<number[]>([
    activeIndex,
  ]);
  const [model, setModel] = useState<DistortionModelKind>("smooth_spline");
  const [gridN, setGridN] = useState("8");
  const [smoothness, setSmoothness] = useState("1.0");
  const [maxOrder, setMaxOrder] = useState("5");
  const [maxDegree, setMaxDegree] = useState("3");
  const [moduleH, setModuleH] = useState("195");
  const [moduleW, setModuleW] = useState("487");
  const [gapH, setGapH] = useState("17");
  const [gapW, setGapW] = useState("7");
  const [fitZ, setFitZ] = useState(false);
  const [nPasses, setNPasses] = useState("3");
  const [detectNote, setDetectNote] = useState<string | null>(null);
  const lastPresetKey = useRef<string | null>(null);
  const lastAutoDetectKey = useRef<string | null>(null);
  const activeShapeKey = activeShape ? `${activeShape[0]}x${activeShape[1]}` : "";
  const activeImageKey = `${activeIndex}:${activeShapeKey}:${state?.imagePath ?? state?.imageName ?? ""}`;
  const currentDetectContextRef = useRef({ open, activeImageKey });
  currentDetectContextRef.current = { open, activeImageKey };

  // Keep eligible selection synced when dialog opens or configurations change.
  const eligibleIndices = useMemo(
    () =>
      summaries
        .filter(
          (c) =>
            c.hasImage &&
            c.calibrated &&
            c.shape &&
            activeShape &&
            c.shape[0] === activeShape[0] &&
            c.shape[1] === activeShape[1],
        )
        .map((c) => c.index),
    [summaries, activeShape],
  );

  const detectModules = useCallback(
    (userInitiated: boolean) => {
      const requestedKey = currentDetectContextRef.current.activeImageKey;
      void run(
        "detect_detector_modules",
        {},
        userInitiated ? "Detecting detector modules…" : undefined,
        (result) => {
          if (
            !currentDetectContextRef.current.open ||
            currentDetectContextRef.current.activeImageKey !== requestedKey
          ) {
            return;
          }
          const m = result.detectedModules;
          if (!m) return;
          if (
            m.detected &&
            m.moduleHeight != null &&
            m.moduleWidth != null &&
            m.gapHeight != null &&
            m.gapWidth != null
          ) {
            setModuleH(String(m.moduleHeight));
            setModuleW(String(m.moduleWidth));
            setGapH(String(m.gapHeight));
            setGapW(String(m.gapWidth));
            setDetectNote(m.notice);
          } else if (userInitiated) {
            setDetectNote(m.notice);
          }
        },
      );
    },
    [run],
  );

  // Sync eligible configurations without touching module fields or detection state.
  useEffect(() => {
    if (!open) return;
    setSelectedConfigs((prev) => {
      const kept = prev.filter((i) => eligibleIndices.includes(i));
      if (kept.length > 0) return kept;
      if (eligibleIndices.includes(activeIndex)) return [activeIndex];
      return eligibleIndices.slice(0, 1);
    });
  }, [open, activeIndex, eligibleIndices]);

  // Apply detector-name / shape preset once per dialog open or active image change,
  // so subsequent workspace updates (e.g. after Estimate) never overwrite detected or
  // user-edited module dimensions.
  const detectorName = state?.calibration.detector;
  useEffect(() => {
    if (!open) {
      lastPresetKey.current = null;
      lastAutoDetectKey.current = null;
      return;
    }
    const presetKey = `${activeImageKey}:${detectorName ?? ""}`;
    if (lastPresetKey.current === presetKey) return;
    lastPresetKey.current = presetKey;
    const preset = modulePresetForDetector(detectorName, activeShape);
    if (preset) {
      setModuleH(preset.h);
      setModuleW(preset.w);
      setGapH(preset.gh);
      setGapW(preset.gw);
    }
    setDetectNote(null);
  }, [open, activeImageKey, detectorName, activeShape]);

  useEffect(() => {
    if (!open || !ready || model !== "per_module" || !activeShape) return;
    if (lastAutoDetectKey.current === activeImageKey) return;
    lastAutoDetectKey.current = activeImageKey;
    detectModules(false);
  }, [open, ready, model, activeShape, activeImageKey, detectModules]);

  if (!open) return null;

  const toggleConfig = (idx: number, checked: boolean) => {
    setSelectedConfigs((prev) =>
      checked
        ? [...new Set([...prev, idx])].sort((a, b) => a - b)
        : prev.filter((i) => i !== idx),
    );
  };

  const handleEstimate = () => {
    const payload: Record<string, unknown> = {
      configurations: selectedConfigs.length ? selectedConfigs : [activeIndex],
      model,
      n_passes: Math.max(1, Math.min(6, Math.round(Number(nPasses) || 3))),
      cv_folds: 5,
    };
    if (model === "smooth_spline") {
      const g = Math.max(4, Math.min(24, Math.round(Number(gridN) || 8)));
      payload.grid_nx = g;
      payload.grid_ny = g;
      payload.smoothness = Math.max(1e-6, Number(smoothness) || 1.0);
    } else if (model === "radial_optical") {
      payload.max_order = Math.max(
        3,
        Math.min(7, Math.round(Number(maxOrder) || 5)),
      );
    } else if (model === "bow_z") {
      payload.max_degree = Math.max(
        2,
        Math.min(5, Math.round(Number(maxDegree) || 3)),
      );
      payload.smoothness = Math.max(1e-8, Number(smoothness) || 1e-3);
    } else if (model === "per_module") {
      const parsedGapH = gapH.trim() === "" ? Number.NaN : Number(gapH);
      const parsedGapW = gapW.trim() === "" ? Number.NaN : Number(gapW);
      payload.module_height = Math.max(16, Math.round(Number(moduleH) || 195));
      payload.module_width = Math.max(16, Math.round(Number(moduleW) || 487));
      payload.gap_height = Number.isFinite(parsedGapH)
        ? Math.max(0, Math.round(parsedGapH))
        : 17;
      payload.gap_width = Number.isFinite(parsedGapW)
        ? Math.max(0, Math.round(parsedGapW))
        : 7;
      payload.fit_z = fitZ;
    }
    void run(
      "estimate_distortion",
      payload,
      selectedConfigs.length > 1
        ? `Estimating distortion across ${selectedConfigs.length} configurations…`
        : "Estimating detector distortion…",
    );
  };

  const hasAppliedDistortion = Boolean(state?.calibration.distortionFile);

  return (
    <Portal>
      <Dialog
        open={open}
        onDismiss={onClose}
        onClose={onClose}
        className="distortion-dialog"
        aria-labelledby="distortion-dialog-title"
      >
        <DialogHeader
          headingId="distortion-dialog-title"
          title="Detector distortion correction"
          onClose={onClose}
        />
        <div className="distortion-dialog-body">
        <div className="distortion-dialog-grid">
          <div className="distortion-controls-col">
            <section className="distortion-section">
              <div className="distortion-section-title">
                Exposures (configurations)
              </div>
              <div className="distortion-config-list">
                {summaries.map((cfg) => {
                  const sameShape =
                    !!cfg.shape &&
                    !!activeShape &&
                    cfg.shape[0] === activeShape[0] &&
                    cfg.shape[1] === activeShape[1];
                  const eligible = cfg.hasImage && cfg.calibrated && sameShape;
                  const reason = !cfg.hasImage
                    ? "No image"
                    : !cfg.calibrated
                      ? "Uncalibrated"
                      : !sameShape
                        ? "Different size"
                        : null;
                  return (
                    <label
                      key={cfg.index}
                      className={`distortion-config-row${eligible ? "" : " muted"}`}
                    >
                      <Input
                        type="checkbox"
                        disabled={!ready || !eligible}
                        checked={
                          eligible && selectedConfigs.includes(cfg.index)
                        }
                        onChange={(e) =>
                          toggleConfig(cfg.index, e.target.checked)
                        }
                      />
                      <span className="distortion-config-name">
                        {cfg.label}
                        {cfg.active ? " (active)" : ""}
                      </span>
                      <span className="distortion-config-meta">
                        {reason ??
                          `${cfg.distMm !== null ? `${cfg.distMm.toFixed(1)} mm` : ""}${cfg.imageName ? ` · ${cfg.imageName}` : ""}`}
                      </span>
                    </label>
                  );
                })}
              </div>
              {summaries.length < 2 && (
                <p className="muted distortion-tip">
                  Tip: add configurations at different detector distances or
                  positions in the top bar for stronger multi-exposure
                  constraints.
                </p>
              )}
            </section>

            <section className="distortion-section">
              <label className="field-label" htmlFor="distortion-model">
                Distortion model
                <Select
                  id="distortion-model"
                  disabled={!ready}
                  value={model}
                  onChange={(e) => {
                    const next = e.target.value as DistortionModelKind;
                    setModel(next);
                    if (next === "bow_z") setSmoothness("0.001");
                    else if (next === "smooth_spline") setSmoothness("1.0");
                  }}
                >
                  <option value="smooth_spline">
                    Smooth B-spline (.spline)
                  </option>
                  <option value="radial_optical">
                    Radial optical / taper (.spline)
                  </option>
                  <option value="bow_z">Detector bow Δz (.h5)</option>
                  <option value="per_module">
                    Per-module rigid offsets (.h5)
                  </option>
                </Select>
              </label>
              <p className="muted distortion-tip">
                {MODEL_DESCRIPTIONS[model]}
              </p>

              {model === "smooth_spline" && (
                <div className="setup-pair">
                  <label className="field-label">
                    Control grid
                    <Input
                      type="number"
                      min="4"
                      max="24"
                      step="1"
                      disabled={!ready}
                      value={gridN}
                      onChange={(e) => setGridN(e.target.value)}
                    />
                  </label>
                  <label className="field-label">
                    Smoothness
                    <Input
                      type="number"
                      min="0.0001"
                      step="any"
                      disabled={!ready}
                      value={smoothness}
                      onChange={(e) => setSmoothness(e.target.value)}
                    />
                  </label>
                </div>
              )}

              {model === "radial_optical" && (
                <label className="field-label">
                  Max radial order
                  <Select
                    disabled={!ready}
                    value={maxOrder}
                    onChange={(e) => setMaxOrder(e.target.value)}
                  >
                    <option value="3">Order 3 (cubic)</option>
                    <option value="5">Order 5 (quintic)</option>
                    <option value="7">Order 7</option>
                  </Select>
                </label>
              )}

              {model === "bow_z" && (
                <div className="setup-pair">
                  <label className="field-label">
                    Polynomial degree
                    <Select
                      disabled={!ready}
                      value={maxDegree}
                      onChange={(e) => setMaxDegree(e.target.value)}
                    >
                      <option value="2">Degree 2</option>
                      <option value="3">Degree 3</option>
                      <option value="4">Degree 4</option>
                      <option value="5">Degree 5</option>
                    </Select>
                  </label>
                  <label className="field-label">
                    Smoothness
                    <Input
                      type="number"
                      min="0.000001"
                      step="any"
                      disabled={!ready}
                      value={smoothness}
                      onChange={(e) => setSmoothness(e.target.value)}
                    />
                  </label>
                </div>
              )}

              {model === "per_module" && (
                <>
                  <div className="setup-pair">
                    <label className="field-label">
                      Module H · px
                      <Input
                        type="number"
                        min="16"
                        step="1"
                        disabled={!ready}
                        value={moduleH}
                        onChange={(e) => setModuleH(e.target.value)}
                      />
                    </label>
                    <label className="field-label">
                      Module W · px
                      <Input
                        type="number"
                        min="16"
                        step="1"
                        disabled={!ready}
                        value={moduleW}
                        onChange={(e) => setModuleW(e.target.value)}
                      />
                    </label>
                  </div>
                  <div className="setup-pair">
                    <label className="field-label">
                      Gap H · px
                      <Input
                        type="number"
                        min="0"
                        step="1"
                        disabled={!ready}
                        value={gapH}
                        onChange={(e) => setGapH(e.target.value)}
                      />
                    </label>
                    <label className="field-label">
                      Gap W · px
                      <Input
                        type="number"
                        min="0"
                        step="1"
                        disabled={!ready}
                        value={gapW}
                        onChange={(e) => setGapW(e.target.value)}
                      />
                    </label>
                  </div>
                  <label className="check-row">
                    <Input
                      type="checkbox"
                      disabled={!ready}
                      checked={fitZ}
                      onChange={(e) => setFitZ(e.target.checked)}
                    />
                    Fit out-of-plane Δz per module
                  </label>
                  <div className="distortion-module-detect">
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={!ready || !activeShape}
                      onClick={() => detectModules(true)}
                    >
                      Auto-detect modules from image
                    </Button>
                    {detectNote && (
                      <p className="muted distortion-tip">{detectNote}</p>
                    )}
                  </div>
                </>
              )}

              <label className="field-label">
                Re-picking passes
                <Input
                  type="number"
                  min="1"
                  max="6"
                  step="1"
                  disabled={!ready}
                  value={nPasses}
                  onChange={(e) => setNPasses(e.target.value)}
                />
              </label>
            </section>

            <div className="distortion-actions">
              <Button
                type="button"
                variant="primary"
                disabled={!ready || selectedConfigs.length === 0}
                onClick={handleEstimate}
              >
                Estimate distortion
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={!ready || !preview}
                onClick={() =>
                  void run(
                    "apply_distortion",
                    {},
                    "Applying distortion correction…",
                  )
                }
              >
                Apply to{" "}
                {preview && preview.exposures.length > 1
                  ? `${preview.exposures.length} configs`
                  : "configuration"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={!ready || !preview}
                onClick={() =>
                  void run(
                    "save_distortion",
                    { format: preview?.canSaveSpline ? "spline" : "h5" },
                    preview?.canSaveSpline
                      ? "Saving distortion spline…"
                      : "Saving NeXus detector…",
                  )
                }
              >
                {preview?.canSaveSpline ? "Save .spline" : "Save .h5"}
              </Button>
              {hasAppliedDistortion && (
                <Button
                  type="button"
                  variant="quiet"
                  disabled={!ready}
                  onClick={() => {
                    onClearPreview();
                    void run("distortion_file", { reset: true });
                  }}
                >
                  Clear active distortion
                </Button>
              )}
            </div>
          </div>

          <div className="distortion-preview-col">
            <DistortionCanvas preview={preview} />
            {preview && (
              <div className="distortion-metrics">
                <div className="distortion-badge-row">
                  <span
                    className={`distortion-badge ${preview.significant ? "good" : "warn"}`}
                  >
                    {preview.significant
                      ? "Statistically significant (CV)"
                      : "Not significant (CV)"}
                  </span>
                  <span className="muted">
                    {preview.nPointsUsed} pts · {preview.nPassesCompleted} pass
                    {preview.nPassesCompleted === 1 ? "" : "es"}
                  </span>
                </div>
                <div className="distortion-stat-grid">
                  <div>
                    <span className="muted">RMS (px)</span>
                    <strong>
                      {preview.rmsBeforePx.toFixed(3)} →{" "}
                      {preview.rmsAfterPx.toFixed(3)}
                    </strong>
                  </div>
                  <div>
                    <span className="muted">CV RMS (px)</span>
                    <strong>{preview.cvRmsPx.toFixed(3)}</strong>
                  </div>
                  <div>
                    <span className="muted">RMS (2θ)</span>
                    <strong>
                      {preview.rmsBeforeDegrees.toFixed(4)}° →{" "}
                      {preview.rmsAfterDegrees.toFixed(4)}°
                    </strong>
                  </div>
                  <div>
                    <span className="muted">Max |δ|</span>
                    <strong>{preview.maxDisplacementPx.toFixed(2)} px</strong>
                  </div>
                </div>
                {preview.exposures.length > 0 && (
                  <div className="distortion-exposures">
                    {preview.exposures.map((ex) => (
                      <div key={ex.index} className="distortion-exposure-row">
                        <span>{ex.label}</span>
                        <span className="muted">
                          {ex.nRings} rings · {ex.distBeforeMm.toFixed(2)} →{" "}
                          {ex.distAfterMm.toFixed(2)} mm
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        </div>
      </Dialog>
    </Portal>
  );
}

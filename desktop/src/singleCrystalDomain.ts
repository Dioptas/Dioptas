import type { Raster } from "./types";
export interface CrystalConfig {
  omega_start: number;
  omega_step: number;
  exposure: number;
  axis: [number, number, number];
  background: boolean;
  smoothness: number;
  threshold: number;
  min_pixels: number;
  link_radius: number;
  tolerance: number;
  min_cell: number;
  max_cell: number;
  group: number;
  elements: string;
  adp: "isotropic" | "anisotropic";
  search_seconds: number;
  aperture_radius: number;
  omega_radius: number;
  saturation: number;
  metric: [number, number, number, number, number, number] | null;
  scan_scaling: boolean;
  polarization: number;
  confirmed: boolean;
  gain: number;
  read_noise: number;
  refine_geometry: boolean;
  integration_method: "summation" | "profile";
  protocol: Record<string, unknown> | null;
  keep_stage_audit: boolean;
  dac_enabled: boolean;
  dac_axis: [number, number, number];
  dac_half_opening: number;
  shadow_block: number;
  seat_enabled: boolean;
  seat_threshold: number;
  seat_guard: number;
}
export const crystalDefaults: CrystalConfig = {
  omega_start: 0,
  omega_step: 0.1,
  exposure: 0.1,
  axis: [1, 0, 0],
  background: false,
  smoothness: 1e4,
  threshold: 5,
  min_pixels: 3,
  link_radius: 5,
  tolerance: 0.015,
  min_cell: 2,
  max_cell: 30,
  group: 1,
  elements: "",
  adp: "isotropic",
  search_seconds: 60,
  aperture_radius: 7,
  omega_radius: 4.5,
  saturation: 4294967294,
  metric: null,
  scan_scaling: false,
  polarization: 0.98,
  confirmed: false,
  gain: 1,
  read_noise: 0,
  refine_geometry: true,
  integration_method: "profile",
  protocol: null,
  keep_stage_audit: false,
  dac_enabled: false,
  dac_axis: [0, 0, 1],
  dac_half_opening: 35,
  shadow_block: 16,
  seat_enabled: false,
  seat_threshold: 0.85,
  seat_guard: 32,
};
export type CrystalFileOperation =
  | "calibration"
  | "protocol"
  | "protocol_save"
  | "protocol_builtin"
  | "audit"
  | "use_calibration"
  | "open"
  | "preset"
  | "save"
  | "reflections"
  | "hkl"
  | "cif";
export type CrystalEdit =
  | { operation: "undo" | "redo" }
  | {
      operation: "cell" | "track" | "frame" | "rerun" | "remove_mask";
      index: number;
    }
  | { operation: "mask"; bounds: [number, number, number, number] }
  | { operation: "clear_mask" };
export type CrystalImageKind = "raw" | "background" | "corrected";
export interface CrystalData {
  protocolTemplate: Record<string, unknown>;
  effectiveProtocol: Record<string, unknown> | null;
  protocolInspectionError: string | null;
  profileReport: {
    recipe: string;
    used?: number;
    errorFloor?: number;
    warningPolicy?: string;
    auditAvailable?: boolean;
    effectiveProtocol?: Record<string, unknown>;
    protocolSha256?: string;
  } | null;
  shadows: {
    first: number;
    last: number;
    illuminationExcluded: number;
    dacExcluded: number;
    illuminationSha256: string;
    dacSha256: string;
    referenceFrames?: number[];
  } | null;
  exported: boolean;
  canUndo: boolean;
  canRedo: boolean;
  undoLabel: string | null;
  redoLabel: string | null;
  engine: string;
  adapter: string;
  revision: number;
  config: CrystalConfig;
  frames: number;
  frame: number;
  firstSource: string | null;
  lastSource: string | null;
  filename: string | null;
  shape: [number, number];
  stages: {
    status: "pending" | "complete" | "attention" | "paused";
    detail: string;
    seconds: number;
  }[];
  geometry: {
    origin: number[];
    fast: number[];
    slow: number[];
    beam: number[];
    axis: number[];
    wavelength: number;
  } | null;
  geometryReport: {
    refined?: boolean;
    rmsPixels?: number;
    observations?: number;
    converged?: boolean;
    atBounds?: boolean;
    condition?: number;
    maximumCorrelation?: number;
    counts?: number[];
    rms?: number[][][];
    parameters?: number[];
    accepted?: boolean;
  } | null;
  predictions: { x: number; y: number; track: number }[];
  trackOffset: number;
  reflectionOffset: number;
  peaks: {
    x: number;
    y: number;
    track: number;
    flags: number;
    excluded: boolean;
  }[];
  peakCount: number;
  peakFrames: number[];
  tracks: {
    id: number;
    native: boolean;
    observed: [number, number, number];
    first: number;
    last: number;
    flags: number;
    excluded: boolean;
  }[];
  trackCount: number;
  cells: {
    direct: number[][];
    parameters: number[];
    indexed: number;
    total: number;
    rms: number;
    validation: number;
  }[];
  selected: number | null;
  reflections: {
    hkl: number[];
    native_use: boolean | null;
    omega: number;
    intensity: number;
    sigma: number;
    flags: number;
    track: number | null;
    crossing: number | null;
    correction: number;
  }[];
  reflectionCount: number;
  reflectionFilteredCount: number;
  reflectionFilter: "all" | "usable" | "excluded";
  suppliedGroupSymbol: string | null;
  usableReflections: number;
  scaling: {
    fit: {
      recipe?: string;
      applied: boolean;
      model: string;
      coefficient?: number;
      references?: number;
      variance?: number;
    };
    symbol: string;
    families: number;
    systematicAbsences: number;
    nonpositiveFamilies: number;
    repeatedFamilies: number;
    rInt: number | null;
    ccHalf: number | null;
    multiplicity: number;
    symmetryStatus: string;
    strongAbsenceViolations: number;
    absorption: string;
  } | null;
  structure: {
    r1: number;
    mode: string;
    parameters: number;
    termination: string;
    searchTermination: string;
    targetMet: boolean;
    atoms: number;
    group: number;
    observations: number;
    families: number;
    absentObservations: number;
    seed: number;
    engine: string;
  } | null;
  mask: [number, number, number, number][];
  excludedFrames: number[];
  error: string | null;
  notice: string | null;
  previewKind: CrystalImageKind;
  image: Raster | null;
}
export const crystalSteps = [
  "Frames",
  "Background",
  "Peaks",
  "Cell",
  "Geometry",
  "Intensities",
  "Scaling",
  "Structure",
  "Export",
] as const;
export function nextCrystalStep(data: CrystalData | null) {
  if (!data?.frames || !data.config.confirmed) return 0;
  const i = data.stages.findIndex((s) => s.status !== "complete");
  return i < 0 ? 8 : i + 1;
}
export function crystalFlags(
  flags: number,
  nativeUse?: boolean | null,
  nativeTrack = false,
) {
  if (nativeUse != null) {
    // Pinned PhaseSmith spots, local_background, integration and profiles bits.
    // These overlap the exploratory adapter's namespace (notably 1024/2048).
    const reasons: [number, string][] = [
      [1, "detector edge"],
      [2, "masked / shadowed pixels"],
      [4, "saturated pixels"],
      [8, "overlapping signals"],
      [16, "insufficient background pixels"],
      [32, "component too large"],
      [64, "no centroid"],
      [128, "multiple observations in one frame"],
      [256, "scan / segment partial"],
      [1024, "no data"],
      [2048, "signal reaches aperture boundary"],
      [4096, "poor background model"],
      [8192, "incomplete profile support"],
      [16384, "profile fit failed"],
      [32768, "no usable profile"],
      [131072, "profile mismatch warning"],
    ];
    const labels = reasons
      .filter(([bit]) => flags & bit)
      .map(([, reason]) => reason);
    const unknown = flags & ~reasons.reduce((mask, [bit]) => mask | bit, 0);
    if (unknown) labels.push(`unknown flags ${unknown}`);
    return (
      (nativeUse ? "usable" : "excluded") +
      (labels.length
        ? ` · ${labels.join(", ")}`
        : !nativeUse
          ? " by native validity gate"
          : "")
    );
  }

  const names: [number, string][] = [
    ...(nativeTrack
      ? ([
          [128, "multiple observations in one frame"],
          [256, "scan / segment partial"],
        ] as [number, string][])
      : []),
    [1, "edge"],
    [2, "masked"],
    [4, "saturated"],
    [8, "overlap"],
    [16, "background"],
    [32, "large"],
    [64, "no centroid"],
    [1024, "partial"],
    [2048, "position mismatch"],
  ];
  const labels = names.filter(([bit]) => flags & bit).map(([, label]) => label);
  const unknown = flags & ~names.reduce((mask, [bit]) => mask | bit, 0);
  if (unknown) labels.push(`flags ${unknown}`);
  return labels.join(", ") || "usable";
}
export function crystalConfigError(c: CrystalConfig): string | null {
  const ranges: [number, number, number, string][] = [
    [c.omega_start, -10000, 10000, "Exposure start"],
    [c.omega_step, 0.000001, 10, "Rotation step"],
    [c.smoothness, 1e-6, 1e9, "Smoothness"],
    [c.threshold, 1, 100, "Peak threshold"],
    [c.min_pixels, 1, 1000, "Minimum area"],
    [c.link_radius, 0.1, 30, "Link radius"],
    [c.tolerance, 0.001, 0.1, "Indexing tolerance"],
    [c.min_cell, 1.5, 100, "Shortest vector"],
    [c.max_cell, c.min_cell, 100, "Longest vector"],
    [c.group, 1, 230, "Space group"],
    [c.search_seconds, 1, 600, "Search budget"],
    [c.gain, 1e-9, 1e6, "Gain"],
    [c.read_noise, 0, 1e6, "Read noise"],
    [c.saturation, 1, 4294967295, "Overload threshold"],
    [c.aperture_radius, 2, 64, "Aperture half-width"],
    [c.omega_radius, 0.01, 10, "Rocking half-width"],
    [c.polarization, 0, 1, "Polarization"],
    [c.dac_half_opening, 0.01, 89.999, "DAC half opening"],
    [c.shadow_block, 1, 1024, "Shadow block"],
    [c.seat_threshold, 0.01, 0.999, "Illumination threshold"],
    [c.seat_guard, 0, 4096, "Illumination guard"],
  ];
  for (const [v, min, max, name] of ranges)
    if (!Number.isFinite(v) || v < min || v > max)
      return `${name} must be between ${min} and ${max}.`;
  if (
    !Number.isFinite(c.exposure) ||
    c.exposure <= 0 ||
    c.exposure > c.omega_step * 1.001
  )
    return "Exposure width must be positive and no larger than the rotation step.";
  if (
    ![
      c.min_pixels,
      c.group,
      c.aperture_radius,
      c.shadow_block,
      c.seat_guard,
    ].every(Number.isInteger)
  )
    return "Pixel support and space-group values must be whole numbers.";
  if (!c.dac_axis.every(Number.isFinite) || !c.dac_axis.some((v) => v !== 0))
    return "Choose a nonzero DAC axis at omega zero.";
  if (!c.axis.every(Number.isFinite) || !c.axis.some((v) => v !== 0))
    return "Choose a nonzero spindle axis.";
  const hard = (c.protocol?.search as { hard_seconds?: number } | undefined)
    ?.hard_seconds;
  if (
    c.integration_method === "profile" &&
    c.search_seconds > (typeof hard === "number" ? hard : 75)
  )
    return "Search budget exceeds the protocol hard limit. Reduce it or load a protocol with a larger declared hard_seconds budget.";
  if (c.metric) {
    if (
      c.integration_method === "profile" &&
      c.metric.slice(3).some((a) => Math.abs(a - 90) > 1e-8)
    )
      return "PhaseSmith protocol v1 requires an orthorhombic metric (all angles 90°).";
    const [a, b, d, alpha, beta, gamma] = c.metric;
    if (
      !c.metric.every(Number.isFinite) ||
      [a, b, d].some((v) => v <= 0) ||
      [alpha, beta, gamma].some((v) => v <= 0 || v >= 180)
    )
      return "Enter positive cell lengths and angles between 0° and 180°.";
    const [x, y, z] = [alpha, beta, gamma].map((v) =>
      Math.cos((v * Math.PI) / 180),
    );
    if (1 + 2 * x * y * z - x * x - y * y - z * z <= 0)
      return "The cell metric has no positive volume.";
  }
  return null;
}

export const crystalTermination = (value: string) =>
  (
    ({
      max_iterations: "Iteration limit (not fully converged)",
      max_runtime: "Time budget reached",
      gradient: "Gradient tolerance reached",
      r1_target: "Requested R1 target",
      trial_budget: "Phase-start budget reached",
    }) as Record<string, string>
  )[value] ?? value.replaceAll("_", " ");

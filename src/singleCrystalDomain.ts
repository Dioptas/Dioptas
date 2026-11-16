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
  /** The diamond anvil cell masks (DAC opening, seat shadow, diamond spots);
   * their choices are kept while off. Detector masks do not depend on it. */
  cell_masks_enabled: boolean;
  dac_enabled: boolean;
  dac_axis: [number, number, number];
  dac_half_opening: number;
  shadow_block: number;
  seat_enabled: boolean;
  seat_threshold: number;
  seat_guard: number;
  diamond_enabled: boolean;
  /** Former seed-area setting, kept for older files; not used. */
  diamond_min_area: number;
  /** Smallest diamond spot area (significant excess region), pixels. */
  diamond_min_size: number;
  diamond_tolerance: number;
  /** Round border around each diamond spot, pixels. */
  diamond_margin: number;
  /** Diamond spot detection level, sigma above the local background. */
  diamond_level: number;
  /** Apply the Mask mode mask to every frame when its shape matches. */
  shared_mask_enabled: boolean;
  /** Mask pixels that stand out on most frames (detector flaws). */
  persistent_enabled: boolean;
  /** Share of the frames a pixel must stand out on, percent (20-100). */
  persistent_fraction: number;
  /** Find lattices search; older configs load with "both". */
  lattice_method: LatticeMethod;
  /** Find lattices stops after this many grains (1-20); older configs load with 5. */
  max_grains: number;
  /** Find lattices merges lattices of one crystal whose orientations differ
   * by at most this (degrees, 0-5; 0 never merges); older configs load with 0.5. */
  merge_angle: number;
  /** Refine lattice: largest mismatch of lengths a lattice type requires to
   * be equal, percent (0-10); older configs load with 1. */
  symmetry_length_tolerance: number;
  /** Refine lattice: largest deviation of an angle a lattice type fixes,
   * degrees (0-10); older configs load with 1. */
  symmetry_angle_tolerance: number;
  /** Integrate: resolution limit (Å); null follows the detector corner. */
  integration_d_min: number | null;
  /** Integrate: side of the square peak box (px); null follows the spots. */
  integration_box: number | null;
  /** Integrate: rocking width in ω for |ζ| = 1 (°); null follows the
   * spots' spread in ω. */
  rocking_width: number | null;
  /** Integrate: profile intensity where the fit is usable; null follows the
   * default. */
  profile_fitting?: boolean | null;
}
export type LatticeMethod = "both" | "fft" | "rows";
/** Find lattices search choices; the first is the default. */
export const latticeMethods: { value: LatticeMethod; label: string }[] = [
  { value: "both", label: "FFT + row search" },
  { value: "fft", label: "FFT" },
  { value: "rows", label: "Row search" },
];
/** Which search found a candidate (older results: FFT). */
export type LatticeFound = "fft" | "rows" | "both";
export const latticeFoundLabel = (found: LatticeFound | undefined) =>
  ({ fft: "FFT", rows: "Rows", both: "FFT · Rows" })[found ?? "fft"];
/** The method of a config that may predate the setting. */
export const latticeMethod = (c: Partial<CrystalConfig>): LatticeMethod =>
  latticeMethods.some((m) => m.value === c.lattice_method)
    ? c.lattice_method!
    : "both";
/** The grain cap of a config that may predate the setting. */
export const maxGrains = (c: Partial<CrystalConfig>): number =>
  Number.isInteger(c.max_grains) && c.max_grains! >= 1 && c.max_grains! <= 20
    ? c.max_grains!
    : 5;
/** The merge angle of a config that may predate the setting. */
export const mergeAngle = (c: Partial<CrystalConfig>): number =>
  Number.isFinite(c.merge_angle) && c.merge_angle! >= 0 && c.merge_angle! <= 5
    ? c.merge_angle!
    : 0.5;
/** A merged lattice's detail: "2 domains, 0.26°". */
export const mergedNote = (merged?: { domains: number; angle: number }) =>
  merged ? `${merged.domains} domains, ${merged.angle.toFixed(2)}°` : "";
/** Unit-cell volume (Å³) from a, b, c, α, β, γ. */
export const cellVolume = (p: number[]) => {
  const [ca, cb, cg] = p.slice(3, 6).map((x) => Math.cos((x * Math.PI) / 180));
  return (
    p[0] * p[1] * p[2] * Math.sqrt(Math.max(0, 1 - ca * ca - cb * cb - cg * cg + 2 * ca * cb * cg))
  );
};
export const crystalDefaults: CrystalConfig = {
  omega_start: -34,
  omega_step: 0.5,
  exposure: 0.5,
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
  diamond_enabled: false,
  diamond_min_area: 20,
  diamond_min_size: 120,
  cell_masks_enabled: true,
  diamond_tolerance: 3,
  diamond_margin: 10,
  diamond_level: 10,
  shared_mask_enabled: true,
  persistent_enabled: false,
  persistent_fraction: 50,
  lattice_method: "both",
  max_grains: 5,
  merge_angle: 0.5,
  symmetry_length_tolerance: 1,
  symmetry_angle_tolerance: 1,
  integration_d_min: null,
  integration_box: null,
  rocking_width: null,
  profile_fitting: null,
};
/**
 * The flexible measured-track path; the fixed protocol and the omega
 * background are not offered here. Only the geometric DAC opening mask starts
 * on; the measured seat shadow and the diamond spots are opt-in.
 */
export const exploratoryCrystalConfig = (c: CrystalConfig): CrystalConfig =>
  c.integration_method === "summation"
    ? { ...c, confirmed: true, background: false }
    : {
        ...c,
        confirmed: true,
        integration_method: "summation",
        protocol: null,
        background: false,
        dac_enabled: true,
        dac_axis: [0, 0, 1],
        seat_enabled: false,
        // Measured on the ID11 Eiger scan: below 0.6 of each block's own lit
        // level plus a 20 px margin covers the umbra and the dim penumbra; 0.7
        // already follows noise at the soft edge. The margin steps by 20 px.
        seat_threshold: 0.6,
        seat_guard: 20,
        diamond_enabled: false,
        aperture_radius: 6,
        omega_radius: 1.5,
        polarization: 0.99,
        // Measured on the ID11 enstatite scan: 2 px keeps sharp 2-pixel
        // reflections (+24 % found, 202 of 219 missed ≥10σ ones) at the same
        // indexed share; 1 px admits flickering hot pixels.
        min_pixels: 2,
        link_radius: 3,
        // Refine geometry on: its gates fall back to the calibration.
        refine_geometry: true,
        scan_scaling: false,
      };
/** Settings that follow the workflow choice: the fixed profile protocol's
 * frozen controls, or the lean summation defaults. */
export const workflowDefaults = (
  method: "summation" | "profile",
): Partial<CrystalConfig> =>
  method === "profile"
    ? {
        background: false,
        aperture_radius: 7,
        omega_radius: 4.5,
        polarization: 0.98,
        link_radius: 5,
        min_pixels: 3,
        refine_geometry: true,
        scan_scaling: false,
        gain: 1,
        read_noise: 0,
        threshold: 5,
      }
    : {
        background: true,
        aperture_radius: 6,
        omega_radius: 1.5,
        polarization: 0.99,
        link_radius: 3,
        min_pixels: 2,
        refine_geometry: true,
        scan_scaling: false,
      };
const frameList = (frames: number[]) => frames.map((f) => f + 1).join(", ");
/** One line under Find spots: frames with unusually many spots (1-based). */
export const busyFramesNote = (frames: number[]) =>
  frames.length
    ? `${frames.length} frame${frames.length === 1 ? "" : "s"} with unusually many spots: ${frameList(frames)}`
    : "";
/** One line under Find spots while frames are left out (1-based). */
export const excludedFramesNote = (frames: number[]) =>
  frames.length
    ? `Excluded frame${frames.length === 1 ? "" : "s"}: ${frameList([...frames].sort((a, b) => a - b))}`
    : "";
/** `scxrd_edit {operation:"estimate_dac"}`: start and DAC half-opening fitted
 * to the measured cell shadow. Null values were not determined. */
export interface DacEstimate {
  status: "both" | "opening_only" | "no_shadow" | "undetermined";
  omegaStart: number | null;
  halfOpening: number | null;
  /** Overlap of measured shadow and mask (0-1) at the old and new values. */
  before: number;
  after: number;
  startRange: [number, number] | null;
  openingRange: [number, number] | null;
  darkShare: number;
  /** Frames read (0-based). */
  frames: number[];
  block: number;
  seconds: number;
}
/** The settings an estimate determines (none without a usable shadow). */
export const dacEstimatePatch = (e: DacEstimate): Partial<CrystalConfig> => ({
  ...(e.omegaStart != null && { omega_start: e.omegaStart }),
  ...(e.halfOpening != null && { dac_half_opening: e.halfOpening }),
});
/** One line for the panel. */
export const dacEstimateSummary = (e: DacEstimate) => {
  const angle = (v: number | null) => `${v?.toFixed(2)}°`;
  const fit = `fit ${Math.round(e.before * 100)} → ${Math.round(e.after * 100)} %`;
  switch (e.status) {
    case "both":
      return `Start ${angle(e.omegaStart)}, opening ${angle(e.halfOpening)} · ${fit}`;
    case "opening_only":
      return `Shadow at one end only: start kept, opening ${angle(e.halfOpening)} · ${fit}`;
    case "no_shadow":
      return "No cell shadow in the frames; nothing changed";
    default:
      return "The shadow does not fix the opening; nothing changed";
  }
};
/** Settings whose change clears the prepared masks. */
const maskInputs: (keyof CrystalConfig)[] = [
  "axis",
  "omega_start",
  "omega_step",
  "exposure",
  "dac_enabled",
  "dac_half_opening",
  "seat_enabled",
  "diamond_enabled",
  "cell_masks_enabled",
  "shared_mask_enabled",
  "persistent_enabled",
];
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
  | { operation: "keep"; index: number; keep: boolean }
  /** Refine a lattice (row in Find lattices) as another listed type. */
  | { operation: "symmetry"; index: number; choice: number }
  /** Marks a lattice's spots on the image (view only, no undo entry). */
  | { operation: "show"; index?: number }
  | { operation: "mask"; bounds: [number, number, number, number] }
  | { operation: "clear_mask" }
  | { operation: "estimate_dac" }
  /** Leave frames out of every step, or take them back. */
  | { operation: "exclude_frames"; frames: number[]; exclude: boolean };
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
    /** Prepare masks: the numbers of each mask in use. */
    masks?: MaskCounts;
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
    /** Owning lattice, 1-based; 0 none (older snapshots: absent). */
    lattice?: number;
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
    found?: LatticeFound;
    /** Kept for the following steps (the row's tick). */
    kept?: boolean;
    /** Merged from domains of one crystal (count, largest misorientation °). */
    merged?: { domains: number; angle: number };
  }[];
  /** Refine lattice: one per kept lattice (older snapshots: absent). */
  refinedLattices?: RefinedLattice[];
  /** Refine geometry product (absent until it ran or when it was off). */
  poseFit?: PoseFit | null;
  /** Integrate: defaults, settings and per-lattice statistics. */
  integration?: IntegrationSummary;
  /** Integrate: predicted positions on the shown frame. */
  integratedMarkers?: IntegratedMarker[];
  /** Integrate: one page of the reflection table. */
  integratedTable?: IntegratedTable;
  /** First kept lattice, used by the following steps. */
  selected: number | null;
  /** Lattice whose spots are marked on the image. */
  shownLattice?: number | null;
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
  /** Frames (0-based) with far more spots than the scan's typical frame,
   * once Find spots is complete (e.g. looking into the cell body). */
  busyFrames?: number[];
  error: string | null;
  notice: string | null;
  previewKind: CrystalImageKind;
  image: Raster | null;
  /** Prepared masks (shadows, diamond spots) on the shown frame. */
  maskImage?: Raster | null;
  /** Mask mode mask for this series: ready, another detector shape, or none. */
  sharedMask?: SharedMaskStatus;
  /** File and file frame of the shown frame. */
  source?: { path: string; frame: number } | null;
}
/** A lattice type the lattice fits, in PhaseSmith's standard setting. */
export interface SymmetryCandidate {
  /** Bravais symbol, aP … cF. */
  bravais: string;
  cell: number[];
  constrained: number[];
  /** Largest relative mismatch of lengths that must be equal (fraction). */
  length_deviation: number;
  /** Largest deviation of a fixed angle or obliquity (degrees). */
  angle_deviation: number;
}
export interface LatticeRefinement {
  bravais: string;
  /** Refined conventional direct rows (Å). */
  conventional: number[][];
  cell: number[];
  cell_su: number[];
  volume: number;
  volume_su: number;
  /** RMS of |q_obs − q_calc| (Å⁻¹). */
  rms: number;
  used: number;
  owned: number;
  converged: boolean;
}
export interface RefinedLattice {
  /** Row in Find lattices. */
  lattice: number;
  /** Highest symmetry first; triclinic last. */
  candidates: SymmetryCandidate[];
  chosen: number;
  result?: LatticeRefinement;
  error?: string;
}
/** Refine geometry: detector pose and crystal orientation, cell fixed. */
export interface PoseFit {
  /** Lattice row the pose was fitted on. */
  lattice: number;
  /** Passed PhaseSmith's gates; its pose is in use. */
  passed: boolean;
  /** Why the calibration was kept. */
  reason?: string;
  cycles: number;
  /** Position RMS in px, [training, withheld] × [before, after]. */
  rms: number[][];
  /** Spots in the fit, [training, withheld]. */
  counts: number[];
  /** Detector centre shift in mm along fast, slow and the normal (away
   * from the sample). */
  shift: number[];
  /** Pixel size along fast and slow, mm. */
  pixel: number[];
  /** Detector rotation (°). */
  tilt: number;
  /** Largest turn of a crystal axis (°). */
  turn: number;
  converged: boolean;
  at_bounds: boolean;
  condition: number;
  /** Refine lattice product on the calibration. */
  before: RefinedLattice[];
  before_detail: string;
}
const signed = (x: number, decimals: number) => {
  const text = Math.abs(x).toFixed(decimals);
  return Number(text) === 0 ? text : `${x < 0 ? "−" : "+"}${text}`;
};
/**
 * Refine geometry in a few lines: the position RMS before → after, how the
 * detector and the crystal moved, the spots used and the cell on the
 * calibration (for comparison with the refined one above). A kept
 * calibration is one line.
 */
export function poseLines(p: PoseFit, lattices = 1) {
  if (!p.passed)
    return { kept: `Calibration kept: ${p.reason ?? "the fit failed its gates."}` };
  const [training, withheld] = p.rms;
  const [fast, slow, normal] = p.shift;
  const before = p.before.find((r) => r.lattice === p.lattice)?.result;
  const px = (pair: number[]) => `${pair[0].toFixed(2)} → ${pair[1].toFixed(2)} px`;
  return {
    rms: `${px(withheld)} withheld`,
    training: `${px(training)} training · ${p.counts[0] + p.counts[1]} spots${lattices > 1 ? ` of lattice ${p.lattice + 1}` : ""}`,
    moved: `Centre ${signed(fast / p.pixel[0], 2)}, ${signed(slow / p.pixel[1], 2)} px · distance ${signed(normal, 3)} mm`,
    turned: [
      `Tilt ${p.tilt.toFixed(3)}°`,
      `crystal ${p.turn.toFixed(3)}°`,
      ...(p.cycles > 1 ? [`${p.cycles} cycles`] : []),
    ].join(" · "),
    before: before ? `Calibration: ${refinedCellLines(before).lengths}` : "",
  };
}
/** Integrate settings in effect (or derived from the data). */
export interface IntegrationSettings {
  d_min: number;
  box_size: number;
  rocking: number;
  /** Profile intensity where the fit is usable, summation elsewhere. */
  profiles?: boolean;
  /** The derived rocking width is the step floor, not a measured spread. */
  rocking_floor?: boolean;
}
/** R_int of a resolution shell (limits d, Å) or I/σ bin. */
export interface IntegrationBin {
  limits: [number | null, number | null];
  r_int: number | null;
  reflections: number;
}
export interface IntegrationStats {
  /** Crossings in the scan and on the detector, not hidden by masks. */
  predicted: number;
  /** Crossings whose centre is masked or on an excluded frame. */
  hidden: number;
  measured: number;
  /** Measured and unflagged. */
  usable: number;
  /** Usable with I/σ > 3. */
  strong: number;
  /** Usable reflections whose intensity is the profile-fitted one. */
  profiled?: number;
  /** Profile fitting: "fitted (N teachers)" or "failed: why". */
  profile?: string | null;
  /** Largest and smallest d of the usable reflections (Å). */
  d_range: [number, number];
  /** Laue class of the holohedry used for equivalents. */
  laue: string;
  r_int: number | null;
  redundancy: number;
  completeness: number;
  unique: number;
  possible: number;
  /** Count per flag, in `flagNames` order. */
  flags: number[];
  /** Why a fitted profile was not used: count per profile flag, in
   * `profileFlagNames` order. */
  profile_flags?: number[];
  /** Usable reflections a detected spot lies on. */
  detected: number;
  /** Of those, the ones with I/σ > 3. */
  detected_strong?: number;
  /** Median predicted − centroid distance of strong reflections (px). */
  offset: number | null;
  shells: IntegrationBin[];
  bins: IntegrationBin[];
}
export interface IntegratedLattice {
  lattice: number;
  bravais: string;
  cell: number[];
  stats: IntegrationStats;
}
export interface IntegrationSummary {
  defaults: IntegrationSettings | null;
  settings: IntegrationSettings | null;
  lattices: IntegratedLattice[];
  flagNames: string[];
  profileFlagNames?: string[];
}
export interface IntegratedMarker {
  x: number;
  y: number;
  /** Row in Find lattices. */
  lattice: number;
  usable: boolean;
}
export type IntegratedFilter = "all" | "usable" | "flagged";
export interface IntegratedTable {
  lattice: number;
  offset: number;
  filter: IntegratedFilter;
  count: number;
  rows: {
    hkl: number[];
    i: number;
    sigma: number;
    d: number;
    omega: number;
    flags: number;
    /** Short flag letters (E edge, M masked, S saturated, O overlap,
     * B background, W wider than the box, A axial, P partial, N no data). */
    letters: string;
    usable?: boolean;
    /** Summation intensity and σ (corrected). */
    summed?: [number, number];
    /** Profile-fitted intensity and σ, when profiles were fitted. */
    profile?: [number, number] | null;
    profileFlags?: number | null;
    /** The intensity in use (`i`, `sigma`) is the profile one. */
    profiled?: boolean;
    /** Names of the profile flags (why the profile value is not used). */
    profileWhy?: string | null;
  }[];
}
/** Rows per page of the reflection table (as the processor sends them). */
export const INTEGRATED_PAGE = 100;
type IntegrationKey = "integration_d_min" | "integration_box" | "rocking_width";
const DEFAULT_KEYS: Record<IntegrationKey, "d_min" | "box_size" | "rocking"> = {
  integration_d_min: "d_min",
  integration_box: "box_size",
  rocking_width: "rocking",
};
/**
 * One Integrate setting: the user's value, or the value derived from the
 * data while none is set (`auto`). Without a derived value (no calibration
 * yet) the box shows a neutral placeholder number.
 */
export function integrationSetting(
  config: Partial<CrystalConfig>,
  summary: IntegrationSummary | undefined,
  key: IntegrationKey,
) {
  const own = config[key];
  const derived = summary?.defaults?.[DEFAULT_KEYS[key]];
  const fallback = { integration_d_min: 0.8, integration_box: 9, rocking_width: 0.5 }[key];
  return {
    value: own ?? derived ?? fallback,
    auto: own == null,
  };
}
/** Clear the user's Integrate settings: all follow the data again. */
export const integrationAuto: Partial<CrystalConfig> = {
  integration_d_min: null,
  integration_box: null,
  rocking_width: null,
  profile_fitting: null,
};
/** Profile fitting in effect: the user's choice, or the default. */
export function profileFitting(
  config: Partial<CrystalConfig>,
  summary: IntegrationSummary | undefined,
) {
  const own = config.profile_fitting;
  return { value: own ?? summary?.defaults?.profiles ?? true, auto: own == null };
}
const share = (x: number) => `${(100 * x).toFixed(x < 0.1 ? 1 : 0)} %`;
/**
 * One lattice's Integrate result as label/value rows, few and short, and
 * one muted line with the rest.
 */
export function integrationLines(s: IntegrationStats) {
  const rows: [string, string][] = [
    ["Reflections", `${s.usable} usable of ${s.predicted}`],
    ...(s.profiled
      ? ([["Profile fitted", `${s.profiled} of ${s.usable}`]] as [string, string][])
      : []),
    ["I/σ > 3", s.usable ? share(s.strong / s.usable) : "—"],
    [
      "Resolution",
      s.usable ? `${s.d_range[0].toFixed(2)}–${s.d_range[1].toFixed(2)} Å` : "—",
    ],
    [`R_int (${s.laue})`, s.r_int == null ? "—" : `${(100 * s.r_int).toFixed(1)} %`],
    [
      "Redundancy",
      `${s.redundancy.toFixed(1)} · ${share(s.completeness)} complete`,
    ],
  ];
  const note = [
    `${s.measured} measured`,
    ...(s.hidden ? [`${s.hidden} under masks`] : []),
    `${s.usable - s.detected} without a found spot`,
    ...(s.offset == null ? [] : [`offset ${s.offset.toFixed(2)} px`]),
    ...(s.profile?.startsWith("failed") ? ["profiles failed, summation used"] : []),
  ].join(" · ");
  return { rows, note };
}
/** The most frequent flags of a lattice, e.g. "masked 426 · boundary 97";
 * `counts` picks another tally (the profile flags). */
export function flagCounts(
  s: IntegrationStats,
  names: string[],
  most = 3,
  counts: number[] = s.flags,
) {
  return counts
    .map((n, i) => [names[i] ?? `bit ${i}`, n] as const)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, most)
    .map(([name, n]) => `${name} ${n}`)
    .join(" · ");
}
/** Cross colours of predicted positions, one per integrated lattice;
 * apart from the orange detected spots and the green shown lattice. */
export const LATTICE_TONES = ["#69baff", "#ff6ad5", "#ffd60a", "#64d2ff", "#bf5af2"];
export function latticeTone(lattice: number, lattices: number[]) {
  const i = Math.max(0, lattices.indexOf(lattice));
  return LATTICE_TONES[i % LATTICE_TONES.length];
}
/** A table intensity: few decimals, signed. */
export const intensityText = (v: number) =>
  !Number.isFinite(v)
    ? "—"
    : Math.abs(v) >= 1000
      ? v.toFixed(0)
      : Math.abs(v) >= 10
        ? v.toFixed(1)
        : v.toFixed(2);
/** A symmetry tolerance of a config that may predate the setting. */
export const symmetryTolerance = (value: number | undefined) =>
  Number.isFinite(value) && value! > 0 && value! <= 10 ? value! : 1;
const BRAVAIS_NAMES: Record<string, string> = {
  aP: "Triclinic",
  mP: "Primitive monoclinic",
  mC: "C-centred monoclinic",
  oP: "Primitive orthorhombic",
  oC: "C-centred orthorhombic",
  oI: "Body-centred orthorhombic",
  oF: "Face-centred orthorhombic",
  tP: "Primitive tetragonal",
  tI: "Body-centred tetragonal",
  hP: "Hexagonal",
  hR: "Rhombohedral (hexagonal axes)",
  cP: "Primitive cubic",
  cI: "Body-centred cubic",
  cF: "Face-centred cubic",
};
export const bravaisName = (symbol: string) => BRAVAIS_NAMES[symbol] ?? symbol;
/**
 * A value with its standard uncertainty in crystallographic notation: the
 * uncertainty in units of the last digit, two digits up to 19, otherwise one
 * ("18.2301(12)", "18.230(4)", "833(12)", "830(30)"). Without an
 * uncertainty the value is given with `fallback` decimals.
 */
export function withUncertainty(value: number, su: number, fallback = 2) {
  if (!Number.isFinite(value)) return "—";
  if (!(su > 0) || !Number.isFinite(su)) return value.toFixed(fallback);
  let exponent = Math.floor(Math.log10(su));
  // Two digits while they read 10-19, otherwise one.
  let digits = Math.round(su / 10 ** (exponent - 1));
  if (digits >= 100) {
    exponent += 1;
    digits = Math.round(su / 10 ** (exponent - 1));
  }
  let decimals = digits < 20 ? 1 - exponent : -exponent;
  let units = Math.round(su * 10 ** decimals);
  if (units >= 20 && decimals > -exponent) {
    // 19.6 rounds to 20: one digit.
    decimals -= 1;
    units = Math.round(su * 10 ** decimals);
  }
  if (decimals >= 0) return `${value.toFixed(decimals)}(${units})`;
  const scale = 10 ** -decimals;
  return `${Math.round(value / scale) * scale}(${units * scale})`;
}
/** Deviations of a candidate from its constraints: "0.12 % · 0.08°". */
export const deviationLabel = (c: SymmetryCandidate) =>
  c.bravais === "aP"
    ? "—"
    : `${(100 * c.length_deviation).toFixed(2)} % · ${c.angle_deviation.toFixed(2)}°`;
/** Angles a candidate's type leaves free (shown with the lengths). */
const FREE_ANGLES: Record<string, number[]> = { aP: [3, 4, 5], mP: [4], mC: [4] };
/** One line for a candidate: lengths and its free or non-90° angles. */
export function candidateCell(c: SymmetryCandidate) {
  const p = c.constrained;
  const lengths = p.slice(0, 3).map((x) => x.toFixed(3)).join(" · ");
  const names = ["α", "β", "γ"];
  const angles = [3, 4, 5]
    .filter((i) => (FREE_ANGLES[c.bravais] ?? []).includes(i) || Math.abs(p[i] - 90) > 1e-6)
    .map((i) => `${names[i - 3]} ${p[i].toFixed(2)}°`);
  return { lengths: `${lengths} Å`, angles: angles.join(" · ") };
}
/** The refined cell in crystallographic notation. */
export function refinedCellLines(r: LatticeRefinement) {
  const lengths = r.cell
    .slice(0, 3)
    .map((x, i) => withUncertainty(x, r.cell_su[i], 4))
    .join(" · ");
  const angles = r.cell
    .slice(3)
    .map((x, i) => withUncertainty(x, r.cell_su[i + 3], Math.abs(x - Math.round(x)) < 1e-9 ? 0 : 3))
    .join(" · ");
  return {
    lengths: `${lengths} Å`,
    angles: `${angles}°`,
    volume: `${withUncertainty(r.volume, r.volume_su, 1)} Å³`,
    fit: `${r.used} spots · rms ${r.rms.toFixed(4)} Å⁻¹${r.converged ? "" : " · not converged"}`,
  };
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
    [c.diamond_min_size, 1, 1000000, "Diamond spot size"],
    [c.diamond_margin, 0, 200, "Diamond spot margin"],
    [c.diamond_level, 3, 50, "Diamond spot level"],
    [c.persistent_fraction, 20, 100, "Persistent pixel frame share"],
    [c.symmetry_length_tolerance ?? 1, 0.01, 10, "Length tolerance"],
    [c.symmetry_angle_tolerance ?? 1, 0.01, 10, "Angle tolerance"],
    [c.integration_d_min ?? 1, 0.2, 50, "Resolution limit"],
    [c.integration_box ?? 9, 3, 41, "Peak box"],
    [c.rocking_width ?? 0.5, 0.01, 20, "Rocking width"],
  ];
  for (const [v, min, max, name] of ranges)
    if (!Number.isFinite(v) || v < min || v > max)
      return `${name} must be between ${min} and ${max}.`;
  if (c.integration_box != null && c.integration_box % 2 === 0)
    return "Peak box must be an odd number of pixels.";
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

export type SharedMaskStatus = "none" | "shape" | "ready";
/** Short note beside the Mask mode mask switch; null when it applies. */
export const sharedMaskNote = (status: SharedMaskStatus | undefined) =>
  status === "shape" ? "other shape" : status === "ready" ? null : "empty";
/**
 * `open_image` arguments that make the shown frame the shared detector image
 * (Mask, Calibration, Integration); the shared calibration is left alone.
 */
export const sharedImageRequest = (data: Pick<CrystalData, "source">) =>
  data.source ? { path: data.source.path, frame: data.source.frame } : null;

/** Prepare masks numbers (backend `mask_counts`): percentages of all scan
 * pixels (`total` counts overlaps once) and counts. Absent keys: not in use. */
export interface MaskCounts {
  total: number;
  dac?: number;
  seat?: number;
  diamonds?: number;
  persistent?: number;
  shared?: number;
  /** The DAC mask misses the measured shadow (check the rotation axis). */
  warning?: string;
}
export type MaskKey = "dac" | "seat" | "diamond" | "persistent" | "shared";
const MASK_SWITCHES: Record<MaskKey, keyof CrystalConfig> = {
  dac: "dac_enabled",
  seat: "seat_enabled",
  diamond: "diamond_enabled",
  persistent: "persistent_enabled",
  shared: "shared_mask_enabled",
};
export const maskSwitch = (key: MaskKey) => MASK_SWITCHES[key];
/** The two mask groups: the cell masks follow `cell_masks_enabled`. */
export const cellMasks: MaskKey[] = ["dac", "seat", "diamond"];
export const detectorMasks: MaskKey[] = ["persistent", "shared"];
const trim = (v: number, digits: number) => String(+v.toFixed(digits));
const percent = (v: number) =>
  `${v < 0.1 && v > 0 ? "< 0.1" : v.toFixed(1)}\u00a0%`;
/** Each mask row's result, right of its name; null shows nothing. */
export function maskResult(
  key: MaskKey,
  config: CrystalConfig,
  counts: MaskCounts | undefined,
  shared: SharedMaskStatus | undefined,
): string | null {
  const on =
    !!config[MASK_SWITCHES[key]] &&
    (!cellMasks.includes(key) || config.cell_masks_enabled);
  if (key === "shared" && on && shared !== "ready")
    return sharedMaskNote(shared);
  if (!on) return null;
  if (key === "dac") return `${trim(config.dac_half_opening, 2)}°`;
  if (!counts) return null;
  const n =
    key === "seat"
      ? counts.seat
      : key === "diamond"
        ? counts.diamonds
        : key === "persistent"
          ? counts.persistent
          : counts.shared;
  if (n == null) return null;
  if (key === "seat") return percent(n);
  if (key === "diamond") return `${n} spot${n === 1 ? "" : "s"}`;
  return `${n}\u00a0px`;
}
/** Total masked share for the Prepare masks row; null before it is made. */
export const maskTotal = (counts: MaskCounts | undefined) =>
  counts ? `${percent(counts.total)} masked` : null;
/**
 * The collapsed Setup line: start, step (and width when it differs), axis
 * with its sense, wavelength. Negative numbers use a true minus sign.
 */
export function setupSummary(
  config: Pick<
    CrystalConfig,
    "omega_start" | "omega_step" | "exposure" | "axis"
  >,
  wavelength: number | null | undefined,
) {
  const n = (v: number, d = 3) => trim(v, d).replace("-", "\u2212");
  const vertical = !!config.axis[0];
  const sign = (config.axis[0] || config.axis[1] || 1) < 0 ? -1 : 1;
  const parts = [
    `${n(config.omega_start)}°`,
    `step ${n(config.omega_step, 4)}°` +
      (config.exposure !== config.omega_step
        ? ` / ${n(config.exposure, 4)}°`
        : ""),
    `${vertical ? "vertical" : "horizontal"} ${sign > 0 ? "\u21ba" : "\u21bb"}`,
    wavelength ? `λ ${n(wavelength, 4)} Å` : "no calibration",
  ];
  return parts.join(" · ");
}
/** Width per frame follows Step unless the user chose to set it, or an
 * existing configuration already holds a different width. */
export const widthFollowsStep = (
  config: Pick<CrystalConfig, "omega_step" | "exposure">,
  separate: boolean,
) => !separate && config.exposure === config.omega_step;
/** A new Step, with the width in the same settings command when it follows. */
export const stepPatch = (
  config: Pick<CrystalConfig, "omega_step" | "exposure">,
  step: number,
  separate: boolean,
): Partial<CrystalConfig> =>
  widthFollowsStep(config, separate)
    ? { omega_step: step, exposure: step }
    : { omega_step: step };

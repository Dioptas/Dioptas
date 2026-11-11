import type { BatchData } from "./batchDomain";
import type { MapData } from "./mapDomain";
import type {
  Cake,
  Pattern,
  Raster,
  Response,
  RingOverlay,
  State,
} from "./types";

/** State owned by processor snapshots. UI drafts, display preferences and plot
 * viewports have independent owners and are deliberately outside this model. */
export interface ResponseSnapshot {
  state: State | null;
  image: Raster | null;
  rawImage: Raster | null;
  mask: Raster | null;
  cake: Cake | null;
  pattern: Pattern | null;
  batch: BatchData | null;
  map: MapData | null;
  rings: RingOverlay[];
  linked: Response["linked"];
  batchWarning: string | null;
  mapWarning: string | null;
  showOriginalPattern: boolean;
  originalPatternColor: string;
}
export function initialResponseSnapshot(): ResponseSnapshot {
  return {
    state: null,
    image: null,
    rawImage: null,
    mask: null,
    cake: null,
    pattern: null,
    batch: null,
    map: null,
    rings: [],
    linked: undefined,
    batchWarning: null,
    mapWarning: null,
    showOriginalPattern: true,
    originalPatternColor: "#ffffff",
  };
}

export function responseState(
  previous: State | null,
  result: Response,
): State | null {
  const next = result.state;
  if (!next) return previous;
  if (!previous || !result.patternOnly) return next;
  // A pattern-only reply carries current undo state but must not replace
  // detector inputs/drafts or reconstruct the existing plot geometry.
  return {
    ...next,
    calibration: {
      ...previous.calibration,
      canUndo: next.calibration.canUndo,
      canRedo: next.calibration.canRedo,
    },
    geometry: previous.geometry,
    integration: { ...next.integration, roi: previous.integration.roi },
  };
}
export function sameRasterSource(
  a: Raster | null | undefined,
  b: Raster | null | undefined,
) {
  return (
    a?.data === b?.data && a?.width === b?.width && a?.height === b?.height
  );
}

/** Pure response transition. Presence checks are intentional: omitted products
 * retain their owners, explicit null clears nullable products, and source buffers
 * are never copied, converted or rebound by the UI's response application. */
export function reduceResponseSnapshot(
  previous: ResponseSnapshot,
  result: Response,
): ResponseSnapshot {
  if (!result.ok)
    throw new Error(result.error || "The operation could not be completed.");
  const next = { ...previous, state: responseState(previous.state, result) };
  if ("batch" in result) next.batch = result.batch ?? null;
  if (result.batchPhaseLines !== undefined && next.batch)
    next.batch = { ...next.batch, phaseLines: result.batchPhaseLines };
  if (result.batchSelection !== undefined && next.batch)
    next.batch = {
      ...next.batch,
      selected: result.batchSelection,
      pattern: result.pattern ?? next.batch.pattern,
      position: result.batchPosition ?? next.batch.position,
    };
  if ("batchWarning" in result) next.batchWarning = result.batchWarning ?? null;
  if ("map" in result) next.map = result.map ?? null;
  if ("mapWarning" in result) next.mapWarning = result.mapWarning ?? null;
  if (result.state) {
    if (typeof result.state.integration.originalPatternVisible === "boolean")
      next.showOriginalPattern =
        result.state.integration.originalPatternVisible;
    if (result.state.integration.originalPatternColor)
      next.originalPatternColor = result.state.integration.originalPatternColor;
  }
  if (result.clearImage) {
    next.image = null;
    next.rawImage = null;
    next.mask = null;
  }
  if (result.rawImage) next.rawImage = result.rawImage;
  if (result.image) next.image = result.image;
  if ("linked" in result) next.linked = result.linked;
  if (result.mask)
    next.mask = sameRasterSource(next.mask, result.mask)
      ? next.mask
      : result.mask;
  if (result.rings) next.rings = result.rings;
  if ("pattern" in result) next.pattern = result.pattern ?? null;
  if ("cake" in result) next.cake = result.cake ?? null;
  return (Object.keys(next) as (keyof ResponseSnapshot)[]).every(
    (key) => next[key] === previous[key],
  )
    ? previous
    : next;
}

/** Image/configuration/source identity for retaining a physical selected point.
 * Neither revision-only updates nor display-only unit changes invalidate it. */
export function clickContext(state: State | null) {
  return JSON.stringify([
    state?.imagePath,
    state?.selectedImageSource,
    state?.configurationContext ?? state?.configurationIndex,
    state?.projectName,
    state?.integration.frame,
    state?.integration.patternName,
    state?.calibration.transformations,
    state?.geometry,
    state?.shape,
  ]);
}

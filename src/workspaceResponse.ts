import type { Response, Raster, Cake, State, RingOverlay } from "./types";
import {
  clickContext,
  reduceResponseSnapshot,
  sameRasterSource,
} from "./responseSnapshot.ts";
import type { ResponseSnapshot } from "./responseSnapshot.ts";

type Ref<T> = { current: T };
type ConfigurationDisplay = {
  configurationChanged: boolean;
  cakeDisplayChanged: boolean;
  restore(): void;
};
/** Named domain ports keep response effects at their existing owners. The pure
 * snapshot transition owns scientific/render data; this adapter owns ordering
 * between configuration preferences, transient inspection and UI workflow. */
export interface WorkspaceResponsePorts {
  snapshot: {
    current: Ref<ResponseSnapshot>;
    publish(next: ResponseSnapshot): void;
  };
  configuration: {
    begin(result: Response, previous: State | null): ConfigurationDisplay;
  };
  session: {
    current: Ref<State | null>;
    supportsProducts: Ref<boolean>;
    canDefer: Ref<boolean>;
    retainedClick: Ref<string | undefined>;
    phaseGuideRevision: Ref<number | null>;
    resetCalibrationDrafts(state: State): void;
    clearCalibrationSelection(): void;
  };
  detector: {
    source: Ref<Raster | null>;
    rawSource: Ref<Raster | null>;
    invalidateHover(clearTimer: boolean): void;
    autoActive: Ref<boolean>;
    useRaw(): boolean;
    levels(value: [number, number]): void;
    resetView(): void;
  };
  cake: {
    source: Ref<Cake | null>;
    autoActive: Ref<boolean>;
    levels(value: [number, number]): void;
  };
  inspection: {
    linked: Ref<Response["linked"]>;
    batchPosition(result: Response): void;
  };
  products: {
    guides(value: RingOverlay[]): void;
    ring(value: number): void;
    requestedRings: Ref<{ rings: boolean }>;
    requestedRingContext: Ref<string | null>;
  };
  workflow: {
    revealOverlays(): void;
    openBatch(): void;
    notice(message: string | null): void;
  };
}

/** Apply a successful snapshot synchronously inside the command reservation.
 * Canonical backend refs intentionally receive the unmerged state, while React
 * receives the pattern-only merge from reduceResponseSnapshot. */
export function applyWorkspaceResponse(
  result: Response,
  ports: WorkspaceResponsePorts,
  resetImageView = true,
  retainClick = false,
) {
  const next = reduceResponseSnapshot(ports.snapshot.current.current, result);
  const display = ports.configuration.begin(
    result,
    ports.session.current.current,
  );
  if (result.batchWaterfallCreated) ports.workflow.revealOverlays();
  if (result.batchPosition) ports.inspection.batchPosition(result);
  if (result.batchOpened) ports.workflow.openBatch();
  if (result.state) {
    ports.session.supportsProducts.current =
      result.state.supportsRequestedProducts === true;
    if (result.calibrationReset)
      ports.session.resetCalibrationDrafts(result.state);
    if (result.calibrationReset || result.imageStateReset)
      ports.session.clearCalibrationSelection();
    if (retainClick)
      ports.session.retainedClick.current = clickContext(result.state);
    ports.session.current.current = result.state;
    // Explicit compatibility with an already-running older comparison worker.
    ports.session.canDefer.current = "integrationDirty" in result.state;
    if (result.patternOnly && !result.phaseOnly)
      ports.session.phaseGuideRevision.current = result.state.revision;
  }
  if (result.phaseGuides) ports.products.guides(result.phaseGuides);
  if (result.clearImage) {
    ports.detector.source.current = null;
    ports.detector.rawSource.current = null;
    ports.detector.invalidateHover(false);
  }
  if (result.rawImage) ports.detector.rawSource.current = result.rawImage;
  if (result.image) {
    const sourceChanged = !sameRasterSource(
      result.image,
      ports.detector.source.current,
    );
    ports.detector.source.current = result.image;
    ports.detector.invalidateHover(true);
    if (
      sourceChanged &&
      (ports.detector.autoActive.current || display.configurationChanged)
    )
      ports.detector.levels(
        ports.detector.useRaw() && result.rawImage
          ? result.rawImage.limits
          : result.image.limits,
      );
    if (resetImageView) ports.detector.resetView();
  }
  if (result.levels)
    (result.display === "cake" ? ports.cake.levels : ports.detector.levels)(
      result.levels,
    );
  if (result.nextRing !== undefined) ports.products.ring(result.nextRing);
  if ("linked" in result) ports.inspection.linked.current = result.linked;
  if (
    result.rings &&
    !result.rings.length &&
    !ports.products.requestedRings.current.rings
  )
    ports.products.requestedRingContext.current = null;
  if ("cake" in result) {
    if (
      result.cake &&
      (ports.cake.autoActive.current || display.cakeDisplayChanged) &&
      !sameRasterSource(result.cake, ports.cake.source.current)
    )
      ports.cake.levels(result.cake.limits);
    ports.cake.source.current = result.cake ?? null;
  }
  ports.snapshot.publish(next);
  display.restore();
  if (display.configurationChanged) ports.session.clearCalibrationSelection();
  if (result.configurationNavigation) {
    const { advanced, skipped } = result.configurationNavigation;
    ports.workflow.notice(
      advanced.length
        ? `Advanced ${advanced.length} configuration${advanced.length === 1 ? "" : "s"}${skipped.length ? ` · ${skipped.length} without a matching file` : ""}`
        : "No matching files for configuration browsing",
    );
  }
  if (result.savedPath || result.savedPaths?.length)
    ports.workflow.notice(
      result.savedPaths?.length
        ? `Saved ${result.savedPaths.length} batch files`
        : `Saved ${result.savedPath!.split(/[\\/]/).at(-1)}`,
    );
}

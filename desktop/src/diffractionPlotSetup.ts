import {
  detectorViewport,
  plotViewContext,
  type SharedPlotViews,
} from "./plotViewport";
import type { ComponentProps } from "react";
import type { RasterView } from "./RasterView";
import type { PatternView } from "./PatternView";
import type { PatternHover } from "./plotReadout";
import type { Pattern, Raster, Response, State } from "./types";
import { patternPositionInUnit, type PatternPosition } from "./linkedPosition";

type DetectorProps = ComponentProps<typeof RasterView>;
type PatternProps = ComponentProps<typeof PatternView>;

/** Common detector setup; display levels and mode-specific tools stay with the caller. */
export function detectorPlotSetup({
  state,
  viewports,
  mask,
  showMask = state?.useMask,
  linked,
  localImageClick,
  onInspect,
}: {
  state: State | null;
  viewports?: SharedPlotViews;
  mask: Raster | null;
  showMask?: boolean;
  linked?: Response["linked"];
  localImageClick?: DetectorProps["clickedPoint"];
  onInspect?: DetectorProps["onInspect"];
}) {
  return {
    viewport: viewports
      ? detectorViewport(viewports.detector, plotViewContext(state))
      : undefined,
    zoomMode: "rectangle" as const,
    mask: showMask ? (mask ?? undefined) : undefined,
    maskOpacity: state?.transparentMask ? 0.72 : 1,
    clickedPoint: linked?.imagePoint ?? localImageClick ?? null,
    onInspect,
  };
}

/** Shared pattern presentation and click sampling, with each mode's display data. */
export function patternPlotSetup({
  pattern,
  viewport,
  patternColor = "#ffffff",
  showPattern = true,
  patternName = "",
  curves,
  referenceLines,
  legendCurves = curves,
  showLegend = true,
  linked,
  localPatternClick,
  wavelength,
  onInspect,
}: Pick<
  PatternProps,
  | "pattern"
  | "viewport"
  | "patternColor"
  | "showPattern"
  | "curves"
  | "referenceLines"
> & {
  patternName?: string;
  legendCurves?: Pattern["curves"];
  showLegend?: boolean;
  linked?: Response["linked"];
  localPatternClick?: PatternPosition;
  wavelength?: number;
  onInspect?: (point: PatternHover) => void;
}) {
  return {
    props: {
      pattern,
      viewport,
      patternColor,
      showPattern,
      curves,
      referenceLines,
      overlayLegend: showLegend
        ? [
            ...(showPattern
              ? [
                  {
                    name: (legendCurves ?? []).some(
                      (curve) => curve.name === patternName,
                    )
                      ? `Original · ${patternName}`
                      : patternName,
                    color: patternColor,
                  },
                ]
              : []),
            ...(legendCurves ?? []),
          ]
        : undefined,
      linkedPosition: patternPositionInUnit(
        linked,
        localPatternClick,
        pattern.unit,
        wavelength,
      ),
    },
    inspect: (
      x: number,
      mouseY: number,
      resolution: { x: number; y: number },
    ) => {
      if (!onInspect) return;
      const nearest = pattern.x.reduce(
        (best, value, i) =>
          Math.abs(value - x) < Math.abs(pattern.x[best] - x) ? i : best,
        0,
      );
      onInspect({
        x,
        mouseY,
        unit: pattern.unit,
        y: pattern.y[nearest],
        xResolution: resolution.x,
        yResolution: resolution.y,
      });
    },
  };
}

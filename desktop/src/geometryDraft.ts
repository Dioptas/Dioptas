import { useCallback, useLayoutEffect, useState } from "react";
import type { Calibration } from "./types";

export const pyfaiFields = [
  ["dist", "Distance", "mm", 1000],
  ["poni1", "PONI 1", "m", 1],
  ["poni2", "PONI 2", "m", 1],
  ["rot1", "Rotation 1", "rad", 1],
  ["rot2", "Rotation 2", "rad", 1],
  ["rot3", "Rotation 3", "rad", 1],
  ["pixel1", "Pixel height", "µm", 1e6],
  ["pixel2", "Pixel width", "µm", 1e6],
  ["wavelength", "Wavelength", "Å", 1e10],
  ["polarization_factor", "Polarization", "", 1],
] as const;
export const fit2dFields = [
  ["directDist", "Direct distance", "mm", 1],
  ["centerX", "Center x", "pixels", 1],
  ["centerY", "Center y", "pixels", 1],
  ["tilt", "Tilt", "°", 1],
  ["tiltPlanRotation", "Tilt rotation", "°", 1],
  ["pixelX", "Pixel width", "µm", 1],
  ["pixelY", "Pixel height", "µm", 1],
  ["wavelength", "Wavelength", "Å", 1e10],
  ["polarization_factor", "Polarization", "", 1],
] as const;

export type GeometryConvention = "pyfai" | "fit2d";
type Drafts = Record<GeometryConvention, Record<string, string>>;
const valuesFor = (
  calibration: Calibration | undefined,
  convention: GeometryConvention,
) =>
  Object.fromEntries(
    (convention === "pyfai" ? pyfaiFields : fit2dFields).map(
      ([key, , , factor]) => [
        key,
        String((calibration?.[convention]?.[key] ?? 0) * factor),
      ],
    ),
  );
const readDrafts = (calibration?: Calibration): Drafts => ({
  pyfai: valuesFor(calibration, "pyfai"),
  fit2d: valuesFor(calibration, "fit2d"),
});

/** The session owns a geometry draft; changing visible modes never discards it. */
export function useGeometryDraft(calibration?: Calibration) {
  const [drafts, setDrafts] = useState(() => readDrafts(calibration));
  const modelKey = JSON.stringify([calibration?.pyfai, calibration?.fit2d]);
  useLayoutEffect(() => {
    setDrafts(readDrafts(calibration));
  }, [modelKey]);
  const sync = useCallback(
    (next?: Calibration) => setDrafts(readDrafts(next)),
    [],
  );
  const changed = (convention: GeometryConvention) =>
    (convention === "pyfai" ? pyfaiFields : fit2dFields).some(
      ([key, , , factor]) => {
        const text = drafts[convention][key];
        return (
          text !== undefined &&
          (text.trim() === "" ||
            !Number.isFinite(Number(text)) ||
            Number(text) !== (calibration?.[convention]?.[key] ?? 0) * factor)
        );
      },
    );
  const reset = (convention: GeometryConvention) =>
    setDrafts((values) => ({
      ...values,
      [convention]: valuesFor(calibration, convention),
    }));
  return {
    calibration,
    drafts,
    setDrafts,
    changed,
    dirty: changed("pyfai") || changed("fit2d"),
    sync,
    reset,
  };
}
export type GeometryDraft = ReturnType<typeof useGeometryDraft>;

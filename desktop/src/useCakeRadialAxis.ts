import { useMemo, useRef } from "react";
import type { Cake, Unit } from "./types";
import {
  createCakeRadialAxis,
  nextCakeAxisUnit,
  type CakeAxisUnit,
} from "./cakeRadialAxis";

/** Display state only: no scientific request and no replacement pixel buffer. */
export function useCakeRadialAxis(
  cake: Cake | null,
  unit?: Unit,
  wavelength?: number,
) {
  const last = useRef<CakeAxisUnit>("2th_deg");
  last.current = nextCakeAxisUnit(unit, last.current);
  const displayUnit = last.current;
  return useMemo(
    () =>
      cake ? createCakeRadialAxis(cake, displayUnit, wavelength) : undefined,
    [cake, displayUnit, wavelength],
  );
}

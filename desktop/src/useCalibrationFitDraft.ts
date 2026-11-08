import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Calibration } from "./types";
import { numericDraftError, type NumericLimits } from "./numericDraft";

export const fitParameterLimits = (key: string): NumericLimits =>
  key === "wavelength"
    ? { min: 0.01, max: 10, unit: "Å" }
    : key === "dist"
      ? { min: 1, max: 10000, unit: "mm" }
      : key.startsWith("poni")
        ? { min: -1e5, max: 1e5, unit: "mm" }
        : { min: -2 * Math.PI, max: 2 * Math.PI, unit: "rad" };
export const fitEnergyLimits = {
  min: 12.39841984332 / 10,
  max: 12.39841984332 / 0.01,
  unit: "keV",
};

/** Session-owned starting values are separate from applied geometry. */
export function useCalibrationFitDraft(c?: Calibration) {
  const [parameterSettings, setParameters] = useState<
    Calibration["parameters"]
  >(c?.parameters ?? {});
  const [parameterText, setParameterText] = useState<Record<string, string>>(
    {},
  );
  const [energyText, setEnergyText] = useState<string | null>(null);
  const parameters = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(parameterSettings).map(([key, setting]) => {
          const text = parameterText[key] ?? String(setting.value);
          return [
            key,
            {
              ...setting,
              value: numericDraftError(text, fitParameterLimits(key))
                ? NaN
                : Number(text),
            },
          ];
        }),
      ),
    [parameterSettings, parameterText],
  );
  const [polarization, setPolarization] = useState(
    String(c?.polarization ?? 0.99),
  );

  const base = useRef(c);
  useLayoutEffect(() => {
    if (c) {
      const previous = base.current;
      setParameterText((texts) =>
        Object.fromEntries(
          Object.entries(texts).filter(
            ([key, text]) =>
              numericDraftError(text) ||
              Number(text) !== previous?.parameters[key]?.value,
          ),
        ),
      );
      setParameters((settings) =>
        Object.fromEntries(
          Object.entries(c.parameters).map(([key, setting]) => [
            key,
            {
              ...setting,
              refine:
                settings[key]?.refine !== previous?.parameters[key]?.refine
                  ? (settings[key]?.refine ?? setting.refine)
                  : setting.refine,
            },
          ]),
        ),
      );
      setPolarization((text) =>
        !previous ||
        (!numericDraftError(text) && Number(text) === previous.polarization)
          ? String(c.polarization)
          : text,
      );
      if (
        parameterText.wavelength === undefined ||
        (!numericDraftError(parameterText.wavelength) &&
          Number(parameterText.wavelength) ===
            previous?.parameters.wavelength?.value)
      )
        setEnergyText(null);
      base.current = c;
    }
  }, [JSON.stringify(c?.parameters), c?.polarization]);

  const draft = useMemo(
    () => ({
      parameters,
      polarization: numericDraftError(polarization, { min: -1, max: 1 })
        ? NaN
        : Number(polarization),
    }),
    [parameters, polarization],
  );
  const dirty =
    !!c &&
    (draft.polarization !== c.polarization ||
      Object.entries(parameters).some(
        ([key, parameter]) =>
          parameter.value !== c.parameters[key]?.value ||
          parameter.refine !== c.parameters[key]?.refine,
      ));
  const sync = useCallback((next?: Calibration) => {
    base.current = next;
    setParameters(next?.parameters ?? {});
    setParameterText({});
    setEnergyText(null);
    setPolarization(String(next?.polarization ?? 0.99));
  }, []);
  return {
    draft,
    dirty,
    sync,
    parameters,
    parameterSettings,
    parameterText,
    setParameterText,
    setParameters,
    energyText,
    setEnergyText,
    polarization,
    setPolarization,
  };
}
export type CalibrationFitEditor = ReturnType<typeof useCalibrationFitDraft>;

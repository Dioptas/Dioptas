import { useCallback, useLayoutEffect, useMemo, useState } from "react";
import type { Calibration } from "./types";
import { numericDraftError } from "./numericDraft";

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
            { ...setting, value: numericDraftError(text) ? NaN : Number(text) },
          ];
        }),
      ),
    [parameterSettings, parameterText],
  );
  const [polarization, setPolarization] = useState(
    String(c?.polarization ?? 0.99),
  );

  useLayoutEffect(() => {
    if (c) {
      setParameters(c.parameters);
      setParameterText({});
      setEnergyText(null);
      setPolarization(String(c.polarization));
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

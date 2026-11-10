import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import type { IntegrationRun } from "./integration";
import type { AutoLevels, State, Invoke } from "./types";
import {
  correctionPreviewContext,
  retainsCorrectionPreview,
  type CorrectionPreview,
} from "./correctionPreview";

export function useCorrectionPreview(
  state: State | null,
  visible: boolean,
  run: IntegrationRun,
  bridge: RefObject<Invoke | null>,
) {
  const context = correctionPreviewContext(state, visible);
  const current = useRef(context);
  current.current = context;
  const generation = useRef(0);
  const [selected, setSelected] = useState<{
    context: string;
    map: CorrectionPreview;
  } | null>(null);
  const close = useCallback(() => {
    ++generation.current;
    setSelected(null);
  }, []);
  useEffect(close, [context, close]);
  const map = visible && selected?.context === context ? selected.map : null;
  const load = async (kind: string, settings?: AutoLevels) => {
    const epoch = ++generation.current;
    // A failed or superseded request must never leave a preceding map visible.
    if (!settings) setSelected(null);
    let received = false;
    await run(
      "integration_correction_preview",
      {
        kind,
        ...settings,
        revision: state?.revision,
        configuration: state?.configurationContext,
      },
      settings ? "" : "Loading correction map…",
      (response) => {
        received = true;
        if (epoch === generation.current && current.current === context) {
          setSelected(
            response.ok && response.correctionPreview
              ? { context, map: response.correctionPreview }
              : null,
          );
        }
      },
    );
    if (!received && epoch === generation.current) close();
  };
  return {
    map,
    sampleGeometry: async (point: { x: number; y: number }) => {
      const response = await bridge.current?.("pixel", {
        ...point,
        source: "geometry",
      });
      return current.current === context && response?.ok
        ? response.pixel
        : undefined;
    },
    close,
    toggle: (kind: string) => (map?.kind === kind ? close() : void load(kind)),
    auto: (settings: AutoLevels) =>
      map ? load(map.kind, settings) : Promise.resolve(),
    beforeCommand: (command: string) => {
      if (!retainsCorrectionPreview(command)) close();
    },
  };
}

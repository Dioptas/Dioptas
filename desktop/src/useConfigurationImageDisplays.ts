import { useRef } from "react";
import type {
  ImageDisplayPreferences,
  Palette,
  Response,
  State,
} from "./types";

interface Displays {
  limits: [number, number];
  setLimits: (value: [number, number]) => void;
  logImage: boolean;
  setLogImage: (value: boolean) => void;
  palette: Palette;
  setPalette: (value: Palette) => void;
  detectorPreferences: ImageDisplayPreferences;
  setDetectorPreferences: (value: ImageDisplayPreferences) => void;
  multiDetectorPreferences: ImageDisplayPreferences;
  setMultiDetectorPreferences: (value: ImageDisplayPreferences) => void;
  cakeLimits: [number, number];
  setCakeLimits: (value: [number, number]) => void;
  cakeLog: boolean;
  setCakeLog: (value: boolean) => void;
  cakePalette: Palette;
  setCakePalette: (value: Palette) => void;
  cakePreferences: ImageDisplayPreferences;
  setCakePreferences: (value: ImageDisplayPreferences) => void;
}

/** Retain each detector's contrast and each individual/combined cake independently. */
export function useConfigurationImageDisplays(input: Displays) {
  const latest = useRef(input);
  latest.current = input;
  const {
    limits,
    logImage,
    palette,
    detectorPreferences,
    multiDetectorPreferences,
    cakeLimits,
    cakeLog,
    cakePalette,
    cakePreferences,
  } = input;
  const detectorAutoActive = useRef(true);
  const cakeAutoActive = useRef(true);
  const configurationDisplays = useRef(
    new Map<
      number,
      {
        limits: [number, number];
        log: boolean;
        palette: Palette;
        autoActive: boolean;
        detector: typeof detectorPreferences;
        multi: typeof multiDetectorPreferences;
      }
    >(),
  );
  const configurationCakeDisplays = useRef(
    new Map<
      string,
      {
        limits: [number, number];
        log: boolean;
        palette: Palette;
        autoActive: boolean;
        preferences: typeof cakePreferences;
      }
    >(),
  );
  const currentDisplays = useRef({
    limits,
    logImage,
    palette,
    detectorPreferences,
    multiDetectorPreferences,
    cakeLimits,
    cakeLog,
    cakePalette,
    cakePreferences,
  });
  currentDisplays.current = {
    limits,
    logImage,
    palette,
    detectorPreferences,
    multiDetectorPreferences,
    cakeLimits,
    cakeLog,
    cakePalette,
    cakePreferences,
  };
  const initialDisplayPreferences = useRef({
    detectorPreferences,
    multiDetectorPreferences,
    cakePreferences,
  });

  const beginConfigurationDisplay = (
    result: Response,
    previousState: State | null,
  ) => {
    const nextState = result.state;
    const configurationChanged =
      !!nextState &&
      !!previousState &&
      nextState.configurationIndex !== previousState.configurationIndex;
    const cakeDisplayKey = (s: State) =>
      `${s.configurationIndex}:${!!s.combination?.cakes}`;
    const cakeDisplayChanged =
      !!nextState &&
      !!previousState &&
      cakeDisplayKey(nextState) !== cakeDisplayKey(previousState);
    if (result.configurationReset) {
      configurationDisplays.current.clear();
      configurationCakeDisplays.current.clear();
    } else if (previousState) {
      const d = currentDisplays.current;
      if (configurationChanged)
        configurationDisplays.current.set(previousState.configurationIndex, {
          limits: d.limits,
          log: d.logImage,
          palette: d.palette,
          autoActive: detectorAutoActive.current,
          detector: d.detectorPreferences,
          multi: d.multiDetectorPreferences,
        });
      if (cakeDisplayChanged)
        configurationCakeDisplays.current.set(cakeDisplayKey(previousState), {
          limits: d.cakeLimits,
          log: d.cakeLog,
          palette: d.cakePalette,
          autoActive: cakeAutoActive.current,
          preferences: d.cakePreferences,
        });
    }

    return {
      configurationChanged: configurationChanged || !!result.configurationReset,
      restore: () => {
        const {
          setLimits,
          setLogImage,
          setPalette,
          setDetectorPreferences,
          setMultiDetectorPreferences,
          setCakeLimits,
          setCakeLog,
          setCakePalette,
          setCakePreferences,
        } = latest.current;
        if (nextState && (configurationChanged || result.configurationReset)) {
          const display = configurationDisplays.current.get(
            nextState.configurationIndex,
          );
          if (display) setLimits(display.limits);
          detectorAutoActive.current = display?.autoActive ?? true;
          setLogImage(display?.log ?? false);
          setPalette(display?.palette ?? "grey");
          setDetectorPreferences(
            display?.detector ??
              initialDisplayPreferences.current.detectorPreferences,
          );
          setMultiDetectorPreferences(
            display?.multi ??
              initialDisplayPreferences.current.multiDetectorPreferences,
          );
        }
        if (nextState && (cakeDisplayChanged || result.configurationReset)) {
          const display = configurationCakeDisplays.current.get(
            cakeDisplayKey(nextState),
          );
          if (display) setCakeLimits(display.limits);
          cakeAutoActive.current = display?.autoActive ?? true;
          setCakeLog(display?.log ?? false);
          setCakePalette(display?.palette ?? "grey");
          setCakePreferences(
            display?.preferences ??
              initialDisplayPreferences.current.cakePreferences,
          );
        }
      },
    };
  };
  return {
    detectorAutoActive,
    cakeAutoActive,
    configurationDisplays,
    configurationCakeDisplays,
    beginConfigurationDisplay,
  };
}

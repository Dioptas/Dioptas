import {
  defaultPatternFigureSettings,
  validatePatternFigure,
  type CurveStyle,
  type PatternFigureOptions,
  type PatternFigureSettings,
  type PatternFigureSource,
} from "./patternFigure";

// Only appearance travels between datasets. Identities, labels, visibility,
// order, scales and numerical ranges remain with the current figure.
const appearanceKeys = [
  "width",
  "height",
  "fontSize",
  "font",
  "theme",
  "legend",
  "phaseLegend",
  "phaseTickWeight",
  "phaseRowSpacing",
  "phaseTickHeight",
  "phaseGuides",
  "phases",
  "grid",
  "box",
  "yTicks",
  "tickDirection",
] as const;
type Appearance = Pick<PatternFigureOptions, (typeof appearanceKeys)[number]>;
type CurveAppearance = Pick<CurveStyle, "color" | "width" | "style">;
export type PatternFigureStyle = {
  id: string;
  name: string;
  appearance: Appearance;
  curves: CurveAppearance[];
  phaseColors: string[];
};
export const patternFigureStylesKey = "dioptas-pattern-figure-styles-v1";
const appearanceOf = (options: Appearance): Appearance =>
  Object.fromEntries(
    appearanceKeys.map((key) => [key, options[key]]),
  ) as Appearance;

export function capturePatternFigureStyle(
  name: string,
  settings: PatternFigureSettings,
  id: string = crypto.randomUUID(),
): PatternFigureStyle {
  const style = {
    id,
    name: name.trim(),
    appearance: appearanceOf(settings.options),
    curves: settings.options.curves.map(({ color, width, style }) => ({
      color,
      width,
      style,
    })),
    phaseColors: settings.options.phaseStyles.map(({ color }) => color),
  };
  validateStyle(style);
  return style;
}

export function applyPatternFigureStyle(
  source: PatternFigureSource,
  settings: PatternFigureSettings,
  style: PatternFigureStyle,
): PatternFigureSettings {
  validateStyle(style);
  const options: PatternFigureOptions = {
    ...settings.options,
    ...appearanceOf(style.appearance),
    curves: settings.options.curves.map((curve, i) => {
      const {
        color,
        width,
        style: lineStyle,
      } = style.curves[i % style.curves.length];
      return { ...curve, color, width, style: lineStyle };
    }),
    phaseStyles: settings.options.phaseStyles.map((phase, i) => ({
      ...phase,
      color: style.phaseColors.length
        ? style.phaseColors[i % style.phaseColors.length]
        : phase.color,
    })),
  };
  validatePatternFigure(source, options);
  return { ...settings, options };
}

function validateStyle(style: PatternFigureStyle) {
  if (
    typeof style?.id !== "string" ||
    !style.id ||
    style.id.length > 100 ||
    typeof style.name !== "string" ||
    !style.name.trim() ||
    style.name.length > 80 ||
    !style.appearance ||
    !appearanceKeys.every((key) => Object.hasOwn(style.appearance, key)) ||
    !Array.isArray(style.curves) ||
    !style.curves.length ||
    style.curves.length > 256 ||
    !Array.isArray(style.phaseColors) ||
    style.phaseColors.length > 256
  )
    throw Error(
      "Use a style name of 1–80 characters and valid appearance settings.",
    );
  // Validate every palette slot, even when the current dataset has fewer curves.
  const source: PatternFigureSource = {
    unit: "2th_deg",
    scale: "linear",
    pattern: { x: [0, 1], y: [1, 2] },
    view: { xMin: 0, xMax: 1, yMin: 0, yMax: 2 },
    curves: style.curves.map((_, i) => ({
      id: String(i),
      name: "Curve",
      color: "#202124",
      x: [0, 1],
      y: [1, 2],
    })),
    phases: style.phaseColors.map((color, i) => ({
      phaseIndex: i,
      name: "Phase",
      color,
      x: 0.5,
      intensity: 1,
      hkl: [1, 1, 1],
    })),
  };
  const options = defaultPatternFigureSettings(source).options;
  Object.assign(options, appearanceOf(style.appearance));
  options.curves = options.curves.map((curve, i) => ({
    ...curve,
    color: style.curves[i]?.color,
    width: style.curves[i]?.width,
    style: style.curves[i]?.style,
  }));
  options.phaseStyles = options.phaseStyles.map((phase, i) => ({
    ...phase,
    color: style.phaseColors[i],
  }));
  validatePatternFigure(source, options);
}

export function loadPatternFigureStyles(): PatternFigureStyle[] {
  try {
    const saved = JSON.parse(
      localStorage.getItem(patternFigureStylesKey) ?? "null",
    );
    if (saved?.version !== 1 || !Array.isArray(saved.styles)) return [];
    const styles: PatternFigureStyle[] = [];
    for (const candidate of saved.styles.slice(0, 256)) {
      try {
        validateStyle(candidate);
        if (
          styles.some(
            (style) =>
              style.id === candidate.id ||
              style.name.toLowerCase() === candidate.name.trim().toLowerCase(),
          )
        )
          continue;
        // Drop unrecognized fields; a stored template never carries source data.
        styles.push({
          id: candidate.id,
          name: candidate.name.trim(),
          appearance: appearanceOf(candidate.appearance),
          curves: candidate.curves.map(
            ({ color, width, style }: CurveAppearance) => ({
              color,
              width,
              style,
            }),
          ),
          phaseColors: [...candidate.phaseColors],
        });
      } catch {
        /* Ignore a corrupt entry without losing the other styles. */
      }
    }
    return styles;
  } catch {
    return [];
  }
}

export function storePatternFigureStyles(styles: PatternFigureStyle[]) {
  if (styles.length > 256)
    throw Error("The style library can hold up to 256 styles.");
  const ids = new Set(),
    names = new Set();
  for (const style of styles) {
    validateStyle(style);
    const name = style.name.trim().toLowerCase();
    if (ids.has(style.id) || names.has(name))
      throw Error(
        "A style with this name already exists. Select it and use Update.",
      );
    ids.add(style.id);
    names.add(name);
  }
  try {
    localStorage.setItem(
      patternFigureStylesKey,
      JSON.stringify({ version: 1, styles }),
    );
  } catch {
    throw Error(
      "The style could not be saved on this computer. Check that local storage is available.",
    );
  }
}

export type PlotTick = { value: number; label: string };

function label(value: number, step: number) {
  if (value === 0) return "0";
  if (Math.abs(value) >= 1e5 || Math.abs(value) < 1e-3) {
    const precision = Math.max(
      0,
      Math.min(14, Math.ceil(Math.log10(Math.abs(value) / step)) + 1),
    );
    return value
      .toExponential(precision)
      .replace(/\.?0+e/, "e")
      .replace("e+", "e");
  }
  const digits = Math.max(0, Math.min(12, -Math.floor(Math.log10(step)) + 1));
  return Number(value.toFixed(digits)).toString();
}

/** Ticks are multiples of a readable step, independent of the viewport ends. */
export function linearTicks(
  min: number,
  max: number,
  intervals = 5,
): PlotTick[] {
  const span = max - min;
  if (!Number.isFinite(span) || span <= 0) return [];
  const raw = span / Math.max(1, intervals);
  const power = 10 ** Math.floor(Math.log10(raw));
  if (!Number.isFinite(power) || power === 0) return [];
  const normalized = raw / power;
  const step =
    [1, 2, 2.5, 5, 10].reduce((best, n) =>
      Math.abs(Math.log(n / normalized)) < Math.abs(Math.log(best / normalized))
        ? n
        : best,
    ) * power;
  const first = Math.ceil(min / step - 1e-10);
  const last = Math.floor(max / step + 1e-10);
  return Array.from(
    { length: Math.max(0, Math.min(100, last - first + 1)) },
    (_, i) => {
      const value = Number(((first + i) * step).toPrecision(14));
      return { value, label: label(value, step) };
    },
  );
}

/** Keep tick positions in data units; factor shared digits out of their labels.
 * A labelled value represents offset + scale * label, as on scientific axes. */
export function linearAxisTicks(min: number, max: number, intervals = 5) {
  const ticks = linearTicks(min, max, intervals);
  const span = max - min;
  if (!ticks.length) return { ticks, offset: 0, scale: 1, annotation: null };
  const step = ticks.length > 1 ? ticks[1].value - ticks[0].value : span;
  let offset = 0;
  const offsetUnit = 10 ** Math.ceil(Math.log10(span));
  if (
    Math.abs((min + max) / 2) >= span * 100 &&
    ticks.some((tick) => tick.label.length > 6)
  ) {
    offset = Number(
      (Math.floor(min / offsetUnit + 1e-10) * offsetUnit).toPrecision(14),
    );
  }
  const residuals = ticks.map((tick) => {
    const value = tick.value - offset;
    return Math.abs(value) < step * 1e-8 ? 0 : value;
  });
  const magnitude = Math.max(...residuals.map(Math.abs));
  const exponent = magnitude ? Math.floor(Math.log10(magnitude)) : 0;
  const scale = exponent <= -3 || exponent >= 4 ? 10 ** exponent : 1;
  const superscripts = "⁰¹²³⁴⁵⁶⁷⁸⁹";
  const scaleLabel =
    scale === 1
      ? ""
      : `×10${String(exponent)
          .split("")
          .map((digit) => (digit === "-" ? "⁻" : superscripts[Number(digit)]))
          .join("")}`;
  const offsetLabel =
    offset === 0
      ? ""
      : `${offset > 0 ? "+" : "−"}${label(Math.abs(offset), offsetUnit)}`;
  return {
    ticks: ticks.map((tick, i) => ({
      value: tick.value,
      label: label(residuals[i] / scale, step / scale),
    })),
    offset,
    scale,
    annotation: [scaleLabel, offsetLabel].filter(Boolean).join("  ") || null,
  };
}

/** Log viewport values are exponents; labels still show actual intensities. */
export function logTicks(min: number, max: number, intervals = 5): PlotTick[] {
  const span = max - min;
  if (!Number.isFinite(span) || span <= 0) return [];
  if (span < 0.5) {
    return linearTicks(10 ** min, 10 ** max, intervals).map((tick) => ({
      ...tick,
      value: Math.log10(tick.value),
    }));
  }
  const stride = Math.max(1, Math.round(span / Math.max(1, intervals)));
  const first = Math.ceil(min / stride) * stride;
  const exponents =
    span >= 3
      ? Array.from(
          {
            length: Math.max(
              0,
              Math.min(100, Math.floor((max - first) / stride) + 1),
            ),
          },
          (_, i) => first + i * stride,
        )
      : Array.from({ length: Math.ceil(max) - Math.floor(min) + 1 }, (_, i) =>
          [1, 2, 5].map((n) => Math.floor(min) + i + Math.log10(n)),
        ).flat();
  let previous = -Infinity;
  return exponents
    .filter((value) => {
      if (
        value < min ||
        value > max ||
        value - previous < span / (intervals * 1.5)
      )
        return false;
      previous = value;
      return Number.isFinite(10 ** value) && 10 ** value > 0;
    })
    .map((value) => ({ value, label: label(10 ** value, 10 ** value) }));
}

// Pure helpers for check_native_desktop.mjs: per-step wall times, the summary
// printed after every gate run, timings.json and the GitHub job summary table.

// DIOPTAS_GATE_COVERAGE is an explicit opt-in; anything but 0/1 is a typo.
export function coverageRequested(value) {
  if (value === undefined || value === "" || value === "0") return false;
  if (value === "1") return true;
  throw Error(`DIOPTAS_GATE_COVERAGE must be 0 or 1, not ${value}`);
}

export const seconds = (s) => s.toFixed(1);

export function timingReport({
  steps,
  status,
  flags,
  coverage = false,
  totalSeconds,
  platform = process.platform,
  arch = process.arch,
}) {
  return {
    status,
    platform,
    arch,
    node: process.version,
    flags: [...flags],
    coverage,
    totalSeconds: Number(totalSeconds.toFixed(3)),
    stepSeconds: Number(
      steps.reduce((sum, step) => sum + step.seconds, 0).toFixed(3),
    ),
    steps: steps.map((step) => ({
      ...step,
      seconds: Number(step.seconds.toFixed(3)),
    })),
  };
}

// Slowest first; equal durations keep their execution order.
export const slowestFirst = (steps) =>
  steps
    .map((step, order) => ({ step, order }))
    .sort((a, b) => b.step.seconds - a.step.seconds || a.order - b.order)
    .map(({ step }) => step);

const share = (step, total) =>
  total > 0 ? `${((100 * step.seconds) / total).toFixed(1)}%` : "-";

const heading = (report) =>
  `${report.flags.join(" ")}; ${report.platform} ${report.arch}; ` +
  `${report.status}; total ${seconds(report.totalSeconds)} s` +
  (report.coverage ? "; coverage" : "");

export function textSummary(report) {
  const rows = slowestFirst(report.steps).map((step) => [
    seconds(step.seconds),
    share(step, report.totalSeconds),
    step.status,
    step.name,
  ]);
  const widths = [0, 1, 2].map((column) =>
    Math.max(...rows.map((row) => row[column].length), 0),
  );
  return [
    `Native gate timings (${heading(report)})`,
    ...rows.map(
      ([time, part, status, name]) =>
        `  ${time.padStart(widths[0])} s  ${part.padStart(widths[1])}  ` +
        `${status.padEnd(widths[2])}  ${name}`,
    ),
  ].join("\n");
}

const cell = (text) => String(text).replaceAll("|", "\\|");
const code = (text) => `<code>${cell(text).replaceAll("<", "&lt;")}</code>`;

export function markdownSummary(report) {
  return [
    `### Native gate timings: ${cell(heading(report))}`,
    "",
    "| Step | Seconds | Share | Status | Command |",
    "| --- | ---: | ---: | --- | --- |",
    ...slowestFirst(report.steps).map(
      (step) =>
        `| ${cell(step.name)} | ${seconds(step.seconds)} | ` +
        `${share(step, report.totalSeconds)} | ${step.status} | ` +
        `${code(step.command)} |`,
    ),
    "",
    "",
  ].join("\n");
}

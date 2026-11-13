// Pure helpers for check_native_desktop.mjs: per-step wall times, the summary
// printed after every gate run, timings.json and the GitHub job summary table.

// Gate switches are explicit; anything but 0/1 is a typo.
export function gateSwitch(name, value, fallback) {
  if (value === undefined || value === "") return fallback;
  if (value === "0") return false;
  if (value === "1") return true;
  throw Error(`${name} must be 0 or 1, not ${value}`);
}

// DIOPTAS_GATE_COVERAGE is an opt-in.
export const coverageRequested = (value) =>
  gateSwitch("DIOPTAS_GATE_COVERAGE", value, false);

// DIOPTAS_GATE_UI_JOBS: how many UI checks run at once. Three by default,
// which is what a hosted CI runner has cores for; never more than the machine.
export function uiJobs(value, cores) {
  if (value === undefined || value === "")
    return Math.max(1, Math.min(3, cores));
  if (!/^[1-9]\d*$/.test(value))
    throw Error(
      `DIOPTAS_GATE_UI_JOBS must be a positive integer, not ${value}`,
    );
  return Number(value);
}

// Runs every task, at most `jobs` at a time, starting them in list order.
// Tasks that share a lock never overlap. The first failure stops new starts
// and rejects once the tasks already running have settled.
export async function runPool(tasks, jobs, start) {
  const pending = [...tasks];
  const held = new Set();
  let running = 0;
  let failure;
  await new Promise((resolve) => {
    const next = () => {
      while (!failure && running < jobs) {
        const index = pending.findIndex((task) =>
          (task.locks ?? []).every((lock) => !held.has(lock)),
        );
        if (index < 0) break;
        const [task] = pending.splice(index, 1);
        for (const lock of task.locks ?? []) held.add(lock);
        running++;
        Promise.resolve()
          .then(() => start(task))
          .catch((error) => (failure ??= error))
          .finally(() => {
            for (const lock of task.locks ?? []) held.delete(lock);
            running--;
            next();
          });
      }
      if (running === 0) resolve();
    };
    next();
  });
  if (failure) throw failure;
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

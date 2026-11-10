import type { IntegrationRun } from "./integration";
import { reportFailure } from "./errorReporting";
import type { PlotFigureExport } from "./plotFigureExport";

/** The host chooses a path first. Data saves and cancellation need no rendering. */
export async function saveIntegrationPattern(
  run: IntegrationRun,
  capture: PlotFigureExport["capture"],
) {
  let path: string | undefined;
  await run(
    "integration_save_pattern",
    { subtract_background: true, figure_export: true },
    "Saving pattern…",
    (result) => {
      path = result.figureExportPath;
    },
  );
  if (!path) return;
  try {
    await run(
      "integration_save_pattern",
      { path, ...capture() },
      "Saving pattern figure…",
    );
  } catch (error) {
    reportFailure("integration_save_pattern", error);
  }
}

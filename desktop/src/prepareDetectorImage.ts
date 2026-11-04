import type { AutoLevels, Invoke, Raster, Response } from "./types";

/** Resolve source-precision Auto limits before publishing new detector pixels.
 * The caller retains the command queue until this finishes, so another file
 * cannot become the scientific source halfway through the levels request.
 */
export async function prepareDetectorImage(
  invoke: Invoke,
  result: Response,
  previous: Raster | null,
  auto: AutoLevels,
  raw = false,
): Promise<Response> {
  const key = raw ? "rawImage" : "image";
  const raster = result[key];
  if (
    !result.ok ||
    !raster ||
    (previous?.data === raster.data &&
      previous.width === raster.width &&
      previous.height === raster.height)
  )
    return result;
  const levels = await invoke("image_levels", {
    ...auto,
    source: raw ? "raw_detector" : "detector",
  });
  if (!levels.ok)
    throw new Error(
      levels.error || "Could not calculate image intensity limits.",
    );
  return {
    ...result,
    [key]: {
      ...raster,
      limits: levels.levels ?? raster.limits,
      autoLevels: auto,
    },
  };
}

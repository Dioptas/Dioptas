export type ProcessingProgress = {
  running: boolean;
  current: number;
  total: number;
  label?: string;
  fps?: number;
  elapsedSeconds?: number;
};

export function processingProgressText(
  progress: ProcessingProgress,
  fallback = "Processing",
) {
  const rate =
    progress.current > 0 &&
    progress.fps !== undefined &&
    Number.isFinite(progress.fps) &&
    progress.fps > 0
      ? ` · ${progress.fps.toFixed(1)} images/s`
      : "";
  return `${progress.label ?? fallback} ${progress.current} / ${progress.total}${rate}`;
}

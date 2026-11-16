export const PATTERN_UPDATE_INTERVAL_MS = 1000 / 30;
export const MAP_UPDATE_INTERVAL_MS = 500;

/** Keep the newest pointer position, with an exact final update on release. */
export function createRateLimitedInput<T>(
  intervalMs: number,
  apply: (value: T) => void,
  now = () => performance.now(),
) {
  let pending: { value: T } | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let lastUpdate = -Infinity;
  const cancel = () => {
    clearTimeout(timer);
    timer = undefined;
    pending = null;
  };
  const deliver = () => {
    timer = undefined;
    const next = pending;
    if (!next) return;
    pending = null;
    lastUpdate = now();
    apply(next.value);
  };
  return {
    push(value: T) {
      pending = { value };
      if (timer === undefined)
        timer = setTimeout(
          deliver,
          Math.max(0, Math.ceil(intervalMs - (now() - lastUpdate))),
        );
    },
    flush(value: T) {
      cancel();
      lastUpdate = now();
      apply(value);
    },
    cancel,
  };
}

import { PATTERN_UPDATE_INTERVAL_MS } from "./updateRateLimit";
import { useEffect, useRef, useState } from "react";
import type { IntegrationState } from "./integration";

export type BackgroundRange = [number, number] | null;
const sameRange = (a: BackgroundRange, b: BackgroundRange) =>
  a === b || (!!a && !!b && a[0] === b[0] && a[1] === b[1]);
export type BackgroundSettings = Omit<
  IntegrationState["patternBackground"],
  "overlay"
>;
const same = (a: BackgroundSettings, b: BackgroundSettings) =>
  a.enabled === b.enabled &&
  a.smoothing === b.smoothing &&
  a.iterations === b.iterations &&
  a.order === b.order &&
  sameRange(a.range, b.range);
export const DEFAULT_BACKGROUND: BackgroundSettings = {
  enabled: false,
  smoothing: 0.1,
  iterations: 50,
  order: 50,
  range: null,
};

/** Keep the newest settings visible while fitting one background at a time. */
export function useLiveBackground(
  context: string,
  value: BackgroundSettings,
  commit: (
    settings: BackgroundSettings,
    isCurrent: () => boolean,
  ) => Promise<void>,
) {
  const latest = useRef({ context, value, commit });
  latest.current = { context, value, commit };
  const [preview, setPreview] = useState<{
    context: string;
    settings: BackgroundSettings;
  } | null>(null);
  const desired = useRef({ context, settings: value });
  const queue = useRef<{
    context: string;
    pending: { settings: BackgroundSettings } | null;
    running: boolean;
    lastStarted: number;
    timer?: ReturnType<typeof setTimeout>;
    sent?: { settings: BackgroundSettings };
  }>({ context, pending: null, running: false, lastStarted: -Infinity });
  const beforeDrag = useRef<BackgroundRange>(value.range);
  const mounted = useRef(true);

  function currentQueue() {
    if (queue.current.context !== context) {
      clearTimeout(queue.current.timer);
      queue.current = {
        context,
        pending: null,
        running: false,
        lastStarted: -Infinity,
      };
    }
    return queue.current;
  }
  function schedule(q: ReturnType<typeof currentQueue>) {
    q.timer = setTimeout(
      () => void pump(q),
      Math.max(
        0,
        Math.ceil(
          PATTERN_UPDATE_INTERVAL_MS - (performance.now() - q.lastStarted),
        ),
      ),
    );
  }
  async function pump(q: ReturnType<typeof currentQueue>) {
    q.timer = undefined;
    if (q.running || !q.pending || queue.current !== q || !mounted.current)
      return;
    const next = q.pending;
    q.pending = null;
    q.sent = next;
    q.running = true;
    q.lastStarted = performance.now();
    try {
      await latest.current.commit(
        next.settings,
        () => mounted.current && latest.current.context === q.context,
      );
    } finally {
      q.running = false;
      if (
        queue.current !== q ||
        latest.current.context !== q.context ||
        !mounted.current
      )
        return;
      if (q.pending) schedule(q);
      else {
        desired.current = {
          context: q.context,
          settings: latest.current.value,
        };
        setPreview(null);
      }
    }
  }
  function change(patch: Partial<BackgroundSettings>) {
    const q = currentQueue();
    const base =
      desired.current.context === context && (q.running || q.pending)
        ? desired.current.settings
        : latest.current.value;
    const settings = { ...base, ...patch };
    const previous = q.pending ?? q.sent;
    if (
      previous &&
      same(previous.settings, settings) &&
      (q.running || q.pending)
    )
      return;
    if (!q.running && !q.pending && same(latest.current.value, settings))
      return;
    desired.current = { context, settings };
    q.pending = { settings };
    setPreview({ context, settings });
    if (!q.running && q.timer === undefined) schedule(q);
  }
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimeout(queue.current.timer);
    };
  }, []);
  useEffect(() => {
    currentQueue();
    setPreview(null);
  }, [context]);
  return {
    settings: preview?.context === context ? preview.settings : value,
    updating: preview?.context === context,
    change,
    begin: () => {
      beforeDrag.current =
        preview?.context === context ? preview.settings.range : value.range;
    },
    cancel: () => change({ range: beforeDrag.current }),
  };
}

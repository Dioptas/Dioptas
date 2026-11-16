import { MAP_UPDATE_INTERVAL_MS } from "./updateRateLimit";
import { useEffect, useRef, useState } from "react";
import type { MapData, MapRun } from "./mapDomain";

type Region = { name: string; min: number; max: number };
const same = (a: Region | null, b: Region) =>
  a?.name === b.name && a.min === b.min && a.max === b.max;

/** One map reduction in flight; replace queued pointer positions with the latest. */
export function useLiveMapRegion(
  map: MapData | null,
  run: MapRun,
  context: string,
) {
  const latest = useRef({ map, run, context });
  latest.current = { map, run, context };
  const [draft, setDraft] = useState<Region | null>(null);
  const queue = useRef({
    context,
    pending: null as Region | null,
    sent: null as Region | null,
    running: false,
    timer: undefined as ReturnType<typeof setTimeout> | undefined,
    lastStarted: -Infinity,
  });
  const before = useRef<Region[] | null>(null);
  const mounted = useRef(true);

  function currentQueue() {
    if (queue.current.context !== context) {
      clearTimeout(queue.current.timer);
      queue.current = {
        context,
        pending: null,
        sent: null,
        running: false,
        timer: undefined,
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
        Math.ceil(MAP_UPDATE_INTERVAL_MS - (performance.now() - q.lastStarted)),
      ),
    );
  }
  async function pump(q: ReturnType<typeof currentQueue>) {
    q.timer = undefined;
    if (
      !mounted.current ||
      q.running ||
      !q.pending ||
      queue.current !== q ||
      latest.current.context !== q.context
    )
      return;
    const next = q.pending;
    q.pending = null;
    q.sent = next;
    q.running = true;
    q.lastStarted = performance.now();
    try {
      await latest.current.run(
        "map_roi",
        {
          name: next.name,
          minimum: next.min,
          maximum: next.max,
        },
        "",
      );
    } finally {
      q.running = false;
      if (
        mounted.current &&
        queue.current === q &&
        latest.current.context === q.context
      ) {
        if (q.pending) schedule(q);
        else setDraft(null);
      }
    }
  }

  function change(next: Region, flush = false) {
    const q = currentQueue();
    setDraft(next);
    if (!same(q.pending ?? (q.running ? q.sent : null), next)) {
      const stored = latest.current.map?.rois.find((r) => r.name === next.name);
      if (q.running || !same(stored ?? null, next)) q.pending = next;
      else {
        q.pending = null;
        setDraft(null);
      }
    }
    if (flush && q.timer !== undefined) {
      clearTimeout(q.timer);
      q.timer = undefined;
    }
    if (!q.running && q.pending && q.timer === undefined) schedule(q);
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimeout(queue.current.timer);
      queue.current.pending = null;
    };
  }, []);

  useEffect(() => {
    currentQueue();
    setDraft(null);
  }, [context]);
  return {
    draft,
    change,
    begin: () => {
      before.current =
        latest.current.map?.rois.map((r) =>
          draft?.name === r.name
            ? draft
            : {
                name: r.name,
                min: r.min,
                max: r.max,
              },
        ) ?? null;
    },
    cancel: () => {
      const name = queue.current.pending?.name ?? queue.current.sent?.name;
      const original = before.current?.find((r) => r.name === name);
      if (original) change(original, true);
    },
  };
}

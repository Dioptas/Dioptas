import { useEffect, useRef, useState } from "react";
import type { MapData, MapRun } from "./mapDomain";

type Region = { name: string; min: number; max: number };
const same = (a: Region | null, b: Region) =>
  a?.name === b.name && a.min === b.min && a.max === b.max;

/** One map reduction in flight; replace queued pointer positions with the latest. */
export function useLiveMapRegion(map: MapData | null, run: MapRun) {
  const latest = useRef({ map, run });
  latest.current = { map, run };
  const [draft, setDraft] = useState<Region | null>(null);
  const queue = useRef({
    pending: null as Region | null,
    sent: null as Region | null,
    running: false,
    frame: 0,
  });
  const before = useRef<Region[] | null>(null);
  const mounted = useRef(true);

  async function pump() {
    const q = queue.current;
    q.frame = 0;
    if (!mounted.current || q.running || !q.pending) return;
    const next = q.pending;
    q.pending = null;
    q.sent = next;
    q.running = true;
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
      if (mounted.current) {
        if (q.pending) q.frame = requestAnimationFrame(() => void pump());
        else setDraft(null);
      }
    }
  }

  function change(next: Region, flush = false) {
    const q = queue.current;
    setDraft(next);
    if (!same(q.pending ?? (q.running ? q.sent : null), next)) {
      const stored = latest.current.map?.rois.find((r) => r.name === next.name);
      if (q.running || !same(stored ?? null, next)) q.pending = next;
      else {
        q.pending = null;
        setDraft(null);
      }
    }
    if (flush && q.frame) {
      cancelAnimationFrame(q.frame);
      q.frame = 0;
    }
    if (!q.running && q.pending && !q.frame) {
      if (flush) void pump();
      else q.frame = requestAnimationFrame(() => void pump());
    }
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      cancelAnimationFrame(queue.current.frame);
      queue.current.pending = null;
    };
  }, []);

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

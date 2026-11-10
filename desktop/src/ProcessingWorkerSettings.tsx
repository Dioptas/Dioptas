import { useEffect, useRef } from "react";
import { Cpu } from "lucide-react";
import { Button, Select } from "./ui";
import type { State } from "./types";
import type { IntegrationRun } from "./integration";

const key = "dioptas-processing-workers";
export function useProcessingWorkerPreference(
  state: State | null,
  ready: boolean,
  run: IntegrationRun,
) {
  const workers = state?.processingWorkers;
  const restored = useRef(false);
  useEffect(() => {
    if (!workers || !ready || restored.current) return;
    restored.current = true;
    try {
      const saved = localStorage.getItem(key);
      if (saved === null) return;
      const value: unknown = JSON.parse(saved);
      const requested =
        typeof value === "number" &&
        Number.isInteger(value) &&
        value > 0 &&
        value <= workers.available
          ? value
          : null;
      if (requested !== workers.requested)
        void run(
          "processing_workers",
          { workers: requested },
          "Restoring processing workers…",
        );
    } catch {}
  }, [workers?.requested, workers?.available, ready, run]);
}

export function ProcessingWorkerSettings({
  state,
  ready,
  run,
}: {
  state: State | null;
  ready: boolean;
  run: IntegrationRun;
}) {
  const workers = state?.processingWorkers;
  if (!workers) return null;
  const choose = (requested: number | null) =>
    void run(
      "processing_workers",
      { workers: requested },
      "Updating processing workers…",
      () => {
        try {
          localStorage.setItem(key, JSON.stringify(requested));
        } catch {}
      },
    );
  return (
    <section className="settings-card">
      <div className="settings-card-heading">
        <Cpu size={18} />
        <h3>Processing workers</h3>
      </div>
      <p>
        Share CPU workers across integration, background processing and image
        preparation.
      </p>
      <label className="field-label">
        Workers
        <Select
          aria-label="Processing workers"
          value={workers.requested ?? "auto"}
          disabled={!ready}
          onChange={(event) =>
            choose(
              event.target.value === "auto" ? null : Number(event.target.value),
            )
          }
        >
          <option value="auto">
            Automatic — default ({workers.automatic})
          </option>
          {Array.from({ length: workers.available }, (_, i) => i + 1).map(
            (n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ),
          )}
        </Select>
      </label>
      <Button
        disabled={!ready || workers.requested === null}
        onClick={() => choose(null)}
      >
        Use default
      </Button>
      <p role="status">
        Using {workers.effective} of {workers.available} available CPU cores.
        Frame count and memory limits may reduce workers for an operation.
      </p>
      <p>
        Your choice is saved on this computer and applies to the next operation.
      </p>
    </section>
  );
}

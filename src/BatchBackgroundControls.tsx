import { useEffect, useState } from "react";
import { Button } from "./ui";
import { ScientificNumberInput } from "./ScientificNumberInput";
import type { BatchData, BatchRun } from "./batchDomain";
import { unitLabel, type Unit } from "./types";
import "./batch_background.css";

type Parameters = { smoothing: number; iterations: number; order: number };
export interface BatchBackgroundState {
  parametersUnit?: Unit;
  patternSettings?: boolean;
  parameters: Parameters;
  extracted: Parameters | null;
  range: [number, number] | null;
  unit: Unit;
  available: boolean;
  subtract: boolean;
  cut: boolean;
  stale: boolean;
}
export function BatchBackgroundControls({
  batch,
  ready,
  run,
}: {
  batch: BatchData | null;
  ready: boolean;
  run: BatchRun;
}) {
  const state = batch?.backgroundState;
  const [smoothing, setSmoothing] = useState("0.1"),
    [iterations, setIterations] = useState("150"),
    [order, setOrder] = useState("50");
  useEffect(() => {
    setSmoothing(String(state?.parameters.smoothing ?? 0.1));
    setIterations(String(state?.parameters.iterations ?? 150));
    setOrder(String(state?.parameters.order ?? 50));
  }, [
    state?.parameters.smoothing,
    state?.parameters.iterations,
    state?.parameters.order,
  ]);
  const valid =
    smoothing.trim() !== "" &&
    Number(smoothing) >= 1e-6 &&
    Number(smoothing) <= 1e7 &&
    Number.isInteger(Number(iterations)) &&
    Number(iterations) >= 1 &&
    Number(iterations) <= 99999 &&
    Number.isInteger(Number(order)) &&
    Number(order) >= 1 &&
    Number(order) <= 1000;
  const parameters = {
    smoothing: Number(smoothing),
    iterations: Number(iterations),
    order: Number(order),
  };
  const changed =
    !state ||
    Object.entries(parameters).some(
      ([key, value]) => value !== state.parameters[key as keyof Parameters],
    );
  return (
    <fieldset className="batch-background-settings">
      <legend>Batch background</legend>
      <p>
        Changes to the pattern background update this batch automatically. You
        can also extract a separate background below.
      </p>
      <label>
        Smooth width{" "}
        {unitLabel(state?.parametersUnit ?? batch?.sourceUnit ?? "2th_deg")}
        <ScientificNumberInput
          aria-label="Batch background smooth width"
          value={smoothing}
          onValueChange={setSmoothing}
          disabled={!ready || !batch}
        />
      </label>
      <label>
        Iterations
        <ScientificNumberInput
          aria-label="Batch background iterations"
          value={iterations}
          onValueChange={setIterations}
          disabled={!ready || !batch}
        />
      </label>
      <label>
        Polynomial order
        <ScientificNumberInput
          aria-label="Batch background polynomial order"
          value={order}
          onValueChange={setOrder}
          disabled={!ready || !batch}
        />
      </label>
      {!valid && (
        <p className="ui-field-error">
          Enter a positive width, 1–99999 iterations and an integer order from 1
          to 1000.
        </p>
      )}
      <div className="batch-background-actions">
        <Button
          disabled={!ready || !batch || !valid || !changed}
          onClick={() =>
            run(
              "batch_background_settings",
              { parameters },
              "Updating batch background settings…",
            )
          }
        >
          Apply background settings
        </Button>
        <Button
          disabled={!ready || !batch || !valid}
          onClick={() =>
            run(
              "batch_background_extract",
              { parameters },
              "Extracting batch background…",
            )
          }
        >
          Extract background
        </Button>
      </div>
      <p role="status">
        {state?.stale
          ? "Settings changed. Extract again to update the background."
          : state?.available
            ? "Background available for every frame."
            : "No batch background extracted."}
      </p>
      {state?.patternSettings && (
        <p>The background follows the pattern settings and fitted range.</p>
      )}
      <BatchBackgroundDisplay batch={batch} ready={ready} run={run} />
      <p>
        The batch follows changes to the pattern background automatically.
        Original intensities remain available. Counting std does not include
        uncertainty in the fitted background.
      </p>
    </fieldset>
  );
}
export function BatchBackgroundDisplay({
  batch,
  ready,
  run,
}: {
  batch: BatchData | null;
  ready: boolean;
  run: BatchRun;
}) {
  const state = batch?.backgroundState;
  return (
    <div
      className="batch-background-display"
      role="group"
      aria-label="Batch background display"
    >
      <Button
        aria-pressed={!state?.subtract}
        disabled={!ready || !batch}
        onClick={() =>
          run(
            "batch_background_display",
            { subtract: false },
            "Showing original batch intensities…",
          )
        }
      >
        Original
      </Button>
      <Button
        aria-label="Background subtracted"
        title="Show background-subtracted batch overview"
        aria-pressed={state?.subtract ?? false}
        disabled={!ready || !state?.available}
        onClick={() =>
          run(
            "batch_background_display",
            { subtract: true },
            "Subtracting batch background…",
          )
        }
      >
        Subtract bg
      </Button>
    </div>
  );
}

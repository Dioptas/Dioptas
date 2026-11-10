import "./batch_waterfall.css";
import { useEffect, useState } from "react";
import { ChartNoAxesCombined } from "lucide-react";
import { PlotToggle } from "./IntegrationPlotControls";
import type { BatchData, BatchRun } from "./batchDomain";
import type { BatchWaterfallRegion } from "./batchWaterfall";

export function useBatchWaterfall(batch: BatchData | null, run: BatchRun) {
  const [active, setActive] = useState(false);
  const [region, setRegion] = useState<BatchWaterfallRegion | null>(null);
  const [step, setStep] = useState(1);
  useEffect(() => {
    setRegion(null);
    setActive(false);
    setStep(1);
  }, [batch?.waterfallKey, batch?.id]);
  const create = (selection: BatchWaterfallRegion, stride = step) => {
    if (!batch) return;
    setRegion(selection);
    void run(
      "batch_waterfall",
      { series: batch.waterfallKey ?? batch.id, ...selection, step: stride },
      "Creating Batch waterfall…",
    );
  };
  return {
    active,
    region,
    toggle: () => {
      setActive(!active);
      setRegion(null);
    },
    cancel: () => {
      setActive(false);
      setRegion(null);
    },
    select: create,
    step: (value: number) => {
      setStep(value);
      if (active && region) create(region, value);
    },
  };
}

export function BatchWaterfallControls({
  active,
  ready,
  onToggle,
}: {
  active: boolean;
  ready: boolean;
  onToggle: () => void;
}) {
  return (
    <PlotToggle
      label="Batch waterfall"
      title={
        active
          ? "Drag a radial/frame rectangle to replace overlays. Step sets the row stride. Escape cancels selection."
          : "Create waterfall overlays from a rectangle in the Batch overview"
      }
      pressed={active}
      disabled={!ready}
      onClick={onToggle}
    >
      <ChartNoAxesCombined size={15} aria-hidden="true" />
      <span className="plot-toolbar-label">Waterfall</span>
    </PlotToggle>
  );
}

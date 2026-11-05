import { colorMapPreview } from "./colorMaps";
import { scientificValue } from "./ScientificNumberInput";

/** A quantitative display key, using the same limits and palette as the plot. */
export function ColorScaleLegend({
  label,
  detail,
  palette,
  limits,
  scale = "linear",
}: {
  label: string;
  detail?: string;
  palette: string;
  limits: [number, number];
  scale?: "linear" | "log" | "sqrt";
}) {
  return (
    <div
      className="color-scale-legend"
      role="group"
      aria-label={`${label} display scale`}
      title="Display limits control color contrast; source values are unchanged."
    >
      <span>
        {label}
        {detail && <small>{detail}</small>}
      </span>
      <span className="color-scale-range">
        <span title={String(limits[0])}>{scientificValue(limits[0], 5)}</span>
        <img
          src={colorMapPreview(palette)}
          alt="Low to high displayed intensity"
        />
        <span title={String(limits[1])}>{scientificValue(limits[1], 5)}</span>
        <span>
          {scale === "log" ? "log" : scale === "sqrt" ? "√" : "linear"}
        </span>
      </span>
    </div>
  );
}

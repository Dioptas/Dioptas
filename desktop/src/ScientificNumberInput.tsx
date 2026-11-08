import { Input } from "./ui";
import type { ComponentProps } from "react";

/** Compact display is not a refit or an uncertainty estimate. Exact draft text
 * remains with the owner and is revealed on focus; focus/blur never round it. */
export const scientificValue = (value: number, digits = 7) => {
  if (!Number.isFinite(value)) return "—";
  const superscripts: Record<string, string> = {
    "-": "⁻",
    "+": "⁺",
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
  };
  return String(Number(value.toPrecision(digits)))
    .replace(
      /e([+-]?\d+)/,
      (_, exponent: string) =>
        ` × 10${[...exponent.replace(/^\+/, "")].map((char) => superscripts[char]).join("")}`,
    )
    .replaceAll("-", "−");
};
export function ScientificNumberInput({
  value,
  onValueChange,
  displayDigits = 7,
  ...props
}: Omit<ComponentProps<"input">, "value" | "onChange"> & {
  value: string;
  onValueChange?: (value: string) => void;
  displayDigits?: number;
}) {
  const number = Number(value);
  const display =
    value.trim() && Number.isFinite(number)
      ? scientificValue(number, displayDigits)
      : value;
  // Formatting is a visual overlay. Never replace the input's value on focus:
  // doing so can interfere with native selection and the first edit event.
  const negative = display.startsWith("−");
  const [mantissa, exponent] = display.split(" × ");
  return (
    <span className="scientific-number-input">
      <Input
        {...props}
        type="number"
        value={value}
        title={props.title ?? value}
        data-exact-value={value}
        onChange={(event) => onValueChange?.(event.currentTarget.value)}
      />
      <span className="scientific-number-preview" aria-hidden="true">
        <span className="scientific-number-sign">{negative ? "−" : ""}</span>
        <span className="scientific-number-digits">
          {negative ? mantissa.slice(1) : mantissa}
        </span>
        {exponent && (
          <span className="scientific-number-exponent"> × {exponent}</span>
        )}
      </span>
    </span>
  );
}

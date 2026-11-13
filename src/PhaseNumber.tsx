import { Input } from "./ui";
import { useEffect, useRef, useState } from "react";
import { useSpinBoxWheel } from "./spinBoxWheel";

export function PhaseNumber({
  label,
  title,
  value,
  onCommit,
  disabled,
  step = "any",
  multiply = false,
  min,
  max,
}: {
  label: string;
  title?: string;
  value: number;
  onCommit: (v: number) => void | Promise<void>;
  disabled?: boolean;
  step?: number | string;
  multiply?: boolean;
  min?: number;
  max?: number;
}) {
  const [text, setText] = useState(String(value));
  const input = useRef<HTMLInputElement>(null);
  const pending = useRef(0);
  const disposed = useRef(false);
  useEffect(
    () => () => {
      disposed.current = true;
    },
    [],
  );
  const draftGeneration = useRef(0);
  const applied = useRef(value);
  applied.current = value;
  const last = useRef(value);
  useEffect(() => {
    if (pending.current) return;
    setText(String(value));
    last.current = value;
  }, [value]);
  const send = (n: number) => {
    const generation = ++draftGeneration.current;
    last.current = n;
    pending.current++;
    void Promise.resolve(onCommit(n))
      .catch(() => {})
      .finally(() => {
        pending.current--;
        requestAnimationFrame(() => {
          if (
            !disposed.current &&
            !pending.current &&
            generation === draftGeneration.current
          ) {
            setText(String(applied.current));
            last.current = applied.current;
          }
        });
      });
  };
  const commit = (input: HTMLInputElement) => {
    const n = Number(text);
    if (
      text.trim() &&
      Number.isFinite(n) &&
      (min === undefined || n >= min) &&
      (max === undefined || n <= max)
    ) {
      if (n !== last.current) {
        send(n);
      }
    } else {
      setText(String(value));
      last.current = value;
    }
    input.setCustomValidity("");
  };
  const increment = (direction: number) => {
    const current =
      text.trim() && Number.isFinite(Number(text)) ? Number(text) : value;
    const power = 10 ** Math.floor(Math.log10(Math.max(current, 1e-10)));
    const ratio = current / power;
    const multiple =
      direction > 0
        ? ratio < 1.9
          ? 2
          : ratio < 4.9
            ? 5
            : 10
        : ratio < 1.1
          ? 0.5
          : ratio < 2.1
            ? 1
            : ratio < 5.1
              ? 2
              : 5;
    const next = multiply
      ? power * multiple
      : current + direction * (typeof step === "number" ? step : 1);
    const n = Math.max(
      min ?? -Infinity,
      Math.min(max ?? Infinity, Number(next.toPrecision(12))),
    );
    setText(String(n));
    if (n !== last.current) {
      send(n);
    }
  };
  useSpinBoxWheel(input, increment);
  return (
    <Input
      ref={input}
      className="numeric-stepper"
      type="number"
      aria-label={label}
      title={title}
      value={text}
      step={step}
      min={min}
      max={max}
      disabled={disabled}
      onChange={(e) => {
        // Native spinner clicks emit plain input events; typed edits carry inputType.
        if (
          !("inputType" in e.nativeEvent) &&
          Number(e.target.value) !== Number(text)
        )
          increment(Number(e.target.value) > Number(text) ? 1 : -1);
        else {
          draftGeneration.current++;
          setText(e.target.value);
        }
      }}
      onBlur={(e) => commit(e.currentTarget)}
      onKeyDown={(e) => {
        if (e.key === "ArrowUp" || e.key === "ArrowDown") {
          e.preventDefault();
          increment(e.key === "ArrowUp" ? 1 : -1);
        }
        if (e.key === "Enter") {
          e.preventDefault();
          commit(e.currentTarget);
        }
        if (e.key === "Escape") {
          draftGeneration.current++;
          setText(String(value));
          last.current = value;
        }
      }}
    />
  );
}

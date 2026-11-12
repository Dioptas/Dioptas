import type { ComponentProps } from "react";
import { Input } from "./ui";

/** Keep a filename's distinguishing counter/extension visible while preserving
 * the exact editable value and its native selection/copy behavior. */
export function middleElidedParts(value: string): [string, string] {
  const basename = value.split(/[\\/]/).at(-1) ?? value;
  const dot = basename.lastIndexOf(".");
  const stem = dot > 0 ? basename.slice(0, dot) : basename;
  const counter = [...stem.matchAll(/\d+/g)].at(-1);
  const suffix = counter
    ? basename.slice(counter.index)
    : basename.slice(-Math.min(12, basename.length));
  const tail = suffix.slice(-24);
  return [value.slice(0, value.length - tail.length), tail];
}

export function MiddleElidedText({
  value,
  className = "",
}: {
  value: string;
  className?: string;
}) {
  const [head, tail] = middleElidedParts(value);
  return (
    <span className={`middle-elided-text ${className}`} title={value}>
      <span className="middle-elided-head">{head}</span>
      <span className="middle-elided-tail">{tail}</span>
    </span>
  );
}

export function MiddleElidedInput({
  value,
  className = "",
  ...props
}: Omit<ComponentProps<"input">, "value"> & { value: string }) {
  return (
    <span className="middle-elided-input">
      <Input {...props} className={className} value={value} />
      <span className="middle-elided-preview" aria-hidden="true">
        <MiddleElidedText value={value} />
      </span>
    </span>
  );
}

import { useLayoutEffect, useRef, type ComponentProps } from "react";

/** A long directory shows its useful tail at rest; native editing stays intact. */
export function PathInput({
  value,
  onBlur,
  ...props
}: ComponentProps<"input">) {
  const input = useRef<HTMLInputElement>(null);
  const showTail = () => {
    const element = input.current;
    if (element && document.activeElement !== element)
      element.scrollLeft = element.scrollWidth;
  };
  useLayoutEffect(showTail, [value]);
  return (
    <input
      {...props}
      ref={input}
      value={value}
      title={String(value ?? "") || props.title}
      style={{ ...props.style, textOverflow: "clip" }}
      onBlur={(event) => {
        onBlur?.(event);
        event.currentTarget.scrollLeft = event.currentTarget.scrollWidth;
      }}
    />
  );
}

import { Input } from "./ui";
import { useLayoutEffect, useRef, useState, type ComponentProps } from "react";

/** Long directories reveal their useful tail, with a visible clipping cue. */
export function PathInput({
  value,
  onBlur,
  ...props
}: ComponentProps<"input">) {
  const input = useRef<HTMLInputElement>(null);
  const [truncated, setTruncated] = useState(false);
  const showTail = () => {
    const element = input.current;
    if (!element) return;
    if (document.activeElement !== element)
      element.scrollLeft = element.scrollWidth;
    setTruncated(element.scrollWidth > element.clientWidth + 1);
  };
  useLayoutEffect(showTail, [value]);
  useLayoutEffect(() => {
    if (!input.current) return;
    const observer = new ResizeObserver(showTail);
    observer.observe(input.current);
    return () => observer.disconnect();
  }, []);
  return (
    <span className="path-input">
      <Input
        {...props}
        ref={input}
        value={value}
        title={String(value ?? "") || props.title}
        aria-description={props["aria-description"] ?? props.title}
        style={{ ...props.style, textOverflow: "clip" }}
        onBlur={(event) => {
          onBlur?.(event);
          event.currentTarget.scrollLeft = event.currentTarget.scrollWidth;
          showTail();
        }}
      />
      {truncated && (
        <span className="path-input-truncation" aria-hidden="true">
          …
        </span>
      )}
    </span>
  );
}

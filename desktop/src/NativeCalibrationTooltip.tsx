import { useEffect, useLayoutEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

type TooltipContent = {
  generation: number;
  text: string;
  fontSize: string;
  width: number;
};

// This window has no scientific bridge and never takes keyboard focus.
export function NativeCalibrationTooltip() {
  const [content, setContent] = useState<TooltipContent | null>(null);
  useEffect(() => {
    document.documentElement.classList.add("native-calibration-tooltip");
    const update = (next: TooltipContent | null) => {
      if (next)
        setContent((current) =>
          !current || next.generation > current.generation ? next : current,
        );
    };
    const receive = (event: Event) =>
      update((event as CustomEvent<TooltipContent>).detail);
    window.addEventListener("calibration-tooltip", receive);
    void invoke<TooltipContent | null>("calibration_tooltip_ready").then(
      update,
    );
    return () => window.removeEventListener("calibration-tooltip", receive);
  }, []);

  useLayoutEffect(() => {
    if (content)
      void invoke("present_calibration_tooltip", {
        generation: content.generation,
      });
  }, [content]);

  return content ? (
    <div
      role="tooltip"
      className="calibration-help-tooltip native-tooltip-content"
      style={{ width: content.width, fontSize: content.fontSize }}
    >
      {content.text}
    </div>
  ) : null;
}

// Keep hover/leave IPC in order, including when moving between help buttons.
let pending = Promise.resolve();
export function nativeTooltipCommand(
  command: string,
  args: Record<string, unknown>,
) {
  const next = pending.then(() => invoke(command, args));
  pending = next.then(
    () => undefined,
    () => undefined,
  );
  return next;
}

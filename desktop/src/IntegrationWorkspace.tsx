import { useRef, useState, type CSSProperties, type ReactNode } from "react";

/** Qt's horizontal image/right splitter and vertical controls/pattern splitter.
 * Renderers remain in App and retain their instances when these dividers move.
 */
export function IntegrationWorkspace({
  active,
  concealed = false,
  display,
  children,
}: {
  active: boolean;
  concealed?: boolean;
  display: string;
  children: ReactNode;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [imageShare, setImageShare] = useState(50);
  const [controlsShare, setControlsShare] = useState(38);
  const constrain = (value: number, axis: "image" | "controls") => {
    const box = container.current;
    const total =
      axis === "image"
        ? (box?.clientWidth ?? 1000) - 20
        : (box?.clientHeight ?? 800) - 16;
    const minimum = axis === "image" ? 300 : 208;
    const otherMinimum = axis === "image" ? 348 : 208;
    return Math.max(
      Math.max(25, (minimum / total) * 100),
      Math.min(Math.min(75, ((total - otherMinimum) / total) * 100), value),
    );
  };
  const divider = (axis: "image" | "controls") => {
    const value = axis === "image" ? imageShare : controlsShare;
    const update = (next: number) =>
      (axis === "image" ? setImageShare : setControlsShare)(
        constrain(next, axis),
      );
    return (
      <div
        className={`integration-divider integration-divider-${axis}`}
        role="separator"
        tabIndex={0}
        aria-label={
          axis === "image"
            ? "Image and analysis divider"
            : "Controls and pattern divider"
        }
        aria-orientation={axis === "image" ? "vertical" : "horizontal"}
        aria-valuemin={25}
        aria-valuemax={75}
        aria-valuenow={Math.round(value)}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          event.preventDefault();
        }}
        onPointerMove={(event) => {
          if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
          const box = container.current?.getBoundingClientRect();
          if (!box) return;
          update(
            axis === "image"
              ? ((event.clientX - box.left) / box.width) * 100
              : ((event.clientY - box.top) / box.height) * 100,
          );
        }}
        onPointerUp={(event) => {
          if (event.currentTarget.hasPointerCapture(event.pointerId))
            event.currentTarget.releasePointerCapture(event.pointerId);
        }}
        onKeyDown={(event) => {
          const lower = axis === "image" ? "ArrowLeft" : "ArrowUp";
          const higher = axis === "image" ? "ArrowRight" : "ArrowDown";
          if (event.key === lower || event.key === higher) {
            event.preventDefault();
            update(value + (event.key === lower ? -2 : 2));
          } else if (event.key === "Home") {
            event.preventDefault();
            update(axis === "image" ? 50 : 38);
          }
        }}
        onDoubleClick={() => update(axis === "image" ? 50 : 38)}
      >
        <span />
      </div>
    );
  };
  return (
    <div
      ref={container}
      inert={concealed}
      aria-hidden={concealed || undefined}
      data-concealed={concealed}
      className={`workspace-content ${active ? "integration-layout" : ""}`}
      data-integration-display={display}
      style={
        active
          ? ({
              "--integration-image-share": `${imageShare}%`,
              "--integration-controls-share": `${controlsShare}%`,
            } as CSSProperties)
          : undefined
      }
    >
      {children}
      {active && (
        <>
          {divider("image")}
          {divider("controls")}
        </>
      )}
    </div>
  );
}

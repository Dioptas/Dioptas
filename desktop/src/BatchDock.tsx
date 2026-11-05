import { useEffect, useRef, useState, type ComponentProps } from "react";
import { BatchView } from "./BatchView";
export function BatchDock(
  props: Omit<
    ComponentProps<typeof BatchView>,
    "collapsed" | "onCollapse" | "docked"
  >,
) {
  const container = useRef<HTMLDivElement>(null),
    start = useRef({ y: 0, height: 0 });
  const [collapsed, setCollapsed] = useState(false);
  const [height, setHeight] = useState(() => {
    try {
      return Math.max(
        220,
        Math.min(
          600,
          Number(localStorage.getItem("dioptas-batch:dock-height")) || 320,
        ),
      );
    } catch {
      return 320;
    }
  });
  const maximum = () => {
    const parent = container.current?.parentElement;
    const toolbar =
      parent?.querySelector(".integration-image-tools")?.getBoundingClientRect()
        .height ?? 40;
    return Math.max(220, (parent?.clientHeight ?? 650) - toolbar - 180);
  };
  useEffect(() => {
    const parent = container.current?.parentElement;
    if (!parent) return;
    const observer = new ResizeObserver(() =>
      setHeight((h) => Math.min(h, maximum())),
    );
    observer.observe(parent);
    const tools = parent.querySelector(".integration-image-tools");
    if (tools) observer.observe(tools);
    return () => observer.disconnect();
  }, []);
  const update = (next: number) => {
    const max = maximum();
    const value = Math.max(220, Math.min(max, next));
    setHeight(value);
    try {
      localStorage.setItem("dioptas-batch:dock-height", String(value));
    } catch {
      /* Keep session height. */
    }
  };
  return (
    <div
      ref={container}
      className={`batch-dock ${collapsed ? "batch-dock-collapsed" : ""}`}
      style={{ height: collapsed ? 36 : height }}
    >
      {!collapsed && (
        <div
          className="batch-dock-divider"
          role="separator"
          tabIndex={0}
          aria-label="Image and batch divider"
          title="Drag to resize image and Batch; double-click to reset"
          aria-orientation="horizontal"
          aria-valuemin={220}
          aria-valuenow={Math.round(height)}
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            start.current = {
              y: e.clientY,
              height: container.current?.clientHeight ?? height,
            };
            e.currentTarget.setPointerCapture(e.pointerId);
            e.preventDefault();
          }}
          onPointerMove={(e) => {
            if (e.currentTarget.hasPointerCapture(e.pointerId))
              update(start.current.height + start.current.y - e.clientY);
          }}
          onPointerUp={(e) => {
            if (e.currentTarget.hasPointerCapture(e.pointerId))
              e.currentTarget.releasePointerCapture(e.pointerId);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowUp" || e.key === "ArrowDown") {
              e.preventDefault();
              update(height + (e.key === "ArrowUp" ? 20 : -20));
            }
          }}
          onDoubleClick={() => update(320)}
        >
          <span />
        </div>
      )}
      <BatchView
        {...props}
        docked
        collapsed={collapsed}
        onCollapse={() => setCollapsed((v) => !v)}
      />
    </div>
  );
}

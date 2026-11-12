import { useIntegrationLayout } from "./IntegrationWorkspace";
import { useDetectorDetached } from "./DetectorWindow";
import { LayoutDivider } from "./LayoutDivider";
import {
  layoutKeys,
  readLayoutFlag,
  readLayoutNumber,
  saveLayoutValue,
} from "./layoutPreferences";
import { useEffect, useRef, useState, type ComponentProps } from "react";
import { BatchView } from "./BatchView";
export function BatchDock(
  props: Omit<
    ComponentProps<typeof BatchView>,
    "collapsed" | "onCollapse" | "docked"
  >,
) {
  const { narrow } = useIntegrationLayout();
  const imageDetached = useDetectorDetached();
  const fill = narrow || imageDetached;
  const container = useRef<HTMLDivElement>(null),
    start = useRef({ y: 0, height: 0 });
  const [collapsed, setCollapsed] = useState(() =>
    readLayoutFlag(layoutKeys.batchCollapsed),
  );
  const [preferredHeight, setHeight] = useState(() =>
    readLayoutNumber(layoutKeys.batchHeight, 320, 220, 600),
  );
  const [availableHeight, setAvailableHeight] = useState(600);
  const height = Math.min(preferredHeight, availableHeight);
  const maximum = () => {
    const parent = container.current?.closest(".integration-left-pane");
    const toolbar =
      parent?.querySelector(".integration-image-tools")?.getBoundingClientRect()
        .height ?? 40;
    return Math.max(220, (parent?.clientHeight ?? 650) - toolbar - 180);
  };
  useEffect(() => {
    const parent = container.current?.closest(".integration-left-pane");
    if (!parent) return;
    const observer = new ResizeObserver(() => setAvailableHeight(maximum()));
    observer.observe(parent);
    const tools = parent.querySelector(".integration-image-tools");
    if (tools) observer.observe(tools);
    return () => observer.disconnect();
  }, [imageDetached]);
  const update = (next: number) => {
    const max = maximum();
    const value = Math.max(220, Math.min(max, next));
    setHeight(value);
    saveLayoutValue(layoutKeys.batchHeight, value);
  };
  return (
    <div
      ref={container}
      className={`batch-dock ${fill ? "batch-dock-fill" : ""} ${!fill && collapsed ? "batch-dock-collapsed" : ""}`}
      style={fill ? undefined : { height: collapsed ? 36 : height }}
    >
      {!fill && !collapsed && (
        <LayoutDivider
          className="integration-divider integration-divider-horizontal batch-dock-divider"
          label="Image and batch divider"
          orientation="horizontal"
          value={height}
          min={220}
          max={Math.max(220, availableHeight)}
          defaultValue={320}
          step={20}
          reverse
          unit="px"
          onChange={update}
          onDragStart={(event) => {
            start.current = {
              y: event.clientY,
              height: container.current?.clientHeight ?? height,
            };
          }}
          pointerValue={(event) =>
            start.current.height + start.current.y - event.clientY
          }
        />
      )}
      <BatchView
        {...props}
        docked
        collapsed={!fill && collapsed}
        onCollapse={
          fill
            ? undefined
            : () => {
                setCollapsed(!collapsed);
                saveLayoutValue(layoutKeys.batchCollapsed, !collapsed);
              }
        }
      />
    </div>
  );
}

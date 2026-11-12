import { LayoutDivider } from "./LayoutDivider";
import {
  layoutKeys,
  readLayoutNumber,
  saveLayoutValue,
} from "./layoutPreferences";
import {
  createContext,
  useContext,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

const IntegrationLayout = createContext({ narrow: false });
export const useIntegrationLayout = () => useContext(IntegrationLayout);

/** Qt's horizontal image/right splitter and vertical controls/pattern splitter.
 * Renderers remain in App and retain their instances when these dividers move.
 */
export function IntegrationWorkspace({
  active,
  concealed = false,
  controlsCollapsed = false,
  detectorDetached = false,
  display,
  children,
}: {
  active: boolean;
  concealed?: boolean;
  controlsCollapsed?: boolean;
  detectorDetached?: boolean;
  display: string;
  children: ReactNode;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [preferredImage, setImageShare] = useState(() =>
    readLayoutNumber(layoutKeys.imageShare, 50, 25, 75),
  );
  const [preferredControls, setControlsShare] = useState(() =>
    readLayoutNumber(layoutKeys.controlsShare, 38, 25, 75),
  );
  const [size, setSize] = useState({ width: 1000, height: 800 });
  useLayoutEffect(() => {
    const node = container.current;
    if (!active || !node) return;
    const measure = () =>
      setSize((old) =>
        old.width === node.clientWidth && old.height === node.clientHeight
          ? old
          : { width: node.clientWidth, height: node.clientHeight },
      );
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [active]);
  const narrow = active && size.width < 1160;
  const constrain = (value: number, axis: "image" | "controls") => {
    const total = axis === "image" ? size.width - 20 : size.height - 16;
    const minimum = axis === "image" ? 300 : 208;
    const otherMinimum = axis === "image" ? 348 : 208;
    return Math.max(
      Math.max(25, (minimum / total) * 100),
      Math.min(Math.min(75, ((total - otherMinimum) / total) * 100), value),
    );
  };
  const imageShare = constrain(preferredImage, "image");
  const controlsShare = constrain(preferredControls, "controls");
  const divider = (axis: "image" | "controls") => {
    const value = axis === "image" ? imageShare : controlsShare;
    const update = (next: number) => {
      const value = constrain(next, axis);
      (axis === "image" ? setImageShare : setControlsShare)(value);
      saveLayoutValue(
        axis === "image" ? layoutKeys.imageShare : layoutKeys.controlsShare,
        value,
      );
    };
    return (
      <LayoutDivider
        className={`integration-divider integration-divider-${axis}`}
        label={
          axis === "image"
            ? "Image and analysis divider"
            : "Controls and pattern divider"
        }
        orientation={axis === "image" ? "vertical" : "horizontal"}
        value={value}
        min={constrain(0, axis)}
        max={constrain(100, axis)}
        defaultValue={axis === "image" ? 50 : 38}
        onChange={update}
        pointerValue={(event) => {
          const box = container.current?.getBoundingClientRect();
          return !box
            ? null
            : axis === "image"
              ? ((event.clientX - box.left) / box.width) * 100
              : ((event.clientY - box.top) / box.height) * 100;
        }}
      />
    );
  };
  return (
    <IntegrationLayout.Provider value={{ narrow }}>
      <div
        ref={container}
        inert={concealed}
        aria-hidden={concealed || undefined}
        data-concealed={concealed}
        className={`workspace-content ${active ? "integration-layout" : ""}`}
        data-integration-display={display}
        data-integration-layout={narrow ? "top" : "right"}
        data-controls-collapsed={controlsCollapsed}
        data-detector-detached={detectorDetached}
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
            {!controlsCollapsed && divider("controls")}
          </>
        )}
      </div>
    </IntegrationLayout.Provider>
  );
}

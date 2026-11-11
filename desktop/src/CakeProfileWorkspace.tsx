import {
  createContext,
  useContext,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type PointerEvent,
  type RefObject,
} from "react";
import { LayoutDivider } from "./LayoutDivider";
import {
  layoutKeys,
  readLayoutNumber,
  saveLayoutValue,
} from "./layoutPreferences";
import type { usePlotNavigation } from "./usePlotNavigation";

type Kind = "profile" | "cake";
type Event = PointerEvent<HTMLCanvasElement>;
type Navigation = ReturnType<typeof usePlotNavigation>;
type Plot = { element: HTMLCanvasElement; navigation: Navigation };
type Start = { clientX: number; clientY: number; pointerId: number };
const ProfileWindow = createContext<{
  visible: boolean;
  setVisible: (visible: boolean) => void;
  range: [number, number] | null;
  setRange: (range: [number, number] | null) => void;
} | null>(null);

export const useCakeProfileWindow = () => useContext(ProfileWindow);

function forwarded(
  event: Event,
  element: HTMLCanvasElement,
  start?: Start,
): Event {
  return {
    currentTarget: element,
    clientX: start?.clientX ?? event.clientX,
    clientY: start?.clientY ?? event.clientY,
    pointerId: event.pointerId,
    button: 0,
    ctrlKey: false,
    metaKey: false,
    timeStamp: event.timeStamp,
    preventDefault: () => event.preventDefault(),
    stopPropagation: () => event.stopPropagation(),
  } as Event;
}
function axisGestures() {
  const plots = new Map<Kind, { current: Plot | null }>();
  let drag: (Start & { target: Kind }) | null = null;
  const plot = (kind: Kind) => plots.get(kind)?.current;
  return {
    register(kind: Kind, value: { current: Plot | null }) {
      plots.set(kind, value);
      return () => {
        if (plots.get(kind) !== value) return;
        if (drag?.target === kind) {
          const element = value.current?.element;
          if (element?.hasPointerCapture(drag.pointerId))
            element.releasePointerCapture(drag.pointerId);
          drag = null;
        }
        plots.delete(kind);
      };
    },
    start(event: Event) {
      const p = plot("profile");
      if (
        !p ||
        !plot("cake") ||
        event.button !== 0 ||
        event.ctrlKey ||
        event.metaKey
      )
        return false;
      drag = {
        clientX: event.clientX,
        clientY: event.clientY,
        pointerId: event.pointerId,
        target: "profile",
      };
      p.navigation.onPointerDown(forwarded(event, p.element), true, true);
      return true;
    },
    move(event: Event) {
      if (!drag || drag.pointerId !== event.pointerId) return false;
      const cake = plot("cake");
      const target: Kind =
        cake &&
        event.clientX >=
          cake.element.getBoundingClientRect().left +
            Number(cake.element.dataset.plotLeft)
          ? "cake"
          : "profile";
      const next = plot(target);
      if (!next) return false;
      if (drag.target !== target) {
        const previous = plot(drag.target);
        if (previous)
          previous.navigation.onPointerCancel(
            forwarded(event, previous.element),
          );
        drag.target = target;
        next.navigation.onPointerDown(
          forwarded(event, next.element, drag),
          true,
          true,
        );
      }
      next.navigation.onPointerMove(forwarded(event, next.element));
      return true;
    },
    finish(event: Event) {
      if (!drag || drag.pointerId !== event.pointerId) return false;
      this.move(event);
      const current = plot(drag.target);
      drag = null;
      current?.navigation.onPointerUp(forwarded(event, current.element));
      return true;
    },
    cancel(event: Event) {
      if (!drag || drag.pointerId !== event.pointerId) return false;
      const current = plot(drag.target);
      drag = null;
      current?.navigation.onPointerCancel(forwarded(event, current.element));
      return true;
    },
  };
}
const SharedAxisGestures = createContext<ReturnType<
  typeof axisGestures
> | null>(null);

/** An axis-started selection may cross the divider without losing its gesture. */
export function useCakeAxisGesture(
  kind: Kind,
  element: RefObject<HTMLCanvasElement | null>,
  navigation: Navigation,
) {
  const shared = useContext(SharedAxisGestures);
  const latest = useRef<Plot | null>(null);
  latest.current = element.current
    ? { element: element.current, navigation }
    : null;
  useLayoutEffect(() => {
    latest.current = element.current
      ? { element: element.current, navigation }
      : null;
    return shared?.register(kind, latest);
  }, [shared, kind]);
  return shared;
}

function CakeProfileDivider() {
  const holder = useRef<HTMLDivElement>(null);
  const [available, setAvailable] = useState(500);
  const [preferred, setPreferred] = useState(() =>
    readLayoutNumber(layoutKeys.cakeProfileWidth, 0, 0, 10000),
  );
  useLayoutEffect(() => {
    const workspace = holder.current?.parentElement;
    if (!workspace) return;
    const histogram = workspace.querySelector<HTMLElement>(
      ":scope > .image-intensity",
    );
    const measure = () => {
      if (!workspace.clientWidth) return;
      const histogramWidth =
        histogram?.dataset.orientation === "vertical"
          ? histogram.getBoundingClientRect().width
          : 0;
      setAvailable(Math.max(1, workspace.clientWidth - histogramWidth - 8));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(workspace);
    if (histogram) observer.observe(histogram);
    const mutations = new MutationObserver(measure);
    mutations.observe(workspace, {
      subtree: true,
      attributes: true,
      attributeFilter: ["data-orientation"],
    });
    return () => {
      observer.disconnect();
      mutations.disconnect();
      workspace.style.removeProperty("--cake-profile-width");
    };
  }, []);
  const min = Math.min(160, available * 0.45),
    max = Math.max(min, available - 140);
  const clamp = (width: number) => Math.max(min, Math.min(max, width));
  const defaultWidth = clamp(Math.max(170, Math.min(230, available * 0.3)));
  const width = clamp(preferred || defaultWidth);
  useLayoutEffect(() => {
    holder.current?.parentElement?.style.setProperty(
      "--cake-profile-width",
      `${width}px`,
    );
  }, [width]);
  return (
    <div ref={holder} className="cake-profile-divider-slot">
      <LayoutDivider
        className="integration-divider cake-profile-divider"
        label="Profile and cake divider"
        orientation="vertical"
        unit="px"
        value={width}
        min={min}
        max={max}
        defaultValue={defaultWidth}
        step={8}
        onChange={(next) => {
          setPreferred(next);
          saveLayoutValue(layoutKeys.cakeProfileWidth, next);
        }}
        pointerValue={(event) => {
          const box = holder.current?.parentElement?.getBoundingClientRect();
          return box ? event.clientX - box.left - 4 : null;
        }}
      />
    </div>
  );
}

export function CakeProfileWorkspace({
  profile,
  children,
}: {
  profile?: ReactNode;
  children: ReactNode;
}) {
  const gestures = useMemo(axisGestures, []);
  const [visible, setVisible] = useState(true);
  const [range, setRange] = useState<[number, number] | null>(null);
  const window = useMemo(
    () => ({ visible: !!profile && visible, setVisible, range, setRange }),
    [profile, visible, range],
  );
  return (
    <SharedAxisGestures.Provider value={gestures}>
      <ProfileWindow.Provider value={window}>
        <div className="detector-workspace">
          {profile}
          {profile && <CakeProfileDivider />}
          {children}
        </div>
      </ProfileWindow.Provider>
    </SharedAxisGestures.Provider>
  );
}

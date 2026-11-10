import { Input, Select, Button, Portal } from "./ui";
import { Dialog, DialogHeader } from "./Dialog";
import { useEffect, useId, useRef, useState } from "react";

import { Settings } from "lucide-react";
import type {
  Palette,
  Raster,
  AutoLevels,
  ImageDisplayPreferences,
} from "./types";
import { ColorMapPicker } from "./ColorMapPicker";
import type { ColorMapPickerHandle } from "./ColorMapPicker";
import { colorsFor } from "./colorMaps";

type WindowDrag = {
  kind: "min" | "max" | "window";
  start: number;
  min: number;
  max: number;
  axisMin: number;
  axisMax: number;
};
const editableIntensity = (value: number) =>
  String(Number(value.toPrecision(7)));

export function ImageIntensity({
  raster,
  limits,
  onLimits,
  log,
  onLog,
  palette,
  onPalette,
  onAuto,
  ready,
  display = "detector",
  preferences,
  onPreferences,
  initialLevelsReady = false,
  initialAutoActive = true,
  onAutoActiveChange,
  mirrored = false,
  gapFiltering = true,
}: {
  preferences: ImageDisplayPreferences;
  onPreferences: (preferences: ImageDisplayPreferences) => void;
  raster: Raster;
  limits: [number, number];
  onLimits: (limits: [number, number]) => void;
  log: boolean;
  onLog: (value: boolean) => void;
  palette: Palette;
  onPalette: (value: Palette) => void;
  onAuto: (settings: AutoLevels) => unknown;
  ready: boolean;
  display?: "detector" | "cake" | "map" | "batch";
  initialLevelsReady?: boolean;
  initialAutoActive?: boolean;
  onAutoActiveChange?: (active: boolean) => void;
  mirrored?: boolean;
  gapFiltering?: boolean;
}) {
  const id = useId(),
    container = useRef<HTMLDivElement>(null);
  const dialogTrigger = useRef<HTMLElement | SVGElement | null>(null);
  const colorMapPicker = useRef<ColorMapPickerHandle>(null);
  const [size, setSize] = useState({ width: 136, height: 300 });
  const horizontal = preferences.orientation === "horizontal";
  const auto = preferences.auto;
  const [percentileDraft, setPercentileDraft] = useState(
    String(auto.percentile),
  );
  const [minimumDraft, setMinimumDraft] = useState(() =>
    editableIntensity(limits[0]),
  );
  const [maximumDraft, setMaximumDraft] = useState(() =>
    editableIntensity(limits[1]),
  );
  useEffect(
    () => setPercentileDraft(String(auto.percentile)),
    [auto.percentile],
  );
  useEffect(() => setMinimumDraft(editableIntensity(limits[0])), [limits[0]]);
  useEffect(() => setMaximumDraft(editableIntensity(limits[1])), [limits[1]]);
  const [autoActive, setLocalAutoActive] = useState(initialAutoActive);
  const setAutoActive = (active: boolean) => {
    setLocalAutoActive(active);
    onAutoActiveChange?.(active);
  };
  const applyAuto = (settings: AutoLevels) => {
    previousSource.current = raster.data;
    setAutoActive(true);
    return onAuto(settings);
  };
  const setHorizontal = (horizontal: boolean) =>
    onPreferences({
      ...preferences,
      orientation: horizontal ? "horizontal" : "vertical",
    });
  const setAuto = (auto: AutoLevels) => onPreferences({ ...preferences, auto });
  const [dialog, setDialog] = useState<{ x: number; y: number } | null>(null);
  const previousSource = useRef<Raster["data"] | null>(
    initialLevelsReady ? raster.data : null,
  );
  const [drag, setDrag] = useState<WindowDrag | null>(null);
  const [hover, setHover] = useState<WindowDrag["kind"] | null>(null);
  const active = drag?.kind ?? hover;
  const label = (text: string) =>
    display === "detector"
      ? text
      : `${display === "batch" ? "Batch" : display === "map" ? "Map" : "Cake"} ${text[0].toLowerCase()}${text.slice(1)}`;
  const title =
    display === "batch"
      ? "Batch"
      : display === "map"
        ? "Map"
        : display === "cake"
          ? "Cake"
          : "Detector";
  const open = (x: number, y: number, trigger: HTMLElement | SVGElement) => {
    dialogTrigger.current = trigger;
    setDialog({ x, y });
  };
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) =>
      setSize({
        width: Math.max(1, entry.contentRect.width),
        height: Math.max(1, entry.contentRect.height),
      }),
    );
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!autoActive || !ready || previousSource.current === raster.data) return;
    if (
      raster.autoLevels?.mode === auto.mode &&
      raster.autoLevels.percentile === auto.percentile &&
      raster.autoLevels.filter_gaps === auto.filter_gaps
    ) {
      previousSource.current = raster.data;
      return;
    }
    const timer = setTimeout(() => {
      previousSource.current = raster.data;
      applyAuto(auto);
    }, 0);
    return () => clearTimeout(timer);
  }, [raster.data, ready, autoActive]);
  const updateAuto = (change: Partial<AutoLevels>) => {
    const next = { ...auto, ...change };
    setAuto(next);
    applyAuto(next);
  };
  const commitPercentile = () => {
    const percentile = Number(percentileDraft);
    if (
      percentileDraft.trim() &&
      Number.isFinite(percentile) &&
      percentile >= 0.01 &&
      percentile <= 25
    ) {
      setPercentileDraft(String(percentile));
      updateAuto({ percentile });
    } else setPercentileDraft(String(auto.percentile));
  };
  const edges = raster.histogram?.edges ?? [0, Math.max(1, raster.limits[1])],
    counts = raster.histogram?.counts ?? [0];
  // Freeze the axis during a gesture so extending the range does not change
  // the pointer-to-intensity mapping. Fit the extended limits on release.
  const min = drag?.axisMin ?? Math.asinh(Math.min(edges[0], limits[0])),
    max = drag?.axisMax ?? Math.asinh(Math.max(edges.at(-1)!, limits[1])),
    span = Math.max(1e-9, max - min),
    gap = span / 1000;
  const length = Math.max(40, horizontal ? size.width : size.height),
    plotLength = length - 32;
  const offset = 38,
    thickness = 92;
  const y = (value: number) =>
    16 + (1 - (Math.asinh(value) - min) / span) * plotLength;
  const upper = Math.max(16, Math.min(length - 16, y(limits[1]))),
    lower = Math.max(16, Math.min(length - 16, y(limits[0])));
  const peak = Math.max(1, ...counts.map((n) => Math.log1p(n)));
  const update = (low: number, high: number) => {
    if (Number.isFinite(low) && Number.isFinite(high) && low < high) {
      setAutoActive(false);
      onLimits([low, high]);
    }
  };
  const commitLimit = (index: 0 | 1, draft: string) => {
    const value = draft.trim() ? Number(draft) : NaN;
    const next: [number, number] = [...limits];
    next[index] = value;
    const valid = Number.isFinite(value) && next[0] < next[1];
    if (valid) update(...next);
    (index === 0 ? setMinimumDraft : setMaximumDraft)(
      editableIntensity(valid ? value : limits[index]),
    );
  };
  const coordinate = (event: React.PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const f = horizontal
      ? (event.clientX - box.left) / box.width
      : (event.clientY - box.top) / box.height;
    return (
      min +
      (horizontal
        ? (f * length - 16) / plotLength
        : 1 - (f * length - 16) / plotLength) *
        span
    );
  };
  // Hover and drag use the same hit area, including the generous handle margin.
  const targetAt = (event: React.PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const cross = horizontal
      ? 130 - ((event.clientY - box.top) / box.height) * thickness
      : (mirrored
          ? 1 - (event.clientX - box.left) / box.width
          : (event.clientX - box.left) / box.width) *
          thickness +
        offset;
    if (cross < 39 || cross > 94) return null;
    const value = coordinate(event),
      a = Math.asinh(limits[0]),
      b = Math.asinh(limits[1]),
      near = (span * 12) / plotLength;
    if (Math.min(Math.abs(value - a), Math.abs(value - b)) < near)
      return Math.abs(value - a) <= Math.abs(value - b) ? "min" : "max";
    if (value > a && value < b) return "window";
    return Math.abs(value - a) < Math.abs(value - b) ? "min" : "max";
  };
  const move = (value: number, current: WindowDrag) => {
    if (current.kind === "min")
      update(
        Math.sinh(Math.min(value, Math.asinh(limits[1]) - gap)),
        limits[1],
      );
    else if (current.kind === "max")
      update(
        limits[0],
        Math.sinh(Math.max(value, Math.asinh(limits[0]) + gap)),
      );
    else {
      const shift = value - current.start;
      update(Math.sinh(current.min + shift), Math.sinh(current.max + shift));
    }
  };
  return (
    <>
      <aside
        className="image-intensity"
        data-display={display}
        data-orientation={horizontal ? "horizontal" : "vertical"}
        data-mirrored={mirrored && !horizontal}
        aria-label={`${title} intensity controls`}
      >
        <div className="histogram-container" ref={container}>
          <svg
            className="intensity-histogram"
            data-active-target={active ?? undefined}
            data-dragging={!!drag}
            data-testid={
              display === "cake"
                ? "cake-intensity-histogram"
                : "intensity-histogram"
            }
            viewBox={
              horizontal
                ? `0 0 ${length} ${thickness}`
                : `${offset} 0 ${thickness} ${length}`
            }
            preserveAspectRatio="none"
            aria-label={`${title} intensity histogram`}
            onDoubleClick={(event) =>
              open(event.clientX, event.clientY, event.currentTarget)
            }
            onPointerDown={(event) => {
              if (event.button !== 0) return;
              const kind = targetAt(event);
              if (!kind) return;
              const value = coordinate(event),
                a = Math.asinh(limits[0]),
                b = Math.asinh(limits[1]);
              const current: WindowDrag = {
                kind,
                start: value,
                min: a,
                max: b,
                axisMin: min,
                axisMax: max,
              };
              setHover(kind);
              setDrag(current);
              event.currentTarget.setPointerCapture(event.pointerId);
              if (kind !== "window") move(value, current);
              event.preventDefault();
            }}
            onPointerMove={(event) => {
              if (drag) move(coordinate(event), drag);
              else setHover(targetAt(event));
            }}
            onPointerLeave={() => setHover(null)}
            onPointerUp={(event) => {
              setDrag(null);
              // The axis can refit on release; let the next move resolve hover.
              setHover(null);
              if (event.currentTarget.hasPointerCapture(event.pointerId))
                event.currentTarget.releasePointerCapture(event.pointerId);
            }}
            onPointerCancel={() => {
              setDrag(null);
              setHover(null);
            }}
            onLostPointerCapture={() => setDrag(null)}
          >
            <title>{`${title} intensity. Drag the window or handles. Left or right click the colour scale to choose a colour map. Use the settings button or double-click the histogram for display settings.`}</title>
            <defs>
              <linearGradient id={`${id}-ramp`} x1="0" y1="1" x2="0" y2="0">
                {colorsFor(palette).map((rgb, i, colors) => (
                  <stop
                    key={i}
                    offset={i / (colors.length - 1)}
                    stopColor={`rgb(${rgb.join(",")})`}
                  />
                ))}
              </linearGradient>
            </defs>
            <g
              transform={
                horizontal
                  ? `matrix(0,-1,-1,0,${length},130)`
                  : mirrored
                    ? `translate(${2 * offset + thickness},0) scale(-1,1)`
                    : undefined
              }
            >
              <rect
                data-testid="intensity-selected-window"
                x="42"
                y={upper}
                width="50"
                height={Math.max(0, lower - upper)}
                fill="#ff95001a"
              />
              {counts.map((count, i) => {
                const top = Math.max(
                    16,
                    Math.min(length - 16, y(edges[i + 1])),
                  ),
                  bottom = Math.max(16, Math.min(length - 16, y(edges[i])));
                return (
                  <rect
                    key={i}
                    x="42"
                    y={top}
                    width={(Math.log1p(count) / peak) * 50}
                    height={Math.max(0.6, bottom - top)}
                    fill="#829ba8"
                    fillOpacity=".8"
                  />
                );
              })}
              <rect
                className="intensity-window-feedback"
                x="42"
                y={upper}
                width="50"
                height={Math.max(0, lower - upper)}
                pointerEvents="none"
              />
              <rect
                data-testid="intensity-colour-bar"
                className="intensity-colour-bar"
                x="101"
                y="16"
                width="21"
                height={plotLength}
                fill={`url(#${id}-ramp)`}
                role="button"
                tabIndex={0}
                aria-label={label("Color map")}
                data-color-map={palette}
                aria-haspopup="listbox"
                onClick={(event) => {
                  event.stopPropagation();
                  colorMapPicker.current?.open(event.currentTarget, event);
                }}
                onContextMenu={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  colorMapPicker.current?.open(event.currentTarget, event);
                }}
                onDoubleClick={(event) => event.stopPropagation()}
                onKeyDown={(event) => {
                  if (["Enter", " "].includes(event.key)) {
                    event.preventDefault();
                    event.stopPropagation();
                    colorMapPicker.current?.open(event.currentTarget);
                  }
                }}
              />
              {(
                [
                  ["max", upper, limits[1]],
                  ["min", lower, limits[0]],
                ] as const
              ).map(([kind, position, value]) => (
                <g
                  key={kind}
                  className="intensity-handle"
                  data-active={active === kind}
                  role="slider"
                  tabIndex={0}
                  aria-label={label(
                    kind === "min"
                      ? "Lower intensity handle"
                      : "Upper intensity handle",
                  )}
                  aria-orientation={horizontal ? "horizontal" : "vertical"}
                  aria-valuemin={Math.sinh(min)}
                  aria-valuemax={Math.sinh(max)}
                  aria-valuenow={value}
                  onKeyDown={(event) => {
                    if (
                      ![
                        "ArrowUp",
                        "ArrowDown",
                        "ArrowRight",
                        "ArrowLeft",
                      ].includes(event.key)
                    )
                      return;
                    event.preventDefault();
                    event.stopPropagation();
                    const direction = ["ArrowUp", "ArrowRight"].includes(
                      event.key,
                    )
                      ? 1
                      : -1;
                    move(Math.asinh(value) + (direction * span) / 100, {
                      kind,
                      start: 0,
                      min: 0,
                      max: 0,
                      axisMin: min,
                      axisMax: max,
                    });
                  }}
                >
                  <title>{value.toLocaleString()}</title>
                  <rect
                    className="intensity-handle-feedback"
                    x="39"
                    y={position - 9}
                    width="54"
                    height="18"
                    fill="transparent"
                  />
                  <path
                    d={`M42 ${position}H92`}
                    stroke="#10151b"
                    strokeWidth="5"
                  />
                  <path
                    className="intensity-handle-line"
                    d={`M42 ${position}H92`}
                    stroke="#ff9500"
                    strokeWidth="2"
                  />
                  <path
                    className="intensity-handle-marker"
                    d={`M92 ${position - 5} 86 ${position} 92 ${position + 5}Z`}
                    fill="#ff9500"
                  />
                </g>
              ))}
            </g>
          </svg>
        </div>
        <div className="intensity-basic-controls">
          <div className="intensity-actions">
            <Button
              aria-label={label("Auto intensity")}
              aria-pressed={autoActive}
              disabled={!ready}
              title={
                autoActive
                  ? "Disable auto levels and keep current limits"
                  : "Enable auto levels for each image"
              }
              onClick={() =>
                autoActive ? setAutoActive(false) : applyAuto(auto)
              }
            >
              {horizontal ? "A" : "Auto"}
            </Button>
            <Button
              aria-label={`${title} histogram settings`}
              aria-haspopup="dialog"
              aria-expanded={!!dialog}
              title={`${title} histogram settings`}
              onClick={(event) => {
                const box = event.currentTarget.getBoundingClientRect();
                open(box.left, box.bottom, event.currentTarget);
              }}
            >
              <Settings size={16} aria-hidden="true" />
            </Button>
          </div>
          <ColorMapPicker
            ref={colorMapPicker}
            label={label("Color map")}
            value={palette}
            onChange={onPalette}
          />
        </div>
      </aside>
      {dialog && (
        <Portal>
          {
            <Dialog
              returnFocusTarget={dialogTrigger.current}
              aria-label={`${title} display settings`}
              className="display-settings"
              style={{
                left: Math.max(8, Math.min(dialog.x, window.innerWidth - 316)),
                top: Math.max(8, Math.min(dialog.y, window.innerHeight - 530)),
              }}
              onDismiss={() => setDialog(null)}
            >
              <DialogHeader
                title={`${title} display`}
                closeLabel={`Close ${display} display settings`}
                onClose={() => setDialog(null)}
              />
              <label>
                Scale
                <Select
                  aria-label={label("Image scale")}
                  value={log ? "log" : "linear"}
                  onChange={(event) => {
                    setAutoActive(false);
                    onLog(event.target.value === "log");
                  }}
                >
                  <option value="linear">Linear</option>
                  <option value="log">Logarithmic</option>
                </Select>
              </label>
              <label>
                Auto mode
                <Select
                  aria-label={label("Auto intensity mode")}
                  value={auto.mode}
                  disabled={!ready}
                  onChange={(event) =>
                    updateAuto({
                      mode: event.target.value as AutoLevels["mode"],
                    })
                  }
                >
                  <option value="percentile">Percentile</option>
                  <option value="minmax">Min/max</option>
                  <option value="mean3std">Mean ± 3 std</option>
                </Select>
              </label>
              {auto.mode === "percentile" && (
                <label>
                  Clip each tail · %
                  <Input
                    aria-label={label("Clipping percentile")}
                    type="number"
                    min="0.01"
                    max="25"
                    step=".01"
                    value={percentileDraft}
                    disabled={!ready}
                    onChange={(event) => setPercentileDraft(event.target.value)}
                    onBlur={commitPercentile}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        commitPercentile();
                      }
                    }}
                  />
                </label>
              )}
              {gapFiltering && (
                <label className="display-settings-check">
                  <Input
                    aria-label={label("Filter detector gaps")}
                    type="checkbox"
                    checked={auto.filter_gaps}
                    disabled={!ready}
                    onChange={(event) =>
                      updateAuto({ filter_gaps: event.target.checked })
                    }
                  />
                  Filter gaps
                </label>
              )}
              <label>
                Minimum
                <Input
                  aria-label={label("Minimum intensity")}
                  type="number"
                  step="any"
                  value={minimumDraft}
                  onChange={(event) => setMinimumDraft(event.target.value)}
                  onBlur={() => commitLimit(0, minimumDraft)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      commitLimit(0, minimumDraft);
                    }
                  }}
                />
              </label>
              <label>
                Maximum
                <Input
                  aria-label={label("Maximum intensity")}
                  type="number"
                  step="any"
                  value={maximumDraft}
                  onChange={(event) => setMaximumDraft(event.target.value)}
                  onBlur={() => commitLimit(1, maximumDraft)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      commitLimit(1, maximumDraft);
                    }
                  }}
                />
              </label>
              <label>
                Bar layout
                <Select
                  aria-label={label("Histogram orientation")}
                  value={horizontal ? "horizontal" : "vertical"}
                  onChange={(event) =>
                    setHorizontal(event.target.value === "horizontal")
                  }
                >
                  <option value="vertical">Vertical (right)</option>
                  <option value="horizontal">Horizontal (top)</option>
                </Select>
              </label>
              <p className="ui-display-note">
                Intensity in source units. Display changes leave scientific data
                unchanged.
              </p>
            </Dialog>
          }
        </Portal>
      )}
    </>
  );
}

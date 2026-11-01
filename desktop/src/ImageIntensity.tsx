import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type {
  Palette,
  Raster,
  AutoLevels,
  ImageDisplayPreferences,
} from "./types";
import { ColorMapPicker } from "./ColorMapPicker";
import { colorsFor } from "./colorMaps";

type WindowDrag = {
  kind: "min" | "max" | "window";
  start: number;
  min: number;
  max: number;
};
const compact = (value: number) =>
  value.toLocaleString("en-US", {
    notation: "compact",
    maximumSignificantDigits: 2,
  });

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
  display?: "detector" | "cake";
}) {
  const id = useId(),
    container = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 136, height: 300 });
  const small = preferences.size === "compact";
  const horizontal = preferences.orientation === "horizontal";
  const auto = preferences.auto;
  const setSmall = (small: boolean) =>
    onPreferences({ ...preferences, size: small ? "compact" : "large" });
  const setHorizontal = (horizontal: boolean) =>
    onPreferences({
      ...preferences,
      orientation: horizontal ? "horizontal" : "vertical",
    });
  const setAuto = (auto: AutoLevels) => onPreferences({ ...preferences, auto });
  const [dialog, setDialog] = useState<{ x: number; y: number } | null>(null);
  const previousSource = useRef(raster.data),
    drag = useRef<WindowDrag | null>(null);
  const label = (text: string) =>
    display === "cake" ? `Cake ${text[0].toLowerCase()}${text.slice(1)}` : text;
  const title = display === "cake" ? "Cake" : "Detector";
  const open = (x: number, y: number) => setDialog({ x, y });
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
    if (previousSource.current === raster.data) return;
    previousSource.current = raster.data;
    const timer = setTimeout(() => onAuto(auto), 0);
    return () => clearTimeout(timer);
  }, [raster.data]);
  useEffect(() => {
    if (!dialog) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setDialog(null);
      }
    };
    document.addEventListener("keydown", escape, true);
    return () => document.removeEventListener("keydown", escape, true);
  }, [dialog]);
  const updateAuto = (change: Partial<AutoLevels>) => {
    const next = { ...auto, ...change };
    setAuto(next);
    onAuto(next);
  };
  const edges = raster.histogram?.edges ?? [0, Math.max(1, raster.limits[1])],
    counts = raster.histogram?.counts ?? [0];
  const min = Math.asinh(edges[0]),
    max = Math.asinh(edges.at(-1)!),
    span = Math.max(1e-9, max - min),
    gap = span / 1000;
  const length = Math.max(40, horizontal ? size.width : size.height),
    plotLength = length - 32;
  const offset = small ? 38 : 0,
    thickness = small ? 92 : 136;
  const y = (value: number) =>
    16 + (1 - (Math.asinh(value) - min) / span) * plotLength;
  const upper = Math.max(16, Math.min(length - 16, y(limits[1]))),
    lower = Math.max(16, Math.min(length - 16, y(limits[0])));
  const peak = Math.max(1, ...counts.map((n) => Math.log1p(n)));
  const update = (low: number, high: number) => {
    if (Number.isFinite(low) && Number.isFinite(high) && low < high)
      onLimits([low, high]);
  };
  const coordinate = (event: React.PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const f = horizontal
      ? (event.clientX - box.left) / box.width
      : (event.clientY - box.top) / box.height;
    return Math.max(
      min,
      Math.min(
        max,
        min +
          (horizontal
            ? (f * length - 16) / plotLength
            : 1 - (f * length - 16) / plotLength) *
            span,
      ),
    );
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
      const shift = Math.max(
        min - current.min,
        Math.min(max - current.max, value - current.start),
      );
      update(Math.sinh(current.min + shift), Math.sinh(current.max + shift));
    }
  };
  return (
    <>
      <aside
        className="image-intensity"
        data-size={small ? "compact" : "expanded"}
        data-orientation={horizontal ? "horizontal" : "vertical"}
        aria-label={`${title} intensity controls`}
        onContextMenu={(event) => {
          event.preventDefault();
          event.stopPropagation();
          open(event.clientX, event.clientY);
        }}
      >
        <div className="histogram-container" ref={container}>
          <svg
            className="intensity-histogram"
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
            onDoubleClick={(event) => open(event.clientX, event.clientY)}
            onPointerDown={(event) => {
              const box = event.currentTarget.getBoundingClientRect();
              const cross = horizontal
                ? (small ? 130 : 136) -
                  ((event.clientY - box.top) / box.height) * thickness
                : ((event.clientX - box.left) / box.width) * thickness + offset;
              if (cross < 39 || cross > 106) return;
              const value = coordinate(event),
                a = Math.asinh(limits[0]),
                b = Math.asinh(limits[1]),
                near = (span * 12) / plotLength;
              const kind =
                Math.abs(value - a) < near
                  ? "min"
                  : Math.abs(value - b) < near
                    ? "max"
                    : value > a && value < b
                      ? "window"
                      : Math.abs(value - a) < Math.abs(value - b)
                        ? "min"
                        : "max";
              drag.current = { kind, start: value, min: a, max: b };
              event.currentTarget.setPointerCapture(event.pointerId);
              if (kind !== "window") move(value, drag.current);
              event.preventDefault();
            }}
            onPointerMove={(event) => {
              if (drag.current) move(coordinate(event), drag.current);
            }}
            onPointerUp={(event) => {
              drag.current = null;
              if (event.currentTarget.hasPointerCapture(event.pointerId))
                event.currentTarget.releasePointerCapture(event.pointerId);
            }}
            onPointerCancel={() => {
              drag.current = null;
            }}
          >
            <title>{`${title} intensity. Drag the window or handles. Click the colour scale, double-click or right-click for display settings.`}</title>
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
                  ? `matrix(0,-1,-1,0,${length},${small ? 130 : 136})`
                  : undefined
              }
            >
              <rect
                data-testid="intensity-selected-window"
                x="42"
                y={upper}
                width="62"
                height={Math.max(0, lower - upper)}
                fill="#edbc801a"
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
                    width={(Math.log1p(count) / peak) * 62}
                    height={Math.max(0.6, bottom - top)}
                    fill="#829ba8"
                    fillOpacity=".8"
                  />
                );
              })}
              <rect
                data-testid="intensity-colour-bar"
                x="111"
                y="16"
                width="11"
                height={plotLength}
                fill={`url(#${id}-ramp)`}
                role="button"
                tabIndex={0}
                aria-label={`Configure ${display} display`}
                onClick={(event) => {
                  event.stopPropagation();
                  open(event.clientX, event.clientY);
                }}
                onKeyDown={(event) => {
                  if (["Enter", " "].includes(event.key)) {
                    event.preventDefault();
                    const box = event.currentTarget.getBoundingClientRect();
                    open(box.left, box.bottom);
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
                  role="slider"
                  tabIndex={0}
                  aria-label={label(
                    kind === "min"
                      ? "Lower intensity handle"
                      : "Upper intensity handle",
                  )}
                  aria-orientation={horizontal ? "horizontal" : "vertical"}
                  aria-valuemin={edges[0]}
                  aria-valuemax={edges.at(-1)}
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
                    move(
                      Math.max(
                        min,
                        Math.min(
                          max,
                          Math.asinh(value) + (direction * span) / 100,
                        ),
                      ),
                      { kind, start: 0, min: 0, max: 0 },
                    );
                  }}
                >
                  <title>{value.toLocaleString()}</title>
                  <rect
                    x="39"
                    y={position - 9}
                    width="66"
                    height="18"
                    fill="transparent"
                  />
                  <path
                    d={`M42 ${position}H104`}
                    stroke="#10151b"
                    strokeWidth="5"
                  />
                  <path
                    d={`M42 ${position}H104`}
                    stroke="#edbc80"
                    strokeWidth="2"
                  />
                  <path
                    d={`M104 ${position - 5} 98 ${position} 104 ${position + 5}Z`}
                    fill="#edbc80"
                  />
                </g>
              ))}
            </g>
            {!small &&
              [0, 0.25, 0.5, 0.75, 1].map((f) => (
                <text
                  key={f}
                  x={horizontal ? 16 + f * plotLength : 36}
                  y={horizontal ? 124 : 20 + f * (plotLength - 4)}
                  textAnchor={horizontal ? "middle" : "end"}
                  fill="#a7b5c0"
                  fontSize="13"
                >
                  {compact(
                    Math.sinh(horizontal ? min + f * span : max - f * span),
                  )}
                </text>
              ))}
          </svg>
        </div>
        <div className="intensity-basic-controls">
          <button
            aria-label={label("Auto intensity")}
            disabled={!ready}
            title="Apply auto levels. Click the colour bar or right-click for settings."
            onClick={() => onAuto(auto)}
          >
            Auto
          </button>
          <ColorMapPicker
            label={label("Color map")}
            value={palette}
            onChange={onPalette}
          />
        </div>
      </aside>
      {dialog &&
        createPortal(
          <div
            className="display-settings-backdrop"
            onPointerDown={() => setDialog(null)}
          >
            <section
              role="dialog"
              aria-modal="true"
              aria-label={`${title} display settings`}
              className="display-settings"
              style={{
                left: Math.max(8, Math.min(dialog.x, window.innerWidth - 316)),
                top: Math.max(8, Math.min(dialog.y, window.innerHeight - 530)),
              }}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <div className="display-settings-heading">
                <h2>{title} display</h2>
                <button
                  aria-label={`Close ${display} display settings`}
                  onClick={() => setDialog(null)}
                >
                  ×
                </button>
              </div>
              <label>
                Scale
                <select
                  aria-label={label("Image scale")}
                  value={log ? "log" : "linear"}
                  onChange={(event) => onLog(event.target.value === "log")}
                >
                  <option value="linear">Linear</option>
                  <option value="log">Logarithmic</option>
                </select>
              </label>
              <label>
                Auto mode
                <select
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
                  <option value="mean3std">Mean ± 3 Std</option>
                </select>
              </label>
              {auto.mode === "percentile" && (
                <label>
                  Clip each tail · %
                  <input
                    aria-label={label("Clipping percentile")}
                    type="number"
                    min="0.01"
                    max="25"
                    step=".01"
                    value={auto.percentile}
                    disabled={!ready}
                    onChange={(event) =>
                      setAuto({
                        ...auto,
                        percentile: Number(event.target.value),
                      })
                    }
                    onBlur={() => onAuto(auto)}
                  />
                </label>
              )}
              <label className="display-settings-check">
                <input
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
              <label>
                Minimum
                <input
                  aria-label={label("Minimum intensity")}
                  type="number"
                  step="any"
                  value={Number(limits[0].toPrecision(7))}
                  onChange={(event) =>
                    update(Number(event.target.value), limits[1])
                  }
                />
              </label>
              <label>
                Maximum
                <input
                  aria-label={label("Maximum intensity")}
                  type="number"
                  step="any"
                  value={Number(limits[1].toPrecision(7))}
                  onChange={(event) =>
                    update(limits[0], Number(event.target.value))
                  }
                />
              </label>
              <label>
                Bar layout
                <select
                  aria-label={label("Histogram orientation")}
                  value={horizontal ? "horizontal" : "vertical"}
                  onChange={(event) =>
                    setHorizontal(event.target.value === "horizontal")
                  }
                >
                  <option value="vertical">Vertical · right of image</option>
                  <option value="horizontal">Horizontal · above image</option>
                </select>
              </label>
              <label>
                Bar size
                <select
                  aria-label={label("Histogram size")}
                  value={small ? "compact" : "large"}
                  onChange={(event) =>
                    setSmall(event.target.value === "compact")
                  }
                >
                  <option value="compact">Compact</option>
                  <option value="large">Large</option>
                </select>
              </label>
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}

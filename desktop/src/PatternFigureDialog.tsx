import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Dialog, DialogHeader, Input, Select } from "./ui";
import { TabList } from "./TabList";
import type { IntegrationRun } from "./integration";
import type { Response } from "./types";
import {
  defaultPatternFigureSettings,
  patternFigurePng,
  patternFigurePresets,
  rememberPatternFigure,
  renderPatternFigure,
  restorePatternFigure,
  type CurveStyle,
  type PatternFigureOptions,
  type PatternFigureSource,
  type PhaseStyle,
} from "./patternFigure";
import "./patternFigure.css";

export function PatternFigureDialog({
  source,
  initialPath,
  run,
  onClose,
}: {
  source: PatternFigureSource;
  initialPath: string | null;
  run: IntegrationRun;
  onClose: () => void;
}) {
  const initialFormat = initialPath
    ? /\.png$/i.test(initialPath)
      ? "png"
      : "svg"
    : undefined;
  const [settings, setSettings] = useState(() =>
    restorePatternFigure(source, initialFormat),
  );
  const [section, setSection] = useState("layout"),
    [magnify, setMagnify] = useState(false);
  const [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [saveError, setSaveError] = useState("");
  const [savedPath, setSavedPath] = useState(initialPath ?? "");
  const trigger = useRef<HTMLElement | null>(
    document.querySelector('[aria-label="Save pattern"]'),
  );
  const o = settings.options;
  const preview = useMemo(() => {
    try {
      return { svg: renderPatternFigure(source, o), error: "" };
    } catch (e) {
      return { svg: "", error: e instanceof Error ? e.message : String(e) };
    }
  }, [source, o]);
  useEffect(() => {
    if (preview.svg) rememberPatternFigure(source, settings);
  }, [source, settings, preview.svg]);
  const close = () => {
    if (!busy) {
      onClose();
      requestAnimationFrame(() =>
        trigger.current?.focus({ preventScroll: true }),
      );
    }
  };
  const change = <K extends keyof PatternFigureOptions>(
    key: K,
    value: PatternFigureOptions[K],
  ) => {
    setSettings((s) => ({ ...s, options: { ...s.options, [key]: value } }));
    setNotice("");
    setSaveError("");
  };
  const curveChange = (id: string, values: Partial<CurveStyle>) =>
    change(
      "curves",
      o.curves.map((c) => (c.id === id ? { ...c, ...values } : c)),
    );
  const phaseChange = (id: string, values: Partial<PhaseStyle>) =>
    change(
      "phaseStyles",
      o.phaseStyles.map((p) => (p.id === id ? { ...p, ...values } : p)),
    );
  const field = (
    label: string,
    key: "width" | "height" | "fontSize" | "xMin" | "xMax" | "yMin" | "yMax",
    min?: number,
    max?: number,
  ) => (
    <label>
      {label}
      <Input
        aria-label={`Figure ${label.toLowerCase()}`}
        type="number"
        step="any"
        min={min}
        max={max}
        value={Number.isFinite(o[key]) ? o[key] : ""}
        onChange={(e) => change(key, e.target.valueAsNumber)}
      />
    </label>
  );
  const textField = (label: string, key: "title" | "xLabel" | "yLabel") => (
    <label>
      {label}
      <Input
        aria-label={`Figure ${label.toLowerCase()}`}
        value={o[key]}
        maxLength={240}
        onChange={(e) => change(key, e.target.value)}
      />
    </label>
  );
  const check = (label: string, key: "grid" | "box" | "yTicks") => (
    <label className="pattern-figure-check">
      <Input
        aria-label={label}
        type="checkbox"
        checked={o[key]}
        onChange={(e) => change(key, e.target.checked)}
      />
      {label}
    </label>
  );
  const appearance = (theme: PatternFigureOptions["theme"]) => {
    const dark = theme === "dark";
    change("theme", theme);
    setSettings((s) => ({
      ...s,
      options: {
        ...s.options,
        theme,
        curves: s.options.curves.map((c) => ({
          ...c,
          color:
            dark && /^#(?:202124|000000)$/i.test(c.color)
              ? "#ffffff"
              : !dark && /^#ffffff$/i.test(c.color)
                ? "#202124"
                : c.color,
        })),
      },
    }));
  };
  async function save(choose = false) {
    if (busy || !preview.svg) return;
    setBusy(true);
    setSaveError("");
    setNotice("");
    try {
      const payload =
        settings.format === "png"
          ? {
              png_dpi: settings.dpi,
              png_data: await patternFigurePng(
                preview.svg,
                o.width,
                o.height,
                settings.dpi,
              ),
            }
          : { svg_data: preview.svg };
      const extensionMatches = savedPath
        .toLowerCase()
        .endsWith(`.${settings.format}`);
      const basename =
        savedPath
          .split(/[\\/]/)
          .at(-1)
          ?.replace(/\.[^.]+$/, "") ||
        source.curves[0]?.name
          .split(/[\\/]/)
          .at(-1)
          ?.replace(/\.[^.]+$/, "")
          .replace(/[<>:"|?*]/g, "_") ||
        "pattern";
      const directory = savedPath.slice(
        0,
        savedPath.length - (savedPath.split(/[\\/]/).at(-1)?.length ?? 0),
      );
      let result: Response | undefined;
      await run(
        "integration_save_pattern",
        {
          ...payload,
          format: settings.format,
          suggested_name: `${basename}.${settings.format}`,
          ...(directory ? { directory } : {}),
          ...(!choose && extensionMatches ? { path: savedPath } : {}),
        },
        "Saving pattern figure…",
        (r) => {
          result = r;
        },
      );
      if (!result)
        throw Error(
          "The figure could not be saved. Check the destination and try again.",
        );
      if (result.cancelled) setNotice("Save canceled; figure settings kept.");
      else if (result.savedPath) {
        setSavedPath(result.savedPath);
        setNotice(
          `Saved ${result.savedPath.split(/[\\/]/).at(-1) || "Choose a destination when saving"}`,
        );
      } else throw Error(result.error || "The figure could not be saved.");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open
      onDismiss={close}
      className="pattern-figure-dialog"
      aria-labelledby="pattern-figure-title"
      onKeyDown={(e) => e.stopPropagation()}
    >
      <DialogHeader
        headingId="pattern-figure-title"
        title="Export pattern figure"
        closeLabel="Close figure editor"
        onClose={close}
      />
      <div className="pattern-figure-body">
        <div className="pattern-figure-preview-area">
          <div className="pattern-figure-preview-meta">
            <span>
              Live preview · {o.width || "—"} × {o.height || "—"} mm
            </span>
            <Button
              type="button"
              aria-pressed={magnify}
              onClick={() => setMagnify((v) => !v)}
            >
              Actual-size preview
            </Button>
          </div>
          <div
            className={`pattern-figure-paper ${magnify ? "magnified" : ""}`}
            role="region"
            aria-label="Pattern figure preview"
            tabIndex={magnify ? 0 : undefined}
          >
            {preview.svg ? (
              <div
                data-testid="pattern-figure-artwork"
                dangerouslySetInnerHTML={{ __html: preview.svg }}
              />
            ) : (
              <p role="alert">{preview.error}</p>
            )}
          </div>
          <p className="pattern-figure-caption">
            Figure settings are remembered on this computer. Data and phase
            positions stay unchanged.
          </p>
        </div>
        <fieldset className="pattern-figure-controls" disabled={busy}>
          <TabList
            label="Figure editor sections"
            value={section}
            onChange={setSection}
            options={[
              { value: "layout", label: "Layout" },
              { value: "axes", label: "Axes" },
              { value: "curves", label: "Curves" },
              { value: "phases", label: "Phases" },
            ]}
          />
          <div
            className="pattern-figure-control-scroll"
            role="tabpanel"
            aria-label={`Figure ${section}`}
          >
            {section === "layout" && (
              <>
                <div className="pattern-figure-section-heading">
                  <h3>Figure & layout</h3>
                  <Button
                    type="button"
                    aria-label="Reset figure settings"
                    onClick={() => {
                      setSettings(
                        defaultPatternFigureSettings(
                          source,
                          initialFormat ?? "svg",
                        ),
                      );
                      setNotice("Figure settings reset.");
                      setSaveError("");
                    }}
                  >
                    Reset
                  </Button>
                </div>
                <label>
                  Figure size
                  <Select
                    aria-label="Figure size preset"
                    value={
                      ["90x80", "180x115", "240x135"].includes(
                        `${o.width}x${o.height}`,
                      )
                        ? `${o.width}x${o.height}`
                        : "custom"
                    }
                    onChange={(e) => {
                      const preset =
                        patternFigurePresets[
                          e.target.value as keyof typeof patternFigurePresets
                        ];
                      if (preset) {
                        setSettings((s) => ({
                          ...s,
                          options: { ...s.options, ...preset },
                        }));
                        setNotice("");
                        setSaveError("");
                      }
                    }}
                  >
                    <option value="90x80">Journal · Single column</option>
                    <option value="180x115">Journal · Double column</option>
                    <option value="240x135">Presentation · Widescreen</option>
                    <option value="custom">Custom</option>
                  </Select>
                </label>
                <div className="pattern-figure-pair">
                  {field("Width (mm)", "width", 50, 400)}
                  {field("Height (mm)", "height", 45, 400)}
                </div>
                <p className="pattern-figure-caption">
                  Presets include print typography: 8 pt for single column, 10
                  pt for double column, and 14 pt for presentations.
                </p>
                {textField("Title", "title")}
                <div className="pattern-figure-pair">
                  <label>
                    Font
                    <Select
                      aria-label="Figure font"
                      value={o.font}
                      onChange={(e) =>
                        change(
                          "font",
                          e.target.value as PatternFigureOptions["font"],
                        )
                      }
                    >
                      {["Arial", "Helvetica", "Times New Roman"].map((font) => (
                        <option key={font}>{font}</option>
                      ))}
                    </Select>
                  </label>
                  {field("Font size (pt)", "fontSize", 6, 24)}
                </div>
                <label>
                  Background
                  <Select
                    aria-label="Figure background"
                    value={o.theme}
                    onChange={(e) =>
                      appearance(
                        e.target.value as PatternFigureOptions["theme"],
                      )
                    }
                  >
                    <option value="white">White paper</option>
                    <option value="transparent">Transparent</option>
                    <option value="dark">Dark</option>
                  </Select>
                </label>
                <label>
                  Curve legend
                  <Select
                    aria-label="Curve legend position"
                    value={o.legend}
                    onChange={(e) =>
                      change(
                        "legend",
                        e.target.value as PatternFigureOptions["legend"],
                      )
                    }
                  >
                    {[
                      ["auto", "Auto · Open space or below plot"],
                      ["top-left", "Inside · Upper left"],
                      ["top-right", "Inside · Upper right"],
                      ["bottom-left", "Inside · Lower left"],
                      ["bottom-right", "Inside · Lower right"],
                      ["above", "Above plot"],
                      ["below", "Below plot"],
                      ["right", "To the right"],
                      ["none", "Hidden"],
                    ].map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </label>
              </>
            )}
            {section === "axes" && (
              <>
                <h3>Axes & ranges</h3>
                {textField("Horizontal label", "xLabel")}
                {textField("Intensity label", "yLabel")}
                <label>
                  Horizontal range
                  <Select
                    aria-label="Figure horizontal range"
                    value={o.range}
                    onChange={(e) =>
                      change(
                        "range",
                        e.target.value as PatternFigureOptions["range"],
                      )
                    }
                  >
                    <option value="view">Current displayed range</option>
                    <option value="full">Full visible curves</option>
                    <option value="custom">Custom limits</option>
                  </Select>
                </label>
                {o.range === "custom" && (
                  <div className="pattern-figure-pair">
                    {field("Horizontal minimum", "xMin")}
                    {field("Horizontal maximum", "xMax")}
                  </div>
                )}
                <div className="pattern-figure-pair">
                  <label>
                    Intensity scale
                    <Select
                      aria-label="Figure intensity scale"
                      value={o.scale}
                      onChange={(e) => {
                        change(
                          "scale",
                          e.target.value as PatternFigureOptions["scale"],
                        );
                        if (
                          o.yRange === "view" &&
                          e.target.value !== source.scale
                        )
                          change("yRange", "auto");
                      }}
                    >
                      <option value="linear">Linear</option>
                      <option value="log">Logarithmic</option>
                      <option value="sqrt">Square root</option>
                    </Select>
                  </label>
                  <label>
                    Intensity range
                    <Select
                      aria-label="Figure intensity range"
                      value={o.yRange}
                      onChange={(e) =>
                        change(
                          "yRange",
                          e.target.value as PatternFigureOptions["yRange"],
                        )
                      }
                    >
                      <option value="view">Current displayed limits</option>
                      <option value="auto">Fit selected curves</option>
                      <option value="custom">Custom limits</option>
                    </Select>
                  </label>
                </div>
                {o.yRange === "custom" && (
                  <div className="pattern-figure-pair">
                    {field("Intensity minimum", "yMin")}
                    {field("Intensity maximum", "yMax")}
                  </div>
                )}
                <p className="pattern-figure-caption">
                  Intensity limits are in the original intensity units,
                  including for log and √ axes.
                </p>
                <label>
                  Tick direction
                  <Select
                    aria-label="Figure tick direction"
                    value={o.tickDirection}
                    onChange={(e) =>
                      change("tickDirection", e.target.value as "in" | "out")
                    }
                  >
                    <option value="in">Inside</option>
                    <option value="out">Outside</option>
                  </Select>
                </label>
                {check("Show intensity tick labels", "yTicks")}
                {check("Box around axes", "box")}
                {check("Show grid", "grid")}
              </>
            )}
            {section === "curves" && (
              <>
                <h3>Curves & colors</h3>
                <p className="pattern-figure-caption">
                  First drawn sits behind later curves. These changes affect
                  only this figure.
                </p>
                {o.curves.map((c, i) => (
                  <div className="pattern-figure-curve" key={c.id}>
                    <div className="pattern-figure-entry">
                      <Input
                        type="checkbox"
                        aria-label={`Show figure curve ${i + 1}`}
                        checked={c.visible}
                        onChange={(e) =>
                          curveChange(c.id, { visible: e.target.checked })
                        }
                      />
                      <Input
                        type="color"
                        aria-label={`Figure curve ${i + 1} color`}
                        value={c.color}
                        onChange={(e) =>
                          curveChange(c.id, { color: e.target.value })
                        }
                      />
                      <Input
                        aria-label={`Figure curve ${i + 1} label`}
                        value={c.label}
                        maxLength={240}
                        onChange={(e) =>
                          curveChange(c.id, { label: e.target.value })
                        }
                      />
                    </div>
                    <div className="pattern-figure-pair">
                      <label>
                        Appearance
                        <Select
                          aria-label={`Figure curve ${i + 1} style`}
                          value={c.style}
                          onChange={(e) =>
                            curveChange(c.id, {
                              style: e.target.value as CurveStyle["style"],
                            })
                          }
                        >
                          <option value="line">Line</option>
                          <option value="dash">Dashed line</option>
                          <option value="points">Points</option>
                          <option value="both">Line + points</option>
                        </Select>
                      </label>
                      <label>
                        Width (pt)
                        <Input
                          aria-label={`Figure curve ${i + 1} width`}
                          type="number"
                          min={0.2}
                          max={5}
                          step={0.1}
                          value={Number.isFinite(c.width) ? c.width : ""}
                          onChange={(e) =>
                            curveChange(c.id, { width: e.target.valueAsNumber })
                          }
                        />
                      </label>
                    </div>
                    <div className="pattern-figure-order">
                      <Button
                        type="button"
                        disabled={!i}
                        aria-label={`Move figure curve ${i + 1} earlier`}
                        onClick={() => {
                          const values = [...o.curves];
                          [values[i - 1], values[i]] = [
                            values[i],
                            values[i - 1],
                          ];
                          change("curves", values);
                        }}
                      >
                        ↑ Earlier
                      </Button>
                      <Button
                        type="button"
                        disabled={i === o.curves.length - 1}
                        aria-label={`Move figure curve ${i + 1} later`}
                        onClick={() => {
                          const values = [...o.curves];
                          [values[i + 1], values[i]] = [
                            values[i],
                            values[i + 1],
                          ];
                          change("curves", values);
                        }}
                      >
                        ↓ Later
                      </Button>
                    </div>
                  </div>
                ))}
              </>
            )}
            {section === "phases" && (
              <>
                <h3>Phase references</h3>
                <label>
                  Reference sticks
                  <Select
                    aria-label="Figure phase placement"
                    value={o.phases}
                    onChange={(e) => {
                      const phases = e.target
                        .value as PatternFigureOptions["phases"];
                      setSettings((s) => ({
                        ...s,
                        options: {
                          ...s.options,
                          phases,
                          phaseLegend:
                            phases === "plot" &&
                            s.options.phaseLegend === "rows"
                              ? "auto"
                              : s.options.phaseLegend,
                        },
                      }));
                      setNotice("");
                      setSaveError("");
                    }}
                    disabled={!o.phaseStyles.length}
                  >
                    <option value="rows">Separate rows below pattern</option>
                    <option value="plot">Inside pattern axes</option>
                    <option value="none">Hidden</option>
                  </Select>
                </label>
                <label>
                  Phase labels
                  <Select
                    aria-label="Figure phase legend"
                    value={o.phaseLegend}
                    disabled={!o.phaseStyles.length || o.phases === "none"}
                    onChange={(e) =>
                      change(
                        "phaseLegend",
                        e.target.value as PatternFigureOptions["phaseLegend"],
                      )
                    }
                  >
                    <option value="rows" disabled={o.phases !== "rows"}>
                      Beside each reference row
                    </option>
                    <option value="auto">
                      Separate legend · Auto placement
                    </option>
                    <option value="top-left">
                      Separate legend · Upper left
                    </option>
                    <option value="top-right">
                      Separate legend · Upper right
                    </option>
                    <option value="bottom-left">
                      Separate legend · Lower left
                    </option>
                    <option value="bottom-right">
                      Separate legend · Lower right
                    </option>
                    <option value="above">Separate legend · Above plot</option>
                    <option value="below">Separate legend · Below plot</option>
                    <option value="right">
                      Separate legend · To the right
                    </option>
                    <option value="none">Hidden</option>
                  </Select>
                </label>
                <label>
                  Tick thickness
                  <Select
                    aria-label="Figure phase tick thickness"
                    value={o.phaseTickWeight}
                    disabled={o.phases !== "rows"}
                    onChange={(e) =>
                      change(
                        "phaseTickWeight",
                        e.target
                          .value as PatternFigureOptions["phaseTickWeight"],
                      )
                    }
                  >
                    <option value="intensity">
                      Relative reflection intensity
                    </option>
                    <option value="uniform">Uniform</option>
                  </Select>
                </label>
                {!o.phaseStyles.length && (
                  <p>No visible phase references in the source plot.</p>
                )}
                <p className="pattern-figure-caption">
                  Each phase has its own row below the patterns, aligned to the
                  same horizontal axis. Ticks have equal height; their thickness
                  can show relative reflection intensity. Phase legends stay
                  separate from the curve legend.
                </p>
                {o.phaseStyles.map((p, i) => (
                  <div className="pattern-figure-entry" key={p.id}>
                    <Input
                      type="checkbox"
                      aria-label={`Show figure phase ${i + 1}`}
                      checked={p.visible}
                      onChange={(e) =>
                        phaseChange(p.id, { visible: e.target.checked })
                      }
                    />
                    <Input
                      type="color"
                      aria-label={`Figure phase ${i + 1} color`}
                      value={p.color}
                      onChange={(e) =>
                        phaseChange(p.id, { color: e.target.value })
                      }
                    />
                    <Input
                      aria-label={`Figure phase ${i + 1} label`}
                      value={p.label}
                      maxLength={240}
                      onChange={(e) =>
                        phaseChange(p.id, { label: e.target.value })
                      }
                    />
                  </div>
                ))}
              </>
            )}
          </div>
        </fieldset>
      </div>
      <footer className="pattern-figure-footer">
        <div className="pattern-figure-file-controls">
          <label>
            Format
            <Select
              aria-label="Figure file format"
              value={settings.format}
              disabled={busy}
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  format: e.target.value as "png" | "svg",
                }))
              }
            >
              <option value="svg">SVG · Editable vector</option>
              <option value="png">PNG · Image</option>
            </Select>
          </label>
          {settings.format === "png" && (
            <label>
              Resolution
              <Select
                aria-label="Figure PNG resolution"
                disabled={busy}
                value={settings.dpi}
                onChange={(e) =>
                  setSettings((s) => ({ ...s, dpi: Number(e.target.value) }))
                }
              >
                {[150, 300, 600].map((dpi) => (
                  <option key={dpi} value={dpi}>
                    {dpi} dpi
                  </option>
                ))}
              </Select>
            </label>
          )}
          <span className="pattern-figure-caption">
            {settings.format === "png"
              ? `${Math.round((o.width / 25.4) * settings.dpi)} × ${Math.round((o.height / 25.4) * settings.dpi)} pixels`
              : "Vector curves, references and text"}
          </span>
        </div>
        <div className="pattern-figure-save">
          <span
            role={saveError ? "alert" : "status"}
            title={saveError || notice || savedPath}
          >
            {saveError ||
              notice ||
              savedPath.split(/[\\/]/).at(-1) ||
              "Choose a destination when saving"}
          </span>
          <Button
            type="button"
            disabled={busy || !preview.svg}
            onClick={() => void save(true)}
          >
            Save as…
          </Button>
          <Button
            variant="primary"
            type="button"
            disabled={busy || !preview.svg}
            onClick={() => void save()}
          >
            {busy ? "Saving…" : "Save figure"}
          </Button>
        </div>
      </footer>
    </Dialog>
  );
}

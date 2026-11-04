import { useEffect, useState, useRef, type CSSProperties } from "react";
import { Plus, Trash2 } from "lucide-react";
import { DataTable, TableActions, TableScroll } from "./DataTable";
import { unitLabel, type Unit } from "./types";
import { radialValues } from "./radialReadout";
import type { MapData, MapRun } from "./mapDomain";
function Cell({
  value,
  label,
  numeric = false,
  disabled,
  commit,
  cancel,
}: {
  value: string | number;
  label: string;
  numeric?: boolean;
  disabled: boolean;
  commit: (value: string) => void;
  cancel?: () => void;
}) {
  const shown =
    numeric && typeof value === "number"
      ? Number(value.toPrecision(6)).toString()
      : String(value);
  const [draft, setDraft] = useState(shown);
  const dirty = useRef(false);
  const apply = () => {
    if (!dirty.current) return;
    const next = draft.trim();
    if (
      next !== String(value) &&
      next !== shown &&
      next &&
      (!numeric || Number.isFinite(Number(next)))
    )
      commit(next);
    dirty.current = false;
    setDraft(shown);
  };
  return (
    <input
      aria-label={label}
      type={numeric ? "number" : "text"}
      step={numeric ? "any" : undefined}
      disabled={disabled}
      value={dirty.current ? draft : shown}
      spellCheck={false}
      title={String(value)}
      onChange={(e) => {
        dirty.current = true;
        setDraft(e.target.value);
      }}
      onBlur={apply}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          apply();
        }
        if (e.key === "Escape") {
          e.preventDefault();
          dirty.current = false;
          cancel?.();
          setDraft(shown);
        }
      }}
    />
  );
}
export function MapLayers({
  map,
  ready,
  run,
  unit,
  wavelength,
}: {
  unit: Unit;
  wavelength?: number;
  map: MapData;
  ready: boolean;
  run: MapRun;
}) {
  const latest = useRef({ map, run });
  latest.current = { map, run };
  const tail = useRef<Promise<void>>(Promise.resolve());
  const [pending, setPending] = useState(0);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const canEdit = ready || pending > 0;
  type RangeDraft = { min?: number; max?: number; version: number };
  const rangeDrafts = useRef<Record<string, RangeDraft>>({});
  const rangeVersion = useRef(0);
  const [, refreshRanges] = useState(0);
  const rangeKey = (index: number, coordinate = unit) =>
    `${index}:${coordinate}`;
  const clearRange = (index: number) => {
    delete rangeDrafts.current[rangeKey(index)];
    setRangeError(null);
    refreshRanges((n) => n + 1);
  };
  useEffect(() => {
    rangeDrafts.current = {};
    setRangeError(null);
    refreshRanges((n) => n + 1);
  }, [unit, map.labels[0]]);
  type Edit = {
    command: string;
    args: Record<string, unknown>;
    after?: () => void;
  };
  const enqueue = (build: () => Edit | null) => {
    setPending((n) => n + 1);
    setRangeError(null);
    const task = tail.current
      .then(async () => {
        setRangeError(null);
        const edit = build();
        if (edit) await latest.current.run(edit.command, edit.args);
        // Let the parent's response update the source values before the next edit.
        await new Promise<void>((resolve) =>
          requestAnimationFrame(() => resolve()),
        );
        edit?.after?.();
      })
      .finally(() => setPending((n) => n - 1));
    tail.current = task.catch(() => {});
    return task;
  };
  const edit: MapRun = (command, args = {}) =>
    enqueue(() => ({ command, args }));
  const updateWindow = (index: number, changes: Record<string, unknown>) =>
    enqueue(() => {
      const roi = latest.current.map.rois[index];
      return roi
        ? { command: "map_roi", args: { name: roi.name, ...changes } }
        : null;
    });
  const rangeIn = (
    minimum: number,
    maximum: number,
    source: Unit,
    target: Unit,
  ): [number, number] | null => {
    const values = [minimum, maximum].map(
      (value) => radialValues(value, source, wavelength)[target],
    );
    return values.every((v): v is number => v != null && Number.isFinite(v))
      ? [Math.min(...values), Math.max(...values)]
      : null;
  };
  const updateRange = (index: number, edge: "min" | "max", value: number) => {
    const enteredUnit = unit;
    const key = rangeKey(index, enteredUnit);
    const snapshot = {
      ...rangeDrafts.current[key],
      [edge]: value,
      version: ++rangeVersion.current,
    };
    rangeDrafts.current[key] = snapshot;
    refreshRanges((n) => n + 1);
    return enqueue(() => {
      const source = latest.current.map,
        roi = source.rois[index];
      if (!roi) return null;
      const range = rangeIn(roi.min, roi.max, source.unit, enteredUnit);
      if (!range) {
        setRangeError("This window cannot be converted to the displayed unit.");
        return null;
      }
      range[0] = snapshot.min ?? range[0];
      range[1] = snapshot.max ?? range[1];
      if (!(range[0] < range[1])) {
        setRangeError("Window limits must be finite and increasing.");
        return null;
      }
      const stored = rangeIn(range[0], range[1], enteredUnit, source.unit);
      if (!stored) {
        setRangeError("This window cannot be converted to the stored unit.");
        return null;
      }
      return {
        command: "map_roi",
        args: { name: roi.name, minimum: stored[0], maximum: stored[1] },
        after: () => {
          if (rangeDrafts.current[key]?.version === snapshot.version) {
            delete rangeDrafts.current[key];
            refreshRanges((n) => n + 1);
          }
        },
      };
    });
  };
  const [selected, setSelected] = useState(map.rois[0]?.name ?? "");
  const [expressionSelection, setExpressionSelection] = useState("");
  const [name, setName] = useState("Ratio"),
    [expression, setExpression] = useState("A/B");
  useEffect(() => {
    if (map.rois.some((r) => r.name === map.active)) setSelected(map.active);
    else if (!map.rois.some((r) => r.name === selected))
      setSelected(map.rois[0]?.name ?? "");
  }, [map.active, map.rois.map((r) => r.name).join("\0")]);
  const show = (layer: string, color?: string) => (
    <input
      type="radio"
      name="map-visible-layer"
      aria-label={`Show map layer ${layer}`}
      checked={map.active === layer}
      disabled={!ready}
      style={color ? { accentColor: color } : undefined}
      onChange={() => void run("map_layer", { name: layer })}
    />
  );
  return (
    <div className="map-layers" aria-busy={pending > 0}>
      <div className="map-section-heading">
        <span>
          Pattern windows{" "}
          <small data-testid="map-window-unit">{unitLabel(unit)}</small>
        </span>
        <TableActions aria-label="Window actions">
          <button
            aria-label="Add window"
            title="Add a pattern window and map layer"
            disabled={!ready}
            onClick={() => run("map_roi", { op: "add" })}
          >
            <Plus size={16} />
          </button>
          <button
            aria-label="Remove window"
            title="Remove selected window"
            disabled={!ready || map.rois.length < 2 || !selected}
            onClick={() => run("map_roi", { op: "remove", name: selected })}
          >
            <Trash2 size={15} />
          </button>
        </TableActions>
      </div>
      {rangeError && (
        <p role="status" className="map-range-error">
          {rangeError}
        </p>
      )}
      <TableScroll className="map-window-scroll">
        <DataTable className="map-window-table" aria-label="Pattern windows">
          <colgroup>
            <col className="map-radio-col" />
            <col className="map-color-col" />
            <col className="map-name-col" />
            <col className="map-range-col" />
            <col className="map-range-col" />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th title="Layer shown on map" aria-label="Show" />
              <th aria-label="Color" />
              <th>Name</th>
              <th>From</th>
              <th>To</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {map.rois.map((roi, index) => {
              const range = rangeIn(roi.min, roi.max, map.unit, unit);
              const draft = rangeDrafts.current[rangeKey(index)];
              if (range && draft) {
                range[0] = draft.min ?? range[0];
                range[1] = draft.max ?? range[1];
              }
              return (
                <tr
                  key={index}
                  aria-selected={selected === roi.name}
                  style={{ "--roi-color": roi.color } as CSSProperties}
                  onClick={() => setSelected(roi.name)}
                >
                  <td>{show(roi.name, roi.color)}</td>
                  <td>
                    <input
                      type="color"
                      aria-label={`Window ${roi.name} color`}
                      title={`Color for window ${roi.name}`}
                      value={roi.color}
                      disabled={!canEdit}
                      onChange={(e) =>
                        updateWindow(index, { color: e.target.value })
                      }
                    />
                  </td>
                  <td>
                    <Cell
                      label={`Window ${roi.name} name`}
                      value={roi.name}
                      disabled={!canEdit}
                      commit={(new_name) => updateWindow(index, { new_name })}
                    />
                  </td>
                  <td>
                    <Cell
                      label={`Window ${roi.name} minimum`}
                      value={range?.[0] ?? ""}
                      cancel={() => clearRange(index)}
                      numeric
                      disabled={!canEdit}
                      commit={(minimum) =>
                        updateRange(index, "min", Number(minimum))
                      }
                    />
                  </td>
                  <td>
                    <Cell
                      label={`Window ${roi.name} maximum`}
                      value={range?.[1] ?? ""}
                      cancel={() => clearRange(index)}
                      numeric
                      disabled={!canEdit}
                      commit={(maximum) =>
                        updateRange(index, "max", Number(maximum))
                      }
                    />
                  </td>
                  <td>
                    <select
                      aria-label={`Window ${roi.name} value`}
                      disabled={!canEdit}
                      value={roi.reduction + (roi.background ? ":bkg" : "")}
                      onChange={(e) => {
                        const [reduction, bg] = e.target.value.split(":");
                        void updateWindow(index, {
                          reduction,
                          background: bg === "bkg",
                        });
                      }}
                    >
                      <option value="sum">Sum</option>
                      <option value="sum:bkg">Sum − bkg</option>
                      <option value="mean">Mean</option>
                      <option value="max">Maximum</option>
                      <option value="area">Peak area</option>
                      <option value="center">Peak position</option>
                      <option value="width">FWHM</option>
                      {roi.background && roi.reduction !== "sum" && (
                        <option value={`${roi.reduction}:bkg`}>
                          {roi.reduction} − bkg
                        </option>
                      )}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </DataTable>
      </TableScroll>
      <div className="map-section-heading">
        <span>Expression layers</span>
        <TableActions aria-label="Expression actions">
          <button
            aria-label="Remove expression"
            title="Remove selected expression"
            disabled={!ready || !map.expressions[expressionSelection]}
            onClick={() =>
              run("map_expression", { name: expressionSelection, remove: true })
            }
          >
            <Trash2 size={15} />
          </button>
        </TableActions>
      </div>
      <TableScroll className="map-expression-scroll">
        <DataTable
          className="map-expression-table"
          aria-label="Expression layers"
        >
          <colgroup>
            <col className="map-radio-col" />
            <col style={{ width: "26%" }} />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th aria-label="Show" />
              <th>Name</th>
              <th>Expression</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(map.expressions).map(([key, value]) => (
              <tr
                key={key}
                aria-selected={expressionSelection === key}
                onClick={() => setExpressionSelection(key)}
              >
                <td>{show(key)}</td>
                <td>
                  <Cell
                    label={`Layer ${key} name`}
                    value={key}
                    disabled={!canEdit}
                    commit={(new_name) =>
                      edit("map_expression", {
                        name: key,
                        new_name,
                        expression: value,
                      })
                    }
                  />
                </td>
                <td>
                  <Cell
                    label={`Layer ${key} expression`}
                    value={value}
                    disabled={!canEdit}
                    commit={(expression) =>
                      edit("map_expression", { name: key, expression })
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
        {!Object.keys(map.expressions).length && (
          <div className="map-table-empty">No expression layers</div>
        )}
      </TableScroll>
      <form
        className="map-expression-entry"
        onSubmit={(e) => {
          e.preventDefault();
          void run("map_expression", { name, expression });
        }}
      >
        <label>
          Name
          <input
            aria-label="Expression layer name"
            value={name}
            disabled={!canEdit}
            onChange={(e) => setName(e.target.value)}
            spellCheck={false}
          />
        </label>
        <label>
          Expression
          <input
            aria-label="Map expression"
            value={expression}
            disabled={!canEdit}
            onChange={(e) => setExpression(e.target.value)}
            spellCheck={false}
          />
        </label>
        <button
          aria-label="Apply expression"
          title="Add or update expression layer"
          disabled={!ready || !name.trim() || !expression.trim()}
        >
          <Plus size={16} />
        </button>
      </form>
    </div>
  );
}

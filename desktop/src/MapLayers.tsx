import { useEffect, useState, type CSSProperties } from "react";
import { Plus, Trash2 } from "lucide-react";
import { DataTable, TableActions, TableScroll } from "./DataTable";
import { unitLabel } from "./types";
import type { MapData, MapRun } from "./mapDomain";
function Cell({
  value,
  label,
  numeric = false,
  disabled,
  commit,
}: {
  value: string | number;
  label: string;
  numeric?: boolean;
  disabled: boolean;
  commit: (value: string) => void;
}) {
  const shown =
    numeric && typeof value === "number"
      ? Number(value.toPrecision(6)).toString()
      : String(value);
  const [draft, setDraft] = useState(shown);
  useEffect(() => setDraft(shown), [shown]);
  const apply = () => {
    const next = draft.trim();
    if (
      next !== String(value) &&
      next !== shown &&
      next &&
      (!numeric || Number.isFinite(Number(next)))
    )
      commit(next);
    setDraft(shown);
  };
  return (
    <input
      aria-label={label}
      type={numeric ? "number" : "text"}
      step={numeric ? "any" : undefined}
      disabled={disabled}
      value={draft}
      spellCheck={false}
      title={String(value)}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={apply}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.currentTarget.blur();
        }
        if (e.key === "Escape") {
          e.preventDefault();
          setDraft(String(value));
        }
      }}
    />
  );
}
export function MapLayers({
  map,
  ready,
  run,
}: {
  map: MapData;
  ready: boolean;
  run: MapRun;
}) {
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
    <div className="map-layers">
      <div className="map-section-heading">
        <span>
          Pattern windows <small>{unitLabel(map.unit)}</small>
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
            {map.rois.map((roi) => (
              <tr
                key={roi.name}
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
                    disabled={!ready}
                    onChange={(e) =>
                      run("map_roi", { name: roi.name, color: e.target.value })
                    }
                  />
                </td>
                <td>
                  <Cell
                    label={`Window ${roi.name} name`}
                    value={roi.name}
                    disabled={!ready}
                    commit={(new_name) =>
                      run("map_roi", { name: roi.name, new_name })
                    }
                  />
                </td>
                <td>
                  <Cell
                    label={`Window ${roi.name} minimum`}
                    value={roi.min}
                    numeric
                    disabled={!ready}
                    commit={(minimum) =>
                      run("map_roi", {
                        name: roi.name,
                        minimum: Number(minimum),
                      })
                    }
                  />
                </td>
                <td>
                  <Cell
                    label={`Window ${roi.name} maximum`}
                    value={roi.max}
                    numeric
                    disabled={!ready}
                    commit={(maximum) =>
                      run("map_roi", {
                        name: roi.name,
                        maximum: Number(maximum),
                      })
                    }
                  />
                </td>
                <td>
                  <select
                    aria-label={`Window ${roi.name} value`}
                    disabled={!ready}
                    value={roi.reduction + (roi.background ? ":bkg" : "")}
                    onChange={(e) => {
                      const [reduction, bg] = e.target.value.split(":");
                      void run("map_roi", {
                        name: roi.name,
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
            ))}
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
                    disabled={!ready}
                    commit={(new_name) =>
                      run("map_expression", {
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
                    disabled={!ready}
                    commit={(expression) =>
                      run("map_expression", { name: key, expression })
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
            disabled={!ready}
            onChange={(e) => setName(e.target.value)}
            spellCheck={false}
          />
        </label>
        <label>
          Expression
          <input
            aria-label="Map expression"
            value={expression}
            disabled={!ready}
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

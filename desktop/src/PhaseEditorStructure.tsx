import { useEffect, useState } from "react";
import { DataTable, TableScroll } from "./DataTable";
import { EditorNumber, TextEdit } from "./PhaseEditorFields";
import type { EditorData, EditorEdit as Edit } from "./phaseEditorTypes";

export function PhaseEditorStructure({
  data,
  locked,
  act,
}: {
  data: EditorData;
  locked: boolean;
  act: Edit;
}) {
  const [selected, setSelected] = useState<number[]>([]);
  const [group, setGroup] = useState(data.structure.spaceGroup);
  const [adding, setAdding] = useState(false);
  const [newSite, setNewSite] = useState({
    element: "",
    x: "0",
    y: "0",
    z: "0",
    occupancy: "1",
  });
  const [error, setError] = useState("");
  const structure = data.structure;
  useEffect(() => {
    setGroup(structure.spaceGroup);
  }, [structure.spaceGroup]);
  useEffect(() => {
    setSelected([]);
  }, [data.index, structure.sites.length]);
  const keys = [
    ...new Set([
      "label",
      "_label",
      "element",
      "x",
      "y",
      "z",
      "occupancy",
      "wyckoff",
      ...structure.sites.flatMap(Object.keys),
    ]),
  ].filter(
    (k) =>
      structure.sites.some((s) => k in s) ||
      ["element", "x", "y", "z", "occupancy"].includes(k),
  );
  if (!structure.spaceGroup && !structure.sites.length)
    return (
      <p className="pe-help">
        Reference peak table; no atomic structure is stored.
      </p>
    );
  const applyGroup = async () => {
    const value =
      structure.groups
        .find((g) => `${g.number} — ${g.symbol}` === group)
        ?.number.toString() || group;
    if (!(await act("editor_space_group", { value })))
      setGroup(structure.spaceGroup);
  };
  return (
    <div className="pe-structure">
      <h3>Atomic positions</h3>
      <div className="pe-space-group">
        <label>
          Space group
          <input
            aria-label="Space group"
            list="pe-space-groups"
            value={group}
            disabled={!data.editable || !structure.sites.length}
            onChange={(e) => setGroup(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void applyGroup();
              }
              if (e.key === "Escape") {
                e.preventDefault();
                e.stopPropagation();
                setGroup(structure.spaceGroup);
              }
            }}
          />
        </label>
        <datalist id="pe-space-groups">
          {structure.groups.map((g) => (
            <option key={g.number} value={`${g.number} — ${g.symbol}`} />
          ))}
        </datalist>
        <button
          disabled={
            locked ||
            !data.editable ||
            !structure.sites.length ||
            group === structure.spaceGroup
          }
          onClick={() => void applyGroup()}
        >
          Apply group
        </button>
      </div>
      <p className="pe-help">
        Search by symbol or number. Coordinates remain in the current basis and
        origin.
      </p>
      {structure.assumption && (
        <p className="pe-note">Assumed structure: {structure.assumption}</p>
      )}
      <p className="pe-composition" title={structure.compositionDetail}>
        {structure.modified ? "Edited structure · " : ""}
        {structure.formula || "Formula unavailable"} · Stored Z ={" "}
        {structure.storedZ ?? "unavailable"}
        <br />
        {structure.calculatedZ != null
          ? `Calculated Z = ${structure.calculatedZ.toPrecision(6)}`
          : structure.compositionStatus === "mismatch"
            ? "Formula mismatch · no common Z"
            : "Calculated Z unavailable"}
        {structure.calculatedZ != null &&
          structure.storedZ != null &&
          Math.abs(structure.calculatedZ - structure.storedZ) >
            1e-4 * structure.storedZ &&
          " · differs from stored Z"}
      </p>
      <details className="pe-record-details">
        <summary>Composition diagnostic</summary>
        <p>{structure.compositionDetail}</p>
      </details>
      <p className="pe-help">
        x, y, z are fractional coordinates. Site edits recalculate reflections;
        stored Z and EoS normalization are retained.
      </p>
      <TableScroll className="pe-sites-scroll">
        <DataTable aria-label="Atomic sites">
          <thead>
            <tr>
              <th>Select</th>
              {keys.map((key) => (
                <th key={key}>
                  {key === "u_iso_angstrom2"
                    ? "Uiso (Å²)"
                    : key.replace(/^_/, "")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody key={`${data.index}-${structure.sites.length}`}>
            {structure.sites.map((site, row) => (
              <tr key={row} aria-selected={selected.includes(row)}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Select atomic site ${row + 1}`}
                    checked={selected.includes(row)}
                    onChange={(e) =>
                      setSelected((s) =>
                        e.target.checked
                          ? [...s, row]
                          : s.filter((n) => n !== row),
                      )
                    }
                  />
                </td>
                {keys.map((key) => (
                  <td key={key}>
                    {key === "element" ? (
                      <TextEdit
                        label={`Site ${row + 1} element`}
                        value={String(site[key] ?? "")}
                        disabled={!data.editable}
                        onCommit={(value) =>
                          act("editor_site", {
                            action: "update",
                            row,
                            parameter: key,
                            value,
                          })
                        }
                      />
                    ) : [
                        "x",
                        "y",
                        "z",
                        "occupancy",
                        "u_iso_angstrom2",
                      ].includes(key) ? (
                      <EditorNumber
                        label={`Site ${row + 1} ${key}`}
                        value={site[key] == null ? null : Number(site[key])}
                        disabled={!data.editable}
                        min={
                          key === "occupancy" || key === "u_iso_angstrom2"
                            ? 0
                            : undefined
                        }
                        max={key === "occupancy" ? 1 : undefined}
                        onCommit={(value) =>
                          act("editor_site", {
                            action: "update",
                            row,
                            parameter: key,
                            value,
                          })
                        }
                      />
                    ) : (
                      <span title={String(site[key] ?? "")}>
                        {String(site[key] ?? "")}
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </DataTable>
      </TableScroll>
      <div className="pe-record-actions">
        <button
          disabled={locked || !data.editable || !structure.spaceGroup}
          onClick={() => setAdding(!adding)}
        >
          Add atomic site…
        </button>
        <button
          disabled={
            locked ||
            !data.editable ||
            !selected.length ||
            selected.length >= structure.sites.length
          }
          onClick={() => {
            void act("editor_site", { action: "remove", rows: selected });
            setSelected([]);
          }}
        >
          Remove selected sites
        </button>
      </div>
      {adding && (
        <form
          className="pe-new-site"
          onSubmit={(e) => {
            e.preventDefault();
            const site = {
              element: newSite.element,
              x: Number(newSite.x),
              y: Number(newSite.y),
              z: Number(newSite.z),
              occupancy: Number(newSite.occupancy),
            };
            if (
              !site.element.trim() ||
              [newSite.x, newSite.y, newSite.z, newSite.occupancy].some(
                (v) => !v.trim() || !Number.isFinite(Number(v)),
              ) ||
              site.occupancy < 0 ||
              site.occupancy > 1
            ) {
              setError(
                "Enter an element, finite coordinates and occupancy between 0 and 1.",
              );
              return;
            }
            void act("editor_site", { action: "add", site }).then((ok) => {
              if (ok) {
                setAdding(false);
                setError("");
              }
            });
          }}
        >
          <p>New site · fractional coordinates</p>
          <div>
            {Object.entries(newSite).map(([key, value]) => (
              <label key={key}>
                {key}
                <input
                  aria-label={`New site ${key}`}
                  autoFocus={key === "element"}
                  inputMode={key === "element" ? "text" : "decimal"}
                  value={value}
                  onChange={(e) =>
                    setNewSite((s) => ({ ...s, [key]: e.target.value }))
                  }
                />
              </label>
            ))}
          </div>
          {error && <p className="pe-edit-error">{error}</p>}
          <button type="button" onClick={() => setAdding(false)}>
            Cancel site
          </button>
          <button disabled={locked}>Add site</button>
        </form>
      )}
    </div>
  );
}

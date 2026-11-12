import { Button, Input } from "./ui";
import { useEffect, useState } from "react";
import { DataTable, TableScroll } from "./DataTable";
import { EditorNumber, TextEdit } from "./PhaseEditorFields";
import { PhaseElementPicker } from "./PhaseElementPicker";
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
  const [pickElement, setPickElement] = useState<number | "new" | null>(null);
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
      ["element", "x", "y", "z", "occupancy", "wyckoff"].includes(k),
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
          <span>
            Space group{" "}
            <output aria-label="Space group number">
              No. {structure.spaceGroupNumber ?? "—"}
            </output>
          </span>
          <Input
            aria-label="Space group"
            list="pe-space-groups"
            placeholder="Symbol or number"
            title="Coordinates remain in their current basis and origin"
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
        <Button
          disabled={
            locked ||
            !data.editable ||
            !structure.sites.length ||
            group === structure.spaceGroup
          }
          onClick={() => void applyGroup()}
        >
          Apply group
        </Button>
      </div>
      {structure.assumption && (
        <p className="pe-note">Assumed structure: {structure.assumption}</p>
      )}
      <TableScroll className="pe-sites-scroll">
        <DataTable aria-label="Atomic sites">
          <thead>
            <tr>
              <th aria-label="Site selection" />
              {keys.map((key) => (
                <th key={key}>
                  {key === "u_iso_angstrom2"
                    ? "Uiso (Å²)"
                    : key === "occupancy"
                      ? "Occ."
                      : key === "wyckoff"
                        ? "Site"
                        : key.replace(/^_/, "")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody key={`${data.index}-${structure.sites.length}`}>
            {structure.sites.map((site, row) => (
              <tr key={row} aria-selected={selected.includes(row)}>
                <td>
                  <Input
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
                      <span className="pe-site-element">
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
                        <Button
                          type="button"
                          disabled={locked || !data.editable}
                          aria-label={`Choose element for site ${row + 1}`}
                          onClick={() => setPickElement(row)}
                        >
                          …
                        </Button>
                      </span>
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
                    ) : key === "wyckoff" ? (
                      <span
                        title={
                          structure.siteWyckoff[row]?.detail ||
                          "Source Wyckoff label"
                        }
                      >
                        {structure.siteWyckoff[row]?.label || site[key] || "—"}
                      </span>
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
        <Button
          disabled={locked || !data.editable || !structure.spaceGroup}
          onClick={() => setAdding(!adding)}
        >
          Add atomic site…
        </Button>
        <Button
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
        </Button>
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
          <p>New site</p>
          <div>
            {Object.entries(newSite).map(([key, value]) => (
              <label key={key}>
                {key === "occupancy" ? "Occ." : key}
                <Input
                  aria-label={`New site ${key}`}
                  autoFocus={key === "element"}
                  inputMode={key === "element" ? "text" : "decimal"}
                  value={value}
                  onChange={(e) =>
                    setNewSite((s) => ({ ...s, [key]: e.target.value }))
                  }
                />
                {key === "element" && (
                  <Button
                    type="button"
                    aria-label="Choose new site element"
                    onClick={() => setPickElement("new")}
                  >
                    …
                  </Button>
                )}
              </label>
            ))}
          </div>
          {error && <p className="pe-edit-error">{error}</p>}
          <Button type="button" onClick={() => setAdding(false)}>
            Cancel site
          </Button>
          <Button disabled={locked}>Add site</Button>
        </form>
      )}
      {pickElement !== null && (
        <PhaseElementPicker
          elements={structure.elements}
          value={
            pickElement === "new"
              ? newSite.element
              : String(structure.sites[pickElement].element || "")
          }
          onClose={() => setPickElement(null)}
          onChoose={(value) => {
            if (pickElement === "new")
              setNewSite((s) => ({ ...s, element: value }));
            else
              void act("editor_site", {
                action: "update",
                row: pickElement,
                parameter: "element",
                value,
              });
          }}
        />
      )}
    </div>
  );
}

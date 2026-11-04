import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { DataTable, TableScroll } from "./DataTable";
import type { IntegrationRun } from "./integration";
import type { DatabaseMaterial, DatabaseRecord } from "./phaseDatabaseTypes";
import "./phaseDatabase.css";

type View = "Recent" | "Favourites" | "All";
type Sort = { key: string; descending: boolean } | null;
const views: View[] = ["Recent", "Favourites", "All"];
const savedIds = (key: string): string[] => {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value)
      ? [...new Set(value.filter((id): id is string => typeof id === "string"))]
      : [];
  } catch {
    return [];
  }
};
const saveIds = (key: string, ids: string[]) => {
  try {
    localStorage.setItem(key, JSON.stringify(ids));
  } catch {
    /* Browsing still works when storage is unavailable. */
  }
};
const compare = (a: unknown, b: unknown) => {
  if (a == null || a === "") return b == null || b === "" ? 0 : 1;
  if (b == null || b === "") return -1;
  return typeof a === "number" && typeof b === "number"
    ? a - b
    : String(a).localeCompare(String(b), undefined, {
        numeric: true,
        sensitivity: "base",
      });
};
const spaceGroup = (text: string) =>
  text
    .replace(
      /^([PABCIFR]\s*)([2346])([1-5])/,
      (_, p, a, b) => p + a + "₀₁₂₃₄₅₆₇₈₉"[Number(b)],
    )
    .replace(/_(\d)/g, (_, digit) => "₀₁₂₃₄₅₆₇₈₉"[Number(digit)]);
// Only add a variant name where author/year and EoS alone are ambiguous.
// Keep the catalog's own wording, removing its repeated citation prefix.
function variant(record: DatabaseRecord, records: DatabaseRecord[]) {
  const duplicates = records.filter(
    (r) =>
      r.authors === record.authors &&
      r.year === record.year &&
      r.eos === record.eos,
  );
  if (duplicates.length < 2) return "";
  const label = String(record.sourceRecord.label || record.label);
  const citation = `${record.authors} (${record.year}), `;
  return label.startsWith(citation) ? label.slice(citation.length) : label;
}
function keepVisible(row: HTMLElement | null) {
  const scroll = row?.closest(".data-table-scroll");
  if (!scroll || !row) return;
  const bounds = row.getBoundingClientRect(),
    area = scroll.getBoundingClientRect();
  const head =
    scroll.querySelector("thead")?.getBoundingClientRect().height || 0;
  if (bounds.top < area.top + head)
    scroll.scrollTop += bounds.top - area.top - head;
  else if (bounds.bottom > area.bottom)
    scroll.scrollTop += bounds.bottom - area.bottom;
}
function rowKey(
  event: KeyboardEvent<HTMLTableRowElement>,
  select: (index: number) => void,
  index: number,
  count: number,
  load: () => void,
) {
  let next = index;
  if (event.key === "ArrowDown") next = Math.min(count - 1, index + 1);
  else if (event.key === "ArrowUp") next = Math.max(0, index - 1);
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = count - 1;
  else if (event.key === "Enter") {
    event.preventDefault();
    load();
    return;
  } else if (event.key === " ") {
    event.preventDefault();
    select(index);
    return;
  } else return;
  event.preventDefault();
  select(next);
  const row = event.currentTarget.parentElement?.children[next] as
    HTMLElement | undefined;
  row?.focus({ preventScroll: true });
  keepVisible(row || null);
}

export function PhaseDatabase({
  materials,
  run,
  ready,
  onClose,
}: {
  materials: DatabaseMaterial[];
  run: IntegrationRun;
  ready: boolean;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const queryRef = useRef("");
  queryRef.current = query.trim();
  const [result, setResult] = useState({ query: "", hits: materials });
  const [searchError, setSearchError] = useState("");
  const [retry, setRetry] = useState(0);
  const inFlight = useRef<string | null>(null);
  const [view, setView] = useState<View>("All");
  const beforeSearch = useRef<View | null>(null);
  const [diffractionOnly, setDiffractionOnly] = useState(true);
  const [recent] = useState(() =>
    savedIds("dioptas-phase-recent").slice(0, 20),
  );
  const [favourites, setFavourites] = useState(() =>
    savedIds("dioptas-phase-favourites"),
  );
  const [selected, setSelected] = useState("");
  const [choice, setChoice] = useState<{
    material: string;
    reference: number;
  } | null>(null);
  const [assumedFor, setAssumedFor] = useState("");
  const [materialSort, setMaterialSort] = useState<Sort>(null);
  const [recordSort, setRecordSort] = useState<Sort>(null);
  const materialTable = useRef<HTMLTableElement>(null);
  const recordTable = useRef<HTMLTableElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    search.current?.focus();
    return () => {
      previous?.focus();
    };
  }, []);
  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setResult({ query: "", hits: materials });
      setSearchError("");
      return;
    }
    if (!ready || searchError || result.query === q || inFlight.current === q)
      return;
    const timer = setTimeout(() => {
      inFlight.current = q;
      setSearchError("");
      let received = false;
      void run(
        "integration_phase_catalog",
        { query: q },
        "Searching materials…",
        (r) => {
          received = !!r.phaseCatalog;
          if (queryRef.current === q && r.phaseCatalog)
            setResult({ query: q, hits: r.phaseCatalog });
        },
      )
        .catch(() => {
          // The host normally reports errors; retain a local retry if a host rejects.
        })
        .finally(() => {
          if (inFlight.current === q) inFlight.current = null;
          if (!received && queryRef.current === q)
            setSearchError(
              "Search did not complete. Retry or clear the search.",
            );
        });
    }, 220);
    return () => clearTimeout(timer);
  }, [query, materials, run, ready, retry, result.query, searchError]);
  const pending = result.query !== query.trim();
  const hits = pending ? [] : result.hits;
  let shown = hits.filter(
    (m) =>
      (!diffractionOnly || m.diffraction) &&
      (view === "All" ||
        (view === "Recent" ? recent : favourites).includes(m.id)),
  );
  if (view === "Recent" && !materialSort)
    shown.sort((a, b) => recent.indexOf(a.id) - recent.indexOf(b.id));
  if (materialSort)
    shown.sort(
      (a, b) =>
        compare(a[materialSort.key as "name"], b[materialSort.key as "name"]) *
        (materialSort.descending ? -1 : 1),
    );
  const material = shown.find((m) => m.id === selected) || shown[0];
  const reference =
    choice && choice.material === material?.id
      ? choice.reference
      : (material?.defaultReference ?? -1);
  useEffect(() => {
    setAssumedFor("");
    setChoice((previous) =>
      previous?.material === material?.id ? previous : null,
    );
    if (material) setSelected(material.id);
  }, [material?.id]);
  const record = material?.references[reference];
  const hasVariants = material?.references.some((r) =>
    variant(r, material.references),
  );
  const assumed = !!material?.canAssumeStructure && assumedFor === material.id;
  const reason = !material
    ? "Select a material."
    : !material.diffraction && !assumed
      ? "No crystal structure or reference peak table is available. EoS records can still be inspected and exported."
      : material.references.length && !record
        ? "Select an EoS record explicitly; no automatic default is recommended."
        : (assumed ? record?.assumedLoadError : record?.loadError) || "";
  const canLoad = ready && !pending && !reason;
  let records = material?.references.map((r, index) => ({ r, index })) || [];
  if (recordSort)
    records.sort((a, b) => {
      const value = (r: DatabaseRecord) =>
        recordSort.key === "variant"
          ? variant(r, material?.references || [])
          : recordSort.key === "authors"
            ? `${r.authors} (${r.year})`
            : r.eos;
      return compare(value(a.r), value(b.r)) * (recordSort.descending ? -1 : 1);
    });
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      keepVisible(
        materialTable.current?.querySelector('tr[aria-selected="true"]') ||
          null,
      );
      keepVisible(
        recordTable.current?.querySelector('tr[aria-selected="true"]') || null,
      );
    });
    if (dialog.current) observer.observe(dialog.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    keepVisible(
      materialTable.current?.querySelector('tr[aria-selected="true"]') || null,
    );
    keepVisible(
      recordTable.current?.querySelector('tr[aria-selected="true"]') || null,
    );
  }, [material?.id, reference, result, materialSort, recordSort]);
  const changeQuery = (q: string) => {
    if (q.trim() && beforeSearch.current === null) {
      beforeSearch.current = view;
      setView("All");
    } else if (!q.trim() && beforeSearch.current !== null) {
      setView(beforeSearch.current);
      beforeSearch.current = null;
    }
    setMaterialSort(null);
    setSearchError("");
    setQuery(q);
  };
  const selectMaterial = (id: string) => {
    setSelected(id);
    if (id !== material?.id) {
      setChoice(null);
      setAssumedFor("");
    }
  };
  const load = (index = reference, m = material) => {
    if (!ready || pending || !m) return;
    const useAssumption = m.id === material?.id && assumed;
    const target = m.references[index];
    if (
      (!m.diffraction && !useAssumption) ||
      (m.references.length && !target) ||
      (useAssumption ? target?.assumedLoadError : target?.loadError)
    )
      return;
    void run(
      "integration_phase",
      {
        operation: "load_database",
        material_id: m.id,
        reference: index,
        assume_structure: useAssumption,
      },
      "Loading phase…",
      () => {
        saveIds(
          "dioptas-phase-recent",
          [m.id, ...recent.filter((id) => id !== m.id)].slice(0, 20),
        );
        onClose();
      },
    );
  };
  const sortHead = (
    label: string,
    key: string,
    sort: Sort,
    update: (s: Sort) => void,
  ) => (
    <th
      scope="col"
      aria-sort={
        sort?.key === key
          ? sort.descending
            ? "descending"
            : "ascending"
          : "none"
      }
    >
      <button
        onClick={() =>
          update({ key, descending: sort?.key === key && !sort.descending })
        }
      >
        {label}
        {sort?.key === key ? (sort.descending ? " ↓" : " ↑") : ""}
      </button>
    </th>
  );
  const empty = query.trim()
    ? "No materials in this view match your search."
    : view === "Recent"
      ? "No recently loaded materials. Choose All or search to load a phase; the last 20 appear here."
      : view === "Favourites"
        ? "No favourites yet. Choose All or search, select a material and choose ☆ Favourite."
        : "No materials in this view.";
  return createPortal(
    <dialog
      ref={dialog}
      className="phase-dialog phase-database-dialog"
      aria-label="EoS Material Database"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          onClose();
          return;
        }
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "f") {
          e.preventDefault();
          search.current?.focus();
          search.current?.select();
        }
      }}
    >
      <header>
        <h2>EoS Material Database</h2>
        <button aria-label="Close EoS Material Database" onClick={onClose}>
          ×
        </button>
      </header>
      <div className="phase-database-body">
        <div className="phase-database-search">
          <input
            ref={search}
            type="search"
            aria-label="Search materials"
            placeholder="Search all materials: Au, MgFe, gold, periclase…"
            value={query}
            onChange={(e) => changeQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                (
                  materialTable.current?.querySelector(
                    'tr[aria-selected="true"]',
                  ) as HTMLElement
                )?.focus();
              }
            }}
          />
          <button
            disabled={!query}
            onClick={() => {
              changeQuery("");
              search.current?.focus();
            }}
          >
            Clear
          </button>
        </div>
        <div className="phase-database-tools">
          <div role="tablist" aria-label="Material views">
            {views.map((name, i) => (
              <button
                key={name}
                role="tab"
                tabIndex={view === name ? 0 : -1}
                aria-selected={view === name}
                onClick={() => {
                  setView(name);
                  setMaterialSort(null);
                  if (beforeSearch.current !== null)
                    beforeSearch.current = name;
                }}
                onKeyDown={(e) => {
                  if (
                    !["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)
                  )
                    return;
                  e.preventDefault();
                  const next =
                    e.key === "Home"
                      ? 0
                      : e.key === "End"
                        ? 2
                        : (i + (e.key === "ArrowRight" ? 1 : 2)) % 3;
                  setView(views[next]);
                  setMaterialSort(null);
                  if (beforeSearch.current !== null)
                    beforeSearch.current = views[next];
                  (
                    e.currentTarget.parentElement?.children[next] as HTMLElement
                  )?.focus();
                }}
              >
                {name}
              </button>
            ))}
          </div>
          <label title="Show materials with a crystal structure or reference peak table. Assumed structures are hidden.">
            <input
              type="checkbox"
              checked={diffractionOnly}
              onChange={(e) => setDiffractionOnly(e.target.checked)}
            />
            Diffraction data only
          </label>
          <button
            disabled={!material}
            onClick={() => {
              const ids = favourites.includes(material.id)
                ? favourites.filter((id) => id !== material.id)
                : [...favourites, material.id];
              setFavourites(ids);
              saveIds("dioptas-phase-favourites", ids);
            }}
          >
            {material && favourites.includes(material.id)
              ? "★ Favourite"
              : "☆ Favourite"}
          </button>
        </div>
        <section
          className="phase-database-section"
          aria-label="Material results"
          aria-busy={pending}
          data-small={shown.length <= 3}
        >
          <div className="phase-database-heading">
            <h3>
              {query.trim() ? "Search results" : "Materials"} ({shown.length})
            </h3>
            {materialSort && (
              <button onClick={() => setMaterialSort(null)}>
                Restore{" "}
                {query.trim()
                  ? "search ranking"
                  : view === "Recent"
                    ? "recent order"
                    : "library order"}
              </button>
            )}
          </div>
          <TableScroll>
            <DataTable ref={materialTable} aria-label="Database materials">
              <thead>
                <tr>
                  {sortHead("Material", "name", materialSort, setMaterialSort)}
                  {sortHead(
                    "Space group",
                    "spaceGroup",
                    materialSort,
                    setMaterialSort,
                  )}
                  {sortHead(
                    "Diffraction data",
                    "diffractionStatus",
                    materialSort,
                    setMaterialSort,
                  )}
                </tr>
              </thead>
              <tbody>
                {shown.map((m, i) => (
                  <tr
                    key={m.id}
                    aria-selected={m.id === material?.id}
                    tabIndex={m.id === material?.id ? 0 : -1}
                    onClick={() => selectMaterial(m.id)}
                    onDoubleClick={() => {
                      load(
                        m.id === material?.id ? reference : m.defaultReference,
                        m,
                      );
                    }}
                    onKeyDown={(e) =>
                      rowKey(
                        e,
                        (n) => selectMaterial(shown[n].id),
                        i,
                        shown.length,
                        () => load(),
                      )
                    }
                  >
                    <td>{m.name}</td>
                    <td>{spaceGroup(m.spaceGroup)}</td>
                    <td>{m.diffractionStatus}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            {!shown.length && (
              <p role="status" className="phase-database-empty">
                {pending ? searchError || "Searching materials…" : empty}
                {!pending &&
                  diffractionOnly &&
                  " Materials without diffraction data are hidden; uncheck the filter to include them."}
                {searchError && (
                  <button
                    onClick={() => {
                      setSearchError("");
                      setRetry((n) => n + 1);
                    }}
                  >
                    Retry search
                  </button>
                )}
              </p>
            )}
          </TableScroll>
        </section>
        <section className="phase-database-section">
          <div className="phase-database-heading">
            <h3>
              {material
                ? `${material.name} — EoS records (${records.length})`
                : "Equation of state records"}
            </h3>
            {recordSort && (
              <button onClick={() => setRecordSort(null)}>
                Restore record order
              </button>
            )}
          </div>
          <TableScroll>
            <DataTable
              ref={recordTable}
              aria-label="Material EoS records"
              className="phase-database-records"
            >
              <thead>
                <tr>
                  {sortHead("Reference", "authors", recordSort, setRecordSort)}
                  {sortHead("EoS", "eos", recordSort, setRecordSort)}
                  {hasVariants &&
                    sortHead("Variant", "variant", recordSort, setRecordSort)}
                </tr>
              </thead>
              <tbody>
                {records.map(({ r, index }, i) => (
                  <tr
                    key={index}
                    title={r.label}
                    data-reference={index}
                    aria-selected={index === reference}
                    tabIndex={
                      index === reference || (reference < 0 && i === 0) ? 0 : -1
                    }
                    onClick={() =>
                      setChoice({ material: material.id, reference: index })
                    }
                    onDoubleClick={() => {
                      load(index);
                    }}
                    onKeyDown={(e) =>
                      rowKey(
                        e,
                        (n) =>
                          setChoice({
                            material: material.id,
                            reference: records[n].index,
                          }),
                        i,
                        records.length,
                        () => load(index),
                      )
                    }
                  >
                    <td className="phase-database-reference">
                      <span>
                        {r.authors
                          ? `${r.authors}${r.year ? ` (${r.year})` : ""}`
                          : r.label}
                      </span>
                      {index === material.defaultReference && (
                        <small>Default</small>
                      )}
                    </td>
                    <td title={r.thermal ? `${r.eos} · ${r.thermal}` : r.eos}>
                      {r.eos}
                    </td>
                    {hasVariants && (
                      <td className="phase-database-variant" title={r.label}>
                        {variant(r, material.references)}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </DataTable>
            {!records.length && (
              <p className="phase-database-empty">
                {material
                  ? "No EoS records for this material."
                  : "Select a material."}
              </p>
            )}
          </TableScroll>
        </section>
        <div className="phase-database-conditions">
          {material?.canAssumeStructure && (
            <label>
              <input
                type="checkbox"
                checked={assumed}
                onChange={(e) =>
                  setAssumedFor(e.target.checked ? material.id : "")
                }
              />
              Use assumed tetragonal perovskite structure
            </label>
          )}
          {assumed && (
            <p className="phase-condition-note" title={material.assumptionNote}>
              Approximate diffraction lines; not a refined structure.
            </p>
          )}
          {reason && material && (
            <p
              className="phase-condition-note"
              role="status"
              title={material.hold || reason}
            >
              {!material.diffraction && !assumed
                ? "No diffraction data available."
                : !record
                  ? "Select a record to load."
                  : "This record is source-only and cannot be loaded."}
            </p>
          )}
        </div>
      </div>
      <footer>
        <button
          disabled={!ready || !material || pending}
          title="Export the selected material with all its EoS records"
          onClick={() =>
            void run(
              "integration_phase_export",
              { material_id: material.id, assume_structure: assumed },
              "Exporting material…",
            )
          }
        >
          Export .eosmat…
        </button>
        <div className="phase-database-links">
          {record?.recordUrl && (
            <button
              disabled={!ready}
              title="View the selected record in Peritheos"
              onClick={() =>
                void run(
                  "integration_phase_documentation",
                  { material_id: material.id, reference, kind: "record" },
                  "Opening Peritheos record…",
                )
              }
            >
              Peritheos ↗
            </button>
          )}
          {record?.reportUrl && (
            <button
              disabled={!ready}
              title="Open the selected record’s reconstruction report"
              onClick={() =>
                void run(
                  "integration_phase_documentation",
                  { material_id: material.id, reference, kind: "report" },
                  "Opening reconstruction report…",
                )
              }
            >
              Reconstruction report ↗
            </button>
          )}
        </div>
        <button onClick={onClose}>Close</button>
        <button
          className="primary"
          disabled={!canLoad}
          title={
            reason ||
            "Load the selected material and EoS record as a diffraction phase"
          }
          onClick={() => load()}
        >
          Load as Phase
        </button>
      </footer>
    </dialog>,
    document.querySelector(".app") || document.body,
  );
}

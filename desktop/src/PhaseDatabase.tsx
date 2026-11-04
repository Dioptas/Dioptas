import { matchesRecordAuthor, recordAuthors } from "./phaseAuthorSearch";
import { Star } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { createPortal } from "react-dom";
import { DataTable, TableScroll } from "./DataTable";
import type { IntegrationRun } from "./integration";
import type { DatabaseMaterial, DatabaseRecord } from "./phaseDatabaseTypes";
import "./phaseDatabase.css";

type View = "Recent" | "Favourites" | "All";
type Sort = { key: string; descending: boolean } | null;
const views: View[] = ["All", "Recent", "Favourites"];
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
const materialSortName = (name: string) => name.replace(/^[\s()[\]{}]+/u, "");
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
function matchesRecord(record: DatabaseRecord, query: string) {
  const terms = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  const text = [
    ...recordAuthors(record),
    record.authors,
    record.year,
    record.eos,
    record.thermal,
    record.label,
    "eos",
    record.thermal ? "thermal therm term pvt" : "",
  ]
    .join(" ")
    .toLocaleLowerCase();
  return (
    matchesRecordAuthor(record, query) ||
    terms.every(
      (term) => text.includes(term) || matchesRecordAuthor(record, term),
    )
  );
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
  const [materialSort, setMaterialSort] = useState<Sort>(null);
  const [recordSort, setRecordSort] = useState<Sort>(null);
  const [recordFilter, setRecordFilter] = useState({ material: "", text: "" });
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
  const authorHits = useMemo(
    () =>
      query.trim()
        ? materials
            .filter((m) =>
              m.references.some((r) => matchesRecordAuthor(r, query)),
            )
            .sort((a, b) =>
              compare(materialSortName(a.name), materialSortName(b.name)),
            )
        : [],
    [materials, query],
  );
  // Keep the model's formula/name ranking, then append author-only matches once.
  const namedIds = new Set(result.hits.map((m) => m.id));
  const hits = pending
    ? []
    : [...result.hits, ...authorHits.filter((m) => !namedIds.has(m.id))];
  let shown = hits.filter(
    (m) =>
      m.diffraction &&
      (view === "All" ||
        (view === "Recent" ? recent : favourites).includes(m.id)),
  );
  if (view === "Recent" && !materialSort)
    shown.sort((a, b) => recent.indexOf(a.id) - recent.indexOf(b.id));
  if (materialSort)
    shown.sort(
      (a, b) =>
        compare(
          materialSort.key === "name" ? materialSortName(a.name) : a.spaceGroup,
          materialSort.key === "name" ? materialSortName(b.name) : b.spaceGroup,
        ) * (materialSort.descending ? -1 : 1),
    );
  if (!materialSort && view !== "Recent" && !query.trim())
    shown.sort((a, b) =>
      compare(materialSortName(a.name), materialSortName(b.name)),
    );
  const material = shown.find((m) => m.id === selected) || shown[0];
  const chosenReference =
    choice && choice.material === material?.id
      ? choice.reference
      : (material?.defaultReference ?? -1);
  const recordQuery =
    recordFilter.material === material?.id ? recordFilter.text : "";
  const authorQuery = material?.references.some((r) =>
    matchesRecordAuthor(r, query),
  )
    ? query.trim()
    : "";
  let records = (
    material?.references.map((r, index) => ({ r, index })) || []
  ).filter(
    ({ r }) =>
      (!authorQuery || matchesRecordAuthor(r, authorQuery)) &&
      matchesRecord(r, recordQuery),
  );
  const reference = records.some(({ index }) => index === chosenReference)
    ? chosenReference
    : -1;
  useEffect(() => {
    setRecordFilter({ material: material?.id || "", text: "" });
    setChoice((previous) =>
      previous?.material === material?.id ? previous : null,
    );
    if (material) setSelected(material.id);
  }, [material?.id]);
  const record = material?.references[reference];
  const hasVariants = material?.references.some((r) =>
    variant(r, material.references),
  );
  const reason = !material
    ? "Select a material."
    : !material.diffraction
      ? "No crystal structure or reference peak table is available. EoS records can still be inspected and exported."
      : material.references.length && !record
        ? recordQuery.trim() || authorQuery
          ? "Select a matching record. The previous selection is hidden by the active search/filter."
          : "Select an EoS record explicitly; no automatic default is recommended."
        : record?.loadError || "";
  const canLoad = ready && !pending && !reason;
  if (recordSort)
    records.sort((a, b) => {
      const value = (r: DatabaseRecord) =>
        recordSort.key === "variant"
          ? variant(r, material?.references || [])
          : recordSort.key === "authors"
            ? `${r.authors} (${r.year})`
            : recordSort.key === "thermal"
              ? r.thermal
              : recordSort.key === "pressureRange"
                ? ((
                    r.sourceRecord.experimental_pressure_range_gpa as
                      number[] | undefined
                  )?.[0] ?? r.pressureRange)
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
  }, [
    material?.id,
    reference,
    result,
    materialSort,
    recordSort,
    recordQuery,
    authorQuery,
  ]);
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
    }
  };
  const load = (index = reference, m = material) => {
    if (!ready || pending || !m) return;
    const target = m.references[index];
    const authorFiltered = m.references.some((r) =>
      matchesRecordAuthor(r, query),
    );
    if (
      !m.diffraction ||
      (m.references.length && !target) ||
      target?.loadError ||
      (target && authorFiltered && !matchesRecordAuthor(target, query)) ||
      (target && m.id === material?.id && !matchesRecord(target, recordQuery))
    )
      return;
    void run(
      "integration_phase",
      {
        operation: "load_database",
        material_id: m.id,
        reference: index,
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
      data-column={key}
      title={
        key === "pressureRange"
          ? "Pressure interval used to constrain the fit, not a phase-stability range."
          : key === "thermal"
            ? "Whether a thermal model is included. Hover over its indicator for the model name."
            : undefined
      }
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
        ? "No favourites yet. Choose All or search, select a material and mark its star."
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
            placeholder="Search material, formula or author…"
            title="Search material names, formulas, aliases or EoS authors."
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
          {materialSort && (
            <button
              className="phase-database-sort-reset"
              onClick={() => setMaterialSort(null)}
            >
              Restore{" "}
              {query.trim()
                ? "search ranking"
                : view === "Recent"
                  ? "recent order"
                  : "alphabetical order"}
            </button>
          )}
          <span
            className="phase-database-result-count"
            aria-label="Material result count"
          >
            {pending
              ? "…"
              : `${shown.length} ${shown.length === 1 ? "result" : "results"}`}
          </span>
          <button
            className="icon-button phase-database-favourite"
            aria-label={
              material && favourites.includes(material.id)
                ? "Remove from favourites"
                : "Add to favourites"
            }
            title={
              material && favourites.includes(material.id)
                ? "Remove from favourites"
                : "Add to favourites"
            }
            aria-pressed={!!material && favourites.includes(material.id)}
            disabled={!material}
            onClick={() => {
              const ids = favourites.includes(material.id)
                ? favourites.filter((id) => id !== material.id)
                : [...favourites, material.id];
              setFavourites(ids);
              saveIds("dioptas-phase-favourites", ids);
            }}
          >
            <Star
              size={17}
              aria-hidden="true"
              fill={
                material && favourites.includes(material.id)
                  ? "currentColor"
                  : "none"
              }
            />
          </button>
        </div>
        <section
          className="phase-database-section phase-database-materials"
          aria-label="Material results"
          aria-busy={pending}
        >
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
                    <td title={m.name}>{m.name}</td>
                    <td>{spaceGroup(m.spaceGroup)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
            {!shown.length && (
              <p role="status" className="phase-database-empty">
                {pending ? searchError || "Searching materials…" : empty}
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
                ? `${material.name} — EoS records (${records.length}${recordQuery.trim() || authorQuery ? ` / ${material.references.length}` : ""})`
                : "Equation of state records"}
            </h3>
            <input
              type="search"
              className="phase-database-record-filter"
              aria-label="Filter EoS records"
              placeholder={
                authorQuery
                  ? `Filter ${authorQuery} records…`
                  : "Filter records…"
              }
              title={
                authorQuery
                  ? `Showing only records matching author ${authorQuery}. Refine by reference, EoS or thermal model; clear the upper author search to show all authors.`
                  : "Filter authors, year, EoS or thermal model. PVT and TERM find thermal records."
              }
              value={recordQuery}
              disabled={!material}
              onChange={(e) =>
                setRecordFilter({ material: material.id, text: e.target.value })
              }
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  const row =
                    recordTable.current?.querySelector<HTMLTableRowElement>(
                      'tbody tr[aria-selected="true"]',
                    ) ||
                    recordTable.current?.querySelector<HTMLTableRowElement>(
                      "tbody tr",
                    );
                  row?.focus({ preventScroll: true });
                  keepVisible(row || null);
                }
              }}
            />
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
                  {sortHead("Thermal", "thermal", recordSort, setRecordSort)}
                  {sortHead(
                    "Fit P range",
                    "pressureRange",
                    recordSort,
                    setRecordSort,
                  )}
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
                    <td
                      className="phase-database-thermal"
                      title={r.thermal || "No thermal model"}
                      aria-label={
                        r.thermal
                          ? `Thermal model: ${r.thermal}`
                          : "No thermal model"
                      }
                    >
                      {r.thermal ? "✓" : "—"}
                    </td>
                    <td
                      title={
                        r.pressureRange || "Fit pressure range not recorded"
                      }
                    >
                      {r.pressureRange || "—"}
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
                  ? recordQuery.trim()
                    ? "No records match this filter."
                    : "No EoS records for this material."
                  : "Select a material."}
              </p>
            )}
          </TableScroll>
        </section>
        <div className="phase-database-conditions">
          {reason && material && records.length > 0 && (
            <p
              className="phase-condition-note"
              role="status"
              title={material.hold || reason}
            >
              {!material.diffraction
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
              { material_id: material.id },
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

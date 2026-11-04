import { isTauri } from "@tauri-apps/api/core";
import { openNativePhaseEditor } from "./phaseEditorWindow";
import type { EditorData } from "./phaseEditorTypes";
import { DataTable, TableScroll, TableActions } from "./DataTable";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Database, FolderOpen, Pencil, RotateCcw, Trash2 } from "lucide-react";
import type { IntegrationRun, IntegrationState } from "./integration";
import type {
  PhaseEditorData,
  PhaseImport,
  PhaseMaterial,
} from "./integrationPhase";
import { PhaseEditor } from "./PhaseEditor";
import { useSpinBoxWheel } from "./spinBoxWheel";
import { createPhaseCommandQueue } from "./phaseCommandQueue";
import "./integrationPhaseControls.css";

/** Qt's PhaseWidget: action rail, row table, P/T steps and list files. */
export function IntegrationPhaseControls({
  source,
  ready,
  active,
  run: parentRun,
}: {
  source: IntegrationState;
  ready: boolean;
  active: boolean;
  run: IntegrationRun;
}) {
  // Parent run invokes its callback while its command lock is held. Defer local
  // follow-up actions until that command has completed (file selection → load).
  const latestRun = useRef(parentRun);
  latestRun.current = parentRun;
  const commandQueue = useRef<IntegrationRun | null>(null);
  if (!commandQueue.current)
    commandQueue.current = createPhaseCommandQueue(() => latestRun.current);
  const run = commandQueue.current;
  const [selected, setSelected] = useState(source.phases.length - 1);
  const previousCount = useRef(source.phases.length);
  const tableRef = useRef<HTMLTableElement>(null);
  useEffect(() => {
    const table = tableRef.current;
    const scroll = table?.parentElement;
    const row = table?.tBodies[0]?.rows[selected];
    if (!scroll || !row || !active) return;
    const area = scroll.getBoundingClientRect();
    const bounds = row.getBoundingClientRect();
    const header = table.tHead?.getBoundingClientRect().height || 0;
    if (bounds.top < area.top + header)
      scroll.scrollTop += bounds.top - area.top - header;
    else if (bounds.bottom > area.bottom)
      scroll.scrollTop += bounds.bottom - area.bottom;
  }, [selected, source.phases.length, active]);
  const [pressureStep, setPressureStep] = useState(() => {
    const value = Number(sessionStorage.getItem("dioptas-phase-pressure-step"));
    return value > 0 ? value : 1;
  });
  useEffect(
    () =>
      sessionStorage.setItem(
        "dioptas-phase-pressure-step",
        String(pressureStep),
      ),
    [pressureStep],
  );
  const [temperatureStep, setTemperatureStep] = useState(() => {
    const value = Number(
      sessionStorage.getItem("dioptas-phase-temperature-step"),
    );
    return value >= 1 && value <= 1000 ? value : 100;
  });
  useEffect(
    () =>
      sessionStorage.setItem(
        "dioptas-phase-temperature-step",
        String(temperatureStep),
      ),
    [temperatureStep],
  );
  const [importFiles, setImportFiles] = useState<PhaseImport | null>(null);
  const [catalog, setCatalog] = useState<PhaseMaterial[] | null>(null);
  const [editor, setEditor] = useState<PhaseEditorData | null>(null);
  const phase = source.phases[selected];
  useEffect(() => {
    if (source.phases.length > previousCount.current)
      setSelected(source.phases.length - 1);
    else if (selected >= source.phases.length)
      setSelected(source.phases.length - 1);
    previousCount.current = source.phases.length;
  }, [source.phases.length, selected]);
  const action = (operation: string, args: Record<string, unknown> = {}) =>
    run("integration_phase", { operation, ...args }, "Updating phases…");
  const inspect = (index: number) =>
    void run(
      "integration_phase_editor",
      { index },
      "Opening phase editor…",
      (result) => {
        if (result.phaseEditor) {
          if (isTauri())
            void openNativePhaseEditor(
              (result.phaseEditor as EditorData).uid,
            ).catch(() => setEditor(result.phaseEditor!));
          else setEditor(result.phaseEditor);
        }
      },
    );
  const load = (files: PhaseImport) => {
    if (files.paths.some((p) => /\.cif$/i.test(p))) setImportFiles(files);
    else action("load", { paths: files.paths });
  };
  return (
    <div
      className="phase-controls"
      hidden={!active}
      data-testid="phase-controls"
    >
      <TableActions
        orientation="vertical"
        className="phase-action-rail"
        role="toolbar"
        aria-label="Phase actions"
      >
        <PhaseIcon
          label="Add phase…"
          title="Loads Phase(s) from jcpds or cif file(s)"
          onClick={() =>
            void run("integration_phase_files", {}, "Choosing phases…", (r) => {
              if (r.phaseImport) load(r.phaseImport);
            })
          }
        >
          <FolderOpen />
        </PhaseIcon>
        <PhaseIcon
          label="Browse EoS Material Database"
          onClick={() =>
            void run(
              "integration_phase_catalog",
              {},
              "Loading EoS Material Database…",
              (r) => {
                if (r.phaseCatalog) setCatalog(r.phaseCatalog);
              },
            )
          }
        >
          <Database />
        </PhaseIcon>
        <PhaseIcon
          label="Edit selected Phase"
          disabled={!phase}
          onClick={() => inspect(selected)}
        >
          <Pencil />
        </PhaseIcon>
        <hr />
        <PhaseIcon
          label="Removes currently selected phase"
          disabled={!phase}
          onClick={() => action("remove", { index: selected })}
        >
          <Trash2 />
        </PhaseIcon>
        <hr />
        <PhaseIcon
          label="Removes all phases"
          disabled={!source.phases.length}
          onClick={() => {
            action("clear");
            setEditor(null);
          }}
        >
          <RotateCcw />
        </PhaseIcon>
      </TableActions>
      <TableScroll className="phase-table-scroll">
        <DataTable ref={tableRef} className="phase-table" aria-label="Phases">
          <colgroup>
            <col className="phase-show-col" />
            <col className="phase-color-col" />
            <col className="phase-name-col" />
            <col className="phase-value-col" />
            <col className="phase-value-col" />
            <col className="phase-reference-col" />
          </colgroup>
          <thead>
            <tr>
              <th>
                <button
                  className="phase-show-all"
                  aria-label="Toggle all phase visibility"
                  disabled={!source.phases.length}
                  title="Show / hide all phases"
                  onClick={() =>
                    action("visibility_all", {
                      visible: !source.phases.some((p) => p.visible),
                    })
                  }
                >
                  ✓
                </button>
              </th>
              <th aria-label="Color" />
              <th>Name</th>
              <th
                title={
                  source.phaseColdPressure
                    ? "Cold pressure at the thermal EoS reference temperature"
                    : "Pressure"
                }
              >
                {source.phaseColdPressure ? "P₀" : "P"} (GPa)
              </th>
              <th>T (K)</th>
              <th>Ref</th>
            </tr>
          </thead>
          <tbody>
            {source.phases.map((p, index) => (
              <tr
                key={p.uid ?? index}
                aria-selected={index === selected}
                onClick={() => {
                  setSelected(index);
                  if (editor && editor.index !== index) inspect(index);
                }}
                onDoubleClick={(e) => {
                  if (
                    !(e.target as HTMLElement).closest("input, select, button")
                  )
                    inspect(index);
                }}
                onKeyDown={(e) => {
                  if (e.target !== e.currentTarget) return;
                  if (["ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) {
                    e.preventDefault();
                    const next =
                      e.key === "Home"
                        ? 0
                        : e.key === "End"
                          ? source.phases.length - 1
                          : Math.max(
                              0,
                              Math.min(
                                source.phases.length - 1,
                                index + (e.key === "ArrowUp" ? -1 : 1),
                              ),
                            );
                    setSelected(next);
                    (
                      e.currentTarget.parentElement?.children[
                        next
                      ] as HTMLElement
                    )?.focus();
                    if (editor) inspect(next);
                  } else if (e.key === "Enter") inspect(index);
                  else if (e.key === "Delete" || e.key === "Backspace") {
                    e.preventDefault();
                    action("remove", { index });
                  }
                }}
                tabIndex={index === selected ? 0 : -1}
              >
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Show phase ${index + 1}`}
                    checked={p.visible}
                    onChange={(e) =>
                      action("update", { index, visible: e.target.checked })
                    }
                  />
                </td>
                <td>
                  <input
                    type="color"
                    aria-label={`Phase ${index + 1} color`}
                    value={p.color}
                    onChange={(e) =>
                      action("update", { index, color: e.target.value })
                    }
                  />
                </td>
                <td title={p.name} className="phase-name">
                  {p.name}
                </td>
                <td>
                  <PhaseNumber
                    label={`Phase ${index + 1} pressure (GPa)`}
                    value={p.pressure}
                    step={pressureStep}
                    min={-9999999}
                    max={9999999}
                    onCommit={(pressure) =>
                      action("update", { index, editor_uid: p.uid, pressure })
                    }
                  />
                </td>
                <td>
                  <PhaseNumber
                    label={`Phase ${index + 1} temperature (K)`}
                    title="Absolute temperature in kelvin. 0 uses the legacy room-temperature convention."
                    disabled={!p.thermal}
                    value={p.temperature}
                    step={temperatureStep}
                    min={0}
                    max={9999999}
                    onCommit={(temperature) =>
                      action("update", {
                        index,
                        editor_uid: p.uid,
                        temperature,
                      })
                    }
                  />
                </td>
                <td>
                  <select
                    aria-label={`Phase ${index + 1} reference`}
                    title={
                      p.referenceDetails[p.reference]?.detail ||
                      "No alternative references (legacy jcpds file)"
                    }
                    disabled={p.references.length < 2}
                    value={p.references.length ? p.reference : -1}
                    onChange={(e) =>
                      action("update", {
                        index,
                        reference: Number(e.target.value),
                      })
                    }
                  >
                    {!p.references.length && <option value={-1}>—</option>}
                    {p.references.map((ref, i) => (
                      <option
                        key={i}
                        value={i}
                        title={p.referenceDetails[i]?.detail}
                      >
                        {["Not reproduced", "Do not use"].includes(
                          p.referenceDetails[i]?.assessment,
                        )
                          ? "⚠ "
                          : ""}
                        {ref}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
        {!source.phases.length && (
          <p className="phase-empty">
            Load JCPDS, CIF or EOSMAT phase files, or browse the EoS Material
            Database.
          </p>
        )}
      </TableScroll>
      <div className="phase-parameters">
        <div className="phase-step-controls">
          <label>
            P step
            <PhaseNumber
              label="P step"
              multiply
              value={pressureStep}
              min={0.001}
              max={9999999}
              step={pressureStep}
              onCommit={setPressureStep}
            />
          </label>
          <label>
            T Step
            <PhaseNumber
              label="T Step"
              multiply
              value={temperatureStep}
              min={1}
              max={1000}
              step={temperatureStep}
              onCommit={setTemperatureStep}
            />
          </label>
          <label
            className="phase-apply-all"
            title="Whether individual changes in P or T are applied to all other phases"
          >
            <input
              type="checkbox"
              aria-label="Apply conditions to all phases"
              checked={source.sameConditions}
              onChange={(e) =>
                action("same_conditions", { enabled: e.target.checked })
              }
            />
            apply to all
          </label>
          <hr />
        </div>
        <div className="phase-list-actions">
          <button
            disabled={
              !source.phases.length || source.phases.some((p) => !p.fileBacked)
            }
            title={
              source.phases.some((p) => !p.fileBacked)
                ? "Phase lists reference files on disk. Save a project to retain database or unsaved phases."
                : "Save Phase List"
            }
            onClick={() =>
              void run(
                "integration_phase_list",
                { save: true },
                "Saving phase list…",
              )
            }
          >
            Save List
          </button>
          <button
            onClick={() =>
              void run(
                "integration_phase_list",
                { save: false },
                "Loading phase list…",
              )
            }
          >
            Load List
          </button>
        </div>
      </div>
      {importFiles && (
        <PhaseImportDialog
          files={importFiles}
          ready={ready}
          onClose={() => setImportFiles(null)}
          onLoad={(options) => {
            action("load", { paths: importFiles.paths, ...options });
            setImportFiles(null);
          }}
        />
      )}
      {catalog && (
        <PhaseDatabase
          materials={catalog}
          run={run}
          ready={ready}
          onClose={() => setCatalog(null)}
        />
      )}
      {editor && phase && (
        <PhaseEditor
          data={editor}
          ready={ready}
          run={run}
          onData={setEditor}
          onClose={() => setEditor(null)}
        />
      )}
    </div>
  );
}

function PhaseIcon({
  label,
  title = label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  title?: string;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={title}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function PhaseNumber({
  label,
  title,
  value,
  onCommit,
  disabled,
  step = "any",
  multiply = false,
  min,
  max,
}: {
  label: string;
  title?: string;
  value: number;
  onCommit: (v: number) => void | Promise<void>;
  disabled?: boolean;
  step?: number | string;
  multiply?: boolean;
  min?: number;
  max?: number;
}) {
  const [text, setText] = useState(String(value));
  const input = useRef<HTMLInputElement>(null);
  const pending = useRef(0);
  const disposed = useRef(false);
  useEffect(
    () => () => {
      disposed.current = true;
    },
    [],
  );
  const draftGeneration = useRef(0);
  const applied = useRef(value);
  applied.current = value;
  const last = useRef(value);
  useEffect(() => {
    if (pending.current) return;
    setText(String(value));
    last.current = value;
  }, [value]);
  const send = (n: number) => {
    const generation = ++draftGeneration.current;
    last.current = n;
    pending.current++;
    void Promise.resolve(onCommit(n))
      .catch(() => {})
      .finally(() => {
        pending.current--;
        requestAnimationFrame(() => {
          if (
            !disposed.current &&
            !pending.current &&
            generation === draftGeneration.current
          ) {
            setText(String(applied.current));
            last.current = applied.current;
          }
        });
      });
  };
  const commit = (input: HTMLInputElement) => {
    const n = Number(text);
    if (
      text.trim() &&
      Number.isFinite(n) &&
      (min === undefined || n >= min) &&
      (max === undefined || n <= max)
    ) {
      if (n !== last.current) {
        send(n);
      }
    } else {
      setText(String(value));
      last.current = value;
    }
    input.setCustomValidity("");
  };
  const increment = (direction: number) => {
    const current =
      text.trim() && Number.isFinite(Number(text)) ? Number(text) : value;
    const power = 10 ** Math.floor(Math.log10(Math.max(current, 1e-10)));
    const ratio = current / power;
    const multiple =
      direction > 0
        ? ratio < 1.9
          ? 2
          : ratio < 4.9
            ? 5
            : 10
        : ratio < 1.1
          ? 0.5
          : ratio < 2.1
            ? 1
            : ratio < 5.1
              ? 2
              : 5;
    const next = multiply
      ? power * multiple
      : current + direction * (typeof step === "number" ? step : 1);
    const n = Math.max(
      min ?? -Infinity,
      Math.min(max ?? Infinity, Number(next.toPrecision(12))),
    );
    setText(String(n));
    if (n !== last.current) {
      send(n);
    }
  };
  useSpinBoxWheel(input, increment);
  return (
    <input
      ref={input}
      className="numeric-stepper"
      type="number"
      aria-label={label}
      title={title}
      value={text}
      step={step}
      min={min}
      max={max}
      disabled={disabled}
      onChange={(e) => {
        // Native spinner clicks emit plain input events; typed edits carry inputType.
        if (
          !("inputType" in e.nativeEvent) &&
          Number(e.target.value) !== Number(text)
        )
          increment(Number(e.target.value) > Number(text) ? 1 : -1);
        else {
          draftGeneration.current++;
          setText(e.target.value);
        }
      }}
      onBlur={(e) => commit(e.currentTarget)}
      onKeyDown={(e) => {
        if (e.key === "ArrowUp" || e.key === "ArrowDown") {
          e.preventDefault();
          increment(e.key === "ArrowUp" ? 1 : -1);
        }
        if (e.key === "Enter") {
          e.preventDefault();
          commit(e.currentTarget);
        }
        if (e.key === "Escape") {
          draftGeneration.current++;
          setText(String(value));
          last.current = value;
        }
      }}
    />
  );
}

function PhaseDialog({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return createPortal(
    <dialog
      ref={ref}
      className={`phase-dialog${wide ? " phase-dialog-wide" : ""}`}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button type="button" aria-label={`Close ${title}`} onClick={onClose}>
          ×
        </button>
      </header>
      {children}
    </dialog>,
    document.querySelector(".app") || document.body,
  );
}

function PhaseImportDialog({
  files,
  ready,
  onClose,
  onLoad,
}: {
  files: PhaseImport;
  ready: boolean;
  onClose: () => void;
  onLoad: (v: Record<string, number>) => void;
}) {
  const [cutoff, setCutoff] = useState(0.5);
  const [spacing, setSpacing] = useState(files.minimumDSpacing);
  return (
    <PhaseDialog title="CIF conversion parameters" onClose={onClose}>
      <div className="phase-dialog-body phase-import-fields">
        <label>
          Intensity Cutoff:
          <PhaseNumber
            label="Intensity Cutoff (%)"
            value={cutoff}
            min={0}
            max={100}
            onCommit={setCutoff}
          />
          <span>%</span>
        </label>
        <label>
          Minimum d-spacing:
          <PhaseNumber
            label="Minimum d-spacing (Å)"
            value={spacing}
            min={0.01}
            max={100}
            onCommit={setSpacing}
          />
          <span>Å</span>
        </label>
      </div>
      <footer>
        <button onClick={onClose}>Cancel</button>
        <button
          className="primary"
          disabled={!ready}
          onClick={() =>
            onLoad({ intensity_cutoff: cutoff, minimum_d_spacing: spacing })
          }
        >
          OK
        </button>
      </footer>
    </PhaseDialog>
  );
}

const savedIds = (key: string): string[] => {
  try {
    return JSON.parse(localStorage.getItem(key) || "[]");
  } catch {
    return [];
  }
};
function PhaseDatabase({
  materials,
  run,
  ready,
  onClose,
}: {
  materials: PhaseMaterial[];
  run: IntegrationRun;
  ready: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState(materials);
  const [view, setView] = useState("All");
  const [diffractionOnly, setDiffractionOnly] = useState(true);
  const [recent, setRecent] = useState(() => savedIds("dioptas-phase-recent"));
  const [favourites, setFavourites] = useState(() =>
    savedIds("dioptas-phase-favourites"),
  );
  const [selected, setSelected] = useState("");
  const [reference, setReference] = useState(-1);
  const recordScroll = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const scroll = recordScroll.current;
    const row = scroll?.querySelector('tr[aria-selected="true"]');
    if (scroll && row)
      scroll.scrollTop +=
        row.getBoundingClientRect().top -
        scroll.getBoundingClientRect().top -
        30;
  }, [reference, selected, hits]);
  useEffect(() => {
    if (!query.trim()) {
      setHits(materials);
      return;
    }
    let current = true;
    const timer = setTimeout(() => {
      void run(
        "integration_phase_catalog",
        { query },
        "Searching materials…",
        (r) => {
          if (current && r.phaseCatalog) setHits(r.phaseCatalog);
        },
      );
    }, 250);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [query, materials, run]);
  const shown = hits.filter(
    (m) =>
      (!diffractionOnly || m.diffraction) &&
      (view === "All" ||
        (view === "Recent" ? recent : favourites).includes(m.id)),
  );
  const material = shown.find((m) => m.id === selected) || shown[0];
  useEffect(() => {
    setReference(material?.defaultReference ?? -1);
  }, [material?.id]);
  const record = material?.references[reference];
  const reason = !material
    ? "Select a material."
    : !material.diffraction
      ? "No crystal structure or reference peak table is available for diffraction phase lines."
      : material.references.length && !record
        ? material.hold || "Select an EoS record explicitly."
        : record?.loadError || "";
  const parameter = (r: NonNullable<typeof record>, key: string) => {
    const value = r.parameters[key];
    if (value === undefined)
      return r.eos === "BM2" && key === "K0_prime" ? "4 (fixed)" : "—";
    return `${value.toLocaleString(undefined, { maximumSignificantDigits: 7 })}${r.errors[key] != null ? ` ± ${r.errors[key]}` : r.fixed.includes(key) ? "" : " (error n/r)"}${r.fixed.includes(key) ? " (fixed)" : ""}`;
  };
  return (
    <PhaseDialog title="EoS Material Database" onClose={onClose} wide>
      <div className="phase-dialog-body phase-database">
        <input
          type="search"
          aria-label="Search materials"
          placeholder="Search material name or formula…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setView("All");
          }}
        />
        <div className="phase-db-tools">
          <div role="tablist" aria-label="Material views">
            {["Recent", "Favourites", "All"].map((name) => (
              <button
                key={name}
                role="tab"
                aria-selected={view === name}
                onClick={() => setView(name)}
              >
                {name}
              </button>
            ))}
          </div>
          <label>
            <input
              type="checkbox"
              checked={diffractionOnly}
              onChange={(e) => setDiffractionOnly(e.target.checked)}
            />
            Hide EoS-only materials
          </label>
          <button
            disabled={!material}
            onClick={() => {
              const ids = favourites.includes(material.id)
                ? favourites.filter((id) => id !== material.id)
                : [...favourites, material.id];
              setFavourites(ids);
              localStorage.setItem(
                "dioptas-phase-favourites",
                JSON.stringify(ids),
              );
            }}
          >
            {material && favourites.includes(material.id)
              ? "★ Favourite"
              : "☆ Favourite"}
          </button>
        </div>
        <TableScroll className="phase-materials-scroll">
          <DataTable>
            <thead>
              <tr>
                <th>Material</th>
                <th>Space group</th>
                <th>Diffraction data</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((m) => (
                <tr
                  key={m.id}
                  aria-selected={m.id === material?.id}
                  tabIndex={0}
                  onClick={() => setSelected(m.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected(m.id);
                    }
                  }}
                >
                  <td>{m.name}</td>
                  <td>{m.spaceGroup}</td>
                  <td>{m.diffraction ? "Available" : "EoS only"}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
          {!shown.length && <p>No materials in this view match your search.</p>}
        </TableScroll>
        <TableScroll ref={recordScroll} className="phase-records-scroll">
          <DataTable aria-label="Material EoS records">
            <thead>
              <tr>
                <th>EoS</th>
                <th>Thermal</th>
                <th>Reference</th>
                <th>P (GPa)</th>
                <th>K₀ (GPa)</th>
                <th>K₀′</th>
                <th>V₀ (Å³)</th>
                <th>Reproduction</th>
              </tr>
            </thead>
            <tbody>
              {material?.references.map((r, i) => (
                <tr
                  key={i}
                  title={r.detail}
                  aria-selected={i === reference}
                  tabIndex={0}
                  onClick={() => setReference(i)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setReference(i);
                    }
                  }}
                >
                  <td>{r.eos}</td>
                  <td title={r.thermal}>{r.thermal ? "✓" : "—"}</td>
                  <td>{r.label}</td>
                  <td>{r.pressureRange}</td>
                  <td>{parameter(r, "K0")}</td>
                  <td>{parameter(r, "K0_prime")}</td>
                  <td>{parameter(r, "V0")}</td>
                  <td>{r.assessment}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </TableScroll>
        {record && <p className="phase-assessment">{record.detail}</p>}
        {reason && <p className="phase-condition-note">{reason}</p>}
      </div>
      <footer>
        <button
          disabled={!ready || !material}
          onClick={() =>
            void run(
              "integration_phase_export",
              { material_id: material.id },
              "Exporting material…",
            )
          }
        >
          Export .eosmat
        </button>
        <button onClick={onClose}>Cancel</button>
        <button
          className="primary"
          disabled={!ready || !!reason}
          title={reason}
          onClick={() =>
            void run(
              "integration_phase",
              {
                operation: "load_database",
                material_id: material.id,
                reference,
              },
              "Loading phase…",
              () => {
                const ids = [
                  material.id,
                  ...recent.filter((id) => id !== material.id),
                ].slice(0, 20);
                setRecent(ids);
                localStorage.setItem(
                  "dioptas-phase-recent",
                  JSON.stringify(ids),
                );
                onClose();
              },
            )
          }
        >
          Load as Phase
        </button>
      </footer>
    </PhaseDialog>
  );
}

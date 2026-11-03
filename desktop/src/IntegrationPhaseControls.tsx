import { PhaseDatabase } from "./PhaseDatabase";
import { DataTable, TableScroll, TableActions } from "./DataTable";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { Database, FolderOpen, Pencil, RotateCcw, Trash2 } from "lucide-react";
import type { IntegrationRun, IntegrationState } from "./integration";
import type {
  PhaseEditorData,
  PhaseImport,
  PhaseMaterial,
} from "./integrationPhase";
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
  const run = useCallback<IntegrationRun>(
    async (command, args, message, onSuccess) => {
      let result: Parameters<NonNullable<typeof onSuccess>>[0] | undefined;
      await parentRun(command, args, message, (r) => {
        result = r;
      });
      if (result) onSuccess?.(result);
    },
    [parentRun],
  );
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
    void run("integration_phase", { operation, ...args }, "Updating phases…");
  const inspect = (index: number) =>
    void run(
      "integration_phase_editor",
      { index },
      "Opening phase editor…",
      (result) => {
        if (result.phaseEditor) setEditor(result.phaseEditor);
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
                key={index}
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
                      action("update", { index, pressure })
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
                      action("update", { index, temperature })
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
  onCommit: (v: number) => void;
  disabled?: boolean;
  step?: number | string;
  multiply?: boolean;
  min?: number;
  max?: number;
}) {
  const [text, setText] = useState(String(value));
  const last = useRef(value);
  useEffect(() => {
    setText(String(value));
    last.current = value;
  }, [value, onCommit]);
  const commit = (input: HTMLInputElement) => {
    const n = Number(text);
    if (
      text.trim() &&
      Number.isFinite(n) &&
      (min === undefined || n >= min) &&
      (max === undefined || n <= max)
    ) {
      if (n !== last.current) {
        last.current = n;
        onCommit(n);
      }
    } else {
      setText(String(value));
      last.current = value;
    }
    input.setCustomValidity("");
  };
  const increment = (direction: number) => {
    const current = Number(text) || value;
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
    const n = Math.max(min ?? -Infinity, Math.min(max ?? Infinity, next));
    setText(String(n));
    if (n !== last.current) {
      last.current = n;
      onCommit(n);
    }
  };
  return (
    <input
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
        else setText(e.target.value);
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

function PhaseEditor({
  data,
  ready,
  run,
  onData,
  onClose,
}: {
  data: PhaseEditorData;
  ready: boolean;
  run: IntegrationRun;
  onData: (v: PhaseEditorData) => void;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<number[]>([]);
  const [lengthStep, setLengthStep] = useState(0.01);
  const [angleStep, setAngleStep] = useState(1);
  const act = (operation: string, args: Record<string, unknown> = {}) =>
    void run(
      "integration_phase",
      { operation, index: data.index, editor: true, ...args },
      "Updating phase…",
      (r) => {
        if (r.phaseEditor) onData(r.phaseEditor);
      },
    );
  const number = (
    label: string,
    parameter: string,
    value: number,
    disabled: boolean,
    step: number | string = "any",
    unit?: string,
  ) => (
    <label key={parameter}>
      {label}
      <PhaseNumber
        label={label}
        value={value}
        disabled={disabled || !ready}
        step={step}
        onCommit={(v) => act("parameter", { parameter, value: v })}
      />
      {unit && <span>{unit}</span>}
    </label>
  );
  return (
    <PhaseDialog title="Phase Editor" onClose={onClose} wide>
      <div className="phase-dialog-body phase-editor">
        <label className="phase-editor-filename">
          Filename:
          <input readOnly value={data.filename} title={data.filename} />
        </label>
        <fieldset>
          <legend>Lattice &amp; structure</legend>
          {!data.editable && (
            <p className="phase-condition-note">
              Bundled material structure is read-only.
            </p>
          )}
          <label>
            Symmetry
            <select
              aria-label="Phase symmetry"
              disabled={!data.editable || !ready}
              value={data.symmetry}
              onChange={(e) =>
                act("parameter", {
                  parameter: "symmetry",
                  value: e.target.value,
                })
              }
            >
              {[
                "cubic",
                "tetragonal",
                "hexagonal",
                "trigonal",
                "rhombohedral",
                "orthorhombic",
                "monoclinic",
                "triclinic",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <div className="phase-editor-grid">
            {["a0", "b0", "c0"].map((p) =>
              number(
                `${p[0]}₀`,
                p,
                data.lattice[p],
                !data.editable || !data.latticeEditable.includes(p),
                lengthStep,
                "Å",
              ),
            )}
            {["a", "b", "c"].map((p) => (
              <label key={p}>
                {p}
                <input
                  aria-label={`Current lattice ${p}`}
                  readOnly
                  value={data.lattice[p].toFixed(4)}
                />
                <span>Å</span>
              </label>
            ))}
            {["alpha0", "beta0", "gamma0"].map((p, i) =>
              number(
                ["α₀", "β₀", "γ₀"][i],
                p,
                data.lattice[p],
                !data.editable || !data.latticeEditable.includes(p),
                angleStep,
                "°",
              ),
            )}
            {["v0", "v"].map((p) => (
              <label key={p}>
                {p === "v0" ? "V₀" : "V"}
                <input readOnly value={data.lattice[p].toFixed(4)} />
                <span>Å³</span>
              </label>
            ))}
          </div>
          <div className="phase-lattice-steps">
            <span>Steps:</span>
            <label>
              Length
              <PhaseNumber
                label="Lattice length step"
                value={lengthStep}
                min={0.0001}
                onCommit={setLengthStep}
              />
            </label>
            <label>
              Angle
              <PhaseNumber
                label="Lattice angle step"
                value={angleStep}
                min={0.0001}
                onCommit={setAngleStep}
              />
            </label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Equation of State</legend>
          {!!data.references.length && (
            <label>
              Material record:
              <select
                aria-label="Editor material record"
                disabled={!ready || data.references.length < 2}
                value={data.reference}
                title={data.references[data.reference]?.detail}
                onChange={(e) =>
                  act("update", { reference: Number(e.target.value) })
                }
              >
                {data.references.map((r, i) => (
                  <option key={i} value={i}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p>
            {data.eosType}
            {data.thermalType ? ` · ${data.thermalType}` : ""}
          </p>
          {data.references[data.reference] && (
            <p className="phase-assessment">
              {data.references[data.reference].detail}
            </p>
          )}
          {!data.eosEditable && (
            <p className="phase-condition-note">
              Published EoS record is read-only.
            </p>
          )}
          <div className="phase-editor-grid">
            {Object.entries(data.eosParameters).map(([p, v]) =>
              number(
                (
                  {
                    k0: "K₀",
                    k0p0: "K₀′",
                    k0pp0: "K₀″",
                    alpha_t0: "α(T₀)",
                    d_alpha_dt: "dα/dT",
                    dk0dt: "dK₀/dT",
                    dk0pdt: "dK₀′/dT",
                  } as Record<string, string>
                )[p],
                p,
                v,
                !data.eosEditable,
              ),
            )}
          </div>
        </fieldset>
        <fieldset>
          <legend>Reflections</legend>
          <div className="phase-reflection-actions">
            <button
              disabled={!ready || !data.editable}
              onClick={() => act("reflection", { action: "add" })}
            >
              Add
            </button>
            <button
              disabled={!ready || !data.editable || !selected.length}
              onClick={() => {
                act("reflection", { action: "remove", rows: selected });
                setSelected([]);
              }}
            >
              Delete
            </button>
            <button
              disabled={!ready || !data.editable || !data.reflections.length}
              onClick={() => {
                act("reflection", { action: "clear" });
                setSelected([]);
              }}
            >
              Clear
            </button>
          </div>
          <TableScroll className="phase-reflections-scroll">
            <DataTable aria-label="Phase reflections">
              <thead>
                <tr>
                  <th>Select</th>
                  {[
                    "h",
                    "k",
                    "l",
                    "Intensity",
                    "d₀ (Å)",
                    "d (Å)",
                    "2θ (°)",
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.reflections.map((r, row) => (
                  <tr key={row}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Select reflection ${row + 1}`}
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
                    {(["h", "k", "l", "intensity"] as const).map((p) => (
                      <td key={p}>
                        <PhaseNumber
                          label={`Reflection ${row + 1} ${p}`}
                          value={r[p]}
                          disabled={!ready || !data.editable}
                          step={p === "intensity" ? "any" : 1}
                          onCommit={(value) =>
                            act("reflection", {
                              action: "update",
                              row,
                              parameter: p,
                              value,
                            })
                          }
                        />
                      </td>
                    ))}
                    <td>{r.d0.toFixed(4)}</td>
                    <td>{r.d.toFixed(4)}</td>
                    <td>{r.twoTheta?.toFixed(4) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </TableScroll>
        </fieldset>
      </div>
      <footer>
        <button
          disabled={!ready || !data.canReload}
          onClick={() => act("reload")}
        >
          Reload File
        </button>
        <button
          disabled={!ready}
          onClick={() =>
            void run(
              "integration_phase_export",
              { index: data.index },
              "Saving phase…",
              () =>
                void run(
                  "integration_phase_editor",
                  { index: data.index },
                  "",
                  (r) => {
                    if (r.phaseEditor) onData(r.phaseEditor);
                  },
                ),
            )
          }
        >
          Save As…
        </button>
        <button onClick={onClose}>Close</button>
      </footer>
    </PhaseDialog>
  );
}

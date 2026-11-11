import { Button, Input, Select, Portal } from "./ui";
import { Dialog, DialogHeader } from "./Dialog";
import { PhaseDatabase } from "./PhaseDatabase";
import { isTauri } from "@tauri-apps/api/core";
import { openNativePhaseEditor } from "./phaseEditorWindow";
import type { EditorData } from "./phaseEditorTypes";
import { DataTable, TableScroll, TableActions } from "./DataTable";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Database, FolderOpen, Pencil, RotateCcw, Trash2 } from "lucide-react";
import type { IntegrationRun, IntegrationState } from "./integration";
import type {
  PhaseEditorData,
  PhaseImport,
  PhaseMaterial,
} from "./integrationPhase";
import { PhaseEditor } from "./PhaseEditor";
import { PhaseNumber } from "./PhaseNumber";
import { createPhaseCommandQueue } from "./phaseCommandQueue";
import "./integrationPhaseControls.css";

/** Keep Qt's action/table/steps arrangement while space permits. */
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
  const reference = (
    p: IntegrationState["phases"][number],
    index: number,
    label: string,
  ) => (
    <Select
      aria-label={label}
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
        <option key={i} value={i} title={p.referenceDetails[i]?.detail}>
          {["Not reproduced", "Do not use"].includes(
            p.referenceDetails[i]?.assessment,
          )
            ? "⚠ "
            : ""}
          {ref}
        </option>
      ))}
    </Select>
  );
  return (
    <div
      className="phase-controls"
      hidden={!active}
      data-testid="phase-controls"
    >
      <TableActions
        className="phase-toolbar"
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
        <PhaseIcon
          label="Removes currently selected phase"
          disabled={!phase}
          onClick={() => action("remove", { index: selected })}
        >
          <Trash2 />
        </PhaseIcon>
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
            <col className="phase-pressure-col" />
            <col className="phase-temperature-col" />
            <col className="phase-reference-col" />
          </colgroup>
          <thead>
            <tr>
              <th>
                <Button
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
                </Button>
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
              <th title="Temperature (K)">T (K)</th>
              <th className="phase-reference-cell">Ref</th>
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
                  <Input
                    type="checkbox"
                    aria-label={`Show phase ${index + 1}`}
                    checked={p.visible}
                    onChange={(e) =>
                      action("update", { index, visible: e.target.checked })
                    }
                  />
                </td>
                <td>
                  <Input
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
                  <div className="phase-condition-value">
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
                  </div>
                </td>
                <td>
                  <div className="phase-condition-value">
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
                  </div>
                </td>
                <td className="phase-reference-cell">
                  {reference(p, index, `Phase ${index + 1} reference`)}
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
      {phase && (
        <label className="phase-selected-reference">
          <span>Reference</span>
          {reference(phase, selected, "Selected phase reference")}
        </label>
      )}
      <div className="phase-parameters" aria-label="Phase conditions and lists">
        <span className="phase-step-caption">Step sizes</span>
        <div className="phase-step-controls">
          <label className="phase-condition-step">
            <span title="Pressure step">P step</span>
            <PhaseNumber
              label="P step"
              title="Pressure step (GPa)"
              multiply
              value={pressureStep}
              min={0.001}
              max={9999999}
              step={pressureStep}
              onCommit={setPressureStep}
            />
            <span className="integration-number-unit" aria-hidden="true">
              GPa
            </span>
          </label>
          <label className="phase-condition-step">
            <span title="Temperature step">T step</span>
            <PhaseNumber
              label="T Step"
              title="Temperature step (K)"
              multiply
              value={temperatureStep}
              min={1}
              max={1000}
              step={temperatureStep}
              onCommit={setTemperatureStep}
            />
            <span className="integration-number-unit" aria-hidden="true">
              K
            </span>
          </label>
        </div>
        <label
          className="phase-apply-all"
          title="Whether individual changes in P or T are applied to all other phases"
        >
          <Input
            type="checkbox"
            aria-label="Apply conditions to all phases"
            checked={source.sameConditions}
            onChange={(e) =>
              action("same_conditions", { enabled: e.target.checked })
            }
          />
          Apply P/T to all
        </label>

        <div className="phase-list-actions">
          <Button
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
          </Button>
          <Button
            onClick={() =>
              void run(
                "integration_phase_list",
                { save: false },
                "Loading phase list…",
              )
            }
          >
            Load List
          </Button>
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
    <Button
      type="button"
      aria-label={label}
      title={title}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </Button>
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
  return (
    <Portal>
      {
        <Dialog
          onDismiss={onClose}
          dialogRef={ref}
          className={`phase-dialog${wide ? " phase-dialog-wide" : ""}`}
          aria-label={title}
          onCancel={(e) => {
            e.preventDefault();
            onClose();
          }}
        >
          <DialogHeader
            title={title}
            closeLabel={`Close ${title}`}
            onClose={onClose}
          />
          {children}
        </Dialog>
      }
    </Portal>
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
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="primary"
          disabled={!ready}
          onClick={() =>
            onLoad({ intensity_cutoff: cutoff, minimum_d_spacing: spacing })
          }
        >
          OK
        </Button>
      </footer>
    </PhaseDialog>
  );
}

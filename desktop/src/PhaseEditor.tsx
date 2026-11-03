import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CopyPlus, ListX, Plus, Star, Trash2 } from "lucide-react";
import { DataTable, TableScroll } from "./DataTable";
import type { IntegrationRun } from "./integration";
import type { PhaseEditorData } from "./integrationPhase";
import type {
  EditorData,
  EditorField,
  EditorEdit as Edit,
} from "./phaseEditorTypes";
import { EditorNumber, TextEdit } from "./PhaseEditorFields";
import { PhaseEditorStructure } from "./PhaseEditorStructure";
import { PhaseEditorConfirm } from "./PhaseEditorConfirm";
import "./phaseEditor.css";

export function PhaseEditor({
  data: base,
  ready,
  run,
  onData,
  onClose,
  detached = false,
}: {
  data: PhaseEditorData;
  ready: boolean;
  run: IntegrationRun;
  onData: (v: PhaseEditorData) => void;
  onClose: () => void;
  detached?: boolean;
}) {
  const data = base as EditorData;
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const [tab, setTab] = useState("Volume & structure");
  const [positionView, setPositionView] = useState("d-angle");
  const positions = (
    [
      ["d0", "d₀ (Å)", "d"],
      ["d", "d (Å)", "d"],
      ["twoTheta0", "2θ₀ (°)", "angle"],
      ["twoTheta", "2θ (°)", "angle"],
      ["q0", "Q₀ (Å⁻¹)", "q"],
      ["q", "Q (Å⁻¹)", "q"],
    ] as const
  ).filter(
    ([, , group]) =>
      positionView === "all" ||
      positionView === group ||
      (positionView === "d-angle" && group !== "q"),
  );
  const columns = [
    ["h", "h"],
    ["k", "k"],
    ["l", "l"],
    ["intensity", "Intensity"],
    ...positions.map(([key, label]) => [key, label] as const),
  ] as const;
  const [selected, setSelected] = useState<number[]>([]);
  const [sort, setSort] = useState<{
    key: keyof EditorData["reflections"][number];
    direction: number;
  } | null>(null);
  const focusAddedReflection = useRef(false);
  const orderedRows = data.reflections.map((r, row) => ({ r, row }));
  if (sort)
    orderedRows.sort((a, b) => {
      const left = a.r[sort.key],
        right = b.r[sort.key];
      if (left == null) return right == null ? a.row - b.row : 1;
      if (right == null) return -1;
      return (left - right) * sort.direction || a.row - b.row;
    });
  const [lengthStep, setLengthStep] = useState(0.01);
  const [angleStep, setAngleStep] = useState(1);
  const [ratioStep, setRatioStep] = useState(0.01);
  const [legacy, setLegacy] = useState(data.thermalSelection === "alphakt");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(0);
  const [confirm, setConfirm] = useState("");
  const deleteRecord = useRef<HTMLButtonElement>(null);
  const clearRecords = useRef<HTMLButtonElement>(null);
  const clearReflections = useRef<HTMLButtonElement>(null);
  const queue = useRef(Promise.resolve());
  const content = useRef(data);
  content.current = data;
  useEffect(() => {
    returnFocus.current =
      document.activeElement === document.body
        ? document.querySelector<HTMLElement>(
            '.phase-action-rail button[aria-label="Edit selected Phase"]',
          )
        : (document.activeElement as HTMLElement);
    if (!detached) dialog.current?.showModal();
    return () => {
      if (!detached) dialog.current?.close();
      const target = returnFocus.current;
      requestAnimationFrame(() => target?.focus());
    };
  }, []);
  useEffect(() => {
    setSelected([]);
    setConfirm("");
    if (focusAddedReflection.current) {
      focusAddedReflection.current = false;
      const target = dialog.current?.querySelector<HTMLInputElement>(
        `input[aria-label="Reflection ${data.reflections.length} h"]`,
      );
      target?.focus();
      target?.select();
    }
  }, [data.index, data.reflections.length]);
  useEffect(() => {
    setLegacy(data.thermalSelection === "alphakt");
  }, [data.reference, data.thermalSelection]);
  useEffect(() => setConfirm(""), [data.uid, data.reference, tab]);
  const act: Edit = (operation, args = {}) => {
    const target = content.current;
    setPending((n) => n + 1);
    const result = queue.current.then(async () => {
      setMessage("");
      let accepted = false;
      let responded = false;
      await run(
        "integration_phase",
        {
          operation: "editor_transaction",
          edit_operation: operation,
          index: target.index,
          editor_uid: target.uid,
          editor: true,
          ...args,
        },
        "Updating phase…",
        (r) => {
          if (r.phaseEditor) {
            content.current = r.phaseEditor as EditorData;
            responded = true;
            onData(r.phaseEditor);
            const rejection = (r.phaseEditor as EditorData).editError;
            if (rejection) setMessage(`Edit not applied: ${rejection}`);
            accepted = !rejection;
          }
        },
      );
      if (!responded) {
        setMessage(
          "Edit was not applied. Previous values are restored; see the application message for details.",
        );
        await run(
          "integration_phase_editor",
          { index: target.index, editor_uid: target.uid },
          "",
          (r) => {
            if (r.phaseEditor) onData(r.phaseEditor);
          },
        );
      }
      setPending((n) => n - 1);
      return accepted;
    });
    queue.current = result.then(() => undefined);
    return result;
  };
  // Local edits are serialized without removing keyboard focus during processing.
  const locked = !ready && pending === 0;
  const field = (f: EditorField, thermal = false) => (
    <label
      className={`pe-field${f.choices?.length ? " pe-field-choice" : ""}${(f.unit?.length ?? 0) > 8 ? " pe-field-wide" : ""}`}
      key={`${data.index}-${data.reference}-${f.key}`}
    >
      <span title={f.description ? `${f.description} · ${f.key}` : f.key}>
        {f.label}
        {f.isDefault && (
          <sup className="pe-default" title="Model default">
            *
          </sup>
        )}
      </span>
      {!!f.choices?.length ? (
        <select
          aria-label={f.label}
          title={f.description}
          value={String(f.value ?? "")}
          disabled={locked || !data.eosEditable}
          onChange={(e) =>
            void act("editor_thermal_parameter", {
              parameter: f.key,
              value: e.target.value,
            })
          }
        >
          {f.choices.map((v) => (
            <option key={v} value={v}>
              {v.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      ) : (
        <EditorNumber
          label={f.label}
          value={f.value == null ? null : Number(f.value)}
          disabled={!data.eosEditable}
          min={f.min}
          max={f.max}
          integer={f.integer}
          optional={thermal && !f.required}
          title={
            thermal
              ? `${f.description ? `${f.description} · ` : ""}${f.key}${f.isDefault ? " · constructor default" : ""}${!f.required ? `; blank uses default ${f.default ?? "unset"}` : "; required"}`
              : f.key
          }
          onCommit={(value) =>
            act(
              thermal && data.thermalType
                ? "editor_thermal_parameter"
                : "editor_parameter",
              { parameter: f.key, value },
            )
          }
        />
      )}
      <span className="pe-unit">{f.unit}</span>
    </label>
  );
  const lattice = (key: string, label: string, unit: string, step: number) => (
    <label className="pe-field" key={key}>
      <span>{label}</span>
      <EditorNumber
        label={label}
        value={data.lattice[key]}
        disabled={!data.editable || !data.latticeEditable.includes(key)}
        min={key.includes("0") && key.length > 2 ? 0.001 : 0.000001}
        max={key.length > 2 ? 179.999 : 99999}
        step={step}
        stepper
        title={
          data.latticeEditable.includes(key)
            ? "Reference lattice; Enter or Tab applies"
            : "Constrained by symmetry"
        }
        onCommit={(value) => act("parameter", { parameter: key, value })}
      />
      <span className="pe-unit">{unit}</span>
    </label>
  );
  const ratioAllowed = (key: string) =>
    data.editable &&
    (key === "a/b" || key === "c/b"
      ? ["orthorhombic", "monoclinic", "triclinic"].includes(data.symmetry)
      : data.latticeEditable.includes("c0"));
  const removeReflections = () => {
    void act("reflection", { action: "remove", rows: selected });
    setSelected([]);
  };
  const close = () => {
    void queue.current.then(onClose);
  };
  const save = async (format?: string, overwrite = false) => {
    const invalid = dialog.current?.querySelector<HTMLInputElement>(
      '[aria-invalid="true"]',
    );
    if (invalid) {
      setMessage("Resolve the invalid value before saving.");
      const panel = invalid.closest('[role="tabpanel"]');
      if (panel)
        setTab(
          panel.id === "pe-page-0" ? "Volume & structure" : "Equation of state",
        );
      requestAnimationFrame(() => invalid.focus());
      return;
    }
    // A preceding blur has already queued its edit before this click.
    await queue.current;
    const applied = content.current;
    await run(
      "integration_phase_export",
      {
        index: applied.index,
        editor_uid: applied.uid,
        ...(format ? { format } : {}),
        save_current: overwrite && applied.canSaveCurrent,
        suggested_name: `${applied.materialName.replace(/[\/:*?"<>|]/g, "-").slice(0, 100) || "material"}.${format === "txt" ? "txt" : "eosmat"}`,
      },
      "Saving phase…",
      (result) => {
        if (result.cancelled) return;
        if (result.phaseEditor) onData(result.phaseEditor);
        setMessage(
          `${format === "txt" ? "Exported table" : "Saved"} ${result.savedPath?.split(/[\/]/).at(-1) || "material"}`,
        );
      },
    );
  };
  const Surface = detached ? "section" : "dialog";
  const surfaceContent = (
    <Surface
      ref={dialog}
      className={`phase-dialog pe-dialog${detached ? " pe-native" : ""}`}
      aria-label="Phase Editor"
      onCancel={(e) => {
        e.preventDefault();
        if (confirm) setConfirm("");
        else close();
      }}
    >
      {!detached && (
        <header>
          <h2>
            Phase Editor <span className="pe-material-name">· {data.name}</span>
          </h2>
          <button type="button" aria-label="Close Phase Editor" onClick={close}>
            ×
          </button>
        </header>
      )}
      <div className="pe-source">
        <label className="pe-material-name-field">
          Material name
          <TextEdit
            label="Material name"
            value={data.materialName}
            disabled={!data.editable}
            onCommit={(value) => act("editor_name", { value })}
          />
        </label>
        <div className="pe-file-state">
          <span>
            {data.origin === "bundled"
              ? "Bundled database"
              : data.filename
                ? "File"
                : "Unsaved material"}
          </span>
          {data.filename && data.origin !== "bundled" && (
            <input
              aria-label="Material file"
              readOnly
              value={data.filename}
              title={data.filename}
            />
          )}
          <span>
            {data.modified
              ? "Modified"
              : data.origin === "bundled"
                ? "Bundled material"
                : data.filename
                  ? data.canSaveCurrent
                    ? "Saved"
                    : "Loaded material"
                  : "Session values"}
          </span>
        </div>
      </div>
      <div className="pe-body">
        <section className="pe-parameters" aria-label="Phase parameters">
          <div className="pe-tabs" role="tablist" aria-label="Phase parameters">
            {["Volume & structure", "Equation of state"].map((name, i) => (
              <button
                key={name}
                role="tab"
                id={`pe-tab-${i}`}
                aria-selected={tab === name}
                aria-controls={`pe-page-${i}`}
                tabIndex={tab === name ? 0 : -1}
                onClick={() => setTab(name)}
                onKeyDown={(e) => {
                  if (
                    ["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)
                  ) {
                    e.preventDefault();
                    const next = i === 0 ? 1 : 0;
                    const index =
                      e.key === "Home" ? 0 : e.key === "End" ? 1 : next;
                    setTab(
                      index === 0 ? "Volume & structure" : "Equation of state",
                    );
                    dialog.current
                      ?.querySelector<HTMLButtonElement>(`#pe-tab-${index}`)
                      ?.focus();
                  }
                }}
              >
                {name}
              </button>
            ))}
          </div>
          <div
            className="pe-parameter-scroll"
            role="tabpanel"
            id="pe-page-0"
            aria-labelledby="pe-tab-0"
            hidden={tab !== "Volume & structure"}
          >
            {!data.editable && (
              <p className="pe-note">
                Bundled structure is read-only. Choose Edit a copy to change its
                lattice, atomic sites or reflections.
              </p>
            )}
            <label className="pe-selector">
              Symmetry{" "}
              <select
                aria-label="Phase symmetry"
                disabled={locked || !data.editable}
                value={data.symmetry}
                onChange={(e) =>
                  void act("parameter", {
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
                ].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <h3>Reference lattice</h3>
            <div className="pe-lattice-grid">
              {["a0", "b0", "c0"].map((p) =>
                lattice(p, `${p[0]}₀`, "Å", lengthStep),
              )}
              {["alpha0", "beta0", "gamma0"].map((p, i) =>
                lattice(p, ["α₀", "β₀", "γ₀"][i], "°", angleStep),
              )}
            </div>
            <div className="pe-lattice-grid pe-ratios">
              {["a/b", "c/a", "c/b"].map((key) => (
                <label className="pe-field" key={key}>
                  <span>{key}</span>
                  <EditorNumber
                    label={key}
                    value={
                      data.lattice[`${key[0]}0`] / data.lattice[`${key[2]}0`]
                    }
                    disabled={!ratioAllowed(key)}
                    min={0.000001}
                    step={ratioStep}
                    stepper
                    title="Ratio of reference lattice lengths; changes the numerator length"
                    onCommit={(value) =>
                      act("editor_ratio", { parameter: key, value })
                    }
                  />
                  <span className="pe-unit" aria-hidden="true" />
                </label>
              ))}
            </div>
            <div className="pe-steps">
              <span>Steps</span>
              {[
                ["Length", lengthStep, setLengthStep, "Å"],
                ["Angle", angleStep, setAngleStep, "°"],
                ["Ratio", ratioStep, setRatioStep, ""],
              ].map(([label, value, setter, unit]) => (
                <label key={String(label)}>
                  {String(label)}
                  <EditorNumber
                    label={`Lattice ${String(label).toLowerCase()} step`}
                    value={Number(value)}
                    min={0.000001}
                    onCommit={(n) => {
                      (setter as (n: number) => void)(n!);
                    }}
                  />
                  {String(unit)}
                </label>
              ))}
            </div>
            <h3
              title={
                data.coldPressure
                  ? "Input cold pressure at the thermal EoS reference temperature"
                  : "Current pressure and temperature"
              }
            >
              {data.coldPressure ? "P₀ = " : "At "}
              {data.pressure.toLocaleString()} GPa ·{" "}
              {data.temperature.toLocaleString()} K
            </h3>
            <div className="pe-lattice-grid">
              {["a", "b", "c", "v0", "v"].map((p) => (
                <label className="pe-field" key={p}>
                  <span>{p === "v0" ? "V₀" : p === "v" ? "V" : p}</span>
                  <input
                    aria-label={`Current lattice ${p}`}
                    readOnly
                    value={data.lattice[p].toPrecision(8)}
                    title={String(data.lattice[p])}
                  />
                  <span className="pe-unit">
                    {p.startsWith("v") ? "Å³" : "Å"}
                  </span>
                </label>
              ))}
            </div>
            <PhaseEditorStructure data={data} locked={locked} act={act} />
          </div>
          <div
            className="pe-parameter-scroll pe-eos-page"
            role="tabpanel"
            id="pe-page-1"
            aria-labelledby="pe-tab-1"
            hidden={tab !== "Equation of state"}
          >
            {!!data.references.length && (
              <>
                <label className="pe-selector">
                  EoS record{" "}
                  <select
                    aria-label="Editor material record"
                    value={data.reference}
                    disabled={locked}
                    onChange={(e) =>
                      void act("update", { reference: Number(e.target.value) })
                    }
                  >
                    {data.references.map((r, i) => (
                      <option key={i} value={i}>
                        {r.label}
                        {i === data.defaultReference ? " · default" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="pe-record-state">
                  {data.recordOrigin === "bundled"
                    ? "Published record · read-only"
                    : `${data.recordOrigin || "User"} record · editable`}{" "}
                  · {data.references[data.reference]?.assessment}
                </p>
                <details className="pe-record-details">
                  <summary>Reference &amp; scientific assessment</summary>
                  <p>{data.references[data.reference]?.detail}</p>
                </details>
              </>
            )}
            <div
              className="pe-record-actions"
              role="toolbar"
              aria-label="EoS records"
            >
              <button
                type="button"
                aria-label="Duplicate as custom"
                title="Duplicate this EoS as a custom record"
                disabled={locked || !data.references.length}
                onClick={() =>
                  void act("editor_record", { action: "duplicate" })
                }
              >
                <CopyPlus aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label="Add record"
                title="Add an EoS record from the current parameters"
                disabled={locked}
                onClick={() => void act("editor_record", { action: "add" })}
              >
                <Plus aria-hidden="true" />
              </button>
              <button
                type="button"
                aria-label="Set default"
                aria-pressed={
                  !!data.references.length &&
                  data.defaultReference === data.reference
                }
                title="Set this EoS as the default"
                disabled={
                  locked ||
                  !data.eosEditable ||
                  !data.references.length ||
                  data.defaultReference === data.reference
                }
                onClick={() => void act("editor_record", { action: "default" })}
              >
                <Star aria-hidden="true" />
              </button>
              <button
                ref={deleteRecord}
                type="button"
                aria-label="Delete record…"
                title="Delete this EoS record"
                disabled={
                  locked || !data.eosEditable || !data.references.length
                }
                onClick={() => setConfirm("record")}
              >
                <Trash2 aria-hidden="true" />
              </button>
              <button
                ref={clearRecords}
                type="button"
                aria-label="Clear all records…"
                disabled={locked || !data.editable || !data.references.length}
                title={
                  data.editable
                    ? "Keep the structure and remove all EoS records"
                    : "Edit a copy to clear its EoS records"
                }
                onClick={() => setConfirm("records")}
              >
                <ListX aria-hidden="true" />
              </button>
            </div>
            {data.eosEditable && !!data.references.length && (
              <label className="pe-selector">
                EoS name
                <TextEdit
                  key={`${data.index}-${data.reference}`}
                  label="EoS name"
                  value={data.recordLabel}
                  disabled={locked}
                  onCommit={(value) =>
                    act("editor_record", { action: "rename", value })
                  }
                />
              </label>
            )}
            {!data.eosEditable && (
              <p className="pe-note">
                Published record. Duplicate as custom to edit its parameters.
              </p>
            )}
            <label className="pe-selector">
              EoS{" "}
              <select
                aria-label="Equation of state model"
                value={data.eosType}
                disabled={locked || !data.eosEditable}
                onChange={(e) =>
                  void act("editor_eos_type", { value: e.target.value })
                }
              >
                {!data.eosOptions.some((o) => o.value === data.eosType) && (
                  <option>{data.eosType}</option>
                )}
                {data.eosOptions.map((o) => (
                  <option
                    key={o.value}
                    value={o.value}
                    disabled={!!o.error}
                    title={o.error}
                  >
                    {o.value}
                  </option>
                ))}
              </select>
            </label>
            <div
              className="pe-eos-fields"
              role="group"
              aria-label="Equation of state parameters"
            >
              {data.eosFields.map((f) => field(f))}
            </div>
            {!!data.materialFields.length && (
              <details className="pe-record-details">
                <summary>Material normalization data</summary>
                <p>
                  n: atoms per formula; Z electrons: electrons per formula; Z
                  cell: formula units per cell used by the EoS. Structural edits
                  retain these values.
                </p>
                <div
                  className="pe-eos-fields"
                  role="group"
                  aria-label="Material normalization parameters"
                >
                  {data.materialFields.map((f) => field(f))}
                </div>
              </details>
            )}
            {data.recordData && (
              <details className="pe-record-details">
                <summary>Complete record metadata</summary>
                <p>
                  Source parameters, reported errors, fixed parameters, scope
                  and provenance are retained in the material file.
                </p>
                <pre className="pe-record-json">
                  {JSON.stringify(data.recordData, null, 2)}
                </pre>
              </details>
            )}
            <label className="pe-selector">
              Thermal model{" "}
              <select
                aria-label="Thermal model"
                value={
                  !data.thermalType && legacy
                    ? "alphakt"
                    : data.thermalSelection
                }
                disabled={locked || !data.eosEditable}
                onChange={(e) => {
                  const value = e.target.value;
                  setLegacy(value === "alphakt");
                  if (value !== "alphakt" || data.thermalType)
                    void act("editor_thermal_type", { value });
                }}
              >
                {!data.thermalOptions.some(
                  (o) => o.value === data.thermalSelection,
                ) && <option>{data.thermalSelection}</option>}
                {data.thermalOptions.map((o) => (
                  <option
                    key={o.value}
                    value={o.value}
                    disabled={!!o.error}
                    title={o.error}
                  >
                    {o.value === "none"
                      ? "None"
                      : o.value === "alphakt"
                        ? "Legacy α, dK/dT correction"
                        : o.value}
                  </option>
                ))}
              </select>
            </label>
            {(data.thermalType || legacy) && (
              <>
                <details className="pe-record-details">
                  <summary>Parameter defaults</summary>
                  <p>
                    {data.thermalType
                      ? "Blank optional fields use the model default. Selecting another thermal model initializes starting estimates."
                      : "Legacy constant-coefficient correction."}
                  </p>
                </details>
                <div
                  className="pe-eos-fields"
                  role="group"
                  aria-label="Thermal parameters"
                >
                  {data.thermalFields.map((f) => field(f, !!data.thermalType))}
                </div>
              </>
            )}
          </div>
        </section>
        <section className="pe-reflections" aria-label="HKL reflections">
          <div className="pe-reflection-heading">
            <h3>
              HKL reflections <span>{data.reflections.length}</span>
            </h3>
            <span>
              {selected.length
                ? `${selected.length} selected`
                : "h, k, l and intensity editable"}
            </span>
          </div>
          <label className="pe-position-choice">
            Positions{" "}
            <select
              aria-label="Reflection position columns"
              value={positionView}
              onChange={(e) => setPositionView(e.target.value)}
            >
              <option value="d-angle">d + 2θ</option>
              <option value="d">d only</option>
              <option value="angle">2θ only</option>
              <option value="q">Q only</option>
              <option value="all">All positions</option>
            </select>
          </label>
          <TableScroll
            className="pe-reflection-scroll"
            tabIndex={0}
            onKeyDown={(e) => {
              if ((e.target as HTMLElement).closest("input")) return;
              if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a") {
                e.preventDefault();
                setSelected(data.reflections.map((_, i) => i));
              }
              if (
                (e.key === "Delete" || e.key === "Backspace") &&
                data.editable &&
                !locked &&
                selected.length
              ) {
                e.preventDefault();
                removeReflections();
              }
            }}
            onCopy={(e) => {
              if ((e.target as HTMLElement).closest("input")) return;
              const rows = orderedRows
                .filter(({ row }) => !selected.length || selected.includes(row))
                .map(({ row }) => row);
              e.clipboardData.setData(
                "text/plain",
                [
                  columns.map(([, label]) => label).join("\t"),
                  ...rows.map((i) =>
                    columns
                      .map(([key]) => data.reflections[i][key] ?? "")
                      .join("\t"),
                  ),
                ].join("\n"),
              );
              e.preventDefault();
            }}
          >
            <DataTable
              aria-label="Phase reflections"
              data-position-columns={positions.length}
            >
              <colgroup>
                <col className="pe-check-col" />
                <col className="pe-index-col" />
                <col className="pe-index-col" />
                <col className="pe-index-col" />
                <col className="pe-intensity-col" />
                {positions.map(([key]) => (
                  <col className="pe-position-col" key={key} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      aria-label="Select all reflections"
                      checked={
                        !!data.reflections.length &&
                        selected.length === data.reflections.length
                      }
                      onChange={(e) =>
                        setSelected(
                          e.target.checked
                            ? data.reflections.map((_, i) => i)
                            : [],
                        )
                      }
                    />
                  </th>
                  {columns.map(([key, label]) => (
                    <th
                      key={key}
                      aria-sort={
                        sort?.key === key
                          ? sort.direction === 1
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                    >
                      <button
                        className="pe-sort"
                        title={`Sort by ${label}`}
                        onClick={() =>
                          setSort((s) => ({
                            key,
                            direction: s?.key === key ? -s.direction : 1,
                          }))
                        }
                      >
                        {label}
                        {sort?.key === key
                          ? sort.direction === 1
                            ? " ↑"
                            : " ↓"
                          : ""}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody key={`${data.index}-${data.reflections.length}`}>
                {orderedRows.map(({ r, row }) => (
                  <tr key={row} aria-selected={selected.includes(row)}>
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
                      <td
                        key={p}
                        className={
                          p === "intensity"
                            ? "pe-intensity-cell"
                            : "pe-index-cell"
                        }
                      >
                        <EditorNumber
                          label={`Reflection ${row + 1} ${p}`}
                          value={r[p]}
                          significantDigits={p === "intensity" ? 4 : undefined}
                          disabled={!data.editable}
                          min={p === "intensity" ? 0 : -10000}
                          max={p === "intensity" ? 1e9 : 10000}
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
                    {positions.map(([key]) => (
                      <td
                        key={key}
                        title={
                          r[key] == null
                            ? "Unavailable at the session wavelength"
                            : String(r[key])
                        }
                      >
                        {r[key]?.toFixed(4) ?? "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </DataTable>
            {!data.reflections.length && (
              <p className="pe-help">
                No reflections. Add a reflection or reload the source file.
              </p>
            )}
          </TableScroll>
          <div className="pe-reflection-actions">
            <button
              disabled={locked || !data.editable}
              onClick={() => {
                focusAddedReflection.current = true;
                void act("reflection", { action: "add" }).then((ok) => {
                  if (!ok) focusAddedReflection.current = false;
                });
              }}
            >
              Add
            </button>
            <button
              disabled={locked || !data.editable || !selected.length}
              onClick={removeReflections}
            >
              Delete
            </button>
            <button
              ref={clearReflections}
              disabled={locked || !data.editable || !data.reflections.length}
              onClick={() => setConfirm("reflections")}
            >
              Clear…
            </button>
            <button
              disabled={locked || !data.reflections.length}
              onClick={() => void save("txt")}
            >
              Export table…
            </button>
          </div>
          <p className="pe-help">
            ₀: reference · unmarked: current P/T. Intensities: 4 significant
            digits; full precision on focus.
          </p>
        </section>
      </div>
      {confirm && (
        <PhaseEditorConfirm
          anchor={
            confirm === "record"
              ? deleteRecord.current
              : confirm === "records"
                ? clearRecords.current
                : clearReflections.current
          }
          title={
            confirm === "record"
              ? "Delete EoS record?"
              : confirm === "records"
                ? "Clear all EoS records?"
                : "Clear all reflections?"
          }
          detail={
            confirm === "record"
              ? `Delete “${data.recordLabel}” and its dataset links?`
              : confirm === "records"
                ? "Remove every EoS record and its dataset links. The lattice and atomic sites are kept."
                : "Remove every reflection from this material?"
          }
          action={
            confirm === "records" ? "Clear all records" : "Confirm delete"
          }
          onCancel={() => setConfirm("")}
          onConfirm={() => {
            void act(
              confirm === "reflections" ? "reflection" : "editor_record",
              {
                action: confirm === "record" ? "delete" : "clear",
              },
            );
            setConfirm("");
          }}
        />
      )}
      <footer>
        <p className={message ? "pe-edit-error" : "pe-status"} role="status">
          {message ||
            (pending
              ? "Applying edit…"
              : data.modified
                ? "Unsaved changes"
                : data.filename
                  ? "Saved"
                  : "Session material")}
        </p>
        <button
          disabled={locked || !data.canReload}
          onClick={() => void act("reload")}
        >
          Reload File
        </button>
        <button
          disabled={locked}
          title="Create an independent editable material"
          onClick={() => void act("editor_copy")}
        >
          Edit a copy
        </button>
        <button
          className="primary"
          title={
            data.editable
              ? "Save this material"
              : "Use Edit a copy to create an editable material"
          }
          disabled={
            locked || !data.editable || (!data.modified && data.canSaveCurrent)
          }
          onClick={() => void save("eosmat", data.canSaveCurrent)}
        >
          Save
        </button>
        <button
          disabled={locked}
          title="Save .eosmat to retain EoS records, provenance and atomic positions"
          onClick={() => void save("eosmat")}
        >
          Save As…
        </button>
        <button onClick={close}>Close</button>
      </footer>
    </Surface>
  );
  return detached
    ? surfaceContent
    : createPortal(
        surfaceContent,
        document.querySelector(".app") || document.body,
      );
}

import { useRef, useState } from "react";
import { Check } from "lucide-react";
import { Dialog, DialogHeader } from "./Dialog";
import { TabList } from "./TabList";
import { ScientificNumberInput } from "./ScientificNumberInput";
import {
  pyfaiFields,
  fit2dFields,
  useGeometryDraft,
  type GeometryDraft,
} from "./geometryDraft";
import type { Calibration } from "./types";
type Run = (
  command: string,
  args?: Record<string, unknown>,
  message?: string,
) => unknown;

export function GeometryEditor({
  editor,
  ready,
  run,
  open = false,
  embedded = false,
  formId,
  convention: savedConvention,
  onConventionChange,
}: {
  editor: GeometryDraft;
  ready: boolean;
  run: Run;
  open?: boolean;
  embedded?: boolean;
  formId?: string;
  convention?: "pyfai" | "fit2d";
  onConventionChange?: (convention: "pyfai" | "fit2d") => void;
}) {
  const [localConvention, setLocalConvention] = useState<"pyfai" | "fit2d">(
    "pyfai",
  );
  const convention = savedConvention ?? localConvention;
  const setConvention = (value: "pyfai" | "fit2d") => {
    setLocalConvention(value);
    onConventionChange?.(value);
  };
  const { calibration: c, drafts, setDrafts, changed, dirty, reset } = editor;
  const fields = convention === "pyfai" ? pyfaiFields : fit2dFields;
  const draft = drafts[convention];
  const activeDirty = changed(convention);
  const otherConvention = convention === "pyfai" ? "fit2d" : "pyfai";
  const otherDirty = changed(otherConvention);
  const applyGeometry = () => {
    if (!activeDirty) return;
    return run(
      "manual_geometry",
      {
        convention,
        values: Object.fromEntries(
          fields.map(([key, , , factor]) => [
            key,
            Number(draft[key]) === (c?.[convention]?.[key] ?? 0) * factor
              ? (c?.[convention]?.[key] ?? 0)
              : Number(draft[key]) / factor,
          ]),
        ),
      },
      "Applying geometry…",
    );
  };
  const content = (
    <>
      <TabList
        className="geometry-tabs"
        label="Geometry convention"
        value={convention}
        onChange={setConvention}
        options={(["pyfai", "fit2d"] as const).map((value) => ({
          value,
          name: value === "pyfai" ? "pyFAI" : "Fit2D",
          label: (
            <>
              {value === "pyfai" ? "pyFAI" : "Fit2D"}
              {changed(value) && (
                <span className="geometry-draft-marker" aria-hidden="true">
                  {" "}
                  ·
                </span>
              )}
            </>
          ),
          description: changed(value) ? "Unapplied geometry draft" : undefined,
          title: changed(value)
            ? `${value === "pyfai" ? "pyFAI" : "Fit2D"} · unapplied changes`
            : undefined,
        }))}
      />
      {dirty && (
        <p className="control-note">
          {otherDirty
            ? `${otherConvention === "pyfai" ? "pyFAI" : "Fit2D"} has unapplied edits. Return there to apply or reset; this convention remains available for comparison.`
            : "Apply or reset this geometry draft before editing the other convention."}
        </p>
      )}
      {fields.map(([key, label, unit]) => (
        <label className="geometry-field" key={key}>
          <span>{label}</span>
          <ScientificNumberInput
            aria-label={`Manual ${label.toLowerCase()}`}
            required
            type="number"
            step="any"
            disabled={!ready}
            readOnly={otherDirty}
            aria-description={
              otherDirty
                ? "Comparison only while the other convention has pending edits"
                : undefined
            }
            title={draft[key] ?? ""}
            value={draft[key] ?? ""}
            onValueChange={(value) =>
              setDrafts((values) => ({
                ...values,
                [convention]: { ...values[convention], [key]: value },
              }))
            }
          />
          <span className="calibration-unit">{unit}</span>
        </label>
      ))}
      {!formId && (
        <>
          <button
            type="button"
            className="secondary full-input"
            disabled={
              !ready ||
              !activeDirty ||
              fields.some(
                ([key]) =>
                  draft[key] === "" || !Number.isFinite(Number(draft[key])),
              )
            }
            onClick={applyGeometry}
          >
            <Check size={14} />
            Apply geometry
          </button>
        </>
      )}
      {activeDirty && (
        <button
          type="button"
          className="quiet full-input"
          onClick={() => reset(convention)}
        >
          Reset geometry draft
        </button>
      )}
    </>
  );
  return embedded ? (
    <section className="geometry-editor">
      {formId ? (
        <form
          id={formId}
          onSubmit={(event) => {
            event.preventDefault();
            if (ready) applyGeometry();
          }}
        >
          {content}
        </form>
      ) : (
        content
      )}
    </section>
  ) : (
    <details className="compact-section" open={open}>
      <summary>Manual geometry · pyFAI / Fit2D</summary>
      {content}
    </details>
  );
}

export function ManualGeometryDialog({
  calibration,
  ready,
  run,
  onClose,
}: {
  calibration?: Calibration;
  ready: boolean;
  run: Run;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const editor = useGeometryDraft(calibration);
  return (
    <Dialog
      dialogRef={dialog}
      className="manual-geometry-dialog"
      aria-label="Enter calibration manually"
      onDismiss={onClose}
      onClose={onClose}
    >
      <DialogHeader
        title="Enter calibration manually"
        closeLabel="Close manual geometry"
        onClose={onClose}
      />
      <GeometryEditor editor={editor} ready={ready} run={run} embedded />
    </Dialog>
  );
}

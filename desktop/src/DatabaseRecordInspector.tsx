import { useState } from "react";
import { DataTable } from "./DataTable";
import type { DatabaseMaterial, DatabaseRecord } from "./phaseDatabaseTypes";
import type { IntegrationRun } from "./integration";

const valueText = (value: unknown) =>
  value == null
    ? "—"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);

export function DatabaseRecordInspector({
  material,
  record,
  reference,
  run,
  ready,
}: {
  material: DatabaseMaterial | undefined;
  record: DatabaseRecord | undefined;
  reference: number;
  run: IntegrationRun;
  ready: boolean;
}) {
  const [inspect, setInspect] = useState("Assessment & source");
  return (
    <section
      className="phase-database-inspector"
      aria-label="Selected record inspection"
    >
      <div className="phase-database-heading">
        <div role="tablist" aria-label="Record inspection">
          {["Assessment & source", "Parameters", "Original record"].map(
            (name) => (
              <button
                key={name}
                role="tab"
                aria-selected={inspect === name}
                tabIndex={inspect === name ? 0 : -1}
                onKeyDown={(e) => {
                  const names = [
                    "Assessment & source",
                    "Parameters",
                    "Original record",
                  ];
                  const i = names.indexOf(name);
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
                  setInspect(names[next]);
                  (
                    e.currentTarget.parentElement?.children[next] as HTMLElement
                  )?.focus();
                }}
                onClick={() => setInspect(name)}
              >
                {name}
              </button>
            ),
          )}
        </div>
        <div className="phase-database-links">
          {record?.reportUrl && (
            <button
              disabled={!ready}
              onClick={() =>
                void run(
                  "integration_phase_documentation",
                  { material_id: material!.id, reference, kind: "report" },
                  "Opening reconstruction report…",
                )
              }
            >
              Reconstruction report ↗
            </button>
          )}
          {record?.recordUrl && (
            <button
              disabled={!ready}
              onClick={() =>
                void run(
                  "integration_phase_documentation",
                  { material_id: material!.id, reference, kind: "record" },
                  "Opening Peritheos record…",
                )
              }
            >
              View in Peritheos ↗
            </button>
          )}
        </div>
      </div>
      <div
        className="phase-database-detail"
        role="tabpanel"
        aria-label={inspect}
        tabIndex={0}
        key={`${material?.id}-${reference}-${inspect}`}
      >
        {inspect === "Assessment & source" ? (
          <>
            {record && (
              <>
                <h4>{record.label}</h4>
                <p className="phase-assessment">{record.detail}</p>
                {record.notes && (
                  <p className="phase-assessment">{record.notes}</p>
                )}
                <dl>
                  <dt>Thermal model</dt>
                  <dd>{record.thermal || "None recorded"}</dd>
                  <dt>Fit temperature</dt>
                  <dd>
                    {record.temperatureRange
                      ? `${record.temperatureRange.join("–")} K`
                      : "Not recorded"}
                  </dd>
                  <dt>Reference temperature</dt>
                  <dd>
                    {record.temperatureRef == null
                      ? "Not recorded"
                      : `${record.temperatureRef} K`}
                  </dd>
                </dl>
              </>
            )}
            {material?.notes && (
              <p className="phase-assessment">{material.notes}</p>
            )}
            {!record && (
              <p>
                {material?.hold ||
                  "Select an EoS record to inspect its assessment and source."}
              </p>
            )}
          </>
        ) : inspect === "Original record" ? (
          <pre>
            {record
              ? JSON.stringify(record.sourceRecord, null, 2)
              : "Select an EoS record."}
          </pre>
        ) : record ? (
          <>
            <p>
              Values retain source parameter names and units. ± denotes a
              reported error; “error n/r” means no verified error is recorded,
              not zero. See Original record for model configuration and unit
              metadata.
            </p>
            <DataTable aria-label="Selected record parameters">
              <thead>
                <tr>
                  <th>Part</th>
                  <th>Parameter</th>
                  <th>Source value</th>
                  <th>Reported error</th>
                  <th>Fixed</th>
                </tr>
              </thead>
              <tbody>
                {[
                  {
                    part: "EoS",
                    params: record.parameters,
                    errors: record.errors,
                    fixed: record.fixed,
                  },
                  {
                    part: "Thermal",
                    params: record.thermalParameters,
                    errors: record.thermalErrors,
                    fixed: record.thermalFixed,
                  },
                ].flatMap(({ part, params, errors, fixed }) =>
                  Object.entries(params).map(([key, value]) => (
                    <tr key={`${part}-${key}`}>
                      <td>{part}</td>
                      <td>{key}</td>
                      <td>{valueText(value)}</td>
                      <td>
                        {errors[key] == null ? "n/r" : valueText(errors[key])}
                      </td>
                      <td>{fixed.includes(key) ? "Yes" : "—"}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </DataTable>
          </>
        ) : (
          <p>Select an EoS record to inspect its parameters.</p>
        )}
      </div>
    </section>
  );
}

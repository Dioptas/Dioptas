import { useEffect, useRef, useState } from "react";
import { Input, Select } from "./ui";
import type { State } from "./types";
import type { CorrectionMaterial, IntegrationRun } from "./integration";
import {
  ProcessingToggle,
  ProcessingFile,
  ProcessingNumberField,
  ProcessingType,
} from "./IntegrationProcessingFields";
import "./integrationProcessingControls.css";

const groups = [
  [
    "Geometry",
    [
      "diamond_thickness",
      "seat_thickness",
      "small_cbn_seat_radius",
      "large_cbn_seat_radius",
    ],
  ],
  [
    "Alignment",
    ["tilt", "tilt_rotation", "center_offset", "center_offset_angle"],
  ],
  ["Absorption", ["diamond_abs_length", "cbn_abs_length"]],
] as const;

export function IntegrationCorrectionControls({
  state,
  run,
  tab,
  onTabChange,
}: {
  tab: string;
  onTabChange: (tab: string) => void;
  state: State;
  run: IntegrationRun;
}) {
  const source = state.integration;
  const [inactiveParameters, setInactiveParameters] = useState<
    Record<string, Record<string, number>>
  >({});
  const [switching, setSwitching] = useState<string | null>(null);
  const current = useRef(source.corrections);
  current.current = source.corrections;
  const tail = useRef(Promise.resolve());
  // Merge each complete edit against the previous successful result, so rapid
  // Tab/Enter edits cannot overwrite a preceding parameter with a stale value.
  const edit = (
    kind: string,
    patch: {
      enabled?: boolean;
      parameters?: Record<string, number>;
      material?: Partial<CorrectionMaterial>;
    },
  ) => {
    const task = tail.current.then(() => {
      const correction = current.current[kind];
      return run(
        "integration_correction",
        {
          kind,
          enabled: patch.enabled ?? correction.enabled,
          parameters: { ...correction.parameters, ...patch.parameters },
          ...(patch.material
            ? { material: { ...correction.material, ...patch.material } }
            : {}),
        },
        "",
        (response) => {
          if (response.state) {
            current.current = response.state.integration.corrections;
            const applied = current.current[kind];
            if (applied.enabled)
              setInactiveParameters((previous) => ({
                ...previous,
                [kind]: applied.parameters,
              }));
          }
        },
      );
    });
    tail.current = task.catch(() => {});
    return task;
  };
  const correction = source.corrections[tab];
  const name = (
    {
      cbn: "cBN seat",
      oiadac: "detector absorption",
      plate: "plate absorption",
      slab: "slab self-absorption",
    } as Record<string, string>
  )[tab];
  const field = (key: string) => {
    if (
      key === "absorption_coefficient" &&
      correction.material?.mode === "formula" &&
      !correction.enabled
    )
      return null;
    const definition = correction.fields[key];
    return (
      <ProcessingNumberField
        key={key}
        label={definition.label}
        value={
          correction.enabled
            ? correction.parameters[key]
            : (inactiveParameters[tab] ?? correction.parameters)[key]
        }
        min={definition.min}
        max={definition.max}
        disabled={
          !state.hasImage ||
          switching === tab ||
          (key === "absorption_coefficient" &&
            correction.material?.mode === "formula")
        }
        onCommit={async (value) => {
          if (correction.enabled)
            await edit(tab, { parameters: { [key]: value } });
          else
            setInactiveParameters((previous) => ({
              ...previous,
              [tab]: {
                ...(previous[tab] ?? correction.parameters),
                [key]: value,
              },
            }));
        }}
      />
    );
  };
  return (
    <>
      <nav
        className="integration-subnav processing-subnav"
        aria-label="Correction type"
      >
        {[
          ["flat", "Flat field"],
          ["transfer", "Transfer"],
          ["plate", "Plate"],
          ["slab", "Slab"],
          ["cbn", "cBN seat"],
          ["oiadac", "Detector absorption"],
        ].map(([key, label]) => (
          <ProcessingType
            key={key}
            label={label}
            selected={tab === key}
            active={
              key === "flat"
                ? source.flatField.enabled
                : key === "transfer"
                  ? (source.transfer?.enabled ?? false)
                  : (source.corrections[key]?.enabled ?? false)
            }
            onClick={() => onTabChange(key)}
          />
        ))}
      </nav>
      <div className="processing-page">
        {tab === "flat" ? (
          <div className="processing-form">
            <ProcessingFile
              kind="flat field"
              filename={source.flatField.filename}
              disabled={!state.hasImage}
              onLoad={() => void run("integration_flat_field")}
              onRemove={() =>
                void run("integration_flat_field", { reset: true })
              }
            />
            <ProcessingToggle
              label="Apply flat field"
              checked={source.flatField.enabled}
              disabled={!source.flatField.filename}
              onCommit={(enabled) =>
                run("integration_flat_field", { enabled }, "")
              }
            />
            <p className="integration-note">
              Corrects pixel sensitivity using the mean-normalized flat field.
            </p>
          </div>
        ) : tab === "transfer" ? (
          <div className="processing-form">
            {(["original", "response"] as const).map((sourceName) => (
              <ProcessingFile
                key={sourceName}
                kind={`transfer ${sourceName}`}
                filename={source.transfer?.[sourceName] ?? null}
                disabled={!state.hasImage}
                onLoad={() =>
                  void run("integration_transfer", { source: sourceName })
                }
                onRemove={() =>
                  void run("integration_transfer", {
                    source: sourceName,
                    reset: true,
                  })
                }
              />
            ))}
            <ProcessingToggle
              label="Apply transfer correction"
              checked={source.transfer?.enabled ?? false}
              disabled={
                !source.transfer?.original || !source.transfer?.response
              }
              onCommit={(enabled) =>
                run("integration_transfer", { enabled }, "")
              }
            />
            <p className="integration-note">
              Multiplies counts by original / response. Both references need the
              detector’s source dimensions and finite, positive counts.
            </p>
          </div>
        ) : !correction ? (
          <p className="integration-note">
            This correction is unavailable in the selected processor.
          </p>
        ) : (
          <div className="processing-form">
            <ProcessingToggle
              key={tab}
              label={`Apply ${name}`}
              checked={correction.enabled}
              disabled={!state.hasImage || !state.calibrated}
              onCommit={async (enabled) => {
                setSwitching(tab);
                if (!enabled)
                  setInactiveParameters((previous) => ({
                    ...previous,
                    [tab]: correction.parameters,
                  }));
                try {
                  await edit(tab, {
                    enabled,
                    parameters: enabled ? inactiveParameters[tab] : undefined,
                  });
                } finally {
                  setSwitching(null);
                }
              }}
            />
            {!correction.enabled && state.calibrated && (
              <p className="integration-note">
                Enable to apply these parameters.
              </p>
            )}
            {!state.calibrated && (
              <p className="integration-note">
                Load an image and calibration to use this correction.
              </p>
            )}
            {(tab === "plate" || tab === "slab") && correction.material && (
              <MaterialControls
                key={`material-${tab}`}
                material={correction.material}
                disabled={!state.hasImage || switching === tab}
                onCommit={(material) => edit(tab, { material })}
              />
            )}
            {(tab === "plate" || tab === "slab") && (
              <p className="integration-note">
                {tab === "plate"
                  ? "Absorption by a plate in the diffracted beam."
                  : "Self-absorption integrated through a uniformly scattering slab."}{" "}
                Tilt is relative to the incident beam; rotation is about the
                beam.
              </p>
            )}
            {tab === "cbn" ? (
              groups.map(([title, keys]) => (
                <section
                  key={title}
                  className="processing-parameter-group"
                  aria-label={title}
                >
                  <h3>{title}</h3>
                  <div className="processing-parameter-grid">
                    {keys.map(field)}
                  </div>
                </section>
              ))
            ) : (
              <div className="processing-parameter-grid">
                {Object.keys(correction.fields).map(field)}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

function MaterialControls({
  material,
  disabled,
  onCommit,
}: {
  material: CorrectionMaterial;
  disabled: boolean;
  onCommit: (patch: Partial<CorrectionMaterial>) => Promise<void>;
}) {
  const [formula, setFormula] = useState(material.formula);
  useEffect(() => setFormula(material.formula), [material.formula]);
  return (
    <>
      <label className="field-label processing-material-input">
        <span>Attenuation source</span>
        <Select
          aria-label="Attenuation source"
          value={material.mode}
          disabled={disabled}
          onChange={(e) =>
            void onCommit({
              mode: e.currentTarget.value as CorrectionMaterial["mode"],
            })
          }
        >
          <option value="manual">Enter μ</option>
          <option value="formula">Formula</option>
        </Select>
      </label>
      {material.mode === "formula" && (
        <>
          <label className="field-label processing-material-input">
            <span>Formula or material</span>
            <Input
              aria-label="Formula or material"
              value={formula}
              disabled={disabled}
              maxLength={256}
              onChange={(e) => setFormula(e.currentTarget.value)}
              onBlur={() => {
                if (formula.trim() !== material.formula)
                  void onCommit({ formula: formula.trim() });
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") e.currentTarget.blur();
                if (e.key === "Escape") {
                  e.preventDefault();
                  setFormula(material.formula);
                }
              }}
            />
          </label>
          <ProcessingNumberField
            label="Density (g/cm³)"
            value={material.density}
            min={0}
            max={100000}
            disabled={disabled}
            onCommit={(density) => onCommit({ density })}
          />
          <p className="integration-note">
            μ follows the calibration wavelength. Density 0 uses the material
            database; enable to calculate.
          </p>
        </>
      )}
    </>
  );
}

import type { CorrectionKind, CorrectionPreviewKind } from "./commandPayloads";
import { correctionPreviewAvailable } from "./correctionPreview";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ChartNoAxesCombined } from "lucide-react";
import { Button, Input, Select } from "./ui";
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
  previewKind,
  onPreview,
  run,
  tab,
  onTabChange,
}: {
  tab: CorrectionPreviewKind;
  onTabChange: (tab: CorrectionPreviewKind) => void;
  state: State;
  previewKind: CorrectionPreviewKind | null;
  onPreview: (kind: CorrectionPreviewKind) => void;
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
    kind: CorrectionKind,
    patch: {
      enabled?: boolean;
      parameters?: Record<string, number>;
      material?: Partial<CorrectionMaterial>;
      container?: { enabled?: boolean; material?: Partial<CorrectionMaterial> };
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
          ...(patch.container
            ? {
                container: {
                  ...correction.container,
                  ...patch.container,
                  ...(patch.container.material
                    ? {
                        material: {
                          ...correction.container?.material,
                          ...patch.container.material,
                        },
                      }
                    : {}),
                },
              }
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
      cylinder: "cylinder absorption",
      sphere: "sphere absorption",
    } as Record<string, string>
  )[tab];
  const field = (key: string) => {
    if (
      (key === "absorption_coefficient"
        ? correction.material?.mode === "formula"
        : key === "container_absorption_coefficient" &&
          correction.container?.material.mode === "formula") &&
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
            correction.material?.mode === "formula") ||
          (key === "container_absorption_coefficient" &&
            correction.container?.material.mode === "formula")
        }
        onCommit={async (value) => {
          if (correction.enabled && tab !== "flat" && tab !== "transfer")
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
  const plotButton = (
    <Button
      variant="quiet"
      className="correction-plot-button"
      aria-label={
        previewKind === tab ? "Back from correction preview" : "Plot correction"
      }
      aria-pressed={previewKind === tab}
      disabled={
        !state.hasImage ||
        !correctionPreviewAvailable(source, tab) ||
        switching !== null
      }
      onClick={() => onPreview(tab)}
    >
      {previewKind === tab ? (
        <ArrowLeft aria-hidden="true" />
      ) : (
        <ChartNoAxesCombined aria-hidden="true" />
      )}
      <span>{previewKind === tab ? "Back" : "Plot"}</span>
    </Button>
  );
  return (
    <>
      <nav
        className="integration-subnav processing-subnav"
        aria-label="Correction type"
      >
        {(
          [
            ["flat", "Flat field"],
            ["transfer", "Transfer"],
            ["plate", "Plate"],
            ["slab", "Slab"],
            ["cylinder", "Cylinder"],
            ["sphere", "Sphere"],
            ["cbn", "cBN seat"],
            ["oiadac", "Detector absorption"],
          ] as const
        ).map(([key, label]) => (
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
            <div className="correction-apply-row">
              <ProcessingToggle
                label="Apply flat field"
                displayLabel="Apply"
                checked={source.flatField.enabled}
                disabled={!source.flatField.filename}
                onCommit={(enabled) =>
                  run("integration_flat_field", { enabled }, "")
                }
              />
              {plotButton}
            </div>
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
            <div className="correction-apply-row">
              <ProcessingToggle
                label="Apply transfer correction"
                displayLabel="Apply"
                checked={source.transfer?.enabled ?? false}
                disabled={
                  !source.transfer?.original || !source.transfer?.response
                }
                onCommit={(enabled) =>
                  run("integration_transfer", { enabled }, "")
                }
              />
              {plotButton}
            </div>
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
            <div className="correction-apply-row">
              <ProcessingToggle
                key={tab}
                label={`Apply ${name}`}
                displayLabel="Apply"
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
              {plotButton}
            </div>
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
            {correction.material && (
              <MaterialControls
                key={`material-${tab}`}
                material={correction.material}
                disabled={!state.hasImage || switching === tab}
                onCommit={(material) => edit(tab, { material })}
              />
            )}
            {tab === "oiadac" && (
              <p className="integration-note">
                Detector orientation and pixel incidence follow the calibration.
                Thickness and absorption length describe the detector sensor.
              </p>
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
            {(tab === "cylinder" || tab === "sphere") && (
              <p className="integration-note">
                Beam width 0 uses a pencil beam; a width at least twice the
                radius illuminates the full sample.
                {tab === "cylinder" &&
                  " Axis tilt is from vertical; rotation 0° tilts toward the incident beam."}
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
                {Object.keys(correction.fields)
                  .filter(
                    (key) =>
                      ![
                        "container_absorption_coefficient",
                        "wall_thickness",
                      ].includes(key),
                  )
                  .map(field)}
              </div>
            )}
            {tab === "cylinder" && correction.container && (
              <section
                className="processing-parameter-group"
                aria-label="Capillary wall"
              >
                <h3>Capillary wall</h3>
                <ProcessingToggle
                  label="Correct capillary wall"
                  checked={correction.container.enabled}
                  disabled={!state.hasImage}
                  onCommit={(enabled) => edit(tab, { container: { enabled } })}
                />
                {correction.container.enabled && (
                  <>
                    <MaterialControls
                      prefix="Container "
                      material={correction.container.material}
                      disabled={!state.hasImage || switching === tab}
                      onCommit={(material) =>
                        edit(tab, { container: { material } })
                      }
                    />
                    <div className="processing-parameter-grid">
                      {field("wall_thickness")}
                      {field("container_absorption_coefficient")}
                    </div>
                  </>
                )}
              </section>
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
  prefix = "",
}: {
  prefix?: string;
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
          aria-label={`${prefix}Attenuation source`}
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
              aria-label={`${prefix}Formula or material`}
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
            label={`${prefix}Density (g/cm³)`}
            value={material.density}
            min={0}
            max={100000}
            disabled={disabled}
            onCommit={(density) => onCommit({ density })}
          />
          <p className="integration-note">
            μ follows the calibration wavelength. Density 0 uses the material
            database.
          </p>
        </>
      )}
    </>
  );
}

import { CrystalNumberField } from "./CrystalNumberField";
import { useEffect, useState } from "react";
import { FolderOpen, Save, Check, Download } from "lucide-react";
import { Button, Input, Select } from "./ui";
import { DataTable, TableScroll } from "./DataTable";
import type { Run } from "./commandContracts";
import {
  crystalFlags,
  crystalTermination,
  type CrystalConfig,
  type CrystalData,
  type CrystalFileOperation,
  type CrystalImageKind,
} from "./singleCrystalDomain";
const fmt = (n: number, d = 3) => (Number.isFinite(n) ? n.toFixed(d) : "—");
export interface CrystalStageProps {
  step: number;
  setStep: (v: number) => void;
  data: CrystalData | null;
  run: Run;
  ready: boolean;
  calibrated: boolean;
  draft: CrystalConfig;
  update: <K extends keyof CrystalConfig>(
    key: K,
    value: CrystalConfig[K],
  ) => void;
  file: (op: CrystalFileOperation) => void;
  changeFrame: (index: number, kind?: CrystalImageKind) => void;
  predicted: boolean;
  setPredicted: (v: boolean) => void;
  observed: boolean;
  setObserved: (v: boolean) => void;
  rejected: boolean;
  setRejected: (v: boolean) => void;
  selectedTrack: number | null;
  setSelectedTrack: (v: number | null) => void;
  maskPicking: boolean;
  setMaskPicking: (v: boolean) => void;
  onValidation: (field: string, error: string | null) => void;
  corner: { x: number; y: number } | null;
  setCorner: (v: { x: number; y: number } | null) => void;
}
export function SingleCrystalStages({
  step,
  setStep,
  data,
  run,
  ready,
  calibrated,
  draft,
  update,
  file,
  changeFrame,
  observed,
  setObserved,
  predicted,
  setPredicted,
  rejected,
  setRejected,
  selectedTrack,
  setSelectedTrack,
  maskPicking,
  setMaskPicking,
  corner,
  setCorner,
  onValidation,
}: CrystalStageProps) {
  const [filter, setFilter] = useState("all");
  const [showProtocol, setShowProtocol] = useState(false);
  const [pendingTrack, setPendingTrack] = useState<{
    id: number;
    checked: boolean;
  } | null>(null);
  useEffect(() => {
    if (selectedTrack != null)
      document
        .getElementById(`sc-track-${selectedTrack}`)
        ?.scrollIntoView({ block: "nearest" });
  }, [selectedTrack, data?.trackOffset]);
  const numberField = (
    key: Exclude<
      keyof CrystalConfig,
      | "axis"
      | "adp"
      | "elements"
      | "background"
      | "confirmed"
      | "refine_geometry"
      | "metric"
      | "scan_scaling"
      | "keep_stage_audit"
      | "protocol"
      | "integration_method"
      | "dac_enabled"
      | "dac_axis"
      | "seat_enabled"
      | "diamond_enabled"
    >,
    label: string,
    units = "",
    min?: number,
    max?: number,
  ) => (
    <CrystalNumberField
      key={key}
      field={key}
      label={label + (units ? ` / ${units}` : "")}
      value={draft[key]}
      disabled={
        draft.integration_method === "profile" &&
        [
          "threshold",
          "min_pixels",
          "link_radius",
          "aperture_radius",
          "omega_radius",
          "polarization",
          "gain",
          "read_noise",
          "smoothness",
        ].includes(key)
      }
      onCommit={(v) => update(key, v)}
      onValidation={onValidation}
      min={min}
      max={max}
      integer={[
        "group",
        "min_pixels",
        "aperture_radius",
        "shadow_block",
        "seat_guard",
      ].includes(key)}
      positive={["omega_step", "exposure", "gain"].includes(key)}
    />
  );

  const protocolDocument =
    draft.protocol ?? data?.effectiveProtocol ?? data?.protocolTemplate;
  const protocolAcquisition = protocolDocument?.acquisition as
    Record<string, unknown> | undefined;
  const changeProtocolFrame = (
    key: "first_frame" | "last_frame_inclusive",
    frame: number,
  ) => {
    if (protocolDocument && protocolAcquisition)
      update("protocol", {
        ...protocolDocument,
        acquisition: { ...protocolAcquisition, [key]: frame - 1 },
      });
  };
  const chooseWorkflow = (method: "summation" | "profile") => {
    update("integration_method", method);
    const profile = method === "profile";
    update("background", !profile);
    update("aperture_radius", profile ? 7 : 6);
    update("omega_radius", profile ? 4.5 : 1.5);
    update("polarization", profile ? 0.98 : 0.99);
    update("link_radius", profile ? 5 : 3);
    update("refine_geometry", profile);
    update("scan_scaling", false);
    if (profile) {
      // Enter the displayed protocol interval explicitly, replacing old manual
      // omissions instead of leaving two competing frame selections.
      if (!draft.protocol && protocolDocument)
        update("protocol", protocolDocument);
      update("gain", 1);
      update("read_noise", 0);
      update("threshold", 5);
      update("min_pixels", 3);
    }
  };
  const pagination = (kind: "tracks" | "reflections") => {
    if (!data) return null;
    const offset = kind === "tracks" ? data.trackOffset : data.reflectionOffset;
    const total =
      kind === "tracks" ? data.trackCount : data.reflectionFilteredCount;
    return (
      <div className="sc-pagination" role="group" aria-label={`${kind} pages`}>
        <Button
          variant="quiet"
          disabled={!ready || offset === 0}
          onClick={() =>
            void run(
              "scxrd_table",
              { kind, offset: Math.max(0, offset - 200) },
              "",
            )
          }
        >
          Previous
        </Button>
        <span>
          {total ? offset + 1 : 0}–{Math.min(total, offset + 200)} / {total}
        </span>
        <Button
          variant="quiet"
          disabled={!ready || offset + 200 >= total}
          onClick={() =>
            void run("scxrd_table", { kind, offset: offset + 200 }, "")
          }
        >
          Next
        </Button>
      </div>
    );
  };
  const trackRows =
    data?.tracks.filter(
      (t) =>
        filter === "all" ||
        (filter === "usable"
          ? t.flags === 0 && !t.excluded
          : t.flags !== 0 || t.excluded),
    ) ?? [];
  if (step === 0)
    return (
      <>
        <div className="sc-actions">
          <Button
            disabled={!ready}
            onClick={() =>
              void run("scxrd_load", {}, "Verifying rotation frames…")
            }
          >
            <FolderOpen size={15} />
            Load frames…
          </Button>
          <Button disabled={!ready} onClick={() => file("open")}>
            Open recipe…
          </Button>
          <Button disabled={!ready} onClick={() => file("preset")}>
            Apply recipe settings…
          </Button>
        </div>
        {!!data?.frames && (
          <p className="sc-source" title={data.filename ?? ""}>
            {data.frames} frames · {data.shape[1]} × {data.shape[0]} px
            <br />
            {data.filename}
          </p>
        )}
        {!!data?.frames && (
          <details className="sc-source-order">
            <summary>Review scan order</summary>
            <p>First: {data.firstSource}</p>
            <p>Last: {data.lastSource}</p>
            <p>
              Numbered sequences are sorted and checked for missing or duplicate
              frames. Other names retain selection order.
            </p>
          </details>
        )}
        {draft.integration_method === "profile" && (
          <fieldset disabled={!ready}>
            <legend>Sample setup · required before processing</legend>
            <div className="sc-actions">
              <Button variant="secondary" onClick={() => setStep(4)}>
                {draft.metric
                  ? `Cell: ${draft.metric
                      .slice(0, 3)
                      .map((v) => fmt(v, 3))
                      .join(" × ")} Å`
                  : "Enter sample cell…"}
              </Button>
              <Button variant="secondary" onClick={() => setStep(6)}>
                Space group:{" "}
                {draft.group === data?.config.group && data?.suppliedGroupSymbol
                  ? `${data.suppliedGroupSymbol} (#${draft.group})`
                  : `#${draft.group} (draft)`}
              </Button>
              <Button variant="secondary" onClick={() => setStep(7)}>
                {draft.elements.trim()
                  ? `Elements: ${draft.elements}`
                  : "Enter elements…"}
              </Button>
            </div>
            <p className="sc-note">
              Review these supplied priors before any checkpoint. Each button
              opens its editor; apply the draft, then confirm acquisition below.
            </p>
          </fieldset>
        )}
        <fieldset disabled={!ready}>
          <legend>PhaseSmith analysis protocol</legend>
          <label className="sc-field">
            <span>Workflow</span>
            <Select
              aria-label="Single-crystal workflow"
              value={draft.integration_method}
              onChange={(e) =>
                chooseWorkflow(e.target.value as "summation" | "profile")
              }
            >
              <option value="profile">PhaseSmith · orthorhombic</option>
              <option value="summation">
                Exploratory measured-track summation
              </option>
            </Select>
          </label>
          <div className="sc-actions">
            <Button variant="secondary" onClick={() => file("protocol")}>
              Load protocol…
            </Button>
            <Button
              variant="secondary"
              onClick={() => file("protocol_builtin")}
            >
              Use bundled v29
            </Button>
            <Button
              variant="secondary"
              disabled={!data?.frames || draft.integration_method !== "profile"}
              onClick={() => file("protocol_save")}
            >
              Save effective protocol…
            </Button>
            <Button
              variant="quiet"
              onClick={() => setShowProtocol(!showProtocol)}
            >
              {showProtocol ? "Hide protocol" : "Inspect protocol"}
            </Button>
          </div>
          <p className="sc-note">
            Versioned native workflow for a supplied orthorhombic metric. Review
            the frame range below.
          </p>
          <details className="sc-protocol-details">
            <summary>Protocol compatibility and reproducibility</summary>
            <p className="sc-note">
              Supplied-symmetry orthorhombic protocols use the complete
              PhaseSmith workflow. Declared acquisition and shadow edits are
              recorded as protocol overrides. Save a Dioptas recipe for source
              paths, calibration and sample priors. When entering protocol mode
              its frame range replaces manual frame exclusions; review the
              first/last frame.
            </p>
          </details>
          {protocolAcquisition && (
            <>
              <p className="sc-note">
                Frame fields use one-based numbering; protocol JSON uses
                zero-based indices.
              </p>
              <CrystalNumberField
                field="protocol_first_frame"
                label="Protocol first frame"
                value={Number(protocolAcquisition.first_frame) + 1}
                min={1}
                max={data?.frames || 10000}
                integer
                onCommit={(v) => changeProtocolFrame("first_frame", v)}
                onValidation={onValidation}
              />
              <CrystalNumberField
                field="protocol_last_frame"
                label="Protocol last frame"
                value={Number(protocolAcquisition.last_frame_inclusive) + 1}
                min={1}
                max={data?.frames || 10000}
                integer
                onCommit={(v) => changeProtocolFrame("last_frame_inclusive", v)}
                onValidation={onValidation}
              />
            </>
          )}
          <label className="sc-check">
            <Input
              type="checkbox"
              checked={draft.keep_stage_audit}
              onChange={(e) => update("keep_stage_audit", e.target.checked)}
            />
            Keep lossless intermediate stage outputs
          </label>
          {showProtocol && (
            <>
              <p className="sc-note" role="status">
                {data?.effectiveProtocol
                  ? "Applied effective protocol. Apply any settings draft to refresh this document."
                  : "Bundled template; load a protocol and apply valid settings to inspect the effective document."}
                {(!draft.dac_enabled || !draft.seat_enabled) &&
                  " The combined-mask policy requires both cell-shadow masks enabled before execution."}
                {data?.protocolInspectionError &&
                  ` ${data.protocolInspectionError}`}
              </p>
              <pre
                className="sc-protocol-code"
                tabIndex={0}
                aria-label="PhaseSmith protocol document"
              >
                {JSON.stringify(
                  data?.effectiveProtocol ?? data?.protocolTemplate,
                  null,
                  2,
                )}
              </pre>
            </>
          )}
        </fieldset>
        <fieldset disabled={!ready}>
          <legend>Acquisition · user supplied</legend>
          {numberField(
            "omega_start",
            "First exposure start",
            "°",
            -10000,
            10000,
          )}
          {numberField("omega_step", "Rotation step", "°", 0, 10)}
          {numberField("exposure", "Exposure width", "°", 0, 10)}
          <label className="sc-field">
            <span>
              Spindle axis<small>lab frame</small>
            </span>
            <Select
              value={JSON.stringify(draft.axis)}
              onChange={(e) => update("axis", JSON.parse(e.target.value))}
            >
              <option value="[1,0,0]">+slow · [1, 0, 0]</option>
              <option value="[-1,0,0]">−slow · [−1, 0, 0]</option>
              <option value="[0,1,0]">+fast · [0, 1, 0]</option>
              <option value="[0,-1,0]">−fast · [0, −1, 0]</option>
              <option value="[0,0,1]">beam · [0, 0, 1]</option>
            </Select>
          </label>
          <p className="sc-note">
            Uniform positive rotation scans. Choose files in acquisition order;
            missing exposures must not be compressed. Angles are not inferred
            from filenames.
          </p>
        </fieldset>
        <fieldset disabled={!ready}>
          <legend>Detector geometry</legend>
          <div className="sc-actions">
            <Button onClick={() => file("calibration")}>Load .poni…</Button>
            <Button
              disabled={!calibrated}
              onClick={() => file("use_calibration")}
            >
              Use current calibration
            </Button>
          </div>
          <p className="sc-note">
            {data?.geometry
              ? `Loaded affine geometry · λ = ${fmt(data.geometry.wavelength, 6)} Å`
              : "Load a PONI calibration before cell finding."}
          </p>
        </fieldset>
        <fieldset disabled={!ready}>
          <legend>Counting uncertainty</legend>
          {numberField("gain", "Gain", "photons/count", 1e-9, 1e6)}
          {numberField("read_noise", "Read noise", "counts", 0, 1e6)}
          {numberField(
            "saturation",
            "Overload threshold",
            "counts",
            1,
            4294967295,
          )}
          <p className="sc-note">
            {draft.integration_method === "profile"
              ? "Set by protocol: original photon counts, gain 1 and read noise 0. ADU gain conversion is available in exploratory summation."
              : "Photon counters: gain 1, read noise 0. ADU detectors need a measured gain."}
          </p>
        </fieldset>
        <label className="sc-check">
          <Input
            type="checkbox"
            checked={draft.confirmed}
            onChange={(e) => update("confirmed", e.target.checked)}
            disabled={!ready || !data?.frames}
          />
          <span>
            {draft.integration_method === "profile"
              ? "I checked the frame order, angles, axis, count gain and cell-shadow assumptions."
              : "I checked the frame order, angles, axis and count gain."}
          </span>
        </label>
      </>
    );
  if (step === 1)
    return (
      <>
        <fieldset disabled={!ready}>
          <legend>Moving cell shadows · original counts</legend>
          <label className="sc-check">
            <Input
              type="checkbox"
              checked={draft.dac_enabled}
              onChange={(e) => update("dac_enabled", e.target.checked)}
            />
            Mask the diamond-anvil-cell aperture
          </label>
          {draft.dac_enabled && (
            <>
              {numberField(
                "dac_half_opening",
                "DAC half opening",
                "°",
                0.01,
                89.999,
              )}
              <p className="sc-note">
                Declare the sample-fixed cell axis in lab coordinates at omega
                zero. The whole exposure and detector-block footprint must stay
                inside the cone; this is exclusion, not absorption correction.
              </p>
              {draft.dac_axis.map((v, i) => (
                <CrystalNumberField
                  key={i}
                  field={`dac_axis_${i}`}
                  label={`DAC axis ${["x", "y", "z"][i]}`}
                  value={v}
                  onCommit={(value) => {
                    const axis: [number, number, number] = [...draft.dac_axis];
                    axis[i] = value;
                    update("dac_axis", axis);
                  }}
                  onValidation={onValidation}
                  min={-1e6}
                  max={1e6}
                />
              ))}
            </>
          )}
          <label className="sc-check">
            <Input
              type="checkbox"
              checked={draft.seat_enabled}
              onChange={(e) => update("seat_enabled", e.target.checked)}
            />
            Estimate moving seat / illumination shadows
          </label>
          {draft.seat_enabled && (
            <>
              {numberField(
                "seat_threshold",
                "Illumination threshold",
                "",
                0.01,
                0.999,
              )}
              {numberField("seat_guard", "Illumination guard", "px", 0, 4096)}
            </>
          )}
          {(draft.dac_enabled || draft.seat_enabled) &&
            numberField("shadow_block", "Shadow block side", "px", 1, 1024)}
          <p className="sc-note">
            Shadow masks are shared by background, peaks and intensities. They
            never rescale original counts. Enabling or changing them requires
            rerunning dependent stages.
          </p>
          {data?.shadows && (
            <p className="sc-note">
              Prepared exposures {data.shadows.first + 1}–
              {data.shadows.last + 1}: {data.shadows.illuminationExcluded}{" "}
              illumination blocks and {data.shadows.dacExcluded} DAC blocks
              excluded. Recipe and report retain mask fingerprints.
            </p>
          )}
        </fieldset>
        <label className="sc-check">
          <Input
            type="checkbox"
            checked={draft.background}
            onChange={(e) => update("background", e.target.checked)}
            disabled={!ready || draft.integration_method === "profile"}
          />
          <span>Fit omega background (arPLS)</span>
        </label>
        {numberField("smoothness", "Smoothness", "λ", 1e-6, 1e9)}
        <label className="sc-field">
          <span>Image</span>
          <Select
            aria-label="Single crystal image source"
            disabled={!ready || !data?.frames}
            value={data?.previewKind ?? "raw"}
            onChange={(e) =>
              changeFrame(data!.frame, e.target.value as CrystalImageKind)
            }
          >
            <option value="raw">Original counts</option>
            <option
              value="background"
              disabled={
                data?.stages[0]?.status !== "complete" ||
                !data?.config.background
              }
            >
              Omega background · positions only
            </option>
            <option
              value="corrected"
              disabled={
                data?.stages[0]?.status !== "complete" ||
                !data?.config.background
              }
            >
              Subtracted · positions only
            </option>
          </Select>
        </label>
        <fieldset>
          <legend>Exclude detector regions</legend>
          <p className="sc-note">
            {draft.integration_method === "profile"
              ? "The protocol uses its moving cell-shadow masks above. Manual regions and track exclusions are available in exploratory summation. Select a contiguous protocol frame range in Frames."
              : "Mask beamstop, gaps, diamond spots or powder regions. These exclusions also remove counts from integration."}
          </p>
          <Button
            disabled={
              !ready || !data?.image || draft.integration_method === "profile"
            }
            aria-pressed={maskPicking}
            onClick={() => {
              setMaskPicking(!maskPicking);
              setCorner(null);
            }}
          >
            {maskPicking
              ? "Finish region picking"
              : "Pick two corners on image"}
          </Button>
          {maskPicking && (
            <p className="sc-note" role="status">
              {corner
                ? "Click the opposite corner. Right-drag still pans."
                : "Click the first corner of an exclusion rectangle."}
            </p>
          )}
          <p>{data?.mask.length ?? 0} excluded regions</p>
          {data?.mask.map((b, i) => (
            <div className="sc-region-row" key={i}>
              <span>
                Region {i + 1}: x {b[0]}–{b[2]}, rows {data.shape[0] - b[3]}–
                {data.shape[0] - b[1] - 1}
              </span>
              <Button
                variant="quiet"
                aria-label={`Remove region ${i + 1}`}
                disabled={!ready}
                onClick={() =>
                  void run(
                    "scxrd_edit",
                    { operation: "remove_mask", index: i },
                    "Removing detector exclusion…",
                  )
                }
              >
                Remove
              </Button>
            </div>
          ))}
          <Button
            variant="quiet"
            disabled={!ready || !data?.mask.length}
            onClick={() =>
              void run(
                "scxrd_edit",
                { operation: "clear_mask" },
                "Clearing exclusions…",
              )
            }
          >
            Clear regions
          </Button>
        </fieldset>
        <Button
          variant="secondary"
          disabled={
            !ready || !data?.frames || draft.integration_method === "profile"
          }
          onClick={() =>
            void run(
              "scxrd_edit",
              { operation: "frame", index: data!.frame },
              "Updating frame exclusion…",
            )
          }
        >
          {data?.excludedFrames.includes(data.frame)
            ? "Restore current frame"
            : "Exclude current frame"}
        </Button>
      </>
    );
  if (step === 2)
    return (
      <>
        {draft.integration_method === "profile" && (
          <p className="sc-note">
            Detection and linking controls are set by the versioned protocol.
            Inspect it in Frames.
          </p>
        )}
        {numberField("threshold", "Peak threshold", "σ", 1, 100)}
        {numberField("min_pixels", "Minimum area", "px", 1, 1000)}
        {numberField("link_radius", "Link radius", "px", 0.1, 30)}
        <p className="sc-summary">
          {data?.peakCount ?? 0} peak observations · {data?.trackCount ?? 0}{" "}
          linked tracks
        </p>
        {!!data?.peakFrames?.length && (
          <div className="sc-peak-chart">
            <svg
              viewBox="0 0 400 72"
              role="slider"
              tabIndex={0}
              aria-label="Peaks per rotation frame"
              aria-valuemin={1}
              aria-valuemax={data.frames}
              aria-valuenow={data.frame + 1}
              onKeyDown={(e) => {
                if (!ready) return;
                const next =
                  e.key === "Home"
                    ? 0
                    : e.key === "End"
                      ? data.frames - 1
                      : ["ArrowRight", "ArrowUp"].includes(e.key)
                        ? data.frame + 1
                        : ["ArrowLeft", "ArrowDown"].includes(e.key)
                          ? data.frame - 1
                          : null;
                if (next == null) return;
                e.preventDefault();
                e.stopPropagation();
                changeFrame(Math.max(0, Math.min(data.frames - 1, next)));
              }}
              onClick={(e) => {
                if (!ready) return;
                const b = e.currentTarget.getBoundingClientRect();
                changeFrame(
                  Math.max(
                    0,
                    Math.min(
                      data.frames - 1,
                      Math.round(
                        ((e.clientX - b.left) / b.width) * (data.frames - 1),
                      ),
                    ),
                  ),
                );
              }}
            >
              <path
                d={`M ${data.peakFrames.map((n, i) => `${(i / Math.max(1, data.frames - 1)) * 400},${68 - (n / Math.max(1, ...data.peakFrames)) * 62}`).join(" L ")}`}
                fill="none"
                stroke="#ffac58"
                strokeWidth="1.5"
              />
              <line
                x1={(data.frame / Math.max(1, data.frames - 1)) * 400}
                x2={(data.frame / Math.max(1, data.frames - 1)) * 400}
                y1="0"
                y2="72"
                stroke="#dce2e7"
                strokeDasharray="3 3"
              />
            </svg>
            <span>
              Peaks per frame · click or arrow keys to inspect · max{" "}
              {Math.max(...data.peakFrames)}
            </span>
          </div>
        )}
        <div className="sc-actions">
          <label className="sc-check">
            <Input
              type="checkbox"
              checked={observed}
              onChange={(e) => setObserved(e.target.checked)}
            />
            Observed
          </label>
          <label className="sc-check">
            <Input
              type="checkbox"
              checked={predicted}
              onChange={(e) => setPredicted(e.target.checked)}
            />
            Predicted
          </label>
          <label className="sc-check">
            <Input
              type="checkbox"
              checked={rejected}
              onChange={(e) => setRejected(e.target.checked)}
            />
            Flagged / excluded
          </label>
        </div>
        <label className="sc-field">
          <span>Track table</span>
          <Select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All tracks</option>
            <option value="usable">Unflagged tracks</option>
            <option value="flagged">Flagged / excluded</option>
          </Select>
        </label>
        {draft.integration_method === "profile" && (
          <p className="sc-note">
            Track diagnostics describe detection and linking. Final reflection
            eligibility is shown in Intensities.
          </p>
        )}
        {!!trackRows.length && (
          <TableScroll
            className="sc-table"
            tabIndex={0}
            role="region"
            aria-label="Single-crystal data table"
          >
            <DataTable>
              <caption>
                Tracks ·{" "}
                {filter === "all"
                  ? "all tracks"
                  : filter === "usable"
                    ? "unflagged tracks"
                    : "flagged / excluded"}{" "}
                · page
              </caption>
              <thead>
                <tr>
                  <th scope="col">Track</th>
                  <th scope="col">Frames</th>
                  <th scope="col">ω / °</th>
                  <th scope="col">Quality</th>
                  <th scope="col">Exclude</th>
                </tr>
              </thead>
              <tbody>
                {trackRows.map((t) => (
                  <tr
                    key={t.id}
                    id={`sc-track-${t.id}`}
                    aria-selected={selectedTrack === t.id}
                  >
                    <td>
                      <Button
                        variant="quiet"
                        aria-label={`Inspect track ${t.id + 1}`}
                        onClick={() => {
                          setSelectedTrack(t.id);
                          changeFrame(t.first);
                        }}
                      >
                        {t.id + 1}
                      </Button>
                    </td>
                    <td>
                      {t.first + 1}–{t.last + 1}
                    </td>
                    <td>{fmt(t.observed[2], 2)}</td>
                    <td>{crystalFlags(t.flags, undefined, t.native)}</td>
                    <td>
                      <Input
                        type="checkbox"
                        aria-label={`Exclude track ${t.id + 1}`}
                        checked={
                          pendingTrack?.id === t.id
                            ? pendingTrack.checked
                            : t.excluded
                        }
                        disabled={
                          !ready ||
                          pendingTrack?.id === t.id ||
                          (draft.integration_method === "profile" &&
                            !t.excluded)
                        }
                        onChange={(e) => {
                          setPendingTrack({
                            id: t.id,
                            checked: e.target.checked,
                          });
                          void run(
                            "scxrd_edit",
                            { operation: "track", index: t.id },
                            "Updating track exclusion…",
                          ).finally(() => setPendingTrack(null));
                        }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </TableScroll>
        )}
        {pagination("tracks")}
        <p className="sc-note">
          Click a peak to inspect its track. Excluding a track requires
          rerunning cell finding and dependent stages. Flagged tracks are
          retained in this table and counted separately.
        </p>
      </>
    );
  if (step === 3)
    return (
      <>
        {draft.integration_method !== "profile" && (
          <>
            {numberField("min_cell", "Shortest vector", "Å", 1.5, 100)}
            {numberField("max_cell", "Longest vector", "Å", 1.5, 100)}
            {numberField("tolerance", "Indexing tolerance", "Å⁻¹", 0.001, 0.1)}
          </>
        )}
        {draft.integration_method === "profile" && (
          <p className="sc-note">
            The protocol indexes and validates the declared metric using its
            native grain search and whole-family position holdouts. Declare the
            sample metric in Geometry before running.
          </p>
        )}
        {!!data?.cells.length && (
          <div
            className="sc-cell-list"
            role="group"
            aria-label="Cell candidates"
          >
            {data.cells.map((cell, i) => (
              <div
                className={`sc-cell-card ${data.selected === i ? "sc-cell-chosen" : ""}`}
                key={i}
              >
                <div className="sc-cell-card-head">
                  <Button
                    disabled={!ready}
                    aria-label={`Select cell ${i + 1}`}
                    aria-pressed={data.selected === i}
                    onClick={() =>
                      void run(
                        "scxrd_edit",
                        { operation: "cell", index: i },
                        "Selecting sample cell…",
                      )
                    }
                  >
                    {data.selected === i ? <Check size={14} /> : null}
                    {data.selected === i ? "Selected cell" : "Use cell"} {i + 1}
                  </Button>
                  <span>
                    {cell.indexed}/{cell.total} indexed ·{" "}
                    {fmt((100 * cell.indexed) / cell.total, 0)}%
                  </span>
                </div>
                <dl>
                  <dt>a, b, c / Å</dt>
                  <dd>
                    {cell.parameters
                      .slice(0, 3)
                      .map((n) => fmt(n))
                      .join(" · ")}
                  </dd>
                  <dt>α, β, γ / °</dt>
                  <dd>
                    {cell.parameters
                      .slice(3)
                      .map((n) => fmt(n, 2))
                      .join(" · ")}
                  </dd>
                  <dt>Withheld RMS / Å⁻¹</dt>
                  <dd>
                    {fmt(cell.rms, 5)} · n = {cell.validation}
                  </dd>
                </dl>
              </div>
            ))}
          </div>
        )}
        <p className="sc-note">
          Positions only, with every fifth point withheld. A reduced primitive
          cell does not determine the conventional Bravais setting. Automatic
          processing pauses on ambiguity and diamond-like cells.
        </p>
      </>
    );
  if (step === 4)
    return (
      <>
        <label className="sc-check">
          <Input
            type="checkbox"
            checked={draft.refine_geometry}
            onChange={(e) => update("refine_geometry", e.target.checked)}
            disabled={!ready || draft.integration_method === "profile"}
          />
          <span>Refine detector pose and crystal orientation</span>
        </label>
        <p className="sc-note">
          {draft.integration_method === "profile"
            ? "The protocol refines pose/orientation with whole-family holdouts. Wavelength and the declared metric stay fixed."
            : "Default: keep the loaded calibration fixed. Optional refinement fits 9 parameters; wavelength and cell lengths stay fixed. Changes must pass independent withheld checks."}
        </p>
        {draft.integration_method === "profile" ? (
          <fieldset disabled={!ready}>
            <legend>Supplied orthorhombic cell</legend>
            {draft.metric &&
            draft.metric.slice(3).some((a) => Math.abs(a - 90) > 1e-8) ? (
              <div className="sc-attention">
                <p>
                  The previous metric has nonorthogonal angles. Clear it before
                  declaring an orthorhombic prior; its angles will not be
                  silently changed.
                </p>
                <Button
                  variant="secondary"
                  onClick={() => update("metric", null)}
                >
                  Clear incompatible metric
                </Button>
              </div>
            ) : (
              <>
                <p className="sc-note">
                  Enter sample lengths before processing. Angles are fixed at
                  90°. No indexed cell is needed to enter this prior.
                </p>
                {["a / Å", "b / Å", "c / Å"].map((label, i) => (
                  <CrystalNumberField
                    key={label}
                    field={`metric${i}`}
                    label={label}
                    value={draft.metric?.[i] ?? 0}
                    min={0.000001}
                    max={1000}
                    positive
                    onValidation={onValidation}
                    onCommit={(v) => {
                      const p: [
                        number,
                        number,
                        number,
                        number,
                        number,
                        number,
                      ] = [...(draft.metric ?? [0, 0, 0, 90, 90, 90])];
                      p[i] = v;
                      update("metric", p);
                    }}
                  />
                ))}{" "}
              </>
            )}
          </fieldset>
        ) : (
          <>
            <label className="sc-check">
              <Input
                type="checkbox"
                checked={draft.metric !== null}
                disabled={!ready || data?.selected == null}
                onChange={(e) =>
                  update(
                    "metric",
                    e.target.checked
                      ? (data!.cells[data!.selected!].parameters.slice() as [
                          number,
                          number,
                          number,
                          number,
                          number,
                          number,
                        ])
                      : null,
                  )
                }
              />
              <span>
                Use a supplied exact metric in the selected row setting
              </span>
            </label>
            {draft.metric && (
              <div className="sc-metric">
                {["a / Å", "b / Å", "c / Å", "α / °", "β / °", "γ / °"].map(
                  (label, i) => (
                    <CrystalNumberField
                      key={label}
                      field={`metric${i}`}
                      label={label}
                      value={draft.metric![i]}
                      positive
                      min={i < 3 ? 0.000001 : 0.0001}
                      max={i < 3 ? 1000 : 179.9999}
                      onValidation={onValidation}
                      onCommit={(v) => {
                        const p = [...draft.metric!] as [
                          number,
                          number,
                          number,
                          number,
                          number,
                          number,
                        ];
                        p[i] = v;
                        update("metric", p);
                      }}
                    />
                  ),
                )}
              </div>
            )}
          </>
        )}

        {data?.geometryReport && (
          <dl className="sc-statistics">
            {data.geometryReport.refined ? (
              <>
                <dt>Converged</dt>
                <dd>{data.geometryReport.converged ? "Yes" : "No"}</dd>
                <dt>At parameter bounds</dt>
                <dd>{data.geometryReport.atBounds ? "Yes" : "No"}</dd>
                <dt>Maximum correlation</dt>
                <dd>{fmt(data.geometryReport.maximumCorrelation ?? NaN, 4)}</dd>
                <dt>Condition</dt>
                <dd>{fmt(data.geometryReport.condition ?? NaN, 0)}</dd>
                <dt>Withheld RMS · before → after</dt>
                <dd>
                  {fmt(data.geometryReport.rms?.[1]?.[0]?.[0] ?? NaN)} →{" "}
                  {fmt(data.geometryReport.rms?.[1]?.[1]?.[0] ?? NaN)} px
                </dd>
              </>
            ) : (
              <>
                <dt>Prediction RMS</dt>
                <dd>{fmt(data.geometryReport.rmsPixels ?? NaN)} px</dd>
                <dt>Valid observations</dt>
                <dd>{data.geometryReport.observations}</dd>
                <dt>Detector geometry</dt>
                <dd>Held fixed</dd>
              </>
            )}
          </dl>
        )}
      </>
    );
  if (step === 5)
    return (
      <>
        <label className="sc-field">
          <span>Integration recipe</span>
          <Select
            value={draft.integration_method}
            disabled={!ready}
            onChange={(e) =>
              chooseWorkflow(e.target.value as "summation" | "profile")
            }
          >
            <option value="summation">
              Exploratory measured-track summation
            </option>
            <option value="profile">PhaseSmith · orthorhombic</option>
          </Select>
        </label>
        <details
          className="sc-protocol-details"
          open={draft.integration_method === "summation"}
        >
          <summary>Integration support and corrections</summary>
          {draft.integration_method === "profile" && (
            <p className="sc-note">
              Uses the standalone native workflow: shared seat/DAC masks,
              predicted crossings, independent learned profiles and robust
              family scaling. Requires explicit orthorhombic metric, space
              group, element symbols and configured cell shadows. It refits
              orientation/geometry from original counts; preview peak controls
              do not replace its frozen recipe. Custom regions, excluded tracks
              and interior excluded frames are rejected.
            </p>
          )}
          <fieldset disabled={draft.integration_method === "profile"}>
            <legend>
              {draft.integration_method === "profile"
                ? "Frozen native recipe support"
                : "Summation support"}
            </legend>
            {numberField("aperture_radius", "Aperture half-width", "px", 2, 64)}
            {numberField("omega_radius", "Rocking half-width", "°", 0.01, 10)}
            {numberField("polarization", "Polarization fraction", "", 0, 1)}
          </fieldset>
          <p className="sc-note">
            {draft.integration_method === "profile"
              ? "Frozen profile recipe: 7 px spatial support, up to 4.5° rocking support adapted to zeta, guarded-plane background, polarization 0.98 and native per-frame/detector/ray scaling. Original profile flags remain visible; mismatch warnings do not silently remove bright reflections. No absorption correction."
              : "3D summation uses the declared spatial aperture and angular width around each measured track, including weak tails beyond detection. Signed counts and sigma use Lorentz/polarization corrections. Partials, masked, saturated and overlapping measurements are flagged. Summation does not perform profile fitting or empirical family scaling."}
          </p>
        </details>
        <p className="sc-summary">
          {draft.integration_method === "profile" && !data?.reflectionCount ? (
            "No current reduction · run this stage to compute observations."
          ) : (
            <>
              {data?.usableReflections ?? 0} usable /{" "}
              {data?.reflectionCount ?? 0}{" "}
              {draft.integration_method === "profile"
                ? "predicted crossings"
                : "integrated tracks"}
            </>
          )}
        </p>
        <label className="sc-field">
          <span>Observation table</span>
          <Select
            aria-label="Observation quality filter"
            value={data?.reflectionFilter ?? "all"}
            disabled={!ready || !data?.reflectionCount}
            onChange={(e) =>
              void run(
                "scxrd_table",
                {
                  kind: "reflections",
                  offset: 0,
                  filter: e.target.value as "all" | "usable" | "excluded",
                },
                "",
              )
            }
          >
            <option value="all">All observations</option>
            <option value="usable">Usable observations</option>
            <option value="excluded">Excluded observations</option>
          </Select>
        </label>
        {!!data?.reflectionCount && !data.reflections.length && (
          <p className="sc-note">No observations match this filter.</p>
        )}
        {!!data?.reflections.length && (
          <TableScroll
            className="sc-table sc-reflections"
            tabIndex={0}
            role="region"
            aria-label="Single-crystal data table"
          >
            <DataTable>
              <caption>
                {draft.integration_method === "profile"
                  ? "Unmerged predicted crossings · displayed page"
                  : "Unmerged measured tracks · displayed page"}
              </caption>
              <thead>
                <tr>
                  <th scope="col">h k l</th>
                  <th scope="col">I</th>
                  <th scope="col">σ(I)</th>
                  <th scope="col">Quality</th>
                </tr>
              </thead>
              <tbody>
                {data.reflections.map((r, i) => (
                  <tr
                    key={
                      r.crossing != null
                        ? `crossing-${r.crossing}`
                        : `track-${r.track ?? i}`
                    }
                  >
                    <td>{r.hkl.join(" ")}</td>
                    <td>{fmt(r.intensity, 2)}</td>
                    <td>{fmt(r.sigma, 2)}</td>
                    <td
                      title={`${crystalFlags(r.flags, r.native_use)}. Raw quality flags: ${r.flags}`}
                    >
                      {r.flags ? (
                        <details className="sc-quality-details">
                          <summary>
                            {(() => {
                              const full = crystalFlags(r.flags, r.native_use);
                              const [state, reasons] = full.split(" · ");
                              if (!reasons) return full;
                              const labels = reasons.split(", ");
                              return `${state} · ${labels[0]}${labels.length > 1 ? ` (+${labels.length - 1})` : ""}`;
                            })()}
                          </summary>
                          <p>{crystalFlags(r.flags, r.native_use)}</p>
                          <small>Raw quality flags: {r.flags}</small>
                        </details>
                      ) : (
                        crystalFlags(r.flags, r.native_use)
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </TableScroll>
        )}
        {pagination("reflections")}
      </>
    );
  if (step === 6)
    return (
      <>
        {numberField("group", "Supplied space-group number", "1–230", 1, 230)}
        <p className="sc-note">
          The supplied group must preserve the exact selected cell metric and
          index setting. Use P1 for an unconstrained reduced primitive cell.
          Symmetry evidence does not establish a unique space group.
        </p>
        <label className="sc-check">
          <Input
            type="checkbox"
            checked={draft.scan_scaling}
            disabled={!ready || draft.integration_method === "profile"}
            onChange={(e) => update("scan_scaling", e.target.checked)}
          />
          <span>Fit robust log-linear omega scale</span>
        </label>
        <p className="sc-note">
          Requires strong repeated symmetry families at different angles. Shared
          scale uncertainty is reported separately from conditional counting σ.
          This is not a DAC absorption correction.
        </p>
        {data?.scaling?.rInt != null && data.scaling.rInt > 0.2 && (
          <div className="sc-attention" role="status">
            <strong>Review intensity agreement</strong>
            <p>
              Equivalent observations disagree substantially (Rint{" "}
              {fmt(100 * data.scaling.rInt, 1)}%). Inspect aperture support,
              overlaps, the supplied symmetry and scan scaling before
              interpreting a structure candidate. Absorption is not corrected.
              This advisory is not a crystallographic acceptance threshold.
            </p>
          </div>
        )}
        {data?.scaling && (
          <dl className="sc-statistics">
            <dt>Supplied setting</dt>
            <dd>{data.scaling.symbol}</dd>
            <dt>Independent families</dt>
            <dd>{data.scaling.families}</dd>
            <dt>Repeated families</dt>
            <dd>{data.scaling.repeatedFamilies}</dd>
            <dt>Mean multiplicity</dt>
            <dd>{fmt(data.scaling.multiplicity, 2)}</dd>
            <dt>Rint · repeated families</dt>
            <dd>
              {data.scaling.rInt == null
                ? "Insufficient redundancy"
                : `${fmt(100 * data.scaling.rInt, 2)}%`}
            </dd>
            <dt>CC½ · deterministic split</dt>
            <dd>
              {data.scaling.ccHalf == null
                ? "Insufficient redundancy"
                : fmt(data.scaling.ccHalf, 4)}
            </dd>
            <dt>Strong absence violations</dt>
            <dd>{data.scaling.strongAbsenceViolations}</dd>
            <dt>Intensity-symmetry evidence</dt>
            <dd>
              {(
                {
                  friedel_only: "Friedel symmetry only",
                  insufficient_data: "Insufficient redundancy",
                  supported: "Supported",
                  contradicted: "Contradicted",
                } as Record<string, string>
              )[data.scaling.symmetryStatus] ?? data.scaling.symmetryStatus}
            </dd>
            <dt>Scan scale</dt>
            <dd>
              {data.scaling.fit.recipe
                ? "Native per-frame / detector / ray family scale"
                : data.scaling.fit.applied
                  ? `Applied · β ${fmt(data.scaling.fit.coefficient ?? 0, 4)}`
                  : "Disabled"}
            </dd>
            <dt>Absorption</dt>
            <dd>Not corrected</dd>
          </dl>
        )}
      </>
    );
  if (step === 7)
    return (
      <>
        <label className="sc-field">
          <span>
            Elements<small>no atom counts</small>
          </span>
          <Input
            placeholder="Mg Si O"
            value={draft.elements}
            onChange={(e) => update("elements", e.target.value)}
            disabled={!ready}
          />
        </label>
        {draft.integration_method === "profile" ? (
          <p className="sc-note">
            Supplied space group: #{draft.group}. Edit it in Scaling; it is an
            explicit prior.
          </p>
        ) : (
          numberField("group", "Supplied space-group number", "1–230", 1, 230)
        )}
        <p className="sc-note">
          Use the exact setting matching the selected cell. P1 is the default; a
          space group is an explicit prior, not an automatic determination.
        </p>
        <label className="sc-field">
          <span>ADP model</span>
          <Select
            value={
              draft.integration_method === "profile" ? "protocol" : draft.adp
            }
            onChange={(e) =>
              update("adp", e.target.value as CrystalConfig["adp"])
            }
            disabled={!ready || draft.integration_method === "profile"}
          >
            {draft.integration_method === "profile" && (
              <option value="protocol">
                validated-v1 · native staged search
              </option>
            )}
            <option value="isotropic">Isotropic</option>
            <option value="anisotropic">Anisotropic · more parameters</option>
          </Select>
        </label>
        {numberField("search_seconds", "Search budget", "s", 1, 600)}
        <p className="sc-note">
          {draft.integration_method === "profile"
            ? "Search seed, starts, cycles and staged ADP policy follow the effective PhaseSmith protocol. The actual retained model and parameter count are reported below."
            : "Seed 0 · 4 phase starts · dual-space search. ADP mode affects R1 and parameter count; compare models using the same observations."}
        </p>
        {data?.structure && (
          <>
            <dl className="sc-statistics">
              <dt>Candidate R1</dt>
              <dd>{fmt(data.structure.r1 * 100)}%</dd>
              <dt>ADP model</dt>
              <dd>{data.structure.mode}</dd>
              <dt>Fitted parameters</dt>
              <dd>{data.structure.parameters}</dd>
              <dt>Atoms</dt>
              <dd>{data.structure.atoms}</dd>
              <dt>Observations / families</dt>
              <dd>
                {data.structure.observations} / {data.structure.families}
              </dd>
              <dt>Systematic-absence rows</dt>
              <dd>{data.structure.absentObservations}</dd>
              <dt>Optimizer termination</dt>
              <dd>{crystalTermination(data.structure.termination)}</dd>
            </dl>
            <p className="sc-note">
              A low R1 or reaching the search target is not a correctness
              certificate. Iteration-limited candidates are not fully converged
              refinements.
            </p>
          </>
        )}
        <Button variant="quiet" onClick={() => setStep(8)}>
          Skip structure search and export
        </Button>
      </>
    );
  return (
    <div className="sc-export">
      <Button
        variant="secondary"
        disabled={!ready || !data?.profileReport?.auditAvailable}
        onClick={() => file("audit")}
      >
        Export stage audit…
      </Button>
      <p>
        Lossless arrays for comparing masks, spots, geometry, background,
        profiles, corrections and eligibility with standalone PhaseSmith.
      </p>
      <div className="sc-export-recipe">
        <Save size={16} />
        Workflow recipe · save with the action below
      </div>
      <p>
        Source hashes, acquisition, geometry, applied parameters and explicit
        choices. Settings drafts stay in this session. Reopening verifies the
        original data.
      </p>
      <Button
        variant="secondary"
        title={
          !data?.reflectionCount
            ? "Run Intensities first."
            : "Export every integrated row, including quality flags."
        }
        disabled={!ready || !data?.reflectionCount}
        onClick={() => file("reflections")}
      >
        <Download size={16} />
        Unmerged observations…
      </Button>
      <p>
        All rows, signed intensity, reported σ, omega, corrections and quality
        flags. Profile σ includes the native equivalent-error model; eligibility
        is explicit.
      </p>
      <Button
        variant="secondary"
        title={
          !data?.usableReflections
            ? "Run Intensities and retain usable reflections first."
            : "Export usable fixed-column intensities."
        }
        disabled={!ready || !data?.usableReflections}
        onClick={() => file("hkl")}
      >
        <Download size={16} />
        Usable HKLF4 intensities…
      </Button>
      <p>
        Usable measured reflections only, with a common scale if needed for
        field widths.
      </p>
      <Button
        variant="secondary"
        title={
          !data?.structure
            ? "Run the optional Structure search first."
            : draft.integration_method === "profile"
              ? "Export the native P1 candidate and available fitted ADP tensors."
              : "Export candidate coordinates and Ueq; tensors are omitted."
        }
        disabled={!ready || !data?.structure}
        onClick={() => file("cif")}
      >
        <Download size={16} />
        Structure candidate CIF…
      </Button>
      <p>
        {!data?.structure
          ? "Run the optional Structure stage to enable this export. "
          : ""}
        {draft.integration_method === "profile"
          ? "Native P1 full-cell candidate with available fitted ADP tensors. "
          : "P1 full-cell coordinates and Ueq only; anisotropic tensors are not included. "}
        Retain the recipe and observation table for provenance.
      </p>
    </div>
  );
}

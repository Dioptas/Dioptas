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
      onCommit={(v) => update(key, v)}
      onValidation={onValidation}
      min={min}
      max={max}
      integer={["group", "min_pixels", "aperture_radius"].includes(key)}
      positive={["omega_step", "exposure", "gain"].includes(key)}
    />
  );

  const pagination = (kind: "tracks" | "reflections") => {
    if (!data) return null;
    const offset = kind === "tracks" ? data.trackOffset : data.reflectionOffset;
    const total = kind === "tracks" ? data.trackCount : data.reflectionCount;
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
            Photon counters: gain 1, read noise 0. ADU detectors need a measured
            gain.
          </p>
        </fieldset>
        <label className="sc-check">
          <Input
            type="checkbox"
            checked={draft.confirmed}
            onChange={(e) => update("confirmed", e.target.checked)}
            disabled={!ready || !data?.frames}
          />
          <span>I checked the frame order, angles, axis and count gain.</span>
        </label>
      </>
    );
  if (step === 1)
    return (
      <>
        <label className="sc-check">
          <Input
            type="checkbox"
            checked={draft.background}
            onChange={(e) => update("background", e.target.checked)}
            disabled={!ready}
          />
          <span>Fit omega background (arPLS)</span>
        </label>
        {numberField("smoothness", "Smoothness", "λ", 1e-6, 1e9)}
        <label className="sc-field">
          <span>Image</span>
          <Select
            aria-label="SCXRD image source"
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
            Mask beamstop, gaps, diamond spots or powder regions. These
            exclusions also remove counts from integration.
          </p>
          <Button
            disabled={!ready || !data?.image}
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
          disabled={!ready || !data?.frames}
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
              role="img"
              aria-label="Peaks per rotation frame"
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
              Peaks per frame · click to inspect · max{" "}
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
            <option value="usable">Usable</option>
            <option value="flagged">Flagged / excluded</option>
          </Select>
        </label>
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
                    ? "usable tracks"
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
                    <td>{crystalFlags(t.flags)}</td>
                    <td>
                      <Input
                        type="checkbox"
                        aria-label={`Exclude track ${t.id + 1}`}
                        checked={
                          pendingTrack?.id === t.id
                            ? pendingTrack.checked
                            : t.excluded
                        }
                        disabled={!ready || pendingTrack?.id === t.id}
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
        {numberField("min_cell", "Shortest vector", "Å", 1.5, 100)}
        {numberField("max_cell", "Longest vector", "Å", 1.5, 100)}
        {numberField("tolerance", "Indexing tolerance", "Å⁻¹", 0.001, 0.1)}
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
            disabled={!ready}
          />
          <span>Refine detector pose and crystal orientation</span>
        </label>
        <p className="sc-note">
          Default: keep the loaded calibration fixed. Optional refinement fits 9
          parameters; wavelength and cell lengths stay fixed. Changes must pass
          independent withheld checks.
        </p>
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
          <span>Use a supplied exact metric in the selected row setting</span>
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
        {numberField("aperture_radius", "Aperture half-width", "px", 2, 64)}
        {numberField("omega_radius", "Rocking half-width", "°", 0.01, 10)}
        {numberField("polarization", "Polarization fraction", "", 0, 1)}
        <p className="sc-summary">
          {data?.usableReflections ?? 0} usable / {data?.reflectionCount ?? 0}{" "}
          integrated tracks
        </p>
        <p className="sc-note">
          3D summation uses the declared spatial aperture and angular width
          around each measured track, including weak tails beyond detection.
          Signed counts and σ are corrected for Lorentz and polarization
          (electric vector along lab fast/y). Partials, masked, saturated and
          overlapping measurements are flagged. This pass does not perform
          profile fitting, absorption correction or empirical scan scaling.
        </p>
        {!!data?.reflections.length && (
          <TableScroll
            className="sc-table"
            tabIndex={0}
            role="region"
            aria-label="Single-crystal data table"
          >
            <DataTable>
              <caption>Unmerged observations · displayed page</caption>
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
                  <tr key={i}>
                    <td>{r.hkl.join(" ")}</td>
                    <td>{fmt(r.intensity, 2)}</td>
                    <td>{fmt(r.sigma, 2)}</td>
                    <td>{crystalFlags(r.flags)}</td>
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
            disabled={!ready}
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
              {data.scaling.fit.applied
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
        {numberField("group", "Supplied space-group number", "1–230", 1, 230)}
        <p className="sc-note">
          Use the exact setting matching the selected cell. P1 is the default; a
          space group is an explicit prior, not an automatic determination.
        </p>
        <label className="sc-field">
          <span>ADP model</span>
          <Select
            value={draft.adp}
            onChange={(e) =>
              update("adp", e.target.value as CrystalConfig["adp"])
            }
            disabled={!ready}
          >
            <option value="isotropic">Isotropic</option>
            <option value="anisotropic">Anisotropic · more parameters</option>
          </Select>
        </label>
        {numberField("search_seconds", "Search budget", "s", 1, 600)}
        <p className="sc-note">
          Seed 0 · 4 phase starts · dual-space search. ADP mode affects R1 and
          parameter count; compare models using the same observations.
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
        All rows, signed intensity, counting σ, omega, corrections and quality
        flags.
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
        P1 full-cell candidate coordinates and Ueq only; anisotropic tensors are
        not included. Retain the recipe and observation table for provenance.
      </p>
    </div>
  );
}

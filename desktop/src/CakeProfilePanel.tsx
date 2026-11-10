import { useEffect, useMemo, useRef, useState } from "react";
import { Save } from "lucide-react";
import { Button } from "./ui";
import { Field } from "./IntegrationFields";
import { PatternView } from "./PatternView";
import { coordinateValue, intensityValue } from "./readoutNumbers";
import { radialFields } from "./radialReadout";
import type { Cake, CakeProfile, Response, State } from "./types";
import type { IntegrationRun } from "./integration";
import type { ReportPlot } from "./plotReadout";
import { detectorViewport, type ViewportMemory } from "./plotViewport";
import type { ZoomMode } from "./usePlotNavigation";
import "./cakeProfile.css";

/** Only the native owner extracts samples. Local state is view/draft state. */
export function CakeProfilePanel({
  state,
  cake,
  linked,
  shift,
  bins,
  onBins,
  ready,
  run,
  reportPlot,
  onInspect,
}: {
  state: State | null;
  cake: Cake | null;
  linked: Response["linked"];
  shift: number;
  bins: number;
  onBins: (bins: number) => void;
  ready: boolean;
  run: IntegrationRun;
  reportPlot: ReportPlot;
  onInspect: (azimuth: number) => void;
}) {
  const [result, setResult] = useState<{
    key: string;
    profile: CakeProfile;
  } | null>(null);
  const viewMemory = useRef<ViewportMemory["current"]>(null);
  const viewContext = JSON.stringify([
    state?.configurationContext ?? state?.configurationIndex,
    state?.combination?.cakes,
    state?.geometry.wavelength,
    cake?.azimuthRange,
    shift,
  ]);
  const viewport = useMemo(
    () => detectorViewport(viewMemory, viewContext),
    [viewContext],
  );
  const [zoom, setZoom] = useState<ZoomMode>("rectangle");
  const args = useMemo(
    () => ({ two_theta: linked?.twoTheta, bins, shift }),
    [linked?.twoTheta, bins, shift],
  );
  const key = JSON.stringify([
    state?.revision,
    state?.configurationContext ?? state?.configurationIndex,
    state?.combination?.cakes,
    state?.geometry.wavelength,
    state?.unit,
    cake?.bufferId,
    args,
  ]);
  const eligible =
    !!state?.hasImage &&
    state.calibrated &&
    !state.integrationDirty &&
    linked != null;
  useEffect(() => {
    if (!ready || !eligible) return;
    let current = true;
    void run("cake_profile", args, "", (reply) => {
      if (current && reply.cakeProfile)
        setResult({ key, profile: reply.cakeProfile });
    });
    return () => {
      current = false;
    };
  }, [key, ready, eligible, run, args]);
  useEffect(() => () => reportPlot("profile", null), [reportPlot]);
  const profile = eligible && result?.key === key ? result.profile : null;
  const available = !!profile?.x.length;
  const pattern = useMemo(
    () => profile && { x: profile.x, y: profile.y, unit: profile.unit },
    [profile],
  );
  const azimuth = linked?.azimuth;
  const low = profile?.x[0] ?? 0;
  const high = profile?.x.at(-1) ?? 0;
  const period =
    profile && profile.x.length > 1
      ? ((high - low) * profile.x.length) / (profile.x.length - 1)
      : 0;
  const candidate =
    azimuth == null
      ? undefined
      : period >= 359
        ? low + ((((azimuth - low) % 360) + 360) % 360)
        : azimuth;
  const selectedAzimuth =
    candidate != null && candidate >= low && candidate <= high
      ? candidate
      : undefined;
  return (
    <section className="cake-profile-panel" aria-label="Azimuthal profile">
      <form
        className="cake-profile-tools"
        onSubmit={(event) => {
          event.preventDefault();
          if (!available || !ready) return;
          void run(
            "save_cake_profile",
            {
              ...args,
              directory: state?.integration.outputDirectory,
              suggested_name: `${state?.imageName?.replace(/\.[^.]+$/, "") ?? "cake"}_azimuth.xy`,
            },
            "Saving azimuthal profile…",
          );
        }}
      >
        <span>Azimuthal profile</span>
        <Field
          label="Integral width"
          displayLabel="Width (bins)"
          value={bins}
          min={1}
          max={1000000}
          step={1}
          commitOnBlur
          onChange={onBins}
        />
        <Button
          aria-label="Save azimuthal profile"
          title="Save azimuth (degrees) and native intensity; no error column"
          disabled={!ready || !available}
          type="submit"
        >
          <Save size={15} />
        </Button>
        {profile?.clipped && (
          <span
            className="cake-profile-edge"
            title="The window extends beyond the cake; missing columns contribute zero to the requested-width average"
          >
            Edge clipped
          </span>
        )}
      </form>
      {available && pattern ? (
        <PatternView
          pattern={pattern}
          viewport={viewport}
          plotLabel="Azimuthal profile"
          compact
          log={false}
          zoomMode={zoom}
          onZoomMode={setZoom}
          linkedPosition={selectedAzimuth}
          onInspect={(x) => onInspect(x)}
          onHover={(point) =>
            reportPlot(
              "profile",
              point
                ? {
                    text: `χ ${coordinateValue(point.x, point.xResolution)}° · I ${intensityValue(point.y)}`,
                    fields: [
                      ...radialFields(
                        profile.twoTheta,
                        "2th_deg",
                        state?.geometry.wavelength,
                      ),
                      {
                        label: "χ",
                        value: coordinateValue(point.x, point.xResolution),
                        title: "Azimuth (°)",
                        kind: "coordinate",
                      },
                      {
                        label: "y",
                        value: intensityValue(point.mouseY),
                        kind: "intensity",
                      },
                      {
                        label: "I",
                        value: intensityValue(point.y),
                        kind: "intensity",
                      },
                    ],
                    hint: "Left drag zooms · right drag pans · right double-click or F fits · Alt+arrows inspects samples.",
                  }
                : null,
            )
          }
        />
      ) : (
        <div className="cake-profile-empty">
          {!eligible
            ? "Click a calibrated detector, cake or pattern position."
            : profile
              ? "Selected radial position is outside the cake."
              : "Preparing azimuthal profile…"}
        </div>
      )}
    </section>
  );
}

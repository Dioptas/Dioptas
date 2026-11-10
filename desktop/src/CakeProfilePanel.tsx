import { useEffect, useMemo, useState } from "react";
import { Save } from "lucide-react";
import { Button } from "./ui";
import { Field } from "./IntegrationFields";
import { CakeProfileView } from "./CakeProfileView";
import { coordinateValue, intensityValue } from "./readoutNumbers";
import { radialFields } from "./radialReadout";
import type { Cake, CakeProfile, Response, State } from "./types";
import type { IntegrationRun } from "./integration";
import type { ReportPlot } from "./plotReadout";
import type { PlotRange } from "./usePlotNavigation";
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
  cakeView,
  onAzimuthRange,
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
  cakeView: PlotRange;
  onAzimuthRange: (range: [number, number]) => void;
}) {
  const [result, setResult] = useState<{
    key: string;
    profile: CakeProfile;
  } | null>(null);
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
        <Field
          label="Integral width"
          displayLabel="Bins"
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
            aria-label="Edge clipped"
            className="cake-profile-edge"
            title="The window extends beyond the cake; missing columns contribute zero to the requested-width average"
          >
            ⋯
          </span>
        )}
      </form>
      <CakeProfileView
        profile={available ? profile : null}
        cake={cake}
        cakeView={cakeView}
        onAzimuthRange={onAzimuthRange}
        context={JSON.stringify([
          state?.configurationContext ?? state?.configurationIndex,
          cake?.fullHeight,
          !!state?.combination?.cakes,
          state?.geometry.wavelength,
        ])}
        selectedAzimuth={linked?.azimuth}
        onInspect={(azimuth) => {
          if (ready && available) onInspect(azimuth);
        }}
        onHover={(point) =>
          reportPlot(
            "profile",
            point && profile
              ? {
                  text: `χ ${coordinateValue(point.azimuth, point.resolution)}° · I ${intensityValue(point.intensity)}`,
                  fields: [
                    ...radialFields(
                      profile.twoTheta,
                      "2th_deg",
                      state?.geometry.wavelength,
                    ),
                    {
                      label: "χ",
                      value: coordinateValue(point.azimuth, point.resolution),
                      title: "Azimuth (°)",
                      kind: "coordinate",
                    },
                    {
                      label: "I",
                      value: intensityValue(point.intensity),
                      kind: "intensity",
                    },
                  ],
                  hint: "Azimuth is shared with the cake · left drag zooms · right drag pans · F fits.",
                }
              : null,
          )
        }
      />
      {!available && (
        <div className="cake-profile-empty" role="status">
          {!eligible
            ? "Click a ring."
            : profile
              ? "Outside cake."
              : "Preparing…"}
        </div>
      )}
    </section>
  );
}

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { cakeSourcePixel } from "./cakeRadialAxis";
import { previewProfileWindow } from "./useCakeProfileResize";
import { Columns2, Save } from "lucide-react";
import { useCakeProfileWindow } from "./CakeProfileWorkspace";
import { Button } from "./ui";
import { Field } from "./IntegrationFields";
import { CakeProfileView } from "./CakeProfileView";
import { shiftCakeProfile } from "./shiftCakeProfile";
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
  run: import("./detectorProfileCommands").ProfileRun;
  reportPlot: ReportPlot;
  onInspect: (azimuth: number) => void;
  cakeView: PlotRange;
  onAzimuthRange: (range: [number, number]) => void;
}) {
  const [result, setResult] = useState<{
    key: string;
    source: string;
    profile: CakeProfile;
  } | null>(null);
  const args = useMemo(
    () => (linked ? { two_theta: linked.twoTheta, bins, shift: 0 } : null),
    [linked?.twoTheta, bins],
  );
  const source = JSON.stringify([
    state?.revision,
    state?.configurationContext ?? state?.configurationIndex,
    state?.combination?.cakes,
    state?.geometry.wavelength,
    state?.unit,
    cake?.bufferId,
    linked?.twoTheta,
  ]);
  const key = JSON.stringify([source, bins]);
  const eligible =
    !!state?.hasImage &&
    state.calibrated &&
    !state.integrationDirty &&
    linked != null;
  const active = useRef({ source, eligible });
  active.current = { source, eligible };
  const alive = useRef(true),
    fetching = useRef(false);
  const pending = useRef<{
    key: string;
    source: string;
    args: NonNullable<typeof args>;
    run: import("./detectorProfileCommands").ProfileRun;
  } | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      pending.current = null;
    };
  }, []);
  useEffect(() => {
    pending.current =
      ready && eligible && args ? { key, source, args, run } : null;
    if (fetching.current || !pending.current) return;
    fetching.current = true;
    void (async () => {
      try {
        while (alive.current && pending.current) {
          const request = pending.current;
          pending.current = null;
          await request.run("cake_profile", request.args, "", (reply) => {
            if (
              alive.current &&
              active.current.eligible &&
              active.current.source === request.source &&
              reply.cakeProfile
            )
              setResult({
                key: request.key,
                source: request.source,
                profile: reply.cakeProfile,
              });
          });
        }
      } finally {
        fetching.current = false;
      }
    })();
  }, [key, source, ready, eligible, run, args]);
  useEffect(() => () => reportPlot("profile", null), [reportPlot]);
  // The slider only wraps existing source rows, exactly like the cake display.
  // Keep extraction independent of it so moving the slider never clears the curve.
  const profile = useMemo(() => {
    if (!eligible || result?.source !== source) return null;
    return shiftCakeProfile(result.profile, shift);
  }, [eligible, result, source, shift]);
  const available = !!profile?.x.length;
  const window = useCakeProfileWindow();
  const setWindowRange = window?.setRange;
  const center = cake && profile ? cakeSourcePixel(cake, profile.radial) : null;
  const radialWindow = useMemo(
    () =>
      !profile?.radialWindow || center == null || !cake
        ? null
        : profile.bins === bins
          ? profile.radialWindow
          : previewProfileWindow(center, bins, cake.fullWidth),
    [profile?.radialWindow, profile?.bins, center, bins, cake?.fullWidth],
  );
  useLayoutEffect(() => {
    setWindowRange?.(radialWindow ?? null);
    return () => setWindowRange?.(null);
  }, [radialWindow, setWindowRange]);
  const editor = window?.editor;
  useLayoutEffect(() => {
    if (!editor) return;
    editor.current =
      available && center != null
        ? { bins, onBins, ready, center, source }
        : null;
    return () => {
      editor.current = null;
    };
  }, [editor, available, center, bins, onBins, ready, source]);
  return (
    <section className="cake-profile-panel" aria-label="Azimuthal profile">
      <form
        className="cake-profile-tools plot-controls"
        title={
          profile?.clipped
            ? "Radial window reaches the cake edge; averaging available nonzero cake bins."
            : undefined
        }
        onSubmit={(event) => {
          event.preventDefault();
          if (!available || !ready || !args) return;
          void run(
            "save_cake_profile",
            {
              ...args,
              shift,
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
          className="plot-tool-button icon-button"
          aria-label="Show profile bin width"
          type="button"
          title="Show the profile's radial averaging window on the cake"
          aria-pressed={window?.visible ?? false}
          onClick={() => window?.setVisible(!window.visible)}
        >
          <Columns2 size={15} />
        </Button>
        <Button
          className="plot-tool-button icon-button"
          aria-label="Save azimuthal profile"
          title={
            profile?.clipped
              ? "Save azimuthal profile · radial window reaches the cake edge; averaging available nonzero cake bins."
              : "Save azimuth (degrees) and native intensity averaged over nonzero cake bins; no error column"
          }
          disabled={!ready || !available}
          type="submit"
        >
          <Save size={15} />
        </Button>
      </form>
      <CakeProfileView
        profile={available ? profile : null}
        emptyMessage={
          available
            ? undefined
            : !eligible
              ? "Click a ring."
              : profile
                ? "Outside cake."
                : "Loading profile…"
        }
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
    </section>
  );
}

import { isTauri, invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Dialog } from "./ui";
import { colorMaps } from "./colorMaps";
import type { ImageDisplayPreferences } from "./types";
import "./sessionRecovery.css";

export interface RecoveryUi {
  mode: "calibration" | "integration" | "mask" | "map";
  calibrationStep: number;
  validationConvention: "pyfai" | "fit2d";
  integrationDisplay: string;
  showConfigurationControls: boolean;
  showRings: boolean;
  showNumbers: boolean;
  pickingEnabled: boolean;
  ring: number;
  logImage: boolean;
  palette: string;
  limits: [number, number];
  detectorAuto: boolean;
  cakeLog: boolean;
  cakePalette: string;
  cakeLimits: [number, number];
  cakeAuto: boolean;
  detectorPreferences: ImageDisplayPreferences;
  multiDetectorPreferences: ImageDisplayPreferences;
  cakePreferences: ImageDisplayPreferences;
  sqrtPattern: boolean;
  correctedImage: boolean;
  cakeShift: number;
}
interface RecoveryResult {
  available?: boolean;
  path?: string;
  ui?: unknown;
  missingSources?: string[];
  notice?: string | null;
  startup?: { action: string; path: string }[];
}
export async function sessionRecovery(
  operation: string,
  ui?: unknown,
): Promise<RecoveryResult> {
  if (isTauri()) return invoke("session_recovery", { operation, ui });
  // The headless native test harness supplies this adapter; ordinary browser
  // previews do not access native application recovery directories.
  const adapter = (
    window as unknown as {
      dioptasRecovery?: (
        operation: string,
        ui?: unknown,
      ) => Promise<RecoveryResult>;
    }
  ).dioptasRecovery;
  return adapter ? adapter(operation, ui) : {};
}
export function checkedRecoveryUi(value: unknown): Partial<RecoveryUi> {
  if (!value || typeof value !== "object") return {};
  const input = value as Record<string, unknown>;
  const result: Record<string, unknown> = {};
  const enums: Record<string, string[]> = {
    mode: ["calibration", "integration", "mask", "map"],
    validationConvention: ["pyfai", "fit2d"],
    integrationDisplay: ["image", "cake"],
    palette: Object.keys(colorMaps),
    cakePalette: Object.keys(colorMaps),
  };
  for (const [key, choices] of Object.entries(enums)) {
    if (typeof input[key] === "string" && choices.includes(input[key]))
      result[key] = input[key];
  }
  for (const key of [
    "showConfigurationControls",
    "showRings",
    "showNumbers",
    "pickingEnabled",
    "logImage",
    "detectorAuto",
    "cakeLog",
    "cakeAuto",
    "sqrtPattern",
    "correctedImage",
  ]) {
    if (typeof input[key] === "boolean") result[key] = input[key];
  }
  for (const [key, min, max] of [
    ["calibrationStep", 0, 3],
    ["ring", 1, 10000],
    ["cakeShift", -100000, 100000],
  ] as const) {
    const n = input[key];
    if (typeof n === "number" && Number.isInteger(n) && n >= min && n <= max)
      result[key] = n;
  }
  for (const key of ["limits", "cakeLimits"]) {
    const a = input[key];
    if (
      Array.isArray(a) &&
      a.length === 2 &&
      a.every((n) => typeof n === "number" && Number.isFinite(n)) &&
      a[0] < a[1]
    )
      result[key] = a;
  }
  for (const key of [
    "detectorPreferences",
    "multiDetectorPreferences",
    "cakePreferences",
  ]) {
    const p = input[key] as ImageDisplayPreferences | undefined;
    if (
      p &&
      ["horizontal", "vertical"].includes(p.orientation) &&
      p.auto &&
      ["percentile", "minmax", "mean3std"].includes(p.auto.mode) &&
      Number.isFinite(p.auto.percentile) &&
      p.auto.percentile >= 0.01 &&
      p.auto.percentile <= 25 &&
      typeof p.auto.filter_gaps === "boolean"
    )
      result[key] = p;
  }
  return result as Partial<RecoveryUi>;
}

export function useSessionRecovery(input: {
  ui: RecoveryUi;
  restoreUi: (ui: Partial<RecoveryUi>) => void;
  refresh: () => Promise<unknown>;
  openStartup: (action: string, path: string) => Promise<unknown>;
}) {
  const latest = useRef(input);
  latest.current = input;
  const [pending, setPending] = useState<RecoveryResult | null>(null);
  const [ready, setReady] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const start = useCallback(async () => {
    try {
      const status = await sessionRecovery("status");
      if (status.available) setPending(status);
      else {
        setPending(null);
        for (const file of status.startup ?? [])
          await latest.current.openStartup(file.action, file.path);
        setReady(true);
      }
    } catch (e) {
      setError(String(e));
      setPending({});
    }
  }, []);
  const fresh = async () => {
    try {
      await sessionRecovery("fresh");
      setPending(null);
      setError("");
      setReady(true);
    } catch (e) {
      setError(String(e));
    }
  };
  const restore = async () => {
    setWorking(true);
    setError("");
    let loaded = false;
    try {
      const result = await sessionRecovery("restore");
      loaded = true;
      await latest.current.refresh();
      latest.current.restoreUi(checkedRecoveryUi(result.ui));
      setPending(null);
      setReady(true);
      const notices = [result.notice];
      if (result.missingSources?.length)
        notices.push(
          `Restored embedded data. Original image files are unavailable; browsing or reloading them requires reconnecting their location.\n${result.missingSources.join("\n")}`,
        );
      if (notices.some(Boolean))
        setNotice(notices.filter(Boolean).join("\n\n"));
    } catch (e) {
      if (loaded) {
        setPending(null);
        setReady(false);
        setNotice(
          `Previous work was restored, but its workspace could not be displayed. The recovery file was preserved. Restart Dioptas to try again. ${String(e)}`,
        );
      } else
        setError(
          `Could not restore previous work. The recovery file was preserved. ${String(e)}`,
        );
    } finally {
      setWorking(false);
    }
  };
  const serialized = JSON.stringify(input.ui);
  useEffect(() => {
    if (ready && !pending && !saving)
      void sessionRecovery("ui", JSON.parse(serialized)).catch((e) =>
        setNotice(`Could not retain recovery display settings. ${String(e)}`),
      );
  }, [serialized, ready, pending, saving]);
  useEffect(() => {
    if (!isTauri()) return;
    const subscriptions = [
      listen<string>("dioptas-recovery-error", (e) =>
        setNotice(
          `Could not save session recovery. The previous file was preserved. ${e.payload}`,
        ),
      ),
      listen<boolean>("dioptas-recovery-saving", (e) => setSaving(e.payload)),
      listen("dioptas-startup-files", () => {
        void start();
      }),
    ];
    return () => {
      for (const subscription of subscriptions)
        void subscription.then((stop) => stop());
    };
  }, [start]);
  const dialog = pending ? (
    <Dialog
      open
      className="session-recovery-dialog"
      aria-labelledby="session-recovery-title"
      onCancel={() => {
        if (!working) void fresh();
      }}
    >
      <h2 id="session-recovery-title">Restore previous work?</h2>
      <p>
        Dioptas saved your previous session. Restore its data, configurations
        and display settings, or start a fresh workspace.
      </p>
      {pending.path && <p className="session-recovery-path">{pending.path}</p>}
      {error && <p role="alert">{error}</p>}
      <div className="session-recovery-actions">
        <Button
          variant="secondary"
          disabled={working}
          onClick={() => void fresh()}
        >
          Start fresh
        </Button>
        <Button
          variant="primary"
          autoFocus
          disabled={working}
          onClick={() => void restore()}
        >
          {working ? "Restoring…" : "Restore"}
        </Button>
      </div>
    </Dialog>
  ) : notice ? (
    <Dialog
      open
      className="session-recovery-dialog"
      aria-labelledby="session-recovery-notice"
      onCancel={() => setNotice("")}
    >
      <h2 id="session-recovery-notice">Session recovery</h2>
      <p className="session-recovery-path" role="status">
        {notice}
      </p>
      <div className="session-recovery-actions">
        <Button autoFocus onClick={() => setNotice("")}>
          OK
        </Button>
      </div>
    </Dialog>
  ) : saving ? (
    <Dialog
      open
      className="session-recovery-dialog"
      aria-labelledby="session-recovery-saving"
      onCancel={() => {}}
    >
      <h2 id="session-recovery-saving">Saving previous work…</h2>
      <p>Dioptas will close when the recovery checkpoint is saved.</p>
    </Dialog>
  ) : null;
  return { start, dialog };
}

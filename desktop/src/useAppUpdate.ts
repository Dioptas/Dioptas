import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  errorMessage,
  launchDelayMs,
  recheckIntervalMs,
  statusAfterCheck,
  type UpdateCheck,
  type UpdateStatus,
} from "./appUpdateModel";

/** The four host commands; replaceable in component tests. */
export type UpdateHost = {
  check: () => Promise<UpdateCheck>;
  download: (
    progress: (received: number, total: number | null) => void,
  ) => Promise<void>;
  apply: () => Promise<void>;
  openPage: () => Promise<void>;
};

const nativeHost: UpdateHost = {
  check: () => invoke<UpdateCheck>("update_check"),
  async download(progress) {
    const stop = await listen<{ received: number; total: number | null }>(
      "dioptas-update-progress",
      (event) => progress(event.payload.received, event.payload.total),
    );
    try {
      await invoke("update_download");
    } finally {
      stop();
    }
  },
  apply: () => invoke("update_apply"),
  openPage: () => invoke("open_update_page"),
};

const automaticKey = "dioptas-update-automatic";
const skippedKey = "dioptas-update-skipped-version";
function stored(key: string) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function store(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* The choice still applies to this session. */
  }
}

export type ManualCheck =
  | { state: "idle" }
  | { state: "checking" }
  | { state: "current" }
  | { state: "found" }
  | { state: "failed"; message: string };

export type AppUpdateController = {
  /** null until the first answer; false in previews and unmanaged builds. */
  supported: boolean | null;
  currentVersion: string | null;
  status: UpdateStatus;
  skippedVersion: string | null;
  automatic: boolean;
  manual: ManualCheck;
  setAutomatic: (automatic: boolean) => void;
  checkNow: () => void;
  download: () => void;
  apply: () => void;
  skip: () => void;
  openPage: () => void;
};

export function useAppUpdate(
  host: UpdateHost | null = isTauri() ? nativeHost : null,
  launchDelay = launchDelayMs,
): AppUpdateController {
  const [supported, setSupported] = useState<boolean | null>(
    host ? null : false,
  );
  const [currentVersion, setCurrentVersion] = useState<string | null>(null);
  const [status, setStatus] = useState<UpdateStatus>({ phase: "idle" });
  const [skippedVersion, setSkippedVersion] = useState(() =>
    stored(skippedKey),
  );
  const [automatic, setAutomaticState] = useState(
    () => stored(automaticKey) !== "false",
  );
  const [manual, setManual] = useState<ManualCheck>({ state: "idle" });
  const checking = useRef(false);

  // Mirror the status so an action reads the latest phase and starts its host
  // call exactly once, outside React's state updater.
  const latest = useRef(status);
  latest.current = status;
  const move = useCallback((next: UpdateStatus) => {
    latest.current = next;
    setStatus(next);
  }, []);

  const check = useCallback(
    async (requested: boolean) => {
      if (!host || checking.current) return;
      checking.current = true;
      if (requested) setManual({ state: "checking" });
      try {
        const result = await host.check();
        setSupported(result.supported);
        setCurrentVersion(result.currentVersion);
        move(statusAfterCheck(result, latest.current));
        if (requested) {
          setManual({ state: result.update ? "found" : "current" });
          // Asking explicitly shows a version that was skipped earlier.
          store(skippedKey, null);
          setSkippedVersion(null);
        }
      } catch (error) {
        // Offline instruments are normal. Only a requested check reports it.
        if (requested)
          setManual({ state: "failed", message: errorMessage(error) });
      } finally {
        checking.current = false;
      }
    },
    [host, move],
  );

  useEffect(() => {
    if (!host || !automatic) return;
    const first = setTimeout(() => void check(false), launchDelay);
    const repeat = setInterval(() => void check(false), recheckIntervalMs);
    return () => {
      clearTimeout(first);
      clearInterval(repeat);
    };
  }, [host, automatic, check, launchDelay]);

  const download = useCallback(() => {
    const previous = latest.current;
    if (
      !host ||
      (previous.phase !== "available" &&
        !(previous.phase === "error" && previous.during === "download"))
    )
      return;
    const update = previous.update;
    move({ phase: "downloading", update, received: 0, total: null });
    host
      .download((received, total) => {
        if (latest.current.phase === "downloading")
          move({ phase: "downloading", update, received, total });
      })
      .then(
        () => move({ phase: "ready", update }),
        (error) =>
          move({
            phase: "error",
            update,
            message: errorMessage(error),
            during: "download",
          }),
      );
  }, [host, move]);

  const apply = useCallback(() => {
    const previous = latest.current;
    if (
      !host ||
      (previous.phase !== "ready" &&
        !(previous.phase === "error" && previous.during === "install"))
    )
      return;
    const update = previous.update;
    move({ phase: "installing", update });
    // On success the application restarts and this promise never settles.
    host.apply().catch((error) =>
      move({
        phase: "error",
        update,
        message: errorMessage(error),
        during: "install",
      }),
    );
  }, [host, move]);

  const skip = useCallback(() => {
    if (status.phase !== "available") return;
    store(skippedKey, status.update.version);
    setSkippedVersion(status.update.version);
  }, [status]);

  const setAutomatic = useCallback((next: boolean) => {
    store(automaticKey, next ? null : "false");
    setAutomaticState(next);
  }, []);

  const checkNow = useCallback(() => void check(true), [check]);
  const openPage = useCallback(() => {
    void host?.openPage().catch(() => undefined);
  }, [host]);

  return useMemo(
    () => ({
      supported,
      currentVersion,
      status,
      skippedVersion,
      automatic,
      manual,
      setAutomatic,
      checkNow,
      download,
      apply,
      skip,
      openPage,
    }),
    [
      supported,
      currentVersion,
      status,
      skippedVersion,
      automatic,
      manual,
      setAutomatic,
      checkNow,
      download,
      apply,
      skip,
      openPage,
    ],
  );
}

// Update notification state shared by the sidebar notice and Settings.
// Pure functions only: the native calls live in useAppUpdate.ts.

export type UpdateInfo = {
  version: string;
  notes: string | null;
  /** Unix seconds from the release manifest, when present. */
  published: number | null;
  /** The verified package is already held by the host. */
  downloaded: boolean;
};

export type UpdateCheck = {
  supported: boolean;
  currentVersion: string;
  update: UpdateInfo | null;
};

export type UpdateStatus =
  | { phase: "idle" }
  | { phase: "available"; update: UpdateInfo }
  | {
      phase: "downloading";
      update: UpdateInfo;
      received: number;
      total: number | null;
    }
  | { phase: "ready"; update: UpdateInfo }
  | { phase: "installing"; update: UpdateInfo }
  | {
      phase: "error";
      update: UpdateInfo;
      message: string;
      /** The step to repeat when the user tries again. */
      during: "download" | "install";
    };

/** A launch check runs after start-up work has settled. */
export const launchDelayMs = 8_000;
/** Long sessions at an instrument look again a few times per day. */
export const recheckIntervalMs = 6 * 60 * 60 * 1000;

export function statusAfterCheck(
  check: UpdateCheck,
  previous: UpdateStatus,
): UpdateStatus {
  if (!check.supported || !check.update) return { phase: "idle" };
  const update = check.update;
  // A periodic check must not interrupt a download or installation that is
  // already running for the same version.
  if (
    (previous.phase === "downloading" || previous.phase === "installing") &&
    previous.update.version === update.version
  )
    return previous;
  return update.downloaded
    ? { phase: "ready", update }
    : { phase: "available", update };
}

/**
 * The sidebar notice stays hidden for a version the user skipped. A package
 * that is already downloading or downloaded was chosen explicitly and stays
 * visible.
 */
export function noticeVisible(
  status: UpdateStatus,
  skippedVersion: string | null,
): boolean {
  if (status.phase === "idle") return false;
  if (status.phase !== "available") return true;
  return status.update.version !== skippedVersion;
}

export function downloadFraction(status: UpdateStatus): number | null {
  if (status.phase !== "downloading" || !status.total) return null;
  return Math.max(0, Math.min(1, status.received / status.total));
}

export function formatMegabytes(bytes: number): string {
  const megabytes = bytes / 1_000_000;
  return megabytes >= 100 ? megabytes.toFixed(0) : megabytes.toFixed(1);
}

export function progressLabel(status: UpdateStatus): string {
  if (status.phase !== "downloading") return "";
  const received = formatMegabytes(status.received);
  return status.total
    ? `${received} of ${formatMegabytes(status.total)} MB`
    : `${received} MB`;
}

export function noticeLabel(status: UpdateStatus): string {
  switch (status.phase) {
    case "idle":
      return "";
    case "available":
      return `Update available: Dioptas ${status.update.version}`;
    case "downloading": {
      const fraction = downloadFraction(status);
      return fraction === null
        ? `Downloading Dioptas ${status.update.version}`
        : `Downloading Dioptas ${status.update.version}: ${Math.round(fraction * 100)}%`;
    }
    case "ready":
      return `Restart to update to Dioptas ${status.update.version}`;
    case "installing":
      return `Installing Dioptas ${status.update.version}`;
    case "error":
      return `Update to Dioptas ${status.update.version} needs attention`;
  }
}

/** Release notes are shown as plain text; trim what a popover cannot hold. */
export function notesPreview(notes: string | null, limit = 1200): string {
  const text = (notes ?? "").replace(/\r\n?/g, "\n").trim();
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const paragraph = cut.lastIndexOf("\n");
  return `${cut.slice(0, paragraph > limit / 2 ? paragraph : limit).trimEnd()}\n…`;
}

export function errorMessage(error: unknown): string {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  return "The update could not be completed.";
}

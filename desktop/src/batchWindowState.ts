import type { BatchData } from "./batchDomain";

export const BATCH_BUSY_MESSAGE =
  "The main window is busy. Try again when processing finishes.";

/** The main window owns scientific errors; a fallback RPC busy message must
 * not hide its subsequently published export failure. Keep real local errors.
 */
export function batchWindowError(local: string | null, parent: string | null) {
  return local === BATCH_BUSY_MESSAGE ? parent || local : local || parent;
}

// Binary matrix data stays on the native raster bridge. Only the changing
// selection/pattern/guide fields cross the window notification channel.
type Version = { base: number; sequence: number };
export type BatchWindowUpdate = Version &
  (
    | { kind: "clear"; id: null }
    | { kind: "snapshot" | "retain"; id: string }
    | {
        kind: "selection";
        id: string;
        selected: number;
        pattern: BatchData["pattern"];
        position: BatchData["position"];
        phaseLines: BatchData["phaseLines"];
      }
  );
const selectionFields = new Set([
  "selected",
  "pattern",
  "position",
  "phaseLines",
]);

// Worker metadata is decoded into fresh objects on every response. Compare
// its values, while identifying the matrix by its cached binary buffer ID.
function sameMetadata(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (!a || !b || typeof a !== "object" || typeof b !== "object") return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const left = a as Record<string, unknown>,
    right = b as Record<string, unknown>;
  const keys = Object.keys(left);
  return (
    keys.length === Object.keys(right).length &&
    keys.every(
      (key) => Object.hasOwn(right, key) && sameMetadata(left[key], right[key]),
    )
  );
}
function sameMatrix(a: BatchData["raster"], b: BatchData["raster"]) {
  const { data: leftData, ...left } = a,
    { data: rightData, ...right } = b;
  return (
    (a.bufferId ?? leftData) === (b.bufferId ?? rightData) &&
    sameMetadata(left, right)
  );
}

/** Mirror the main window's applied result; any other model change invalidates
 * the child's matrix/metadata together, including newly added model fields. */
export function batchWindowUpdate(
  previous: BatchData | null | undefined,
  current: BatchData | null,
  version: Version,
  initial = false,
): BatchWindowUpdate {
  const sequence = version.sequence + 1;
  if (!current)
    return {
      kind: "clear",
      id: null,
      base: version.base + Number(initial || previous !== null),
      sequence,
    };
  if (!initial && previous === current)
    return { kind: "retain", id: current.id, base: version.base, sequence };
  const keys = new Set([
    ...Object.keys(previous ?? {}),
    ...Object.keys(current),
  ]);
  const selectionOnly =
    !initial &&
    previous &&
    [...keys].every(
      (key) =>
        selectionFields.has(key) ||
        (key === "raster"
          ? sameMatrix(previous.raster, current.raster)
          : sameMetadata(
              previous[key as keyof BatchData],
              current[key as keyof BatchData],
            )),
    );
  if (!selectionOnly)
    return {
      kind: "snapshot",
      id: current.id,
      base: version.base + 1,
      sequence,
    };
  return {
    kind: "selection",
    id: current.id,
    base: version.base,
    sequence,
    selected: current.selected,
    pattern: current.pattern,
    position: current.position,
    phaseLines: current.phaseLines,
  };
}

/** A late matrix read must not undo a newer selection or a replaced series. */
export class BatchWindowSync {
  private desired: BatchWindowUpdate | null = null;
  private sequence = -1;
  private model: BatchData | null = null;
  private loadedBase: number | null = null;
  private requestedBase: number | null = null;
  private refreshing = false;
  private queued = false;
  private disposed = false;
  private readonly read: () => Promise<BatchData | null | undefined>;
  private readonly apply: (batch: BatchData | null) => void;
  constructor(
    read: () => Promise<BatchData | null | undefined>,
    apply: (batch: BatchData | null) => void,
  ) {
    this.read = read;
    this.apply = apply;
  }
  receive(update: BatchWindowUpdate, ready: boolean): boolean {
    if (this.disposed || update.sequence <= this.sequence) return false;
    this.sequence = update.sequence;
    // Retain status notifications must keep a selection waiting on its matrix.
    if (update.kind !== "retain" || this.desired?.base !== update.base)
      this.desired = update;
    if (update.kind === "clear") {
      this.model = null;
      this.loadedBase = update.base;
      this.apply(null);
      return true;
    }
    if (this.loadedBase === update.base && this.model?.id === update.id) {
      if (update.kind === "selection") this.publish(this.model, update);
      return true;
    }
    if (ready && this.requestedBase !== update.base) {
      this.requestedBase = update.base;
      this.queued = true;
      void this.refresh();
    }
    return true;
  }
  private publish(batch: BatchData, update: BatchWindowUpdate) {
    this.model =
      update.kind === "selection"
        ? {
            ...batch,
            selected: update.selected,
            pattern: update.pattern,
            position: update.position,
            phaseLines: update.phaseLines,
          }
        : batch;
    this.loadedBase = update.base;
    this.apply(this.model);
  }
  private async refresh() {
    if (this.refreshing) return;
    this.refreshing = true;
    try {
      while (this.queued && !this.disposed) {
        this.queued = false;
        const target = this.desired;
        if (!target || target.kind === "clear") continue;
        const batch = await this.read();
        if (this.disposed || this.desired?.base !== target.base) continue;
        if (batch?.id === target.id) this.publish(batch, this.desired);
        else this.requestedBase = null; // A failed read can retry on the next status.
      }
    } finally {
      this.refreshing = false;
    }
  }
  dispose() {
    this.disposed = true;
  }
}

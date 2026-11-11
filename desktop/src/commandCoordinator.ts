/** Scheduling policy for the main workspace's processor commands. Scientific
 * response application, drafts, dialogs and display preparation stay with App.
 */
type InteractiveKind =
  "mask" | "background" | "correction" | "overlay" | "frame" | "map-region";

export interface CommandPolicy {
  action: string;
  quiet: boolean;
  backgroundJob: boolean;
  mayQueue: boolean;
  interactive: InteractiveKind | null;
}
export type CommandResult<T> =
  | { status: "applied"; value: T }
  | { status: "cancelled"; value?: T }
  | { status: "deferred"; value?: T }
  | { status: "failed"; error: unknown };
export type CommandOutcome<T> =
  CommandResult<T> | { status: "skipped"; reason: "busy" | "superseded" };

export function commandPolicy({
  action,
  args,
  message,
  mode,
  overlayHistory = false,
  queueIfBusy = false,
}: {
  action: string;
  args: Record<string, unknown>;
  message: string;
  mode: string;
  overlayHistory?: boolean;
  queueIfBusy?: boolean;
}): CommandPolicy {
  const overlay =
    action === "batch_waterfall" ||
    (action === "integration_overlay" && args.operation !== "load") ||
    overlayHistory;
  const background = action === "integration_background" && message === "";
  const mapRegion = action === "map_roi" && message === "";
  const correction =
    message === "" &&
    [
      "integration_correction",
      "integration_image_background",
      "integration_flat_field",
      "integration_transfer",
    ].includes(action);
  const frame =
    ["map_select", "batch_select", "next_image"].includes(action) ||
    (action === "integration_navigation" &&
      (args.frame !== undefined || args.direction !== undefined));
  const phaseConditions =
    action === "integration_phase" &&
    args.operation === "update" &&
    (typeof args.pressure === "number" || typeof args.temperature === "number");
  const mask =
    mode === "mask" &&
    (action === "mask_stroke" ||
      (action === "mask_edit" &&
        ["rectangle", "circle", "polygon", "arc"].includes(
          String(args.operation),
        )));
  const displayOnly =
    action === "settings" &&
    typeof args.transparent_mask === "boolean" &&
    Object.keys(args).length === 1;
  const quiet =
    displayOnly ||
    overlay ||
    mask ||
    background ||
    mapRegion ||
    correction ||
    phaseConditions ||
    frame ||
    [
      "integration_phase_state",
      "integration_phase_guides",
      "integration_autoprocess_poll",
      "cake_profile",
      "validation_position",
      "image_levels",
      "image_batch_mode",
    ].includes(action);
  return {
    action,
    quiet,
    backgroundJob: quiet && (background || overlay),
    mayQueue:
      queueIfBusy ||
      mapRegion ||
      correction ||
      background ||
      phaseConditions ||
      frame ||
      [
        "cake_profile",
        "integration_phase_state",
        "integration_phase_guides",
        "image_levels",
        "image_batch_mode",
      ].includes(action),
    interactive: mask
      ? "mask"
      : overlay
        ? "overlay"
        : frame
          ? "frame"
          : mapRegion
            ? "map-region"
            : background
              ? "background"
              : correction
                ? "correction"
                : null,
  };
}

/** One serial queue with explicit outcomes. Every accepted reservation releases
 * in finally, including obsolete work and failed predicates/executors. This
 * keeps a rejected edit from poisoning subsequent commands or admission state.
 */
export class CommandCoordinator {
  private active: CommandPolicy | null = null;
  private tail: Promise<void> | null = null;
  private interactivePending = 0;

  get busy() {
    return this.active !== null;
  }
  get pending() {
    return this.tail !== null;
  }

  accepts(policy: CommandPolicy) {
    if (policy.action === "integration_autoprocess_poll" && this.pending)
      return false;
    return (
      !this.active ||
      this.active.quiet ||
      this.active.action === "integration_autoprocess_poll" ||
      this.interactivePending > 0 ||
      policy.mayQueue
    );
  }

  async execute<T>(
    policy: CommandPolicy,
    operation: () => Promise<CommandResult<T>>,
    isCurrent?: () => boolean,
  ): Promise<CommandOutcome<T>> {
    if (!this.accepts(policy)) return { status: "skipped", reason: "busy" };
    const previous = this.tail;
    let release!: () => void;
    const completion = new Promise<void>((resolve) => {
      release = resolve;
    });
    this.tail = completion;
    if (policy.interactive) this.interactivePending++;
    let started = false;
    try {
      if (previous) await previous;
      if (isCurrent && !isCurrent())
        return { status: "skipped", reason: "superseded" };
      this.active = policy;
      started = true;
      return await operation();
    } catch (error) {
      return { status: "failed", error };
    } finally {
      if (started) this.active = null;
      if (policy.interactive) this.interactivePending--;
      if (this.tail === completion) this.tail = null;
      release();
    }
  }
}

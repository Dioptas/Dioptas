import type { Invoke, Run } from "../../src/commandContracts";
import type { ScheduledRun } from "../../src/workspaceCommands";
declare const invoke: Invoke;
declare const run: Run;
declare const scheduled: ScheduledRun;
// @ts-expect-error Known required fields must not hide an extra payload key.
invoke("pixel", { x: 1, y: 2, typo: true });
// @ts-expect-error Shared metadata must not hide an extra payload key.
invoke("state", { requested_products: { cake: false }, typo: true });
// @ts-expect-error Queue helpers must also reject direct extra keys.
run("batch_select", { index: 0, typo: 1 });
// @ts-expect-error Scheduling options must not permit extra payload fields.
scheduled("batch_select", { index: 0, typo: 1 }, "Loading…", undefined, () => true, true, false);
invoke("state", { requested_products: { cake: false } });

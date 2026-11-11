import type { Invoke, Run } from "../../src/commandContracts";
declare const invoke: Invoke;
declare const run: Run;
// @ts-expect-error Known required fields must not hide an extra payload key.
invoke("pixel", { x: 1, y: 2, typo: true });
// @ts-expect-error Shared metadata must not hide an extra payload key.
invoke("state", { requested_products: { cake: false }, typo: true });
// @ts-expect-error Queue helpers must also reject direct extra keys.
run("batch_select", { index: 0, typo: 1 });
invoke("state", { requested_products: { cake: false } });

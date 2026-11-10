import type { Invoke } from "./types";

/** One display-demand policy for image browsing, Batch, Map and validation. */
export function wantsCake(view: {
  mode: string;
  display: string;
  calibrationStep: number;
  concealed: boolean;
  combinedCake: boolean;
  profile?: boolean;
}): boolean {
  return (
    view.combinedCake ||
    (!view.concealed &&
      ((view.mode === "integration" &&
        (view.display === "cake" || view.profile === true)) ||
        (view.mode === "calibration" && view.calibrationStep === 3)))
  );
}
export function requestedDisplayProducts(
  view: Parameters<typeof wantsCake>[0] & { showRings: boolean },
) {
  return {
    cake: wantsCake(view),
    rings: view.mode === "calibration" && view.showRings && !view.concealed,
  };
}

export function withRequestedProducts(
  invoke: Invoke,
  products: () => { cake: boolean; rings: boolean },
): Invoke {
  return (action, payload = {}) =>
    invoke(action, {
      ...payload,
      requested_products: {
        cake:
          action === "display_products"
            ? payload.cake === true
            : action === "integration_save_image" && payload.source === "cake"
              ? true
              : products().cake,
        rings:
          action === "display_products" && typeof payload.rings === "boolean"
            ? payload.rings
            : products().rings,
      },
    });
}

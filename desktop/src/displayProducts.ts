import type { CheckedInvocation } from "./commandContracts";
import type { Invoke, CommandInvocation } from "./commandContracts";
import { withTransportMetadata, forwardInvoke } from "./commandDispatch.ts";

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
  return <A extends CommandInvocation>(...call: CheckedInvocation<A>) => {
    const [action, payload] = call;
    const explicitCake =
      action === "display_products"
        ? !!payload && "cake" in payload && payload.cake === true
        : action === "integration_save_image" &&
            payload &&
            "source" in payload &&
            payload.source === "cake"
          ? true
          : products().cake;
    const explicitRings =
      action === "display_products" &&
      payload &&
      "rings" in payload &&
      typeof payload.rings === "boolean"
        ? payload.rings
        : products().rings;
    return forwardInvoke<A>(
      invoke,
      withTransportMetadata<A>(call, {
        requested_products: { cake: explicitCake, rings: explicitRings },
      }),
    );
  };
}

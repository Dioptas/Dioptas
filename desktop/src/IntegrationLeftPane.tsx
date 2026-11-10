import { useEffect, useState, type ReactNode } from "react";
import { useDetectorDetached } from "./DetectorWindow";
import { TabList } from "./TabList";
import { useIntegrationLayout } from "./IntegrationWorkspace";

/** Keep both renderers mounted and sized while the compact view switches. */
export function IntegrationLeftPane({
  active,
  batch,
  children,
}: {
  active: boolean;
  batch: ReactNode;
  children: ReactNode;
}) {
  const imageDetached = useDetectorDetached();
  const { narrow } = useIntegrationLayout();
  const [view, setView] = useState<"image" | "batch">("batch");
  const batchOpen = !!batch;
  useEffect(() => {
    if (batchOpen) setView("batch");
  }, [batchOpen]);
  const switched = narrow && batchOpen && !imageDetached;
  if (!active) return <div className="plot-group-contents">{children}</div>;
  return (
    <div className="integration-left-pane" data-switched={switched}>
      {switched && (
        <TabList
          label="Integration left view"
          className="integration-left-tabs"
          value={view}
          onChange={setView}
          options={[
            { value: "image", label: "Image" },
            { value: "batch", label: "Batch" },
          ]}
        />
      )}
      <div className="integration-left-content">
        <div
          className="integration-image-pane"
          data-left-concealed={switched && view !== "image"}
          inert={switched && view !== "image"}
          aria-hidden={(switched && view !== "image") || undefined}
        >
          {children}
        </div>
        <div
          className="integration-batch-pane"
          data-left-concealed={switched && view !== "batch"}
          inert={switched && view !== "batch"}
          aria-hidden={(switched && view !== "batch") || undefined}
        >
          {batch}
        </div>
      </div>
    </div>
  );
}

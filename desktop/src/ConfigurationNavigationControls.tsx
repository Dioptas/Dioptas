import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./ui";
import type { IntegrationRun } from "./integration";
import { useConfigurationBrowsing } from "./configurationBrowsing";
import "./configurationNavigation.css";

export function ConfigurationNavigationControls({
  ready,
  run,
}: {
  ready: boolean;
  run: IntegrationRun;
}) {
  const rules = useConfigurationBrowsing();
  const scope = "all configurations";
  const navigate = (target: "file" | "folder", direction: number) =>
    void run(
      "configuration_navigation",
      {
        target,
        direction,
        scope: "all",
        number_position: rules.fileNumber,
        step: target === "file" ? rules.fileStep : rules.folderStep,
        folder_number_position: rules.folderNumber,
        folder_filename_position: rules.folderFileNumber,
        folder_filename_step: rules.folderFileStep,
      },
      "Browsing detector configurations…",
    );
  return (
    <div
      className="configuration-navigation"
      role="group"
      aria-label="Configuration browsing"
      title="Configure scope, numbered parts and step sizes in Settings → Configurations."
    >
      {(["file", "folder"] as const).map((target) => (
        <div
          key={target}
          className="configuration-navigation-group"
          role="group"
          aria-label={`Browse configuration ${target}s`}
        >
          <span>{target === "file" ? "File" : "Folder"}</span>
          <Button
            aria-label={`Previous ${target}s in ${scope}`}
            title={`Previous ${target} in ${scope}`}
            disabled={!ready}
            onClick={() => navigate(target, -1)}
          >
            <ChevronLeft size={16} />
          </Button>
          <Button
            aria-label={`Next ${target}s in ${scope}`}
            title={`Next ${target} in ${scope}`}
            disabled={!ready}
            onClick={() => navigate(target, 1)}
          >
            <ChevronRight size={16} />
          </Button>
        </div>
      ))}
    </div>
  );
}

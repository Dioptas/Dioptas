import { RefreshCw } from "lucide-react";
import { Button, Input } from "./ui";
import type { AppUpdateController } from "./useAppUpdate";

/** Settings › General: the automatic check and an explicit "check now". */
export function AppUpdateSettings({
  controller,
}: {
  controller: AppUpdateController;
}) {
  const { supported, currentVersion, status, manual } = controller;
  const pending = status.phase === "idle" ? null : status.update.version;
  const result =
    supported === false
      ? "This build is not updated automatically. Installed releases check GitHub for new versions."
      : manual.state === "checking"
        ? "Checking…"
        : manual.state === "failed"
          ? manual.message
          : pending
            ? `Dioptas ${pending} is available. Use the update button above Settings in the sidebar.`
            : manual.state === "current"
              ? "Dioptas is up to date."
              : "";
  return (
    <section className="settings-card app-update-settings">
      <div className="settings-card-heading">
        <RefreshCw size={18} />
        <h3>Updates</h3>
      </div>
      <p>
        {currentVersion ? `You are using Dioptas ${currentVersion}. ` : ""}
        New versions are downloaded only when you choose to, and installed when
        you restart.
      </p>
      <div className="settings-preference-row">
        <div>
          <label htmlFor="settings-update-automatic">
            Check for updates automatically
          </label>
          <p id="settings-update-automatic-description">
            Looks for a new release shortly after start and a few times per day.
            Nothing else is sent. Switch off on computers without internet
            access or with managed installations.
          </p>
        </div>
        <Input
          id="settings-update-automatic"
          type="checkbox"
          disabled={supported === false}
          checked={controller.automatic && supported !== false}
          onChange={(event) => controller.setAutomatic(event.target.checked)}
          aria-describedby="settings-update-automatic-description"
        />
      </div>
      <div className="app-update-settings-check">
        <Button
          type="button"
          disabled={supported === false || manual.state === "checking"}
          onClick={controller.checkNow}
        >
          Check for updates
        </Button>
        <span
          role="status"
          className={manual.state === "failed" ? "app-update-error" : undefined}
        >
          {result}
        </span>
      </div>
    </section>
  );
}

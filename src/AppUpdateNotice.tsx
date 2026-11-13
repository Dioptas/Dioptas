import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { Download, RotateCw, TriangleAlert } from "lucide-react";
import { Button, Popover, Portal } from "./ui";
import {
  downloadFraction,
  noticeLabel,
  noticeVisible,
  notesPreview,
  progressLabel,
} from "./appUpdateModel";
import type { AppUpdateController } from "./useAppUpdate";
import "./appUpdate.css";

/**
 * A quiet sidebar entry above Settings. It appears only when a newer release
 * exists and never opens by itself; restarting is always the user's action.
 */
export function AppUpdateNotice({
  controller,
  ready,
}: {
  controller: AppUpdateController;
  /** False while a command is processing; restarting would interrupt it. */
  ready: boolean;
}) {
  const { status, currentVersion } = controller;
  const visible = noticeVisible(status, controller.skippedVersion);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<CSSProperties>({});
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const id = useId();
  const shown = open && visible;

  useLayoutEffect(() => {
    if (!shown) return;
    const place = () => {
      const anchor = trigger.current?.getBoundingClientRect();
      const panel = popup.current;
      if (!anchor || !panel) return;
      // Open beside the whole sidebar rather than over its edge.
      const rail =
        trigger.current?.closest(".mode-navigation")?.getBoundingClientRect()
          .right ?? anchor.right;
      const width = Math.min(380, window.innerWidth - 24);
      const height = panel.offsetHeight;
      setPosition({
        width,
        left: Math.max(12, Math.min(rail + 8, window.innerWidth - width - 12)),
        // Grow upward from the sidebar entry and stay inside the window.
        top: Math.max(
          12,
          Math.min(anchor.bottom - height, window.innerHeight - height - 12),
        ),
      });
    };
    place();
    const observer = new ResizeObserver(place);
    if (popup.current) observer.observe(popup.current);
    window.addEventListener("resize", place);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", place);
    };
  }, [shown, status.phase]);

  useEffect(() => {
    if (!shown) return;
    const outside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !popup.current?.contains(target) &&
        !trigger.current?.contains(target)
      )
        setOpen(false);
    };
    document.addEventListener("pointerdown", outside, true);
    return () => document.removeEventListener("pointerdown", outside, true);
  }, [shown]);

  useEffect(() => {
    if (shown)
      popup.current
        ?.querySelector<HTMLElement>("button:not(:disabled)")
        ?.focus({ preventScroll: true });
  }, [shown, status.phase]);

  const close = () => {
    setOpen(false);
    trigger.current?.focus({ preventScroll: true });
  };
  const fraction = downloadFraction(status);
  const label = noticeLabel(status);
  const notes =
    status.phase === "idle" ? "" : notesPreview(status.update.notes);
  const Icon =
    status.phase === "error"
      ? TriangleAlert
      : status.phase === "ready" || status.phase === "installing"
        ? RotateCw
        : Download;

  return (
    // The wrapper is always present so the sidebar can account for its height.
    <div className="navigation-update" data-phase={status.phase}>
      {visible && (
        <Button
          ref={trigger}
          className="workspace-nav navigation-update-button"
          aria-label={label}
          aria-haspopup="dialog"
          aria-expanded={shown}
          aria-controls={shown ? id : undefined}
          title={label}
          onClick={() => setOpen(!open)}
        >
          <Icon size={20} />
          <span className="navigation-update-dot" aria-hidden="true" />
          {status.phase === "downloading" && (
            <span
              className="navigation-update-progress"
              aria-hidden="true"
              style={{ "--update-fraction": fraction ?? 0 } as CSSProperties}
            />
          )}
        </Button>
      )}
      {shown && status.phase !== "idle" && (
        <Portal>
          <Popover
            id={id}
            ref={popup}
            className="app-update-popover"
            role="dialog"
            aria-label="Application update"
            style={position}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                close();
              }
            }}
          >
            <h2>
              {status.phase === "ready" || status.phase === "installing"
                ? `Dioptas ${status.update.version} is ready to install`
                : `Dioptas ${status.update.version} is available`}
            </h2>
            {currentVersion && (
              <p className="app-update-current">
                You are using {currentVersion}.
              </p>
            )}
            {notes && status.phase === "available" && (
              <pre className="app-update-notes" tabIndex={0}>
                {notes}
              </pre>
            )}
            {status.phase === "downloading" && (
              <div className="app-update-download">
                <progress
                  aria-label="Download progress"
                  max={1}
                  value={fraction ?? undefined}
                />
                <p aria-live="polite">
                  Downloading… {progressLabel(status)}. You can keep working.
                </p>
              </div>
            )}
            {status.phase === "ready" && (
              <p>
                Dioptas closes, installs the update and opens again. Save your
                project first; unsaved changes are not kept.
              </p>
            )}
            {status.phase === "installing" && (
              <p aria-live="polite">Installing… Dioptas restarts shortly.</p>
            )}
            {status.phase === "error" && (
              <p className="app-update-error" role="alert">
                {status.message}
              </p>
            )}
            <div className="app-update-actions">
              {status.phase === "available" && (
                <>
                  <Button
                    type="button"
                    variant="primary"
                    onClick={controller.download}
                  >
                    Download update
                  </Button>
                  <Button type="button" onClick={close}>
                    Later
                  </Button>
                  <Button
                    type="button"
                    variant="quiet"
                    onClick={() => {
                      controller.skip();
                      setOpen(false);
                    }}
                  >
                    Skip this version
                  </Button>
                </>
              )}
              {status.phase === "ready" && (
                <>
                  <Button
                    type="button"
                    variant="primary"
                    disabled={!ready}
                    title={
                      ready
                        ? undefined
                        : "Available when the current processing has finished"
                    }
                    onClick={controller.apply}
                  >
                    Restart to update
                  </Button>
                  <Button type="button" onClick={close}>
                    Later
                  </Button>
                </>
              )}
              {status.phase === "error" && (
                <>
                  <Button
                    type="button"
                    variant="primary"
                    disabled={status.during === "install" && !ready}
                    onClick={
                      status.during === "download"
                        ? controller.download
                        : controller.apply
                    }
                  >
                    Try again
                  </Button>
                  <Button type="button" onClick={controller.openPage}>
                    Open download page
                  </Button>
                </>
              )}
              {status.phase === "downloading" && (
                <Button type="button" onClick={close}>
                  Hide
                </Button>
              )}
            </div>
            {status.phase === "ready" && !ready && (
              <p className="app-update-hint">
                Restarting is available when the current processing has
                finished.
              </p>
            )}
          </Popover>
        </Portal>
      )}
    </div>
  );
}

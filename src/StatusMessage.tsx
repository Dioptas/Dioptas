import { Button } from "./ui";
import { useState, useRef } from "react";
import { Dialog, DialogHeader } from "./Dialog";

/** Keep live-region roles stable; the complete error is keyboard accessible. */
export function StatusMessage({
  error,
  message,
}: {
  error: string | null;
  message: string;
}) {
  const [details, setDetails] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const detailsButton = useRef<HTMLButtonElement>(null);
  return (
    <>
      <span
        role="status"
        aria-live="polite"
        title={error ? undefined : message}
      >
        {error ? "" : message}
      </span>
      <span role="alert" aria-atomic="true" title={error ?? undefined}>
        {error ?? ""}
      </span>
      {error && (
        <Button
          ref={detailsButton}
          className="quiet status-action"
          aria-label="View error details"
          onClick={() => {
            setDetails(true);
            setCopied(false);
            setCopyFailed(false);
          }}
        >
          Details
        </Button>
      )}
      {details && error && (
        <Dialog
          returnFocusTarget={detailsButton.current}
          className="ui-error-dialog"
          aria-label="Error details"
          onDismiss={() => setDetails(false)}
        >
          <DialogHeader
            title="Error details"
            closeLabel="Close error details"
            onClose={() => setDetails(false)}
          />
          <pre className="ui-error-detail" tabIndex={0}>
            {error}
          </pre>
          <div className="ui-dialog-actions">
            <Button
              className="secondary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(error);
                  setCopied(true);
                  setCopyFailed(false);
                } catch {
                  setCopyFailed(true);
                }
              }}
            >
              {copied ? "Copied" : "Copy error"}
            </Button>
            <Button className="primary" onClick={() => setDetails(false)}>
              Close
            </Button>
          </div>
          {copyFailed && (
            <p className="ui-display-note" role="status">
              Clipboard access is unavailable. Select the message above and copy
              it.
            </p>
          )}
        </Dialog>
      )}
    </>
  );
}

import { useLayoutEffect, useRef, useState } from "react";
import "./operationErrorDialog.css";

import type { OperationFailure } from "./errorReporting";

export function OperationErrorDialog({
  failure,
  onClose,
}: {
  failure: OperationFailure;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const report = useRef<HTMLTextAreaElement>(null);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(failure.report!);
      setCopied(true);
    } catch {
      report.current?.closest("details")?.setAttribute("open", "");
      report.current?.focus();
      report.current?.select();
      setCopied(document.execCommand("copy"));
    }
  };
  const dialog = useRef<HTMLDialogElement>(null);
  const confirm = useRef<HTMLButtonElement>(null);
  useLayoutEffect(() => {
    const element = dialog.current!;
    element.showModal();
    confirm.current?.focus();
    return () => element.close();
  }, []);
  const mismatch = failure.details.includes(
    "Open the matching detector image first.",
  );
  return (
    <dialog
      ref={dialog}
      className="operation-error-dialog"
      aria-labelledby="operation-error-title"
      aria-describedby="operation-error-message"
      onCancel={onClose}
    >
      <h2 id="operation-error-title">{failure.title}</h2>
      <p id="operation-error-message">
        {mismatch
          ? "This calibration’s detector does not match the current image."
          : failure.title === "An error occurred"
            ? "An operation could not be completed."
            : failure.title.includes("save")
              ? "The selected file could not be saved."
              : "The selected file could not be loaded."}
      </p>
      <p>
        {mismatch
          ? "Open the matching detector image, then load the calibration."
          : failure.title === "An error occurred"
            ? "The error report includes diagnostic details and your recent steps."
            : "Check the selected file. Details below explain the problem."}
      </p>
      <details>
        <summary>
          {failure.report ? "Error report and recent steps" : "Details"}
        </summary>
        {failure.report ? (
          <textarea
            ref={report}
            aria-label="Error report"
            readOnly
            value={failure.report}
            rows={12}
          />
        ) : (
          <p>{failure.details}</p>
        )}
      </details>
      {failure.report && (
        <p className="error-report-hint">
          Include this report when reporting the problem.
        </p>
      )}
      <footer>
        {failure.report && (
          <button type="button" onClick={() => void copy()}>
            {copied ? "Copied" : "Copy error report"}
          </button>
        )}
        <button
          ref={confirm}
          type="button"
          className="primary"
          autoFocus
          onClick={onClose}
        >
          OK
        </button>
      </footer>
    </dialog>
  );
}

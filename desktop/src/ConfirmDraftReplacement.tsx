import { Dialog, DialogHeader } from "./Dialog";

export function ConfirmDraftReplacement({
  action,
  onCancel,
  onContinue,
}: {
  action: string;
  onCancel: () => void;
  onContinue: () => void;
}) {
  return (
    <Dialog
      className="ui-error-dialog"
      aria-label="Replace unapplied edits?"
      onDismiss={onCancel}
    >
      <DialogHeader
        title="Replace unapplied edits?"
        closeLabel="Keep unapplied edits"
        onClose={onCancel}
      />
      <p>
        Loading new settings replaces the unapplied edits in this session.
        Cancel to keep them, or continue to choose the new source.
      </p>
      <div className="ui-dialog-actions">
        <button className="secondary" autoFocus onClick={onCancel}>
          Cancel
        </button>
        <button className="primary" onClick={onContinue}>
          {action}
        </button>
      </div>
    </Dialog>
  );
}

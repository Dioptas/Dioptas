import { Dialog, DialogHeader } from "./Dialog";

export function ConfirmDraftReplacement({
  action,
  drafts,
  onCancel,
  onContinue,
}: {
  action: string;
  drafts: string[];
  onCancel: () => void;
  onContinue: () => void;
}) {
  return (
    <Dialog
      className="ui-confirm-dialog"
      aria-label="Replace unapplied edits?"
      onDismiss={onCancel}
    >
      <DialogHeader
        title="Replace unapplied edits?"
        closeLabel="Keep unapplied edits"
        onClose={onCancel}
      />
      <p>
        Loading new settings replaces the unapplied {drafts.join(", ")} in this
        session. Cancel to keep these edits, or continue to choose the new
        source.
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

import { Dialog, DialogHeader } from "./Dialog";
import {
  isMacPlatform,
  shortcutGroups,
  shortcutKeyLabel,
} from "./shortcutKeys";

export function ShortcutReference() {
  const mac = isMacPlatform();
  return (
    <>
      <p className="shortcut-scope-note">
        Except for the Settings toggle, app shortcuts pause while editing text,
        using a menu or viewing Settings. Dialogs keep their own keys. A focused
        button keeps its normal Enter / Space action. Focus a plot with Tab to
        use its navigation keys.
      </p>
      {shortcutGroups.map(({ title, rows }) => (
        <section className="settings-card" key={title}>
          <h3>{title}</h3>
          {rows.map(([label, key]) => (
            <div className="settings-shortcut" key={label}>
              <span>{label}</span>
              <kbd>{shortcutKeyLabel(key, mac)}</kbd>
            </div>
          ))}
        </section>
      ))}
    </>
  );
}

export function ShortcutHelp({ onClose }: { onClose: () => void }) {
  return (
    <Dialog
      className="ui-shortcuts-dialog"
      aria-label="Keyboard shortcuts and gestures"
      onDismiss={onClose}
    >
      <DialogHeader
        title="Keyboard shortcuts & gestures"
        closeLabel="Close shortcut help"
        onClose={onClose}
      />
      <div className="ui-shortcuts-content" tabIndex={0}>
        <ShortcutReference />
        <section className="settings-card">
          <h3>Plot toolbar symbols</h3>
          {[
            ["bg", "Show or subtract background"],
            ["|", "Show phase reflection markers"],
            ["AA", "Antialias the pattern line"],
            ["A", "Automatically fit the plot range"],
            ["2θ / Q / d", "Scattering angle, momentum transfer, or d spacing"],
            ["Log / √", "Logarithmic or square-root intensity display"],
            [
              "ROI",
              "Show map pattern windows; image ROI restricts detector integration",
            ],
            ["↔", "Edit map pattern windows by dragging"],
          ].map(([symbol, meaning]) => (
            <div className="settings-shortcut" key={symbol}>
              <kbd>{symbol}</kbd>
              <span>{meaning}</span>
            </div>
          ))}
        </section>
      </div>
    </Dialog>
  );
}

import { Dialog, DialogHeader } from "./Dialog";

// Keep the scope visible: a focused plot, Mask, Settings, and text editing own
// different keys. The UI audit exercises these against real command handlers.
export const shortcutGroups = [
  {
    title: "Files & history",
    rows: [
      [
        "Open image(s) · uses the selected batch mode in Integration",
        "⌘ / Ctrl + O",
      ],
      ["Save project · save mask file in Mask mode", "⌘ / Ctrl + S"],
      ["Undo the latest scientific edit · shared across modes", "⌘ / Ctrl + Z"],
      ["Redo the latest scientific edit", "⌘ / Ctrl + Shift + Z · Ctrl + Y"],
      ["Delete selected calibration peak groups", "Delete / Backspace"],
      [
        "Undo / redo custom actions · in Custom actions settings",
        "⌘ / Ctrl + Z / Shift + Z",
      ],
    ],
  },
  {
    title: "Workspace & mask tools",
    rows: [
      [
        "Enable picking / switch to Calibration · valid image setup; outside Mask mode",
        "P",
      ],
      ["Switch to Mask brush / eraser", "B / E"],
      ["Navigate · in Mask mode", "V"],
      [
        "Increase / decrease diameter · active point brush in Mask mode",
        "Q / W",
      ],
      ["Finish a mask polygon · outside text fields and buttons", "Enter"],
      ["Cancel the current mask polygon", "Esc"],
      ["Integrate a calibrated image · outside Mask mode", "Enter"],
      ["Restore detector view · when no plot has focus", "F"],
      ["Return from Settings · close the active dialog", "Esc"],
    ],
  },
  {
    title: "Focused image, cake & pattern",
    rows: [
      ["Focus a plot", "Tab"],
      ["Pan the view", "Arrow keys"],
      ["Zoom in / out around the view center", "+ / −"],
      ["Restore the fitted view", "F / Home"],
    ],
  },
  {
    title: "Batch overview",
    rows: [
      ["Select next / previous frame", "↑ / ↓"],
      ["Select first / last frame", "Home / End"],
      ["Restore the fitted overview", "F"],
    ],
  },
  {
    title: "Mouse & trackpad",
    rows: [
      ["Zoom under the pointer", "Scroll"],
      ["Zoom a selection", "Left drag"],
      ["Pan", "Right drag · Ctrl + left drag"],
      ["Zoom out one step", "Right click"],
      ["Restore the fitted view", "Right double-click"],
      ["Paint with the point brush · in Mask mode", "Shift + left drag"],
    ],
  },
] as const;

export function ShortcutReference() {
  return (
    <>
      <p className="shortcut-scope-note">
        App shortcuts pause while editing text, using a dialog or menu, or
        viewing Settings. A focused button keeps its normal Enter / Space
        action. Focus a plot with Tab to use its navigation keys.
      </p>
      {shortcutGroups.map(({ title, rows }) => (
        <section className="settings-card" key={title}>
          <h3>{title}</h3>
          {rows.map(([label, key]) => (
            <div className="settings-shortcut" key={label}>
              <span>{label}</span>
              <kbd>{key}</kbd>
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

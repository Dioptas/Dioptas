// Shortcut handlers accept both ⌘ and Ctrl; the reference shows only the keys
// of the platform the application runs on.

export function isMacPlatform(
  nav:
    { platform?: string; userAgent?: string } | undefined = typeof navigator ===
  "undefined"
    ? undefined
    : navigator,
): boolean {
  return /Mac|iPhone|iPad/.test(nav?.platform || nav?.userAgent || "");
}

// "Mod" is the primary modifier: ⌘ on macOS, Ctrl elsewhere.
// "Mac:" / "Other:" segments, separated by " · ", appear on one platform only.
export function shortcutKeyLabel(key: string, mac: boolean): string {
  return key
    .split(" · ")
    .flatMap((part) => {
      if (part.startsWith("Mac: ")) return mac ? [part.slice(5)] : [];
      if (part.startsWith("Other: ")) return mac ? [] : [part.slice(7)];
      return [part];
    })
    .map((part) => part.replace(/\bMod\b/g, mac ? "⌘" : "Ctrl"))
    .join(" · ");
}

// Keep the scope visible: a focused plot, Mask, Settings, and text editing own
// different keys. The UI audit exercises these against real command handlers.
export const shortcutGroups = [
  {
    title: "Files & history",
    rows: [
      [
        "Open image(s) · uses the selected batch mode in Integration",
        "Mod + O",
      ],
      ["Save project · save mask file in Mask mode", "Mod + S"],
      [
        "Previous / next image file · Calibration and Integration; uses File step in Integration",
        "Page Up / Page Down · Mac: Fn + ↑ / ↓",
      ],
      ["Undo the latest scientific edit · shared across modes", "Mod + Z"],
      ["Redo the latest scientific edit", "Mod + Shift + Z · Other: Ctrl + Y"],
      ["Delete selected calibration peak groups", "Delete / Backspace"],
      [
        "Undo / redo custom actions · in Custom actions settings",
        "Mod + Z / Shift + Z",
      ],
    ],
  },
  {
    title: "Workspace & mask tools",
    rows: [
      ["Open / close Settings · also while editing fields", "Mod + ,"],
      ["Enable / disable configurations", "Shift + C"],
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
      ["Inspect previous / next visible pattern sample", "Alt + ← / →"],
      ["Inspect first / last visible pattern sample", "Alt + Home / End"],
    ],
  },
  {
    title: "Focused pane dividers",
    rows: [
      ["Resize the adjacent panes", "Arrow keys"],
      ["Resize in larger steps", "Shift + Arrow keys"],
      ["Restore the default split", "Home · double-click"],
      ["Expand to the allowed maximum", "End"],
    ],
  },
  {
    title: "Focused pattern & phase legends",
    rows: [
      ["Move the legend inside the plot", "Arrow keys"],
      ["Move the legend faster", "Shift + Arrow keys"],
      ["Restore the legend position", "Home / Esc"],
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

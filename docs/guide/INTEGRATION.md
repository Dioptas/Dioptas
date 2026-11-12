# Integration workflow

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

New sessions trim contiguous leading and trailing exact-zero bins from 1D
integrated patterns by default, including combined-detector patterns and their
exports. **Settings → Integration → Trim leading and trailing zeros** can retain
the full radial grid; saved project choices are honored. Radial coordinates,
counting errors and azimuthal std are sliced together. Internal zeros, negative
intensities and entirely zero patterns are retained. Cakes and the shared stored
Batch/Map grids keep their full binning.

At wider widths Integration follows Qt's pane arrangement: a full-height image/cake
on the left, with tabbed controls above the integrated pattern on the right.
Below 1160 px of workspace width, the controls span above both plots. A docked
Batch then shares the left plot area with Image through an Image/Batch switch;
wider windows retain the image and Batch stack. Switching or resizing keeps
renderers mounted and preserves plot zoom. Drag either divider to resize the
panes; Image/Cake switches the detector display and preserves its independent
intensity controls.

The task tabs also follow Qt's responsive grouping, based on the task panel's own
width: one group below 900 px, primary file/processing controls on the left and
Overlay/Phase on the right at 900–1400 px, and separate Overlay and Phase columns
above 1400 px. Larger text increases these thresholds proportionally. This keeps
image or pattern browsing available beside phase pressure/temperature controls.
Selections are independent across groups; switching a primary tab, resizing or
collapsing retains the selected references and pending field drafts.

The Phase table wraps full phase names and labels P/P₀ and T units in its column
headers. The normal Phase layout retains Qt's left action rail and right-side
compact P/T step fields and apply-to-all. Step fields are 64 px wide and use
the table field height, as does the selected-phase reference chooser. Save/Load
List are compact document-arrow icon buttons beside the step controls. The left
action rail contains phase loading, database, edit and row deletion, then Clear All
between separators and phase up/down arrows at the bottom. Clear All uses the
Overlay list-clear icon and asks for confirmation with Cancel focused. Phase moves
retain the selected phase by identity and participate in Undo/Redo; projects, phase
lists, plot references and newly opened figure exports follow the resulting order.
Below 600 px of phase-panel width, only the step controls move above the table;
the action rail stays on the left. New phases use Qt's generated color
sequence (starting with muted orange, green and teal), and swatches are centered
vertically with each row. Stored or manually selected colors are preserved.
Narrow phase tables show references for the selected phase below the table,
while wider tables retain a reference selector in each row. The native phase
commands and numeric editing behavior are unchanged. `npm run test:integration-responsive`
checks these layouts, real phase edits and Batch switching in headless Chromium
and WebKit.

The save icon at the far left of the lower
image toolbar saves the current Image/Cake view as PNG, scientific image/cake data
as TIFF, or cake data as TXT/CSV through the native file dialog. PNG preserves the
current view and colour settings and omits ROI/inspection markers, matching Qt's
2048-pixel export width. The Image, Pattern, Background, Corrections, Overlay and Phase groups connect to the existing local models. Native file
choosers cover pattern/background/phase files and output/input folders. See
[Integration parity and limitations](../parity/INTEGRATION_PARITY.md) for the implemented
controls, scientific qualifications, tests and shared contracts.

Overlay uses the same 64 px, table-height fields for Scale and Offset steps,
with padding around their borders. Below 600 px of Overlay-panel width, controls
wrap above the table and Waterfall uses a stacked-trace icon. Its 64 px manual
spacing field sits between Waterfall and Auto, without a text label in the
compact layout. Before actions would wrap, the spacing field hides to preserve
one row. If two rows become necessary, the complete waterfall/background group
moves together and the spacing field returns when it fits. The toolbar reserves
both rows above the table, keeping every control visible and clickable. Separators
distinguish steps, waterfall controls and the background action. Overlay and the pattern
toolbar share the same background icon, showing a diffraction peak above a red
baseline. Auto estimates 10% of each pattern's mean finite intensity above its
minimum, applies the absolute overlay scale, then averages equally across
nonflat patterns and rounds up to a 1/2/5 step. This replaces the previous largest
peak-to-peak range estimate, reducing the influence of narrow high peaks. Existing
offsets are ignored; empty/flat data retain the default fallback. The same Auto
estimate is used when creating Batch waterfall overlays. Headless Integration
responsive checks cover both layouts and text
sizes, actual scale/offset edits, and horizontal overflow in Chromium and WebKit. `node scripts/overlay_responsive_sweep.mjs` additionally sweeps 76 splitter widths per
text size and browser, checking spacing visibility, row transitions, overflow and
actual pointer hit targets above the table.

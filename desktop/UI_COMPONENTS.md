# Desktop UI components

All desktop modes and detached windows use `src/ui/index.tsx`. Their shared
appearance is defined in `src/ui/ui.css`. This includes the field, checkbox,
radio, button, dropdown, dialog, popup and tooltip palette. Scientific tables
use the existing `DataTable` components and the same field primitives.

Import controls from `./ui`:

```tsx
import { Button, Input, Select, Dialog, DialogHeader, Portal } from "./ui";

<Input type="number" aria-label="Distance" value={draft} onChange={edit} />
<Select aria-label="Scale" value={scale} onChange={changeScale}>
  <option value="linear">Linear</option>
  <option value="log">Logarithmic</option>
</Select>
<Button type="button" variant="primary" onClick={apply}>Apply</Button>
```

`Input`, `Select`, `TextArea` and `Button` retain their native DOM props, refs,
form semantics and events. `Input` covers text, search, numeric, checkbox,
radio, range and color inputs. `Button` provides default, primary, secondary
and quiet variants; specialized toolbar/tab/plot layouts remain supported.
The native select menu and keyboard behavior stay available, with a shared
field background and dropdown arrow across rendering engines.

Numeric editors such as `EditorNumber`, `ProcessingNumberField` and
`BackgroundNumberField` compose `Input`. Their draft, validation, asynchronous
commit and wheel behavior remain with the scientific workflow that owns them.
Do not replace those behaviors with an immediate `Number(value)` conversion.

## Dialogs and popups

```tsx
<Portal>
  <Dialog open aria-label="Display settings" onDismiss={close}>
    <DialogHeader title="Display settings" onClose={close} />
    {fields}
  </Dialog>
</Portal>
```

`Dialog` opens controlled dialogs in the native top layer and honors field or
button autofocus after opening. It handles Escape through `onDismiss` and
keeps native focus containment/restoration. `dismissOnBackdrop` opts into
outside-click dismissal; `backdrop="clear"` provides an undimmed anchored
dialog. Existing native `onCancel` handlers can prevent dismissal, including
for scientific draft cancellation. `open` can be omitted for persistent dialogs
whose existing DOM ref controls `showModal()` and `close()`.

`DialogPanel` uses the same surface for an independent editor window without
opening a second modal. `DialogHeader` owns heading and close-button styling.
`Popover` supplies the same surface for custom menus, listboxes and small
settings panels; callers retain anchor positioning and specialized selection
keyboard behavior. Use `Tooltip` for help bubbles.

Use `Portal` for floating content. It attaches to the active `.app`, falling
back to `document.body` in isolated components, so text size and theme variables
remain available. Do not call `createPortal` directly in individual views.

## Styling and verification

Change common colors, borders, corners and control states in `src/ui/ui.css`.
`src/ui/scrollbars.css` owns scrollbar appearance across all modes, dialogs and
detached windows. Scrollbars remain visible while overflowing content is idle
and occupy their own 12 px gutter rather than covering fields or text. Keep
component overflow rules in view CSS; do not add thin, hidden or fading scrollbar
overrides. Existing stable gutters remain available where content width should
also stay constant as overflow starts or stops.
View CSS can set dimensions, spacing, grid layout and toolbar/tab geometry.
Readonly transparency, invalid-field feedback and scientific color swatches
remain explicit semantic states. Do not add a private field or dialog palette
in a view stylesheet.

`npm test` includes an architecture check that rejects raw control/dialog JSX,
private portal implementations and hard-coded field/floating-surface colors
outside the shared components. `npm run test:ui-components` exercises the
components in headless Chromium and WebKit at both text sizes, including table
and detached-editor fields, popup inheritance, refs, form submission, nested
dialogs, Escape/backdrop dismissal, focus and scientific numeric editing.
It also checks idle vertical, horizontal and nested scrollbars, reserved gutter
space, and content that fits without overflow. Chromium is launched without its
headless-only `--hide-scrollbars` default for accurate layout and screenshots.
Screenshots and the result report are written to `artifacts/ui-components/`.
The existing calibration, mask, integration, phase, map, batch and custom-action
smoke suites cover the migrated workflows.

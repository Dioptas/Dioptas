# Custom actions

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

Use **Settings → Custom actions → Add action** to create a named sidebar
button for a local program or beamline script. Open the compact icon selector
to search 57 symbols, including plain and diagonal arrows. Choose an icon and
press **Save action** to apply it together with the other form edits.
Enter the executable (for
example, an absolute Python interpreter path), then one argument per line.
For Python scripts, the first argument is the script's full path. Paths with
spaces need no quotes. Save the action to add its button above Undo and Redo;
actions can be edited, hidden or deleted from the same settings page.
Each saved action has a trash button in its row for deletion without opening
the editor. Running actions cannot be deleted.
Drag saved actions by their grip handles, or use the up/down controls, to set
their order. A line shows the insertion point and the list scrolls when dragging
near its edges. Focused handles also accept Up/Down keys. Order is
saved as an interface preference and applies to both sidebar buttons and the
action menu. Up to three actions appear directly in the sidebar; additional
actions are available through **More actions**, a searchable list of all
enabled actions. Smaller windows reserve fewer sidebar slots to keep Undo,
Redo and Settings accessible. The menu opens on click and supports keyboard
navigation and Escape to close.
Use a short button name, such as Move or Lookup. The compact name field includes
a live preview at the sidebar's width; longer names are shortened to two lines
there and remain available in full in the menu and tooltip.
No startup configuration file needs to be prepared.

While **Custom actions** is open, the existing sidebar **Undo/Redo** buttons
restore action creation, saved edits (including names, icons and visibility),
deletion, and ordering. Cmd/Ctrl+Z and Cmd/Ctrl+Shift+Z (or Ctrl+Y) work here too;
text fields retain their normal text-editing undo. Save or cancel unfinished
form edits before undoing saved actions. Restored action definitions and order
are saved immediately. The last 100 changes are retained for the current window
session, including when Settings is closed and reopened. Returning to another
workspace restores its scientific history. Running a script does not add an
undo entry or rerun during history restoration.

For a motor-position lookup, arguments might be:

```text
/beamline/tools/lookup_motors.py
--image={image_path}
--frame={frame_index}
```

The input buttons insert placeholders; **Current input values** shows what
they will receive. Available inputs are:

| Placeholder             | Value                                                          |
| ----------------------- | -------------------------------------------------------------- |
| `{image_path}`          | Current detector file's full path                              |
| `{frame_index}`         | Current frame, starting at 0                                   |
| `{frame_number}`        | Current frame, starting at 1 (Qt's series position convention) |
| `{dataset}`             | Selected HDF5 image source, when present                       |
| `{calibration_path}`    | Loaded or last saved `.poni` path                              |
| `{project_path}`        | Current saved `.dio` project path                              |
| `{wavelength_angstrom}` | Current calibrated wavelength in Å                             |
| `{image_name}`          | Detector filename including extension                          |
| `{image_directory}`     | Folder containing the detector file                            |

A button is disabled when an input it needs is unavailable. Manually entered
geometry has no calibration path until saved. A loaded or previously saved
calibration file contains that saved geometry; save subsequent edits before
passing it to another tool. Actions receive the current context when clicked.
They are explicit actions and are never triggered by image loading or project
loading. Each argument is passed directly, without shell evaluation. Shell
scripts can be run using their executable path or a shell executable with the
script path as its first argument.

Actions run in the background without occupying the scientific worker.
Settings shows their running/completed status, exit code and the last 16 KiB
of combined output. A running action cannot be launched again or deleted.
External programs may continue running after Dioptas closes.

Settings are stored automatically in
`~/.Dioptas/desktop-custom-commands.json`, separately from scientific projects
and Qt's startup action configuration. `DIOPTAS_CUSTOM_COMMANDS_FILE` overrides
this location for isolated testing. **Save action** applies the icon and the
remaining form edits. `npm run test:native-custom-actions` exercises the
headless workflow against Rust using temporary settings and a disposable
script; it does not touch user actions.

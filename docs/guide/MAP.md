# Map workspace

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

Map follows the Qt arrangement: scan map on the left, detector and task tabs
at upper right, and a wide pattern beneath them. When the analysis area is
narrow, the detector moves into an Image tab. Drag the dividers to adjust the
panels; double-click a divider to restore its default proportions.

Use **Detach map** (the outward-arrow button below the scan) to move just
the scan map into an independent window and return the main window to
Integration. Move that window to a second screen and click cells to update the
main detector, cake and pattern. The window keeps its layer selector, histogram,
Smooth/Contours and data/PNG exports. Map mode remains available in the main
window for Points, Layers and Grid. **Show map** brings the existing window
forward; the **Dock map** icon returns it to Map mode. Closing the separate window also
docks the panel, without changing the main mode or discarding the scan.
Palette, contrast for unchanged map pixels, smoothing and contours survive
docking. The native map window remembers its size, position and monitor across
docking and app restarts. If the display is rearranged or its scaling changes,
placement follows the saved monitor; if it is disconnected, the window opens
within the current display's usable area. Maximizing/minimizing preserves its
last normal bounds. Plot zoom is not restored after reopening.
While detached, Map mode retains the original left map column as a quiet
placeholder with Show/Dock icons; the detector, controls and pattern keep their
positions. There is no separate workspace header or in-window expansion button.
Selections and layer edits use the main command queue and the same Rust
session; the child reads scan pixels through binary IPC. In Integration, a raw
point is calculated with current settings to populate all integration plots;
stored and normalized map profiles are retained. A missing raw image still
allows inspection of the stored profile. The browser test preview uses a popup
with the same shared panel and ordered commands.

Load calibrated images, a scan folder or a saved project. Load, Folder and
Live/Follow are grouped in Points; calibration and full-map reintegration use
compact icon buttons with tooltips. Grid dimensions apply on Enter or blur.
Points, Layers and Grid show scrollbars as soon as content overflows. Points
keeps its action buttons in one row above the file list; only the list scrolls
when the pattern is enlarged. Point indices and filenames use separate aligned
columns.
Points contains the scan arrangement with drag/keyboard reordering, blanks,
filename-numbering checks and exclude/include. Selected raw images are
reintegrated automatically with current settings when possible; stored-only and
normalized patterns remain available. The Points gear opens Map settings with
an option to reintegrate selected images (on by default) and normalization in a
compact popup beside the gear. Click outside or press Escape to close it.
Normalize using a physical 2θ/Q/d range or an existing pattern window, choose a
reference file, and apply or restore the originals. Reference choices show the
same 1-based row number and filename as Points, including after reordering;
blank cells cannot be references. A window supplies its current
bounds when Normalize is pressed. Layers contains editable
window and expression tables. Window colors link the table and pattern; edits
apply on blur or Enter, keeping Tab navigation within the table. Its numeric ranges
follow the displayed 2θ/Q/d unit. Pattern windows can be dragged, resized,
selected or recentered by clicking. Turn Edit off to zoom inside them. Pattern
2θ/Q/d display and Log/√ scaling do not change stored map data. Each raster keeps its own histogram.
Map's pattern plot shows the visible overlays and phase reflections shared with
Integration, including colors, phase pressure/temperature, overlay scale/offset
and measured-pattern visibility. Manage those references in Integration; Map
retains its Points/Layers/Grid controls. Changing Map's 2θ/Q/d display converts
references along with the measured curve without changing the stored profiles.
Clicking Map's detector or pattern marks the same calibrated position with a
green detector ring/crosshair and pattern line. Integration uses the same
position, including after switching modes or detaching/docking the scan window.
Selecting another scan point keeps both the green position and the Click readout.
The line follows the active 2θ/Q/d display unit. Stationary pattern clicks also
inspect inside editable ROIs; ROI drags continue to edit only the window. The
shared footer reports the clicked 2θ, Q, d and azimuth when available.

Live watches the loaded scan folder for completed numbered continuation files.
Follow selects the latest point; turn it off to retain the selected image.
The reintegration icon applies changed integration settings to the full map.
Save map data writes text/TIFF, PNG saves the map viewport, and Save project
retains the scientific map, windows, colors and layout. See [Map parity](../parity/MAP_PARITY.md) for
validation and remaining limitations, including detached windows and growing
HDF5 datasets.

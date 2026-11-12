# Batch image series

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

Integration → Image offers Qt's Integrate, Add, Average and Save choices for
multiple images. Integrate opens a separate Batch window following Qt's Files/2D
dialog layout. Selecting a frame updates
Integration's detector, cake and stored pattern. Use **Dock batch** to place the
series below the image in the lower-left corner; its divider resizes the dock,
and the header can collapse it or detach it again. The compact **Batch…** button
beside **File Info** in the Image tab reopens the window or dock without discarding
data, and is orange while Batch is open. The dock's settings icon opens **Options**, which holds
normalization and range settings so the series keeps most of the space. Its
histogram defaults to vertical on the left, mirrored toward the plot.
Hover uses separate Frame, intensity and radial fields in the shared footer.
Clicking selects both a frame and the linked green radial marker. The Phases
toggle shows shared phase references with the cake view's colors and line strengths.
The floating window has pattern-style unit/scale buttons at the far right; the
dock follows the main pattern’s controls. The dock shows frame position in the header instead
of a bottom browsing slider; click rows or use the overview’s keyboard arrows.
Selecting a frame keeps controls active without a global loading flash.
Detaching the detector lets docked Batch fill the freed image column. Detaching
Batch as well leaves just the full-width task tabs and pattern. Docking the image
restores Batch's saved height and collapsed state.
Both Integration splitters and Batch’s height, collapsed, open and docked states
are remembered across restarts. Smaller windows clamp the visible layout without
erasing your preferred sizes. Closing Batch keeps it closed on restart; quitting
with Batch open restores it. Scientific data is restored by loading a project. Controls include frame range/step,
normalization, HDF5/CSV saving and processed-batch import. Save project retains the series.
See [Batch parity](../parity/BATCH_PARITY.md) for workflow, checks and scope.

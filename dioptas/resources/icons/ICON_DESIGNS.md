# Dioptas icon design references

The unversioned `icon.*` files are the production application icon. They are
used directly by Qt, PyInstaller, the Windows installer, and the conda
installer.

- `icon.svg`, `icon.png`, `icon.ico`, `icon.icns`: current production icon — a
  modernized version of the familiar D in the Dioptas graphite/orange palette.
- `icon-legacy.*`: the previous green, beveled D icon, preserved unchanged for
  historical reference.
- `icon-v2.svg` and `icon-v2.png`: early green D plus diffraction-arcs concept.
- `icon-v3.svg` and `icon-v3.png`: graphite/orange concentric-arcs concept,
  emphasizing diffraction more strongly than the letterform.
- `icon-v4.svg` and `icon-v4.png`: final modernized-D design source and preview;
  currently identical to the production SVG and PNG.

When the production design changes, regenerate all four unversioned formats
together so Windows, macOS, Linux, and installer artwork remain consistent.

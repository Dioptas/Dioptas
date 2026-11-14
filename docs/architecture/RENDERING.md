# Display products and rendering

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

## Requested display products

The Rust UI requests only the display products it uses. Image browsing, Batch
selection and Map selection do not calculate a hidden cake. Switching to Cake,
opening calibration Validation or explicitly exporting cake data calculates it
on demand through the same native cake kernel. Showing it again reuses the
current result; changing the frame, mask or integration settings invalidates it.
Requesting a cake does not replace a stored/normalized pattern or add history.
Calibration ring contours are requested only while their calibration overlay is
visible. Phase guides and linked inspection contours remain independent.
The common request policy applies to file opens, arrows, settings, Batch, Map,
configuration changes and project loading. Legacy/reference calls without a
product request retain their complete response for compatibility.

## WebGL pattern benchmark

The renderer comparison is described in
[docs/performance/PATTERN_WEBGL_BENCHMARK.md](../performance/PATTERN_WEBGL_BENCHMARK.md). It covers ordinary and
large-pattern navigation, CPU drawing cost, frame cadence, upload behavior and
curve geometry. WebGL is the default; `VITE_DIOPTAS_PATTERN_RENDERER=canvas2d`
selects the Canvas renderer for diagnostics and comparisons. The headless
`npm run benchmark:pattern` now also defaults to WebGL; pass `-- --canvas2d`
for an explicit fallback benchmark. Headless GPU timing is not a native GPU benchmark.

## Image and pattern rendering

New detector sources are published together with their source-precision Auto
limits, across Calibration, Mask, Integration (corrected/raw) and Map. The
command queue stays reserved through the source-precision intensity calculation. This
avoids first showing new pixels with the previous file's or temporary default
limits. Contrast and view resets happen before drawing; canvas layers update
before the browser paints. Each display retains its own Auto preferences.
`npm run test:detector-redraw -- --webkit` counts real draw/upload calls and
checks delayed Auto responses; add `--canvas` to check the software fallback.

Raster surfaces measure their mounted container and initialize the renderer
before the first browser paint. No image is drawn at a provisional size, and
retained surfaces remeasure before painting a mode/layout change. This applies
to every `RasterView`, including detector, cake, Map and detached views.
`npm run test:raster-first-frame` checks the first painted frames in Chromium
and WebKit with GPU/software rendering, Retina scaling, remounts, retained
layout changes and hidden-to-visible transitions.

Detector and cake images use WebGL 2 (`src/WebGLRaster.ts`). Each mounted view
retains one full-resolution R32F intensity texture, an R8 mask and the selected
colour lookup table. Intensity limits, linear/log mapping and mask transparency
are shader uniforms; navigation changes the image projection. These operations
do not re-upload unchanged source pixels or run a JavaScript colour loop.
Nearest-neighbour sampling preserves individual detector pixels and the existing
bottom-origin projection. Calibration guides, masks under construction, ROI
handles, selections and cake axes remain on a transparent Canvas 2D layer above
the image, using the same projection and clip.

WebGL support is optional: unavailable contexts, texture dimensions beyond the
GPU limit and upload failures use the existing Canvas renderer. Context loss
switches to Canvas; restoration rebuilds the textures. Unmounting releases GPU
resources. PNG export deliberately uses the software colour renderer, retaining
its existing 2048-pixel width, current view and annotations without reading back
the GPU. Display rendering does not change scientific arrays, integration,
calibration or original-pixel readouts.

Batch's 3D view uses a filled GPU surface with antialiased intensity contours
by default. Zooming, rotation and panning retain the selected mesh resolution.
Wheel zoom and right-click zoom-out keep the surface point under the cursor fixed, including after
rotation, panning and axis-proportion changes.
The mesh and phase geometry stay in GPU buffers while navigation updates the
camera projection; data, intensity mapping or sampling changes rebuild the
geometry. Palette changes update only the color texture. Axes use the same
projection, and picking projects the mesh only when needed. See
[navigation timings and verification](../performance/SURFACE_NAVIGATION_PERFORMANCE.md).
Surface settings switch contours off or choose phase guides as surface lines
or translucent reference planes. The existing icon-only Phases
toggle controls visibility in both 2D and 3D. References reuse native phase
d spacings and colors, converting with the acquired series wavelength; their
positions follow the current phase model rather than per-frame pressure or
temperature. Plane heights use the same relative reflection intensities as the
pattern view, normalized independently for each visible phase. Their top edges
follow each frame's visible measured maximum, capped by the intensity limits;
these maxima include every source column in range regardless of mesh detail.
Curves intersect the displayed triangles exactly, and the GPU
depth buffer hides references behind opaque peaks. Contour levels use rounded
physical intensities with the same linear/log/square-root transfer as the axes.
Their subtle darkening preserves the surface hue without switching to a
contrasting light or dark line color.
Both preferences persist and PNG capture includes the guides. On GPU failure,
Canvas draws contours and surface phase lines; settings identify the plane
fallback. This changes display geometry only, retaining the native arrays.
`npm run test:batch-surface-guides` checks both browser engines, actual pixels,
depth occlusion, transparent compositing, preference persistence, and unchanged
source bytes; `test:batch-surface` also exercises the native phase toggle.

Pattern curves use WebGL 2 (`src/WebGLPattern.ts`) by default, while axes,
reference lines, editable ranges and the cursor use layered Canvas 2D surfaces
(`src/PatternView.tsx`). GPU buffers retain the curve coordinates and change only
when source arrays or intensity scaling change. High/low coordinate pairs retain
precision when zooming around large offsets. Unsupported or lost contexts and
upload failures use the cached Canvas renderer; turning antialiasing off keeps
the established Canvas pixel-line appearance. Context restoration rebuilds GPU
resources. Data extents and application overlay props are memoized. For monotonic
ascending or descending coordinates, binary search finds visible samples
(including boundary neighbours) and the nearest readout sample. Unordered
coordinates retain the general path; displayed samples inside the view are not
decimated, and gaps remain gaps. `npm run test:pattern-quality` checks curve
geometry, default rendering, fallback and context recovery.

Run `npm run test:rendering` and `npm run test:rendering -- --webkit` for shader
pixel comparisons, texture reuse, square pixels, context recovery, unsupported
GPU/texture-limit fallback, export and 100,000-point pattern navigation checks.
The test serves an isolated component fixture on an automatically assigned port,
without using the primary preview's port 1420. Add `--baseline=44504cc2` to compare
the pattern against the pre-change component from that commit. Reports and
screenshots are written to `artifacts/`.

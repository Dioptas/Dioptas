# Batch 3D navigation

Zoom, rotation, panning and axis proportions reuse a resident normalized
frame/radial/intensity mesh. A camera matrix uses the exact fitted-box projection
of the axes. No triangle construction, full-mesh vertex projection or surface vertex/index
upload occurs during navigation. Phase curves and plane geometry also remain
resident. Their screen widths are calculated in the shader; translucent plane
ordering updates a small guide index buffer when the camera direction changes.

Native data, the sampled region/resolution, intensity limits or linear/log/sqrt
mapping invalidate geometry. Phase changes invalidate guides. Palette changes
update the color texture. CPU projection is deferred until a pick is requested;
the Canvas compatibility fallback projects and draws the complete selected mesh.
Axes, selection and linked markers retain Canvas drawing, and PNG captures
include the composited GPU image. Unmount/context-loss cleanup remains explicit.

## Measured zoom redraws

Measured headlessly on November 10, 2026, before and after this change. Both runs
used the same 64 × 2,048 narrow-peak fixture, Very high resolution (131,072
vertices), an 1,100 × 750 viewport, contours, and eight wheel events at −45.
The reported median is the upper middle sample of eight. Times cover the
renderer through Canvas compositing; they are not physical display latency or
a frame-rate measurement. Initial mesh construction is excluded.

| Engine | Before (ms) | Resident mesh (ms) | Surface buffer uploads during eight zooms |
| --- | ---: | ---: | --- |
| Chromium | 115.8 | 87 | 16 → 0 |
| WebKit | 25 | 3 | 16 → 0 |

The improvement varies with the engine's graphics path. These are headless
browser measurements, not a native Tauri/monitor scanout qualification.

Reproduce the current measurement from `desktop/`:

```sh
node scripts/batch_surface_navigation_benchmark.mjs
```

An optional output filename saves the raw samples as JSON. The original before
samples were Chromium `[139.3,117.3,114.6,115.8,108.8,112.8,122.9,108.8]` and
WebKit `[25,24,21,26,32,24,24,25]`; after samples were Chromium
`[92.3,87.9,87.3,86,87,83.8,83.2,83.3]` and WebKit `[4,3,3,3,3,2,1,1]`.

## Verification

- `npm test`: projection matrices match physical axes across camera angles,
  zoom, pan and unequal axis proportions; phase scaling and existing checks.
- `npm run test:batch-surface-gpu`: selected resolution and mesh upload count
  stay constant through zoom, rotation and pan; stopping zoom preserves exact
  pixels. Histogram limits/scales rebuild geometry; palette changes reuse it.
  Source bytes, narrow peaks, picking, captures, resource cleanup and context
  loss/fallback remain covered in Chromium and WebKit.
- `npm run test:batch-surface-guides`: phase colors, depth occlusion, transparency,
  relative-intensity planes and PNGs in both engines.
- `npm run test:batch-surface` and `test:batch-surface-axes`: native Batch selection,
  gestures, ranges, units, docking, captures and 80 axis layouts per engine.

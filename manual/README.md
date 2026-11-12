# Dioptas user manual

An Astro Starlight documentation site for the Dioptas desktop application. It is written for people who use Dioptas at a beamline or in the lab. Developer documentation stays in `DEVELOPMENT.md` and `docs/`; the older Sphinx pages in `docs/source/` are unchanged.

## Develop

Use Node.js **22.23.4 or newer** (Astro's requirement, which is newer than the application itself needs). The application and the manual keep separate npm dependencies and lockfiles. From the repository root:

```sh
npm ci --prefix manual
npm run dev:manual
```

Open `http://127.0.0.1:4321/Dioptas/manual/` (or the port Astro prints). The manual dev server never uses the application's port 1420.

## Write

Pages live in `src/content/docs/`. Start each Markdown page with a `title` and `description` in YAML frontmatter, then begin its headings at `##`. The sidebar order is explicit in `astro.config.mjs`.

- Explain one user task per page and use the application's exact visible labels, in bold.
- Describe only behaviour you have confirmed in the running interface or in the code. Where a document under `docs/` and the application disagree, the application is right.
- Say what a control is for before listing its options. Keep internal names, command names and file paths of the source out of the text.
- Identify example data in captions: the CeO₂ calibrant image, the nine-image Fe₃O₄ scan, the synthetic rotation scan. Say so when a screenshot only illustrates controls and its data do not belong together.
- Author internal links as `/Dioptas/manual/…`. They are rebased at build time when `DIOPTAS_MANUAL_BASE` sets another path.
- Inline math uses `$…$` and display equations `$$…$$`; KaTeX renders at build time.

## Screenshots

Screenshots are in `src/assets/screenshots/` and are referenced with relative Markdown image paths and descriptive alt text. Click a screenshot in the built site to enlarge it.

Every image is produced by `scripts/capture-manual-screenshots.mjs`, which drives the real interface in headless Chromium against the native Rust processor. Nothing is composited or retouched. Refresh them from the repository root:

```sh
npm ci
cargo build --locked --manifest-path backend/Cargo.toml --bin dioptas-processor
npm run capture:manual
```

- `--section start,calibration,mask,integration,batch,map,scxrd,configurations,settings` captures a subset.
- `--out <folder>` writes somewhere else, for a trial run.
- `DIOPTAS_NATIVE_PROCESSOR` selects another processor executable.
- The Single Crystal XRD section needs the synthetic rotation scan. Generate it once with
  `cargo run --locked --manifest-path backend/Cargo.toml --example scxrd_fixture -- artifacts/scxrd-fixture`.
  Without it the section is skipped with a message.

The script serves the interface with Vite on an ephemeral port, opens no window, and gives the processor a temporary home directory, so your own settings and custom actions are not read or changed. It copies the example data from `tests/data/` to `/tmp/dioptas-manual` first (override with `DIOPTAS_MANUAL_DATA_DIR`) so that no personal folder name appears in a published image, and removes that folder afterwards.

`src/assets/screenshots/capture-record.json` records, for each image, the source commit, viewport, footer status at capture time, a description and the file hash. Refresh a screenshot when the interface it shows changes, and reread the page that uses it: captions quote values from the images.

Dioptas has one dark appearance, so there is one capture per screenshot and it is used in both manual themes. This differs from manuals of applications with a light and a dark theme.

The capture steps assert that no page error and no footer error is present before each image. A step that fails therefore points at a real change in the interface; set `MANUAL_DEBUG=1` to print the page's accessibility tree at the failure.

## Build and check

```sh
npm run build:manual
```

This builds static pages into `manual/dist/`, creates the local search index, and checks generated links, assets and anchors within the manual. External links are outside the check. Building the manual needs neither Rust nor the application build.

To preview the built site:

```sh
npm --prefix manual run preview
```

## Publishing

The site is built for `https://dioptas.github.io/Dioptas/manual/` by default. Nothing deploys it yet. Set `DIOPTAS_MANUAL_SITE`, `DIOPTAS_MANUAL_BASE` and `DIOPTAS_MANUAL_REF` (the branch used for the "Edit page" and source links) to build for another location. Generated output, Astro caches and `node_modules/` are ignored by `manual/.gitignore`.

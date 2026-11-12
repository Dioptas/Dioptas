# Native dependency security

The Linux Tauri/Wry stack currently resolves GTK 0.18 and GLib 0.18.5. A direct
GLib update cannot satisfy this stack's version requirements. The coordinated
[GTK 0.19 migration](https://github.com/tauri-apps/tauri/pull/16170) is upstream
work; adopting it will require qualifying the complete host dependency graph.

## GLib iterator backport

`src-tauri/Cargo.toml` patches `glib` to `vendor/glib`, preserving the published
0.18.5 crate with the exact [upstream iterator fix](https://github.com/gtk-rs/gtk-rs-core/pull/1343).
Only the two pointer-mutability lines in `src/variant_iter.rs` differ from the
published source. The authentic version, normalized registry dependencies,
licenses and complete original file inventory are retained. No unrelated
dependency versions change. This dependency belongs to the Linux GUI host; the
scientific processor and React interface retain their existing implementation.

`scripts/check_glib_backport.mjs` verifies the source tree against the independently
verified published-archive inventory, reverses only the reviewed patch for that
comparison, and requires the host manifest/lockfile to resolve this local source.
The offline guard runs before normal tests, builds and native gates. Git preserves
the verified vendored bytes across line-ending configurations.

An advisory scanner may omit non-registry packages. Therefore scanner silence is
not the regression test, and the original registry version remains monitored.
The dedicated Linux CI job queries OSV for registry `glib` 0.18.5, permits only
the source-verified RUSTSEC-2024-0429 / GHSA-wrw7-89jp-8q8g backport, and fails on
any additional advisory or alias. Network failures, malformed responses and
unbounded pagination fail the check. There is no blanket advisory ignore.

The same job checks the actual Linux Tauri dependency graph without opening an
application window and runs the [optimized regression package](../../security/glib-regression/README.md).
Its seven cases exercise the affected safe iterator APIs; an isolated unpatched
negative control reproduces SIGSEGV, while the patched source passes. Ordinary
debug tests alone do not expose the optimizer-dependent bug.

Run the provenance and live-advisory checks from the repository root:

```sh
node scripts/check_glib_backport.mjs
npm run test:glib-backport
```

The optimized tests require GLib/GObject development libraries visible through
`pkg-config`. No display server or Python environment is required.

Remove the temporary backport when a released Tauri/Wry dependency chain selects
a fixed GLib release. At that point remove the vendored crate, patch and dedicated
regression/guard together, restore normal registry resolution, and qualify the
new Linux host plus existing desktop gates. Do not change the recorded version
or fingerprints merely to satisfy a scanner.

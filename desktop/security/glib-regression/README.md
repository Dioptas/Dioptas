# GLib VariantStrIter backport regression

This small independent Cargo package checks the public safe iterator APIs affected
by RUSTSEC-2024-0429 / GHSA-wrw7-89jp-8q8g. It uses the same vendored `glib` crate
as the native desktop dependency patch, with its authentic version `0.18.5` and
the original normalized crates.io manifest. It does not compile Tauri or open a
window.

Run from `desktop/`:

```sh
cargo test --release --locked --manifest-path security/glib-regression/Cargo.toml
```

Optimizations are essential: the original immutable out-argument reference can
appear to work in debug builds. The regression refuses debug execution and
covers forward, backward, `nth`, `nth_back`, `last`, Unicode strings, mixed-end
iteration, empty/singleton exhaustion and references surviving their iterator.
GLib/GObject development libraries discoverable through `pkg-config` are required.
No GTK display is required.

`desktop/vendor/glib/SECURITY_BACKPORT.json` records the published archive checksum,
every original file checksum, original release commit, exact upstream fix and
backport commits, and the two source replacements. The normalized `Cargo.toml`
continues to resolve all sys/macro dependencies through the registry; no version
number was changed to influence a scanner. A clean audit result is not evidence
of this fix because RustSec's normal database scan skips non-registry sources.

For an independent negative control, copy this regression package and the
vendor crate into an isolated temporary directory, reverse exactly those two
source replacements in the temporary copy, and run the same optimized tests.
Never reverse the fix in the application checkout or Cargo registry cache. The
negative control must fail while the fixed source passes.

Local verification on November 11, 2026 used Rust 1.99.1, macOS arm64 and
GLib/GObject 2.90.1: all seven optimized tests passed. The isolated unpatched
control, whose reconstructed source hash matched the published original,
terminated with SIGSEGV (signal 11, Cargo exit 101). The fixed source passed again
after that control. This qualifies the upstream soundness fix independently of
whether a vulnerability scanner recognizes a non-registry backport; Linux host
qualification is a separate application CI check.


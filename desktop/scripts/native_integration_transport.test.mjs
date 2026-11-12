import { testFixture } from "./test_fixtures.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, utimes } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { nativeClient } from "./native_backend_client.mjs";
for (const [compression, scenario] of [
  ["gzip", "raw"],
  ["bitshuffle-lz4", "raw"],
  ["bitshuffle-lz4", "corrected"],
  ["bitshuffle-lz4", "dynamic"],
  ["bitshuffle-lz4", "combined"],
  ["bitshuffle-lz4", "spot"],
  ["bitshuffle-lz4", "cosmic"],
  ["bitshuffle-lz4", "pyfai"],
  ["bitshuffle-lz4", "pyfai-spread"],
])
  test(
    `${compression}/${scenario}: bulk cancellation and changed sources preserve the preceding complete series`,
    { timeout: 120000 },
    async () => {
      const directory = await mkdtemp(
        path.join(tmpdir(), "dioptas-rust-jobs-"),
      );
      const source = path.join(directory, "frames.h5");
      testFixture("series", source, compression);
      const native = nativeClient();
      const invoke = async (a, p = {}) => {
        const r = await native.invoke(a, p);
        assert.equal(r.ok, true, `${a}: ${r.error}`);
        return r;
      };
      try {
        await invoke("manual_geometry", {
          convention: "pyfai",
          values: {
            dist: 0.13,
            poni1: 0.0192,
            poni2: 0.0224,
            rot1: 0.008,
            rot2: -0.013,
            rot3: 0.02,
            pixel1: 0.0001,
            pixel2: 0.0001,
            wavelength: 0.5e-10,
            polarization_factor: 0.965,
          },
        });
        await invoke("integration_settings", { bins: 128, cake_bins: 24 });
        await invoke("open_image", { path: source, dataset: "frames" });
        if (scenario.startsWith("pyfai")) {
          await invoke("integration_settings", {
            method: "pyfai_full",
            poisson_errors: true,
            azimuthal_std: scenario === "pyfai-spread",
          });
        }
        if (["corrected", "combined"].includes(scenario)) {
          await invoke("integration_settings", { poisson_errors: true });
          await invoke("integration_image_background", {
            path: source + ".background.npy",
            scale: 0.7,
            poisson: true,
          });
          await invoke("integration_flat_field", {
            path: source + ".flat.npy",
          });
        }
        if (["dynamic", "combined"].includes(scenario)) {
          await invoke("mask_plugin", {
            name: "Threshold Mask",
            enabled: true,
            settings: { above_enabled: true, above_value: 900 },
          });
        }
        if (["spot", "cosmic"].includes(scenario)) {
          await invoke("mask_plugin", {
            name: scenario === "spot" ? "Spot Mask" : "Cosmic Ray Mask",
            enabled: true,
          });
        }
        await invoke("batch_load", { paths: [source], start: 1, stop: 2 });
        if (compression === "bitshuffle-lz4") {
          const diagnostics = await invoke("integration_diagnostics");
          assert.equal(
            diagnostics.integrationDiagnostics[
              scenario === "raw"
                ? "patternOnlyDecodes"
                : "processedFrameIntegrations"
            ],
            2,
          );
        }
        const before = await invoke("state");
        const underway = async () => {
          for (let attempt = 0; attempt < 100; attempt++) {
            const r = await invoke("progress");
            if (
              r.progress.label === "Integrating series" &&
              r.progress.current >= 2 &&
              r.progress.current < r.progress.total
            )
              return;
            await new Promise((r) => setTimeout(r, 5));
          }
          throw Error("Bulk progress did not expose an intermediate frame");
        };
        let job = native.invoke("batch_load", { paths: [source] });
        await underway();
        await invoke("cancel_refinement");
        let result = await job;
        assert.equal(result.ok, true);
        assert.equal(result.cancelled, true);
        assert.deepEqual(await invoke("state"), before);
        if (compression === "bitshuffle-lz4") {
          const mapJob = native.invoke("map_load", { paths: [source] });
          let preview;
          for (let attempt = 0; attempt < 100; attempt++) {
            preview = (await invoke("progress")).progress.mapPreview;
            if (
              preview &&
              preview.completed > 0 &&
              preview.completed < preview.total
            )
              break;
            await new Promise((resolve) => setTimeout(resolve, 2));
          }
          assert.ok(preview && preview.completed < preview.total);
          await invoke("cancel_refinement");
          assert.equal((await mapJob).cancelled, true);
          assert.deepEqual(await invoke("state"), before);
          assert.equal(
            (await invoke("progress")).progress.mapPreview,
            undefined,
          );
        }
        job = native.invoke("batch_load", { paths: [source] });
        await underway();
        const time = new Date(Date.now() + 2000);
        await utimes(source, time, time);
        result = await job;
        assert.equal(result.ok, false);
        assert.match(result.error, /chang|mutat|snapshot/i);
        assert.deepEqual(await invoke("state"), before);
      } finally {
        await native.close();
        await rm(directory, { recursive: true, force: true });
      }
    },
  );

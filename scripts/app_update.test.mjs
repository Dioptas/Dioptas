import assert from "node:assert/strict";
import test from "node:test";
import {
  downloadFraction,
  errorMessage,
  noticeLabel,
  noticeVisible,
  notesPreview,
  progressLabel,
  statusAfterCheck,
} from "../src/appUpdateModel.ts";

const update = {
  version: "0.15.0",
  notes: "Faster maps.",
  published: 1794500000,
  downloaded: false,
};
const check = (found) => ({
  supported: true,
  currentVersion: "0.14.0",
  update: found,
});

test("a check announces an update without interrupting work in progress", () => {
  assert.deepEqual(statusAfterCheck(check(null), { phase: "idle" }), {
    phase: "idle",
  });
  assert.deepEqual(statusAfterCheck(check(update), { phase: "idle" }), {
    phase: "available",
    update,
  });
  // The host still holds a verified package from before the window reloaded.
  assert.equal(
    statusAfterCheck(check({ ...update, downloaded: true }), { phase: "idle" })
      .phase,
    "ready",
  );
  const downloading = { phase: "downloading", update, received: 5, total: 10 };
  assert.equal(statusAfterCheck(check(update), downloading), downloading);
  const installing = { phase: "installing", update };
  assert.equal(statusAfterCheck(check(update), installing), installing);
  // A newer announcement replaces a download of the superseded version.
  const newer = { ...update, version: "0.15.1" };
  assert.deepEqual(statusAfterCheck(check(newer), downloading), {
    phase: "available",
    update: newer,
  });
  assert.deepEqual(
    statusAfterCheck({ ...check(update), supported: false }, downloading),
    { phase: "idle" },
  );
});

test("a skipped version stays hidden until a newer one or an explicit download", () => {
  const available = { phase: "available", update };
  assert.equal(noticeVisible({ phase: "idle" }, null), false);
  assert.equal(noticeVisible(available, null), true);
  assert.equal(noticeVisible(available, "0.15.0"), false);
  assert.equal(noticeVisible(available, "0.14.9"), true);
  for (const phase of ["downloading", "ready", "installing", "error"])
    assert.equal(noticeVisible({ phase, update }, "0.15.0"), true);
});

test("labels describe each phase and download progress", () => {
  assert.equal(noticeLabel({ phase: "idle" }), "");
  assert.equal(
    noticeLabel({ phase: "available", update }),
    "Update available: Dioptas 0.15.0",
  );
  const half = {
    phase: "downloading",
    update,
    received: 24_000_000,
    total: 48_000_000,
  };
  assert.equal(downloadFraction(half), 0.5);
  assert.equal(noticeLabel(half), "Downloading Dioptas 0.15.0: 50%");
  assert.equal(progressLabel(half), "24.0 of 48.0 MB");
  const unknown = { ...half, total: null };
  assert.equal(downloadFraction(unknown), null);
  assert.equal(noticeLabel(unknown), "Downloading Dioptas 0.15.0");
  assert.equal(progressLabel(unknown), "24.0 MB");
  assert.equal(downloadFraction({ ...half, received: 60_000_000 }), 1);
  assert.equal(
    noticeLabel({ phase: "ready", update }),
    "Restart to update to Dioptas 0.15.0",
  );
  assert.match(
    noticeLabel({ phase: "error", update, message: "x", during: "install" }),
    /needs attention/,
  );
});

test("release notes stay plain text and bounded", () => {
  assert.equal(notesPreview(null), "");
  assert.equal(notesPreview("  One\r\nTwo  "), "One\nTwo");
  const long = `${"First paragraph. ".repeat(50)}\n${"Second. ".repeat(100)}`;
  const preview = notesPreview(long, 1000);
  assert(preview.length <= 1002);
  assert(preview.endsWith("\n…"));
  assert(preview.startsWith("First paragraph."));
  assert(!preview.includes("Second."));
  assert.equal(errorMessage("offline"), "offline");
  assert.equal(errorMessage(new Error("failed")), "failed");
  assert.match(errorMessage({}), /could not be completed/);
});

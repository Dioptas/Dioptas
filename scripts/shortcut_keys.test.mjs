import assert from "node:assert/strict";
import test from "node:test";
import {
  isMacPlatform,
  shortcutGroups,
  shortcutKeyLabel,
} from "../src/shortcutKeys.ts";

test("the primary modifier is ⌘ on macOS and Ctrl elsewhere", () => {
  assert.equal(shortcutKeyLabel("Mod + O", true), "⌘ + O");
  assert.equal(shortcutKeyLabel("Mod + O", false), "Ctrl + O");
  assert.equal(
    shortcutKeyLabel("Mod + Z / Shift + Z", false),
    "Ctrl + Z / Shift + Z",
  );
});

test("platform-only alternatives appear on their platform only", () => {
  const pageKeys = "Page Up / Page Down · Mac: Fn + ↑ / ↓";
  assert.equal(
    shortcutKeyLabel(pageKeys, true),
    "Page Up / Page Down · Fn + ↑ / ↓",
  );
  assert.equal(shortcutKeyLabel(pageKeys, false), "Page Up / Page Down");
  const redo = "Mod + Shift + Z · Other: Ctrl + Y";
  assert.equal(shortcutKeyLabel(redo, true), "⌘ + Shift + Z");
  assert.equal(shortcutKeyLabel(redo, false), "Ctrl + Shift + Z · Ctrl + Y");
  assert.equal(
    shortcutKeyLabel("Home · double-click", false),
    "Home · double-click",
  );
});

test("no reference label shows the other platform's keys", () => {
  for (const { rows } of shortcutGroups)
    for (const [, key] of rows) {
      assert.doesNotMatch(
        shortcutKeyLabel(key, false),
        /⌘|Mac:|Other:|\bMod\b|Fn \+/,
      );
      assert.doesNotMatch(shortcutKeyLabel(key, true), /Mac:|Other:|\bMod\b/);
    }
});

test("macOS is recognised from the platform or user agent", () => {
  assert.equal(isMacPlatform({ platform: "MacIntel" }), true);
  assert.equal(isMacPlatform({ platform: "Win32" }), false);
  assert.equal(isMacPlatform({ platform: "Linux x86_64" }), false);
  assert.equal(
    isMacPlatform({
      userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    }),
    true,
  );
  assert.equal(isMacPlatform({}), false);
});

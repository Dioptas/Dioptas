import assert from "node:assert/strict";
import test from "node:test";
import {
  canTraverseScientificHistory,
  scientificHistoryAction,
  scientificHistoryCommand,
} from "../src/historyLabels.ts";
test("native masks route both history directions to mask commands", () => {
  const state = {
    canUndoMask: true,
    canRedoMask: true,
    calibration: { canUndo: false, canRedo: false },
  };
  for (const redo of [false, true]) {
    assert.equal(canTraverseScientificHistory(state, redo, "mask"), true);
    assert.equal(
      canTraverseScientificHistory(state, redo, "integration"),
      false,
    );
    assert.equal(
      scientificHistoryCommand(
        scientificHistoryAction(state, "mask", redo),
        redo,
      ),
      redo ? "redo_mask" : "undo_mask",
    );
  }
});
test("native calibration and integration use their shared history independently of masks", () => {
  const state = {
    canUndoMask: false,
    canRedoMask: false,
    calibration: { canUndo: true, canRedo: true },
  };
  for (const mode of ["calibration", "integration", "map"])
    for (const redo of [false, true]) {
      assert.equal(canTraverseScientificHistory(state, redo, mode), true);
      assert.equal(
        scientificHistoryCommand(
          scientificHistoryAction(state, mode, redo),
          redo,
        ),
        redo ? "redo_calibration" : "undo_calibration",
      );
    }
});
test("explicit global history labels retain their command semantics across modes", () => {
  const state = {
    canUndoMask: true,
    canRedoMask: true,
    undoLabel: "pick_peak",
    redoLabel: "integration_overlay",
  };
  for (const mode of ["mask", "integration"]) {
    assert.equal(
      scientificHistoryCommand(scientificHistoryAction(state, mode)),
      "undo_calibration",
    );
    assert.equal(
      scientificHistoryCommand(
        scientificHistoryAction(state, mode, true),
        true,
      ),
      "redo_mask",
    );
  }
});

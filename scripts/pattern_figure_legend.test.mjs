import assert from "node:assert/strict";
import { test } from "node:test";
import { figureSegmentIntersectsBox } from "../src/patternFigureLegend.ts";
test("legend occupancy includes sparse crossing segments and excludes disjoint diagonals", () => {
  const box = { x: 10, y: 20, width: 20, height: 10 };
  for (const segment of [
    { x0: 0, y0: 25, x1: 40, y1: 25 },
    { x0: 40, y0: 25, x1: 0, y1: 25 },
    { x0: 20, y0: 0, x1: 20, y1: 40 },
    { x0: 20, y0: 25, x1: 20, y1: 25 },
    { x0: 0, y0: 10, x1: 10, y1: 20 },
  ])
    assert(figureSegmentIntersectsBox(segment, box));
  for (const segment of [
    { x0: 0, y0: 5, x1: 40, y1: 5 },
    { x0: 0, y0: 0, x1: 0, y1: 40 },
    { x0: 0, y0: 21, x1: 30, y1: 51 },
    { x0: 40, y0: 25, x1: 40, y1: 25 },
  ])
    assert(!figureSegmentIntersectsBox(segment, box));
});

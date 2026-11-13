import assert from "node:assert/strict";

export async function capturePhaseGuideStrokes(page) {
  await page.evaluate(() => {
    window.__phaseGuideStrokes = [];
    const stroke = CanvasRenderingContext2D.prototype.stroke;
    window.__restorePhaseGuideStroke = () => {
      CanvasRenderingContext2D.prototype.stroke = stroke;
    };
    CanvasRenderingContext2D.prototype.stroke = function (...args) {
      const view =
        this.canvas.dataset.testid === "phase-lines-layer"
          ? "detector-canvas"
          : this.canvas.dataset.testid;
      if (
        (view === "detector-canvas" || view === "cake-canvas") &&
        (this.canvas.dataset.testid === "phase-lines-layer" ||
          (Number(this.canvas.dataset.plotWidth) > 200 &&
            Number(this.canvas.dataset.plotHeight) > 100))
      )
        window.__phaseGuideStrokes.push({
          view,
          color: this.strokeStyle,
          width: this.lineWidth,
          opacity: this.globalAlpha,
        });
      return stroke.apply(this, args);
    };
  });
}

export async function verifyPhaseGuideStrokes(page, invoke) {
  const { phaseGuides } = await invoke("integration_phase_guides");
  assert.ok(new Set(phaseGuides.map((g) => g.lineWidth)).size > 1);
  const strokes = await page.evaluate(() => {
    window.__restorePhaseGuideStroke();
    return window.__phaseGuideStrokes;
  });
  for (const view of ["detector-canvas", "cake-canvas"]) {
    const rendered = strokes.filter(
      (s) => s.view === view && phaseGuides.some((g) => g.color === s.color),
    );
    assert.ok(
      new Set(rendered.map((s) => s.width)).size > 1,
      `${view}: strong and weak reflections have different widths`,
    );
    for (const stroke of rendered)
      assert.ok(
        phaseGuides.some(
          (g) =>
            g.color === stroke.color &&
            Math.abs(g.lineWidth - stroke.width) < 1e-6 &&
            Math.abs(g.opacity - stroke.opacity) < 1e-6,
        ),
        `${view}: phase stroke matches Qt intensity scaling`,
      );
  }
}

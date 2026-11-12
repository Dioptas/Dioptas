/** Read the actual GPU frame in browser regressions, before the compositor
 * discards its default framebuffer. This instrumentation is test-only. */
export function installRasterProbe() {
  const draw = WebGL2RenderingContext.prototype.drawArrays;
  WebGL2RenderingContext.prototype.drawArrays = function (...args) {
    const result = draw.apply(this, args);
    if (this.canvas.dataset.testid === "detector-gpu") {
      const program = this.getParameter(this.CURRENT_PROGRAM);
      const image = this.getUniform(
        program,
        this.getUniformLocation(program, "image"),
      );
      const overlay = this.canvas.nextElementSibling;
      window.__detectorDraw = {
        sx: Math.abs(image[2] / +overlay.dataset.fullWidth),
        sy: Math.abs(image[3] / +overlay.dataset.fullHeight),
        flippedY: true,
      };
      const pixels = new Uint8Array(this.canvas.width * this.canvas.height * 4);
      this.readPixels(
        0,
        0,
        this.canvas.width,
        this.canvas.height,
        this.RGBA,
        this.UNSIGNED_BYTE,
        pixels,
      );
      window.__detectorPixels = {
        pixels,
        width: this.canvas.width,
        height: this.canvas.height,
      };
    }
    return result;
  };
}

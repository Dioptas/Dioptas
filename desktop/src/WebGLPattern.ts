import { visibleSamples } from "./patternSamples";

export interface PatternCurve {
  x: number[];
  y: (number | null)[];
  color: string;
  width: number;
}
export interface PatternFrame {
  curves: PatternCurve[];
  scale: "linear" | "log" | "sqrt";
  view: { xMin: number; xMax: number; yMin: number; yMax: number };
  bounds: { left: number; top: number; width: number; height: number };
  size: { width: number; height: number; dpr: number };
}
interface CurveBuffer {
  x: number[];
  y: (number | null)[];
  scale: PatternFrame["scale"];
  buffer: WebGLBuffer;
  count: number;
}
const vertex = `#version 300 es
precision highp float;
layout(location=0) in vec4 startPoint;
layout(location=1) in vec4 endPoint;
uniform vec2 originHigh;
uniform vec2 originLow;
uniform vec2 projection;
uniform vec4 plot;
uniform vec2 viewport;
uniform float halfWidth;
uniform float feather;
out vec2 segmentPosition;
flat out float segmentLength;
vec2 position(vec4 p) {
  vec2 relative = (p.xz - originHigh) + (p.yw - originLow);
  return plot.xy + vec2(relative.x * projection.x, plot.w - relative.y * projection.y);
}
void main() {
  if(any(isnan(startPoint)) || any(isnan(endPoint))) {
    gl_Position=vec4(2.0,2.0,0.0,1.0);segmentPosition=vec2(0);segmentLength=0.0;return;
  }
  vec2 a=position(startPoint), b=position(endPoint);
  vec2 delta=b-a;
  float length=length(delta);
  if(length < 0.00001) {gl_Position=vec4(2.0,2.0,0.0,1.0);segmentPosition=vec2(0);segmentLength=0.0;return;}
  vec2 tangent=delta/length;
  vec2 normal=vec2(-tangent.y,tangent.x);
  int corners[6]=int[6](0,1,2,2,1,3);
  int corner=corners[gl_VertexID];
  float extent=halfWidth+feather;
  float along=(corner & 1)==0 ? -extent : length+extent;
  float side=(corner & 2)==0 ? -extent : extent;
  vec2 pixel=a + tangent*along + normal*side;
  gl_Position=vec4(pixel/viewport*vec2(2.0,-2.0)+vec2(-1.0,1.0),0.0,1.0);
  segmentPosition=vec2(along,side);segmentLength=length;
}`;
const fragment = `#version 300 es
precision highp float;
in vec2 segmentPosition;
flat in float segmentLength;
uniform vec4 color;
uniform float halfWidth;
uniform float feather;
out vec4 outColor;
void main() {
  float along=max(max(-segmentPosition.x,segmentPosition.x-segmentLength),0.0);
  float distance=length(vec2(along,segmentPosition.y));
  float coverage=1.0-smoothstep(halfWidth-feather,halfWidth+feather,distance);
  if(coverage<=0.0) discard;
  float alpha=coverage*color.a;
  outColor=vec4(color.rgb*alpha,alpha);
}`;
const colorCache = new Map<string, number[]>();
function rgba(css: string) {
  let value = colorCache.get(css);
  if (!value) {
    const context = document.createElement("canvas").getContext("2d")!;
    context.canvas.width = context.canvas.height = 1;
    context.fillStyle = css;
    context.fillRect(0, 0, 1, 1);
    value = Array.from(context.getImageData(0, 0, 1, 1).data, (v) => v / 255);
    if (colorCache.size >= 128) colorCache.clear();
    colorCache.set(css, value);
  }
  return value;
}

/** Display renderer: six generated vertices per instanced segment.
 * Source data stay in JS doubles. High/low coordinate pairs avoid cancellation
 * during deep zoom on large offsets. Buffers change only with data or y scale.
 */
export class WebGLPattern {
  private gl: WebGL2RenderingContext;
  private program: WebGLProgram;
  private uniforms = new Map<string, WebGLUniformLocation>();
  private buffers: CurveBuffer[] = [];
  private disposed = false;
  readonly stats = { uploads: 0, uploadBytes: 0, draws: 0, segments: 0 };
  constructor(private canvas: HTMLCanvasElement) {
    const gl = canvas.getContext("webgl2", {
      alpha: true,
      premultipliedAlpha: true,
      antialias: false,
      depth: false,
      stencil: false,
      preserveDrawingBuffer: false,
    });
    if (!gl) throw Error("WebGL 2 unavailable");
    this.gl = gl;
    const program = gl.createProgram();
    if (!program) throw Error("Cannot allocate curve program");
    this.program = program;
    try {
      for (const [type, code] of [
        [gl.VERTEX_SHADER, vertex],
        [gl.FRAGMENT_SHADER, fragment],
      ] as const) {
        const shader = gl.createShader(type);
        if (!shader) throw Error("Cannot allocate curve shader");
        gl.shaderSource(shader, code);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
          const error = gl.getShaderInfoLog(shader);
          gl.deleteShader(shader);
          throw Error(error ?? "Curve shader failed");
        }
        gl.attachShader(program, shader);
        gl.deleteShader(shader);
      }
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS))
        throw Error(gl.getProgramInfoLog(program) ?? "Curve program failed");
      gl.enableVertexAttribArray(0);
      gl.enableVertexAttribArray(1);
      gl.vertexAttribDivisor(0, 1);
      gl.vertexAttribDivisor(1, 1);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    } catch (error) {
      this.dispose();
      throw error;
    }
  }
  private uniform(name: string) {
    let location = this.uniforms.get(name);
    if (!location) {
      location = this.gl.getUniformLocation(this.program, name) ?? undefined;
      if (!location) throw Error(`Missing curve uniform ${name}`);
      this.uniforms.set(name, location);
    }
    return location;
  }
  private prepare(curve: PatternCurve, scale: PatternFrame["scale"]) {
    const saved = this.buffers.find(
      (b) => b.x === curve.x && b.y === curve.y && b.scale === scale,
    );
    if (saved) return saved;
    const gl = this.gl,
      points = new Float32Array(curve.x.length * 4);
    for (let i = 0; i < curve.x.length; i++) {
      const x = curve.x[i],
        sourceY = curve.y[i];
      let y =
        sourceY === null ||
        !Number.isFinite(sourceY) ||
        (scale === "log" && sourceY <= 0)
          ? NaN
          : sourceY;
      if (scale === "log") y = Math.log10(Math.max(1e-6, y));
      else if (scale === "sqrt") y = Math.sqrt(Math.max(0, y));
      const xHigh = Math.fround(x),
        yHigh = Math.fround(y);
      if (
        (Number.isFinite(x) && !Number.isFinite(xHigh)) ||
        (Number.isFinite(y) && !Number.isFinite(yHigh))
      )
        throw Error("Curve exceeds GPU float range");
      points.set([xHigh, x - xHigh, yHigh, y - yHigh], i * 4);
    }
    const buffer = gl.createBuffer();
    if (!buffer) throw Error("Cannot allocate curve buffer");
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, points, gl.STATIC_DRAW);
    if (gl.getError() !== gl.NO_ERROR) {
      gl.deleteBuffer(buffer);
      throw Error("Curve upload failed");
    }
    this.stats.uploads++;
    this.stats.uploadBytes += points.byteLength;
    const item = {
      x: curve.x,
      y: curve.y,
      scale,
      buffer,
      count: curve.x.length,
    };
    this.buffers.push(item);
    return item;
  }
  draw(frame: PatternFrame) {
    const gl = this.gl;
    if (this.disposed || gl.isContextLost()) throw Error("Curve context lost");
    const { size, bounds, view } = frame;
    const width = Math.max(1, Math.round(size.width * size.dpr)),
      height = Math.max(1, Math.round(size.height * size.dpr));
    if (this.canvas.width !== width) this.canvas.width = width;
    if (this.canvas.height !== height) this.canvas.height = height;
    gl.viewport(0, 0, width, height);
    gl.disable(gl.SCISSOR_TEST);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.SCISSOR_TEST);
    const left = Math.round(bounds.left * size.dpr),
      right = Math.round((bounds.left + bounds.width) * size.dpr);
    const top = Math.round(bounds.top * size.dpr),
      bottom = Math.round((bounds.top + bounds.height) * size.dpr);
    gl.scissor(
      left,
      height - bottom,
      Math.max(0, right - left),
      Math.max(0, bottom - top),
    );
    gl.useProgram(this.program);
    const xHigh = Math.fround(view.xMin),
      yHigh = Math.fround(view.yMin);
    gl.uniform2f(this.uniform("originHigh"), xHigh, yHigh);
    gl.uniform2f(
      this.uniform("originLow"),
      view.xMin - xHigh,
      view.yMin - yHigh,
    );
    gl.uniform2f(
      this.uniform("projection"),
      bounds.width / (view.xMax - view.xMin),
      bounds.height / (view.yMax - view.yMin),
    );
    gl.uniform4f(
      this.uniform("plot"),
      bounds.left,
      bounds.top,
      bounds.width,
      bounds.height,
    );
    gl.uniform2f(this.uniform("viewport"), width / size.dpr, height / size.dpr);
    gl.uniform1f(this.uniform("feather"), 0.5 / size.dpr);
    const used = new Set<CurveBuffer>();
    let segments = 0;
    try {
      for (const curve of frame.curves) {
        if (curve.x.length < 2) continue;
        const buffer = this.prepare(curve, frame.scale);
        used.add(buffer);
        const [start, end] = visibleSamples(curve.x, view.xMin, view.xMax);
        const count = Math.max(0, end - start - 1);
        if (!count) continue;
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer.buffer);
        gl.vertexAttribPointer(0, 4, gl.FLOAT, false, 16, start * 16);
        gl.vertexAttribPointer(1, 4, gl.FLOAT, false, 16, (start + 1) * 16);
        gl.uniform4fv(this.uniform("color"), rgba(curve.color));
        gl.uniform1f(this.uniform("halfWidth"), curve.width / 2);
        gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, count);
        segments += count;
      }
    } finally {
      // Release superseded buffers even when a later curve cannot be uploaded.
      for (const item of this.buffers)
        if (!used.has(item)) gl.deleteBuffer(item.buffer);
      this.buffers = this.buffers.filter((item) => used.has(item));
    }
    this.stats.draws++;
    this.stats.segments = segments;
  }
  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    for (const item of this.buffers) this.gl.deleteBuffer(item.buffer);
    this.buffers = [];
    this.gl.deleteProgram(this.program);
    this.gl.getExtension("WEBGL_lose_context")?.loseContext();
  }
}

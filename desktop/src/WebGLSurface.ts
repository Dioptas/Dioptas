import { rasterColor } from "./colorMaps";
import type { SurfaceTriangle, SurfaceVertex } from "./batchSurfaceRenderer";
import type { SurfaceGuides } from "./batchSurfaceGuides";

const vertexSource = `#version 300 es
in vec3 position;
in float intensity;
out float value;
void main() {
  gl_Position = vec4(position, 1.0);
  value = intensity;
}`;
const fragmentSource = `#version 300 es
precision highp float;
in float value;
uniform sampler2D palette;
uniform int contourCount;
uniform float contourLevels[12];
uniform float contourWidth;
out vec4 color;
void main() {
  color = texture(palette, vec2((clamp(value, 0.0, 1.0) * 255.0 + 0.5) / 256.0, 0.5));
  float gradient = fwidth(value);
  if (gradient > 0.0000001) {
    float coverage = 0.0;
    for (int i = 0; i < 12; i++) {
      if (i >= contourCount) break;
      float distance = abs(value - contourLevels[i]) / gradient;
      coverage = max(coverage, 1.0 - smoothstep(0.25 * contourWidth, 1.05 * contourWidth, distance));
    }
    // Preserve the surface hue: contours are a faint tonal crease.
    color.rgb *= 1.0 - coverage * 0.14;
  }
}`;

const guideVertexSource = `#version 300 es
in vec3 position;
in vec4 guideColor;
out vec4 tint;
void main() { gl_Position = vec4(position, 1.0); tint = guideColor; }`;
const guideFragmentSource = `#version 300 es
precision highp float;
in vec4 tint;
out vec4 color;
void main() { color = tint; }`;

const guideColors = new Map<string, number[]>();
function guideColor(css: string) {
  let color = guideColors.get(css);
  if (!color) {
    const ctx = document.createElement("canvas").getContext("2d")!;
    ctx.canvas.width = ctx.canvas.height = 1;
    ctx.fillStyle = css;
    ctx.fillRect(0, 0, 1, 1);
    color = Array.from(ctx.getImageData(0, 0, 1, 1).data, (v) => v / 255);
    if (guideColors.size >= 128) guideColors.clear();
    guideColors.set(css, color);
  }
  return color;
}

/** Depth-tested GPU mesh. Positions are the same physical-axis projection used
 * by the Canvas annotations and linked picking. Height/color values are already
 * display-transformed; this class never reads or changes a scientific matrix.
 * The transparent offscreen image is composited into the existing capture canvas.
 */
class WebGLSurface {
  readonly canvas = document.createElement("canvas");
  private gl: WebGL2RenderingContext;
  private program: WebGLProgram | null = null;
  private vao: WebGLVertexArrayObject | null = null;
  private buffers: WebGLBuffer[] = [];
  private texture: WebGLTexture | null = null;
  private guideProgram: WebGLProgram | null = null;
  private guideVAO: WebGLVertexArrayObject | null = null;
  private palette = "";
  private disposed = false;

  constructor() {
    const gl = this.canvas.getContext("webgl2", {
      alpha: true,
      premultipliedAlpha: true,
      antialias: true,
      depth: true,
      stencil: false,
      preserveDrawingBuffer: true,
    });
    if (!gl) throw Error("WebGL 2 is unavailable");
    this.gl = gl;
    try {
      const compile = (vertex: string, fragment: string) => {
        const program = gl.createProgram();
        if (!program) throw Error("Cannot allocate surface program");
        for (const [type, source] of [
          [gl.VERTEX_SHADER, vertex],
          [gl.FRAGMENT_SHADER, fragment],
        ] as const) {
          const shader = gl.createShader(type);
          if (!shader) {
            gl.deleteProgram(program);
            throw Error("Cannot allocate surface shader");
          }
          gl.shaderSource(shader, source);
          gl.compileShader(shader);
          if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            const message = gl.getShaderInfoLog(shader);
            gl.deleteShader(shader);
            gl.deleteProgram(program);
            throw Error(message ?? "Surface shader compilation failed");
          }
          gl.attachShader(program, shader);
          gl.deleteShader(shader);
        }
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
          const message = gl.getProgramInfoLog(program);
          gl.deleteProgram(program);
          throw Error(message ?? "Surface shader link failed");
        }
        return program;
      };
      const program = (this.program = compile(vertexSource, fragmentSource));
      this.guideProgram = compile(guideVertexSource, guideFragmentSource);
      this.vao = gl.createVertexArray();
      const vertices = gl.createBuffer(),
        indices = gl.createBuffer();
      if (vertices) this.buffers.push(vertices);
      if (indices) this.buffers.push(indices);
      this.texture = gl.createTexture();
      if (!this.vao || !vertices || !indices || !this.texture)
        throw Error("Cannot allocate surface buffers");
      gl.bindVertexArray(this.vao);
      gl.bindBuffer(gl.ARRAY_BUFFER, vertices);
      const position = gl.getAttribLocation(program, "position"),
        intensity = gl.getAttribLocation(program, "intensity");
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 3, gl.FLOAT, false, 16, 0);
      gl.enableVertexAttribArray(intensity);
      gl.vertexAttribPointer(intensity, 1, gl.FLOAT, false, 16, 12);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indices);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.texture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.useProgram(program);
      gl.uniform1i(gl.getUniformLocation(program, "palette"), 0);
      this.guideVAO = gl.createVertexArray();
      const guides = gl.createBuffer();
      if (guides) this.buffers.push(guides);
      if (!this.guideVAO || !guides)
        throw Error("Cannot allocate phase guides");
      gl.bindVertexArray(this.guideVAO);
      gl.bindBuffer(gl.ARRAY_BUFFER, guides);
      const guidePosition = gl.getAttribLocation(this.guideProgram, "position"),
        guideTint = gl.getAttribLocation(this.guideProgram, "guideColor");
      gl.enableVertexAttribArray(guidePosition);
      gl.vertexAttribPointer(guidePosition, 3, gl.FLOAT, false, 28, 0);
      gl.enableVertexAttribArray(guideTint);
      gl.vertexAttribPointer(guideTint, 4, gl.FLOAT, false, 28, 12);
    } catch (error) {
      this.dispose();
      throw error;
    }
  }

  draw(
    vertices: SurfaceVertex[],
    triangles: SurfaceTriangle[],
    width: number,
    height: number,
    pixelWidth: number,
    pixelHeight: number,
    palette: string,
    guides: SurfaceGuides,
  ) {
    const gl = this.gl;
    if (this.disposed || gl.isContextLost())
      throw Error("Surface GPU context lost");
    if (this.canvas.width !== pixelWidth) this.canvas.width = pixelWidth;
    if (this.canvas.height !== pixelHeight) this.canvas.height = pixelHeight;
    let minDepth = Infinity,
      maxDepth = -Infinity;
    for (const p of vertices)
      if (Number.isFinite(p.z)) {
        minDepth = Math.min(minDepth, p.depth);
        maxDepth = Math.max(maxDepth, p.depth);
      }
    for (const p of [
      ...guides.planes.flatMap((plane) => plane.points),
      ...guides.segments.flatMap((segment) => segment.points),
    ]) {
      minDepth = Math.min(minDepth, p.depth);
      maxDepth = Math.max(maxDepth, p.depth);
    }
    const span = Math.max(1e-12, maxDepth - minDepth);
    const packed = new Float32Array(vertices.length * 4);
    vertices.forEach((p, i) => {
      if (!Number.isFinite(p.z)) return;
      packed[i * 4] = (2 * p.x) / Math.max(1, width) - 1;
      packed[i * 4 + 1] = 1 - (2 * p.y) / Math.max(1, height);
      // Larger projected depth faces the camera. Keep extrema away from the
      // clipping planes; depth testing resolves crossing/overlapping profiles.
      packed[i * 4 + 2] = 0.98 - (1.96 * (p.depth - minDepth)) / span;
      packed[i * 4 + 3] = p.z;
    });
    const indices = new Uint32Array(triangles.length * 3);
    triangles.forEach((tri, i) =>
      tri.forEach((p, j) => {
        indices[i * 3 + j] = p.meshIndex;
      }),
    );
    gl.viewport(0, 0, pixelWidth, pixelHeight);
    gl.useProgram(this.program);
    gl.uniform1i(
      gl.getUniformLocation(this.program!, "contourCount"),
      guides.contours.length,
    );
    const levels = new Float32Array(12);
    levels.set(guides.contours);
    gl.uniform1fv(
      gl.getUniformLocation(this.program!, "contourLevels[0]"),
      levels,
    );
    gl.uniform1f(
      gl.getUniformLocation(this.program!, "contourWidth"),
      pixelWidth / Math.max(1, width),
    );
    gl.bindVertexArray(this.vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers[0]);
    gl.bufferData(gl.ARRAY_BUFFER, packed, gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers[1]);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, indices, gl.DYNAMIC_DRAW);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    if (this.palette !== palette) {
      const colors = new Uint8Array(256 * 4);
      for (let i = 0; i < 256; i++)
        colors.set([...rasterColor(i / 255, palette), 255], i * 4);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA8,
        256,
        1,
        0,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        colors,
      );
      this.palette = palette;
    }
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.disable(gl.CULL_FACE);
    gl.disable(gl.BLEND);
    gl.depthMask(true);
    gl.clearColor(0, 0, 0, 0);
    gl.clearDepth(1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.drawElements(gl.TRIANGLES, indices.length, gl.UNSIGNED_INT, 0);
    if (guides.planes.length || guides.segments.length) {
      gl.useProgram(this.guideProgram);
      gl.bindVertexArray(this.guideVAO);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers[2]);
      gl.enable(gl.BLEND);
      gl.blendFuncSeparate(
        gl.SRC_ALPHA,
        gl.ONE_MINUS_SRC_ALPHA,
        gl.ONE,
        gl.ONE_MINUS_SRC_ALPHA,
      );
      gl.depthMask(false);
      const pack = (
        x: number,
        y: number,
        depth: number,
        color: number[],
        opacity = 1,
        bias = 0,
      ) => [
        (2 * x) / Math.max(1, width) - 1,
        1 - (2 * y) / Math.max(1, height),
        0.98 - (1.96 * (depth - minDepth)) / span - bias,
        color[0],
        color[1],
        color[2],
        color[3] * opacity,
      ];
      const draw = (data: number[]) => {
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.DYNAMIC_DRAW);
        gl.drawArrays(gl.TRIANGLES, 0, data.length / 7);
      };
      const planes = [...guides.planes].sort(
        (a, b) =>
          a.points.reduce((sum, p) => sum + p.depth, 0) -
          b.points.reduce((sum, p) => sum + p.depth, 0),
      );
      const planeData: number[] = [];
      for (const plane of planes)
        for (const i of [0, 1, 2, 1, 3, 2]) {
          const p = plane.points[i];
          planeData.push(
            ...pack(p.x, p.y, p.depth, guideColor(plane.color), plane.opacity),
          );
        }
      draw(planeData);
      // Screen-space ribbons give a stable CSS width even on Retina displays;
      // their depths interpolate along the exact triangle/slice intersection.
      const lineData: number[] = [];
      for (const segment of guides.segments) {
        const [a, b] = segment.points,
          length = Math.hypot(b.x - a.x, b.y - a.y);
        if (length < 1e-6) continue;
        const nx = ((-(b.y - a.y) / length) * segment.width) / 2,
          ny = (((b.x - a.x) / length) * segment.width) / 2;
        const color = guideColor(segment.color);
        for (const [p, side] of [
          [a, -1],
          [a, 1],
          [b, -1],
          [a, 1],
          [b, 1],
          [b, -1],
        ] as const)
          lineData.push(
            ...pack(
              p.x + nx * side,
              p.y + ny * side,
              p.depth,
              color,
              1,
              0.00015,
            ),
          );
      }
      draw(lineData);
      gl.depthMask(true);
      gl.disable(gl.BLEND);
    }
    if (gl.isContextLost() || gl.getError() !== gl.NO_ERROR)
      throw Error("Surface GPU draw failed");
    return this.canvas;
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    for (const buffer of this.buffers) this.gl.deleteBuffer(buffer);
    if (this.texture) this.gl.deleteTexture(this.texture);
    if (this.vao) this.gl.deleteVertexArray(this.vao);
    if (this.guideVAO) this.gl.deleteVertexArray(this.guideVAO);
    if (this.program) this.gl.deleteProgram(this.program);
    if (this.guideProgram) this.gl.deleteProgram(this.guideProgram);
    this.gl.getExtension("WEBGL_lose_context")?.loseContext();
  }
}

const surfaces = new WeakMap<HTMLCanvasElement, WebGLSurface | null>();
export function drawSurfaceGPU(
  canvas: HTMLCanvasElement,
  vertices: SurfaceVertex[],
  triangles: SurfaceTriangle[],
  width: number,
  height: number,
  palette: string,
  guides: SurfaceGuides = { contours: [], segments: [], planes: [] },
): HTMLCanvasElement | null {
  let surface = surfaces.get(canvas);
  if (surface === null) return null;
  try {
    if (!surface) {
      surface = new WebGLSurface();
      surfaces.set(canvas, surface);
    }
    return surface.draw(
      vertices,
      triangles,
      width,
      height,
      canvas.width,
      canvas.height,
      palette,
      guides,
    );
  } catch {
    surface?.dispose();
    surfaces.set(canvas, null);
    return null;
  }
}
export function disposeSurfaceGPU(canvas: HTMLCanvasElement) {
  surfaces.get(canvas)?.dispose();
  surfaces.delete(canvas);
}

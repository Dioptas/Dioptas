import { rasterColor } from "./colorMaps";
import type { SurfaceTriangle, SurfaceVertex } from "./batchSurfaceRenderer";
import type { SurfaceGuides } from "./batchSurfaceGuides";
import type { SurfacePoint } from "./batchSurfaceGeometry";

const vertexSource = `#version 300 es
in vec3 position;
in float intensity;
uniform mat4 projection;
out float value;
void main() { gl_Position = projection * vec4(position, 1.0); value = intensity; }`;
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
    color.rgb *= 1.0 - coverage * 0.07;
  }
}`;
const guideVertexSource = `#version 300 es
in vec3 position;
in vec3 direction;
in vec2 stroke;
in vec4 guideColor;
uniform mat4 projection;
uniform vec2 viewport;
out vec4 tint;
void main() {
  vec4 p = projection * vec4(position, 1.0);
  vec2 delta = (projection * vec4(direction, 0.0)).xy * viewport;
  float magnitude = length(delta);
  if (magnitude > 0.000001 && stroke.x != 0.0) {
    vec2 normal = vec2(-delta.y, delta.x) / magnitude;
    p.xy += normal * stroke.x * stroke.y / viewport;
    p.z -= 0.00015;
  }
  gl_Position = p; tint = guideColor;
}`;
const guideFragmentSource = `#version 300 es
precision highp float;
in vec4 tint;
out vec4 color;
void main() { color = tint; }`;
const identity = new Float32Array([
  1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1,
]);
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

/** Resident world-space mesh. Navigation updates a projection uniform, leaving
 * source values, vertex/index buffers, and phase geometry on the GPU. */
class WebGLSurface {
  readonly canvas = document.createElement("canvas");
  private gl: WebGL2RenderingContext;
  private programs: WebGLProgram[] = [];
  private vaos: WebGLVertexArrayObject[] = [];
  private buffers: WebGLBuffer[] = [];
  private texture: WebGLTexture | null = null;
  private palette = "";
  private disposed = false;
  private vertices?: SurfaceVertex[];
  private triangles?: SurfaceTriangle[];
  private guides?: SurfaceGuides;
  private planeOrder = "";
  private lineStart = 0;
  private lineCount = 0;
  private meshUploads = 0;

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
      for (const [vertex, fragment] of [
        [vertexSource, fragmentSource],
        [guideVertexSource, guideFragmentSource],
      ]) {
        const program = gl.createProgram();
        if (!program) throw Error("Cannot allocate surface program");
        this.programs.push(program);
        for (const [type, source] of [
          [gl.VERTEX_SHADER, vertex],
          [gl.FRAGMENT_SHADER, fragment],
        ] as const) {
          const shader = gl.createShader(type);
          if (!shader) throw Error("Cannot allocate surface shader");
          gl.shaderSource(shader, source);
          gl.compileShader(shader);
          if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            const message = gl.getShaderInfoLog(shader);
            gl.deleteShader(shader);
            throw Error(message ?? "Surface shader compilation failed");
          }
          gl.attachShader(program, shader);
          gl.deleteShader(shader);
        }
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS))
          throw Error(
            gl.getProgramInfoLog(program) ?? "Surface shader link failed",
          );
        const vao = gl.createVertexArray();
        if (!vao) throw Error("Cannot allocate surface vertex array");
        this.vaos.push(vao);
      }
      for (let i = 0; i < 4; i++) {
        const buffer = gl.createBuffer();
        if (!buffer) throw Error("Cannot allocate surface buffer");
        this.buffers.push(buffer);
      }
      const attribute = (
        program: WebGLProgram,
        name: string,
        size: number,
        stride: number,
        offset: number,
      ) => {
        const location = gl.getAttribLocation(program, name);
        gl.enableVertexAttribArray(location);
        gl.vertexAttribPointer(location, size, gl.FLOAT, false, stride, offset);
      };
      gl.bindVertexArray(this.vaos[0]);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers[0]);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers[1]);
      attribute(this.programs[0], "position", 3, 16, 0);
      attribute(this.programs[0], "intensity", 1, 16, 12);
      gl.bindVertexArray(this.vaos[1]);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers[2]);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers[3]);
      attribute(this.programs[1], "position", 3, 48, 0);
      attribute(this.programs[1], "direction", 3, 48, 12);
      attribute(this.programs[1], "stroke", 2, 48, 24);
      attribute(this.programs[1], "guideColor", 4, 48, 32);
      this.texture = gl.createTexture();
      if (!this.texture) throw Error("Cannot allocate surface palette");
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.texture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.useProgram(this.programs[0]);
      gl.uniform1i(gl.getUniformLocation(this.programs[0], "palette"), 0);
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
    projection?: Float32Array,
  ) {
    const gl = this.gl;
    if (this.disposed || gl.isContextLost())
      throw Error("Surface GPU context lost");
    if (this.canvas.width !== pixelWidth) this.canvas.width = pixelWidth;
    if (this.canvas.height !== pixelHeight) this.canvas.height = pixelHeight;
    const matrix = projection ?? identity;
    // The direct screen-coordinate path is retained for independent renderer
    // checks; the application supplies normalized coordinates plus a matrix.
    let minDepth = Infinity,
      maxDepth = -Infinity;
    if (!projection) {
      for (const p of [
        ...vertices,
        ...guides.planes.flatMap((g) => g.points),
        ...guides.segments.flatMap((g) => g.points),
      ])
        if (Number.isFinite(p.depth)) {
          minDepth = Math.min(minDepth, p.depth);
          maxDepth = Math.max(maxDepth, p.depth);
        }
    }
    const span = Math.max(1e-12, maxDepth - minDepth);
    const position = (p: SurfacePoint): [number, number, number] =>
      projection
        ? [p.x, p.y, p.depth]
        : [
            (2 * p.x) / Math.max(1, width) - 1,
            1 - (2 * p.y) / Math.max(1, height),
            0.98 - (1.96 * (p.depth - minDepth)) / span,
          ];
    gl.bindVertexArray(this.vaos[0]);
    if (
      !projection ||
      this.vertices !== vertices ||
      this.triangles !== triangles
    ) {
      const packed = new Float32Array(vertices.length * 4);
      vertices.forEach((p, i) => {
        if (Number.isFinite(p.z)) packed.set([...position(p), p.z], i * 4);
      });
      const indices = new Uint32Array(triangles.length * 3);
      triangles.forEach((tri, i) =>
        tri.forEach((p, j) => (indices[i * 3 + j] = p.meshIndex)),
      );
      gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers[0]);
      gl.bufferData(gl.ARRAY_BUFFER, packed, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers[1]);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, indices, gl.STATIC_DRAW);
      this.vertices = vertices;
      this.triangles = triangles;
      this.meshUploads++;
    }
    gl.viewport(0, 0, pixelWidth, pixelHeight);
    gl.useProgram(this.programs[0]);
    gl.uniformMatrix4fv(
      gl.getUniformLocation(this.programs[0], "projection"),
      false,
      matrix,
    );
    gl.uniform1i(
      gl.getUniformLocation(this.programs[0], "contourCount"),
      guides.contours.length,
    );
    const levels = new Float32Array(12);
    levels.set(guides.contours);
    gl.uniform1fv(
      gl.getUniformLocation(this.programs[0], "contourLevels[0]"),
      levels,
    );
    gl.uniform1f(
      gl.getUniformLocation(this.programs[0], "contourWidth"),
      pixelWidth / Math.max(1, width),
    );
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
    gl.drawElements(gl.TRIANGLES, triangles.length * 3, gl.UNSIGNED_INT, 0);
    if (guides.planes.length || guides.segments.length) {
      gl.useProgram(this.programs[1]);
      gl.bindVertexArray(this.vaos[1]);
      gl.uniformMatrix4fv(
        gl.getUniformLocation(this.programs[1], "projection"),
        false,
        matrix,
      );
      gl.uniform2f(
        gl.getUniformLocation(this.programs[1], "viewport"),
        Math.max(1, width),
        Math.max(1, height),
      );
      if (!projection || this.guides !== guides) {
        const data: number[] = [];
        const pack = (
          p: SurfacePoint,
          d: number[],
          side: number,
          strokeWidth: number,
          color: number[],
          opacity = 1,
        ) =>
          data.push(
            ...position(p),
            ...d,
            side,
            strokeWidth,
            color[0],
            color[1],
            color[2],
            color[3] * opacity,
          );
        for (const plane of guides.planes)
          for (const i of [0, 1, 2, 1, 3, 2])
            pack(
              plane.points[i],
              [0, 0, 0],
              0,
              0,
              guideColor(plane.color),
              plane.opacity,
            );
        this.lineStart = data.length / 12;
        for (const segment of guides.segments) {
          const [a, b] = segment.points,
            pa = position(a),
            pb = position(b),
            d = pb.map((v, i) => v - pa[i]);
          for (const [p, side] of [
            [a, -1],
            [a, 1],
            [b, -1],
            [a, 1],
            [b, 1],
            [b, -1],
          ] as const)
            pack(p, d, side, segment.width, guideColor(segment.color));
        }
        this.lineCount = data.length / 12 - this.lineStart;
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers[2]);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
        this.guides = guides;
        this.planeOrder = "";
      }
      if (guides.planes.length) {
        const orderKey = [matrix[2], matrix[6], matrix[10]].join(",");
        if (orderKey !== this.planeOrder) {
          const depth = (p: SurfacePoint) => {
            const v = position(p);
            return matrix[2] * v[0] + matrix[6] * v[1] + matrix[10] * v[2];
          };
          const order = guides.planes
            .map((plane, i) => ({
              i,
              depth: plane.points.reduce((sum, p) => sum + depth(p), 0),
            }))
            .sort((a, b) => b.depth - a.depth);
          const indices = new Uint32Array(order.length * 6);
          order.forEach(({ i }, j) => {
            for (let k = 0; k < 6; k++) indices[j * 6 + k] = i * 6 + k;
          });
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.buffers[3]);
          gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, indices, gl.DYNAMIC_DRAW);
          this.planeOrder = orderKey;
        }
      }
      gl.enable(gl.BLEND);
      gl.blendFuncSeparate(
        gl.SRC_ALPHA,
        gl.ONE_MINUS_SRC_ALPHA,
        gl.ONE,
        gl.ONE_MINUS_SRC_ALPHA,
      );
      gl.depthMask(false);
      if (guides.planes.length)
        gl.drawElements(
          gl.TRIANGLES,
          guides.planes.length * 6,
          gl.UNSIGNED_INT,
          0,
        );
      gl.drawArrays(gl.TRIANGLES, this.lineStart, this.lineCount);
      gl.depthMask(true);
      gl.disable(gl.BLEND);
    }
    if (gl.isContextLost() || gl.getError() !== gl.NO_ERROR)
      throw Error("Surface GPU draw failed");
    this.canvas.dataset.meshUploads = String(this.meshUploads);
    return this.canvas;
  }
  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    for (const b of this.buffers) this.gl.deleteBuffer(b);
    if (this.texture) this.gl.deleteTexture(this.texture);
    for (const vao of this.vaos) this.gl.deleteVertexArray(vao);
    for (const p of this.programs) this.gl.deleteProgram(p);
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
  projection?: Float32Array,
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
      projection,
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

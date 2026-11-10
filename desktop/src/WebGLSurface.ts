import { rasterColor } from "./colorMaps";
import type { SurfaceTriangle, SurfaceVertex } from "./batchSurfaceRenderer";

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
out vec4 color;
void main() {
  color = texture(palette, vec2((clamp(value, 0.0, 1.0) * 255.0 + 0.5) / 256.0, 0.5));
}`;

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
  private palette = "";
  private disposed = false;

  constructor() {
    const gl = this.canvas.getContext("webgl2", {
      alpha: true,
      premultipliedAlpha: false,
      antialias: true,
      depth: true,
      stencil: false,
      preserveDrawingBuffer: true,
    });
    if (!gl) throw Error("WebGL 2 is unavailable");
    this.gl = gl;
    try {
      const program = gl.createProgram();
      if (!program) throw Error("Cannot allocate surface program");
      this.program = program;
      for (const [type, source] of [
        [gl.VERTEX_SHADER, vertexSource],
        [gl.FRAGMENT_SHADER, fragmentSource],
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
    gl.clearColor(0, 0, 0, 0);
    gl.clearDepth(1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.drawElements(gl.TRIANGLES, indices.length, gl.UNSIGNED_INT, 0);
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
    if (this.program) this.gl.deleteProgram(this.program);
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

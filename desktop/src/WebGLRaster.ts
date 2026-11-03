/** Display-only renderer. Source arrays stay on the CPU for scientific readout.
 * One full-resolution source/mask texture per mounted view; no unbounded GPU cache.
 */
export interface RasterFrame {
  data: Float32Array | Uint8Array;
  mask: Float32Array | Uint8Array | null;
  width: number;
  height: number;
  colors: number[][];
  lower: number;
  upper: number;
  log: boolean;
  maskOpacity: number;
  viewport: { width: number; height: number; dpr: number };
  image: { x: number; y: number; width: number; height: number };
  clip: { left: number; top: number; width: number; height: number };
}

const vertex = `#version 300 es
precision highp float;
uniform vec2 viewport;
uniform vec4 image;
out vec2 uv;
void main() {
  uv = vec2(float(gl_VertexID & 1), float(gl_VertexID >> 1));
  vec2 pixel = image.xy + vec2(uv.x, 1.0 - uv.y) * image.zw;
  gl_Position = vec4(pixel / viewport * vec2(2.0, -2.0) + vec2(-1.0, 1.0), 0.0, 1.0);
}`;
const fragment = `#version 300 es
precision highp float;
uniform highp sampler2D source;
uniform highp sampler2D mask;
uniform highp sampler2D palette;
uniform float lower;
uniform float lowerResidual;
uniform float span;
uniform float logSpan;
uniform bool logarithmic;
uniform bool masked;
uniform float maskOpacity;
in vec2 uv;
out vec4 outputColor;
float log1p(float x) {
  return x < 0.0001 ? x * (1.0 - x * 0.5) : log(1.0 + x);
}
void main() {
  float value = texture(source, uv).r;
  vec3 color = vec3(23.0, 25.0, 30.0) / 255.0;
  if (!isnan(value) && !isinf(value)) {
    // Split the double-precision display limit so narrow ranges on top of a
    // large source intensity do not lose their offset in a float uniform.
    float delta = (value - lower) - lowerResidual;
    float t = logarithmic ? log1p(max(0.0, delta)) / logSpan : delta / span;
    float k = clamp(t, 0.0, 1.0) * float(textureSize(palette, 0).x - 1);
    int i = min(int(floor(k)), textureSize(palette, 0).x - 2);
    vec3 a = texelFetch(palette, ivec2(i, 0), 0).rgb;
    vec3 b = texelFetch(palette, ivec2(i + 1, 0), 0).rgb;
    // Match the existing rounded colour lookup before blending the mask.
    color = floor(mix(a, b, k - float(i)) * 255.0 + 0.5) / 255.0;
  }
  if (masked && texture(mask, uv).r != 0.0)
    color = mix(color, vec3(1.0, 0.0, 0.0), maskOpacity);
  outputColor = vec4(color, 1.0);
}`;

export class WebGLRaster {
  private gl: WebGL2RenderingContext;
  private program: WebGLProgram;
  private textures: WebGLTexture[] = [];
  private uniforms = new Map<string, WebGLUniformLocation>();
  private sourceData?: Float32Array | Uint8Array;
  private maskData?: Float32Array | Uint8Array | null;
  private colors?: number[][];
  private shape = "";
  private maxSize: number;
  private disposed = false;

  constructor(private canvas: HTMLCanvasElement) {
    const gl = canvas.getContext("webgl2", {
      alpha: true,
      premultipliedAlpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      preserveDrawingBuffer: false,
    });
    if (!gl) throw Error("WebGL 2 unavailable");
    this.gl = gl;
    this.maxSize = gl.getParameter(gl.MAX_TEXTURE_SIZE);
    const program = gl.createProgram();
    if (!program) throw Error("Cannot allocate raster program");
    this.program = program;
    try {
      for (const [type, code] of [
        [gl.VERTEX_SHADER, vertex],
        [gl.FRAGMENT_SHADER, fragment],
      ] as const) {
        const shader = gl.createShader(type);
        if (!shader) throw Error("Cannot allocate raster shader");
        gl.shaderSource(shader, code);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
          const error = gl.getShaderInfoLog(shader);
          gl.deleteShader(shader);
          throw Error(error ?? "Raster shader compilation failed");
        }
        gl.attachShader(program, shader);
        gl.deleteShader(shader);
      }
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS))
        throw Error(
          gl.getProgramInfoLog(program) ?? "Raster shader link failed",
        );
      gl.useProgram(program);
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      for (const [unit, name] of ["source", "mask", "palette"].entries()) {
        const texture = gl.createTexture();
        if (!texture) throw Error("Cannot allocate raster texture");
        this.textures.push(texture);
        gl.activeTexture(gl.TEXTURE0 + unit);
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.uniform1i(this.uniform(name), unit);
      }
      // Always bind a complete mask, including for an unmasked image.
      gl.activeTexture(gl.TEXTURE1);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.R8,
        1,
        1,
        0,
        gl.RED,
        gl.UNSIGNED_BYTE,
        new Uint8Array(1),
      );
    } catch (error) {
      this.dispose();
      throw error;
    }
  }

  private uniform(name: string) {
    let location = this.uniforms.get(name);
    if (!location) {
      location = this.gl.getUniformLocation(this.program, name) ?? undefined;
      if (!location) throw Error(`Missing raster uniform: ${name}`);
      this.uniforms.set(name, location);
    }
    return location;
  }

  draw(frame: RasterFrame) {
    const gl = this.gl;
    if (this.disposed || gl.isContextLost()) throw Error("Raster context lost");
    const { width, height, data, mask, colors, viewport, image, clip } = frame;
    if (width > this.maxSize || height > this.maxSize)
      throw Error(`Image exceeds GPU texture limit (${this.maxSize})`);
    const span = Math.max(frame.upper - frame.lower, 1e-12);
    if (
      !Number.isFinite(Math.fround(span)) ||
      !Number.isFinite(Math.fround(frame.lower))
    )
      throw Error("Display range exceeds GPU float precision");
    const shape = `${width}x${height}`;
    const changedShape = shape !== this.shape;
    let uploaded = false;
    if (data !== this.sourceData || changedShape) {
      gl.activeTexture(gl.TEXTURE0);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.R32F,
        width,
        height,
        0,
        gl.RED,
        gl.FLOAT,
        data instanceof Float32Array ? data : Float32Array.from(data),
      );
      uploaded = true;
    }
    if (mask !== this.maskData || changedShape) {
      gl.activeTexture(gl.TEXTURE1);
      // Masks in the transport are uint8; accept float masks without changing
      // the previous rule that any nonzero value is masked.
      const bytes =
        mask instanceof Float32Array
          ? Uint8Array.from(mask, (v) => (v ? 1 : 0))
          : mask;
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.R8,
        mask ? width : 1,
        mask ? height : 1,
        0,
        gl.RED,
        gl.UNSIGNED_BYTE,
        bytes ?? new Uint8Array(1),
      );
      uploaded = true;
    }
    if (colors !== this.colors) {
      const rgba = Uint8Array.from(colors.flatMap((c) => [...c, 255]));
      gl.activeTexture(gl.TEXTURE2);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA8,
        colors.length,
        1,
        0,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        rgba,
      );
      uploaded = true;
    }
    // Check only at allocations/uploads, never synchronously on every pan frame.
    if (uploaded && gl.getError() !== gl.NO_ERROR)
      throw Error("Raster texture upload failed");
    this.sourceData = data;
    this.maskData = mask;
    this.colors = colors;
    this.shape = shape;
    const pixelWidth = Math.max(1, Math.round(viewport.width * viewport.dpr));
    const pixelHeight = Math.max(1, Math.round(viewport.height * viewport.dpr));
    if (this.canvas.width !== pixelWidth) this.canvas.width = pixelWidth;
    if (this.canvas.height !== pixelHeight) this.canvas.height = pixelHeight;
    gl.viewport(0, 0, pixelWidth, pixelHeight);
    gl.disable(gl.SCISSOR_TEST);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.SCISSOR_TEST);
    // Match Canvas 2D's CSS-to-backing-store transform, including fractional DPR.
    const dx = viewport.dpr,
      dy = viewport.dpr;
    const x0 = Math.round(clip.left * dx),
      x1 = Math.round((clip.left + clip.width) * dx);
    const y0 = Math.round(clip.top * dy),
      y1 = Math.round((clip.top + clip.height) * dy);
    gl.scissor(
      x0,
      pixelHeight - y1,
      Math.max(0, x1 - x0),
      Math.max(0, y1 - y0),
    );
    gl.useProgram(this.program);
    gl.uniform2f(this.uniform("viewport"), pixelWidth / dx, pixelHeight / dy);
    gl.uniform4f(
      this.uniform("image"),
      image.x,
      image.y,
      image.width,
      image.height,
    );
    const lowerHigh = Math.fround(frame.lower);
    gl.uniform1f(this.uniform("lower"), lowerHigh);
    gl.uniform1f(this.uniform("lowerResidual"), frame.lower - lowerHigh);
    gl.uniform1f(this.uniform("span"), span);
    gl.uniform1f(this.uniform("logSpan"), Math.log1p(span));
    gl.uniform1i(this.uniform("logarithmic"), Number(frame.log));
    gl.uniform1i(this.uniform("masked"), Number(!!mask));
    gl.uniform1f(this.uniform("maskOpacity"), frame.maskOpacity);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    for (const texture of this.textures) this.gl.deleteTexture(texture);
    this.gl.deleteProgram(this.program);
    this.sourceData = undefined;
    this.maskData = undefined;
    // Release the browser context slot too when views are switched repeatedly.
    this.gl.getExtension("WEBGL_lose_context")?.loseContext();
  }
}

/** Display-only hook, also usable by future profile/spottiness plots. */
export interface PlotFigureExport {
  capture: () => { png_data: string; svg_data: string };
}

const escapeXml = (value: unknown) =>
  String(value).replace(
    /[<>&"']/g,
    (c) =>
      ({
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
      })[c]!,
  );

let nextId = 0;
const recordings = new WeakMap<HTMLCanvasElement, SvgRecording>();

/** Records the plot's existing Canvas drawing commands while painting normally.
 * Export only: the interactive WebGL/Canvas hot paths do no recording work.
 * Coordinates, clipping, tick generation and phase scaling stay with the renderer.
 */
export class SvgRecording {
  readonly context: CanvasRenderingContext2D;
  crispEdges = false;
  private elements: string[] = [];
  private definitions: string[] = [];
  private path = "";
  private clips: string[] = [];
  private stack: string[][] = [];

  constructor(readonly canvas: HTMLCanvasElement) {
    const context = canvas.getContext("2d")!;
    recordings.set(canvas, this);
    const matrix = () => {
      const m = context.getTransform();
      return `matrix(${[m.a, m.b, m.c, m.d, m.e, m.f].join(" ")})`;
    };
    const add = (element: string) =>
      this.elements.push(
        this.clips.reduce(
          (item, id) => `<g clip-path="url(#${id})">${item}</g>`,
          element,
        ),
      );
    const style = (stroke: boolean) =>
      stroke
        ? `fill="none" stroke="${escapeXml(context.strokeStyle)}" stroke-width="${context.lineWidth}" stroke-linecap="${context.lineCap}" stroke-linejoin="${context.lineJoin}" stroke-miterlimit="${context.miterLimit}" stroke-dasharray="${context.getLineDash().join(" ") || "none"}" stroke-dashoffset="${context.lineDashOffset}"`
        : `fill="${escapeXml(context.fillStyle)}"`;
    const paintPath = (stroke: boolean) =>
      add(
        `<path d="${this.path}" transform="${matrix()}" ${style(stroke)} opacity="${context.globalAlpha}"${this.crispEdges ? ' shape-rendering="crispEdges"' : ""}/>`,
      );
    const methods: Record<string, (...args: any[]) => void> = {
      beginPath: () => {
        this.path = "";
      },
      moveTo: (x, y) => {
        this.path += `M${x} ${y}`;
      },
      lineTo: (x, y) => {
        this.path += `L${x} ${y}`;
      },
      closePath: () => {
        this.path += "Z";
      },
      rect: (x, y, w, h) => {
        this.path += `M${x} ${y}h${w}v${h}h${-w}Z`;
      },
      save: () => {
        this.stack.push([...this.clips]);
      },
      restore: () => {
        this.clips = this.stack.pop() ?? [];
      },
      clip: () => {
        const id = `plot-clip-${nextId++}`;
        this.definitions.push(
          `<clipPath id="${id}" clipPathUnits="userSpaceOnUse"><path d="${this.path}" transform="${matrix()}"/></clipPath>`,
        );
        this.clips.push(id);
      },
      stroke: () => paintPath(true),
      fill: () => paintPath(false),
      fillRect: (x, y, width, height) =>
        add(
          `<rect x="${x}" y="${y}" width="${width}" height="${height}" transform="${matrix()}" ${style(false)} opacity="${context.globalAlpha}"/>`,
        ),
      strokeRect: (x, y, width, height) =>
        add(
          `<rect x="${x}" y="${y}" width="${width}" height="${height}" transform="${matrix()}" ${style(true)}/>`,
        ),
      fillText: (text, x, y) => {
        const anchor =
          context.textAlign === "center"
            ? "middle"
            : ["right", "end"].includes(context.textAlign)
              ? "end"
              : "start";
        const baseline =
          context.textBaseline === "middle"
            ? "central"
            : context.textBaseline === "top"
              ? "text-before-edge"
              : "alphabetic";
        add(
          `<text x="${x}" y="${y}" transform="${matrix()}" style="font: ${escapeXml(context.font)}" text-anchor="${anchor}" dominant-baseline="${baseline}" ${style(false)}>${escapeXml(text)}</text>`,
        );
      },
      drawImage: (
        source: HTMLCanvasElement,
        x,
        y,
        width = source.width,
        height = source.height,
      ) => {
        const recording = recordings.get(source);
        if (!recording)
          throw Error("Figure export requires vector plot layers.");
        this.definitions.push(...recording.definitions);
        add(
          `<g transform="${matrix()}"><g transform="translate(${x} ${y}) scale(${width / source.width} ${height / source.height})">${recording.elements.join("")}</g></g>`,
        );
      },
    };
    this.context = new Proxy(context, {
      get(target, key) {
        const value = Reflect.get(target, key, target);
        if (typeof value !== "function") return value;
        return (...args: any[]) => {
          methods[String(key)]?.(...args);
          return value.apply(target, args);
        };
      },
      set(target, key, value) {
        return Reflect.set(target, key, value, target);
      },
    });
  }

  svg(width: number, height: number) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${this.canvas.width} ${this.canvas.height}" role="img" aria-label="Diffraction pattern"><defs>${this.definitions.join("")}</defs>${this.elements.join("")}</svg>`;
  }
}

/** DOM legends retain their current dragged position, scroll and visible names.
 * Paint text rather than foreignObject so SVG works in independent renderers.
 */
export function drawFigureLegends(
  context: CanvasRenderingContext2D,
  container: HTMLElement,
) {
  const origin = container.getBoundingClientRect();
  for (const legend of container.querySelectorAll<HTMLElement>(
    ".plot-legend",
  )) {
    const box = legend.getBoundingClientRect();
    context.save();
    context.beginPath();
    context.rect(
      box.left - origin.left,
      box.top - origin.top,
      box.width,
      box.height,
    );
    context.clip();
    for (const row of legend.children) {
      const element = row as HTMLElement;
      const style = getComputedStyle(element);
      context.font = `${style.fontSize} ${style.fontFamily}`;
      context.fillStyle = style.color;
      context.textBaseline = "middle";
      context.textAlign = "left";
      // Range rectangles also preserve wrapping when a legend has focus.
      const text = element.firstChild;
      if (!text || text.nodeType !== Node.TEXT_NODE) continue;
      const paint = (value: string, x: number, y: number) => {
        // Same four one-pixel workspace shadows as the visible DOM legend.
        context.fillStyle =
          getComputedStyle(container)
            .getPropertyValue("--ui-workspace")
            .trim() || "#101518";
        for (const [dx, dy] of [
          [-1, 0],
          [1, 0],
          [0, -1],
          [0, 1],
        ])
          context.fillText(value, x + dx, y + dy);
        context.fillStyle = style.color;
        context.fillText(value, x, y);
      };
      if (style.whiteSpace === "nowrap") {
        const rowBox = element.getBoundingClientRect();
        const characters = Array.from(text.textContent ?? "");
        let value = characters.join("");
        if (
          element.scrollWidth > element.clientWidth &&
          style.textOverflow === "ellipsis"
        ) {
          while (
            characters.length &&
            context.measureText(characters.join("") + "…").width > rowBox.width
          )
            characters.pop();
          value = characters.join("") + "…";
        }
        const x = ["right", "end"].includes(style.textAlign)
          ? rowBox.right - context.measureText(value).width
          : rowBox.left;
        paint(
          value,
          x - origin.left,
          rowBox.top - origin.top + rowBox.height / 2,
        );
        continue;
      }
      let line = "",
        lineBox: DOMRect | null = null;
      const flush = () => {
        if (lineBox)
          paint(
            line,
            lineBox.left - origin.left,
            lineBox.top - origin.top + lineBox.height / 2,
          );
      };
      for (let i = 0; i < (text.textContent?.length ?? 0); i++) {
        const range = document.createRange();
        range.setStart(text, i);
        range.setEnd(text, i + 1);
        const rect = range.getBoundingClientRect();
        if (lineBox && Math.abs(rect.top - lineBox.top) > 1) {
          flush();
          line = "";
          lineBox = null;
        }
        if (!lineBox) lineBox = rect;
        line += text.textContent![i];
      }
      flush();
    }
    context.restore();
  }
}

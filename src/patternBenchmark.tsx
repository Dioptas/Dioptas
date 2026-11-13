/** Explicit experiment harness, loaded only by the isolated benchmark fixture. */
import React from "react";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import { PatternView } from "./PatternView";
import type { Pattern } from "./types";

type Sample = {
  cpuMs: number;
  renderer: string;
  xMin: number;
  xMax: number;
  uploads?: number;
  uploadBytes?: number;
};
const quantile = (values: number[], p: number) => {
  const sorted = [...values].sort((a, b) => a - b);
  return (
    sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] ?? 0
  );
};
const summary = (values: number[]) => ({
  median: quantile(values, 0.5),
  p95: quantile(values, 0.95),
  max: Math.max(0, ...values),
});
export function installPatternBenchmark(element: HTMLElement) {
  const root = createRoot(element);
  const nextFrame = () =>
    new Promise<number>((resolve) => requestAnimationFrame(resolve));
  const originals = import.meta.glob("./__CanvasBaseline.tsx");
  let Component: typeof PatternView = PatternView;
  const render = (props: Record<string, unknown>) =>
    flushSync(() => root.render(React.createElement(Component, props as any)));
  let active = false;
  // Synthetic benchmark drags follow the real navigation handler. Pointer
  // capture requires a trusted OS pointer; only this fixture substitutes it.
  const capture = HTMLCanvasElement.prototype.setPointerCapture;
  const release = HTMLCanvasElement.prototype.releasePointerCapture;
  const has = HTMLCanvasElement.prototype.hasPointerCapture;
  HTMLCanvasElement.prototype.setPointerCapture = function (id) {
    if (!active) capture.call(this, id);
  };
  HTMLCanvasElement.prototype.releasePointerCapture = function (id) {
    if (!active) release.call(this, id);
  };
  HTMLCanvasElement.prototype.hasPointerCapture = function (id) {
    return active ? false : has.call(this, id);
  };
  let lastProps: Record<string, unknown>;
  const makePattern = (points: number, phase = 0): Pattern => {
    const x = new Array<number>(points),
      y = new Array<number>(points);
    for (let i = 0; i < points; i++) {
      const t = i / (points - 1);
      x[i] = t * 100;
      y[i] =
        15 +
        2 * Math.sin(t * 33 + phase) +
        0.5 * Math.sin((t * points) / 12 + phase);
      for (const [center, amplitude, width] of [
        [0.19, 80, 0.0015],
        [0.35, 45, 0.003],
        [0.3515, 30, 0.0004],
        [0.63, 65, 0.002],
        [0.82, 35, 0.004],
      ])
        y[i] += amplitude * Math.exp(-(((t - center) / width) ** 2));
    }
    return { x, y, unit: "2th_deg" };
  };
  const api = {
    makePattern,
    render(props: Record<string, unknown>) {
      lastProps = props;
      render(props);
    },
    async run({
      backend = "webgl2",
      cases,
      frames = 90,
      caseName,
    }: {
      backend?: string;
      caseName?: string;
      cases?: {
        name: string;
        points: number;
        curves: number;
        pattern?: Pattern;
      }[];
      frames?: number;
    } = {}) {
      Component =
        backend === "original"
          ? ((await originals["./__CanvasBaseline.tsx"]()) as any).PatternView
          : PatternView;
      const results = [];
      const configurations = cases ?? [
        { name: "normal", points: 2000, curves: 1 },
        { name: "many-overlays", points: 4000, curves: 20 },
        { name: "dense", points: 100000, curves: 1 },
        { name: "dense-overlays", points: 100000, curves: 8 },
        { name: "million", points: 1000000, curves: 1 },
      ];
      const frameIntervals = [];
      let previous = await nextFrame();
      for (let i = 0; i < 20; i++) {
        const now = await nextFrame();
        frameIntervals.push(now - previous);
        previous = now;
      }
      const refreshMs = quantile(frameIntervals, 0.5);
      for (const configuration of configurations.filter(
        (c) => !caseName || c.name === caseName,
      )) {
        const pattern =
          configuration.pattern ?? makePattern(configuration.points);
        const colors = ["#55c8f5", "#ee8f4c", "#70d893", "#d97bed", "#e5d275"];
        const curves = Array.from(
          { length: configuration.curves - 1 },
          (_, i) => ({
            ...makePattern(configuration.points, i * 0.3),
            color: colors[i % colors.length],
            name: `Overlay ${i + 1}`,
            selected: i === configuration.curves - 2,
          }),
        );
        let samples: Sample[] = [];
        let mountSamples: Sample[] = [];
        let mounting = true;
        let submissions: number[] = [];
        let inputTime = 0;
        let collect = false;
        lastProps = {
          pattern,
          curves,
          curveRenderer: backend,
          log: false,
          onRender: (sample: Sample) => {
            if (mounting) mountSamples.push(sample);
            if (collect) {
              samples.push(sample);
              submissions.push(performance.now() - inputTime);
            }
          },
        };
        const mounted = performance.now();
        render(lastProps);
        for (let i = 0; i < 8; i++) await nextFrame();
        const mountMs = performance.now() - mounted;
        mounting = false;
        const canvas = element.querySelector(
          '[data-testid="pattern-canvas"]',
        ) as HTMLCanvasElement;
        const box = canvas.getBoundingClientRect();
        const cx =
          box.x +
          Number(canvas.dataset.plotLeft) +
          Number(canvas.dataset.plotWidth) * 0.5;
        const cy =
          box.y +
          Number(canvas.dataset.plotTop) +
          Number(canvas.dataset.plotHeight) * 0.5;
        for (const interaction of ["pan-wide", "pan-zoomed", "wheel"]) {
          // Each sequence starts from the identical full view.
          render({ ...lastProps, key: interaction });
          for (let i = 0; i < 6; i++) await nextFrame();
          const plot = element.querySelector(
            '[data-testid="pattern-canvas"]',
          ) as HTMLCanvasElement;
          if (interaction === "pan-zoomed") {
            flushSync(() =>
              plot.dispatchEvent(
                new WheelEvent("wheel", {
                  clientX: cx,
                  clientY: cy,
                  deltaY: -1535,
                  bubbles: true,
                  cancelable: true,
                }),
              ),
            );
            for (let i = 0; i < 3; i++) await nextFrame();
          }
          active = true;
          if (interaction.startsWith("pan"))
            flushSync(() =>
              plot.dispatchEvent(
                new PointerEvent("pointerdown", {
                  clientX: cx,
                  clientY: cy,
                  button: 2,
                  buttons: 2,
                  pointerId: 1,
                  bubbles: true,
                  cancelable: true,
                }),
              ),
            );
          samples = [];
          submissions = [];
          collect = true;
          const intervals: number[] = [];
          let lastTime = await nextFrame();
          for (let i = 0; i < frames; i++) {
            const now = await nextFrame();
            if (i >= 10) intervals.push(now - lastTime);
            lastTime = now;
            inputTime = performance.now();
            flushSync(() =>
              plot.dispatchEvent(
                interaction === "wheel"
                  ? new WheelEvent("wheel", {
                      clientX: cx,
                      clientY: cy,
                      deltaY: i < frames / 2 ? -18 : 18,
                      bubbles: true,
                      cancelable: true,
                    })
                  : new PointerEvent("pointermove", {
                      clientX: cx + Math.sin((i / frames) * Math.PI * 2) * 90,
                      clientY: cy + Math.cos((i / frames) * Math.PI * 2) * 30,
                      button: 2,
                      buttons: 2,
                      pointerId: 1,
                      bubbles: true,
                      cancelable: true,
                    }),
              ),
            );
          }
          await nextFrame();
          collect = false;
          if (interaction.startsWith("pan"))
            flushSync(() =>
              plot.dispatchEvent(
                new PointerEvent("pointerup", {
                  clientX: cx,
                  clientY: cy,
                  button: 2,
                  buttons: 0,
                  pointerId: 1,
                  bubbles: true,
                  cancelable: true,
                }),
              ),
            );
          active = false;
          const measured = samples.slice(10);
          const result = {
            case: configuration.name,
            points: pattern.x.length,
            curves: configuration.curves,
            interaction,
            requested: backend,
            actual: plot.dataset.curveRenderer ?? "canvas2d",
            mountMs,
            initialDrawCpuMs: summary(mountSamples.map((s) => s.cpuMs)),
            refreshMs,
            drawCpuMs: summary(measured.map((s) => s.cpuMs)),
            inputToSubmissionMs: summary(submissions.slice(10)),
            frameIntervalMs: summary(intervals),
            missedFramePercent:
              (100 * intervals.filter((t) => t > refreshMs * 1.5).length) /
              intervals.length,
            drawn: measured.length,
            navigationUploads:
              (measured.at(-1)?.uploads ?? 0) - (measured[0]?.uploads ?? 0),
            retainedVertexBytes: measured.at(-1)?.uploadBytes ?? 0,
          };
          if (backend === "webgl2" && result.actual !== "webgl2")
            throw Error("WebGL benchmark silently used Canvas fallback");
          results.push(result);
          (window as any).__patternBenchmarkProgress?.(result);
        }
      }
      const gpuCanvas = element.querySelector(
        '[data-testid="pattern-gpu"]',
      ) as HTMLCanvasElement | null;
      const gl = backend === "webgl2" ? gpuCanvas?.getContext("webgl2") : null;
      const debug = gl?.getExtension("WEBGL_debug_renderer_info");
      return {
        gpu: gl
          ? {
              renderer: debug
                ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)
                : gl.getParameter(gl.RENDERER),
              version: gl.getParameter(gl.VERSION),
            }
          : null,
        userAgent: navigator.userAgent,
        dpr: devicePixelRatio,
        viewport: { width: element.clientWidth, height: element.clientHeight },
        note: "CPU draw/submission time excludes asynchronous GPU completion. rAF intervals measure scheduling cadence, not physical display latency. No gl.finish/readPixels in timed interactions.",
        results,
      };
    },
  };
  (window as any).__patternBenchmark = api;
  return api;
}

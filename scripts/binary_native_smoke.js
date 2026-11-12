// Measure the real Python -> Rust -> WKWebView path and the UI render cache.
window.__dioptasBinaryNativeSmoke = async ({
  call,
  click,
  ready,
  delay,
  check,
  root,
}) => {
  const first = await call("open_image", {
    path: root + "/tests/data/image_001.tif",
  });
  // Preserve this exact geometry, mask and integration state for the Qt
  // comparison, without changing any scientific inputs for the benchmark.
  const comparisonProject = root + "/artifacts/qt-comparison.dio";
  const saved = await call("save_project", { path: comparisonProject });
  check(saved.ok, "Could not save the matched Qt benchmark project");
  const second = await call("next_image", { direction: 1 });
  const warm = await call("next_image", { direction: -1 });
  check(
    first.image.width === 2048 &&
      first.image.height === 2048 &&
      first.image.step === 1,
    "Binary transfer reduced detector resolution",
  );
  check(
    first.image.data instanceof ArrayBuffer &&
      first.image.data.byteLength === 2048 * 2048 * 4,
    "Full detector pixels did not cross the native binary bridge",
  );
  check(
    first.mask.data === second.mask.data,
    "Unchanged mask was transferred/decoded again",
  );
  check(
    first.image.data === warm.image.data,
    "Returning to image_001 did not reuse its buffer",
  );
  check(
    warm.binaryTransfer.bufferBytes === 0,
    "Cached arrays were resent over native IPC",
  );
  const times = [];
  for (const direction of [1, -1, 1, -1, 1, -1, 1, -1]) {
    const start = performance.now();
    const response = await call("next_image", { direction });
    times.push(performance.now() - start);
    check(
      response.binaryTransfer.bufferBytes === 0,
      "Warm file stepping resent binary arrays",
    );
  }
  click("Calibration");
  await delay();
  const setup = document.querySelector('[aria-label="Step 1: Image & setup"]');
  check(setup, "Image/setup toolbar missing");
  setup.click();
  await delay();
  await ready();
  const spinFree = () => !document.querySelector(".spin");
  const waitPaint = (name) =>
    new Promise((resolve, reject) => {
      const start = performance.now();
      const checkFrame = () => {
        if (performance.now() - start > 15000)
          return reject(Error("Image navigation did not finish"));
        if (spinFree() && document.title === `${name} — Dioptas`)
          requestAnimationFrame(() => requestAnimationFrame(resolve));
        else requestAnimationFrame(checkFrame);
      };
      requestAnimationFrame(checkFrame);
    });
  const step = async (direction) => {
    await ready();
    const name = direction === 1 ? "image_002.tif" : "image_001.tif";
    const start = performance.now();
    click(direction === 1 ? "Next image" : "Previous image");
    await waitPaint(name);
    return performance.now() - start;
  };
  // Warm both rendered images with their actual independent display limits.
  await step(1);
  await step(-1);
  let colourMaps = 0;
  const create = CanvasRenderingContext2D.prototype.createImageData;
  CanvasRenderingContext2D.prototype.createImageData = function (...args) {
    if (args[0] === 2048 && args[1] === 2048) colourMaps++;
    return create.apply(this, args);
  };
  const uiTimes = [];
  try {
    for (const d of [1, -1, 1, -1, 1, -1, 1, -1]) uiTimes.push(await step(d));
  } finally {
    CanvasRenderingContext2D.prototype.createImageData = create;
  }
  check(
    colourMaps === 0,
    "Warm image stepping recoloured all detector pixels again",
  );
  await ready();
  return {
    comparisonProject,
    windowSize: [innerWidth, innerHeight],
    devicePixelRatio,
    integrationSettings: {
      bins: first.state.bins,
      unit: first.state.unit,
      geometry: first.state.geometry,
      integration: first.state.integration,
    },
    firstTransferBytes: first.binaryTransfer.bytes,
    warmTransferBytes: warm.binaryTransfer.bytes,
    warmTransferredPixelBytes: warm.binaryTransfer.bufferBytes,
    roundTripMs: times,
    uiSwitchMs: uiTimes,
    warmDetectorColourMaps: colourMaps,
    fullResolution: [2048, 2048],
  };
};

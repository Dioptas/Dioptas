// Loaded only in the native test window, before the shared calibration smoke.
window.__dioptasMaskNativeSmoke = async ({
  call,
  click,
  input,
  ready,
  delay,
  check,
}) => {
  click("Mask");
  await delay();
  const canvas = document.querySelector('[data-testid="detector-canvas"]');
  canvas.setPointerCapture = canvas.releasePointerCapture = () => {};
  const point = async (x, y) => {
    const box = canvas.getBoundingClientRect(),
      d = canvas.dataset;
    const clientX =
      box.x +
      +d.plotLeft +
      ((x - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) * +d.plotWidth;
    const clientY =
      box.y +
      +d.plotTop +
      ((+d.viewYMax - y) / (+d.viewYMax - +d.viewYMin)) * +d.plotHeight;
    for (const type of ["pointerdown", "pointerup"])
      canvas.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          pointerId: 1,
          button: 0,
          buttons: type === "pointerdown" ? 1 : 0,
          clientX,
          clientY,
        }),
      );
    await delay();
    await ready();
  };
  click("Rectangle");
  await delay();
  await point(101.2, 201.2);
  await point(161.2, 251.2);
  let current = await call("state");
  check(
    current.state.maskedPixels === 3000,
    "Native rectangle lost source coordinates",
  );
  const baseline = current.mask.data;
  click("Undo");
  await delay();
  await ready();
  check(
    (await call("state")).state.maskedPixels === 0,
    "Native mask undo failed",
  );
  click("Redo");
  await delay();
  await ready();
  check(
    (await call("state")).mask.data === baseline,
    "Native mask redo failed",
  );
  const fixture = current.state.imagePath;
  const root = fixture.slice(0, fixture.lastIndexOf("/desktop/tests/data/"));
  const path = root + "/desktop/artifacts/native-mask.npy";
  const saved = await call("mask_file", { path, save: true, flipud: true });
  check(saved.ok, "Native pipe could not save mask");
  click("Clear");
  await delay();
  await ready();
  const loaded = await call("mask_file", { path, flipud: true });
  check(
    loaded.ok && loaded.mask.data === baseline,
    "Native mask file roundtrip failed",
  );
  click("Invert");
  await delay();
  await ready();
  check(
    (await call("state")).state.maskedPixels === 981 * 1043 - 3000,
    "Native invert failed",
  );
  click("Clear");
  await delay();
  await ready();
  click("Circle");
  await delay();
  await point(300.2, 400.2);
  await point(330.2, 440.4);
  const circlePixels = (await call("state")).state.maskedPixels;
  check(
    circlePixels > 7800 && circlePixels < 8000,
    "Native circle must use the first click as center and pointer distance as radius",
  );
  click("Clear");
  await delay();
  await ready();
  input("Above threshold counts", "1000");
  await delay();
  click("Above Thresh");
  await delay();
  await ready();
  check(
    (await call("state")).state.maskedPixels > 0,
    "Native threshold failed",
  );
  const checkbox = document.querySelector(
    ".mask-controls input[type=checkbox]",
  );
  check(checkbox, "Native plugins are missing");
  click("Clear");
  await delay();
  await ready();
  click("Calibration");
  await delay();
  await ready();
  for (
    let i = 0;
    i < 100 && !document.querySelector('[data-testid="cake-canvas"]');
    i++
  )
    await delay();
  check(
    document.querySelector('[data-testid="cake-canvas"]'),
    "Returning from Mask lost calibration validation",
  );
  return {
    sourceRectangle: true,
    undoRedo: true,
    fileRoundtrip: true,
    threshold: true,
    calibrationPreserved: true,
  };
};

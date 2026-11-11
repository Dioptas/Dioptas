import assert from "node:assert/strict";

/** Exercise the outer shared axis and resize handle as a user would. */
export async function checkCakeProfileInteraction(page, profile, cake, ready) {
  const view = async (canvas) =>
    canvas.evaluate((el) => ({
      xMin: +el.dataset.viewXMin,
      xMax: +el.dataset.viewXMax,
      yMin: +el.dataset.viewYMin,
      yMax: +el.dataset.viewYMax,
    }));
  const geometry = async (canvas) =>
    canvas.evaluate((el) => {
      const r = el.getBoundingClientRect(),
        d = el.dataset;
      return {
        x: r.x,
        y: r.y,
        width: r.width,
        left: +d.plotLeft,
        top: +d.plotTop,
        w: +d.plotWidth,
        h: +d.plotHeight,
      };
    });
  const shared = async () => {
    const a = await view(profile),
      b = await view(cake);
    assert.equal(a.yMin, b.yMin);
    assert.equal(a.yMax, b.yMax);
  };
  const resize = page.getByRole("separator", {
    name: "Profile and cake divider",
    exact: true,
  });
  await resize.waitFor();
  assert.equal(await cake.getAttribute("data-shows-azimuth-axis"), "false");
  assert.ok(
    (await geometry(profile)).left >= 60,
    "The shared azimuth axis is at the far left",
  );
  assert.equal((await geometry(cake)).left, 8, "No duplicate cake y axis");
  const before = { profile: await view(profile), cake: await view(cake) };
  const initial = (await geometry(profile)).width;
  await resize.focus();
  await resize.press("ArrowRight");
  await ready();
  assert.ok((await geometry(profile)).width > initial + 5);
  const box = await resize.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 50, box.y + box.height / 2, {
    steps: 8,
  });
  await page.mouse.up();
  await ready();
  const widened = (await geometry(profile)).width;
  assert.ok(widened > initial + 35, "Dragging widens the profile");
  assert.deepEqual(
    { profile: await view(profile), cake: await view(cake) },
    before,
    "Resize preserves the scientific viewport",
  );
  const stored = await page.evaluate(() =>
    Number(localStorage.getItem("dioptas-layout:cake-profile-width")),
  );
  assert.ok(Math.abs(stored - widened) < 1.1, "Width preference persists");
  await resize.dblclick();
  await ready();
  assert.ok(
    (await geometry(profile)).width < widened - 15,
    "Double-click resets width",
  );
  await shared();
  const fit = async () => {
    await cake.press("f");
    await profile.press("f");
    await ready();
  };
  const dragAxis = async (destination, returnToProfile = false) => {
    const p = await geometry(profile),
      c = await geometry(cake);
    await page.mouse.move(p.x + p.left - 12, p.y + p.top + p.h * 0.2);
    await page.mouse.down();
    if (destination === "cake")
      await page.mouse.move(c.x + c.left + c.w * 0.6, c.y + c.top + c.h * 0.7, {
        steps: 20,
      });
    if (destination === "profile" || returnToProfile)
      await page.mouse.move(
        p.x + p.left + p.w * 0.75,
        p.y + p.top + p.h * 0.7,
        { steps: 20 },
      );
    await page.mouse.up();
    await ready();
    await shared();
  };
  await fit();
  const full = await view(cake);
  await dragAxis("profile");
  assert.ok((await view(profile)).yMax < full.yMax);
  assert.equal(
    (await view(cake)).xMax,
    full.xMax,
    "Axis drag into profile retains cake radial range",
  );
  await fit();
  await dragAxis("cake");
  assert.ok(
    (await view(cake)).xMax < full.xMax,
    "Axis drag across divider zooms cake",
  );
  assert.ok((await view(cake)).yMax < full.yMax);
  await fit();
  await dragAxis("cake", true);
  assert.equal(
    (await view(cake)).xMax,
    full.xMax,
    "Returning to profile selects its interval",
  );
  assert.ok((await view(profile)).yMax < full.yMax);
  await fit();
}

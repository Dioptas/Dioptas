// Runs only in the disposable --detector-smoke application.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke,
    call = window.__dioptasNativeCall;
  const delay = (ms = 60) => new Promise((r) => setTimeout(r, ms));
  const check = (v, m) => {
    if (!v) throw Error(m);
  };
  const wait = async (predicate) => {
    for (let i = 0; i < 700; i++) {
      if (await predicate()) return;
      await delay();
    }
    throw Error("Detector native test timed out: " + document.body.innerText);
  };
  const click = (label) => {
    const b = [...document.querySelectorAll("button")].find(
      (b) =>
        b.getAttribute("aria-label") === label ||
        b.textContent.trim() === label,
    );
    check(b && !b.disabled, "Missing/disabled " + label);
    b.click();
  };
  const reports = [];
  let listener;
  try {
    const resumed = JSON.parse(
      sessionStorage.getItem("detector-native-resume") || "null",
    );
    if (resumed) {
      await wait(
        () =>
          document.querySelector('[data-detached="true"]') &&
          !document.querySelector(".spin"),
      );
      const host = await call("__host__"),
        state = await call("state");
      check(
        host.pid === resumed.processingPid,
        "Frontend reload replaced the processing owner",
      );
      check(
        state.image.bufferId === resumed.imageId,
        "Frontend reload lost detector pixels",
      );
      await invoke("open_detector_window");
      const windows = await invoke("plugin:window|get_all_windows");
      check(
        windows.filter(
          (w) => w === "detector-window" || w.label === "detector-window",
        ).length === 1,
        "Frontend reload duplicated the detector",
      );
      await invoke("native_smoke_report", {
        report: {
          ok: true,
          stage: "detector",
          processingPid: host.pid,
          reports: resumed.reports,
          windowReuse: true,
          closeRedocks: true,
          placementRestore: true,
          oneProcessor: true,
          frontendReconnect: true,
        },
      });
      return;
    }
    await wait(
      () =>
        document.querySelector('[data-testid="detector-canvas"]') &&
        !document.querySelector(".spin"),
    );
    const host = await call("__host__"),
      before = await call("state");
    check(host.runtime === "rust", "Wrong processor runtime");
    const callback = window.__TAURI_INTERNALS__.transformCallback((event) =>
      reports.push(event.payload),
    );
    listener = await invoke("plugin:event|listen", {
      event: "detector-native-test",
      target: { kind: "Any" },
      handler: callback,
    });
    click("Undock detector image");
    await wait(() => reports.length === 1);
    check(reports[0].ok, reports[0].error);
    // Reopening raises/unminimizes exactly the existing window.
    await invoke("open_detector_window");
    const windows = await invoke("plugin:window|get_all_windows");
    check(
      windows.filter(
        (w) => w === "detector-window" || w.label === "detector-window",
      ).length === 1,
      "Detector was duplicated: " + JSON.stringify(windows),
    );
    await invoke("close_detector_window");
    await wait(() => document.querySelector('[data-testid="detector-canvas"]'));
    click("Undock detector image");
    await wait(() => reports.length === 2);
    check(reports[1].ok, reports[1].error);
    const first = reports[0].placed,
      second = reports[1].initial;
    check(
      Math.abs(first.width - second.width) < 2 &&
        Math.abs(first.height - second.height) < 2 &&
        Math.abs(first.position.x - second.position.x) < 3 &&
        Math.abs(first.position.y - second.position.y) < 3,
      "Placement not retained: " + JSON.stringify({ first, second }),
    );
    // The child's actual OS close is used in the second opening.
    await wait(() => document.querySelector('[data-testid="detector-canvas"]'));
    const after = await call("state"),
      hostAfter = await call("__host__");
    check(
      after.state.imagePath === before.state.imagePath &&
        after.image.bufferId === before.image.bufferId,
      "Closing lost detector pixels",
    );
    check(
      hostAfter.pid === host.pid,
      "Detector created/replaced the scientific owner",
    );
    click("Undock detector image");
    await wait(() => reports.length === 3);
    check(reports[2].ok, reports[2].error);
    sessionStorage.setItem(
      "detector-native-resume",
      JSON.stringify({
        processingPid: host.pid,
        imageId: before.image.bufferId,
        reports,
      }),
    );
    location.reload();
  } catch (error) {
    await invoke("native_smoke_report", {
      report: { ok: false, stage: "detector", error: String(error), reports },
    });
  }
})();

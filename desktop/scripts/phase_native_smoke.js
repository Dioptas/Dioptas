// Loaded only in our explicitly launched bundled smoke window.
window.__dioptasPhaseNativeSmoke = async ({
  call,
  click,
  ready,
  delay,
  check,
  root,
}) => {
  click("Phase");
  await delay();
  await ready();
  const controls = document.querySelector('[data-testid="phase-controls"]');
  check(controls && !controls.hidden, "Native Phase controls did not mount");
  for (const name of ["P step", "T Step", "Phase 1 pressure (GPa)"])
    check(
      controls.querySelector(`input[aria-label="${name}"]`),
      `Native Phase input missing: ${name}`,
    );
  const step = controls.querySelector('input[aria-label="P step"]');
  step.dispatchEvent(
    new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }),
  );
  await delay();
  check(step.value === "2", "Qt multiplicative P-step 1 → 2 failed");
  const pressure = controls.querySelector(
    'input[aria-label="Phase 1 pressure (GPa)"]',
  );
  pressure.dispatchEvent(
    new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }),
  );
  await delay();
  await ready();
  let state = await call("state");
  check(
    state.state.integration.phases[0].pressure === 2,
    "Native phase pressure step did not reach PhaseModel",
  );
  pressure.dispatchEvent(
    new WheelEvent("wheel", { deltaY: -100, bubbles: true, cancelable: true }),
  );
  await delay();
  await ready();
  state = await call("state");
  check(
    state.state.integration.phases[0].pressure === 4,
    "Native phase-table wheel failed",
  );
  pressure.dispatchEvent(
    new WheelEvent("wheel", { deltaY: 100, bubbles: true, cancelable: true }),
  );
  await delay();
  await ready();
  click("Pattern");
  await delay();
  click("Phase");
  await delay();
  check(
    document.querySelector('input[aria-label="P step"]').value === "2",
    "P step was lost on tab change",
  );
  const selected = controls.querySelector('tbody tr[aria-selected="true"]');
  check(selected, "No phase selected in native table");
  const editorComplete = new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(Error("Native detached editor did not report")),
      45000,
    );
    window.addEventListener(
      "phase-editor-smoke",
      (e) => {
        clearTimeout(timer);
        resolve(e.detail);
      },
      { once: true },
    );
  });
  let sawOpening = false,
    watchingEdits = false,
    previewFlickered = false;
  const observer = new MutationObserver(() => {
    const busy = !!document.querySelector(".spin");
    if (!watchingEdits) {
      if (busy) sawOpening = true;
      else if (sawOpening) watchingEdits = true;
    } else if (busy) previewFlickered = true;
  });
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
  });
  click("Edit selected Phase");
  const editorReport = await editorComplete;
  observer.disconnect();
  check(
    !previewFlickered,
    "Editor live updates repeatedly disabled/re-enabled the main GUI",
  );
  check(editorReport.ok, editorReport.error || "Native editor failed");
  check(
    !document.querySelector('dialog[aria-label="Phase Editor"]'),
    "The native editor still blocks the main workspace",
  );
  await ready();
  for (
    let i = 0;
    i < 100 &&
    !controls.querySelector(".phase-name")?.textContent.includes("*");
    i++
  )
    await delay(20);
  check(
    controls.querySelector(".phase-name")?.textContent.includes("*"),
    "The main phase table did not refresh after an editor change",
  );
  const editor = await call("integration_phase_editor", { index: 0 });
  check(
    editor.phaseEditor.lattice.a0 === 4.2,
    "Detached lattice edit did not reach the shared model",
  );
  check(
    editor.phaseEditor.reflections[0].intensity === 66.0396789,
    "Display rounding changed the scientific intensity",
  );
  await call("integration_phase", { operation: "reload", index: 0 });
  const saved = await call("integration_phase_list", {
    save: true,
    path: root + "/desktop/artifacts/native-phase-list.txt",
  });
  check(saved.ok, saved.error || "Native phase-list save failed");
  const loaded = await call("integration_phase_list", {
    path: root + "/desktop/artifacts/native-phase-list.txt",
  });
  check(
    loaded.ok && loaded.state.integration.phases.length === 2,
    loaded.error || "Native phase-list append failed",
  );
  // Return a snapshot through a visible UI operation.
  click("Pattern unit 2θ");
  await delay();
  await ready();
  click("Browse EoS Material Database");
  await delay();
  await ready();
  for (
    let attempt = 0;
    attempt < 100 &&
    !document.querySelector('dialog[aria-label="EoS Material Database"][open]');
    attempt++
  )
    await delay(20);
  check(
    document.querySelector('dialog[aria-label="EoS Material Database"][open]'),
    "Native EoS database did not open",
  );
  check(
    document.querySelectorAll('table[aria-label="Database materials"] tbody tr')
      .length > 0,
    "Native database has no real materials",
  );
  const databaseExplorer = await window.__dioptasDatabaseNativeSmoke({
    call,
    click,
    ready,
    delay,
    check,
  });
  click("Close EoS Material Database");
  await delay();
  return {
    qtTable: true,
    multiplicativeSteps: true,
    tabPersistence: true,
    realPressure: true,
    wheelStepping: true,
    latticeEditing: true,
    editorThermalConstructor: true,
    editorNumericValidation: true,
    editorReflections: true,
    editorDetached: editorReport,
    livePreviewStable: !previewFlickered,

    phaseList: true,
    database: true,
    databaseExplorer,
  };
};

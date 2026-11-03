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
  click("Edit selected Phase");
  await delay();
  await ready();
  check(
    document.querySelector('dialog[aria-label="Phase Editor"][open]'),
    "Native phase editor did not open",
  );
  const a = document.querySelector('input[aria-label="a₀"]');
  check(a && !a.disabled, "Legacy phase lattice should be editable");
  a.dispatchEvent(
    new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }),
  );
  await delay();
  await ready();
  const editor = await call("integration_phase_editor", { index: 0 });
  check(
    editor.ok && editor.phaseEditor.lattice.a0 > 4.078,
    "Native lattice edit did not reach PhaseModel",
  );
  // Exercise the editor's actual WKWebView inputs and constructor controls.
  const editorIdle = async () => {
    for (let attempt = 0; attempt < 500; attempt++) {
      await delay(20);
      await ready();
      const status =
        document.querySelector('.pe-dialog footer [role="status"]')
          ?.textContent || "";
      if (
        !document.querySelector('.pe-dialog input[aria-busy="true"]') &&
        !status.includes("Applying edit")
      )
        return;
    }
    throw Error("Native editor edit did not settle");
  };
  const setInput = async (label, value) => {
    const field = document.querySelector(`input[aria-label="${label}"]`);
    check(field, `Native editor field missing: ${label}`);
    field.focus();
    await delay();
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    ).set.call(field, String(value));
    field.dispatchEvent(new Event("input", { bubbles: true }));
    await delay();
    field.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        bubbles: true,
        cancelable: true,
      }),
    );
    await editorIdle();
  };
  const choose = async (label, value) => {
    const field = document.querySelector(`select[aria-label="${label}"]`);
    check(field, `Native editor selector missing: ${label}`);
    field.focus();
    field.value = value;
    field.dispatchEvent(new Event("change", { bubbles: true }));
    await editorIdle();
  };
  await setInput("a₀", "invalid");
  check(
    a.getAttribute("aria-invalid") === "true",
    "Native invalid lattice input was not identified",
  );
  a.dispatchEvent(
    new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    }),
  );
  await delay();
  check(
    document.querySelector('dialog[aria-label="Phase Editor"][open]'),
    "Escape in a draft closed the editor",
  );
  click("Equation of state");
  await delay();
  await choose("Thermal model", "MieGruneisenDebye");
  await setInput("theta0", 650);
  const thermalEditor = await call("integration_phase_editor", { index: 0 });
  check(
    thermalEditor.phaseEditor.thermalFields.find((f) => f.key === "theta0")
      .value === 650,
    "Native thermal constructor edit did not reach PhaseModel: " +
      JSON.stringify({
        fields: thermalEditor.phaseEditor.thermalFields,
        input: document.querySelector('input[aria-label="theta0"]')?.value,
        message: document.querySelector(".pe-dialog footer")?.textContent,
      }),
  );
  click("Volume & structure");
  await delay();
  await setInput("Reflection 1 intensity", 3);
  const reflectionEditor = await call("integration_phase_editor", { index: 0 });
  check(
    reflectionEditor.phaseEditor.reflections[0].intensity === 3,
    "Native reflection edit was lost",
  );
  const bounds = document
    .querySelector('dialog[aria-label="Phase Editor"]')
    .getBoundingClientRect();
  check(
    bounds.left >= 0 &&
      bounds.right <= innerWidth &&
      bounds.bottom <= innerHeight,
    "Native phase editor exceeds its viewport",
  );
  click("Reload File");
  await delay();
  await ready();
  click("Close Phase Editor");
  await delay();
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
    document.querySelectorAll(".phase-materials-scroll tbody tr").length > 0,
    "Native database has no real materials",
  );
  click("Close EoS Material Database");
  await delay();
  return {
    qtTable: true,
    multiplicativeSteps: true,
    tabPersistence: true,
    realPressure: true,
    latticeEditing: true,
    editorThermalConstructor: true,
    editorNumericValidation: true,
    editorReflections: true,
    phaseList: true,
    database: true,
  };
};

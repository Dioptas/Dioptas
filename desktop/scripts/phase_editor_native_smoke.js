// Injected exclusively in the detached child of our --smoke native process.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  const delay = (ms = 30) => new Promise((resolve) => setTimeout(resolve, ms));
  const check = (ok, text) => {
    if (!ok) throw Error(text);
  };
  const wait = async (predicate) => {
    for (let i = 0; i < 1000; i++) {
      if (predicate()) return;
      await delay();
    }
    throw Error("Detached editor did not settle: " + document.body.innerText);
  };
  const idle = async () => {
    await delay();
    await wait(
      () =>
        !document.querySelector('input[aria-busy="true"]') &&
        !document
          .querySelector('footer [role="status"]')
          ?.textContent.includes("Applying edit"),
    );
  };
  const click = async (text) => {
    const button = [...document.querySelectorAll("button")].find(
      (b) =>
        b.textContent.trim() === text || b.getAttribute("aria-label") === text,
    );
    check(button && !button.disabled, "Missing editor button: " + text);
    button.click();
    await idle();
  };
  const set = async (label, value) => {
    const field = document.querySelector(`input[aria-label="${label}"]`);
    check(field, "Missing detached input: " + label);
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
    await idle();
    return field;
  };
  const choose = async (label, value) => {
    const field = document.querySelector(`select[aria-label="${label}"]`);
    check(field && !field.disabled, "Missing detached selector: " + label);
    field.value = value;
    field.dispatchEvent(new Event("change", { bubbles: true }));
    await idle();
  };
  let report;
  try {
    await wait(() =>
      document.querySelector('.pe-native input[aria-label="a₀"]'),
    );
    check(
      !document.querySelector("dialog"),
      "Detached editor is a modal dialog",
    );
    check(
      !document.querySelector(
        '.pe-native > header, .pe-native button[aria-label="Close Phase Editor"]',
      ),
      "Native editor still has a redundant close header",
    );
    check(
      await invoke("plugin:window|is_decorated", { label: "phase-editor" }),
      "No native title bar",
    );
    const position = await invoke("plugin:window|outer_position", {
      label: "phase-editor",
    });
    await invoke("plugin:window|set_position", {
      label: "phase-editor",
      value: { Physical: { x: position.x + 80, y: position.y + 30 } },
    });
    const moved = await invoke("plugin:window|outer_position", {
      label: "phase-editor",
    });
    check(
      moved.x !== position.x,
      "The editor window did not move independently",
    );
    await invoke("plugin:window|set_size", {
      label: "phase-editor",
      value: { Logical: { width: 1000, height: 480 } },
    });
    const field = await set("a₀", "invalid");
    check(
      field.getAttribute("aria-invalid") === "true",
      "Missing numeric validation",
    );
    field.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Escape",
        bubbles: true,
        cancelable: true,
      }),
    );
    await idle();
    check(
      document.querySelector(".pe-native"),
      "Draft Escape closed the native editor",
    );
    await set("a₀", 4.2);
    await set("Lattice length step", 0.02);
    await click("Increase a₀");
    check(
      document.querySelector('input[aria-label="a₀"]').value === "4.22",
      "Native lattice step did not use the length increment",
    );
    await click("Decrease a₀");
    check(
      document.querySelector('input[aria-label="a₀"]').value === "4.2",
      "Native lattice decrement failed",
    );
    const latticeField = document.querySelector('input[aria-label="a₀"]');
    latticeField.dispatchEvent(
      new WheelEvent("wheel", {
        deltaY: -100,
        bubbles: true,
        cancelable: true,
      }),
    );
    await idle();
    check(latticeField.value === "4.22", "Native lattice wheel failed");
    latticeField.dispatchEvent(
      new WheelEvent("wheel", { deltaY: 100, bubbles: true, cancelable: true }),
    );
    await idle();
    check(
      latticeField.value === "4.2",
      "Native lattice wheel decrement failed",
    );
    const intensity = await set("Reflection 1 intensity", 66.0396789);
    intensity.blur();
    await idle();
    check(
      intensity.value === "66.04",
      "Intensity is not displayed to four significant digits",
    );
    intensity.focus();
    await delay();
    check(
      intensity.value === "66.0396789",
      "Editing lost full scientific precision",
    );
    intensity.blur();
    const index = document
      .querySelector(".pe-index-cell input")
      .getBoundingClientRect();
    check(index.width <= 45, "Miller index input is too wide");
    const volume = document.querySelector(".pe-parameter-scroll:not([hidden])");
    check(
      volume.scrollHeight > volume.clientHeight &&
        volume.offsetWidth - volume.clientWidth >= 10,
      "Volume scrollbar is not persistent",
    );
    const target = new URLSearchParams(location.search).get("phase_uid");
    const original = await window.__dioptasNativeCall(
      "integration_phase_editor",
      { editor_uid: target },
    );
    const root = original.phaseEditor.filename.split("/dioptas/tests/")[0];
    check(
      root && root !== original.phaseEditor.filename,
      "Unexpected native fixture path",
    );
    await set("Material name", "Native saved material");
    const firstSave = await window.__dioptasNativeCall(
      "integration_phase_export",
      {
        editor_uid: target,
        format: "eosmat",
        path: root + "/desktop/artifacts/native-editor-material.eosmat",
      },
    );
    check(firstSave.ok, firstSave.error || "Native material save failed");
    await invoke("plugin:event|emit", {
      event: "phase-editor-changed",
      payload: {},
    });
    await wait(() =>
      document
        .querySelector('input[aria-label="Material file"]')
        ?.value.endsWith("/native-editor-material.eosmat"),
    );
    await set("Material name", "Renamed native material");
    await click("Save");
    const saved = await window.__dioptasNativeCall("integration_phase_editor", {
      editor_uid: target,
    });
    check(
      saved.phaseEditor.materialName === "Renamed native material" &&
        !saved.phaseEditor.modified &&
        saved.phaseEditor.canSaveCurrent,
      "Native Save did not retain the material name/file association",
    );
    await click("Equation of state");
    document.querySelector(".pe-record-tools").open = true;
    await click("Add record");
    await click("Duplicate as custom");
    const recordsBefore = (
      await window.__dioptasNativeCall("integration_phase_editor", {
        editor_uid: target,
      })
    ).phaseEditor.references.length;
    await click("Delete record…");
    const confirmation = document.querySelector(
      'dialog[aria-label="Delete EoS record?"]',
    );
    check(confirmation?.open, "Native record confirmation did not open");
    const anchor = [...document.querySelectorAll("button")]
      .find((b) => b.textContent.trim() === "Delete record…")
      .getBoundingClientRect();
    const popup = confirmation.getBoundingClientRect();
    check(
      Math.min(
        Math.abs(popup.top - anchor.bottom),
        Math.abs(anchor.top - popup.bottom),
      ) <= 8,
      "Native confirmation was not beside Delete record",
    );
    await click("Confirm delete");
    await click("Save");
    const afterDelete = await window.__dioptasNativeCall(
      "integration_phase_editor",
      { editor_uid: target },
    );
    check(
      afterDelete.phaseEditor.references.length === recordsBefore - 1 &&
        !afterDelete.phaseEditor.modified,
      "Native delete/save failed",
    );
    await click("Clear all records…");
    check(
      document.querySelector('dialog[aria-label="Clear all EoS records?"]')
        ?.open,
      "Native clear-record confirmation did not open",
    );
    await click("Cancel");
    check(
      !document.querySelector("dialog[open]"),
      "Cancel left the native confirmation open",
    );
    await choose("Thermal model", "MieGruneisenDebye");
    await set("theta0", 650);
    const eos = document.querySelector(".pe-parameter-scroll:not([hidden])");
    check(
      eos.scrollHeight > eos.clientHeight &&
        eos.offsetWidth - eos.clientWidth >= 10,
      "EoS scrollbar is not persistent",
    );
    await choose("Reflection position columns", "all");
    check(
      document.querySelector('th[aria-sort] button[title="Sort by Q₀ (Å⁻¹)"]'),
      "Reference Q column missing",
    );
    report = {
      ok: true,
      nativeTitleBar: true,
      independentlyMoved: true,
      persistentScrollbars: true,
      compactIndices: true,
      intensityPrecision: true,
      materialNameAndSave: true,
    };
  } catch (error) {
    report = { ok: false, error: String(error) };
  }
  await invoke("plugin:event|emit", {
    event: "phase-editor-smoke",
    payload: report,
  });
  await delay(150);
  await invoke("plugin:window|close", { label: "phase-editor" });
})();

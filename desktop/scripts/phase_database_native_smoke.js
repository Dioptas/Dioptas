// Scoped database checks, injected only into our explicitly launched smoke window.
window.__dioptasDatabaseNativeSmoke = async ({
  call,
  click,
  ready,
  delay,
  check,
}) => {
  const db = () =>
    document.querySelector('dialog[aria-label="EoS Material Database"][open]');
  const input = db().querySelector('input[aria-label="Search materials"]');
  check(
    document.activeElement === input,
    "Native database did not focus search",
  );
  const search = async (query) => {
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    ).set.call(input, query);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await delay();
    for (let i = 0; i < 150; i++) {
      if (
        db().querySelector(
          'section[aria-label="Material results"][aria-busy="false"]',
        )
      )
        break;
      await delay(20);
    }
    check(
      db().querySelector('section[aria-busy="false"]'),
      "Native database search did not settle",
    );
    await ready();
  };
  await search("palladium");
  check(
    !db().querySelector('.phase-database-records tr[aria-selected="true"]'),
    "Native held record was automatically selected",
  );
  check(
    [...db().querySelectorAll("button")].find(
      (b) => b.textContent === "Load as Phase",
    ).disabled,
    "Native held record was loadable without selection",
  );
  await search("no such material xyz");
  check(
    !db().querySelector('table[aria-label="Database materials"] tbody tr'),
    "Native no-hit search kept a stale material",
  );
  await search("gold");
  const material = (
    await call("integration_phase_catalog", { query: "gold" })
  ).phaseCatalog.find((m) => m.id === "gold");
  const selected = () =>
    db().querySelector('.phase-database-records tr[aria-selected="true"]');
  check(selected(), "Native database lost the default record");
  const sourceIndex = selected().getAttribute("data-reference");
  check(tableHeaders(), "Native record list is not reference-first");
  function tableHeaders() {
    const headings = [
      ...db().querySelectorAll(".phase-database-records th"),
    ].map((cell) => cell.textContent.trim());
    return (
      headings[0] === "Reference" &&
      headings[1] === "EoS" &&
      headings.length <= 3
    );
  }
  const table = db().querySelector(".phase-database-records");
  [...table.querySelectorAll("th button")]
    .find((b) => b.textContent === "EoS")
    .click();
  await delay();
  check(
    selected().getAttribute("data-reference") === sourceIndex,
    "Native sorting changed record identity",
  );
  check(
    !db().querySelector(".phase-database-inspector, pre"),
    "Native database still contains the long inspector",
  );
  check(
    Number(sourceIndex) === material.defaultReference,
    "Native default record changed",
  );
  check(
    [...db().querySelectorAll("button")].some(
      (b) => b.textContent === "Peritheos ↗",
    ),
    "Native database lost the documentation link",
  );
  const before = (await call("state")).state.integration.phases.length;
  click("Load as Phase");
  await delay();
  await ready();
  check(!db(), "Native database did not close after loading");
  const phases = (await call("state")).state.integration.phases;
  check(
    phases.length === before + 1 &&
      phases.at(-1).reference === material.defaultReference,
    "Native database loaded the wrong record",
  );
  click("Browse EoS Material Database");
  await delay();
  await ready();
  return {
    heldDefaults: true,
    noHits: true,
    sortIdentity: true,
    conciseRecords: true,
    documentationLinks: true,
    loadSelected: true,
  };
};

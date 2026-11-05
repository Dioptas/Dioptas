// Shared browser/native regression check. Inspect rendered fields rather than
// accepting theme tokens that a table or editor can override.
window.__dioptasFieldAppearance = () => {
  const samples = [...document.querySelectorAll("input, select, textarea")]
    .filter(
      (field) =>
        ![
          "checkbox",
          "radio",
          "range",
          "color",
          "hidden",
          "button",
          "submit",
        ].includes(field.type) &&
        field.getClientRects().length &&
        !field.closest('[hidden], [inert], [aria-hidden="true"]'),
    )
    .map((field) => {
      const style = getComputedStyle(field);
      const colours = [
        style.borderTopColor,
        style.borderRightColor,
        style.borderBottomColor,
        style.borderLeftColor,
      ];
      const pale = (colour) => {
        const values = colour.match(/[\d.]+/g)?.map(Number) ?? [];
        return (
          values.length >= 3 &&
          (values[3] ?? 1) > 0 &&
          Math.max(...values.slice(0, 3)) > 90
        );
      };
      const resting =
        !field.matches(":focus-visible") &&
        field.getAttribute("aria-invalid") !== "true";
      return {
        label: field.getAttribute("aria-label") ?? field.name ?? field.type,
        type: field.type,
        resting,
        border: colours,
        outline: style.outlineColor,
        outlineWidth: style.outlineWidth,
        outlineStyle: style.outlineStyle,
        invalid: field.getAttribute("aria-invalid") === "true",
        focused: field.matches(":focus-visible"),
        failure:
          resting &&
          (colours.some(pale) ||
            (style.outlineStyle !== "none" &&
              parseFloat(style.outlineWidth) > 0 &&
              pale(style.outlineColor))),
      };
    });
  return {
    checked: samples.filter((field) => field.resting).length,
    failures: samples.filter((field) => field.failure),
    samples,
  };
};

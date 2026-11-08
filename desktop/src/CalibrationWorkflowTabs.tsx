import { Button } from "./ui";
const sections = [
  ["Image", "Image & setup"],
  ["Peaks", "Pick rings"],
  ["Fit", "Calibrate"],
  ["Validate", "Validate"],
] as const;

export function CalibrationWorkflowTabs({
  active,
  disabled,
  onChange,
}: {
  active: number;
  disabled: readonly boolean[];
  onChange: (index: number) => void;
}) {
  return (
    <div
      className="calibration-workflow-tabs"
      role="tablist"
      aria-label="Calibration sections"
    >
      {sections.map(([label, description], index) => (
        <Button
          key={label}
          type="button"
          id={`calibration-section-${index}`}
          role="tab"
          aria-label={`Step ${index + 1}: ${description}`}
          aria-controls="calibration-task-content"
          aria-selected={active === index}
          title={description}
          tabIndex={active === index ? 0 : -1}
          disabled={disabled[index]}
          onClick={() => onChange(index)}
          onKeyDown={(event) => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
              return;
            event.preventDefault();
            const enabled = sections.flatMap((_, i) =>
              disabled[i] ? [] : [i],
            );
            const position = enabled.indexOf(index);
            const next =
              event.key === "Home"
                ? enabled[0]
                : event.key === "End"
                  ? enabled[enabled.length - 1]
                  : enabled[
                      (position +
                        (event.key === "ArrowLeft" ? -1 : 1) +
                        enabled.length) %
                        enabled.length
                    ];
            if (next === undefined) return;
            onChange(next);
            event.currentTarget.parentElement
              ?.querySelectorAll<HTMLButtonElement>("button")
              [next]?.focus();
          }}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}

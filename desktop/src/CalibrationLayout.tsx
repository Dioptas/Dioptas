import { Button } from "./ui";
export function CalibrationTabs({
  label,
  tabs,
  active,
  onChange,
}: {
  label: string;
  tabs: readonly string[];
  active: number;
  onChange: (index: number) => void;
}) {
  return (
    <div className="calibration-section-tabs" role="tablist" aria-label={label}>
      {tabs.map((tab, index) => (
        <Button
          type="button"
          key={tab}
          role="tab"
          aria-selected={active === index}
          tabIndex={active === index ? 0 : -1}
          onClick={() => onChange(index)}
          onKeyDown={(event) => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
              return;
            event.preventDefault();
            const next =
              event.key === "Home"
                ? 0
                : event.key === "End"
                  ? tabs.length - 1
                  : (index +
                      (event.key === "ArrowLeft" ? -1 : 1) +
                      tabs.length) %
                    tabs.length;
            onChange(next);
            event.currentTarget.parentElement
              ?.querySelectorAll<HTMLButtonElement>("button")
              [next]?.focus();
          }}
        >
          {tab}
        </Button>
      ))}
    </div>
  );
}

import { useId, type ReactNode } from "react";

export type TabOption<T extends string | number> = {
  value: T;
  label: ReactNode;
  name?: string;
  id?: string;
  panelId?: string;
  title?: string;
  disabled?: boolean;
};

/** One keyboard contract for task tabs, settings, and scientific editors. */
export function TabList<T extends string | number>({
  label,
  value,
  options,
  onChange,
  className,
  orientation = "horizontal",
}: {
  label: string;
  value: T;
  options: readonly TabOption<T>[];
  onChange: (value: T) => void;
  className?: string;
  orientation?: "horizontal" | "vertical";
}) {
  const id = useId();
  const focusValue =
    options.find((option) => option.value === value && !option.disabled)
      ?.value ?? options.find((option) => !option.disabled)?.value;
  return (
    <div
      className={className}
      role="tablist"
      aria-label={label}
      aria-orientation={orientation}
    >
      {options.map((option, index) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          id={option.id ?? `${id}-${index}`}
          aria-label={option.name}
          aria-controls={option.panelId}
          aria-selected={value === option.value}
          tabIndex={focusValue === option.value ? 0 : -1}
          title={option.title}
          disabled={option.disabled}
          onClick={() => onChange(option.value)}
          onKeyDown={(event) => {
            const previous =
              orientation === "vertical" ? "ArrowUp" : "ArrowLeft";
            const next =
              orientation === "vertical" ? "ArrowDown" : "ArrowRight";
            if (![previous, next, "Home", "End"].includes(event.key)) return;
            event.preventDefault();
            const enabled = options.filter((item) => !item.disabled);
            if (!enabled.length) return;
            const position = enabled.findIndex(
              (item) => item.value === option.value,
            );
            const target =
              event.key === "Home"
                ? enabled[0]
                : event.key === "End"
                  ? enabled.at(-1)!
                  : enabled[
                      (position +
                        (event.key === previous ? -1 : 1) +
                        enabled.length) %
                        enabled.length
                    ];
            onChange(target.value);
            const targetIndex = options.indexOf(target);
            event.currentTarget.parentElement
              ?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
              [targetIndex]?.focus();
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

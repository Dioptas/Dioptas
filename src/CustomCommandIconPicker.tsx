import { Button, Input, Popover, Portal } from "./ui";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

import { ChevronDown } from "lucide-react";
import {
  commandIconChoices,
  getCommandIcon,
  type CommandIconId,
} from "./customCommandIcons";

export function CustomCommandIconPicker({
  value = "terminal",
  disabled,
  onChange,
}: {
  value?: CommandIconId;
  disabled: boolean;
  onChange: (icon: CommandIconId) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState({
    left: 0,
    top: 0,
    width: 360,
    maxHeight: 380,
  });
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const Icon = getCommandIcon(value);
  const label =
    commandIconChoices.find((choice) => choice.id === value)?.label ??
    "Terminal";
  const choices = commandIconChoices.filter((choice) =>
    choice.label.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const selectedIndex = Math.max(
    0,
    choices.findIndex((choice) => choice.id === value),
  );
  const close = () => {
    setOpen(false);
    trigger.current?.focus({ preventScroll: true });
  };
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const rect = trigger.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(360, window.innerWidth - 24);
      const below = window.innerHeight - rect.bottom - 12;
      const above = rect.top - 12;
      const columns = Math.max(1, Math.floor((width - 28) / 46));
      const desiredHeight = Math.min(
        380,
        Math.max(120, 72 + Math.ceil(choices.length / columns) * 46),
      );
      const useBelow = below >= desiredHeight || below >= above;
      const maxHeight = Math.min(
        desiredHeight,
        Math.max(120, useBelow ? below : above),
      );
      setPosition({
        width,
        maxHeight,
        left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
        top: useBelow
          ? rect.bottom + 6
          : Math.max(12, rect.top - maxHeight - 6),
      });
    };
    place();
    input.current?.focus({ preventScroll: true });
    window.addEventListener("resize", place);
    const scroll = (event: Event) => {
      if (!popup.current?.contains(event.target as Node)) place();
    };
    window.addEventListener("scroll", scroll, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", scroll, true);
    };
  }, [open, choices.length]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !popup.current?.contains(target) &&
        !trigger.current?.contains(target)
      )
        setOpen(false);
    };
    document.addEventListener("pointerdown", outside, true);
    return () => document.removeEventListener("pointerdown", outside, true);
  }, [open]);
  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);
  return (
    <div className="custom-command-icon-selector">
      <span id={`${id}-label`}>Button icon</span>
      <Button
        ref={trigger}
        type="button"
        className="custom-command-icon-trigger"
        aria-label={`Change action icon: ${label}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        disabled={disabled}
        onClick={() => {
          setSearch("");
          setOpen(!open);
        }}
      >
        <Icon size={20} aria-hidden="true" />
        <span>{label}</span>
        <ChevronDown size={16} aria-hidden="true" />
      </Button>
      {open && (
        <Portal>
          <Popover
            ref={popup}
            id={id}
            role="dialog"
            aria-labelledby={`${id}-label`}
            className="custom-command-icon-popup"
            style={position}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                close();
              }
            }}
            onBlur={(event) => {
              if (
                event.relatedTarget &&
                !event.currentTarget.contains(event.relatedTarget as Node) &&
                !trigger.current?.contains(event.relatedTarget as Node)
              )
                setOpen(false);
            }}
          >
            <Input
              ref={input}
              type="search"
              aria-label="Search action icons"
              placeholder="Search icons…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  popup.current
                    ?.querySelector<HTMLButtonElement>("[tabindex='0']")
                    ?.focus();
                }
              }}
            />
            <div
              className="custom-command-icon-grid"
              role="group"
              aria-label="Available action icons"
              onKeyDown={(event) => {
                const buttons = Array.from(
                  event.currentTarget.querySelectorAll<HTMLButtonElement>(
                    "button",
                  ),
                );
                const index = buttons.indexOf(
                  event.target as HTMLButtonElement,
                );
                if (index < 0) return;
                const columns = getComputedStyle(
                  event.currentTarget,
                ).gridTemplateColumns.split(" ").length;
                const step =
                  event.key === "ArrowRight"
                    ? 1
                    : event.key === "ArrowLeft"
                      ? -1
                      : event.key === "ArrowDown"
                        ? columns
                        : event.key === "ArrowUp"
                          ? -columns
                          : null;
                const next =
                  event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? buttons.length - 1
                      : step === null
                        ? null
                        : Math.max(
                            0,
                            Math.min(buttons.length - 1, index + step),
                          );
                if (next !== null) {
                  event.preventDefault();
                  buttons[next]?.focus();
                }
              }}
            >
              {choices.map(({ id, label, icon: ChoiceIcon }, index) => (
                <Button
                  key={id}
                  type="button"
                  title={label}
                  aria-label={`Use ${label} icon`}
                  aria-pressed={value === id}
                  tabIndex={index === selectedIndex ? 0 : -1}
                  onClick={() => {
                    close();
                    onChange(id);
                  }}
                >
                  <ChoiceIcon size={20} aria-hidden="true" />
                </Button>
              ))}
              {!choices.length && <p>No matching icons.</p>}
            </div>
          </Popover>
        </Portal>
      )}
    </div>
  );
}

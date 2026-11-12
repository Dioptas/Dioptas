import { Button, Input, Popover, Portal } from "./ui";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

import { Ellipsis, LoaderCircle } from "lucide-react";
import { getCommandIcon } from "./customCommandIcons";
import {
  missingCommandInput,
  type CustomCommand,
  type CustomCommandController,
} from "./customCommands";
import "./customCommands.css";

export function CustomCommandButtons({
  controller,
  ready,
  onError,
}: {
  controller: CustomCommandController;
  ready: boolean;
  onError: (message: string | null) => void;
}) {
  const { commands, runs, context, pending, request } = controller;
  const visible = commands.filter((command) => command.enabled);
  const [slots, setSlots] = useState(4);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState({
    left: 76,
    top: 12,
    width: 320,
    maxHeight: 440,
  });
  const group = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const menuId = useId();
  const inlineCount =
    visible.length <= Math.min(3, slots)
      ? visible.length
      : Math.max(0, Math.min(3, slots - 1));
  const overflow = visible.length > inlineCount;
  const matches = visible.filter((command) =>
    command.name.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const close = () => {
    setOpen(false);
    trigger.current?.focus({ preventScroll: true });
  };

  useLayoutEffect(() => {
    const node = group.current;
    const nav = node?.closest<HTMLElement>(".mode-navigation");
    const utilities = node?.parentElement;
    if (!node || !nav || !utilities) return;
    const outerHeight = (element: Element) => {
      const style = getComputedStyle(element);
      return (
        element.getBoundingClientRect().height +
        (parseFloat(style.marginTop) || 0) +
        (parseFloat(style.marginBottom) || 0)
      );
    };
    const measure = () => {
      const navStyle = getComputedStyle(nav);
      const style = getComputedStyle(node);
      const others =
        [...nav.children]
          .filter((child) => child !== utilities)
          .reduce((total, child) => total + outerHeight(child), 0) +
        [...utilities.children]
          .filter((child) => child !== node)
          .reduce((total, child) => total + outerHeight(child), 0);
      const extras = [
        navStyle.paddingTop,
        navStyle.paddingBottom,
        style.marginTop,
        style.marginBottom,
        style.paddingTop,
        style.paddingBottom,
        style.borderTopWidth,
        style.borderBottomWidth,
      ].reduce((total, value) => total + (parseFloat(value) || 0), 0);
      const space = nav.clientHeight - others - extras;
      setSlots(Math.max(1, Math.min(4, Math.floor((space + 4) / 68))));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(nav);
    [...nav.children, ...utilities.children]
      .filter((child) => child !== utilities && child !== node)
      .forEach((child) => observer.observe(child));
    return () => observer.disconnect();
  }, [visible.length]);

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const anchor = trigger.current?.getBoundingClientRect();
      if (!anchor) return;
      const width = Math.min(320, window.innerWidth - 24);
      const maxHeight = Math.min(440, window.innerHeight - 24);
      setPosition({
        width,
        maxHeight,
        left: Math.max(
          12,
          Math.min(anchor.right + 8, window.innerWidth - width - 12),
        ),
        top: Math.max(
          12,
          Math.min(anchor.top, window.innerHeight - maxHeight - 12),
        ),
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
  }, [open]);
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
    if (!overflow) setOpen(false);
  }, [overflow]);

  const runCommand = async (command: CustomCommand) => {
    onError(null);
    if (!(await request("run", { identifier: command.id })))
      onError(
        `Could not run ${command.name}. See Settings → Custom actions for details.`,
      );
  };
  const status = (command: CustomCommand) => {
    const missing = missingCommandInput(command, context);
    const running = !!runs[command.id]?.running;
    return {
      running,
      disabled: !ready || pending || running || !!missing,
      detail: running
        ? "Running…"
        : missing
          ? `${missing} unavailable`
          : !ready
            ? "Workspace busy"
            : "",
    };
  };
  if (!visible.length) return null;
  return (
    <div
      ref={group}
      className="navigation-group navigation-custom-commands"
      role="group"
      aria-label="Custom actions"
    >
      {visible.slice(0, inlineCount).map((command) => {
        const { running, disabled, detail } = status(command);
        const Icon = getCommandIcon(command.icon);
        return (
          <Button
            key={command.id}
            className="workspace-nav"
            aria-label={`Run ${command.name}`}
            title={`${command.name}${detail ? ` · ${detail}` : ""}`}
            disabled={disabled}
            onClick={() => void runCommand(command)}
          >
            {running ? (
              <LoaderCircle size={18} className="spin" />
            ) : (
              <Icon size={18} />
            )}
            <span>{command.name}</span>
          </Button>
        );
      })}
      {overflow && (
        <Button
          ref={trigger}
          className="workspace-nav"
          aria-label="More actions"
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-controls={open ? menuId : undefined}
          title={`All ${visible.length} custom actions`}
          onClick={() => {
            setSearch("");
            setOpen(!open);
          }}
        >
          <Ellipsis size={20} />
          <span>More</span>
        </Button>
      )}
      {open && overflow && (
        <Portal>
          <Popover
            id={menuId}
            ref={popup}
            className="custom-command-menu"
            role="dialog"
            aria-label="Custom actions"
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
            <div className="custom-command-menu-heading">
              Custom actions <span>{visible.length}</span>
            </div>
            <Input
              ref={input}
              type="search"
              aria-label="Search custom actions"
              placeholder="Search actions…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  popup.current
                    ?.querySelector<HTMLButtonElement>(
                      ".custom-command-menu-list button:not(:disabled)",
                    )
                    ?.focus();
                }
              }}
            />
            <div
              className="custom-command-menu-list"
              role="group"
              aria-label="All custom actions"
              onKeyDown={(event) => {
                const buttons = [
                  ...event.currentTarget.querySelectorAll<HTMLButtonElement>(
                    "button:not(:disabled)",
                  ),
                ];
                const index = buttons.indexOf(
                  event.target as HTMLButtonElement,
                );
                if (index < 0) return;
                const next =
                  event.key === "ArrowDown"
                    ? (index + 1) % buttons.length
                    : event.key === "ArrowUp"
                      ? (index + buttons.length - 1) % buttons.length
                      : event.key === "Home"
                        ? 0
                        : event.key === "End"
                          ? buttons.length - 1
                          : null;
                if (next !== null) {
                  event.preventDefault();
                  buttons[next]?.focus();
                }
              }}
            >
              {matches.map((command) => {
                const { running, disabled, detail } = status(command);
                const Icon = getCommandIcon(command.icon);
                return (
                  <Button
                    key={command.id}
                    aria-label={`Run ${command.name}`}
                    title={`${command.name}${detail ? ` · ${detail}` : ""}`}
                    disabled={disabled}
                    onClick={() => {
                      close();
                      void runCommand(command);
                    }}
                  >
                    {running ? (
                      <LoaderCircle size={18} className="spin" />
                    ) : (
                      <Icon size={18} />
                    )}
                    <span>
                      {command.name}
                      {detail && <small>{detail}</small>}
                    </span>
                  </Button>
                );
              })}
              {!matches.length && <p>No matching actions.</p>}
            </div>
          </Popover>
        </Portal>
      )}
    </div>
  );
}

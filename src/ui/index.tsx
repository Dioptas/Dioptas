import {
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  type ComponentProps,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import "./ui.css";
import "./scrollbars.css";

const classes = (base: string, extra?: string) =>
  extra ? `${base} ${extra}` : base;

/** Native props, events and refs remain available to scientific field editors. */
export function Input({
  className,
  autoFocus,
  ...props
}: ComponentProps<"input">) {
  return (
    <input
      {...props}
      autoFocus={autoFocus}
      data-ui-autofocus={autoFocus || undefined}
      className={classes("ui-input", className)}
    />
  );
}

export function Select({
  className,
  autoFocus,
  ...props
}: ComponentProps<"select">) {
  return (
    <select
      {...props}
      autoFocus={autoFocus}
      data-ui-autofocus={autoFocus || undefined}
      className={classes("ui-select", className)}
    />
  );
}

export function TextArea({
  className,
  autoFocus,
  ...props
}: ComponentProps<"textarea">) {
  return (
    <textarea
      {...props}
      autoFocus={autoFocus}
      data-ui-autofocus={autoFocus || undefined}
      className={classes("ui-textarea", className)}
    />
  );
}

export function Button({
  className,
  variant,
  autoFocus,
  ...props
}: ComponentProps<"button"> & {
  variant?: "primary" | "secondary" | "quiet";
}) {
  // Preserve native submit behavior. Form callers choose type="button" explicitly.
  return (
    <button
      {...props}
      autoFocus={autoFocus}
      data-ui-autofocus={autoFocus || undefined}
      className={classes(
        "ui-button",
        [variant, className].filter(Boolean).join(" "),
      )}
    />
  );
}

export function DialogHeader({
  title,
  onClose,
  closeLabel = "Close",
  headingId,
  className,
}: {
  title: ReactNode;
  onClose: () => void;
  closeLabel?: string;
  headingId?: string;
  className?: string;
}) {
  return (
    <header className={classes("ui-dialog-header", className)}>
      <h2 id={headingId}>{title}</h2>
      <Button
        type="button"
        variant="quiet"
        className="ui-dialog-close"
        aria-label={closeLabel}
        title={closeLabel}
        onClick={onClose}
      >
        ×
      </Button>
    </header>
  );
}

/** Portals inherit the active window's theme and text-size preference. */
export function Portal({ children }: { children: ReactNode }) {
  return createPortal(
    children,
    document.querySelector(".app") ?? document.body,
  );
}

/** A native dialog supports controlled opening or existing imperative DOM refs. */
export function Dialog({
  ref,
  className,
  open,
  onDismiss,
  dismissOnBackdrop = false,
  backdrop = "dim",
  onCancel,
  onClick,
  onClose,
  ...props
}: Omit<ComponentProps<"dialog">, "open"> & {
  open?: boolean;
  onDismiss?: () => void;
  dismissOnBackdrop?: boolean;
  backdrop?: "dim" | "clear";
}) {
  const element = useRef<HTMLDialogElement>(null);
  useImperativeHandle(ref, () => element.current!, []);
  useLayoutEffect(() => {
    const dialog = element.current!;
    if (open === undefined) return;
    if (open && !dialog.open) {
      dialog.showModal();
      // React's autoFocus runs while the dialog is still closed. Honor the
      // requested field after it enters the native top layer.
      dialog
        .querySelector<HTMLElement>("[data-ui-autofocus], [autofocus]")
        ?.focus();
    }
    if (!open && dialog.open) dialog.close();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, [open]);
  return (
    <dialog
      {...props}
      ref={element}
      className={classes("ui-dialog", className)}
      data-backdrop={backdrop}
      onClose={(event) => {
        onClose?.(event);
        if (open && onDismiss && !event.defaultPrevented) onDismiss();
      }}
      onCancel={(event) => {
        onCancel?.(event);
        if (!event.defaultPrevented && onDismiss) {
          event.preventDefault();
          onDismiss();
        }
      }}
      onClick={(event) => {
        onClick?.(event);
        if (
          !dismissOnBackdrop ||
          event.defaultPrevented ||
          event.target !== event.currentTarget
        )
          return;
        const box = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < box.left ||
          event.clientX > box.right ||
          event.clientY < box.top ||
          event.clientY > box.bottom
        ) {
          if (onDismiss) onDismiss();
          else event.currentTarget.close();
        }
      }}
    />
  );
}

/** The same dialog surface without modality for an independent editor window. */
export function DialogPanel({
  className,
  open: _open,
  ...props
}: ComponentProps<"section"> & { open?: boolean }) {
  return <section {...props} className={classes("ui-dialog", className)} />;
}

/** Positioning and menu-specific keyboard navigation belong to the calling view. */
export function Popover({ className, ...props }: ComponentProps<"div">) {
  return <div {...props} className={classes("ui-popover", className)} />;
}

export function Tooltip({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      {...props}
      role="tooltip"
      className={classes("ui-tooltip", className)}
    />
  );
}

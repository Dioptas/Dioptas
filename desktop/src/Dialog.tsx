import { Button, Dialog as SharedDialog } from "./ui";
import {
  useLayoutEffect,
  useRef,
  type ComponentProps,
  type ReactNode,
  type RefObject,
} from "react";
import { X } from "lucide-react";

// A processing response can open a dialog after its trigger was temporarily
// disabled. Browsers move focus to body in that interval; retain the real
// trigger so asynchronous dialogs restore the same keyboard workflow.
let lastFocused: HTMLElement | null = null;
document.addEventListener("focusin", (event) => {
  if (event.target instanceof HTMLElement && event.target !== document.body)
    lastFocused = event.target;
});

document.addEventListener("pointerdown", (event) => {
  const target =
    event.target instanceof Element
      ? event.target.closest<HTMLElement>(
          "button, input, select, textarea, a[href], [tabindex]",
        )
      : null;
  if (target) lastFocused = target;
});

/** Native top-layer modal: inert background, keyboard containment and focus return. */
export function Dialog({
  children,
  dialogRef,
  autoOpen = true,
  onDismiss,
  onCancel,
  onClick,
  onKeyDown,
  returnFocusTarget,
  returnFocusRef,
  onClose,
  ...props
}: Omit<ComponentProps<"dialog">, "ref" | "open"> & {
  dialogRef?: RefObject<HTMLDialogElement | null>;
  autoOpen?: boolean;
  onDismiss?: () => void;
  returnFocusTarget?: HTMLElement | SVGElement | null;
  returnFocusRef?: RefObject<HTMLElement | SVGElement | null>;
}) {
  const internal = useRef<HTMLDialogElement>(null);
  const ref = dialogRef ?? internal;
  useLayoutEffect(() => {
    const element = ref.current;
    if (!autoOpen || !element) return;
    const trigger =
      returnFocusRef?.current ??
      returnFocusTarget ??
      (document.activeElement === document.body
        ? lastFocused
        : document.activeElement);
    if (!element.open) element.showModal();
    return () => {
      element.close();
      if (
        (trigger instanceof HTMLElement || trigger instanceof SVGElement) &&
        trigger.isConnected
      )
        trigger.focus({ preventScroll: true });
    };
  }, [autoOpen, ref, returnFocusTarget, returnFocusRef]);
  const dismiss = () => (onDismiss ? onDismiss() : ref.current?.close());
  return (
    <SharedDialog
      {...props}
      ref={ref}
      data-ui-dialog="true"
      onClose={(event) => {
        onClose?.(event);
        const trigger = returnFocusRef?.current ?? returnFocusTarget;
        if (!autoOpen && trigger?.isConnected)
          trigger.focus({ preventScroll: true });
      }}
      onKeyDown={(event) => {
        onKeyDown?.(event);
        if (event.defaultPrevented || event.key !== "Tab") return;
        const controls = [
          ...event.currentTarget.querySelectorAll<HTMLElement>(
            'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])',
          ),
        ].filter(
          (element) =>
            element.tabIndex >= 0 &&
            element.getClientRects().length &&
            !element.closest("[hidden], [inert]"),
        );
        const first = controls[0],
          last = controls.at(-1);
        if (!first || !last) {
          event.preventDefault();
          return;
        }
        if (
          (!event.shiftKey && document.activeElement === last) ||
          (event.shiftKey && document.activeElement === first)
        ) {
          event.preventDefault();
          (event.shiftKey ? last : first).focus();
        }
      }}
      onCancel={(event) => {
        if (onCancel) onCancel(event);
        else {
          event.preventDefault();
          event.stopPropagation();
          dismiss();
        }
      }}
      onClick={(event) => {
        onClick?.(event);
        if (event.defaultPrevented || event.target !== event.currentTarget)
          return;
        const box = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < box.left ||
          event.clientX > box.right ||
          event.clientY < box.top ||
          event.clientY > box.bottom
        )
          dismiss();
      }}
    >
      {children}
    </SharedDialog>
  );
}

export function DialogHeader({
  title,
  titleId,
  closeLabel,
  onClose,
  children,
  compact = false,
}: {
  title: ReactNode;
  titleId?: string;
  closeLabel: string;
  onClose: () => void;
  children?: ReactNode;
  compact?: boolean;
}) {
  return (
    <header
      className="ui-dialog-header"
      data-density={compact ? "compact" : "normal"}
    >
      <h2 id={titleId}>{title}</h2>
      {children}
      <Button
        type="button"
        className="quiet ui-dialog-close"
        aria-label={closeLabel}
        title={closeLabel}
        onClick={onClose}
      >
        <X size={17} aria-hidden="true" />
      </Button>
    </header>
  );
}

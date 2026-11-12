import {
  Component,
  useEffect,
  useState,
  type ErrorInfo,
  type ReactNode,
} from "react";
import { OperationErrorDialog } from "./OperationErrorDialog";
import {
  failureEvent,
  currentFailure,
  dismissFailure,
  reportFailure,
  type OperationFailure,
} from "./errorReporting";

export function ErrorReportHost() {
  const [failure, setFailure] = useState<
    (OperationFailure & { id: number }) | null
  >(null);
  useEffect(() => {
    const failed = (event: Event) => setFailure((event as CustomEvent).detail);
    const runtime = (event: ErrorEvent) =>
      reportFailure("Interface error", event.error ?? event.message);
    const rejected = (event: PromiseRejectionEvent) =>
      reportFailure("Unhandled asynchronous operation", event.reason);
    window.addEventListener(failureEvent, failed);
    if (currentFailure()) setFailure(currentFailure());
    window.addEventListener("error", runtime);
    window.addEventListener("unhandledrejection", rejected);
    return () => {
      window.removeEventListener(failureEvent, failed);
      window.removeEventListener("error", runtime);
      window.removeEventListener("unhandledrejection", rejected);
    };
  }, []);
  return (
    failure && (
      <OperationErrorDialog
        key={failure.id}
        failure={failure}
        onClose={() => {
          dismissFailure();
          setFailure(null);
        }}
      />
    )
  );
}

export class ApplicationErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    reportFailure(
      "Rendering the interface",
      error,
      {},
      { componentStack: info.componentStack },
    );
  }
  render() {
    return this.state.failed ? (
      <main role="alert" style={{ padding: 24 }}>
        The interface encountered an error. Copy the error report, then reopen
        the application.
      </main>
    ) : (
      this.props.children
    );
  }
}

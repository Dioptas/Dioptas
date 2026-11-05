import { useCallback, useEffect, useRef, useState } from "react";

/** One transient notice lifecycle for saved files, loaded sources and history. */
export function useWorkflowNotice() {
  const [notice, setNotice] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const publish = useCallback((message: string | null) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    setNotice(message);
    if (message) timer.current = setTimeout(() => setNotice(null), 4500);
  }, []);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  return [notice, publish] as const;
}

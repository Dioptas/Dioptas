import { useCallback, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { initialResponseSnapshot } from "./responseSnapshot";
import type { ResponseSnapshot } from "./responseSnapshot";

/** One response model, with synchronous access while a serialized command is
 * applying. Local visibility/color controls and optimistic workflow drafts share
 * this owner without changing the canonical backend state reference in App. */
export function useResponseSnapshot() {
  const [snapshot, setSnapshot] = useState(initialResponseSnapshot);
  const current = useRef(snapshot);
  const publish = useCallback((next: ResponseSnapshot) => {
    current.current = next;
    setSnapshot(next);
  }, []);
  const field = useCallback(
    <K extends keyof ResponseSnapshot>(
      key: K,
    ): Dispatch<SetStateAction<ResponseSnapshot[K]>> =>
      (value) => {
        const before = current.current;
        const next =
          typeof value === "function"
            ? (value as (previous: ResponseSnapshot[K]) => ResponseSnapshot[K])(
                before[key],
              )
            : value;
        if (next !== before[key]) publish({ ...before, [key]: next });
      },
    [publish],
  );
  const [setters] = useState(() => ({
    setState: field("state"),
    setShowOriginalPattern: field("showOriginalPattern"),
    setOriginalPatternColor: field("originalPatternColor"),
  }));
  return { ...snapshot, ...setters, current, publish };
}

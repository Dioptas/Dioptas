import { useSyncExternalStore } from "react";

const key = "dioptas-show-model-explanations";
const changed = "dioptas-model-explanations-changed";
let localOverride: boolean | undefined;
function read() {
  if (localOverride !== undefined) return localOverride;
  try {
    return localStorage.getItem(key) === "true";
  } catch {
    return false;
  }
}
function subscribe(listener: () => void) {
  const storage = (event: StorageEvent) => {
    if (event.key === key || event.key === null) {
      localOverride = undefined;
      listener();
    }
  };
  window.addEventListener(changed, listener);
  window.addEventListener("storage", storage);
  return () => {
    window.removeEventListener(changed, listener);
    window.removeEventListener("storage", storage);
  };
}
function set(value: boolean) {
  localOverride = value;
  try {
    localStorage.setItem(key, String(value));
    localOverride = undefined;
  } catch {
    /* The current window can still toggle help. */
  }
  window.dispatchEvent(new Event(changed));
}
export function useModelExplanationPreference() {
  return [useSyncExternalStore(subscribe, read), set] as const;
}

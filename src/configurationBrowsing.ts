import { useSyncExternalStore } from "react";

export interface ConfigurationBrowsing {
  fileNumber: number;
  fileStep: number;
  folderNumber: number;
  folderStep: number;
  folderFileNumber: number;
  folderFileStep: number;
}
export const defaultBrowsing: ConfigurationBrowsing = {
  fileNumber: 0,
  fileStep: 1,
  folderNumber: 0,
  folderStep: 1,
  folderFileNumber: 0,
  folderFileStep: 1,
};
export const mecBrowsing: ConfigurationBrowsing = {
  ...defaultBrowsing,
  folderFileNumber: 3,
};
const key = "dioptas-configuration-browsing";
const listeners = new Set<() => void>();
function read(): ConfigurationBrowsing {
  try {
    const raw = JSON.parse(localStorage.getItem(key) ?? "{}");
    const result = { ...defaultBrowsing };
    for (const name of [
      "fileNumber",
      "fileStep",
      "folderNumber",
      "folderStep",
      "folderFileNumber",
      "folderFileStep",
    ] as const) {
      const min = name.endsWith("Step") ? 1 : 0;
      const max = name.endsWith("Step") ? 1000000 : 100;
      if (Number.isInteger(raw[name]) && raw[name] >= min && raw[name] <= max)
        result[name] = raw[name];
    }
    return result;
  } catch {
    return { ...defaultBrowsing };
  }
}
let current = read();
function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export function saveConfigurationBrowsing(value: ConfigurationBrowsing) {
  current = value;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* Keep this session usable. */
  }
  listeners.forEach((listener) => listener());
}
export function useConfigurationBrowsing() {
  return useSyncExternalStore(subscribe, () => current);
}

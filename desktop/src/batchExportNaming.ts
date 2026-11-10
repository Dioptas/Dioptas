import type { BatchData } from "./batchDomain";

export function batchExportBaseName(
  batch: Pick<BatchData, "exportBaseName" | "files"> | null,
): string {
  const recorded = batch?.exportBaseName?.trim();
  if (recorded && !/[\\/\0]/.test(recorded)) return recorded;
  const stems = (batch?.files ?? [])
    .map((file) =>
      (file.name || file.path.split(/[\\/]/).at(-1) || "").replace(
        /\.[^.]+$/,
        "",
      ),
    )
    .filter(Boolean);
  if (!stems.length) return "batch";
  if (stems.length === 1) return stems[0];
  let prefix = stems[0];
  for (const stem of stems.slice(1)) {
    let end = 0;
    while (end < prefix.length && prefix[end] === stem[end]) end++;
    prefix = prefix.slice(0, end);
  }
  return prefix.replace(/\d+$/, "").replace(/[\s_.-]+$/, "") || stems[0];
}
export function isBatchMultifile(format: string) {
  return ["xy", "chi", "dat", "fxye"].includes(format);
}

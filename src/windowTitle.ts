export function applicationWindowTitle(
  version: string,
  context?: string | null,
  preview?: string,
): string {
  const base = `Dioptas ${version}`;
  const title = context ? `${base} — ${context}` : base;
  return preview ? `${title} · ${preview}` : title;
}

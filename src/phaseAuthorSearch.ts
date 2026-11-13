import type { DatabaseRecord } from "./phaseDatabaseTypes";

export function recordAuthors(record: DatabaseRecord): string[] {
  const reference = record.sourceRecord.reference;
  if (
    reference &&
    typeof reference === "object" &&
    "authors" in reference &&
    Array.isArray(reference.authors)
  ) {
    const authors = reference.authors.filter(
      (author): author is string => typeof author === "string",
    );
    if (authors.length) return authors;
  }
  return [typeof reference === "string" ? reference : record.authors];
}

const folded = (text: string) =>
  text.normalize("NFKD").replace(/\p{M}/gu, "").toLocaleLowerCase();
const normalized = (text: string) =>
  folded(text)
    .replace(/[’']/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();

/** Use full reference authors, including coauthors hidden by compact citations. */
export function matchesRecordAuthor(
  record: DatabaseRecord,
  query: string,
): boolean {
  const name = normalized(query);
  if (name.length < 2) return false;
  return recordAuthors(record).some((author) => {
    // Short surnames (Hu, Li) match whole words so formula searches like Au/Mg
    // do not expand to every author with those letters somewhere in a name.
    const authorName = normalized(author);
    if (name.length <= 2) return authorName.split(" ").includes(name);
    return authorName.includes(name);
  });
}

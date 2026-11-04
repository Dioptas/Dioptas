import assert from "node:assert/strict";
import { test } from "node:test";
import {
  matchesRecordAuthor,
  recordAuthors,
} from "../src/phaseAuthorSearch.ts";

const reference = (authors) => ({
  sourceRecord: { reference: { authors } },
  authors: `${authors[0]} et al.`,
});

test("author search includes coauthors omitted from the compact citation", () => {
  const record = reference(["Dorfman", "Prakapenka", "Dewaele"]);
  assert.equal(record.authors, "Dorfman et al.");
  assert.equal(matchesRecordAuthor(record, "Dewaele"), true);
  assert.equal(matchesRecordAuthor(record, "De Waele"), false);
  assert.equal(matchesRecordAuthor(record, "DEWAELE"), true);
  assert.equal(matchesRecordAuthor(record, "Fei"), false);
});

test("author search tolerates accents and punctuation without editing references", () => {
  const record = reference(["Bréger", "H. K. Mao", "O’Neill"]);
  const before = structuredClone(record);
  assert.equal(matchesRecordAuthor(record, "Breger"), true);
  assert.equal(matchesRecordAuthor(record, "oneill"), true);
  assert.equal(matchesRecordAuthor(record, "H.K. Mao"), true);
  assert.deepEqual(record, before);
});

test("short surnames remain searchable without polluting element searches", () => {
  const record = reference(["Hu", "Li", "Paul", "Humphreys", "M. G. Smith"]);
  assert.equal(matchesRecordAuthor(record, "Hu"), true);
  assert.equal(matchesRecordAuthor(record, "Li"), true);
  assert.equal(matchesRecordAuthor(record, "Au"), false);
  assert.equal(matchesRecordAuthor(record, "Mg"), false);
  assert.equal(matchesRecordAuthor(reference(["Humphreys"]), "Hu"), false);
  assert.equal(matchesRecordAuthor(record, ""), false);
  assert.equal(matchesRecordAuthor(record, "("), false);
  assert.equal(matchesRecordAuthor(record, "P"), false);
});

test("legacy reference strings and missing author lists retain their available names", () => {
  const legacy = {
    sourceRecord: { reference: "Dewaele and Garbarino, journal (2004)" },
    authors: "Dewaele and Garbarino",
  };
  assert.equal(matchesRecordAuthor(legacy, "Garbarino"), true);
  const fallback = { sourceRecord: {}, authors: "Fei et al." };
  assert.deepEqual(recordAuthors(fallback), ["Fei et al."]);
  assert.equal(matchesRecordAuthor(fallback, "Fei"), true);
});

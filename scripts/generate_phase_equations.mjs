// Typesetting only. All equations are authored locally; no numerical evaluation.
import katex from "katex";
import { readFile, writeFile } from "node:fs/promises";
const input = new URL("../src/phaseEquationSources.json", import.meta.url);
const output = new URL("../src/phaseEquations.generated.json", import.meta.url);
const sources = JSON.parse(await readFile(input, "utf8"));
const equations = Object.fromEntries(
  Object.entries(sources).map(([key, expressions]) => [
    key,
    expressions.map((tex, index) => ({
      text: `${key} equation ${index + 1}`,
      math: katex.renderToString(tex, {
        output: "mathml",
        displayMode: true,
        throwOnError: true,
        strict: "error",
        trust: false,
      }),
    })),
  ]),
);
const content = JSON.stringify(equations, null, 2) + "\n";
if (process.argv.includes("--check")) {
  if ((await readFile(output, "utf8")) !== content)
    throw Error(
      "Regenerate phase equations with npm run generate:phase-equations.",
    );
} else await writeFile(output, content);

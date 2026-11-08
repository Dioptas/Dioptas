import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { parsers } from "prettier/plugins/typescript";
import postcss from "postcss";

const source = fileURLToPath(new URL("../src/", import.meta.url));
async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return (
    await Promise.all(
      entries.map((entry) => {
        const filename = path.join(directory, entry.name);
        return entry.isDirectory() ? files(filename) : [filename];
      }),
    )
  ).flat();
}
function walk(node, visit) {
  if (!node || typeof node !== "object") return;
  visit(node);
  for (const [key, value] of Object.entries(node)) {
    if (["loc", "range", "tokens", "comments"].includes(key)) continue;
    if (Array.isArray(value)) value.forEach((child) => walk(child, visit));
    else if (value?.type) walk(value, visit);
  }
}

test("all desktop controls and floating surfaces use the shared components", async () => {
  const bypasses = [];
  for (const filename of await files(source)) {
    if (
      !filename.endsWith(".tsx") ||
      filename.includes(`${path.sep}ui${path.sep}`)
    )
      continue;
    const text = await readFile(filename, "utf8");
    const ast = await parsers.typescript.parse(text, { filepath: filename });
    walk(ast, (node) => {
      if (
        node.type === "ImportDeclaration" &&
        node.specifiers?.some(
          (specifier) => specifier.imported?.name === "createPortal",
        )
      )
        bypasses.push(`${path.basename(filename)}: use Portal from ./ui`);
      if (node.type !== "JSXOpeningElement") return;
      const name = node.name.name;
      const role = node.attributes.find(
        (attribute) =>
          attribute.type === "JSXAttribute" && attribute.name.name === "role",
      )?.value?.value;
      if (
        ["input", "select", "textarea", "button", "dialog"].includes(name) ||
        (["div", "section"].includes(name) &&
          ["dialog", "menu", "tooltip"].includes(role))
      )
        bypasses.push(
          `${path.basename(filename)}:${node.loc.start.line}: <${name}>`,
        );
    });
  }
  assert.deepEqual(
    bypasses,
    [],
    "Use the shared UI primitives so new views inherit the same styling and behavior.",
  );
});

test("field and floating-surface colors are owned by the shared UI styles", async () => {
  const bypasses = [];
  for (const filename of await files(source)) {
    if (
      !filename.endsWith(".css") ||
      filename.includes(`${path.sep}ui${path.sep}`)
    )
      continue;
    const root = postcss.parse(await readFile(filename, "utf8"), {
      from: filename,
    });
    root.walkRules((rule) => {
      // Readonly transparency, invalid-state borders and scientific color swatches
      // are semantic states, not a second theme.
      const fields = /\b(input|select|textarea)\b/.test(rule.selector);
      const surface =
        /^\.(?:[\w-]*(?:dialog|popup|popover|tooltip|menu)|color-map-options|display-settings)$/.test(
          rule.selector,
        );
      if (!fields && !surface) return;
      rule.walkDecls((declaration) => {
        if (
          ![
            "background",
            "background-color",
            "border",
            "border-color",
          ].includes(declaration.prop)
        )
          return;
        const value = declaration.value;
        if (
          /#[\da-f]{3,8}/i.test(value) &&
          !rule.selector.includes('[aria-invalid="true"]')
        )
          bypasses.push(
            `${path.basename(filename)}:${declaration.source.start.line}: ${declaration.prop}: ${value}`,
          );
      });
    });
  }
  assert.deepEqual(
    bypasses,
    [],
    "Use shared palette tokens instead of adding a private field/dialog color.",
  );
});

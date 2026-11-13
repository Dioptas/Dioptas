// Reuse the actual React crystal, so the native icon cannot drift to a hexagon.
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { createServer } from "vite";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const directory = fileURLToPath(
  new URL("../src-tauri/icons/", import.meta.url),
);
await mkdir(directory, { recursive: true });
const server = await createServer({ server: { middlewareMode: true } });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 256, height: 256 } });
  const { CrystalMark } = await server.ssrLoadModule("/src/CrystalMark.tsx");
  const markup = renderToStaticMarkup(createElement(CrystalMark));
  await page.setContent(markup);
  const svg = await page.locator("svg").evaluate((element) => {
    element.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    element.setAttribute("width", "256");
    element.setAttribute("height", "256");
    return element.outerHTML;
  });
  await writeFile(`${directory}/icon.svg`, svg + "\n");
  await page.setContent(`<style>body {margin: 0}</style>${svg}`);
  await page.screenshot({
    path: `${directory}/icon.png`,
    omitBackground: true,
  });
} finally {
  await browser.close();
  await server.close();
}

// Lightweight static HTTP server for prebuilt dist/index.html and prebuilt UI
// test harnesses. Under the gate (DIOPTAS_GATE_PREBUILT=1 or
// DIOPTAS_PREBUILT_HARNESSES=1) it serves prebuilt single-file HTML over
// http://127.0.0.1:0 in <1 ms without importing Vite. When a smoke script is
// invoked standalone outside the gate, it falls back to Vite's dev server so
// live source edits are always tested without risking a stale dist/.
import { createServer as createHttpServer } from "node:http";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { harnessOutputPath, root } from "./test_harness_paths.mjs";

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".txt": "text/plain; charset=utf-8",
};

export const usePrebuiltHarnesses = () =>
  process.env.DIOPTAS_GATE_PREBUILT === "1" ||
  process.env.DIOPTAS_PREBUILT_HARNESSES === "1";

async function startStaticServer({ harnesses = [] } = {}) {
  const indexHtml = path.join(root, "dist/index.html");
  if (!existsSync(indexHtml)) {
    throw Error(
      `Prebuilt frontend missing at ${indexHtml}; run \`npm run build\` first.`,
    );
  }
  const routes = new Map();
  for (const entry of harnesses) {
    const file = harnessOutputPath(entry);
    if (!existsSync(file)) {
      throw Error(
        `Prebuilt test harness missing at ${file}; run \`node scripts/build_test_harnesses.mjs\` first.`,
      );
    }
    routes.set(`/${entry}`, file);
  }

  const server = createHttpServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? "/", "http://127.0.0.1");
      const pathname = decodeURIComponent(url.pathname);
      let file;
      if (pathname === "/" || pathname === "/index.html") {
        file = indexHtml;
      } else if (routes.has(pathname)) {
        file = routes.get(pathname);
      } else if (pathname.startsWith("/licenses/")) {
        const candidate = path.resolve(root, "dist", pathname.slice(1));
        if (
          candidate.startsWith(path.join(root, "dist", "licenses") + path.sep)
        )
          file = candidate;
      }
      if (!file || !existsSync(file)) {
        res.writeHead(404);
        res.end("Not found");
        return;
      }
      const body = await readFile(file);
      const type =
        contentTypes[path.extname(file).toLowerCase()] ??
        "application/octet-stream";
      res.writeHead(200, { "Content-Type": type });
      res.end(body);
    } catch (error) {
      res.writeHead(500);
      res.end(String(error));
    }
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", reject);
      resolve();
    });
  });
  const { port } = server.address();
  const baseUrl = `http://127.0.0.1:${port}/`;
  return {
    url: baseUrl,
    resolvedUrls: { local: [baseUrl] },
    close: () =>
      new Promise((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      ),
  };
}

async function startViteFallback() {
  const { createServer } = await import("vite");
  const server = await createServer({
    root,
    logLevel: "error",
    server: { host: "127.0.0.1", port: 0, strictPort: false },
  });
  await server.listen();
  return server;
}

export async function startDistServer({ harnesses = [] } = {}) {
  if (usePrebuiltHarnesses()) {
    return startStaticServer({ harnesses });
  }
  return startViteFallback();
}

export const startHarnessServer = (harnesses) => startDistServer({ harnesses });

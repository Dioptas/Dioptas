import assert from "node:assert/strict";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { root } from "./native_backend_client.mjs";

// Exercise the real hook and error boundary without writing fixtures into a
// directory watched by a user's live preview. Native pixel/transfer behavior
// is tested separately in the Rust suite.
const entry = `
import React, {useCallback, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {useCrystalHover} from '/src/useCrystalHover.ts';
import {crystalDefaults} from '/src/singleCrystalDomain.ts';
import {withErrorReporting, currentFailure} from '/src/errorReporting.ts';
const state = window.fixture = {calls:[], readings:[], pending:[], reply:'valid', defer:false};
const invoke = withErrorReporting(async (action, args) => {
  state.calls.push({action, args, time:performance.now()});
  if(state.defer) return new Promise(resolve => state.pending.push(resolve));
  if(state.reply === 'legacy') return {ok:false,error:'Pixel outside SCXRD detector.'};
  return {ok:true,scxrdPixel:state.reply === 'empty' ? null : {...args,value:123,twoTheta:null}};
});
function Harness() {
 const [data,setData] = useState({frames:144,frame:0,shape:[2162,2068],image:{bufferId:'one'},config:crystalDefaults,geometry:null,previewKind:'raw'});
 const [active,setActive] = useState(true);
 const report = useCallback((_, reading)=>state.readings.push(reading),[]);
 state.hover = useCrystalHover(data,invoke,report,active);
 state.patch = patch => setData(d=>({...d,...patch}));
 state.activate = setActive;
 state.failure = currentFailure;
 return React.createElement('div', {'data-ready':true}, 'Hover test');
}
createRoot(document.getElementById('root')).render(React.createElement(Harness));
`;
const server = await createServer({
  root,
  logLevel: "error",
  server: { host: "127.0.0.1", port: 0, watch: null },
  plugins: [
    {
      name: "scxrd-hover-harness",
      resolveId(id) {
        if (id === "/hover-harness-entry.js") return "\0scxrd-hover-harness";
      },
      load(id) {
        if (id === "\0scxrd-hover-harness") return entry;
      },
      configureServer(server) {
        server.middlewares.use(async (req, res, next) => {
          if (req.url === "/hover-harness") {
            res.setHeader("Content-Type", "text/html");
            res.end(
              await server.transformIndexHtml(
                req.url,
                '<div id="root"></div><script type="module" src="/hover-harness-entry.js"></script>',
              ),
            );
          } else next();
        });
      },
    },
  ],
});
try {
  await server.listen();
  for (const [name, engine] of Object.entries({ chromium, webkit })) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(
        new URL("/hover-harness", server.resolvedUrls.local[0]).href,
      );
      await page.locator("[data-ready]").waitFor();
      await page.evaluate(() => window.fixture.hover({ x: 2038, y: 647 }));
      await page.waitForFunction(
        () => window.fixture.readings.at(-1)?.value === 123,
      );
      assert.deepEqual(
        await page.evaluate(() => window.fixture.calls.at(-1).args),
        { x: 2038, y: 647 },
      );
      const before = await page.evaluate(() => window.fixture.calls.length);
      for (const point of [
        { x: -1, y: 0 },
        { x: 2068, y: 0 },
        { x: 0, y: 2162 },
        { x: NaN, y: 1 },
        { x: 1, y: Infinity },
      ]) {
        await page.evaluate((p) => window.fixture.hover(p), point);
        await page.waitForTimeout(120);
      }
      assert.equal(
        await page.evaluate(() => window.fixture.calls.length),
        before,
      );
      assert.equal(
        await page.evaluate(() => window.fixture.readings.at(-1)),
        null,
      );
      for (const reply of ["empty", "legacy"]) {
        const callsBefore = await page.evaluate(
          () => window.fixture.calls.length,
        );
        await page.evaluate((reply) => {
          window.fixture.reply = reply;
          window.fixture.hover({ x: 1, y: 2 });
        }, reply);
        await page.waitForFunction(
          (n) => window.fixture.calls.length > n,
          callsBefore,
        );
        await page.waitForTimeout(130);
        assert.equal(
          await page.evaluate(() => window.fixture.readings.at(-1)),
          null,
        );
        assert.equal(await page.evaluate(() => window.fixture.failure()), null);
      }
      await page.evaluate(() => {
        window.fixture.reply = "valid";
        window.fixture.defer = true;
        window.fixture.hover({ x: 4, y: 5 });
      });
      await page.waitForFunction(() => window.fixture.pending.length === 1);
      const inFlight = await page.evaluate(() => window.fixture.calls.length);
      await page.evaluate(() => {
        window.fixture.hover({ x: 6, y: 7 });
        window.fixture.hover({ x: 8, y: 9 });
      });
      await page.waitForTimeout(120);
      assert.equal(
        await page.evaluate(() => window.fixture.calls.length),
        inFlight,
        "hover requests do not overlap",
      );
      await page.evaluate(() =>
        window.fixture.pending.shift()({
          ok: true,
          scxrdPixel: { x: 4, y: 5, value: 123, twoTheta: null },
        }),
      );
      await page.waitForFunction(
        (n) => window.fixture.calls.length === n + 1,
        inFlight,
      );
      assert.deepEqual(
        await page.evaluate(() => window.fixture.calls.at(-1).args),
        { x: 8, y: 9 },
        "intermediate pointer moves coalesce to the latest point",
      );
      await page.evaluate(() =>
        window.fixture.patch({ frame: 1, image: { bufferId: "two" } }),
      );
      await page.waitForTimeout(30);
      await page.evaluate(() =>
        window.fixture.pending.shift()({
          ok: true,
          scxrdPixel: { x: 4, y: 5, value: 999, twoTheta: null },
        }),
      );
      await page.waitForTimeout(120);
      assert.equal(
        await page.evaluate(() => window.fixture.readings.at(-1)),
        null,
        "late response from old frame is discarded",
      );
      await page.evaluate(() => {
        window.fixture.defer = false;
        window.fixture.activate(false);
      });
      await page.waitForTimeout(30);
      const inactive = await page.evaluate(() => window.fixture.calls.length);
      await page.evaluate(() => window.fixture.hover({ x: 2, y: 3 }));
      await page.waitForTimeout(130);
      assert.equal(
        await page.evaluate(() => window.fixture.calls.length),
        inactive,
      );
      await page.evaluate(() => {
        window.fixture.activate(true);
        window.fixture.patch({ frames: 0, image: null });
      });
      await page.waitForTimeout(30);
      await page.evaluate(() => window.fixture.hover({ x: 2, y: 3 }));
      await page.waitForTimeout(130);
      assert.equal(
        await page.evaluate(() => window.fixture.calls.length),
        inactive,
      );
      assert.deepEqual(errors, [], `${name}: no browser failures`);
      console.log(
        `${name}: valid Eiger hover, bounds, empty/legacy reads, frame races and inactive/unloaded modes passed`,
      );
    } finally {
      await browser.close();
    }
  }
} finally {
  await server.close();
}

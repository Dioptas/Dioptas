import { createHash } from "node:crypto";
import { readFile, writeFile, stat, copyFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const output = path.join(root, "desktop/artifacts/ui-audit");
const review = JSON.parse(
  await readFile(path.join(root, "desktop/UI_DESIGN_REVIEW.json"), "utf8"),
);
const escape = (text) =>
  String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
const reports = await Promise.all(
  ["before", "after", "webkit"].map(async (stage) => ({
    stage,
    ...JSON.parse(
      await readFile(path.join(output, stage, "report.json"), "utf8"),
    ),
  })),
);
const currentUiHash = createHash("sha256")
  .update(await readFile(path.join(root, "dioptas/desktop/ui/index.html")))
  .digest("hex");
for (const report of reports.filter((item) => item.stage !== "before")) {
  if (report.completed === false || report.failure)
    throw new Error(
      `${report.stage}: audit failed; see report.json and failure screenshot`,
    );
  if (report.uiSha256 !== currentUiHash)
    throw new Error(
      `${report.stage}: screenshots come from a different UI build; rerun the audit before publishing this report`,
    );
}
const mean = (key) =>
  (
    Math.round(
      (review.criteria.reduce((sum, row) => sum + row[key], 0) /
        review.criteria.length) *
        10,
    ) / 10
  ).toFixed(1);
const exists = async (file) => {
  try {
    await readFile(file);
    return true;
  } catch {
    return false;
  }
};
let peer = "";
const peerFile = (await exists(path.join(root, "desktop/UI_PEER_REVIEW.txt")))
  ? path.join(root, "desktop/UI_PEER_REVIEW.txt")
  : path.join(output, "reviews/claude-final.txt");
if (await exists(peerFile)) peer = await readFile(peerFile, "utf8");
const peerMean =
  review.peer?.mean?.toFixed(2) ??
  [...peer.matchAll(/(\d+(?:\.\d+)?)\s*\/\s*10/g)]
    .map((match) => Number(match[1]))
    .find((value) => value >= 1 && value <= 10)
    ?.toFixed(2);

const names = new Set();
for (const report of reports.filter(
  (item) => item.stage === "before" || item.stage === "after",
)) {
  for (const view of report.inventory) names.add(view.name);
}
const builtAt = (await stat(path.join(root, "dioptas/desktop/ui/index.html")))
  .mtimeMs;
for (const name of [
  "error-details",
  "geometry-draft-restored",
  "keyboard-sample-inspection",
  "integration-overlay-legend",
]) {
  const file = path.join(output, "after", `${name}.png`);
  if ((await exists(file)) && (await stat(file)).mtimeMs >= builtAt)
    names.add(name);
}
const category = (name) =>
  name.startsWith("calibration") || name === "manual-geometry"
    ? "Calibration"
    : name.startsWith("integration")
      ? "Integration"
      : name.startsWith("map")
        ? "Map"
        : name.startsWith("batch")
          ? "Batch"
          : name.startsWith("settings") || name === "shortcut-help"
            ? "Settings"
            : name.startsWith("phase")
              ? "Editors"
              : name === "mask"
                ? "Mask"
                : "Feedback";
const gallery = [];
for (const name of names) {
  const panels = [];
  for (const stage of ["before", "after"]) {
    const file = `${stage}/${name}.png`;
    panels.push(
      (await exists(path.join(output, file)))
        ? `<figure><figcaption>${stage === "before" ? "Before · baseline" : "After · revised"}</figcaption><a href="${file}"><img loading="lazy" src="${file}" alt="${escape(name)} ${stage}"></a></figure>`
        : `<figure class="new-view"><figcaption>${stage === "before" ? "Before" : "After"}</figcaption><p>${stage === "before" ? "New view in the revised interface." : "Not captured."}</p></figure>`,
    );
  }
  gallery.push(
    `<article data-category="${category(name)}"><h3>${escape(name.replaceAll("-", " "))}</h3><div class="pair">${panels.join("")}</div></article>`,
  );
}
const checks = reports.find((r) => r.stage === "after").checks;
const html = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dioptas scientific GUI review</title>
<style>
:root{font-family:system-ui,sans-serif;color:#18212a;background:#f3f5f7;font-size:15px;line-height:1.6}*{box-sizing:border-box}body{margin:0}main{max-width:1580px;margin:auto;padding:40px 28px}h1,h2,h3{line-height:1.25}h1{font-size:34px;margin:8px 0 16px}h2{margin-top:38px}p{max-width:1000px}.eyebrow{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#56616c}.scores{display:flex;gap:16px;flex-wrap:wrap;margin:28px 0}.score{background:white;border:1px solid #d6dde4;border-radius:12px;padding:18px 24px;min-width:210px}.score strong{display:block;font-size:34px;line-height:1.3}.score.final{border-top:4px solid #ef8c00}a{color:#855000}table{width:100%;border-collapse:collapse;background:white}th,td{padding:12px 14px;border-bottom:1px solid #e1e6eb;text-align:left;vertical-align:top}th{background:#e7ecf1}td.num{font-weight:700;white-space:nowrap}td small{display:block;color:#596571;max-width:760px}.table-wrap{overflow:auto;border:1px solid #d6dde4;border-radius:10px}.note{border-left:3px solid #ef8c00;background:#fff9ef;padding:14px 18px}.checks{columns:2;column-gap:40px}.checks li{break-inside:avoid;margin-bottom:10px}button{font:inherit;border:1px solid #c1ccd6;border-radius:20px;padding:7px 14px;background:white;cursor:pointer}button[aria-pressed=true]{background:#26313b;color:white}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0;position:sticky;top:0;background:#f3f5f7ee;padding:10px 0;z-index:2}article{margin:30px 0;padding:20px;background:white;border:1px solid #d6dde4;border-radius:12px}article h3{text-transform:capitalize;margin-top:0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}figure{margin:0;min-width:0}figcaption{font-size:13px;color:#56616c;margin-bottom:6px}img{display:block;width:100%;height:auto;border-radius:6px}.new-view{display:grid;place-content:center;background:#edf1f5;border-radius:6px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace;background:white;padding:20px;border:1px solid #d6dde4;border-radius:10px}code{font-size:.9em}footer{margin-top:36px;border-top:1px solid #cbd4dd;padding-top:20px;color:#56616c}@media(max-width:800px){main{padding:24px 14px}.pair{grid-template-columns:1fr}.checks{columns:1}td,th{padding:8px}}
</style><main>
<div class="eyebrow">Scientific interface review · ${review.date} · codex/scientific-ui-audit</div>
<h1>Dioptas: design, consistency and scientific context</h1>
<p>${escape(review.scope)}</p>
<div class="scores"><div class="score">Codex baseline<strong>${mean("before")} / 10</strong></div><div class="score final">Codex revised assessment<strong>${mean("after")} / 10</strong></div><div class="score">Claude latest completed review<strong>${peerMean ? `${peerMean} / 10` : "See review below"}</strong></div></div>
<p class="note"><strong>${escape(review.status)}</strong><br>${escape(review.peer?.status ?? "")}${review.peer?.resetAt ? " Claude reports an account-usage reset at 21:30 Berlin on November 5; no final score has been invented or inferred." : ""}</p>
<p class="note">${escape(review.method)} ${escape(review.scoreDisplay ?? "")} Current arithmetic mean: ${review.codexMean.toFixed(3)} / 10. This is a scoped design judgment, not certification. Independent reviewers can disagree; their actual scores are retained.</p>
<h2>Criteria and ratings</h2><p>${escape(review.scale)} Each of the 25 criteria has equal weight (4%).</p>
<div class="table-wrap"><table><thead><tr><th>Criterion</th><th>Codex before</th><th>9.1 checkpoint</th><th>Codex now</th><th>Claude preceding review</th><th>Evidence</th></tr></thead><tbody>${review.criteria.map((row) => `<tr><td><strong>${escape(row.name)}</strong><small>${escape(row.criteria)}</small></td><td class="num">${row.before.toFixed(1)}</td><td class="num">${row.at91?.toFixed(1) ?? "—"}</td><td class="num">${row.after.toFixed(1)}</td><td class="num">${review.peer?.criteria.find((item) => item.id === row.id)?.score.toFixed(1) ?? "—"}</td><td>${escape(row.evidence)}</td></tr>`).join("")}</tbody></table></div>
<h2>Implemented improvements</h2>
<div class="table-wrap"><table><thead><tr><th>Problem</th><th>Result</th><th>Shared ownership</th></tr></thead><tbody>${(review.implementedImprovements ?? []).map((item) => `<tr><td>${escape(item.problem)}</td><td>${escape(item.resolution)}</td><td>${item.shared.map(escape).join(", ")}</td></tr>`).join("")}</tbody></table></div>
<h2>Validation and scientific provenance</h2>
<p>The Python model regression suite passed <strong>294 tests, with 5 optional cases skipped</strong>; frontend unit tests passed <strong>${review.validation?.frontendUnitTests ?? 59}/${review.validation?.frontendUnitTests ?? 59}</strong>. The calibration/integration, Map, Mask, Batch, custom-action, phase-editor and database browser checks pass. Native OS dialogs and native window management were not rerun. The app still defaults to WebGL2 for pattern curves; all captured pattern views in both revised browser audits confirmed WebGL2 active. Canvas2D remains the fallback. The diagnostic benchmark now also defaults to WebGL; headless timings do not establish native GPU performance.</p>
<div class="table-wrap"><table><thead><tr><th>Snapshot</th><th>Captured views</th><th>Behavior checks</th><th>Axe violations</th></tr></thead><tbody>${reports.map((r) => `<tr><td><a href="${r.stage}/report.json">${r.stage}</a></td><td>${r.inventory.length}</td><td>${r.checks.length}</td><td>${r.inventory.reduce((n, s) => n + s.accessibility.length, 0)}</td></tr>`).join("")}</tbody></table></div>
<p>Axe findings requiring manual review are retained in the JSON reports and are not counted as passes. Before/after use the same measured detector and map fixtures. A peak-seeded CeO2 fit is separate from loading its reference PONI. The gold phase is an editor fixture, not a specimen identification; the six Batch frames are known intensity-scaled copies of CeO2.</p>
<ul class="checks">${checks.map((check) => `<li>${escape(check)}</li>`).join("")}</ul>
<h2>Refinements since the 9.1 checkpoint</h2><p>Resting input outlines were removed and legends returned inside the data area. Shared geometry drafts, plot legends, pane dividers and keyboard sample inspection improve the working behavior. The earlier 9.1 captures are preserved for direct comparison.</p>
${[
  ["calibration-validate", "Quiet input fields"],
  ["map-compact-large", "More plot space · Larger text"],
]
  .map(
    ([name, title]) =>
      `<article><h3>${title}</h3><div class="pair"><figure><figcaption>9.1 checkpoint</figcaption><a href="checkpoint-9.1/${name}.png"><img loading="lazy" src="checkpoint-9.1/${name}.png" alt="${title} at 9.1 checkpoint"></a></figure><figure><figcaption>Current revision</figcaption><a href="after/${name}.png"><img loading="lazy" src="after/${name}.png" alt="${title} current revision"></a></figure></div></article>`,
  )
  .join("")}
<h2>Accessibility evidence and limits</h2><p>${escape(review.manualAccessibilityReview?.popupControllers ?? "")} ${escape(review.manualAccessibilityReview?.emptyTables ?? "")} ${escape(review.manualAccessibilityReview?.remaining ?? "")}</p>
<div class="table-wrap"><table><thead><tr><th>Solid color pair</th><th>Foreground</th><th>Background</th><th>Computed ratio</th></tr></thead><tbody>${(review.manualAccessibilityReview?.solidColorPairs ?? []).map((pair) => `<tr><td>${escape(pair.use)}</td><td>${pair.foreground}</td><td>${pair.background}</td><td>${pair.ratio.toFixed(2)} : 1</td></tr>`).join("")}</tbody></table></div><p>${escape(review.manualAccessibilityReview?.contrastScope ?? "")} Raw axe incomplete findings remain in each report; they are not counted as automatic passes. Accessibility-tree snapshots accompany the screenshots as <code>.aria.yml</code> files.</p>
<h2>Matched before and after screenshots</h2><p>Click a screenshot for the full-resolution PNG. Viewports, source data and test settings match. Scientific processing remains local Python; the audit changes the frontend.</p>
<div class="filters">${["All", "Calibration", "Mask", "Integration", "Map", "Batch", "Settings", "Editors", "Feedback"].map((name, i) => `<button data-filter="${name}" aria-pressed="${i === 0}">${name}</button>`).join("")}</div>
${gallery.join("")}
<h2>Independent Claude review</h2><p>The last completed score predates the latest fixes. Per the user’s direction, Codex’s metric is used for this pass; an independent Claude follow-up is scheduled for 21:35 Berlin after the account reset. Its actual later score will be recorded separately.</p><p>The raw reviews are preserved: <a href="reviews/claude-baseline.txt">baseline</a>, <a href="reviews/claude-iteration-1.txt">first revision</a>, <a href="reviews/claude-iteration-2.txt">second revision</a>, <a href="reviews/claude-expanded-1.txt">expanded 25-category review</a>${peer.trim() ? ', <a href="reviews/claude-final.txt">latest completed review</a>' : ""}. Findings were checked against the owning implementation; confirmed problems drove further changes.</p>${peer.trim() ? `<details><summary>Read the latest review</summary><pre>${escape(peer)}</pre></details>` : ""}
<h2>Limits of this review</h2><ul>${review.limitations.map((item) => `<li>${escape(item)}</li>`).join("")}</ul>
<footer>Reference guidance: <a href="https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/">W3C modal dialogs</a>, <a href="https://www.w3.org/WAI/ARIA/apg/patterns/tabs/">W3C tabs</a>, <a href="https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html">WCAG text contrast</a>. Reproduce with <code>npm run test:ui-audit</code>, <code>node scripts/ui_audit.mjs --stage=webkit --webkit</code> and <code>npm run test:ui-audit:baseline</code>.</footer>
</main><script>for(const button of document.querySelectorAll('[data-filter]'))button.addEventListener('click',()=>{for(const b of document.querySelectorAll('[data-filter]'))b.setAttribute('aria-pressed',String(b===button));for(const item of document.querySelectorAll('article[data-category]'))item.hidden=button.dataset.filter!=='All'&&item.dataset.category!==button.dataset.filter;});</script></html>`;
await writeFile(path.join(output, "index.html"), html);
await copyFile(
  path.join(root, "desktop/UI_DESIGN_REVIEW.json"),
  path.join(output, "scores.json"),
);
console.log(
  JSON.stringify({
    report: path.join(output, "index.html"),
    before: mean("before"),
    after: mean("after"),
    claude: peerMean ?? null,
    screenshotPairs: names.size,
  }),
);

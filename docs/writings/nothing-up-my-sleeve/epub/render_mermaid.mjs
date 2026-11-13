// Render mermaid diagrams to PNG for the epub, with the mermaid the Atlas reader uses and Playwright's Chromium.
// Usage: node render_mermaid.mjs <mermaid.min.js> <jobs.json>
// jobs.json: [{"src": "<path to .mmd>", "out": "<path to .png>"}, ...]. Run it from packages/ui/apps/app so
// @playwright/test resolves; the Kindle gets PNG because its SVG support is partial.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
const require = createRequire(join(process.cwd(), "package.json")); // resolve from the app, not from this folder
const [mermaidPath, jobsPath] = process.argv.slice(2);
const mermaidJs = readFileSync(mermaidPath, "utf8");
const jobs = JSON.parse(readFileSync(jobsPath, "utf8"));
// The store may hold more than one Playwright, and only one of them has its Chromium downloaded: try each.
import { readdirSync } from "node:fs";
const repo = join(process.cwd(), "..", "..", "..", "..");
const candidates = ["@playwright/test"];
try {
  for (const d of readdirSync(join(repo, "node_modules", ".pnpm")).filter((n) => /^playwright@/.test(n)).sort().reverse())
    candidates.push(join(repo, "node_modules", ".pnpm", d, "node_modules", "playwright"));
} catch {}
let browser = null, lastError = null;
for (const c of candidates) {
  try {
    const { chromium } = require(c);
    browser = await chromium.launch();
    break;
  } catch (e) { lastError = e; }
}
if (!browser) throw lastError;
const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2 });
await page.setContent(`<!doctype html><html><head><style>body{margin:0;background:#fff;font-family:Georgia,serif}#d{display:inline-block;padding:16px}</style></head><body><div id="d"></div></body></html>`);
await page.addScriptTag({ content: mermaidJs });
await page.evaluate(() => mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose", fontFamily: "Georgia, serif", themeVariables: { fontSize: "18px", lineColor: "#000", primaryBorderColor: "#000", primaryTextColor: "#000" } }));
let n = 0;
for (const job of jobs) {
  const src = readFileSync(job.src, "utf8");
  const ok = await page.evaluate(async (s) => {
    try {
      const { svg } = await mermaid.render("m" + Math.random().toString(36).slice(2), s);
      document.getElementById("d").innerHTML = svg;
      // Mermaid gives the svg width:100%, and inside an inline-block that resolves to the 300px default of a
      // replaced element, so until 13 November 2026 every diagram was squeezed to 300px and its lettering
      // with it. Give it the width it was drawn at, up to the width of a Kindle page (536 CSS px, 1072 device
      // px at the 2x this page runs at), so the lettering is the size mermaid set unless the diagram is wider
      // than a page.
      const el = document.querySelector("#d svg");
      const natural = el.viewBox.baseVal.width || el.getBoundingClientRect().width;
      el.style.maxWidth = "none";
      el.style.width = Math.min(natural, 536) + "px";
      el.style.height = "auto";
      el.removeAttribute("height");
      return true;
    } catch (e) { document.getElementById("d").innerHTML = ""; return String(e); }
  }, src);
  if (ok !== true) { console.error(`${job.src}: ${ok}`); continue; }
  await page.locator("#d").screenshot({ path: job.out, type: "png" });
  n += 1;
}
await browser.close();
console.log(`rendered ${n} of ${jobs.length} diagrams`);

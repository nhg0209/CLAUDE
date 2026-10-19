// 프로젝트 한눈에 — Obsidian 노트(MOC/프로젝트 한눈에.md)를 PDF 로 만든다.
//
// Obsidian 밖(Claude 앱 미리보기 등)에서는 수식($…$)·콜아웃·위키링크·그림 경로가
// 그대로 보여 글이 깨진다. 원본은 노트 하나로 두고, 읽기용 PDF 는 여기서 만든다.
//
// 실행:  npm i markdown-it@14.1.0 katex@0.16.11 mermaid@10.9.1 @fontsource/noto-sans-kr@5.1.0 playwright
//        node build_pdf.mjs <위 패키지가 설치된 node_modules 의 상위 폴더>
// 출력:  attachments/overview/project-overview.pdf
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const VAULT = path.resolve(HERE, "..", "..");
const NOTE = path.join(VAULT, "MOC", "프로젝트 한눈에.md");
const OUT = path.join(HERE, "project-overview.pdf");
const MODS = path.resolve(process.argv[2] || ".");
const require = createRequire(path.join(MODS, "package.json"));
const MarkdownIt = require("markdown-it");
const katex = require("katex");
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");
const nm = (p) => pathToFileURL(path.join(MODS, "node_modules", p)).href;

// ── 1. 원문에서 마크다운이 건드리면 안 되는 것을 자리표시자로 뺀다 ──────────
let src = fs.readFileSync(NOTE, "utf8").replace(/^---\n[\s\S]*?\n---\n/, "");
const keep = [];
const hold = (html) => `XKEEP${keep.push(html) - 1}X`;
// 블록 요소(다이어그램·코드·수식 블록·그림)는 따로 표시해서, 마크다운이 감싼 <p> 를 나중에 벗긴다
// (안 벗기면 브라우저가 <p></p><pre> 로 쪼개 빈 문단이 생기고, 제목-다이어그램 묶기가 실패한다)
const holdBlock = (html) => `\n\nXBLOCK${keep.push(html) - 1}X\n\n`;
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const tex = (s, display) => katex.renderToString(s.trim(), { displayMode: display, throwOnError: true, strict: "ignore" });

src = src.replace(/```mermaid\n([\s\S]*?)```/g, (_, body) => holdBlock(`<pre class="mermaid">${esc(body)}</pre>`));
src = src.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, body) => holdBlock(`<pre class="code"><code>${esc(body)}</code></pre>`));
src = src.replace(/`([^`\n]+)`/g, (_, body) => hold(`<code>${esc(body)}</code>`));
src = src.replace(/\$\$([\s\S]+?)\$\$/g, (_, m) => holdBlock(`<div class="math">${tex(m, true)}</div>`));
src = src.replace(/\$([^$\n]+?)\$/g, (_, m) => hold(tex(m, false)));
src = src.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_, target, alias) => hold(`<span class="wl">${esc(alias || target)}</span>`));
src = src.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, p) =>
  holdBlock(`<figure><img src="${pathToFileURL(path.resolve(VAULT, "MOC", p)).href}" alt="${esc(alt)}"></figure>`));

// ── 2. 마크다운 → HTML, 자리표시자 복원, 콜아웃 변환 ───────────────────────
let html = new MarkdownIt({ html: true }).render(src);
html = html.replace(/<p>XBLOCK(\d+)X<\/p>/g, (_, i) => keep[+i]);
html = html.replace(/X(?:KEEP|BLOCK)(\d+)X/g, (_, i) => keep[+i]);
html = html.replace(/<blockquote>\s*<p>\[!(\w+)\]\s*([^\n<]*)(?:\n|<\/p>)/g, (_, type, title) =>
  `<div class="callout ${type}"><div class="callout-title">${title}</div><p>`);
// 콜아웃 안에 blockquote 가 겹치지 않으므로, 열린 콜아웃의 다음 </blockquote> 가 그 짝이다
let out = "", rest = html;
for (;;) {
  const i = rest.indexOf('<div class="callout ');
  if (i < 0) { out += rest; break; }
  const j = rest.indexOf("</blockquote>", i);
  out += rest.slice(0, j) + "</div>";
  rest = rest.slice(j + "</blockquote>".length);
}
html = out.replace(/<p>\s*<\/p>/g, "");

const page = `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="${nm("katex/dist/katex.min.css")}">
<link rel="stylesheet" href="${nm("@fontsource/noto-sans-kr/400.css")}">
<link rel="stylesheet" href="${nm("@fontsource/noto-sans-kr/700.css")}">
<style>
  :root { --ink:#1f2328; --muted:#5b636e; --rule:#d5d9de; --soft:#f4f6f8; --accent:#2f5d8a; }
  html { font-family: "Noto Sans KR", "WenQuanYi Zen Hei", "DejaVu Sans", sans-serif; color: var(--ink);
         font-size: 10pt; line-height: 1.62; }
  body { margin: 0; }
  h1 { font-size: 21pt; margin: 0 0 4mm; letter-spacing: -0.01em; }
  h2 { font-size: 14pt; margin: 9mm 0 3mm; padding-top: 3mm; border-top: 1.2pt solid var(--ink); break-after: avoid; }
  h3 { font-size: 11.5pt; margin: 6mm 0 2mm; color: var(--accent); break-after: avoid; }
  p, li { margin: 0 0 2mm; }
  ul, ol { margin: 0 0 2.5mm; padding-left: 5.5mm; }
  hr { display: none; }
  strong { font-weight: 700; }
  code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.6pt; background: var(--soft); padding: 0 1.2pt; border-radius: 2pt; }
  pre.code { background: var(--soft); border: 0.6pt solid var(--rule); padding: 2.5mm 3mm; font-size: 8.6pt;
             line-height: 1.45; white-space: pre-wrap; break-inside: avoid; margin: 0 0 3mm; }
  pre.code code { background: none; padding: 0; }
  table { border-collapse: collapse; width: 100%; margin: 1mm 0 4mm; font-size: 8.9pt; line-height: 1.45; }
  th, td { border: 0.6pt solid var(--rule); padding: 1.3mm 2mm; text-align: left; vertical-align: top; }
  th { background: var(--soft); font-weight: 700; }
  tr { break-inside: avoid; }
  .math { margin: 2mm 0 3mm; overflow-x: auto; }
  .katex { font-size: 1.06em; }
  figure { margin: 3mm 0 4mm; text-align: center; break-inside: avoid; }
  figure img { max-width: 100%; max-height: 105mm; }
  pre.mermaid { text-align: center; margin: 3mm 0 4mm; break-inside: avoid; background: none; border: 0; }
  pre.mermaid svg { max-width: 100% !important; height: auto; max-height: 215mm; }
  .keep { break-inside: avoid; }
  .wl { color: var(--accent); }
  .callout { border-left: 2.4pt solid var(--accent); background: #f6f8fa; padding: 2.2mm 3.5mm 0.6mm; margin: 0 0 4mm;
             break-inside: avoid; }
  .callout-title { font-weight: 700; margin-bottom: 1.2mm; }
  .callout.warning, .callout.danger { border-left-color: #b8860b; background: #fbf8ef; }
  .callout.important { border-left-color: #8a3b2f; background: #fbf5f3; }
  .callout.tip { border-left-color: #2e7d4f; background: #f3f8f4; }
</style></head><body>${html}
<script src="${nm("mermaid/dist/mermaid.min.js")}"></script>
<script>
  mermaid.initialize({ startOnLoad: false, theme: "neutral",
    themeVariables: { fontFamily: '"Noto Sans KR", "WenQuanYi Zen Hei", sans-serif', fontSize: "15px" },
    flowchart: { useMaxWidth: true, htmlLabels: true } });
  // 제목이 페이지 끝에 홀로 남지 않게 — 제목(연속된 제목 포함)을 바로 뒤의 그림·다이어그램·수식·콜아웃과 묶는다
  function keepHeadings() {
    const solid = (el) => el && el.matches("figure, pre.mermaid, pre.code, div.math, div.callout");
    for (const h of [...document.querySelectorAll("body > h2, body > h3")]) {
      if (h.parentElement !== document.body) continue;
      const group = [h];
      let n = h.nextElementSibling;
      while (n && /^H[23]$/.test(n.tagName)) { group.push(n); n = n.nextElementSibling; }
      if (!solid(n)) continue;
      group.push(n);
      const box = document.createElement("div");
      box.className = "keep";
      h.before(box);
      group.forEach((el) => box.appendChild(el));
    }
  }
  mermaid.run({ querySelector: "pre.mermaid" }).then(keepHeadings).then(() => document.fonts.ready)
    .then(() => { window.__done = true; });
</script></body></html>`;

// ── 3. Chromium 으로 PDF ─────────────────────────────────────────────
const tmp = path.join(MODS, "overview.html");
fs.writeFileSync(tmp, page);
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || "/opt/pw-browsers/chromium" });
const tab = await browser.newPage();
const errors = [];
tab.on("pageerror", (e) => errors.push(e.message));
tab.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await tab.goto(pathToFileURL(tmp).href);
await tab.waitForFunction(() => window.__done === true, null, { timeout: 60000 });
await tab.pdf({
  path: OUT, format: "A4", printBackground: true,
  margin: { top: "16mm", bottom: "16mm", left: "16mm", right: "16mm" },
  displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate: `<div style="width:100%;font-size:7.5pt;color:#888;padding:0 16mm;display:flex;justify-content:space-between;
    font-family:'WenQuanYi Zen Hei',sans-serif"><span>프로젝트 한눈에 · 2026-10-19 기준</span>
    <span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
});
await browser.close();
if (errors.length) { console.error("페이지 오류:\n" + errors.join("\n")); process.exit(1); }
console.log("wrote", OUT);

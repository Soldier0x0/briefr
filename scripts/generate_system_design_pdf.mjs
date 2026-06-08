/**
 * Regenerate SYSTEM_DESIGN.pdf from SYSTEM_DESIGN.md with proper tables,
 * rendered Mermaid diagrams, and print-safe layout (Playwright).
 *
 * Usage (from repo root):
 *   node scripts/generate_system_design_pdf.mjs
 */
import { readFile, writeFile, unlink } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { createRequire } from 'module';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, '..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const { chromium } = require('playwright');

const MD_PATH = path.join(root, 'SYSTEM_DESIGN.md');
const PDF_PATH = path.join(root, 'SYSTEM_DESIGN.pdf');
const DIAGRAMS_DIR = path.join(root, 'docs/diagrams');

const MERMAID_LINK_RE =
  /(?:Sequence diagram|Flowchart):\s*\[`([^`]+\.mermaid)`\]\([^)]+\)/g;
const MERMAID_SOURCE_LINE_RE =
  /\nMermaid source: \[`[^`]+\.mermaid`\]\([^)]+\)\n?/g;

const ASCII_DIAGRAM_RE =
  /### ASCII architecture diagram\s*```[\s\S]*?```/m;

async function readMermaid(filename) {
  const filePath = path.join(DIAGRAMS_DIR, path.basename(filename));
  return (await readFile(filePath, 'utf8')).trim();
}

async function preprocessMarkdown(md) {
  let out = md;

  // Wide ASCII boxes break in PDF — use the Mermaid architecture diagram instead.
  const architecture = await readMermaid('architecture.mermaid');
  out = out.replace(
    ASCII_DIAGRAM_RE,
    '### Architecture diagram\n\n```mermaid\n' + architecture + '\n```',
  );
  out = out.replace(MERMAID_SOURCE_LINE_RE, '\n');

  // Inline sequence / flowchart .mermaid files as renderable blocks.
  const seen = new Set();
  for (const match of md.matchAll(MERMAID_LINK_RE)) {
    const rel = match[1];
    if (seen.has(rel)) continue;
    seen.add(rel);
    const source = await readMermaid(rel);
    const label = path.basename(rel, '.mermaid').replace(/_/g, ' ');
    out = out.replace(
      match[0],
      `**${label}**\n\n\`\`\`mermaid\n${source}\n\`\`\``,
    );
  }

  return out;
}

function buildPrintHtml(bodyHtml, title) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${title}</title>
  <style>
    @page { size: A4; margin: 18mm 16mm; }
    * { box-sizing: border-box; }
    body {
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      font-size: 10.5pt;
      line-height: 1.55;
      color: #111;
      max-width: 100%;
      margin: 0;
      padding: 0;
    }
    h1 { font-size: 22pt; margin: 0 0 0.4em; page-break-after: avoid; }
    h2 {
      font-size: 15pt;
      margin: 1.6em 0 0.5em;
      padding-top: 0.2em;
      border-top: 2px solid #e5e5e5;
      page-break-after: avoid;
    }
    h3 { font-size: 12pt; margin: 1.2em 0 0.4em; page-break-after: avoid; }
    p, li { orphans: 3; widows: 3; }
    a { color: #0b57d0; text-decoration: none; }
    code {
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 0.9em;
      background: #f4f4f5;
      padding: 0.1em 0.35em;
      border-radius: 3px;
    }
    pre {
      background: #f8f8f8;
      border: 1px solid #e4e4e7;
      border-radius: 6px;
      padding: 10px 12px;
      overflow-x: auto;
      font-size: 8.5pt;
      line-height: 1.35;
      page-break-inside: avoid;
    }
    pre code { background: none; padding: 0; }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 0.8em 0 1.2em;
      font-size: 9pt;
      page-break-inside: avoid;
    }
    th, td {
      border: 1px solid #d4d4d8;
      padding: 6px 8px;
      vertical-align: top;
      text-align: left;
    }
    th { background: #f4f4f5; font-weight: 600; }
    tr:nth-child(even) td { background: #fafafa; }
    ul, ol { margin: 0.4em 0 0.8em; padding-left: 1.4em; }
    hr { border: none; border-top: 1px solid #e5e5e5; margin: 1.5em 0; }
    .mermaid {
      margin: 1em 0 1.4em;
      text-align: center;
      page-break-inside: avoid;
    }
    .mermaid svg { max-width: 100% !important; height: auto !important; }
    .cover-meta { color: #52525b; margin-bottom: 1.5em; font-size: 10pt; }
  </style>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    mermaid.initialize({
      startOnLoad: false,
      theme: 'neutral',
      securityLevel: 'loose',
      flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' },
    });
    window.renderMermaid = async () => {
      const blocks = [...document.querySelectorAll('pre code.language-mermaid')];
      for (const block of blocks) {
        const parent = block.parentElement;
        const div = document.createElement('div');
        div.className = 'mermaid';
        div.textContent = block.textContent;
        parent.replaceWith(div);
      }
      await mermaid.run({ querySelector: '.mermaid' });
      window.mermaidDone = true;
    };
    renderMermaid().catch((err) => {
      console.error(err);
      window.mermaidDone = true;
    });
  </script>
  <script src="https://cdn.jsdelivr.net/npm/marked@15/marked.min.js"></script>
</head>
<body>
  <div id="content"></div>
  <script>
    const raw = ${JSON.stringify(bodyHtml)};
    document.getElementById('content').innerHTML = marked.parse(raw, {
      gfm: true,
      breaks: false,
    });
    // marked wraps mermaid in <pre><code class="language-mermaid"> — renderMermaid upgrades them.
    if (document.querySelectorAll('pre code.language-mermaid').length === 0) {
      window.mermaidDone = true;
    }
  </script>
</body>
</html>`;
}

async function main() {
  const md = await preprocessMarkdown(await readFile(MD_PATH, 'utf8'));
  const tmpHtml = path.join(__dirname, '.system_design_print.html');

  // Pass markdown into the HTML shell; marked runs in the browser.
  const shell = buildPrintHtml(md, 'BRIEFR System Design');
  await writeFile(tmpHtml, shell);

  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(`file://${tmpHtml}`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => window.mermaidDone === true, { timeout: 120_000 });

    await page.pdf({
      path: PDF_PATH,
      format: 'A4',
      printBackground: true,
      margin: { top: '18mm', bottom: '18mm', left: '16mm', right: '16mm' },
    });
    console.log(`Wrote ${PDF_PATH}`);
  } finally {
    await browser.close();
    if (process.env.KEEP_PDF_HTML) {
      console.log(`Debug HTML: ${tmpHtml}`);
    } else {
      await unlink(tmpHtml).catch(() => {});
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

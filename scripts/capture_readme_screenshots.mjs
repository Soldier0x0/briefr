import { chromium } from 'playwright';
import { mkdir } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, '..', 'screenshots');
const baseUrl = 'http://localhost:5173';

async function shot(page, name) {
  const file = path.join(outDir, name);
  await page.screenshot({ path: file, fullPage: true });
  console.log('Wrote', file);
}

async function clickTab(page, label) {
  await page.getByRole('button', { name: new RegExp(label, 'i') }).click();
  await page.waitForTimeout(800);
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: 'dark',
  });
  const page = await context.newPage();

  // Default BRIEFR theme is dark; clear any persisted light preference.
  await page.addInitScript(() => {
    try {
      localStorage.removeItem('briefr_theme');
      document.documentElement.removeAttribute('data-theme');
    } catch {}
  });

  await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 120000 });

  // BRIEF tab (default feed)
  await page.waitForSelector('.cve-card, .cve-feed-list, .content-grid', { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await shot(page, 'brief.png');

  // IOC LOOKUP
  await clickTab(page, 'IOC LOOKUP');
  await page.waitForSelector('.ioc-lookup, .ioc-panel, [class*="ioc"]', { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await shot(page, 'ioc-lookup.png');

  // INCIDENTS & NEWS
  await clickTab(page, 'INCIDENTS');
  await page.waitForSelector('.case-studies, .cs-card, .cs-hero', { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(2500);
  await shot(page, 'incidents-news.png');

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

/**
 * Capture BRIEF tab in dark + light for theme audit (before/after).
 * Requires backend :8000 and frontend :5173.
 */
import { createRequire } from 'module';
import { mkdir } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, '../frontend/package.json'));
const { chromium } = require('playwright');
const outDir = path.join(__dirname, '..', 'docs', 'assets', 'screenshots', 'theme-audit');
const baseUrl = 'http://localhost:5173';

async function assertStyled(page) {
  const ok = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    return root.getPropertyValue('--red').trim() === '#e85533';
  });
  if (!ok) throw new Error('CSS not applied (check CSP / Vite). --red token missing.');
}

async function waitForApp(page) {
  await page.waitForSelector('.header, .hero, .stats-row', { timeout: 60000 });
  await page.waitForSelector('.cve-card, .cve-feed-list, .content-grid', { timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await assertStyled(page);
  await page.waitForTimeout(1500);
}

async function setTheme(page, theme) {
  await page.evaluate((t) => {
    if (t === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
      try { localStorage.setItem('briefr_theme', 'light'); } catch {}
    } else {
      document.documentElement.removeAttribute('data-theme');
      try { localStorage.removeItem('briefr_theme'); } catch {}
    }
  }, theme);
}

async function shot(page, name) {
  const file = path.join(outDir, name);
  await page.screenshot({ path: file, fullPage: false });
  console.log('Wrote', file);
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 120000 });
  await waitForApp(page);

  await setTheme(page, 'dark');
  await page.reload({ waitUntil: 'networkidle' });
  await waitForApp(page);
  await shot(page, 'brief-dark.png');

  await setTheme(page, 'light');
  await page.reload({ waitUntil: 'networkidle' });
  await waitForApp(page);
  await shot(page, 'brief-light.png');

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

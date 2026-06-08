import { createRequire } from 'module';
import { mkdir } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, '../frontend/package.json'));
const { chromium } = require('playwright');
const outDir = path.join(__dirname, '..', 'screenshots');
const baseUrl = 'http://localhost:5173';

const VIEWPORT = { width: 1440, height: 900 };

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function shot(page, name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(300);
  const file = path.join(outDir, name);
  // Viewport only — BRIEF feed uses infinite scroll; fullPage would produce an unusably tall image.
  await page.screenshot({ path: file, fullPage: false });
  console.log('Wrote', file);
}

async function clickTab(page, label) {
  await page.getByRole('button', { name: new RegExp(label, 'i') }).click();
  await sleep(800);
}

async function waitForIncidentsContent(page) {
  await page.waitForSelector('.cs-hero', { timeout: 60000 });
  await page.waitForFunction(
    () => {
      const cards = document.querySelectorAll('.cs-card');
      const skeleton = document.querySelector('.cs-skeleton-list');
      const hasError = !!document.querySelector('.cs-source-error');
      const isEmpty = !!document.querySelector('.cs-empty');
      return (cards.length > 0 && !skeleton) || hasError || isEmpty;
    },
    { timeout: 120000 },
  );

  const failureMessage = await page.evaluate(() => {
    const error = document.querySelector('.cs-source-error');
    const empty = document.querySelector('.cs-empty');
    if (error) return `Feed error: ${error.textContent.trim()}`;
    if (empty) return 'Feed is empty';
    return null;
  });
  if (failureMessage) {
    throw new Error(failureMessage);
  }

  // RSS + ATLAS aggregation can take several seconds after the shell renders.
  await sleep(5000);
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
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
  await page.evaluate(() => document.fonts.ready);
  await page.waitForSelector('.header .header-logo-btn', { timeout: 60000 });

  // BRIEF tab (default feed) — require styled UI, not unstyled HTML
  await page.waitForSelector('.cve-card, .cve-feed-list, .content-grid', { timeout: 60000 });
  const styled = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    return root.getPropertyValue('--red').trim() === '#e85533';
  });
  if (!styled) {
    throw new Error('CSS not applied (check CSP / Vite). --red token missing.');
  }
  await sleep(2500);
  await shot(page, 'brief.png');

  // IOC LOOKUP
  await clickTab(page, 'IOC LOOKUP');
  await page.waitForSelector('.ioc-lookup, .ioc-panel, [class*="ioc"]', { timeout: 30000 });
  await sleep(1500);
  await shot(page, 'ioc-lookup.png');

  // INCIDENTS & NEWS — wait for loaded cards, then extra settle time for RSS/ATLAS feed
  await clickTab(page, 'INCIDENTS');
  await waitForIncidentsContent(page);
  await shot(page, 'incidents-news.png');

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

import { createRequire } from 'module';
import { mkdir } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, '../frontend/package.json'));
const { chromium } = require('playwright');
const outDir = path.join(__dirname, '..', 'docs', 'assets', 'screenshots');
const baseUrl = 'http://localhost:5173';
const apiUrl = 'http://127.0.0.1:8000';

const VIEWPORT = { width: 1440, height: 900 };

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`${url} returned ${res.status}`);
  }
  return res.json();
}

async function preflightBackend() {
  await fetchJson(`${apiUrl}/api/health`);

  const health = await fetchJson(`${apiUrl}/api/health`);
  const cveCount = Number(health?.cve_count ?? 0);
  if (!cveCount) {
    throw new Error(
      'Backend has 0 CVEs — run: python3 scripts/seed_screenshot_data.py (with backend stopped or after fresh DB)',
    );
  }
  console.log(`Backend preflight OK — ${cveCount} CVEs in database`);

  const feed = await fetchJson(`${apiUrl}/api/case-studies/feed?atlas_limit=20`);
  const locked = (feed.errors || []).filter((e) =>
    String(e.message || '').toLowerCase().includes('database is locked'),
  );
  if (locked.length) {
    throw new Error(`Incidents feed reports database lock: ${JSON.stringify(locked)}`);
  }
  const newsCount = (feed.data || []).filter((c) => c.kind === 'news').length;
  if (!newsCount) {
    throw new Error(
      'Incidents feed has no RSS news cards — check network access and RSS sources',
    );
  }
  console.log(
    `Incidents feed preflight OK — ${newsCount} news cards, ${(feed.data || []).length} total`,
  );
}

async function shot(page, name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(300);
  const file = path.join(outDir, name);
  await page.screenshot({ path: file, fullPage: false });
  console.log('Wrote', file);
}

async function clickTab(page, label) {
  await page.getByRole('button', { name: new RegExp(label, 'i') }).click();
  await sleep(800);
}

async function waitForBriefFeed(page) {
  await page.waitForSelector('.stats-row, .cve-feed-list', { timeout: 60000 });
  await page.waitForFunction(
    () => document.querySelectorAll('.cve-card').length > 0,
    { timeout: 120000 },
  );
  const stats = await page.evaluate(() => {
    const critical = document.querySelector('.stat-critical .stat-value, [class*="stat"]');
    return {
      cards: document.querySelectorAll('.cve-card').length,
      criticalText: critical?.textContent?.trim() || '',
    };
  });
  if (!stats.cards) {
    throw new Error('BRIEF tab has no CVE cards');
  }
  console.log(`BRIEF tab ready — ${stats.cards} CVE cards visible`);
  await sleep(2000);
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

  const state = await page.evaluate(() => {
    const errors = [...document.querySelectorAll('.cs-source-error')].map((el) =>
      el.textContent.trim(),
    );
    const empty = document.querySelector('.cs-empty');
    const newsBadges = [...document.querySelectorAll('.cs-source-badge')]
      .map((el) => el.textContent.trim())
      .filter((label) => label && label !== 'MITRE ATLAS');
    return {
      errors,
      empty: empty?.textContent?.trim() || null,
      newsBadges,
      cardCount: document.querySelectorAll('.cs-card').length,
    };
  });

  const locked = state.errors.filter((msg) => /database is locked/i.test(msg));
  if (locked.length) {
    throw new Error(`Incidents tab shows database lock: ${locked.join('; ')}`);
  }
  if (state.errors.length) {
    throw new Error(`Incidents tab feed errors: ${state.errors.join('; ')}`);
  }
  if (state.empty) {
    throw new Error(state.empty);
  }
  if (!state.newsBadges.length) {
    throw new Error('Incidents tab has no RSS news source badges (only ATLAS?)');
  }
  console.log(
    `Incidents tab ready — ${state.cardCount} cards, sources: ${state.newsBadges.slice(0, 4).join(', ')}…`,
  );

  await sleep(3000);
}

async function main() {
  await preflightBackend();
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    colorScheme: 'dark',
  });
  const page = await context.newPage();

  await page.addInitScript(() => {
    try {
      localStorage.removeItem('briefr_theme');
      document.documentElement.removeAttribute('data-theme');
    } catch {}
  });

  await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 120000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForSelector('.header .header-logo-btn', { timeout: 60000 });

  const styled = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    return root.getPropertyValue('--red').trim() === '#e85533';
  });
  if (!styled) {
    throw new Error('CSS not applied (check CSP / Vite). --red token missing.');
  }

  await waitForBriefFeed(page);
  await shot(page, 'brief.png');

  await clickTab(page, 'IOC LOOKUP');
  await page.waitForSelector('.ioc-lookup, .ioc-panel, [class*="ioc"]', { timeout: 30000 });
  await sleep(1500);
  await shot(page, 'ioc-lookup.png');

  await clickTab(page, 'INCIDENTS');
  await waitForIncidentsContent(page);
  await shot(page, 'incidents-news.png');

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
